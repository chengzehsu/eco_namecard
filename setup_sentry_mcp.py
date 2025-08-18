#!/usr/bin/env python3
"""
Sentry MCP Server 快速設定腳本
幫助您配置 Cursor/Claude Code 的 Sentry 整合
"""

import os
import json
import sys
import requests
from pathlib import Path


def check_sentry_token(token, org=None):
    """驗證 Sentry token 和權限"""
    print("🔍 驗證 Sentry token...")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        # 測試基本 API 存取
        response = requests.get("https://sentry.io/api/0/", headers=headers, timeout=10)
        
        if response.status_code == 200:
            print("✅ Token 有效")
            
            # 獲取組織列表
            org_response = requests.get("https://sentry.io/api/0/organizations/", headers=headers, timeout=10)
            if org_response.status_code == 200:
                organizations = org_response.json()
                print(f"✅ 可存取 {len(organizations)} 個組織")
                
                for org_data in organizations:
                    print(f"   • {org_data['name']} (slug: {org_data['slug']})")
                    
                    if org and org_data['slug'] == org:
                        # 獲取專案列表
                        proj_response = requests.get(
                            f"https://sentry.io/api/0/organizations/{org}/projects/",
                            headers=headers, timeout=10
                        )
                        if proj_response.status_code == 200:
                            projects = proj_response.json()
                            print(f"   📁 {org} 組織中的專案:")
                            for proj in projects:
                                print(f"      • {proj['name']} (slug: {proj['slug']})")
                
                return True, organizations
            else:
                print(f"⚠️ 無法獲取組織列表: {org_response.status_code}")
                return False, []
                
        elif response.status_code == 401:
            print("❌ Token 無效或已過期")
            return False, []
        else:
            print(f"❌ API 存取失敗: {response.status_code}")
            return False, []
            
    except requests.RequestException as e:
        print(f"❌ 網路錯誤: {e}")
        return False, []


def find_mcp_config():
    """尋找 MCP 設定檔案"""
    possible_paths = [
        Path.home() / ".cursor" / "mcp.json",
        Path.home() / ".config" / "cursor" / "mcp.json",
        Path("/Users/user/.cursor/mcp.json")  # 使用者提供的路徑
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    return None


def backup_mcp_config(config_path):
    """備份現有的 MCP 設定"""
    backup_path = config_path.with_suffix('.json.backup')
    try:
        import shutil
        shutil.copy2(config_path, backup_path)
        print(f"✅ 已備份原設定到: {backup_path}")
        return True
    except Exception as e:
        print(f"⚠️ 備份失敗: {e}")
        return False


def update_mcp_config(config_path, token, org, project):
    """更新 MCP 設定檔案"""
    try:
        # 讀取現有設定
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 更新 Sentry 設定
        config.setdefault("mcpServers", {})
        config["mcpServers"]["Sentry"] = {
            "command": "npx",
            "args": [
                "@sentry/mcp-server@latest",
                f"--access-token={token}",
                "--host=sentry.io"
            ],
            "env": {
                "SENTRY_ACCESS_TOKEN": token,
                "SENTRY_ORG": org,
                "SENTRY_PROJECT": project
            }
        }
        
        # 寫回檔案
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"✅ MCP 設定已更新: {config_path}")
        return True
        
    except Exception as e:
        print(f"❌ 更新設定失敗: {e}")
        return False


def create_test_commands():
    """建立測試指令範例"""
    commands = [
        "# 基本連接測試",
        "在 Claude Code 中執行: '測試 Sentry 連接'",
        "",
        "# 查詢錯誤",
        "顯示今天的新錯誤",
        "查詢包含 'namecard' 的錯誤",
        "列出影響最多用戶的 top 5 錯誤",
        "",
        "# Release 分析",
        "顯示最新 release 的健康度",
        "比較最近兩個 release 的錯誤率",
        "分析 release 部署後的影響",
        "",
        "# 效能監控", 
        "顯示 API 端點效能統計",
        "找出回應時間最慢的操作",
        "分析效能趨勢變化",
        "",
        "# 整合查詢",
        f"檢查專案 '{sys.argv[3] if len(sys.argv) > 3 else 'YOUR_PROJECT'}' 的整體健康度",
        "分析最近 7 天的錯誤趨勢"
    ]
    
    test_file = Path("sentry_mcp_test_commands.txt")
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(commands))
    
    print(f"✅ 測試指令已儲存到: {test_file}")


def main():
    """主設定流程"""
    print("🚀 Sentry MCP Server 設定工具")
    print("=" * 50)
    
    # 檢查參數
    if len(sys.argv) < 4:
        print("使用方法:")
        print(f"  python {sys.argv[0]} <SENTRY_TOKEN> <ORG_SLUG> <PROJECT_SLUG>")
        print()
        print("範例:")
        print(f"  python {sys.argv[0]} sntrys_abc123... my-org my-project")
        print()
        print("取得資訊的方法:")
        print("  1. Token: https://sentry.io/settings/account/api/auth-tokens/")
        print("  2. Org Slug: Sentry URL 中的組織名稱")
        print("  3. Project Slug: Sentry URL 中的專案名稱")
        sys.exit(1)
    
    token = sys.argv[1]
    org_slug = sys.argv[2]
    project_slug = sys.argv[3]
    
    print(f"🔧 設定參數:")
    print(f"   • 組織: {org_slug}")
    print(f"   • 專案: {project_slug}")
    print(f"   • Token: {token[:20]}...")
    print()
    
    # 驗證 token
    valid, organizations = check_sentry_token(token, org_slug)
    if not valid:
        print("❌ Token 驗證失敗，請檢查 token 和權限")
        sys.exit(1)
    
    # 檢查組織存在
    org_found = any(org['slug'] == org_slug for org in organizations)
    if not org_found:
        print(f"❌ 找不到組織 '{org_slug}'")
        print("可用的組織:")
        for org in organizations:
            print(f"   • {org['slug']}")
        sys.exit(1)
    
    print()
    
    # 尋找 MCP 設定檔案
    config_path = find_mcp_config()
    if not config_path:
        print("❌ 找不到 MCP 設定檔案")
        print("預期位置:")
        print("   • ~/.cursor/mcp.json")
        print("   • ~/.config/cursor/mcp.json")
        
        # 詢問是否建立新檔案
        response = input("\n是否建立新的 MCP 設定檔案？ (y/N): ")
        if response.lower() == 'y':
            config_path = Path.home() / ".cursor" / "mcp.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 建立基本設定
            basic_config = {"mcpServers": {}}
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(basic_config, f, indent=2)
            print(f"✅ 已建立: {config_path}")
        else:
            sys.exit(1)
    
    print(f"📄 MCP 設定檔案: {config_path}")
    
    # 備份現有設定
    backup_mcp_config(config_path)
    
    # 更新設定
    if update_mcp_config(config_path, token, org_slug, project_slug):
        print()
        print("🎉 設定完成！")
        print()
        print("📋 下一步:")
        print("1. 重新啟動 Cursor/Claude Code")
        print("2. 等待 MCP server 初始化")
        print("3. 在 Claude Code 中測試連接")
        print()
        
        # 建立測試指令檔案
        create_test_commands()
        
        print("🧪 快速測試:")
        print("在 Claude Code 中執行: '測試 Sentry 連接並顯示專案資訊'")
        print()
        print("📚 更多資訊請參考: SENTRY_MCP_SETUP.md")
        
    else:
        print("❌ 設定失敗")
        sys.exit(1)


if __name__ == "__main__":
    main()