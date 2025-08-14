# 🎉 部署成功！下一步設置指南

恭喜！您的 LINE Bot 名片管理系統已成功部署到 Zeabur！

## 📋 部署後檢查清單

### 1. ✅ 已完成
- [x] GitHub Repository 設為 Public
- [x] Zeabur 服務創建成功
- [x] 代碼成功部署到 Zeabur
- [x] 應用 URL: https://namecard-app.zeabur.app

### 2. 🔧 需要完成的設置

#### A. 在 Zeabur Dashboard 設置環境變數

**前往**: Zeabur Dashboard → 您的服務 → Environment Variables

**必要環境變數**:
```bash
LINE_CHANNEL_ACCESS_TOKEN=<您的 LINE Bot Token>
LINE_CHANNEL_SECRET=<您的 LINE Bot Secret>
GOOGLE_API_KEY=<您的 Google Gemini API Key>
NOTION_API_KEY=<您的 Notion Integration Token>
NOTION_DATABASE_ID=<您的 Notion Database ID>
SECRET_KEY=linebot_namecard_2024
```

**可選環境變數**:
```bash
GOOGLE_API_KEY_FALLBACK=<備用 Google API Key>
SENTRY_DSN=<Sentry 監控 DSN>
DEBUG=False
```

#### B. 重新部署應用

設置環境變數後：
1. 在 Zeabur Dashboard 點擊 **"Redeploy"**
2. 或推送一個小改動觸發重新部署：
   ```bash
   git commit --allow-empty -m "trigger: restart with env vars"
   git push origin main
   ```

## 🚀 驗證部署狀態

### 檢查應用健康狀態
```bash
curl https://namecard-app.zeabur.app/health
```

**預期成功回應**:
```json
{
  "status": "healthy",
  "service": "LINE Bot 名片識別系統",
  "version": "1.0.0",
  "timestamp": "..."
}
```

### 檢查服務配置
```bash
curl https://namecard-app.zeabur.app/test
```

**預期成功回應**:
```json
{
  "message": "LINE Bot 服務運行正常",
  "config": {
    "rate_limit": 50,
    "batch_limit": 10,
    "max_image_size": "10MB"
  }
}
```

## 📱 設置 LINE Bot Webhook

應用運行正常後：

1. **前往 LINE Developer Console**
   - https://developers.line.biz/

2. **設置 Webhook URL**
   ```
   https://namecard-app.zeabur.app/callback
   ```

3. **啟用設定**
   - ✅ Use webhook
   - ❌ Auto-reply messages (關閉)
   - ❌ Greeting messages (關閉)

4. **驗證 Webhook**
   - 點擊 "Verify" 按鈕
   - 應該顯示成功

## 🗃️ 設置 Notion 資料庫

### 1. 建立 Notion 資料庫

在 Notion 中建立新的資料庫，包含以下屬性：

| 屬性名稱 | 類型 | 說明 |
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

### 2. 設置 Select 選項

為 **狀態** 屬性添加選項：
- `已處理`
- `待處理`

### 3. 獲取 Database ID

1. 複製資料庫 URL
2. Database ID 是 URL 中的 32 位字串
3. 例如：`https://notion.so/myworkspace/abc123def456...`
4. Database ID 就是 `abc123def456...` 部分

### 4. 設置 Integration

1. 前往 https://www.notion.so/my-integrations
2. 建立新的 Integration
3. 取得 API Token
4. 回到資料庫 → Share → Invite 您的 Integration

## 🧪 測試完整功能

環境設置完成後：

### 1. 基本功能測試
- 加入 LINE Bot 好友
- 發送 `help` 指令
- 應該收到使用說明

### 2. 名片識別測試
- 發送清晰的名片照片
- 等待 AI 處理（5-10秒）
- 應該收到識別結果和 Notion 連結

### 3. 批次模式測試
- 發送 `批次` 進入批次模式
- 連續發送 2-3 張名片照片
- 發送 `結束批次` 查看統計結果

## 📊 監控和維護

### Zeabur 監控
- **Metrics**: 查看 CPU/記憶體使用
- **Logs**: 監控應用日誌
- **Deployments**: 追蹤部署歷史

### GitHub Actions
- **Actions**: https://github.com/chengzehsu/eco_namecard/actions
- 每次推送自動執行測試和安全檢查

## 🎯 完成確認

當以下都正常工作時，部署就完全成功了：

- [ ] ✅ 健康檢查: `https://namecard-app.zeabur.app/health`
- [ ] ✅ LINE Bot 回應 `help` 指令
- [ ] ✅ 名片照片能正常識別
- [ ] ✅ 識別結果存入 Notion 資料庫
- [ ] ✅ 批次模式正常工作

## 🚀 恭喜！

您的 LINE Bot 名片管理系統現在已經：
- ✅ 成功部署到雲端
- ✅ 具備 CI/CD 自動部署
- ✅ 整合 AI 名片識別功能
- ✅ 自動存儲到 Notion 資料庫

現在可以開始使用您的智能名片管理系統了！🎉