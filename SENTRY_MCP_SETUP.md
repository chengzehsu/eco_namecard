# Sentry MCP Server 設定指南

## 🎯 概述

Sentry MCP (Model Context Protocol) Server 讓您可以直接在 Claude Code 中：
- 🔍 查詢 Sentry issues 和錯誤
- 📊 分析 release 健康度
- 🚀 監控部署影響
- 📈 取得效能指標

## 📋 設定步驟

### 1. 獲取 Sentry Access Token

1. 前往 [Sentry Settings → Auth Tokens](https://sentry.io/settings/account/api/auth-tokens/)
2. 點擊 "Create New Token"
3. 設定權限：
   ```
   Scopes:
   - project:read
   - org:read
   - event:read
   - team:read
   ```
4. 複製生成的 token

### 2. 更新 MCP 設定

編輯 `~/.cursor/mcp.json`：

```json
{
  "mcpServers": {
    "Sentry": {
      "command": "npx",
      "args": [
        "@sentry/mcp-server@latest",
        "--access-token=YOUR_ACTUAL_TOKEN",
        "--host=sentry.io"
      ],
      "env": {
        "SENTRY_ACCESS_TOKEN": "YOUR_ACTUAL_TOKEN",
        "SENTRY_ORG": "your-org-name",
        "SENTRY_PROJECT": "your-project-name"
      }
    }
  }
}
```

### 3. 專案資訊查詢

要找到您的 Sentry 組織和專案名稱：

1. **組織名稱**: 在 Sentry URL 中 `https://sentry.io/organizations/[ORG-NAME]/`
2. **專案名稱**: 在專案 URL 中 `https://sentry.io/organizations/[ORG]/projects/[PROJECT-NAME]/`

## 🔧 與現有 Release Tracking 整合

我們的 LINE Bot 專案已經設定了完整的 release tracking，MCP server 可以幫助您：

### 查詢特定 Release 的錯誤
```
在 Claude Code 中問：
"查詢 release 1.0.0+abcd123 的所有錯誤"
```

### 監控最新部署
```
"顯示最新部署後的錯誤趨勢"
```

### 分析效能回歸
```
"比較最近兩個 release 的效能指標"
```

## 🚀 常用 MCP 指令

一旦設定完成，您可以在 Claude Code 中使用：

### 錯誤查詢
- "顯示今天的新錯誤"
- "查詢包含 'card_processor' 的錯誤"
- "列出影響最多用戶的錯誤"

### Release 分析
- "比較最近 3 個 release 的穩定性"
- "顯示 release 1.0.0+abc123 的部署影響"
- "分析版本回歸問題"

### 效能監控
- "顯示 API 端點的效能趨勢"
- "找出最慢的操作"
- "分析異常的回應時間"

## 🔍 除錯

### 常見問題

**1. MCP Server 無法連接**
```bash
# 檢查 token 權限
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://sentry.io/api/0/organizations/
```

**2. 專案不存在錯誤**
- 確認組織和專案名稱正確
- 檢查 token 是否有該專案的權限

**3. 權限不足**
- 確認 token 包含必要的 scopes
- 檢查是否有專案存取權限

### 測試連接

設定完成後，在 Claude Code 中執行：
```
"測試 Sentry 連接並顯示專案資訊"
```

## 📊 整合效益

結合我們已實作的功能：

### 1. Release Tracking
- **GitHub Actions** 自動建立 release
- **MCP Server** 查詢 release 健康度
- **API 端點** 提供版本資訊

### 2. 錯誤監控
- **應用程式** 自動發送錯誤到 Sentry
- **MCP Server** 分析錯誤趨勢和影響
- **監控服務** 提供完整上下文

### 3. 效能分析
- **裝飾器** 自動記錄效能指標
- **MCP Server** 查詢和分析趨勢
- **Dashboard** 視覺化效能資料

## 🎯 最佳實務

### 定期檢查
使用 MCP server 定期執行：
```
每日：
- "顯示昨天新增的錯誤"
- "檢查 API 效能異常"

每週：
- "分析本週的錯誤趨勢"
- "比較不同 release 的穩定性"

部署後：
- "檢查新部署的健康度"
- "比較部署前後的錯誤率"
```

### 警報整合
當收到 Sentry 警報時，使用 MCP 快速分析：
```
- "分析錯誤 ID XXX 的影響範圍"
- "查詢相似錯誤的歷史趨勢"
- "顯示受影響用戶的詳細資訊"
```

## 🔄 工作流程範例

### 部署後檢查
```
1. Claude Code: "檢查最新 release 的健康度"
2. 分析回應中的錯誤率和效能指標
3. 如發現異常: "詳細分析錯誤 XXX 的 stack trace"
4. 必要時: "查詢類似錯誤的修復歷史"
```

### 版本回歸分析
```
1. "比較 release 1.0.0+abc123 和 1.0.0+def456"
2. 分析新增的錯誤類型
3. "顯示影響最大的效能回歸"
4. 制定修復優先順序
```

## ✅ 完成檢查清單

- [ ] 取得 Sentry Access Token
- [ ] 更新 ~/.cursor/mcp.json 設定
- [ ] 確認組織和專案名稱正確
- [ ] 測試 MCP server 連接
- [ ] 驗證可以查詢專案資料
- [ ] 與現有 release tracking 整合測試

設定完成後，您將擁有完整的 Sentry 整合：從自動化 release tracking 到互動式錯誤分析！