#!/usr/bin/env python3
"""
快速 Sentry 測試腳本
用於驗證 Sentry 設定是否正確運作
"""

import requests
import json
import time

def test_sentry_setup(base_url="https://namecard-app.zeabur.app"):
    """測試 Sentry 設定"""
    print("🧪 快速 Sentry 測試")
    print("=" * 40)
    
    # 1. 測試健康檢查
    print("1️⃣ 測試健康檢查端點...")
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        if response.status_code == 200:
            print("✅ 健康檢查正常")
            data = response.json()
            print(f"   服務版本: {data.get('version', 'Unknown')}")
        else:
            print(f"⚠️ 健康檢查異常: {response.status_code}")
    except Exception as e:
        print(f"❌ 健康檢查失敗: {e}")
    
    # 2. 觸發錯誤（這會被 Sentry 捕獲）
    print("\n2️⃣ 觸發測試錯誤...")
    try:
        # 嘗試訪問不存在的端點
        response = requests.get(f"{base_url}/sentry-test-error", timeout=10)
        print(f"   回應狀態: {response.status_code}")
    except Exception as e:
        print(f"   預期的錯誤: {e}")
    
    # 3. 測試 POST 端點（可能觸發驗證錯誤）
    print("\n3️⃣ 測試 POST 端點...")
    try:
        response = requests.post(
            f"{base_url}/callback", 
            json={"test": "sentry"},
            timeout=10
        )
        print(f"   回應狀態: {response.status_code}")
        if response.status_code != 200:
            print("   ✅ 這個錯誤應該會被 Sentry 記錄")
    except Exception as e:
        print(f"   錯誤: {e}")
    
    print("\n" + "=" * 40)
    print("🎯 測試完成！")
    print("\n接下來請檢查：")
    print("1. 登入 https://sentry.io")
    print("2. 查看你的專案 Dashboard")
    print("3. 檢查 'Issues' 頁面是否有新的錯誤記錄")
    print("4. 如果看到錯誤記錄，表示 Sentry 設定成功！")

def check_sentry_dashboard_guide():
    """檢查 Sentry Dashboard 的指南"""
    print("\n📊 Sentry Dashboard 檢查指南")
    print("=" * 40)
    
    steps = [
        "1. 前往 https://sentry.io 並登入",
        "2. 選擇你的專案 'LINE-Bot-Namecard'",
        "3. 點擊左側的 'Issues' 選單",
        "4. 查看是否有新的錯誤記錄",
        "5. 點擊任何錯誤查看詳細資訊",
        "6. 確認錯誤包含 stack trace 和上下文資訊"
    ]
    
    for step in steps:
        print(f"   {step}")
    
    print("\n🔍 如果看到錯誤記錄，代表設定成功！")
    print("🚨 如果沒有看到任何錯誤，可能需要檢查：")
    print("   - SENTRY_DSN 環境變數是否正確設定")
    print("   - Zeabur 服務是否已重新部署")
    print("   - 檢查 Zeabur 日誌是否有 Sentry 相關訊息")

if __name__ == "__main__":
    print("🚀 Sentry 設定驗證工具")
    print("請確保你已經：")
    print("✅ 在 Sentry 創建了專案")
    print("✅ 在 Zeabur 設定了 SENTRY_DSN 環境變數") 
    print("✅ 重新部署了 Zeabur 服務")
    print()
    
    input("按 Enter 繼續測試...")
    
    test_sentry_setup()
    check_sentry_dashboard_guide()