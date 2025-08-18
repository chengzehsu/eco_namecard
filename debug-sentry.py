#!/usr/bin/env python3
"""
Sentry 偵錯腳本
檢查環境變數和配置是否正確
"""

import os
import sys

# 添加專案根目錄到路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from simple_config import settings

def debug_sentry_config():
    """偵錯 Sentry 配置"""
    print("🔍 Sentry 配置偵錯報告")
    print("=" * 50)
    
    # 1. 檢查環境變數
    print("1️⃣ 環境變數檢查:")
    sentry_dsn_env = os.getenv('SENTRY_DSN')
    if sentry_dsn_env:
        print(f"   ✅ SENTRY_DSN 環境變數存在")
        print(f"   📝 長度: {len(sentry_dsn_env)} 字符")
        print(f"   🔗 開頭: {sentry_dsn_env[:30]}...")
        print(f"   🔗 結尾: ...{sentry_dsn_env[-20:]}")
    else:
        print("   ❌ SENTRY_DSN 環境變數不存在")
    
    # 2. 檢查 Pydantic 設定讀取
    print("\n2️⃣ Pydantic Settings 檢查:")
    if settings.sentry_dsn:
        print(f"   ✅ settings.sentry_dsn 有值")
        print(f"   📝 長度: {len(settings.sentry_dsn)} 字符")
        print(f"   🔗 開頭: {settings.sentry_dsn[:30]}...")
        print(f"   🔗 結尾: ...{settings.sentry_dsn[-20:]}")
    else:
        print("   ❌ settings.sentry_dsn 為空")
    
    # 3. 比較兩者
    print("\n3️⃣ 環境變數 vs Settings 比較:")
    if sentry_dsn_env and settings.sentry_dsn:
        if sentry_dsn_env == settings.sentry_dsn:
            print("   ✅ 環境變數和 Settings 一致")
        else:
            print("   ❌ 環境變數和 Settings 不一致！")
            print(f"   ENV: {sentry_dsn_env}")
            print(f"   SET: {settings.sentry_dsn}")
    
    # 4. 測試 Sentry SDK 導入
    print("\n4️⃣ Sentry SDK 檢查:")
    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        print(f"   ✅ Sentry SDK 版本: {sentry_sdk.VERSION}")
        print("   ✅ Flask Integration 可用")
    except ImportError as e:
        print(f"   ❌ Sentry SDK 導入失敗: {e}")
    
    # 5. 檢查其他相關設定
    print("\n5️⃣ 其他設定檢查:")
    print(f"   Flask 環境: {settings.flask_env}")
    print(f"   Debug 模式: {settings.debug}")
    print(f"   App 主機: {settings.app_host}")
    print(f"   App 端口: {settings.app_port}")
    
    # 6. 檢查所有環境變數
    print("\n6️⃣ 所有環境變數:")
    sentry_related_vars = [k for k in os.environ.keys() if 'SENTRY' in k.upper()]
    if sentry_related_vars:
        for var in sentry_related_vars:
            value = os.environ[var]
            print(f"   {var}: {value[:30]}...{value[-10:] if len(value) > 40 else value}")
    else:
        print("   ❌ 沒有找到 SENTRY 相關的環境變數")
    
    print("\n" + "=" * 50)
    
    # 7. 給出診斷結果
    print("🎯 診斷結果:")
    if settings.sentry_dsn:
        print("   ✅ Sentry DSN 配置正確")
        print("   💡 但 app.py 中沒有顯示 'enabled' 訊息")
        print("   🔧 可能需要檢查日誌或重新部署")
    else:
        print("   ❌ Sentry DSN 配置失敗")
        if sentry_dsn_env:
            print("   💡 環境變數存在但 Pydantic 沒有讀取到")
            print("   🔧 可能是配置檔案問題")
        else:
            print("   💡 環境變數本身就不存在")
            print("   🔧 需要在 Zeabur 重新設定環境變數")

def test_sentry_init():
    """測試 Sentry 初始化"""
    print("\n🧪 測試 Sentry 初始化:")
    
    if not settings.sentry_dsn:
        print("   ❌ 無法測試，settings.sentry_dsn 為空")
        return
    
    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        
        print("   🔄 嘗試初始化 Sentry...")
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            integrations=[FlaskIntegration()],
            traces_sample_rate=0.1,
            environment=settings.flask_env
        )
        print("   ✅ Sentry 初始化成功！")
        
        # 測試發送一個測試事件
        print("   🚀 發送測試事件...")
        sentry_sdk.capture_message("Sentry 配置測試訊息", level="info")
        print("   ✅ 測試事件已發送")
        
    except Exception as e:
        print(f"   ❌ Sentry 初始化失敗: {e}")

if __name__ == "__main__":
    debug_sentry_config()
    test_sentry_init()
    
    print("\n📋 建議的後續步驟:")
    print("1. 檢查上述診斷結果")
    print("2. 如果環境變數問題，重新設定 Zeabur")
    print("3. 如果配置正確，重新部署服務")
    print("4. 檢查 Zeabur 日誌中是否有錯誤訊息")