#!/usr/bin/env python3
"""
建立 Sentry 測試情境
模擬不同類型的錯誤和情況，讓您在 Sentry Dashboard 中看到效果
"""

import sys
import os
import time
import traceback
from datetime import datetime

# 添加專案根目錄到路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from src.namecard.core.version import version_manager
    from src.namecard.core.services.monitoring import (
        monitoring_service, MonitoringEvent, EventCategory, MonitoringLevel,
        PerformanceMetric
    )
except ImportError as e:
    print(f"❌ 無法匯入必要模組: {e}")
    sys.exit(1)

# 初始化 Sentry（如果有設定）
try:
    import sentry_sdk
    from simple_config import settings
    
    if settings.sentry_dsn:
        from sentry_sdk.integrations.flask import FlaskIntegration
        
        # 獲取版本資訊
        sentry_release_info = version_manager.get_sentry_release_info()
        
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            release=sentry_release_info["release"],
            environment=sentry_release_info["environment"],
            dist=sentry_release_info["dist"],
            traces_sample_rate=1.0,  # 測試時設為 100%
            send_default_pii=False
        )
        
        print(f"✅ Sentry 已初始化")
        print(f"   Release: {sentry_release_info['release']}")
        print(f"   Environment: {sentry_release_info['environment']}")
        SENTRY_ENABLED = True
    else:
        print("⚠️ 沒有設定 SENTRY_DSN，將只模擬測試")
        SENTRY_ENABLED = False
        
except ImportError:
    print("⚠️ Sentry SDK 未安裝")
    SENTRY_ENABLED = False


def scenario_1_namecard_processing_error():
    """情境 1: 名片處理錯誤"""
    print("\n📋 情境 1: 模擬名片處理錯誤")
    
    try:
        if SENTRY_ENABLED:
            with sentry_sdk.configure_scope() as scope:
                scope.set_tag("test_scenario", "namecard_processing")
                scope.set_user({"id": "test_user_001", "username": "test_user"})
                scope.set_context("namecard_processing", {
                    "image_size": "2.5MB",
                    "image_format": "JPEG",
                    "processing_time": 3.2,
                    "confidence_threshold": 0.3
                })
                scope.add_breadcrumb(
                    message="開始處理名片圖片",
                    category="ai_processing",
                    data={"image_size": "2.5MB"}
                )
                scope.add_breadcrumb(
                    message="Google Gemini API 呼叫",
                    category="api_call",
                    data={"api": "gemini-1.5-flash", "timeout": 30}
                )
        
        # 模擬 AI 處理失敗
        raise ConnectionError("Google Gemini API 連線逾時 - 這是測試錯誤")
        
    except Exception as e:
        if SENTRY_ENABLED:
            sentry_sdk.capture_exception(e)
        monitoring_service.capture_exception_with_context(
            e,
            EventCategory.AI_PROCESSING,
            user_id="test_user_001",
            extra_context={
                "scenario": "namecard_processing_failure",
                "image_size": 2621440,  # 2.5MB
                "api_timeout": 30
            }
        )
        print("✅ 已發送：名片處理錯誤")


def scenario_2_notion_storage_error():
    """情境 2: Notion 儲存錯誤"""
    print("\n💾 情境 2: 模擬 Notion 儲存錯誤")
    
    try:
        if SENTRY_ENABLED:
            with sentry_sdk.configure_scope() as scope:
                scope.set_tag("test_scenario", "notion_storage")
                scope.set_user({"id": "test_user_002", "username": "batch_user"})
                scope.set_context("notion_operation", {
                    "database_id": "abc123-def456-ghi789",
                    "operation": "batch_save",
                    "cards_count": 5,
                    "retry_count": 2
                })
                scope.add_breadcrumb(
                    message="開始批次儲存名片",
                    category="data_storage",
                    data={"cards_count": 5}
                )
        
        # 模擬 Notion API 權限錯誤
        raise PermissionError("Notion API 權限不足：無法寫入資料庫 - 這是測試錯誤")
        
    except Exception as e:
        if SENTRY_ENABLED:
            sentry_sdk.capture_exception(e)
        monitoring_service.capture_exception_with_context(
            e,
            EventCategory.DATA_STORAGE,
            user_id="test_user_002",
            extra_context={
                "scenario": "notion_permission_denied",
                "database_id": "test_database_123",
                "cards_count": 5
            }
        )
        print("✅ 已發送：Notion 儲存錯誤")


def scenario_3_line_webhook_error():
    """情境 3: LINE Webhook 錯誤"""
    print("\n📱 情境 3: 模擬 LINE Webhook 錯誤")
    
    try:
        if SENTRY_ENABLED:
            with sentry_sdk.configure_scope() as scope:
                scope.set_tag("test_scenario", "line_webhook")
                scope.set_context("line_webhook", {
                    "signature": "invalid_signature_123",
                    "message_type": "image",
                    "user_id": "U1234567890abcdef",
                    "source_type": "user"
                })
                scope.add_breadcrumb(
                    message="收到 LINE Webhook 請求",
                    category="webhook",
                    data={"signature_valid": False}
                )
        
        # 模擬 Webhook 簽章驗證失敗
        raise ValueError("LINE Webhook 簽章驗證失敗 - 這是測試錯誤")
        
    except Exception as e:
        if SENTRY_ENABLED:
            sentry_sdk.capture_exception(e)
        monitoring_service.capture_exception_with_context(
            e,
            EventCategory.LINE_BOT,
            user_id="U1234567890abcdef",
            extra_context={
                "scenario": "webhook_signature_failure",
                "signature_provided": True,
                "signature_valid": False
            }
        )
        print("✅ 已發送：LINE Webhook 錯誤")


def scenario_4_performance_issue():
    """情境 4: 效能問題"""
    print("\n⚡ 情境 4: 模擬效能問題")
    
    # 模擬慢速操作
    start_time = time.time()
    time.sleep(2)  # 模擬 2 秒的慢操作
    duration = time.time() - start_time
    
    # 記錄效能指標
    metric = PerformanceMetric(
        operation="slow_image_processing",
        duration=duration,
        success=False,  # 標記為失敗
        user_id="test_user_003",
        metadata={
            "test_scenario": "performance_issue",
            "image_size": "8MB",
            "timeout_threshold": 5.0,
            "actual_duration": duration
        }
    )
    
    monitoring_service.track_performance(metric)
    
    if SENTRY_ENABLED:
        sentry_sdk.capture_message(
            f"慢速操作偵測：圖片處理耗時 {duration:.2f} 秒",
            level="warning"
        )
    
    print(f"✅ 已發送：效能問題警告 (耗時 {duration:.2f}s)")


def scenario_5_security_alert():
    """情境 5: 安全警報"""
    print("\n🔒 情境 5: 模擬安全警報")
    
    if SENTRY_ENABLED:
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag("test_scenario", "security_alert")
            scope.set_tag("security_risk", "high")
            scope.set_context("security_event", {
                "source_ip": "192.168.1.100",
                "user_agent": "suspicious_bot_v1.0",
                "failed_attempts": 10,
                "time_window": "5_minutes"
            })
    
    monitoring_service.capture_event(MonitoringEvent(
        category=EventCategory.SECURITY,
        level=MonitoringLevel.CRITICAL,
        message="偵測到可疑活動：多次失敗的認證嘗試",
        extra_data={
            "scenario": "security_threat",
            "source_ip": "192.168.1.100",
            "failed_attempts": 10,
            "time_window": "5min",
            "risk_level": "high"
        },
        tags={
            "security_issue": "brute_force",
            "risk_level": "high",
            "auto_detected": "true"
        }
    ))
    
    if SENTRY_ENABLED:
        sentry_sdk.capture_message(
            "安全警報：偵測到暴力破解攻擊",
            level="fatal"
        )
    
    print("✅ 已發送：安全警報")


def scenario_6_business_metric():
    """情境 6: 業務指標事件"""
    print("\n📊 情境 6: 模擬業務指標事件")
    
    monitoring_service.capture_event(MonitoringEvent(
        category=EventCategory.USER_BEHAVIOR,
        level=MonitoringLevel.INFO,
        message="用戶活躍度異常增長",
        user_id="analytics_system",
        extra_data={
            "scenario": "business_spike",
            "daily_active_users": 500,
            "normal_range": "50-100",
            "growth_rate": "400%",
            "period": "last_24h"
        },
        tags={
            "metric_type": "user_engagement",
            "anomaly": "positive_spike",
            "alert_threshold": "300%"
        }
    ))
    
    if SENTRY_ENABLED:
        sentry_sdk.capture_message(
            "業務指標警報：用戶活躍度異常增長 400%",
            level="info"
        )
    
    print("✅ 已發送：業務指標事件")


def scenario_7_deployment_event():
    """情境 7: 部署事件"""
    print("\n🚀 情境 7: 模擬部署事件")
    
    # 標記新的部署
    monitoring_service.mark_deployment(
        environment="production",
        url="https://namecard-app.zeabur.app"
    )
    
    if SENTRY_ENABLED:
        sentry_sdk.capture_message(
            f"新版本部署完成：{version_manager.release_name}",
            level="info"
        )
    
    print(f"✅ 已發送：部署事件 ({version_manager.release_name})")


def scenario_8_ai_confidence_issue():
    """情境 8: AI 信心度問題"""
    print("\n🤖 情境 8: 模擬 AI 信心度問題")
    
    if SENTRY_ENABLED:
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag("test_scenario", "ai_confidence")
            scope.set_context("ai_processing", {
                "model": "gemini-1.5-flash",
                "confidence_score": 0.15,
                "quality_score": 0.12,
                "min_threshold": 0.3,
                "cards_detected": 1
            })
    
    monitoring_service.capture_event(MonitoringEvent(
        category=EventCategory.AI_PROCESSING,
        level=MonitoringLevel.WARNING,
        message="AI 識別信心度過低，建議用戶重新拍攝",
        user_id="test_user_004",
        extra_data={
            "scenario": "low_confidence",
            "confidence_score": 0.15,
            "quality_score": 0.12,
            "threshold": 0.3,
            "recommendation": "retake_photo"
        },
        tags={
            "ai_issue": "low_confidence",
            "user_action_needed": "true"
        }
    ))
    
    print("✅ 已發送：AI 信心度警告")


def main():
    """執行所有測試情境"""
    print("🎯 Sentry 測試情境生成器")
    print(f"⏰ 執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🏷️ Release: {version_manager.release_name}")
    print("=" * 60)
    
    # 執行所有情境
    scenarios = [
        scenario_1_namecard_processing_error,
        scenario_2_notion_storage_error,
        scenario_3_line_webhook_error,
        scenario_4_performance_issue,
        scenario_5_security_alert,
        scenario_6_business_metric,
        scenario_7_deployment_event,
        scenario_8_ai_confidence_issue
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        try:
            scenario()
            time.sleep(0.5)  # 稍微延遲避免過快發送
        except Exception as e:
            print(f"❌ 情境 {i} 執行失敗: {e}")
    
    print("\n" + "=" * 60)
    print("✅ 所有測試情境已執行完成！")
    print()
    print("📊 在 Sentry Dashboard 中您應該能看到：")
    print(f"   🏷️ Release: {version_manager.release_name}")
    print("   🔍 8 個不同類型的測試事件")
    print("   📈 各種錯誤分類和標籤")
    print("   🎯 完整的 stack trace 和上下文")
    print("   ⚡ 效能指標和警報")
    print()
    print("🔗 檢查 Sentry Dashboard:")
    print("   https://sentry.io")
    print("   Issues → 查看所有錯誤")
    print("   Performance → 查看效能指標")
    print("   Releases → 查看版本資訊")
    
    if SENTRY_ENABLED:
        print("\n💡 提示：Sentry 事件可能需要 1-3 分鐘才會出現在 Dashboard 中")
    else:
        print("\n⚠️ Sentry 未完全設定，部分事件僅記錄到本地日誌")


if __name__ == "__main__":
    main()