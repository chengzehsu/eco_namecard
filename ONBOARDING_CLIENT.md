# 名片管理系統 - 客戶設定指南

歡迎使用名片管理系統！本指南將幫助您快速取得所需的各項憑證。

---

## 📋 需要準備的憑證

您需要提供以下三組資訊：

1. **LINE Bot 憑證** (3 項)
2. **Google Gemini API 金鑰** (1 項)
3. **Notion 資訊** (2 項)

預計完成時間：**15-20 分鐘**

---

## 1️⃣ LINE Bot 設定

### 步驟 1: 建立或取得現有的 Messaging API Channel

1. 前往 [LINE Developers Console](https://developers.line.biz/)
2. 使用 LINE 帳號登入
3. 如果沒有 Provider，請先建立一個新的 Provider
4. 建立新的 Messaging API Channel，或使用現有的 Channel

### 步驟 2: 取得 Channel Access Token

1. 在 Messaging API Channel 的設定頁面
2. 找到 **「Channel Access Token」** 區塊
3. 點擊 **「Issue」** 按鈕生成 token（如果還沒有）
4. 複製整個 token（長型文字，開頭通常是 `1234567890abcdef...`）
5. **妥善保管此 token**

### 步驟 3: 取得 Channel Secret

1. 在同一頁面找到 **「Channel Secret」** 區塊
2. 複製 Channel Secret（通常是一串英數字混合）
3. **妥善保管此 secret**

### 步驟 4: 取得 Bot User ID

1. 在 Messaging API Channel 的基本設定頁面
2. 找到 **「Bot User ID」** 或 **「Your user ID」**
3. 這會是一個以 `U` 開頭的長字串（例：`U1234567890abcdefghijklmnopqr`）
4. 複製此 ID

**LINE Bot 憑證檢查清單：**

- [ ] Channel Access Token
- [ ] Channel Secret
- [ ] Bot User ID

---

## 2️⃣ Google Gemini API 金鑰

### 步驟 1: 前往 Google AI Studio

1. 前往 [Google AI Studio](https://aistudio.google.com/app/apikey)
2. 使用 Google 帳號登入

### 步驟 2: 建立 API 金鑰

1. 點擊左側的 **「API Keys」** (如果沒看到，點擊左上角菜單)
2. 點擊 **「Create API key」** 按鈕
3. 選擇 **「Create API key in new project」** 或選擇現有的 Google Cloud 專案
4. 系統會自動生成一個新的 API 金鑰

### 步驟 3: 複製 API 金鑰

1. 複製顯示的 API 金鑰（通常看起來像：`AIzaSy...`）
2. **妥善保管此金鑰**
3. 您可以在這裡隨時查看或重新生成此金鑰

**Google Gemini API 檢查清單：**

- [ ] API Key

---

## 3️⃣ Notion 資訊設定

### 步驟 1: 建立 Notion Integration

1. 前往 [Notion Integrations](https://www.notion.so/my-integrations)
2. 使用 Notion 帳號登入
3. 點擊 **「Create new integration」**
4. 填寫 Integration 名稱（例：「名片管理系統」）
5. 選擇關聯的 Workspace
6. 點擊 **「Submit」**

### 步驟 2: 複製 Integration Token

1. 在新建立的 Integration 頁面
2. 找到 **「Internal Integration Token」** 或 **「Secrets」** 區塊
3. 複製 Integration Token（通常以 `secret_` 開頭，是一長串英數字）
4. **妥善保管此 token**

### 步驟 3: 取得或建立 Notion Database

#### 選項 A: 使用現有的 Database

1. 在 Notion 中開啟要使用的 Database
2. 複製 Database 的 URL
3. Database ID 在 URL 中，格式為：`https://www.notion.so/yourname/...?v=...` 中的長串字符

#### 選項 B: 建立新的 Database

1. 在 Notion 中建立新的 Database（推薦使用表格視圖）
2. 確保 Database 至少包含以下欄位：
   - **名字** (Title) - 必要
   - **公司** (Text)
   - **職稱** (Text)
   - **電話** (Text 或 Phone Number)
   - **Email** (Email)
3. 複製 Database URL 取得 Database ID

### 步驟 4: 授予 Integration 存取權限

1. 在 Notion Database 頁面
2. 點擊右上角的 **「Share」** 或 **「...」** 菜單
3. 選擇 **「Invite」** 或 **「Add connections」**
4. 搜尋並選擇您剛建立的 Integration
5. 確認授予存取權限

### 步驟 5: 複製 Database ID

1. 在 Notion 中開啟要使用的 Database
2. 複製 URL，例如：`https://www.notion.so/abc123def456ghi?v=xyz789`
3. Database ID 是 URL 中 `/` 後面、`?` 前面的部分
4. 複製此 ID（通常是 32 個字符）

**Notion 設定檢查清單：**

- [ ] Integration Token (API Key)
- [ ] Database ID
- [ ] 確認 Integration 已被授予 Database 存取權限

---

## ✅ 最終檢查清單

將以下資訊收集完整並提供給系統管理員：

| 項目                      | 憑證                  | 狀態 |
| ------------------------- | --------------------- | ---- |
| LINE Channel Access Token | `[長串英數字]`        | ☐    |
| LINE Channel Secret       | `[英數字混合]`        | ☐    |
| LINE Bot User ID          | `U[長串英數字]`       | ☐    |
| Google Gemini API Key     | `AIzaSy...`           | ☐    |
| Notion Integration Token  | `secret_[長串英數字]` | ☐    |
| Notion Database ID        | `[32 個字符]`         | ☐    |

---

## 🔒 安全建議

- **不要在公開場所分享這些憑證**
- **使用加密方式傳輸**（如密碼管理器、加密郵件、Slack 私訊）
- **定期檢查 API 使用情況**
- 如果懷疑憑證洩露，應立即重新生成

---

## ❓ 常見問題

**Q: 我需要建立新的 LINE Bot 嗎？**
A: 如果您已有 LINE 商業帳號和 Messaging API Channel，可以直接使用現有的。如果沒有，請先建立一個。

**Q: Gemini API 金鑰會扣費嗎？**
A: Google 提供免費額度。請在 [Google Cloud Console](https://console.cloud.google.com/) 檢查您的配額和使用情況。

**Q: Notion Database 可以是什麼格式？**
A: 可以是表格、看板或任何格式，但必須包含名字欄位。推薦使用表格視圖便於管理。

**Q: 如果我忘記了某個憑證怎麼辦？**
A: 您可以隨時登入各服務重新查看或重新生成。建議使用密碼管理器安全保存。

---

## 📞 需要協助？

如有任何問題，請聯絡系統管理員提供您的操作步驟和錯誤訊息。
