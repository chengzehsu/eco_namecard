# LINE Bot 名片管理系統 🎯

智能 LINE Bot 名片管理系統，使用 Google Gemini AI 識別名片內容，並自動存入 Notion 資料庫。

## 🚀 核心特色

- ✅ **LINE Bot 掃描名片** - 直接在 LINE 中上傳名片照片
- ✅ **Google Gemini AI 識別** - 高精度 OCR 文字識別
- ✅ **Notion 資料庫自動存儲** - 結構化儲存名片資料
- ✅ **批次處理** - 支援多名片同時處理
- ✅ **多名片檢測** - 一張圖片識別多張名片
- ✅ **地址正規化** - 台灣地址自動標準化
- ✅ **電話號碼正規化** - 國際 E.164 格式，支援台灣手機/市話
- ✅ **API 備用機制** - 雙重 API Key 容錯設計
- ✅ **安全性保護** - 完整的安全性和錯誤處理
- ✅ **圖片非同步上傳** - ImgBB + Notion 整合，支援同步 Fallback

## 🏗️ 系統架構

```
LINE用戶上傳名片圖片
    ↓
LINE Webhook 接收 (/callback)
    ↓
Gemini AI 智能識別
├── 多名片檢測
├── 品質評估
└── 地址正規化
    ↓
自動存入 Notion 資料庫
    ↓
回傳處理結果給用戶
```

## 📂 專案結構

```
namecard/
├── app.py                           # 主啟動入口
├── simple_config.py                 # 統一配置管理
├── requirements.txt                 # 依賴包列表
├── zeabur.json                      # Zeabur 部署配置
├── src/namecard/
│   ├── api/line_bot/
│   │   └── main.py                  # LINE Bot 核心邏輯
│   ├── infrastructure/
│   │   ├── ai/
│   │   │   └── card_processor.py    # Gemini AI 名片處理器
│   │   └── storage/
│   │       └── notion_client.py     # Notion 資料庫管理
│   └── core/
│       ├── models/
│       │   └── card.py              # 名片資料模型
│       └── services/
│           ├── user_service.py      # 用戶服務管理
│           └── security.py          # 安全性和錯誤處理
├── tests/                           # 測試文件
├── .github/workflows/
│   └── deploy.yml                   # GitHub Actions CI/CD
└── .env.example                     # 環境變數範例
```

## 🔧 環境配置

### 必要環境變數

```bash
# LINE Bot 配置
LINE_CHANNEL_ACCESS_TOKEN=your_line_token
LINE_CHANNEL_SECRET=your_line_secret

# AI 配置
GOOGLE_API_KEY=your_google_api_key
GOOGLE_API_KEY_FALLBACK=your_fallback_key  # 備用 API

# 資料庫配置
NOTION_API_KEY=your_notion_api_key
NOTION_DATABASE_ID=your_notion_database_id

# 應用配置
SECRET_KEY=your_secret_key
APP_PORT=5002
RATE_LIMIT_PER_USER=50
BATCH_SIZE_LIMIT=10

# RQ Worker 調試日誌（可選）
RQ_WORKER_DEBUG_LOG=true  # 默認啟用，設置為 false 可禁用
```

**注意：Redis 配置**
- 在 Zeabur 上：在專案中新增 Redis 服務，Zeabur 會自動設定 `REDIS_URL` 環境變數
- 本地開發：參考 [REDIS_SETUP.md](REDIS_SETUP.md) 進行配置

### GitHub Actions Secrets

在 Repository Settings → Secrets 中設置：

- `ZEABUR_SERVICE_ID` - Zeabur 服務 ID
- `ZEABUR_API_TOKEN` - Zeabur API Token
- `DEPLOYMENT_URL` - 部署後的應用 URL
- 所有上述環境變數

## 🚀 快速開始

### 1. 本地開發

```bash
# 克隆專案
git clone <repository-url>
cd Ecofirst_namecard

# 安裝依賴
pip install -r requirements.txt

# 設置環境變數
cp .env.example .env
# 編輯 .env 填入你的 API keys

# 啟動應用
python app.py
```

### 2. 部署到 Zeabur

```bash
# 推送代碼觸發自動部署
git add .
git commit -m "feat: 初始化 LINE Bot 名片系統"
git push origin main

# 在 Zeabur Dashboard 設置環境變數
# 設置 LINE Webhook URL: https://eco-namecard.zeabur.app/callback
```

**📋 詳細部署步驟請參考：[DEPLOYMENT.md](DEPLOYMENT.md)**

## 🎯 LINE Bot 功能

### 指令列表

| 指令 | 功能 | 範例 |
|------|------|------|
| `help` | 顯示使用說明 | help |
| `批次` | 啟動批次模式 | 批次 |
| `結束批次` | 結束批次並顯示統計 | 結束批次 |
| `狀態` | 查看批次進度 | 狀態 |
| 圖片上傳 | 智能名片識別 | [發送名片圖片] |

### 使用流程

1. **添加 LINE Bot** - 掃描 QR Code 或搜尋 Bot 名稱
2. **發送 help** - 查看使用說明
3. **上傳名片** - 直接發送名片照片
4. **批次處理** - 發送「批次」→ 連續上傳多張 → 發送「結束批次」
5. **查看結果** - 系統自動回傳 Notion 連結

### 智能功能

- **多名片檢測** - 自動識別單張圖片中的多張名片
- **品質評估** - AI 評估識別信心度，建議重拍模糊圖片
- **地址正規化** - 台灣地址自動標準化（台北 → 台北市）
- **電話號碼正規化** - 自動轉換為國際 E.164 格式（0912-345-678 → +886912345678）
- **API 容錯** - 主要 API 額度不足時自動切換備用 Key
- **安全防護** - 完整的 rate limiting 和輸入驗證

## 🧪 測試

```bash
# 運行所有測試
pytest

# 運行特定測試
pytest tests/test_health.py

# 生成覆蓋率報告
pytest --cov=src --cov-report=html

# 運行安全性檢查
bandit -r src/
safety check
```

## 📊 監控和日誌

### 健康檢查端點

- `GET /health` - 基本健康檢查
- `GET /test` - 服務配置檢查
- `GET /admin/worker/status` - Worker 狀態監控
- `GET /admin/worker/failed-tasks` - 查看失敗的圖片上傳任務
- `POST /admin/worker/retry-all` - 重試所有失敗任務

### 日誌系統

使用 `structlog` 提供結構化日誌：

```python
import structlog
logger = structlog.get_logger()

logger.info("Card processed", 
           user_id=user_id, 
           cards_count=len(cards))
```

### 錯誤監控

支援 Sentry 錯誤監控（可選）：

```bash
export SENTRY_DSN=your_sentry_dsn
```

## 🔒 安全性功能

### 已實現

- ✅ LINE Webhook 簽名驗證
- ✅ Rate Limiting (每用戶每日 50 張)
- ✅ 輸入資料清理和驗證
- ✅ 圖片大小和格式驗證
- ✅ 敏感資料加密
- ✅ 安全事件記錄

### 配置

```python
# 速率限制
RATE_LIMIT_PER_USER=50  # 每日每用戶

# 圖片限制
MAX_IMAGE_SIZE=10485760  # 10MB

# 批次限制
BATCH_SIZE_LIMIT=10  # 每批次最多 10 張
```

## 🛠️ 開發工具

### 代碼品質

```bash
# 代碼格式化
black src/

# 程式碼檢查
flake8 src/

# 類型檢查
mypy src/
```

### Git Hooks（建議）

```bash
# 安裝 pre-commit
pip install pre-commit

# 設置 hooks
pre-commit install
```

## 📈 效能指標

- **識別準確率**: ~90% (Gemini AI)
- **處理速度**: 5-10 秒/張
- **支援格式**: JPG, PNG, WebP
- **多名片**: 最多檢測 5 張/圖
- **並發處理**: 支援多用戶同時使用

## 🐛 故障排除

### 常見問題

1. **502 錯誤**
   - 檢查 Zeabur 環境變數設置
   - 確認所有必要的 API Keys 已配置

2. **Webhook 失效**
   - 確認 LINE Developer Console 中的 URL 正確
   - 檢查 LINE_CHANNEL_SECRET 是否正確

3. **識別失敗**
   - 確保名片圖片清晰，光線充足
   - 檢查 GOOGLE_API_KEY 是否有效

4. **Notion 錯誤**
   - 檢查 NOTION_API_KEY 和 DATABASE_ID
   - 確認 Notion 整合權限正確

5. **RQ Worker 啟動失敗**
   - 確認 Redis 服務已在 Zeabur 中配置
   - 檢查 `REDIS_URL` 環境變數是否自動設定
   - 查看 Zeabur Logs 中的 worker 啟動日誌
   - 如果出現 "duplicate worker" 錯誤，系統會自動清理並重試

### 日誌查看

```bash
# 本地開發
tail -f logs/app.log

# Zeabur 部署
# 在 Zeabur Dashboard 查看 Logs 標籤
```

## 🔄 CI/CD 流程

### GitHub Actions 自動化

1. **代碼品質檢查** - Black, Flake8, MyPy
2. **安全性掃描** - Bandit, Safety
3. **測試運行** - Pytest + 覆蓋率
4. **自動部署** - 推送到 main 分支自動部署
5. **部署驗證** - 健康檢查和基本 API 測試

### 手動部署

```bash
# 確保測試通過
pytest

# 推送到 main 分支
git push origin main

# 檢查 GitHub Actions 狀態
# 驗證 Zeabur 部署成功
```

## 📞 技術支援

- **GitHub Issues**: 回報問題和建議
- **版本管理**: 使用語義化版本號
- **文檔更新**: 隨功能更新同步維護

## 📄 授權

MIT License - 詳見 LICENSE 文件

---

> **🎉 快速上手**: 複製 `.env.example` 為 `.env`，填入你的 API Keys，執行 `python app.py` 即可開始！