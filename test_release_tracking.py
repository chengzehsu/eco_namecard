#!/usr/bin/env python3
"""
Release 追蹤功能測試腳本
驗證版本管理、Sentry 整合和部署追蹤功能
"""

import sys
import os
import json
import requests
from datetime import datetime

# 添加專案根目錄到路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from src.namecard.core.version import version_manager
    from src.namecard.core.services.monitoring import monitoring_service, MonitoringEvent, EventCategory, MonitoringLevel
except ImportError as e:
    print(f"❌ 無法匯入必要模組: {e}")
    sys.exit(1)


def test_version_manager():
    """測試版本管理器"""
    print("🔍 測試版本管理器...")
    
    try:
        # 測試基本版本資訊
        version_info = version_manager.get_version_info()
        sentry_info = version_manager.get_sentry_release_info()
        
        print("✅ 版本資訊:")
        print(f"   • 版本: {version_info['version']}")
        print(f"   • Git Commit: {version_info['git_commit']}")
        print(f"   • Git Branch: {version_info['git_branch']}")
        print(f"   • Release Name: {version_manager.release_name}")
        print(f"   • Build Time: {version_info['build_time']}")
        print(f"   • Platform: {version_info['platform']}")
        
        print("\n✅ Sentry Release 資訊:")
        print(f"   • Release: {sentry_info['release']}")
        print(f"   • Environment: {sentry_info['environment']}")
        print(f"   • Dist: {sentry_info['dist']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 版本管理器測試失敗: {e}")
        return False


def test_monitoring_service():
    """測試監控服務"""
    print("\n🔍 測試監控服務...")
    
    try:
        # 測試部署資訊
        deployment_info = monitoring_service.get_deployment_info()
        
        if deployment_info:
            print("✅ 部署資訊:")
            for key, value in deployment_info.items():
                print(f"   • {key}: {value}")
        else:
            print("⚠️ 沒有部署資訊")
        
        # 測試監控事件
        print("\n🧪 測試監控事件...")
        test_event = MonitoringEvent(
            category=EventCategory.SYSTEM_PERFORMANCE,
            level=MonitoringLevel.INFO,
            message="Release tracking test event",
            extra_data={
                "test": True,
                "timestamp": datetime.now().isoformat(),
                "test_type": "release_tracking"
            },
            tags={
                "test": "release_tracking",
                "component": "version_test"
            }
        )
        
        monitoring_service.capture_event(test_event)
        print("✅ 測試事件已發送到監控系統")
        
        # 測試部署標記
        print("\n🚀 測試部署標記...")
        monitoring_service.mark_deployment(
            environment="test",
            url="https://test.example.com"
        )
        print("✅ 部署標記已發送")
        
        return True
        
    except Exception as e:
        print(f"❌ 監控服務測試失敗: {e}")
        return False


def test_api_endpoints():
    """測試 API 端點"""
    print("\n🔍 測試 API 端點...")
    
    base_url = "https://namecard-app.zeabur.app"
    endpoints = [
        "/health",
        "/version", 
        "/deployment"
    ]
    
    results = {}
    
    for endpoint in endpoints:
        try:
            print(f"📡 測試 {endpoint}...")
            response = requests.get(f"{base_url}{endpoint}", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                results[endpoint] = {
                    "status": "success",
                    "data": data
                }
                print(f"✅ {endpoint}: 成功")
                
                # 顯示重要資訊
                if endpoint == "/version" and "version" in data:
                    version_data = data["version"]
                    print(f"   • 版本: {version_data.get('version', 'N/A')}")
                    print(f"   • Git Commit: {version_data.get('git_commit', 'N/A')}")
                    print(f"   • Release: {data.get('sentry', {}).get('release', 'N/A')}")
                    
                elif endpoint == "/deployment" and "deployment" in data:
                    deployment = data["deployment"]
                    if deployment:
                        print(f"   • Release: {deployment.get('release', 'N/A')}")
                        print(f"   • Build Time: {deployment.get('build_time', 'N/A')}")
                    
            else:
                results[endpoint] = {
                    "status": "error",
                    "status_code": response.status_code
                }
                print(f"❌ {endpoint}: HTTP {response.status_code}")
                
        except Exception as e:
            results[endpoint] = {
                "status": "exception",
                "error": str(e)
            }
            print(f"❌ {endpoint}: {e}")
    
    return results


def test_sentry_integration():
    """測試 Sentry 整合"""
    print("\n🔍 測試 Sentry 整合...")
    
    try:
        # 檢查 Sentry 配置
        print("📋 檢查 Sentry 配置...")
        
        if monitoring_service.is_enabled:
            print("✅ Sentry SDK 已啟用")
            
            # 測試錯誤捕獲
            print("🧪 測試錯誤捕獲...")
            try:
                # 故意觸發錯誤進行測試
                raise ValueError("Release tracking test error - 這是測試錯誤，可以忽略")
            except ValueError as e:
                monitoring_service.capture_exception_with_context(
                    e,
                    EventCategory.SYSTEM_PERFORMANCE,
                    extra_context={
                        "test_type": "release_tracking",
                        "component": "error_testing",
                        "expected": True
                    }
                )
                print("✅ 測試錯誤已發送到 Sentry")
            
            # 測試效能監控
            print("📊 測試效能監控...")
            import time
            
            start_time = time.time()
            time.sleep(0.1)  # 模擬處理時間
            duration = time.time() - start_time
            
            from src.namecard.core.services.monitoring import PerformanceMetric
            metric = PerformanceMetric(
                operation="release_tracking_test",
                duration=duration,
                success=True,
                metadata={
                    "test": True,
                    "component": "performance_testing"
                }
            )
            
            monitoring_service.track_performance(metric)
            print("✅ 效能指標已發送到 Sentry")
            
        else:
            print("⚠️ Sentry SDK 未啟用，跳過 Sentry 測試")
        
        return True
        
    except Exception as e:
        print(f"❌ Sentry 整合測試失敗: {e}")
        return False


def generate_test_report(results):
    """生成測試報告"""
    print("\n" + "="*60)
    print("📋 Release 追蹤功能測試報告")
    print("="*60)
    
    test_summary = {
        "version_manager": results.get("version_manager", False),
        "monitoring_service": results.get("monitoring_service", False),
        "sentry_integration": results.get("sentry_integration", False),
        "api_endpoints": results.get("api_endpoints", {})
    }
    
    # 統計成功的測試
    successful_tests = sum([
        test_summary["version_manager"],
        test_summary["monitoring_service"],
        test_summary["sentry_integration"]
    ])
    
    successful_endpoints = sum([
        1 for result in test_summary["api_endpoints"].values()
        if isinstance(result, dict) and result.get("status") == "success"
    ])
    
    total_tests = 3 + len(test_summary["api_endpoints"])
    total_successful = successful_tests + successful_endpoints
    
    print(f"📊 測試結果: {total_successful}/{total_tests} 通過")
    print(f"📈 成功率: {(total_successful/total_tests)*100:.1f}%")
    
    print("\n🔧 功能狀態:")
    print(f"   • 版本管理: {'✅' if test_summary['version_manager'] else '❌'}")
    print(f"   • 監控服務: {'✅' if test_summary['monitoring_service'] else '❌'}")
    print(f"   • Sentry 整合: {'✅' if test_summary['sentry_integration'] else '❌'}")
    
    print("\n🌐 API 端點:")
    for endpoint, result in test_summary["api_endpoints"].items():
        if isinstance(result, dict):
            status = result.get("status", "unknown")
            icon = "✅" if status == "success" else "❌"
            print(f"   • {endpoint}: {icon} {status}")
        else:
            print(f"   • {endpoint}: ❌ 未測試")
    
    print("\n💡 建議:")
    if total_successful == total_tests:
        print("   🎉 所有測試通過！Release 追蹤功能運作正常")
        print("   📈 可以在 Sentry Dashboard 查看詳細的監控資料")
        print("   🔗 Sentry Dashboard: https://sentry.io")
    else:
        print("   ⚠️ 部分測試失敗，請檢查:")
        if not test_summary["version_manager"]:
            print("     - 版本管理器配置")
        if not test_summary["monitoring_service"]:
            print("     - 監控服務設定")
        if not test_summary["sentry_integration"]:
            print("     - Sentry SDK 和環境變數")
        
        failed_endpoints = [
            endpoint for endpoint, result in test_summary["api_endpoints"].items()
            if not (isinstance(result, dict) and result.get("status") == "success")
        ]
        if failed_endpoints:
            print(f"     - API 端點: {', '.join(failed_endpoints)}")
    
    return test_summary


def main():
    """主測試函數"""
    print("🚀 Release 追蹤功能測試開始")
    print(f"⏰ 測試時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    results = {}
    
    # 執行各項測試
    results["version_manager"] = test_version_manager()
    results["monitoring_service"] = test_monitoring_service()
    results["sentry_integration"] = test_sentry_integration()
    results["api_endpoints"] = test_api_endpoints()
    
    # 生成測試報告
    test_summary = generate_test_report(results)
    
    # 儲存測試結果
    try:
        report_data = {
            "test_time": datetime.now().isoformat(),
            "results": results,
            "summary": test_summary
        }
        
        with open("release_tracking_test_report.json", "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n📄 詳細報告已儲存到: release_tracking_test_report.json")
        
    except Exception as e:
        print(f"\n⚠️ 無法儲存測試報告: {e}")
    
    print("\n" + "="*60)
    print("🎯 測試完成")


if __name__ == "__main__":
    main()