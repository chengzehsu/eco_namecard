# Cloudflare 測試與監控計劃

## 📋 測試階段規劃

### 階段 1: 基礎設定驗證 (第1天)

#### 1.1 DNS 設定測試
```bash
# 檢查 DNS 記錄
dig your-domain.com
dig namecard.your-domain.com

# 驗證 Nameserver 變更
dig NS your-domain.com

# 檢查 SSL 憑證
curl -I https://your-domain.com/health
```

#### 1.2 基本連通性測試
```bash
# 使用 curl 測試所有端點
curl -v https://your-domain.com/health
curl -v https://your-domain.com/test
curl -v -X POST https://your-domain.com/callback
```

#### 1.3 Cloudflare 標頭檢查
```bash
# 確認請求經過 Cloudflare
curl -I https://your-domain.com/health | grep -i "cf-"
```

**預期結果:**
- ✅ DNS 記錄正確解析
- ✅ SSL 憑證有效
- ✅ Cloudflare 標頭存在 (cf-ray, cf-cache-status)

---

### 階段 2: 安全設定驗證 (第2天)

#### 2.1 防火牆規則測試
```bash
# 測試無簽章的 webhook 請求 (應該被阻擋)
curl -X POST https://your-domain.com/callback \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'

# 測試不支援的 HTTP 方法 (應該被阻擋)
curl -X DELETE https://your-domain.com/health

# 測試過大的請求 (應該被阻擋)
curl -X POST https://your-domain.com/callback \
  -H "Content-Type: application/json" \
  -d "$(python -c 'print("x" * 2000000)')"
```

#### 2.2 Rate Limiting 測試
```bash
# 快速連續請求測試
for i in {1..50}; do
  curl -s -o /dev/null -w "%{http_code}\n" https://your-domain.com/health
  sleep 0.1
done
```

#### 2.3 安全標頭檢查
```bash
# 檢查安全標頭
curl -I https://your-domain.com/health | grep -E "(x-content-type-options|x-frame-options|strict-transport-security)"
```

**預期結果:**
- ✅ 無簽章 webhook 請求被阻擋 (400/403)
- ✅ 不支援的方法被阻擋 (405)
- ✅ Rate limiting 正常運作 (429)
- ✅ 安全標頭正確設定

---

### 階段 3: 效能優化驗證 (第3天)

#### 3.1 快取測試
```bash
# 測試健康檢查端點快取
curl -I https://your-domain.com/health
# 再次請求，檢查 cf-cache-status
curl -I https://your-domain.com/health
```

#### 3.2 壓縮測試
```bash
# 檢查 Gzip/Brotli 壓縮
curl -H "Accept-Encoding: gzip, br" -I https://your-domain.com/test
```

#### 3.3 回應時間測試
```bash
# 測量回應時間
curl -w "Total time: %{time_total}s\n" -o /dev/null -s https://your-domain.com/health
```

**預期結果:**
- ✅ 靜態端點正確快取 (HIT)
- ✅ 回應被壓縮
- ✅ 回應時間 < 500ms

---

### 階段 4: LINE Bot 整合測試 (第4天)

#### 4.1 更新 LINE Bot Webhook URL
```bash
# 在 LINE Developers Console 中更新 Webhook URL
# 舊: https://eco-namecard.zeabur.app/callback
# 新: https://your-domain.com/callback
```

#### 4.2 LINE Bot 功能測試
- 傳送「help」指令
- 上傳測試圖片
- 測試批次模式
- 檢查 Notion 資料儲存

#### 4.3 監控設定
```bash
# 設定 Cloudflare Analytics
# 設定通知規則
# 檢查日誌記錄
```

**預期結果:**
- ✅ LINE Bot 正常回應
- ✅ 圖片上傳和處理成功
- ✅ Notion 資料正確儲存

---

## 🔧 自動化測試腳本

### 使用 cloudflare-monitor.py
```bash
# 安裝依賴
pip install requests

# 執行完整測試
python cloudflare-monitor.py your-domain.com --test all --output test-report.md

# 只測試效能
python cloudflare-monitor.py your-domain.com --test performance --json

# 定期監控 (每小時)
*/60 * * * * /usr/bin/python /path/to/cloudflare-monitor.py your-domain.com --test all --output /var/log/cloudflare-test.log
```

### 健康檢查腳本
```bash
#!/bin/bash
# health-check.sh

DOMAIN="your-domain.com"
WEBHOOK_URL="https://hooks.slack.com/your-webhook"  # 可選

check_endpoint() {
    local endpoint=$1
    local expected_status=$2
    
    status=$(curl -s -o /dev/null -w "%{http_code}" https://$DOMAIN$endpoint)
    
    if [ "$status" = "$expected_status" ]; then
        echo "✅ $endpoint: $status (OK)"
        return 0
    else
        echo "❌ $endpoint: $status (Expected: $expected_status)"
        return 1
    fi
}

echo "🔍 Cloudflare 健康檢查 - $(date)"
echo "================================"

# 檢查主要端點
check_endpoint "/health" "200"
check_endpoint "/test" "200"
check_endpoint "/debug/notion" "200"

# 檢查安全性
check_endpoint "/callback" "400"  # 無簽章應該被拒絕

echo "================================"
```

---

## 📊 監控設定

### 1. Cloudflare Analytics
```javascript
// 在 Cloudflare Dashboard 啟用
{
  "web_analytics": true,
  "security_analytics": true,
  "performance_analytics": true,
  "custom_metrics": [
    "api_response_time",
    "error_rate",
    "cache_hit_ratio"
  ]
}
```

### 2. 通知設定
```json
{
  "notifications": [
    {
      "name": "Health Check Failure",
      "condition": "health_check.status != 'healthy'",
      "channels": ["email", "webhook"],
      "frequency": "immediate"
    },
    {
      "name": "High Error Rate",
      "condition": "error_rate > 5%",
      "channels": ["email"],
      "frequency": "once_per_hour"
    },
    {
      "name": "DDoS Detection",
      "condition": "security.ddos_detected",
      "channels": ["email", "sms"],
      "frequency": "immediate"
    }
  ]
}
```

### 3. 自定義監控腳本
```python
# monitor-dashboard.py
import requests
import json
from datetime import datetime

def create_dashboard_data():
    """創建監控儀表板資料"""
    
    endpoints = ['/health', '/test', '/callback']
    results = {}
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"https://your-domain.com{endpoint}", timeout=5)
            results[endpoint] = {
                'status': response.status_code,
                'response_time': response.elapsed.total_seconds(),
                'cf_cache': response.headers.get('cf-cache-status', 'unknown'),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            results[endpoint] = {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    return results

# 每 5 分鐘執行一次
if __name__ == "__main__":
    data = create_dashboard_data()
    with open('/var/log/cloudflare-monitor.json', 'w') as f:
        json.dump(data, f, indent=2)
```

---

## 🚨 故障排除計劃

### 常見問題檢查清單

#### 1. DNS 問題
```bash
# 檢查項目
□ Nameserver 是否正確設定
□ DNS 記錄是否正確
□ TTL 是否合理
□ 代理狀態是否正確 (橘色雲朵)

# 診斷指令
dig your-domain.com
nslookup your-domain.com
```

#### 2. SSL 問題
```bash
# 檢查項目
□ SSL 模式是否設為 "Full (strict)"
□ 憑證是否有效
□ TLS 版本是否正確

# 診斷指令
curl -I https://your-domain.com
openssl s_client -connect your-domain.com:443
```

#### 3. 快取問題
```bash
# 檢查項目
□ Page Rules 是否正確設定
□ Cache-Control 標頭是否正確
□ 快取清除是否需要

# 診斷指令
curl -I https://your-domain.com/health | grep -i cache
```

#### 4. 安全問題
```bash
# 檢查項目
□ 防火牆規則是否過於嚴格
□ Rate limiting 是否誤攔截
□ 地理限制是否影響

# 診斷指令
curl -v -X POST https://your-domain.com/callback
```

---

## 📈 效能基準

### 期望指標
- **可用性**: 99.9%+
- **回應時間**: < 500ms (健康檢查)
- **錯誤率**: < 1%
- **快取命中率**: > 80% (靜態端點)
- **安全攔截**: 99%+ (惡意請求)

### 效能監控
```bash
# 每日效能報告
0 8 * * * python /path/to/cloudflare-monitor.py your-domain.com --test performance --output /var/log/daily-performance-$(date +\%Y\%m\%d).log

# 每週安全報告
0 9 * * 1 python /path/to/cloudflare-monitor.py your-domain.com --test security --output /var/log/weekly-security-$(date +\%Y\%m\%d).log
```

---

## 📝 測試檢查清單

### 設定前檢查
- [ ] 備份原始 DNS 設定
- [ ] 記錄 Zeabur 原始 IP
- [ ] 測試原始服務正常運作
- [ ] 準備回退計劃

### 設定後檢查
- [ ] DNS 記錄正確解析
- [ ] SSL 憑證有效
- [ ] 所有端點正常回應
- [ ] Cloudflare 標頭存在
- [ ] 安全規則生效
- [ ] 快取正常運作
- [ ] LINE Bot 功能正常

### 日常監控
- [ ] 每日健康檢查
- [ ] 每週效能測試
- [ ] 每月安全掃描
- [ ] 季度配置檢視

### 緊急應變
- [ ] 回退到原始設定的程序
- [ ] 聯絡資訊和升級路徑
- [ ] 備用監控方案
- [ ] 事故記錄模板

---

## 🎯 成功指標

### 短期目標 (1週)
- ✅ 所有端點通過 Cloudflare 正常存取
- ✅ 安全規則正確攔截惡意請求
- ✅ 快取規則提升回應速度
- ✅ LINE Bot 功能完全正常

### 中期目標 (1個月)
- ✅ 平均回應時間改善 30%+
- ✅ 安全事件減少 90%+
- ✅ 可用性達到 99.9%+
- ✅ 頻寬使用優化 20%+

### 長期目標 (3個月)
- ✅ 零安全事故
- ✅ 成本節省評估
- ✅ 效能持續優化
- ✅ 監控流程完善

這個測試計劃確保 Cloudflare 免費版能為你的 LINE Bot 提供最大的安全和效能價值。