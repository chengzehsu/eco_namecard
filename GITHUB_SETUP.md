# 🐙 GitHub Repository 設置指南

## 👤 用戶資訊
- **GitHub 用戶名**: chengzehsu
- **Repository**: Ecofirst_namecard
- **完整 URL**: https://github.com/chengzehsu/Ecofirst_namecard

## 📋 設置步驟

### 1. 在 GitHub 上創建 Repository

1. 前往 [GitHub New Repository](https://github.com/new)
2. 填寫以下資訊：
   ```
   Repository name: Ecofirst_namecard
   Description: LINE Bot 名片管理系統 - AI 智能識別名片並自動存入 Notion
   Public ✅ (推薦) 或 Private (如果您希望私有)
   
   ⚠️ 不要勾選以下選項：
   ❌ Add a README file
   ❌ Add .gitignore  
   ❌ Choose a license
   ```
3. 點擊 **"Create repository"**

### 2. 連接本地 Repository 到 GitHub

在您的終端機中執行以下指令：

```bash
# 添加 GitHub remote origin
git remote add origin https://github.com/chengzehsu/Ecofirst_namecard.git

# 確認分支名稱為 main
git branch -M main

# 推送代碼到 GitHub
git push -u origin main
```

### 3. 驗證推送成功

推送完成後，前往：
https://github.com/chengzehsu/Ecofirst_namecard

您應該能看到所有文件，包括：
- README.md
- DEPLOYMENT.md  
- src/ 資料夾
- .github/workflows/ (CI/CD 配置)

### 4. 設置 GitHub Actions Secrets

前往 Repository → **Settings** → **Secrets and variables** → **Actions**

點擊 **"New repository secret"** 並添加：

#### 必要 Secrets：

**ZEABUR_SERVICE_ID**
```
名稱: ZEABUR_SERVICE_ID
值: <從 Zeabur Dashboard 取得>
```

**ZEABUR_API_TOKEN**  
```
名稱: ZEABUR_API_TOKEN
值: <從 Zeabur 帳號設定取得>
```

#### 🔍 如何獲取 Zeabur 資訊：

**獲取 Service ID**:
1. 前往 [Zeabur Dashboard](https://zeabur.com/dashboard)
2. 選擇您的 namecard-app 專案
3. 點擊服務 → **Settings**
4. 複製 **Service ID**

**獲取 API Token**:
1. Zeabur Dashboard 右上角頭像 → **Account Settings**
2. 左側選單 → **Developer**
3. 點擊 **"Create Token"**
4. 輸入 Token 名稱（如：`GitHub Actions`）
5. 複製生成的 Token

### 5. 觸發自動部署

設置完成後，每次推送到 `main` 分支都會自動：

1. **執行測試和品質檢查**
2. **部署到 Zeabur** (namecard-app.zeabur.app)
3. **驗證部署成功**

### 6. 檢查部署狀態

**GitHub Actions**:
- 前往：https://github.com/chengzehsu/Ecofirst_namecard/actions
- 查看最新的 workflow 執行狀態

**Zeabur 部署**:
- 前往：https://namecard-app.zeabur.app/health
- 預期回應：`{"status":"healthy",...}`

## 🚨 常見問題

### 推送被拒絕
```bash
# 如果推送失敗，嘗試：
git pull origin main --allow-unrelated-histories
git push -u origin main
```

### Remote 已存在錯誤
```bash
# 如果 remote 已存在，先移除再添加：
git remote remove origin
git remote add origin https://github.com/chengzehsu/Ecofirst_namecard.git
```

### GitHub Actions 失敗
1. 檢查 Secrets 是否正確設置
2. 確認 ZEABUR_SERVICE_ID 和 ZEABUR_API_TOKEN 有效
3. 查看 Actions 頁面的錯誤訊息

## ✅ 設置完成確認

設置成功的標誌：

- [ ] ✅ GitHub Repository 創建成功
- [ ] ✅ 代碼成功推送到 GitHub
- [ ] ✅ GitHub Actions Secrets 設置完成
- [ ] ✅ 第一次 workflow 執行成功
- [ ] ✅ https://namecard-app.zeabur.app/health 回應正常

## 🎉 完成後的下一步

1. **配置 LINE Bot Webhook**:
   ```
   URL: https://namecard-app.zeabur.app/callback
   ```

2. **設置 Notion 資料庫** (參考 DEPLOYMENT.md)

3. **開始測試 LINE Bot 功能**

---

## 📞 需要幫助？

如果遇到問題：
1. 檢查 GitHub Actions 執行日誌
2. 確認所有 Secrets 正確設置  
3. 參考 DEPLOYMENT.md 和 DEPLOY_CHECKLIST.md
4. 檢查 Zeabur Dashboard 狀態