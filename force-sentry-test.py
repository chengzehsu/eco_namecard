#!/usr/bin/env python3
"""
強制 Sentry 錯誤測試
用於確認 Sentry 是否正常工作
"""

import requests
import time
import json

def force_trigger_errors(base_url="https://namecard-app.zeabur.app"):
    """強制觸發多種錯誤類型"""
    
    print("🚨 強制觸發 Sentry 錯誤測試")
    print("=" * 50)
    
    errors_triggered = []
    
    # 錯誤 1: 404 錯誤
    print("1️⃣ 觸發 404 錯誤...")
    try:
        response = requests.get(f"{base_url}/definitely-does-not-exist-123", timeout=10)
        errors_triggered.append(f"404 錯誤: HTTP {response.status_code}")
        print(f"   ✅ HTTP {response.status_code}")
    except Exception as e:
        print(f"   ❌ 請求失敗: {e}")
    
    # 錯誤 2: 方法不允許
    print("2️⃣ 觸發方法不允許錯誤...")
    try:
        response = requests.put(f"{base_url}/health", timeout=10)
        errors_triggered.append(f"方法錯誤: HTTP {response.status_code}")
        print(f"   ✅ HTTP {response.status_code}")
    except Exception as e:
        print(f"   ❌ 請求失敗: {e}")
    
    # 錯誤 3: 大型 POST 請求
    print("3️⃣ 觸發大型請求錯誤...")
    try:
        large_data = {"data": "X" * 500000}  # 500KB 資料
        response = requests.post(
            f"{base_url}/callback",
            json=large_data,
            timeout=15
        )
        errors_triggered.append(f"大型請求: HTTP {response.status_code}")
        print(f"   ✅ HTTP {response.status_code}")
    except Exception as e:
        print(f"   ✅ 請求被拒絕（預期）: {str(e)[:50]}")
        errors_triggered.append("大型請求: 被拒絕")
    
    # 錯誤 4: 無效的 Content-Type
    print("4️⃣ 觸發無效 Content-Type 錯誤...")
    try:
        response = requests.post(
            f"{base_url}/callback",
            data="這不是 JSON",
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        errors_triggered.append(f"無效JSON: HTTP {response.status_code}")
        print(f"   ✅ HTTP {response.status_code}")
    except Exception as e:
        print(f"   ✅ 請求失敗（預期）: {str(e)[:50]}")
        errors_triggered.append("無效JSON: 請求失敗")
    
    # 錯誤 5: 連續快速請求（可能觸發 rate limiting）
    print("5️⃣ 觸發快速請求...")
    for i in range(5):
        try:
            response = requests.get(f"{base_url}/nonexistent-{i}", timeout=5)
            print(f"   快速請求 {i+1}: HTTP {response.status_code}")
        except Exception as e:
            print(f"   快速請求 {i+1}: 失敗")
        time.sleep(0.1)
    
    errors_triggered.append("快速連續請求: 5次")
    
    print("\n" + "=" * 50)
    print("🎯 錯誤觸發摘要:")
    for error in errors_triggered:
        print(f"   ✅ {error}")
    
    print(f"\n總共觸發了 {len(errors_triggered)} 種錯誤類型")
    print("\n⏳ 請等待 3-5 分鐘，然後檢查 Sentry Dashboard")
    
    return len(errors_triggered)

def check_service_health():
    """檢查服務健康狀態"""
    print("\n🔍 檢查服務狀態...")
    
    try:
        response = requests.get("https://namecard-app.zeabur.app/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print("✅ 服務正常運行")
            print(f"   服務: {data.get('service', 'Unknown')}")
            print(f"   版本: {data.get('version', 'Unknown')}")
            print(f"   時間: {data.get('timestamp', 'Unknown')}")
            return True
        else:
            print(f"❌ 服務異常: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 無法連接服務: {e}")
        return False

def main():
    print("🚨 Sentry 強制錯誤測試工具")
    print("用於排查為什麼 Sentry 沒有收到錯誤記錄")
    print()
    
    # 先檢查服務是否正常
    if not check_service_health():
        print("❌ 服務無法存取，請先檢查 Zeabur 部署狀態")
        return
    
    print("\n準備觸發多種錯誤...")
    input("按 Enter 開始測試...")
    
    error_count = force_trigger_errors()
    
    print("\n" + "=" * 50)
    print("📋 下一步檢查清單:")
    print("1. 等待 3-5 分鐘")
    print("2. 前往 https://sentry.io 登入")
    print("3. 進入你的專案")
    print("4. 查看 'Issues' 頁面")
    print("5. 應該看到多個新的錯誤記錄")
    print()
    print("🔍 如果還是沒有錯誤記錄:")
    print("- 檢查 Zeabur 日誌中是否有 'Sentry monitoring enabled'")
    print("- 確認 SENTRY_DSN 環境變數設定正確")
    print("- 檢查 Sentry 專案設定")

if __name__ == "__main__":
    main()