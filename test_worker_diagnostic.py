#!/usr/bin/env python3
"""
Worker 診斷測試腳本

測試 RQ Worker、Redis 連接、圖片上傳流程等功能。
"""

import sys
import os

# 添加專案根目錄到 Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simple_config import settings


def test_redis_connection():
    """測試 Redis 連接"""
    print("\n=== Redis 連接測試 ===")
    
    print(f"  REDIS_ENABLED: {settings.redis_enabled}")
    print(f"  REDIS_URL: {settings.redis_url[:30] + '...' if settings.redis_url and len(settings.redis_url) > 30 else settings.redis_url}")
    print(f"  REDIS_HOST: {settings.redis_host}")
    print(f"  REDIS_PORT: {settings.redis_port}")
    
    try:
        from src.namecard.infrastructure.redis_client import get_redis_client
        redis_client = get_redis_client()
        
        if redis_client:
            redis_client.ping()
            print("  ✅ Redis 連接成功")
            
            # 檢查 Worker 鎖
            lock_value = redis_client.get("embedded_rq_worker_lock")
            if lock_value:
                print(f"  📌 內嵌 Worker 鎖存在: {lock_value.decode() if isinstance(lock_value, bytes) else lock_value}")
            else:
                print("  📌 內嵌 Worker 鎖不存在（Worker 未運行或使用同步模式）")
            
            return True
        else:
            print("  ❌ Redis 客戶端未初始化")
            return False
            
    except Exception as e:
        print(f"  ❌ Redis 連接失敗: {e}")
        return False


def test_rq_availability():
    """測試 RQ 可用性"""
    print("\n=== RQ 可用性測試 ===")
    
    try:
        from src.namecard.infrastructure.storage.image_upload_worker import (
            RQ_AVAILABLE, 
            _is_rq_available,
            get_queue_info,
        )
        
        print(f"  RQ 套件已安裝: {RQ_AVAILABLE}")
        print(f"  RQ 可用（含 Redis）: {_is_rq_available()}")
        
        queue_info = get_queue_info()
        print(f"  隊列資訊: {queue_info}")
        
        return _is_rq_available()
        
    except Exception as e:
        print(f"  ❌ RQ 檢查失敗: {e}")
        return False


def test_imgbb_config():
    """測試 ImgBB 配置"""
    print("\n=== ImgBB 配置測試 ===")
    
    api_key = getattr(settings, 'imgbb_api_key', None)
    
    if api_key:
        # 只顯示前幾個字元
        masked_key = api_key[:8] + "..." if len(api_key) > 8 else api_key
        print(f"  ✅ IMGBB_API_KEY 已設定: {masked_key}")
        
        try:
            from src.namecard.infrastructure.storage.image_storage import get_image_storage
            storage = get_image_storage()
            if storage:
                print("  ✅ ImageStorage 初始化成功")
                return True
            else:
                print("  ❌ ImageStorage 初始化失敗")
                return False
        except Exception as e:
            print(f"  ❌ ImageStorage 錯誤: {e}")
            return False
    else:
        print("  ❌ IMGBB_API_KEY 未設定")
        return False


def test_upload_flow():
    """測試上傳流程（不實際上傳）"""
    print("\n=== 上傳流程測試 ===")
    
    try:
        from src.namecard.infrastructure.storage.image_upload_worker import (
            _is_rq_available,
            submit_to_rq,
        )
        
        rq_available = _is_rq_available()
        
        if rq_available:
            print("  📤 上傳模式: RQ 非同步")
            print("  → 任務會提交到 Redis 隊列")
            print("  → 內嵌 Worker 或獨立 Worker 處理")
        else:
            print("  📤 上傳模式: 同步上傳")
            print("  → 直接在請求中上傳到 ImgBB")
            print("  → 然後更新 Notion 頁面")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 流程檢查失敗: {e}")
        return False


def test_failed_tasks():
    """檢查失敗的任務"""
    print("\n=== 失敗任務檢查 ===")
    
    try:
        from src.namecard.infrastructure.redis_client import get_redis_client
        redis_client = get_redis_client()
        
        if not redis_client:
            print("  ⚠️ Redis 不可用，無法檢查失敗任務")
            return True
        
        # 查詢失敗任務
        pattern = "failed_upload:*"
        keys = redis_client.keys(pattern)
        
        if keys:
            print(f"  ⚠️ 發現 {len(keys)} 個失敗的上傳任務")
            for key in keys[:5]:  # 只顯示前 5 個
                key_str = key.decode() if isinstance(key, bytes) else key
                print(f"    - {key_str}")
            if len(keys) > 5:
                print(f"    ... 還有 {len(keys) - 5} 個")
            print("\n  💡 使用 POST /admin/worker/retry-all 重試失敗任務")
        else:
            print("  ✅ 沒有失敗的上傳任務")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 檢查失敗: {e}")
        return False


def test_embedded_worker():
    """測試內嵌 Worker 功能"""
    print("\n=== 內嵌 Worker 測試 ===")
    
    try:
        # 檢查環境變數
        enable_embedded = os.environ.get("ENABLE_EMBEDDED_RQ_WORKER", "true").lower()
        print(f"  ENABLE_EMBEDDED_RQ_WORKER: {enable_embedded}")
        
        if enable_embedded in ("true", "1", "yes"):
            print("  ✅ 內嵌 Worker 已啟用")
            
            # 檢查是否能導入啟動函數
            try:
                import app as main_app
                if hasattr(main_app, 'start_embedded_rq_worker'):
                    print("  ✅ start_embedded_rq_worker 函數可用")
                else:
                    print("  ⚠️ start_embedded_rq_worker 函數不存在")
            except Exception as e:
                print(f"  ⚠️ 無法導入 app 模組: {e}")
        else:
            print("  ⚠️ 內嵌 Worker 已停用")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 測試失敗: {e}")
        return False


def main():
    print("=" * 50)
    print("Worker 診斷測試")
    print("=" * 50)
    
    results = {}
    
    # 執行所有測試
    results['redis'] = test_redis_connection()
    results['rq'] = test_rq_availability()
    results['imgbb'] = test_imgbb_config()
    results['flow'] = test_upload_flow()
    results['failed_tasks'] = test_failed_tasks()
    results['embedded_worker'] = test_embedded_worker()
    
    # 總結
    print("\n" + "=" * 50)
    print("診斷總結")
    print("=" * 50)
    
    all_pass = True
    for name, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {name}")
        if not passed:
            all_pass = False
    
    # 建議
    print("\n=== 建議 ===")
    
    if not results['redis']:
        print("  🔧 請檢查 REDIS_URL 或 REDIS_HOST/PORT 設定")
        print("     如果不使用 Redis，系統會自動使用同步上傳")
    
    if not results['imgbb']:
        print("  🔧 請設定 IMGBB_API_KEY 環境變數")
        print("     沒有 API Key 將無法上傳圖片")
    
    if results['redis'] and results['rq']:
        print("  ✅ RQ 模式可用 - 圖片將非同步上傳")
    else:
        print("  ℹ️ 同步模式 - 圖片將在請求中直接上傳")
    
    print()
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
