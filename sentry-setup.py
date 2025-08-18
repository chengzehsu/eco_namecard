#!/usr/bin/env python3
"""
Sentry 設定和測試腳本
用於快速設定和驗證 Sentry 錯誤監控
"""

import os
import sys
import requests
import json
from datetime import datetime
import traceback

def check_sentry_config():
    """檢查 Sentry 配置"""
    print("🔍 檢查 Sentry 配置...")
    
    # 檢查環境變數
    sentry_dsn = os.getenv('SENTRY_DSN')
    if not sentry_dsn:
        print("❌ SENTRY_DSN 環境變數未設定")
        print("💡 請先在 Zeabur 或 .env 中設定 SENTRY_DSN")
        return False
    
    print(f"✅ SENTRY_DSN: {sentry_dsn[:30]}...")
    
    # 檢查 Sentry SDK
    try:
        import sentry_sdk
        print(f"✅ Sentry SDK 版本: {sentry_sdk.VERSION}")
    except ImportError:
        print("❌ Sentry SDK 未安裝")
        print("💡 請執行: pip install sentry-sdk[flask]")
        return False
    
    return True

def initialize_sentry():
    """初始化 Sentry"""
    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        
        sentry_dsn = os.getenv('SENTRY_DSN')
        
        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=[
                FlaskIntegration(transaction_style='endpoint'),
                LoggingIntegration(
                    level=logging.INFO,
                    event_level=logging.ERROR
                )
            ],
            traces_sample_rate=0.1,
            profiles_sample_rate=0.1,
            environment=os.getenv('FLASK_ENV', 'production'),
            release="test-release",
            debug=False
        )
        
        print("✅ Sentry 初始化成功")
        return True
        
    except Exception as e:
        print(f"❌ Sentry 初始化失敗: {e}")
        return False

def test_error_capture():
    """測試錯誤捕獲"""
    print("\n🧪 測試 Sentry 錯誤捕獲...")
    
    try:
        import sentry_sdk
        
        # 測試 1: 基本異常
        print("1️⃣ 測試基本異常捕獲...")
        try:
            1 / 0
        except ZeroDivisionError as e:
            sentry_sdk.capture_exception(e)
            print("✅ 基本異常已發送到 Sentry")
        
        # 測試 2: 自定義訊息
        print("2️⃣ 測試自定義訊息...")
        sentry_sdk.capture_message("LINE Bot 測試訊息", level="info")
        print("✅ 自定義訊息已發送到 Sentry")
        
        # 測試 3: 帶上下文的錯誤
        print("3️⃣ 測試帶上下文的錯誤...")
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag("test_type", "setup_validation")
            scope.set_user({"id": "test_user", "username": "setup_test"})
            scope.set_context("test_info", {
                "timestamp": datetime.now().isoformat(),
                "system": "LINE Bot Namecard",
                "component": "setup_script"
            })
            
            try:
                raise ValueError("這是一個測試錯誤，用於驗證 Sentry 設定")
            except ValueError as e:
                sentry_sdk.capture_exception(e)
                print("✅ 帶上下文的錯誤已發送到 Sentry")
        
        # 測試 4: 效能監控
        print("4️⃣ 測試效能監控...")
        with sentry_sdk.start_transaction(name="test_transaction", op="test"):
            with sentry_sdk.start_span(op="test_span", description="測試 span"):
                import time
                time.sleep(0.1)  # 模擬處理時間
        print("✅ 效能監控資料已發送到 Sentry")
        
        return True
        
    except Exception as e:
        print(f"❌ 錯誤捕獲測試失敗: {e}")
        return False

def simulate_linebot_errors():
    """模擬 LINE Bot 常見錯誤"""
    print("\n🤖 模擬 LINE Bot 常見錯誤...")
    
    import sentry_sdk
    
    # 錯誤 1: AI 處理失敗
    print("1️⃣ 模擬 AI 處理錯誤...")
    with sentry_sdk.configure_scope() as scope:
        scope.set_tag("error_type", "ai_processing")
        scope.set_context("ai_context", {
            "service": "Google Gemini",
            "image_size": "2.5MB",
            "user_id": "test_user_123"
        })
        
        try:
            raise ConnectionError("Google Gemini API 連線逾時")
        except ConnectionError as e:
            sentry_sdk.capture_exception(e)
            print("✅ AI 處理錯誤已記錄")
    
    # 錯誤 2: Notion 儲存失敗
    print("2️⃣ 模擬 Notion 儲存錯誤...")
    with sentry_sdk.configure_scope() as scope:
        scope.set_tag("error_type", "notion_storage")
        scope.set_context("notion_context", {
            "database_id": "test_db_123",
            "card_count": 3,
            "operation": "batch_save"
        })
        
        try:
            raise PermissionError("Notion API 權限不足")
        except PermissionError as e:
            sentry_sdk.capture_exception(e)
            print("✅ Notion 儲存錯誤已記錄")
    
    # 錯誤 3: LINE Webhook 錯誤
    print("3️⃣ 模擬 LINE Webhook 錯誤...")
    with sentry_sdk.configure_scope() as scope:
        scope.set_tag("error_type", "line_webhook")
        scope.set_context("line_context", {
            "signature": "invalid_signature",
            "message_type": "image",
            "user_id": "U1234567890"
        })
        
        try:
            raise ValueError("LINE Webhook 簽章驗證失敗")
        except ValueError as e:
            sentry_sdk.capture_exception(e)
            print("✅ LINE Webhook 錯誤已記錄")
    
    # 錯誤 4: Rate Limiting 錯誤
    print("4️⃣ 模擬 Rate Limiting 錯誤...")
    with sentry_sdk.configure_scope() as scope:
        scope.set_tag("error_type", "rate_limiting")
        scope.set_context("rate_limit_context", {
            "user_id": "heavy_user_456",
            "daily_usage": 55,
            "limit": 50
        })
        
        sentry_sdk.capture_message(
            "使用者超過每日處理限制",
            level="warning"
        )
        print("✅ Rate Limiting 警告已記錄")

def test_sentry_integration():
    """測試與 Flask 應用的整合"""
    print("\n🔧 測試 Flask 整合...")
    
    try:
        from flask import Flask
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        
        app = Flask(__name__)
        
        @app.route('/test-error')
        def test_error():
            raise Exception("Flask 測試錯誤")
        
        @app.route('/test-message')
        def test_message():
            sentry_sdk.capture_message("Flask 測試訊息")
            return "Message sent to Sentry"
        
        print("✅ Flask 整合測試路由已建立")
        print("💡 可以透過 /test-error 和 /test-message 端點測試")
        
        return True
        
    except Exception as e:
        print(f"❌ Flask 整合測試失敗: {e}")
        return False

def validate_sentry_dashboard():
    """驗證 Sentry Dashboard 設定"""
    print("\n📊 Sentry Dashboard 檢查清單...")
    
    print("請手動檢查以下項目:")
    print("□ 登入 https://sentry.io")
    print("□ 專案已建立且顯示最近的錯誤")
    print("□ 設定 Email 通知")
    print("□ 設定 Slack 整合 (可選)")
    print("□ 檢查 Issues 頁面有測試錯誤")
    print("□ 檢查 Performance 頁面有效能資料")
    print("□ 設定 Alert Rules")
    
    print("\n📧 推薦的 Alert 設定:")
    alert_rules = [
        "新錯誤類型出現時立即通知",
        "錯誤率超過 5% 時通知",
        "單一錯誤超過 10 次/小時時通知",
        "效能異常時通知 (回應時間 > 5 秒)"
    ]
    
    for i, rule in enumerate(alert_rules, 1):
        print(f"{i}. {rule}")

def generate_sentry_config():
    """生成 Sentry 配置文件"""
    print("\n📝 生成 Sentry 配置範例...")
    
    config = {
        "sentry_config": {
            "dsn": "YOUR_SENTRY_DSN_HERE",
            "environment": "production",
            "release": "1.0.0",
            "integrations": [
                "FlaskIntegration",
                "LoggingIntegration"
            ],
            "traces_sample_rate": 0.1,
            "profiles_sample_rate": 0.1,
            "send_default_pii": False,
            "max_breadcrumbs": 50,
            "attach_stacktrace": True,
            "before_send": "filter_sensitive_data"
        },
        "zeabur_env_vars": {
            "SENTRY_DSN": "https://your-sentry-dsn@sentry.io/project-id",
            "SENTRY_ENVIRONMENT": "production",
            "SENTRY_RELEASE": "1.0.0"
        },
        "alert_rules": [
            {
                "name": "High Error Rate",
                "condition": "error_rate > 5%",
                "actions": ["email", "slack"]
            },
            {
                "name": "New Error Type",
                "condition": "is:unresolved is:for_review",
                "actions": ["email"]
            },
            {
                "name": "Performance Issues",
                "condition": "transaction.duration > 5s",
                "actions": ["email"]
            }
        ]
    }
    
    with open('sentry-config.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print("✅ Sentry 配置已儲存到 sentry-config.json")

def main():
    """主要執行函數"""
    print("🚀 Sentry 設定和測試工具")
    print("=" * 50)
    
    # 檢查配置
    if not check_sentry_config():
        print("\n❌ Sentry 配置檢查失敗")
        print("請先完成以下步驟:")
        print("1. 在 https://sentry.io 註冊帳號")
        print("2. 建立新專案")
        print("3. 獲取 DSN")
        print("4. 設定 SENTRY_DSN 環境變數")
        print("5. 安裝 sentry-sdk: pip install sentry-sdk[flask]")
        return
    
    # 初始化 Sentry
    if not initialize_sentry():
        print("\n❌ Sentry 初始化失敗")
        return
    
    # 執行測試
    print("\n" + "=" * 50)
    test_error_capture()
    
    print("\n" + "=" * 50)
    simulate_linebot_errors()
    
    print("\n" + "=" * 50)
    test_sentry_integration()
    
    print("\n" + "=" * 50)
    validate_sentry_dashboard()
    
    print("\n" + "=" * 50)
    generate_sentry_config()
    
    print("\n" + "=" * 50)
    print("🎉 Sentry 設定和測試完成！")
    print("\n下一步:")
    print("1. 檢查 Sentry Dashboard 是否收到測試錯誤")
    print("2. 設定通知和 Alert 規則")
    print("3. 在生產環境中監控實際錯誤")
    print("4. 定期檢查錯誤趨勢和效能指標")

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    main()