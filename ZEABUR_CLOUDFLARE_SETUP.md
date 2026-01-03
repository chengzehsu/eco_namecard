# Zeabur + Cloudflare 整合指南

## 🎯 **整合方式選擇**

由於你目前使用 `eco-namecard.zeabur.app`，有三種方式可以整合 Cloudflare：

### 方式 1: 自定義域名 (推薦) ⭐
- 使用自己的域名
- 完全由 Cloudflare 管理 DNS
- 最大彈性和控制權

### 方式 2: 免費域名服務
- 使用免費域名 (.tk, .cf, .freenom 等)
- 適合測試和個人專案

### 方式 3: 子域名 CNAME (如果你有其他域名)
- 使用現有域名的子域名
- 設定 CNAME 指向 Zeabur

---

## 🚀 **方式 1: 自定義域名設定 (推薦)**

### 步驟 1: 準備域名

#### 選項 A: 購買域名
```bash
# 推薦的便宜域名註冊商
- Namecheap: .com $10-15/年
- Cloudflare Registrar: 成本價 (最便宜)
- Google Domains: 方便管理
- GoDaddy: 常有促銷

# 範例域名
your-namecard.com
namecard-bot.net
ecofirst-cards.app
```

#### 選項 B: 免費域名
```bash
# 免費域名提供商
- Freenom: .tk, .ml, .ga, .cf (免費1年)
- No-IP: 免費子域名
- DuckDNS: 免費動態 DNS

# 範例免費域名
namecard-bot.tk
your-project.cf
```

### 步驟 2: 在 Zeabur 設定自定義域名

#### 2.1 進入 Zeabur Dashboard
```bash
1. 登入 https://zeabur.com
2. 選擇你的專案 "eco_namecard"
3. 點擊 "namecard-app" 服務
4. 進入 "Domain" 設定頁面
```

#### 2.2 添加自定義域名
```bash
1. 點擊 "Add Domain"
2. 輸入你的域名: your-domain.com
3. 選擇 "Custom Domain"
4. 點擊 "Add"
```

#### 2.3 獲取 Zeabur 目標資訊
```bash
# Zeabur 會提供以下資訊之一：

選項 A: IP 地址
IP: xxx.xxx.xxx.xxx

選項 B: CNAME 目標
CNAME: namecard-app-xxx.zeabur.app

選項 C: A/AAAA 記錄
A: xxx.xxx.xxx.xxx
AAAA: xxxx:xxxx:xxxx:xxxx::xxxx
```

### 步驟 3: 在 Cloudflare 設定域名

#### 3.1 添加站點到 Cloudflare
```bash
1. 登入 https://dash.cloudflare.com
2. 點擊 "Add a Site"
3. 輸入你的域名
4. 選擇 "Free" 計劃
5. 點擊 "Continue"
```

#### 3.2 設定 DNS 記錄
```bash
# 根據 Zeabur 提供的資訊設定：

如果 Zeabur 提供 IP 地址：
Type: A
Name: @
Content: [Zeabur IP]
Proxy: 🟠 Proxied ✅

如果 Zeabur 提供 CNAME：
Type: CNAME
Name: @
Content: namecard-app-xxx.zeabur.app
Proxy: 🟠 Proxied ✅

# 建議同時設定 www 子域名：
Type: CNAME
Name: www
Content: @
Proxy: 🟠 Proxied ✅
```

#### 3.3 更新 Nameserver
```bash
1. 複製 Cloudflare 提供的 nameserver
   例如: 
   - luna.ns.cloudflare.com
   - tim.ns.cloudflare.com

2. 到你的域名註冊商修改 nameserver
3. 等待 DNS 傳播 (通常 24 小時內)
```

---

## 🆓 **方式 2: 免費域名設定**

### 使用 Freenom 免費域名

#### 步驟 1: 申請免費域名
```bash
1. 前往 https://freenom.com
2. 搜尋可用的免費域名
3. 選擇 .tk, .ml, .ga, 或 .cf
4. 註冊帳號並申請域名 (免費 12 個月)
```

#### 步驟 2: 設定 DNS
```bash
1. 在 Freenom 控制面板中
2. 選擇 "Manage Domain"
3. 點擊 "Management Tools" > "Nameservers"
4. 選擇 "Use custom nameservers"
5. 輸入 Cloudflare nameserver:
   - luna.ns.cloudflare.com
   - tim.ns.cloudflare.com
```

#### 步驟 3: 在 Cloudflare 和 Zeabur 設定
```bash
# 按照方式 1 的步驟 2-3 繼續設定
```

---

## 🔧 **方式 3: 子域名 CNAME (如果你有現有域名)**

### 如果你已經有其他域名

#### 步驟 1: 在 Cloudflare 設定子域名
```bash
# 假設你有 example.com，想用 namecard.example.com

Type: CNAME
Name: namecard
Content: eco-namecard.zeabur.app
Proxy: 🟠 Proxied ✅
```

#### 步驟 2: 在 Zeabur 添加子域名
```bash
1. 在 Zeabur Domain 設定中
2. 添加 "namecard.example.com"
3. 選擇 "Custom Domain"
```

---

## ⚙️ **Zeabur 特殊設定**

### 環境變數更新
```bash
# 如果使用自定義域名，可能需要更新以下環境變數：

APP_HOST=0.0.0.0
APP_PORT=5002
DOMAIN=your-domain.com  # 新增這個變數

# 在 Zeabur Dashboard 中：
1. 進入服務設定
2. 點擊 "Environment Variables"
3. 添加或更新變數
4. 重新部署服務
```

### SSL 憑證處理
```bash
# Zeabur 自動處理 SSL，但需要確認：

1. 在 Zeabur Domain 設定中
2. 確認 SSL 狀態為 "Active"
3. 如果有問題，嘗試重新生成憑證
```

### 健康檢查更新
```bash
# 更新 Dockerfile 中的健康檢查 (如果需要)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5002/health || exit 1

# 或更新為新域名
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f https://your-domain.com/health || exit 1
```

---

## 🧪 **測試設定**

### 設定完成後測試

#### 1. DNS 傳播檢查
```bash
# 檢查 DNS 記錄
dig your-domain.com
nslookup your-domain.com

# 檢查 Cloudflare 是否生效
dig your-domain.com | grep -A1 "ANSWER SECTION"
```

#### 2. 服務可用性測試
```bash
# 測試所有端點
curl https://your-domain.com/health
curl https://your-domain.com/test
curl -X POST https://your-domain.com/callback
```

#### 3. Cloudflare 功能驗證
```bash
# 檢查 Cloudflare 標頭
curl -I https://your-domain.com/health | grep -i "cf-"

# 應該看到類似：
# cf-ray: xxxxx-TPE
# cf-cache-status: MISS/HIT
```

### 使用監控腳本
```bash
# 使用之前創建的監控腳本
python cloudflare-monitor.py your-domain.com --test all
```

---

## 🔄 **LINE Bot Webhook 更新**

### 更新 LINE Developers Console

#### 步驟 1: 進入 LINE Developers
```bash
1. 登入 https://developers.line.biz
2. 選擇你的 Provider
3. 選擇 Messaging API Channel
4. 進入 "Messaging API" 設定
```

#### 步驟 2: 更新 Webhook URL
```bash
# 原始 URL
https://eco-namecard.zeabur.app/callback

# 新的 URL
https://your-domain.com/callback

# 設定步驟：
1. 在 "Webhook URL" 欄位更新
2. 點擊 "Update"
3. 點擊 "Verify" 測試連線
4. 確認狀態為 "Success"
```

#### 步驟 3: 測試 LINE Bot
```bash
1. 在 LINE 中發送 "help" 給你的 Bot
2. 上傳一張測試圖片
3. 確認功能正常運作
```

---

## 📊 **完整設定檢查清單**

### Zeabur 端設定
- [ ] 添加自定義域名
- [ ] 確認 SSL 憑證狀態
- [ ] 更新環境變數 (如需要)
- [ ] 重新部署服務

### Cloudflare 端設定
- [ ] 添加站點
- [ ] 設定 DNS 記錄 (A 或 CNAME)
- [ ] 啟用 Proxy (橘色雲朵)
- [ ] 設定 SSL 模式為 "Full (strict)"
- [ ] 配置防火牆規則
- [ ] 設定 Page Rules

### 驗證測試
- [ ] DNS 解析正確
- [ ] HTTPS 連線成功
- [ ] 所有 API 端點正常
- [ ] Cloudflare 標頭存在
- [ ] LINE Bot 功能正常

### 後續優化
- [ ] 使用 `cloudflare-security-config.json` 配置
- [ ] 部署 `cloudflare-worker.js` (可選)
- [ ] 設定監控和通知
- [ ] 定期執行效能測試

---

## 💡 **實用建議**

### 域名選擇建議
```bash
# 如果是商業用途
推薦: .com, .net, .app
價格: $10-15/年

# 如果是個人測試
推薦: 免費域名 .tk, .cf
價格: 免費

# 如果已有域名
推薦: 使用子域名
例如: namecard.your-existing-domain.com
```

### 設定順序建議
```bash
1. 先申請/準備域名
2. 在 Cloudflare 添加站點
3. 在 Zeabur 設定自定義域名
4. 更新域名 nameserver
5. 等待 DNS 傳播
6. 配置 Cloudflare 設定
7. 更新 LINE Bot webhook
8. 執行完整測試
```

### 故障排除
```bash
# 常見問題：
1. DNS 傳播慢 → 等待 24 小時
2. SSL 錯誤 → 檢查 Cloudflare SSL 模式
3. 502 錯誤 → 檢查 Zeabur 服務狀態
4. LINE Bot 無回應 → 檢查 webhook URL 更新
```

這個整合讓你在**保持 Zeabur 簡單部署優勢**的同時，獲得 **Cloudflare 的安全和效能保護**！