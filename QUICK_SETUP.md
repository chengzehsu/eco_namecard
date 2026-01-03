# ⚡ 5 分鐘快速部署指南

## 🎯 您需要做的 3 個步驟

### 步驟 1: 創建 GitHub Repository (2 分鐘)

1. **點擊這個連結**: [創建新的 Repository](https://github.com/new)

2. **填寫表單**:
   ```
   Repository name: Ecofirst_namecard
   Description: LINE Bot 名片管理系統 - AI 智能識別名片並自動存入 Notion
   ✅ Public (推薦)
   ❌ 不要勾選 Add a README file
   ❌ 不要勾選 Add .gitignore  
   ❌ 不要勾選 Choose a license
   ```

3. **點擊 "Create repository"**

### 步驟 2: 推送代碼到 GitHub (1 分鐘)

回到這個終端機，複製貼上這些指令：

```bash
git remote add origin https://github.com/chengzehsu/eco_namecard.git
git branch -M main
git push -u origin main
```

### 步驟 3: 設置 GitHub Actions Secrets (2 分鐘)

推送完成後：

1. **前往**: https://github.com/chengzehsu/eco_namecard/settings/secrets/actions

2. **點擊 "New repository secret"** 並添加兩個 secret:

   **第一個 Secret:**
   ```
   Name: ZEABUR_SERVICE_ID
   Secret: <從 Zeabur Dashboard 複製>
   ```
   
   **第二個 Secret:**
   ```
   Name: ZEABUR_API_TOKEN  
   Secret: <從 Zeabur Account Settings 複製>
   ```

## 🔍 如何獲取 Zeabur 資訊

### 獲取 Service ID:
1. 前往 [Zeabur Dashboard](https://zeabur.com/dashboard)
2. 找到您的 namecard-app 專案
3. 點擊服務 → Settings → 複製 Service ID

### 獲取 API Token:
1. Zeabur Dashboard 右上角頭像 → Account Settings
2. 左側 Developer → Create Token
3. 輸入名稱: `GitHub Actions`
4. 複製生成的 Token

## ✅ 完成確認

設置完成後：
- GitHub Actions 會自動執行
- 您的應用會部署到: https://namecard-app-sjc.zeabur.app
- 健康檢查: https://namecard-app-sjc.zeabur.app/health

## 🎉 成功後的下一步

1. **設置 LINE Webhook**: `https://namecard-app-sjc.zeabur.app/callback`
2. **配置 Notion 資料庫** (參考 DEPLOYMENT.md)
3. **開始測試您的 LINE Bot**

---

**總時間: 約 5 分鐘** ⏱️