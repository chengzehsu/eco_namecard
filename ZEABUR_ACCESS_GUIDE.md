# 🔐 Zeabur GitHub 存取權限設置

## 問題：為什麼 Zeabur 看不到我的 Repository？

**常見原因：**
1. Repository 是 **私有 (Private)** 的
2. Zeabur 沒有足夠的 GitHub 權限
3. 尚未授權 Zeabur 存取您的 GitHub 帳號

## 🔍 檢查 Repository 可見性

首先確認您的 Repository 狀態：

前往：https://github.com/chengzehsu/eco_namecard

查看 Repository 名稱旁邊是否顯示：
- 🔓 **Public** - 任何人都可以看到
- 🔒 **Private** - 只有您和授權的人可以看到

## 📋 解決方案

### 方案 1: 將 Repository 設為公開 (推薦)

由於這是開源專案，建議設為 Public：

1. 前往 https://github.com/chengzehsu/eco_namecard
2. 點擊 **Settings** 標籤
3. 滑到最下方 **"Danger Zone"**
4. 點擊 **"Change repository visibility"**
5. 選擇 **"Make public"**
6. 輸入 repository 名稱確認：`eco_namecard`
7. 點擊 **"I understand, change repository visibility"**

**設為 Public 的好處：**
- ✅ Zeabur 可以直接存取
- ✅ 其他開發者可以學習您的代碼
- ✅ 符合開源專案精神
- ✅ 不需要額外的權限設置

### 方案 2: 保持私有但授權 Zeabur

如果必須保持私有：

#### 步驟 1: 在 Zeabur 中授權 GitHub
1. 前往 https://zeabur.com/dashboard
2. 點擊右上角頭像 → **Account Settings**
3. 找到 **"Connected Accounts"** 或 **"Integrations"**
4. 點擊 **"Connect GitHub"** 或重新授權
5. **重要**: 在授權頁面選擇：
   - ✅ **"All repositories"** (建議)
   - 或 **"Selected repositories"** → 選擇 `eco_namecard`

#### 步驟 2: 確認權限範圍
確保 Zeabur 獲得以下權限：
- ✅ **Read access** to code
- ✅ **Read access** to metadata  
- ✅ **Read and write access** to deployments
- ✅ **Webhook** permissions

#### 步驟 3: 重新整理 Zeabur
1. 回到 Zeabur Dashboard
2. 嘗試創建新服務
3. 選擇 GitHub
4. 現在應該能看到 `eco_namecard`

## 🚀 快速測試

### 檢查授權狀態

1. **GitHub 端檢查**:
   - 前往 https://github.com/settings/applications
   - 點擊 **"Authorized OAuth Apps"**
   - 查看是否有 **"Zeabur"** 並檢查權限

2. **Zeabur 端檢查**:
   - 前往 https://zeabur.com/dashboard
   - 點擊 "Add Service" → "GitHub"
   - 查看是否能看到 `chengzehsu/eco_namecard`

### 測試部署

如果能看到 Repository：
1. 選擇 `eco_namecard`
2. 分支選擇 `main`
3. 點擊 "Deploy"
4. Zeabur 會自動偵測 `zeabur.json` 並開始部署

## ⚡ 建議的設置流程

**最簡單的方式：**

1. **設為 Public Repository** (推薦)
   ```bash
   # GitHub → Repository → Settings → Danger Zone → Make public
   ```

2. **在 Zeabur 創建服務**
   ```
   Dashboard → Add Service → GitHub → eco_namecard → Deploy
   ```

3. **設置環境變數**
   ```
   LINE_CHANNEL_ACCESS_TOKEN
   LINE_CHANNEL_SECRET
   GOOGLE_API_KEY
   NOTION_API_KEY
   NOTION_DATABASE_ID  
   SECRET_KEY
   ```

4. **等待部署完成**
   ```
   約 2-5 分鐘 → 檢查 https://eco-namecard.zeabur.app/health
   ```

## 🔒 安全考量

**設為 Public 是否安全？**

✅ **安全的內容**:
- 應用程式代碼 (沒有敏感資訊)
- 配置檔案 (.env.example，不含實際 keys)
- 文檔和說明

⚠️ **需要保護的內容**:
- API Keys (存在 Zeabur 環境變數中)
- 資料庫憑證 (存在 Zeabur 環境變數中)
- 實際的 .env 檔案 (已在 .gitignore 中)

**結論**: 將代碼設為 Public 是安全的，敏感資訊都在環境變數中！

## 🎯 推薦行動

1. **立即行動**: 將 Repository 設為 Public
2. **在 Zeabur 中創建服務**
3. **設置環境變數**
4. **測試部署**

這樣就能讓 Zeabur 正確存取您的專案並自動部署了！🚀