#!/usr/bin/env python3
"""
Sentry 監控功能測試腳本
測試所有監控事件和警報機制
"""

import sys
import os
import time
from datetime import datetime

# 添加專案根目錄到路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.namecard.core.services.monitoring import (
    monitoring_service, MonitoringEvent, EventCategory, MonitoringLevel,
    monitor_performance, monitor_ai_processing, PerformanceMetric
)


def test_basic_monitoring():
    """測試基本監控功能"""
    print("🧪 測試基本監控功能...")
    
    # 測試不同級別的事件
    test_events = [
        (MonitoringLevel.INFO, "System startup completed"),
        (MonitoringLevel.WARNING, "High memory usage detected"),
        (MonitoringLevel.ERROR, "Database connection failed"),
        (MonitoringLevel.CRITICAL, "Service completely unavailable")
    ]
    
    for level, message in test_events:
        event = MonitoringEvent(
            category=EventCategory.SYSTEM_PERFORMANCE,
            level=level,
            message=message,
            user_id="test_user_123",
            extra_data={"test": True, "timestamp": datetime.now().isoformat()},
            tags={"test_type": "basic_monitoring", "severity": level.value}
        )
        
        monitoring_service.capture_event(event)
        print(f"   ✅ {level.value.upper()}: {message}")
        time.sleep(0.5)


def test_performance_monitoring():
    """測試效能監控"""
    print("\n🚀 測試效能監控...")
    
    # 模擬不同操作的效能指標
    operations = [
        ("ai_processing", 2.5, True),
        ("notion_save", 1.2, True),
        ("image_upload", 0.8, True),
        ("slow_operation", 8.0, False),  # 慢操作
        ("failed_operation", 0.1, False)  # 失敗操作
    ]
    
    for operation, duration, success in operations:
        metric = PerformanceMetric(
            operation=operation,
            duration=duration,
            success=success,
            user_id="test_user_456",
            metadata={
                "test": True,
                "simulated": True,
                "operation_details": f"Test {operation}"
            }
        )
        
        monitoring_service.track_performance(metric)
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"   {status} {operation}: {duration}s")
        time.sleep(0.3)


def test_ai_processing_monitoring():
    """測試 AI 處理監控"""
    print("\n🤖 測試 AI 處理監控...")
    
    @monitor_ai_processing
    def mock_ai_processing(image_size: int, user_id: str):
        """模擬 AI 處理"""
        if image_size > 5000000:  # 5MB
            raise Exception("Image too large for processing")
        
        time.sleep(1)  # 模擬處理時間
        return {"cards": 2, "confidence": 0.95}
    
    # 測試成功案例
    try:
        result = mock_ai_processing(1000000, "test_user_ai_1")
        print(f"   ✅ AI Processing Success: {result}")
    except Exception as e:
        print(f"   ❌ AI Processing Failed: {e}")
    
    # 測試失敗案例
    try:
        result = mock_ai_processing(6000000, "test_user_ai_2")
        print(f"   ✅ AI Processing Success: {result}")
    except Exception as e:
        print(f"   ❌ AI Processing Failed: {e}")


def test_error_categories():
    """測試不同類別的錯誤監控"""
    print("\n🔍 測試錯誤分類監控...")
    
    error_scenarios = [
        {
            "category": EventCategory.AI_PROCESSING,
            "level": MonitoringLevel.ERROR,
            "message": "Gemini API quota exceeded",
            "extra_data": {"api_calls_today": 1000, "quota_limit": 1000}
        },
        {
            "category": EventCategory.DATA_STORAGE,
            "level": MonitoringLevel.CRITICAL,
            "message": "Notion database corruption detected",
            "extra_data": {"affected_records": 150, "last_backup": "2024-01-15"}
        },
        {
            "category": EventCategory.LINE_BOT,
            "level": MonitoringLevel.WARNING,
            "message": "High webhook response time",
            "extra_data": {"avg_response_time": 4.5, "threshold": 3.0}
        },
        {
            "category": EventCategory.SECURITY,
            "level": MonitoringLevel.CRITICAL,
            "message": "Multiple failed authentication attempts",
            "extra_data": {"failed_attempts": 10, "source_ip": "192.168.1.100"}
        },
        {
            "category": EventCategory.USER_BEHAVIOR,
            "level": MonitoringLevel.INFO,
            "message": "User engagement spike detected",
            "extra_data": {"active_users": 500, "normal_range": "50-100"}
        }
    ]
    
    for scenario in error_scenarios:
        event = MonitoringEvent(
            category=scenario["category"],
            level=scenario["level"],
            message=scenario["message"],
            user_id="test_user_category",
            extra_data=scenario["extra_data"],
            tags={"test_category": scenario["category"].value}
        )
        
        monitoring_service.capture_event(event)
        print(f"   📊 {scenario['category'].value}: {scenario['message']}")
        time.sleep(0.4)


def test_user_context():
    """測試用戶上下文設定"""
    print("\n👤 測試用戶上下文...")
    
    # 設定用戶上下文
    monitoring_service.set_user_context("test_user_context", {
        "email": "test@example.com",
        "subscription": "premium",
        "join_date": "2024-01-01"
    })
    
    # 添加麵包屑
    monitoring_service.add_breadcrumb("User started card processing", "user_action", {
        "card_count": 3,
        "batch_mode": True
    })
    
    monitoring_service.add_breadcrumb("AI analysis completed", "ai_processing", {
        "processing_time": 2.1,
        "confidence": 0.92
    })
    
    # 觸發事件
    event = MonitoringEvent(
        category=EventCategory.USER_BEHAVIOR,
        level=MonitoringLevel.INFO,
        message="User completed card processing session",
        user_id="test_user_context",
        extra_data={
            "cards_processed": 3,
            "success_rate": 1.0,
            "session_duration": 45.2
        }
    )
    
    monitoring_service.capture_event(event)
    print("   ✅ User context and breadcrumbs set")


def test_performance_summary():
    """測試效能摘要"""
    print("\n📈 測試效能摘要...")
    
    summary = monitoring_service.get_performance_summary()
    
    print("   📊 Performance Summary:")
    if isinstance(summary, dict) and "total_operations" in summary:
        print(f"      • Total Operations: {summary.get('total_operations', 0)}")
        print(f"      • Success Rate: {summary.get('success_rate', 0):.1f}%")
        print(f"      • Average Duration: {summary.get('avg_duration', 0):.2f}s")
        print(f"      • Max Duration: {summary.get('max_duration', 0):.2f}s")
        
        if "operation_breakdown" in summary:
            print("      • Operation Breakdown:")
            for op, stats in summary["operation_breakdown"].items():
                print(f"        - {op}: {stats.get('count', 0)} ops, "
                      f"{stats.get('success_rate', 0):.1f}% success")
    else:
        print(f"      • Summary: {summary}")


def test_exception_handling():
    """測試異常捕獲"""
    print("\n🚨 測試異常捕獲...")
    
    try:
        # 故意觸發異常
        raise ValueError("This is a test exception for monitoring")
    except Exception as e:
        monitoring_service.capture_exception_with_context(
            e,
            EventCategory.SYSTEM_PERFORMANCE,
            user_id="test_user_exception",
            extra_context={
                "test_type": "exception_handling",
                "expected": True,
                "function": "test_exception_handling"
            }
        )
        print("   ✅ Exception captured and sent to monitoring")


def main():
    """主測試函數"""
    print("🎯 開始 Sentry 監控功能測試")
    print(f"⚙️  監控服務狀態: {'啟用' if monitoring_service.is_enabled else '停用'}")
    print("=" * 60)
    
    # 運行所有測試
    test_basic_monitoring()
    test_performance_monitoring()
    test_ai_processing_monitoring()
    test_error_categories()
    test_user_context()
    test_exception_handling()
    test_performance_summary()
    
    print("\n" + "=" * 60)
    print("🎉 所有監控測試完成！")
    
    if monitoring_service.is_enabled:
        print("📧 請檢查你的 Sentry Dashboard 查看所有測試事件")
        print("🔗 Dashboard: https://sentry.io")
    else:
        print("⚠️  Sentry SDK 未啟用，事件僅記錄到本地日誌")
    
    print("\n💡 提示：")
    print("   - 在生產環境中，事件會自動發送到 Sentry")
    print("   - 可以設定警報規則來監控關鍵指標")
    print("   - 使用 Dashboard 分析錯誤趨勢和效能瓶頸")


if __name__ == "__main__":
    main()