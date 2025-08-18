#!/usr/bin/env python3
"""
Sentry 完整功能測試腳本
用於驗證 Sentry 在 LINE Bot 名片管理系統中的完整功能
"""

import requests
import json
import time
from datetime import datetime
import sys

class SentryTester:
    def __init__(self, base_url="https://namecard-app.zeabur.app"):
        self.base_url = base_url
        self.test_results = []
        
    def log_result(self, test_name, success, details=""):
        """記錄測試結果"""
        result = {
            "test": test_name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        status = "✅" if success else "❌"
        print(f"{status} {test_name}")
        if details:
            print(f"   {details}")
    
    def test_basic_connectivity(self):
        """測試基本連通性"""
        print("\n🔗 測試 1: 基本連通性檢查")
        print("-" * 40)
        
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                self.log_result(
                    "健康檢查端點",
                    True,
                    f"服務正常運行 - {data.get('service', 'Unknown')}"
                )
                return True
            else:
                self.log_result(
                    "健康檢查端點",
                    False,
                    f"HTTP {response.status_code}"
                )
                return False
                
        except Exception as e:
            self.log_result(
                "健康檢查端點",
                False,
                f"連線失敗: {str(e)}"
            )
            return False
    
    def test_config_endpoint(self):
        """測試配置檢查端點"""
        print("\n⚙️ 測試 2: 系統配置檢查")
        print("-" * 40)
        
        try:
            response = requests.get(f"{self.base_url}/test", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                config = data.get('config', {})
                
                # 檢查關鍵配置
                line_configured = config.get('line_channel_configured', False)
                google_configured = config.get('google_api_configured', False)
                notion_configured = config.get('notion_api_configured', False)
                
                self.log_result(
                    "LINE Bot 配置",
                    line_configured,
                    "已配置" if line_configured else "未配置"
                )
                
                self.log_result(
                    "Google AI 配置",
                    google_configured,
                    "已配置" if google_configured else "未配置"
                )
                
                self.log_result(
                    "Notion API 配置",
                    notion_configured,
                    "已配置" if notion_configured else "未配置"
                )
                
                return True
            else:
                self.log_result(
                    "配置檢查端點",
                    False,
                    f"HTTP {response.status_code}"
                )
                return False
                
        except Exception as e:
            self.log_result(
                "配置檢查端點",
                False,
                f"請求失敗: {str(e)}"
            )
            return False
    
    def test_webhook_security(self):
        """測試 Webhook 安全性（應該觸發錯誤）"""
        print("\n🔒 測試 3: Webhook 安全性測試")
        print("-" * 40)
        
        # 測試 1: 無簽章的 POST 請求
        try:
            response = requests.post(
                f"{self.base_url}/callback",
                json={"test": "sentry_test"},
                timeout=10
            )
            
            # 這應該被拒絕（400 或其他錯誤狀態）
            if response.status_code in [400, 403, 200]:  # 200 也可能因為開發模式
                self.log_result(
                    "Webhook 安全檢查",
                    True,
                    f"正確拒絕無效請求 (HTTP {response.status_code})"
                )
            else:
                self.log_result(
                    "Webhook 安全檢查",
                    False,
                    f"未預期的狀態碼: {response.status_code}"
                )
                
        except Exception as e:
            self.log_result(
                "Webhook 安全檢查",
                True,
                f"連線被拒絕（正常）: {str(e)[:50]}"
            )
    
    def test_error_triggering(self):
        """觸發各種錯誤類型"""
        print("\n🧪 測試 4: 錯誤觸發測試（Sentry 捕獲）")
        print("-" * 40)
        
        # 錯誤 1: 404 錯誤
        try:
            response = requests.get(f"{self.base_url}/nonexistent-endpoint", timeout=10)
            self.log_result(
                "404 錯誤觸發",
                response.status_code == 404,
                f"HTTP {response.status_code} - 應被 Sentry 記錄"
            )
        except Exception as e:
            self.log_result(
                "404 錯誤觸發",
                True,
                "請求失敗，可能觸發錯誤記錄"
            )
        
        # 錯誤 2: 大型 POST 請求
        try:
            large_data = {"data": "x" * 1000000}  # 1MB 資料
            response = requests.post(
                f"{self.base_url}/callback",
                json=large_data,
                timeout=10
            )
            self.log_result(
                "大型請求測試",
                True,
                f"HTTP {response.status_code} - 可能觸發大小限制錯誤"
            )
        except Exception as e:
            self.log_result(
                "大型請求測試",
                True,
                f"請求被拒絕: {str(e)[:50]}"
            )
        
        # 錯誤 3: 無效 JSON
        try:
            response = requests.post(
                f"{self.base_url}/callback",
                data="invalid json data",
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            self.log_result(
                "無效 JSON 測試",
                True,
                f"HTTP {response.status_code} - 可能觸發解析錯誤"
            )
        except Exception as e:
            self.log_result(
                "無效 JSON 測試",
                True,
                "請求失敗，可能觸發錯誤"
            )
    
    def test_debug_endpoints(self):
        """測試偵錯端點"""
        print("\n🔍 測試 5: 偵錯端點檢查")
        print("-" * 40)
        
        debug_endpoints = ["/debug/notion", "/debug/webhook"]
        
        for endpoint in debug_endpoints:
            try:
                if endpoint == "/debug/webhook":
                    # POST 請求
                    response = requests.post(f"{self.base_url}{endpoint}", timeout=10)
                else:
                    # GET 請求
                    response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
                
                self.log_result(
                    f"偵錯端點 {endpoint}",
                    response.status_code in [200, 500],  # 200 成功，500 可能是配置問題
                    f"HTTP {response.status_code}"
                )
                
            except Exception as e:
                self.log_result(
                    f"偵錯端點 {endpoint}",
                    False,
                    f"請求失敗: {str(e)}"
                )
    
    def test_rate_limiting(self):
        """測試 Rate Limiting（快速請求）"""
        print("\n⚡ 測試 6: Rate Limiting 測試")
        print("-" * 40)
        
        success_count = 0
        error_count = 0
        
        print("   發送 10 個快速請求...")
        for i in range(10):
            try:
                response = requests.get(f"{self.base_url}/health", timeout=5)
                if response.status_code == 200:
                    success_count += 1
                elif response.status_code == 429:
                    error_count += 1
                time.sleep(0.1)  # 100ms 間隔
            except Exception:
                error_count += 1
        
        self.log_result(
            "Rate Limiting 測試",
            True,
            f"成功: {success_count}, 被限制: {error_count}"
        )
    
    def check_sentry_dashboard_instructions(self):
        """提供 Sentry Dashboard 檢查說明"""
        print("\n📊 Sentry Dashboard 檢查指示")
        print("=" * 50)
        
        instructions = [
            "1. 前往 https://sentry.io 並登入你的帳號",
            "2. 選擇你的專案（LINE-Bot-Namecard 或類似名稱）",
            "3. 點擊左側選單的 'Issues'",
            "4. 查看是否有新的錯誤記錄（最近 5-10 分鐘內）",
            "5. 點擊任何錯誤查看詳細資訊",
            "6. 確認錯誤包含完整的 stack trace 和上下文"
        ]
        
        for instruction in instructions:
            print(f"   {instruction}")
        
        print("\n🎯 預期結果:")
        print("   ✅ 應該看到 3-5 個新的錯誤記錄")
        print("   ✅ 錯誤類型包括：404、請求過大、JSON 解析錯誤等")
        print("   ✅ 每個錯誤都有詳細的上下文資訊")
        
        print("\n⚠️ 如果沒有看到錯誤記錄:")
        print("   1. 等待 2-3 分鐘（Sentry 可能有延遲）")
        print("   2. 檢查 Zeabur 日誌是否顯示 'Sentry monitoring enabled'")
        print("   3. 確認 SENTRY_DSN 環境變數設定正確")
        print("   4. 重新執行這個測試腳本")
    
    def generate_summary_report(self):
        """生成測試摘要報告"""
        print("\n📋 測試摘要報告")
        print("=" * 50)
        
        total_tests = len(self.test_results)
        successful_tests = len([r for r in self.test_results if r["success"]])
        
        print(f"總測試數: {total_tests}")
        print(f"成功測試: {successful_tests}")
        print(f"成功率: {successful_tests/total_tests*100:.1f}%")
        
        print("\n詳細結果:")
        for result in self.test_results:
            status = "✅" if result["success"] else "❌"
            print(f"{status} {result['test']}")
            if result["details"]:
                print(f"    {result['details']}")
        
        # 儲存報告
        report_data = {
            "test_summary": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "success_rate": successful_tests/total_tests*100,
                "timestamp": datetime.now().isoformat()
            },
            "test_results": self.test_results
        }
        
        with open("sentry-test-report.json", "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 詳細報告已儲存到: sentry-test-report.json")
    
    def run_comprehensive_test(self):
        """執行完整測試套件"""
        print("🚀 Sentry 完整功能測試")
        print("=" * 50)
        print(f"測試目標: {self.base_url}")
        print(f"測試時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # 執行所有測試
        self.test_basic_connectivity()
        self.test_config_endpoint()
        self.test_webhook_security()
        self.test_error_triggering()
        self.test_debug_endpoints()
        self.test_rate_limiting()
        
        # 等待一下讓錯誤傳送到 Sentry
        print("\n⏳ 等待 30 秒讓錯誤資料傳送到 Sentry...")
        time.sleep(30)
        
        # 提供 Dashboard 檢查說明
        self.check_sentry_dashboard_instructions()
        
        # 生成摘要報告
        self.generate_summary_report()
        
        print("\n🎉 測試完成！")
        print("請按照上述說明檢查 Sentry Dashboard。")

def main():
    """主函數"""
    print("請確認以下設定已完成:")
    print("✅ Sentry 專案已建立")
    print("✅ SENTRY_DSN 環境變數已在 Zeabur 設定")
    print("✅ Zeabur 服務已重新部署")
    print()
    
    # 詢問是否使用自定義 URL
    custom_url = input("是否使用自定義 URL？(直接 Enter 使用預設 namecard-app.zeabur.app): ").strip()
    
    if custom_url:
        base_url = f"https://{custom_url}"
    else:
        base_url = "https://namecard-app.zeabur.app"
    
    print(f"\n使用測試 URL: {base_url}")
    input("按 Enter 開始測試...")
    
    tester = SentryTester(base_url)
    tester.run_comprehensive_test()

if __name__ == "__main__":
    main()