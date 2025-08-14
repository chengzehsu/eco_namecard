# Claude Code 協作記錄

## 專案概述
這是一個 LINE Bot 名片管理系統，使用 Google Gemini AI 識別名片內容並自動存入 Notion 資料庫。

## 關鍵指令

### 開發指令
```bash
# 啟動本地開發
python app.py

# 運行測試
pytest

# 代碼品質檢查
black src/
flake8 src/
mypy src/

# 安全性檢查
bandit -r src/
safety check
```

### 部署指令
```bash
# 推送到 GitHub 觸發 CI/CD
git add .
git commit -m "feat: 功能描述"
git push origin main

# 本地 Docker 測試
docker build -t linebot-namecard .
docker run -p 5002:5002 --env-file .env linebot-namecard
```

## 架構設計

### 核心組件
1. **LINE Bot API** (`src/namecard/api/line_bot/main.py`)
   - 處理 webhook 回調
   - 用戶指令解析
   - 圖片消息處理

2. **AI 處理器** (`src/namecard/infrastructure/ai/card_processor.py`)
   - Google Gemini AI 整合
   - 多名片檢測
   - 品質評估

3. **Notion 客戶端** (`src/namecard/infrastructure/storage/notion_client.py`)
   - 資料庫操作
   - 名片資料存儲
   - 搜尋功能

4. **用戶服務** (`src/namecard/core/services/user_service.py`)
   - 批次模式管理
   - 速率限制
   - 使用統計

5. **安全服務** (`src/namecard/core/services/security.py`)
   - 簽名驗證
   - 輸入清理
   - 錯誤處理

### 資料模型
- `BusinessCard`: 名片資料結構
- `BatchProcessResult`: 批次處理結果
- `ProcessingStatus`: 用戶處理狀態

## 環境配置

### 必要環境變數
```bash
LINE_CHANNEL_ACCESS_TOKEN=
LINE_CHANNEL_SECRET=
GOOGLE_API_KEY=
GOOGLE_API_KEY_FALLBACK=
NOTION_API_KEY=
NOTION_DATABASE_ID=
SECRET_KEY=
```

### 可選配置
```bash
APP_PORT=5002
RATE_LIMIT_PER_USER=50
BATCH_SIZE_LIMIT=10
MAX_IMAGE_SIZE=10485760
SENTRY_DSN=
DEBUG=False
```

## 測試策略

### 測試結構
- `tests/test_health.py` - API 端點測試
- `tests/test_card_models.py` - 資料模型測試
- `tests/test_user_service.py` - 用戶服務測試

### 覆蓋率目標
- 最低覆蓋率: 70%
- 核心功能: 90%+

## 部署流程

### GitHub Actions CI/CD
1. **測試階段**
   - 代碼品質檢查
   - 單元測試
   - 安全性掃描

2. **部署階段**
   - 自動部署到 Zeabur
   - 健康檢查
   - 效能測試

### Zeabur 配置
- 部署地址: https://namecard-app.zeabur.app
- Webhook URL: https://namecard-app.zeabur.app/callback
- 健康檢查: https://namecard-app.zeabur.app/health
- 自動部署: 啟用
- 零停機部署: 啟用

## 監控和日誌

### 日誌系統
- 使用 `structlog` 結構化日誌
- 支援 JSON 格式輸出
- 分級日誌記錄

### 錯誤監控
- Sentry 整合 (可選)
- 自定義錯誤處理
- 安全事件記錄

## 安全性措施

### 已實現
- LINE Webhook 簽名驗證
- Rate Limiting
- 輸入資料驗證
- 圖片格式檢查
- 敏感資料加密

### 最佳實踐
- 環境變數管理
- 最小權限原則
- 錯誤訊息清理
- 安全事件記錄

## 效能優化

### 當前指標
- 處理時間: 5-10秒/張
- 並發支援: 多用戶
- 記憶體使用: 適中

### 優化空間
- AI 結果快取
- 圖片預處理優化
- 批次處理優化

## 故障排除

### 常見問題
1. **502 錯誤** - 檢查環境變數
2. **AI 識別失敗** - 檢查 API Key 和網路
3. **Notion 錯誤** - 確認權限和 Database ID
4. **Webhook 失效** - 驗證 LINE 設定

### 日誌查看
```bash
# 本地開發
tail -f app.log

# Zeabur 部署
# 在 Dashboard 查看 Logs
```

## 未來規劃

### 短期 (1-2 個月)
- 重複名片檢測
- 多語言支援
- Rich Menu 設計

### 中期 (3-6 個月)
- CRM 系統整合
- 進階搜尋功能
- 資料分析儀表板

### 長期 (6+ 個月)
- 機器學習優化
- 企業版功能
- API 對外開放

## 開發注意事項

### 代碼風格
- 使用 Black 格式化
- 遵循 PEP 8
- 類型提示 (Type Hints)

### 提交訊息格式
```
feat: 新功能
fix: 錯誤修復
docs: 文檔更新
test: 測試相關
refactor: 代碼重構
```

### 分支策略
- `main`: 生產分支
- `develop`: 開發分支
- `feature/*`: 功能分支
- `hotfix/*`: 緊急修復