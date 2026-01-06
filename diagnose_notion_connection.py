#!/usr/bin/env python3
"""
Notion 連線診斷腳本
用於診斷 "Invalid request URL." 錯誤
"""

import os
import sys

# 添加項目根目錄到 Python 路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

def diagnose():
    print("=" * 80)
    print("Notion 連線診斷")
    print("=" * 80)
    
    # 1. 檢查環境變數
    print("\n[Step 1] 檢查環境變數")
    print("-" * 40)
    
    api_key = os.getenv("NOTION_API_KEY", "")
    database_id = os.getenv("NOTION_DATABASE_ID", "")
    
    print(f"  NOTION_API_KEY: {'已設定 (長度: ' + str(len(api_key)) + ')' if api_key else '❌ 未設定'}")
    print(f"  NOTION_DATABASE_ID: {'已設定' if database_id else '❌ 未設定'}")
    
    if database_id:
        print(f"    - 值: {database_id[:10]}...{database_id[-4:]}")
        print(f"    - 長度: {len(database_id)}")
        print(f"    - 包含連字號: {'-' in database_id}")
        
        # 驗證 UUID 格式
        import re
        uuid_pattern = r'^[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}$'
        is_valid_uuid = bool(re.match(uuid_pattern, database_id.replace('-', '')))
        print(f"    - UUID 格式有效: {'✓' if is_valid_uuid else '❌'}")
    
    if not api_key or not database_id:
        print("\n❌ 環境變數未完整設定，無法繼續診斷")
        return
    
    # 2. 檢查 SDK 版本
    print("\n[Step 2] 檢查 SDK 版本")
    print("-" * 40)
    
    try:
        import notion_client
        sdk_version = getattr(notion_client, "__version__", "unknown")
        print(f"  notion-client 版本: {sdk_version}")
    except ImportError as e:
        print(f"  ❌ notion-client 未安裝: {e}")
        return
    
    # 3. 測試 Notion API 連線
    print("\n[Step 3] 測試 Notion API 連線")
    print("-" * 40)
    
    from notion_client import Client
    from src.namecard.infrastructure.storage.notion_client import NOTION_API_VERSION
    
    print(f"  API 版本: {NOTION_API_VERSION}")
    
    try:
        client = Client(auth=api_key, notion_version=NOTION_API_VERSION)
        print("  ✓ Client 創建成功")
    except Exception as e:
        print(f"  ❌ Client 創建失敗: {e}")
        return
    
    # 4. 測試 databases.retrieve
    print("\n[Step 4] 測試 databases.retrieve")
    print("-" * 40)
    
    try:
        db_response = client.databases.retrieve(database_id=database_id)
        print("  ✓ databases.retrieve 成功")
        print(f"    - 返回的 keys: {list(db_response.keys())}")
        print(f"    - 包含 data_sources: {'data_sources' in db_response}")
        
        if 'data_sources' in db_response:
            data_sources = db_response['data_sources']
            print(f"    - data_sources 數量: {len(data_sources)}")
            if data_sources:
                ds_id = data_sources[0].get('id')
                print(f"    - 第一個 data_source_id: {ds_id[:10]}..." if ds_id else "      (無 ID)")
        else:
            print("    ⚠️ 響應中沒有 data_sources 欄位")
            print("    可能原因:")
            print("      1. API 版本設定不正確")
            print("      2. 資料庫格式不支援")
            
    except Exception as e:
        print(f"  ❌ databases.retrieve 失敗: {e}")
        print(f"    錯誤類型: {type(e).__name__}")
        
        # 提供診斷建議
        error_str = str(e)
        if "Invalid request URL" in error_str:
            print("\n  📋 診斷建議:")
            print("    - 檢查 database_id 格式是否正確")
            print("    - 確保 database_id 是有效的 UUID")
            print("    - 確認 Notion Integration 有權限訪問該資料庫")
        return
    
    # 5. 測試 data_sources 端點
    print("\n[Step 5] 測試 data_sources 端點")
    print("-" * 40)
    
    if 'data_sources' in db_response and db_response['data_sources']:
        ds_id = db_response['data_sources'][0].get('id')
        
        try:
            request_path = f"data_sources/{ds_id}"
            print(f"  請求路徑: {request_path}")
            
            ds_response = client.request(
                method="get",
                path=request_path,
            )
            print("  ✓ data_sources 端點請求成功")
            print(f"    - 返回的 keys: {list(ds_response.keys())}")
            
            if 'properties' in ds_response:
                props = ds_response['properties']
                print(f"    - properties 數量: {len(props)}")
                print(f"    - 欄位名稱: {list(props.keys())[:5]}...")
            
        except Exception as e:
            print(f"  ❌ data_sources 端點請求失敗: {e}")
            print(f"    錯誤類型: {type(e).__name__}")
    else:
        print("  ⚠️ 跳過 (沒有 data_source_id)")
    
    print("\n" + "=" * 80)
    print("診斷完成")
    print("=" * 80)

if __name__ == "__main__":
    diagnose()

