# Redis 設定指南

## 概述

本系統已升級支援 Redis 持久化存儲，用於：
- 用戶會話管理（批次處理狀態、每日使用量）
- 速率限制（請求計數、用戶封鎖）

系統會自動偵測 Redis 是否可用，若無法連接則自動降級為記憶體存儲。

## 本地開發環境設定

### 1. 安裝 Redis

**macOS (使用 Homebrew):**
```bash
brew install redis
brew services start redis
```

**Ubuntu/Debian:**
```bash
sudo apt-get install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

**Docker:**
```bash
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

### 2. 設定環境變數

在 `.env` 檔案中新增（可選，有預設值）：

```bash
# Redis 設定
REDIS_ENABLED=true                    # 是否啟用 Redis（預設: true）
REDIS_HOST=localhost                   # Redis 主機（預設: localhost）
REDIS_PORT=6379                        # Redis 端口（預設: 6379）
REDIS_PASSWORD=                        # Redis 密碼（可選）
REDIS_DB=0                            # Redis 資料庫編號（預設: 0）

# 或使用 Redis URL（優先）
REDIS_URL=redis://localhost:6379/0
```

### 3. 測試連接

啟動應用程式並檢查日誌：

```bash
python app.py
```

應該會看到：
```
INFO  Services initialized with Redis backend  services=["UserService", "SecurityService"]
```

如果 Redis 無法連接，會看到：
```
WARNING  redis package not installed, falling back to in-memory storage
INFO  Services using in-memory backend (Redis not available)
```

## 生產環境部署 (Zeabur)

### 選項 1: 使用 Zeabur Redis 服務

1. 在 Zeabur 專案中新增 Redis 服務
2. Zeabur 會自動設定 `REDIS_URL` 環境變數
3. 應用程式會自動偵測並使用

### 選項 2: 使用外部 Redis 服務

推薦的 Redis 託管服務：
- **Upstash** (免費額度 10,000 命令/天): https://upstash.com/
- **Redis Cloud** (免費 30MB): https://redis.com/
- **AWS ElastiCache** (適合生產環境)

設定步驟：
1. 在服務提供商創建 Redis 實例
2. 獲取連接資訊（host, port, password）
3. 在 Zeabur 設定環境變數：
   ```
   REDIS_URL=redis://username:password@host:port/0
   ```

### 選項 3: 暫時停用 Redis

如果不需要持久化（僅測試），可設定：
```bash
REDIS_ENABLED=false
```

## Redis 資料結構

系統使用以下 Redis keys：

### 用戶會話
- **Key:** `namecard:user:{user_id}:status`
- **類型:** String (JSON)
- **TTL:** 24 小時
- **內容:** ProcessingStatus（批次模式、每日使用量等）

### 速率限制
- **Key:** `namecard:ratelimit:{user_id}`
- **類型:** Sorted Set
- **TTL:** window + 1 秒
- **內容:** 時間戳記錄（滑動窗口演算法）

### 用戶封鎖
- **Key:** `namecard:blocked:{user_id}`
- **類型:** String (ISO 時間戳)
- **TTL:** 封鎖時長
- **內容:** 解除封鎖時間

## 監控 Redis

### 檢查 Redis 狀態

```bash
redis-cli ping
# 應該返回: PONG
```

### 查看所有 namecard keys

```bash
redis-cli KEYS "namecard:*"
```

### 查看特定用戶的會話

```bash
redis-cli GET "namecard:user:U123456:status"
```

### 查看速率限制記錄

```bash
redis-cli ZRANGE "namecard:ratelimit:U123456" 0 -1 WITHSCORES
```

### 清除所有 namecard 資料

```bash
redis-cli --scan --pattern "namecard:*" | xargs redis-cli DEL
```

## 效能優化建議

### 連接池設定

系統預設使用連接池（max_connections=50）。可在 `.env` 調整：

```bash
REDIS_MAX_CONNECTIONS=100  # 高流量時增加
```

### 超時設定

預設 socket timeout 為 5 秒，可調整：

```bash
REDIS_SOCKET_TIMEOUT=10  # 網路不穩定時增加
```

## 疑難排解

### 問題: "redis package not installed"

**解決方法:**
```bash
pip install redis>=5.0.0
```

### 問題: "Connection refused"

**檢查:**
1. Redis 服務是否啟動: `redis-cli ping`
2. Host/Port 設定是否正確
3. 防火牆是否阻擋連接

**解決方法:**
```bash
# 檢查 Redis 狀態
sudo systemctl status redis-server  # Linux
brew services list                   # macOS

# 重啟 Redis
sudo systemctl restart redis-server  # Linux
brew services restart redis          # macOS
```

### 問題: 應用程式仍使用記憶體存儲

**檢查日誌:**
查找 "Redis connection" 相關訊息

**常見原因:**
1. `REDIS_ENABLED=false` 被設定
2. Redis 連接失敗（檢查上方日誌）
3. `redis` 套件未安裝

### 問題: 資料在重啟後消失

**原因:**
Redis 的 TTL 過期或者記憶體淘汰策略

**解決方法:**
```bash
# 檢查 Redis 記憶體政策
redis-cli CONFIG GET maxmemory-policy
# 建議設定: allkeys-lru

# 確認 TTL 設定
redis-cli TTL "namecard:user:U123456:status"
```

## 資料遷移

### 從記憶體存儲遷移到 Redis

無需特殊操作，系統會在 Redis 啟用後自動：
1. 新請求會儲存到 Redis
2. 舊的記憶體資料會逐漸過期

### 備份 Redis 資料

```bash
# 手動儲存快照
redis-cli BGSAVE

# 備份 RDB 檔案
cp /var/lib/redis/dump.rdb /backup/redis-backup-$(date +%Y%m%d).rdb
```

## 安全性建議

### 1. 啟用密碼驗證

```bash
# 在 redis.conf 設定
requirepass your_strong_password_here

# 然後更新環境變數
REDIS_PASSWORD=your_strong_password_here
```

### 2. 限制網路存取

```bash
# 在 redis.conf 設定
bind 127.0.0.1 ::1  # 僅本地存取
```

### 3. 停用危險命令

```bash
# 在 redis.conf 設定
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command CONFIG ""
```

## 相關檔案

- **配置:** `simple_config.py` - Redis 相關設定
- **客戶端:** `src/namecard/infrastructure/redis_client.py` - Redis 連接管理
- **用戶服務:** `src/namecard/core/services/user_service.py` - 使用 Redis 的會話管理
- **安全服務:** `src/namecard/core/services/security.py` - 使用 Redis 的速率限制
- **應用入口:** `app.py` - Redis 初始化邏輯

## 更新日誌

### 2024-10 - Redis 整合
- ✅ 新增 Redis 配置到 simple_config.py
- ✅ 重構 user_service.py 支援 Redis 持久化
- ✅ 重構 security.py 的速率限制使用 Redis
- ✅ 建立 redis_client.py 工具模組
- ✅ 更新 app.py 初始化 Redis
- ✅ 新增自動降級機制（Redis 失敗時使用記憶體）
