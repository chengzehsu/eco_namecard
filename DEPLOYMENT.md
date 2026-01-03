# 🚀 Zeabur 部署指南

## 📝 部署清單

您的 LINE Bot 將部署到：**https://namecard-app-sjc.zeabur.app**

⚠️ **重要**: 需要在 Zeabur Dashboard 中手動連接 GitHub Repository 才能觸發自動部署！

### 1. 🔧 Zeabur Dashboard 環境變數設定

在 Zeabur Dashboard → 您的專案 → Environment Variables 中設置：

#### 必要環境變數 ✅

```bash
# LINE Bot 配置
LINE_CHANNEL_ACCESS_TOKEN=<您的 LINE Bot Token>
LINE_CHANNEL_SECRET=<您的 LINE Bot Secret>

# Google AI 配置
GOOGLE_API_KEY=<您的 Google Gemini API Key>

# Notion 配置  
NOTION_API_KEY=<您的 Notion Integration Token>
NOTION_DATABASE_ID=<您的 Notion Database ID>

# 應用配置
SECRET_KEY=<隨機字串，例如: mysecretkey123>
```

#### 可選環境變數 ⚙️

```bash
# 備用 API Key（建議設置）
GOOGLE_API_KEY_FALLBACK=<備用 Google API Key>

# 監控配置（可選）
SENTRY_DSN=<您的 Sentry DSN>

# 應用配置（使用預設值即可）
APP_PORT=5002
RATE_LIMIT_PER_USER=50
BATCH_SIZE_LIMIT=10
MAX_IMAGE_SIZE=10485760
DEBUG=False
```

### 2. 📱 LINE Developer Console 設定

1. 前往 [LINE Developer Console](https://developers.line.biz/)
2. 選擇您的 LINE Bot
3. 在 **Messaging API** 設定中：
   - **Webhook URL**: `https://namecard-app-sjc.zeabur.app/callback`
   - **Use webhook**: 啟用
   - **Verify**: 點擊驗證（部署完成後）

### 3. 🗃️ Notion 資料庫設定

#### 建立 Notion 資料庫

1. 在 Notion 中建立新的資料庫
2. 新增以下欄位（屬性）：

| 欄位名稱 | 類型 | 說明 |
|---------|------|------|
| 姓名 | Title | 名片姓名（主鍵） |
| 公司 | Text | 公司名稱 |
| 職稱 | Text | 職務頭銜 |
| 電話 | Phone | 電話號碼 |
| Email | Email | 電子郵件 |
| 地址 | Text | 地址資訊 |
| 網站 | URL | 公司網站 |
| 傳真 | Text | 傳真號碼 |
| LINE ID | Text | LINE ID |
| 信心度 | Number | AI 識別信心度 |
| 品質評分 | Number | 圖片品質評分 |
| 建立時間 | Date | 建立日期 |
| LINE用戶 | Text | LINE 用戶 ID |
| 狀態 | Select | 處理狀態 |

3. 為 **狀態** 欄位新增選項：
   - `已處理`
   - `待處理`

#### 設定 Notion Integration

1. 前往 [Notion Integrations](https://www.notion.so/my-integrations)
2. 點擊 **+ New integration**
3. 設定 Integration：
   - **Name**: LINE Bot Namecard System
   - **Logo**: 可選
   - **Associated workspace**: 選擇您的工作區
4. 建立後取得 **Internal Integration Token**
5. 回到您的資料庫，點擊右上角 **Share**
6. **Invite** 您剛建立的 Integration

### 4. 🔐 GitHub Actions Secrets 設定

在 GitHub Repository → Settings → Secrets and variables → Actions：

```bash
# Zeabur 部署配置
ZEABUR_SERVICE_ID=<從 Zeabur Dashboard 取得>
ZEABUR_API_TOKEN=<從 Zeabur 帳號設定取得>
```

**如何取得 Zeabur 資訊：**
- **Service ID**: Zeabur Dashboard → 您的服務 → Settings → Service ID
- **API Token**: Zeabur Dashboard → Account Settings → Developer → Create Token

### 5. ⚡ 部署流程

#### 自動部署（推薦）

```bash
# 1. 確認所有環境變數已在 Zeabur 設定完成
# 2. 推送代碼觸發自動部署
git add .
git commit -m "feat: 配置 Zeabur 部署"
git push origin main

# 3. GitHub Actions 會自動：
#    - 執行測試
#    - 安全性檢查  
#    - 部署到 Zeabur
#    - 驗證健康狀態
```

#### 手動部署

如果您想跳過 GitHub Actions：

1. 在 Zeabur Dashboard 中手動觸發部署
2. 或推送到非 main 分支避免自動部署

### 6. ✅ 部署驗證

部署完成後，檢查以下端點：

```bash
# 健康檢查
curl https://namecard-app-sjc.zeabur.app/health

# 服務測試  
curl https://namecard-app-sjc.zeabur.app/test

# 預期回應
# {"status":"healthy","service":"LINE Bot 名片識別系統",...}
```

### 7. 🧪 LINE Bot 測試

1. **加入 LINE Bot 好友**
2. **測試基本功能**：
   ```
   發送: help
   回應: 顯示使用說明
   
   發送名片照片
   回應: AI 識別結果 + Notion 連結
   
   發送: 批次
   回應: 進入批次模式
   
   發送: 狀態  
   回應: 顯示目前狀態
   ```

### 8. 📊 監控和日誌

#### Zeabur 監控
- **Metrics**: Zeabur Dashboard → Metrics 查看 CPU/記憶體使用
- **Logs**: Zeabur Dashboard → Logs 查看應用日誌
- **Health**: 每30秒自動健康檢查

#### GitHub Actions 監控
- **Build Status**: GitHub Repository → Actions 查看建置狀態
- **Deploy History**: 每次推送的部署記錄
- **Test Reports**: 測試結果和覆蓋率報告

## 🐛 常見問題排除

### 部署失敗

```bash
# 1. 檢查 Zeabur 日誌
# 2. 確認環境變數正確設定
# 3. 檢查 GitHub Actions 錯誤訊息
```

### LINE Bot 無回應

```bash
# 1. 檢查 Webhook URL 設定
# 2. 驗證 LINE_CHANNEL_SECRET
# 3. 查看 Zeabur 日誌
```

### Notion 儲存失敗

```bash
# 1. 確認 NOTION_API_KEY 正確
# 2. 檢查 Integration 權限
# 3. 驗證資料庫結構
```

## 📞 支援

如果遇到問題：

1. 檢查 Zeabur Dashboard → Logs
2. 查看 GitHub Actions 執行結果
3. 參考 `README.md` 和 `CLAUDE.md`
4. 檢查環境變數設定

---

## 🎉 完成！

設定完成後，您的 LINE Bot 將在：
- **服務地址**: https://namecard-app-sjc.zeabur.app
- **健康檢查**: https://namecard-app-sjc.zeabur.app/health
- **Webhook**: https://namecard-app-sjc.zeabur.app/callback

祝您使用愉快！🚀