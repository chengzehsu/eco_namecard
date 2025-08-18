#!/usr/bin/env python3
"""
等待部署完成並測試 Sentry 整合
"""

import requests
import time
import json
from datetime import datetime


def wait_for_deployment(url="https://namecard-app.zeabur.app/health", max_wait=600):
    """等待部署完成"""
    print(f"⏳ 等待部署完成... (最多等待 {max_wait//60} 分鐘)")
    
    start_time = time.time()
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 部署完成！")
                print(f"   狀態: {data.get('status')}")
                print(f"   版本: {data.get('version')}")
                print(f"   Release: {data.get('release')}")
                print(f"   Git Commit: {data.get('git_commit')}")
                return True
            else:
                print(f"🔄 狀態碼: {response.status_code}, 繼續等待...")
                
        except requests.RequestException as e:
            print(f"🔄 連線錯誤: {e}, 繼續等待...")
        
        time.sleep(30)  # 每 30 秒檢查一次
    
    print(f"⏰ 等待超時 ({max_wait//60} 分鐘)")
    return False


def test_version_endpoints():
    """測試版本相關端點"""
    endpoints = [
        "/health",
        "/version", 
        "/deployment",
        "/debug/sentry"
    ]
    
    base_url = "https://namecard-app.zeabur.app"
    results = {}
    
    print("\n🔍 測試版本端點...")
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=10)
            if response.status_code == 200:
                data = response.json()
                results[endpoint] = data
                print(f"✅ {endpoint}: 成功")
                
                # 顯示重要資訊
                if endpoint == "/version":
                    version_info = data.get("version", {})
                    sentry_info = data.get("sentry", {})
                    print(f"   📋 版本: {version_info.get('version')}")
                    print(f"   🏷️ Release: {sentry_info.get('release')}")
                    print(f"   🔄 Git Commit: {version_info.get('git_commit')}")
                    
                elif endpoint == "/debug/sentry":
                    print(f"   📊 Sentry SDK: {data.get('sentry_sdk_available')}")
                    print(f"   🔧 DSN 設定: {data.get('sentry_dsn_settings')}")
                    
            else:
                print(f"❌ {endpoint}: HTTP {response.status_code}")
                results[endpoint] = {"error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            print(f"❌ {endpoint}: {e}")
            results[endpoint] = {"error": str(e)}
    
    return results


def trigger_live_test():
    """觸發線上測試錯誤"""
    print("\n🧪 觸發線上測試...")
    
    # 嘗試觸發一個測試錯誤到線上服務
    try:
        # 發送一個會觸發錯誤的請求
        response = requests.post(
            "https://namecard-app.zeabur.app/callback",
            json={"test": "sentry_integration_test"},
            headers={"X-Test-Sentry": "true"},
            timeout=10
        )
        
        print(f"📡 測試請求發送: HTTP {response.status_code}")
        
        # 檢查是否觸發了監控
        if response.status_code in [400, 401, 403]:
            print("✅ 預期的錯誤回應，應該已觸發 Sentry 監控")
        
    except Exception as e:
        print(f"⚠️ 測試請求失敗: {e}")


def generate_test_summary(results):
    """生成測試總結"""
    print("\n" + "="*60)
    print("📋 Sentry Release Tracking 測試總結")
    print("="*60)
    
    # 分析結果
    successful_endpoints = sum(1 for r in results.values() if not isinstance(r, dict) or "error" not in r)
    total_endpoints = len(results)
    
    print(f"📊 端點測試結果: {successful_endpoints}/{total_endpoints}")
    
    if successful_endpoints == total_endpoints:
        print("🎉 所有端點測試通過！")
        
        # 顯示關鍵資訊
        if "/version" in results:
            version_data = results["/version"]
            if "sentry" in version_data:
                release = version_data["sentry"].get("release")
                print(f"🏷️ 當前 Release: {release}")
                
        if "/debug/sentry" in results:
            sentry_data = results["/debug/sentry"]
            if sentry_data.get("sentry_sdk_available"):
                print("✅ Sentry SDK 已啟用")
            if sentry_data.get("sentry_dsn_settings"):
                print("✅ Sentry DSN 已設定")
    
    else:
        print("⚠️ 部分端點測試失敗")
        for endpoint, result in results.items():
            if isinstance(result, dict) and "error" in result:
                print(f"   ❌ {endpoint}: {result['error']}")
    
    print("\n💡 下一步:")
    print("1. 檢查 Sentry Dashboard: https://sentry.io")
    print("2. 查看 Issues 頁面是否有新的錯誤")
    print(f"3. 搜尋 release:{results.get('/version', {}).get('sentry', {}).get('release', 'unknown')}")
    print("4. 驗證錯誤是否包含完整的上下文資訊")
    
    return results


def main():
    """主函數"""
    print("🚀 Sentry Release Tracking 線上測試")
    print(f"⏰ 開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 等待部署完成
    if wait_for_deployment():
        # 測試端點
        results = test_version_endpoints()
        
        # 觸發測試
        trigger_live_test()
        
        # 生成總結
        generate_test_summary(results)
        
        # 儲存結果
        report_file = f"sentry_live_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "results": results,
                "test_type": "live_sentry_integration"
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 測試報告已儲存: {report_file}")
        
    else:
        print("❌ 部署未完成，無法進行測試")
        print("💡 建議手動檢查 Zeabur Dashboard 的部署狀態")


if __name__ == "__main__":
    main()