# 🚀 Zeabur 部署設置指南

## 問題：為什麼 Zeabur 沒有被觸發？

**原因**: Zeabur 需要在 Dashboard 中手動連接 GitHub Repository，`zeabur.json` 檔案本身不會自動觸發部署。

## 📋 完整設置步驟

### 1. 登入 Zeabur Dashboard

前往：https://zeabur.com/dashboard

### 2. 創建或選擇專案

1. 點擊 **"Create Project"** 或選擇現有專案
2. 專案名稱建議：`namecard-app`

### 3. 添加服務並連接 GitHub

1. 在專案中點擊 **"Add Service"**
2. 選擇 **"GitHub"** 
3. **授權 Zeabur** 存取您的 GitHub 帳號
4. 選擇 Repository: **`chengzehsu/eco_namecard`**
5. 選擇分支: **`main`**
6. 點擊 **"Deploy"**

### 4. 設置環境變數

在 Zeabur 服務設定中，添加以下環境變數：

**必要變數：**
```bash
LINE_CHANNEL_ACCESS_TOKEN=<您的 LINE Bot Token>
LINE_CHANNEL_SECRET=<您的 LINE Bot Secret>
GOOGLE_API_KEY=<您的 Google Gemini API Key>
NOTION_API_KEY=<您的 Notion Integration Key>
NOTION_DATABASE_ID=<您的 Notion Database ID>
SECRET_KEY=linebot_secret_2024
```

**可選變數：**
```bash
GOOGLE_API_KEY_FALLBACK=<備用 API Key>
SENTRY_DSN=<如果有 Sentry 監控>
```

### 5. 設置自訂域名 (如果需要)

1. 在服務設定中找到 **"Domain"** 部分
2. 添加自訂域名：`namecard-app.zeabur.app`
3. 或使用 Zeabur 提供的預設域名

### 6. 啟用自動部署

確保以下設定已啟用：
- ✅ **Auto Deploy**: 啟用 (Git push 時自動部署)
- ✅ **Source**: GitHub Repository 已連接
- ✅ **Branch**: main

## 🔍 檢查部署狀態

### 方法 1: Zeabur Dashboard
1. 前往 https://zeabur.com/dashboard
2. 選擇您的專案和服務
3. 查看 **"Deployments"** 標籤
4. 查看 **"Logs"** 了解部署進度

### 方法 2: 應用 URL
```bash
# 檢查應用是否運行
curl https://namecard-app.zeabur.app/health

# 預期回應
{
  "status": "healthy",
  "service": "LINE Bot 名片識別系統",
  "version": "1.0.0",
  "timestamp": "..."
}
```

## 🔧 觸發手動部署

如果自動部署沒有觸發：

### 選項 1: Zeabur Dashboard
1. 前往服務頁面
2. 點擊 **"Deploy"** 按鈕
3. 選擇最新的 commit

### 選項 2: GitHub 推送
```bash
# 進行一個小改動觸發部署
echo "# Deploy trigger" >> README.md
git add .
git commit -m "trigger: manual Zeabur deployment"
git push origin main
```

## 📊 驗證完整設置

當設置完成後，每次推送到 `main` 分支應該：

1. ✅ **GitHub Actions 執行** (測試、安全掃描)
2. ✅ **Zeabur 自動檢測推送** 
3. ✅ **開始部署程序**
4. ✅ **應用更新** 到 https://namecard-app.zeabur.app

## 🐛 常見問題排除

### Zeabur 沒有自動部署
1. **檢查 GitHub 整合**: 確認 Repository 已正確連接
2. **檢查分支**: 確認監聽的是 `main` 分支
3. **檢查權限**: 確認 Zeabur 有 Repository 存取權限

### 部署失敗
1. **檢查環境變數**: 確認所有必要變數已設定
2. **查看部署日誌**: Zeabur Dashboard → Logs
3. **檢查 Python 版本**: 確認 runtime 相容性

### 應用無法存取
1. **檢查域名設定**: 確認域名配置正確
2. **檢查服務狀態**: Dashboard 顯示 "Running"
3. **檢查健康檢查**: `/health` 端點回應正常

## 🎯 下一步

設置完成後：

1. **設定 LINE Webhook URL**: 
   ```
   https://namecard-app.zeabur.app/callback
   ```

2. **建立 Notion 資料庫** (參考 DEPLOYMENT.md)

3. **測試 LINE Bot 功能**

---

## 📞 需要幫助？

如果仍有問題：
1. 檢查 Zeabur Dashboard 中的 **Logs** 和 **Events**
2. 確認 GitHub Repository 在 Zeabur 中正確連接
3. 驗證所有環境變數都已正確設定

**記住**: Zeabur 需要 GitHub 整合才能自動部署，單純的 `zeabur.json` 不會觸發部署！