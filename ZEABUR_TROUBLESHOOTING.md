# 🔧 Zeabur 部署問題診斷

## 🚨 問題：Zeabur 沒有被觸發或部署失敗

當前狀態：https://namecard-app.zeabur.app 回應 502 Bad Gateway

## 📋 診斷檢查清單

### 1. 確認 Zeabur 服務狀態

**前往 Zeabur Dashboard**：https://zeabur.com/dashboard

**檢查項目**：
- [ ] 服務是否顯示 "Running" 狀態？
- [ ] 是否有最近的 Deployment 記錄？
- [ ] Logs 標籤頁是否顯示錯誤訊息？
- [ ] GitHub Repository 是否正確連接？

### 2. 檢查 GitHub 整合

**在 Zeabur Dashboard 中**：
- [ ] 服務的 "Source" 是否指向 `chengzehsu/eco_namecard`？
- [ ] Branch 是否設定為 `main`？
- [ ] Auto Deploy 是否已啟用？
- [ ] 最近的 GitHub push 是否觸發了新的 deployment？

### 3. 檢查環境變數

**必要的環境變數是否都已設定**：
```bash
LINE_CHANNEL_ACCESS_TOKEN  ← 必要
LINE_CHANNEL_SECRET        ← 必要
GOOGLE_API_KEY            ← 必要
NOTION_API_KEY            ← 必要
NOTION_DATABASE_ID        ← 必要
SECRET_KEY                ← 必要
```

**檢查方法**：
- 在 Zeabur Dashboard → Service → Environment Variables
- 確認所有必要變數都有值（不是空的）

### 4. 檢查 Zeabur Logs

**查看部署日誌**：
1. Zeabur Dashboard → Your Service → **Logs** 標籤
2. 查找以下錯誤類型：

**常見錯誤訊息**：
```bash
# 環境變數缺失
KeyError: 'LINE_CHANNEL_ACCESS_TOKEN'
ValidationError: LINE_CHANNEL_ACCESS_TOKEN

# 依賴安裝失敗
ERROR: Could not install packages
pip install failed

# 應用啟動失敗
ModuleNotFoundError
ImportError
```

## 🔧 解決方案

### 方案 1: 重新創建 Zeabur 服務

如果服務根本沒有正確設置：

1. **刪除現有服務** (如果有)
2. **重新添加服務**：
   - Dashboard → Add Service
   - 選擇 **GitHub**
   - Repository: `chengzehsu/eco_namecard`
   - Branch: `main`
   - 點擊 **Deploy**

### 方案 2: 手動觸發部署

1. **在 Zeabur Dashboard**：
   - 找到您的服務
   - 點擊 **"Redeploy"** 或 **"Deploy"** 按鈕
   - 選擇最新的 commit

2. **或推送觸發**：
   ```bash
   git commit --allow-empty -m "trigger: manual Zeabur deployment"
   git push origin main
   ```

### 方案 3: 檢查部署配置

**確認 zeabur.json 被正確讀取**：

在 Zeabur Logs 中應該看到：
```
✅ Detected zeabur.json
✅ Installing dependencies: pip install -r requirements.txt
✅ Starting application: python app.py
```

### 方案 4: 環境變數設置

**如果是環境變數問題**：

1. **設置所有必要變數**
2. **點擊 "Redeploy"**
3. **等待 2-5 分鐘**
4. **檢查** `https://namecard-app.zeabur.app/health`

## ⚡ 快速診斷步驟

### 步驟 1: 檢查 Zeabur 狀態
```bash
# 如果返回 502，表示服務沒有運行
curl -I https://namecard-app.zeabur.app/health
```

### 步驟 2: 檢查服務面板
**前往**: https://zeabur.com/dashboard
- 查看服務狀態
- 檢查最近的部署
- 查看錯誤日誌

### 步驟 3: 驗證設置
- [ ] GitHub Repository 連接正確
- [ ] 環境變數完整設置
- [ ] 自動部署已啟用

## 🎯 最可能的問題

### 問題 1: 環境變數缺失
**症狀**: 應用啟動失敗，502 錯誤
**解決**: 設置所有必要的環境變數

### 問題 2: GitHub 整合沒有設置
**症狀**: Push 後沒有觸發部署
**解決**: 重新連接 GitHub Repository

### 問題 3: 服務沒有正確創建
**症狀**: Zeabur Dashboard 沒有顯示服務
**解決**: 重新創建服務

## 📞 下一步行動

**建議順序**：

1. **檢查 Zeabur Dashboard** - 確認服務狀態和日誌
2. **設置環境變數** - 確保所有必要變數存在
3. **手動觸發部署** - 點擊 Redeploy
4. **等待並驗證** - 檢查 `/health` 端點
5. **如果失敗** - 重新創建服務

## 🔍 需要檢查的信息

請提供以下信息以便進一步診斷：

1. **Zeabur Dashboard 截圖**：
   - 服務狀態
   - 部署歷史
   - 日誌內容

2. **環境變數狀態**：
   - 哪些變數已設置
   - 是否有錯誤提示

3. **GitHub 連接狀態**：
   - Repository 是否正確顯示
   - 自動部署是否啟用

讓我們一起解決這個問題！🚀