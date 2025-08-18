# Sentry Release 追蹤設定指南

## 🎯 概述

本指南說明如何為 LINE Bot 名片識別系統設定完整的 Sentry release 追蹤功能，包括：

- ✅ Release 版本追蹤
- ✅ Source context 上傳  
- ✅ 部署通知
- ✅ 錯誤與特定版本關聯

## 📋 必要設定

### 1. Sentry 專案設定

1. **註冊 Sentry 帳號**: 前往 https://sentry.io 註冊
2. **建立新專案**: 選擇 Python/Flask 專案類型
3. **獲取 DSN**: 複製專案的 DSN URL

### 2. GitHub Secrets 設定

在 GitHub 專案設定中加入以下 Secrets：

```bash
# 必要的 Secrets
SENTRY_AUTH_TOKEN=你的_Sentry_Auth_Token
SENTRY_ORG=你的_Sentry_組織名稱
SENTRY_PROJECT=你的_Sentry_專案名稱
```

#### 獲取 Sentry Auth Token

1. 前往 Sentry → Settings → Account → API → Auth Tokens
2. 點擊 "Create New Token"
3. 設定權限：
   - **Scopes**: `project:read`, `project:write`, `project:releases`, `org:read`
   - **Projects**: 選擇你的專案
4. 複製生成的 token

### 3. Zeabur 環境變數設定

在 Zeabur 專案中設定：

```bash
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
SENTRY_ENVIRONMENT=production
```

## 🚀 部署流程

### GitHub Actions 自動流程

當推送到 `main` 分支時，GitHub Actions 會自動：

1. **準備 Release 資訊**
   - 獲取 Git commit hash
   - 生成版本號 (格式: `1.0.0+abcd123`)
   - 設定建置時間

2. **建立 Sentry Release**
   - 在 Sentry 中建立新的 release
   - 關聯 Git commit 資訊
   - 設定 commit 歷史

3. **上傳 Source Context**
   - 上傳 Python 原始碼到 Sentry
   - 提供完整的錯誤上下文
   - 支援 stack trace 中的程式碼檢視

4. **部署到 Zeabur**
   - Zeabur 自動部署
   - 健康檢查驗證

5. **完成 Release**
   - 標記 release 為已部署
   - 建立部署記錄
   - 設定環境和 URL

## 📊 監控功能

### 版本追蹤

每個錯誤都會包含：
- **Release**: `1.0.0+abcd123`
- **Git Commit**: `abcd123`
- **Environment**: `production`
- **Deploy Time**: 部署時間戳

### 錯誤上下文

Sentry 中的錯誤會顯示：
- 完整的 stack trace
- 原始程式碼內容
- 版本和部署資訊
- 用戶和請求上下文

### 效能監控

自動追蹤：
- API 回應時間
- AI 處理效能
- 資料庫操作時間
- 異常操作偵測

## 🔧 API 端點

### 版本資訊
```bash
GET https://namecard-app.zeabur.app/version
```

回應範例：
```json
{
  "status": "success",
  "application": {
    "name": "LINE Bot 名片識別系統",
    "service": "namecard-processing"
  },
  "version": {
    "version": "1.0.0",
    "git_commit": "abcd123",
    "git_branch": "main",
    "release_name": "1.0.0+abcd123",
    "build_time": "2024-01-15T10:30:00Z"
  },
  "sentry": {
    "release": "1.0.0+abcd123",
    "environment": "production"
  }
}
```

### 部署資訊
```bash
GET https://namecard-app.zeabur.app/deployment
```

### 健康檢查 (含版本)
```bash
GET https://namecard-app.zeabur.app/health
```

## 🧪 測試

### 自動測試腳本
```bash
python test_release_tracking.py
```

此腳本會測試：
- ✅ 版本管理器功能
- ✅ 監控服務設定
- ✅ Sentry 整合
- ✅ API 端點回應

### 手動驗證步驟

1. **檢查版本端點**:
   ```bash
   curl https://namecard-app.zeabur.app/version
   ```

2. **觸發測試錯誤**:
   ```bash
   python force-sentry-test.py
   ```

3. **檢查 Sentry Dashboard**:
   - 前往 https://sentry.io
   - 查看 Issues 頁面是否有新錯誤
   - 確認錯誤包含正確的 release 資訊

## 📈 Dashboard 監控

### Sentry Dashboard 檢查項目

1. **Issues 頁面**:
   - 錯誤按 release 分組
   - 顯示影響的用戶數
   - Stack trace 包含程式碼

2. **Releases 頁面**:
   - 顯示所有部署的版本
   - 每個版本的錯誤統計
   - 部署健康度指標

3. **Performance 頁面**:
   - API 端點效能
   - 事務時間分佈
   - 異常操作偵測

### 關鍵指標

- **錯誤率**: < 1%
- **回應時間**: < 3 秒
- **版本回歸**: 新版本錯誤率不應顯著增加
- **用戶影響**: 追蹤每個錯誤影響的用戶數

## 🚨 警報設定

建議設定以下警報規則：

### 立即通知
- 新錯誤類型出現
- 錯誤率超過 5%
- 單一錯誤超過 10 次/小時
- 關鍵 API 回應時間 > 5 秒

### 每日摘要
- 錯誤趨勢分析
- 效能變化報告
- 用戶行為統計

## 🔧 故障排除

### 常見問題

**1. Release 沒有在 Sentry 中出現**
- 檢查 GitHub Secrets 是否正確設定
- 確認 SENTRY_AUTH_TOKEN 權限充足
- 查看 GitHub Actions 日誌

**2. 錯誤沒有 release 資訊**
- 確認 SENTRY_DSN 環境變數已設定
- 檢查應用程式中的 Sentry 初始化
- 驗證版本管理器是否正常運作

**3. Source context 沒有上傳**
- 檢查 GitHub Actions 中的 Sentry CLI 步驟
- 確認檔案路徑設定正確
- 查看 Sentry CLI 輸出日誌

### 除錯工具

```bash
# 檢查 Sentry 配置
curl https://namecard-app.zeabur.app/debug/sentry

# 測試監控功能
python test_sentry_monitoring.py

# 完整功能測試
python test_release_tracking.py
```

## 📝 維護清單

### 每週檢查
- [ ] 查看 Sentry Dashboard 錯誤趨勢
- [ ] 檢查 release 部署是否正常記錄
- [ ] 驗證效能指標是否在正常範圍

### 每月檢查
- [ ] 更新 Sentry 警報規則閾值
- [ ] 檢查 source context 上傳是否完整
- [ ] 分析版本回歸和效能變化

### 版本更新時
- [ ] 確認新版本在 Sentry 中正確顯示
- [ ] 檢查 Git commit 關聯是否正確
- [ ] 驗證錯誤能正確歸類到新版本

## 🎉 完成！

設定完成後，你將擁有：

- 🔍 **精確的錯誤追蹤**: 每個錯誤都關聯到特定版本
- 📊 **版本影響分析**: 了解每個版本的穩定性
- 🚀 **自動化部署監控**: 部署後立即了解系統健康狀況
- 📈 **效能回歸偵測**: 快速發現效能問題
- 🔧 **快速除錯**: 在 Sentry 中直接查看程式碼上下文

有任何問題請參考 [Sentry 官方文檔](https://docs.sentry.io/) 或檢查專案中的測試腳本。