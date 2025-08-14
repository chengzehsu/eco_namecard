# ✅ Zeabur 部署檢查清單

## 🎯 您的部署資訊

- **應用地址**: https://namecard-app.zeabur.app
- **LINE Webhook**: https://namecard-app.zeabur.app/callback
- **健康檢查**: https://namecard-app.zeabur.app/health

## 📋 部署前檢查

### 1. Zeabur 環境變數設定

在 Zeabur Dashboard 中設定以下變數：

- [ ] `LINE_CHANNEL_ACCESS_TOKEN` - LINE Bot Token
- [ ] `LINE_CHANNEL_SECRET` - LINE Bot Secret  
- [ ] `GOOGLE_API_KEY` - Google Gemini API Key
- [ ] `NOTION_API_KEY` - Notion Integration Token
- [ ] `NOTION_DATABASE_ID` - Notion Database ID
- [ ] `SECRET_KEY` - 隨機密鑰（例如：`myapp_secret_2024`）

**可選變數：**
- [ ] `GOOGLE_API_KEY_FALLBACK` - 備用 API Key
- [ ] `SENTRY_DSN` - 錯誤監控（可選）

### 2. GitHub Actions 設定

在 GitHub Repository Settings → Secrets 中設定：

- [ ] `ZEABUR_SERVICE_ID` - Zeabur 服務 ID
- [ ] `ZEABUR_API_TOKEN` - Zeabur API Token

### 3. LINE Developer Console

- [ ] Webhook URL 設為：`https://namecard-app.zeabur.app/callback`
- [ ] 啟用 "Use webhook"
- [ ] 關閉 "Auto-reply messages" 和 "Greeting messages"

### 4. Notion 資料庫設定

- [ ] 建立 Notion 資料庫
- [ ] 新增所有必要欄位（參考 DEPLOYMENT.md）
- [ ] 將 Integration 加入資料庫權限

## 🚀 部署步驟

### 方法一：自動部署（推薦）

```bash
# 1. 推送代碼
git add .
git commit -m "feat: 配置部署到 namecard-app.zeabur.app"
git push origin main

# 2. 等待 GitHub Actions 完成
# 3. 檢查部署狀態
```

### 方法二：手動部署

1. 直接在 Zeabur Dashboard 觸發部署
2. 或推送到 `develop` 分支避免自動部署

## ✅ 部署後驗證

### 1. 健康檢查

```bash
curl https://namecard-app.zeabur.app/health
```

預期回應：
```json
{
  "status": "healthy",
  "service": "LINE Bot 名片識別系統",
  "version": "1.0.0",
  "timestamp": "..."
}
```

### 2. 服務測試

```bash
curl https://namecard-app.zeabur.app/test
```

### 3. LINE Bot 功能測試

1. **加入 Bot 好友**
2. **發送指令測試**：
   - 發送：`help`
   - 發送：名片照片
   - 發送：`批次`
   - 發送：`狀態`

### 4. Webhook 驗證

在 LINE Developer Console 點擊 "Verify" 按鈕，應該顯示成功。

## 🔍 問題排查

如果遇到問題，按以下順序檢查：

### 1. 部署狀態
- [ ] GitHub Actions 是否成功
- [ ] Zeabur Dashboard 顯示 "Running"
- [ ] 健康檢查端點回應正常

### 2. 環境變數
- [ ] 所有必要變數都已設定
- [ ] API Keys 格式正確
- [ ] 沒有多餘空格或特殊字符

### 3. 外部服務
- [ ] LINE Bot Token 有效
- [ ] Google API Key 有配額
- [ ] Notion Integration 權限正確

### 4. 日誌檢查
- [ ] Zeabur Dashboard → Logs
- [ ] GitHub Actions 執行記錄
- [ ] LINE Developer Console 錯誤訊息

## 📞 獲得幫助

如果問題持續：

1. 檢查 [DEPLOYMENT.md](DEPLOYMENT.md) 詳細說明
2. 查看 [README.md](README.md) 故障排除章節
3. 檢視 Zeabur 和 GitHub Actions 日誌
4. 確認所有 API Keys 和設定正確

## 🎉 完成確認

部署成功的標誌：

- [ ] ✅ 健康檢查回應正常
- [ ] ✅ LINE Bot 可以回應 `help` 指令
- [ ] ✅ 上傳名片照片能正常識別
- [ ] ✅ 名片資料自動存入 Notion
- [ ] ✅ 批次功能運作正常

**恭喜！您的 LINE Bot 名片管理系統已成功部署！** 🎉