# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LINE Bot namecard management system that uses Google Gemini AI to recognize business card content and automatically saves to Notion database. The system supports batch processing, multi-card detection, and includes comprehensive security and error handling.

**Multi-Tenant Support**: 系統支援多租戶模式，允許管理多個獨立的 LINE Bot 和 Notion Database。每個朋友可以有自己專屬的 Bot，所有請求由單一應用程式處理。

## Essential Commands

### Development

```bash
# Start local development server
python app.py

# Run all tests with coverage
pytest

# Run specific test file
pytest tests/test_health.py -v

# Run tests with specific marker
pytest -m unit

# Code quality checks
black src/
flake8 src/
mypy src/

# Security scanning
bandit -r src/
safety check

# Quick setup for new environment
./setup.sh
```

### Deployment

```bash
# Deploy to GitHub (triggers CI/CD)
git push origin main

# One-click deployment script
./deploy_to_github.sh

# Local Docker testing
docker build -t linebot-namecard .
docker run -p 5002:5002 --env-file .env linebot-namecard
```

## Architecture Overview

### Core Processing Flow

1. **LINE Webhook** (`/callback`) receives image messages
2. **CardProcessor** uses Google Gemini AI for OCR and multi-card detection
3. **NotionClient** stores structured data with validation
4. **UserService** manages batch processing and rate limiting
5. **SecurityService** handles authentication and input sanitization

### Key Components

**LINE Bot Handler** (`src/namecard/api/line_bot/main.py`)

- Webhook event processing with signature validation
- Command parsing (help, 批次, 狀態, 結束批次)
- Image message handling with size/format validation
- Batch mode state management

**AI Processing** (`src/namecard/infrastructure/ai/card_processor.py`)

- Google Gemini integration with fallback API key support
- Multi-card detection in single images
- Quality assessment and confidence scoring
- Taiwan address normalization

**Data Storage** (`src/namecard/infrastructure/storage/notion_client.py`)

- Notion database integration with property mapping
- Search functionality by name/company
- User-specific card retrieval

**Core Models** (`src/namecard/core/models/card.py`)

- `BusinessCard`: Pydantic model with validation (email, phone, address normalization)
- `BatchProcessResult`: Session tracking with success rates
- `ProcessingStatus`: User state with daily usage limits

### Configuration System

Centralized in `simple_config.py` using Pydantic BaseSettings:

- Environment variable mapping with defaults
- Type validation and conversion
- Support for .env files

## Testing Structure

```bash
tests/
├── conftest.py                      # Shared fixtures and mocks
├── test_health.py                   # API endpoint health checks
├── test_app.py                      # Flask application tests
├── test_card_models.py              # Pydantic model validation
├── test_card_processor.py           # AI card processing tests
├── test_card_processor_comprehensive.py
├── test_card_processor_integration.py
├── test_line_bot_main.py            # LINE Bot handler tests
├── test_notion_client.py            # Notion integration tests
├── test_notion_client_extended.py
├── test_security_service.py         # Security service tests
├── test_security_service_extended.py
├── test_simple_config.py            # Configuration tests
└── test_user_service.py             # Batch processing and rate limiting
```

Target coverage: 70% minimum, 90%+ for core business logic.

## Deployment Configuration

**GitHub Actions** (`.github/workflows/deploy.yml`)

- Multi-stage pipeline: test → security-scan → deploy → performance-test
- Zeabur integration with service ID and API token
- Automatic health checks post-deployment

**Zeabur** (`zeabur.json`)

- Production deployment to eco-namecard.zeabur.app
- Environment variables for external services
- Health check endpoint: `/health`

## Security Implementation

**Rate Limiting**: 50 cards/day per user with cleanup of inactive sessions
**Input Validation**: Image size (10MB), format checking, text sanitization
**Webhook Security**: LINE signature verification with HMAC-SHA256
**Data Encryption**: Sensitive data encryption using Fernet (symmetric)
**Error Handling**: Comprehensive error classification with user-friendly messages

## External Service Integration

**LINE Bot**

- Webhook URL: https://eco-namecard.zeabur.app/callback
- Rich messaging with Quick Reply buttons
- Batch mode with progress tracking

**Google Gemini AI**

- Primary + fallback API key configuration
- **Automatic quota fallback**: 當主要 API key quota exceeded 時自動切換到 fallback key（透明且無縫）
- Structured JSON response parsing
- Image preprocessing and size optimization

**Notion Database**

- Required properties: 姓名(Title), 公司, 職稱, 電話, Email, etc.
- Integration permissions and database sharing
- User-based data segregation

## Development Workflow

1. Changes to `main` branch trigger automatic deployment
2. GitHub Actions runs quality checks, tests, and security scans
3. Successful builds deploy to Zeabur automatically
4. Health checks validate deployment success

## Critical Environment Variables

**Required**:

- `LINE_CHANNEL_ACCESS_TOKEN`, `LINE_CHANNEL_SECRET`
- `GOOGLE_API_KEY` (with optional `GOOGLE_API_KEY_FALLBACK`) - 用於名片識別
- `NOTION_API_KEY`, `NOTION_DATABASE_ID`
- `SECRET_KEY`

**Operational**:

- `RATE_LIMIT_PER_USER=50`, `BATCH_SIZE_LIMIT=10`
- `MAX_IMAGE_SIZE=10485760` (10MB)
- `VERBOSE_ERRORS=false` (開發模式設為 true 可顯示完整技術錯誤訊息)

## Error Handling

The system provides 14 detailed error types with user-friendly messages designed for IT debugging.

**AI Recognition Errors**: API key invalid, quota exceeded (auto-fallback), safety filter blocked, low quality, incomplete info, low resolution, JSON parse error, AI analysis failed, timeout

**Notion Storage Errors**: Permission denied, database not found, schema mismatch, rate limiting, network issues

**Debug Mode**: Set `VERBOSE_ERRORS=true` to show full technical details including exception types and stack traces.

**Quota Fallback**: When primary API key quota is exceeded, automatically switches to `GOOGLE_API_KEY_FALLBACK` transparently. Resets daily at 00:00 UTC.

## Troubleshooting Common Issues

**502 Errors**: Check Zeabur environment variables and service status
**AI Recognition Failures**: Verify Google API quotas and network connectivity
**Notion Storage Errors**: Confirm integration permissions and database schema
**Webhook Issues**: Validate LINE channel secret and URL accessibility
**Sentry Configuration Issues**:

- Run `python debug-sentry.py` to diagnose environment variable and SDK configuration
- Check `/debug/sentry` endpoint for real-time configuration status
- Verify SENTRY_DSN environment variable is correctly set in Zeabur
- Use `python force-sentry-test.py` to trigger test errors and verify Dashboard integration
- Note: "Sentry monitoring enabled" log message may not appear but integration can still be functional
- Confirm errors appear in Sentry Dashboard at https://sentry.io after 3-5 minutes

## Development Hard Rules

這些規則是經過慘痛教訓後總結的，必須嚴格遵守：

### 1. 套件版本約束必須使用上限

**禁止**: `package>=1.0.0`
**正確**: `package>=1.0.0,<2.0.0`

原因：主版本升級（如 1.x → 2.x）通常包含 breaking changes。使用開放式版本約束會導致部署環境安裝最新版本，而本地/CI 使用舊版本，造成「本地正常，部署爆炸」的問題。

### 2. 可選依賴的 import 必須捕獲所有異常

**禁止**:

```python
try:
    from package import Something
except ImportError:
    AVAILABLE = False
```

**正確**:

```python
try:
    from package import Something
    AVAILABLE = True
except Exception as e:
    AVAILABLE = False
    logger.warning(f"Package import failed: {e}")
```

原因：版本不相容可能拋出 `AttributeError`、`TypeError` 等非 `ImportError` 異常，只捕獲 `ImportError` 會導致模組載入中斷。

## System Maintenance

**Debug Endpoints**:

- Health check: https://eco-namecard.zeabur.app/health
- Notion fields: https://eco-namecard.zeabur.app/debug/notion
- Config check: https://eco-namecard.zeabur.app/test
- CI/CD: https://github.com/chengzehsu/eco_namecard/actions

**Emergency Recovery**:

- Service down: Check `/health` endpoint first
- Notion save fails: Check `/debug/notion`
- Rollback: `git reset --hard HEAD~1`

Repository: https://github.com/chengzehsu/eco_namecard
Deployment: https://eco-namecard.zeabur.app

## Multi-Tenant Management System

### Overview

系統支援多租戶模式，讓你可以幫多個朋友設定獨立的 LINE Bot 和 Notion Database，所有請求由單一應用程式處理。

### Admin Panel

**管理後台 URL**: https://eco-namecard.zeabur.app/admin

**功能**:

- 新增/編輯/停用租戶
- 設定每個租戶的 LINE Bot 憑證
- 設定每個租戶的 Notion Database
- 測試連線功能
- 查看使用統計

**預設管理員**:

- 首次啟動時會自動建立管理員帳號
- 帳號: 由 `INITIAL_ADMIN_USERNAME` 環境變數設定 (預設 `admin`)
- 密碼: 由 `INITIAL_ADMIN_PASSWORD` 環境變數設定 (如未設定會自動產生並記錄在 logs)

**重設密碼**:

- 如果忘記密碼或需要更新，設定 `RESET_ADMIN_PASSWORD=true` 並重新部署
- 系統會用 `INITIAL_ADMIN_PASSWORD` 的值更新密碼
- 重設成功後記得將 `RESET_ADMIN_PASSWORD` 改回 `false`

### Multi-Tenant Architecture

**核心元件**:

- `src/namecard/core/models/tenant.py` - TenantConfig, TenantContext 模型
- `src/namecard/core/services/tenant_service.py` - 租戶服務 (CRUD + 快取)
- `src/namecard/infrastructure/storage/tenant_db.py` - SQLite 資料庫操作
- `src/namecard/api/admin/` - 管理後台 Blueprint

**資料儲存**:

- SQLite 資料庫: `data/tenants.db`
- API Keys 使用 Fernet 加密存儲
- 租戶配置快取 5 分鐘

**路由機制**:

- 所有 LINE Bot 使用相同的 Webhook URL: `/callback`
- 系統根據 webhook 中的 `destination` (Bot User ID) 識別租戶
- 如果找不到對應租戶，則使用預設的全域設定（向後相容）

### Setting Up a New Tenant

1. **取得 LINE Bot 資訊**:
   - 在 LINE Developers Console 建立 Messaging API Channel
   - 取得 Channel Access Token (long-lived)
   - 取得 Channel Secret
   - 取得 Bot 的 User ID (作為 `line_channel_id`)

2. **取得 Notion 資訊**:
   - 在 https://www.notion.so/my-integrations 建立 Integration
   - 取得 Integration Token
   - 建立或複製 Database，取得 Database ID
   - 將 Integration 加入 Database 的共用設定

3. **在管理後台設定**:
   - 登入 /admin
   - 點擊「新增租戶」
   - 填入上述資訊
   - 點擊「測試連線」確認設定正確

4. **設定 LINE Webhook**:
   - 在 LINE Developers Console 設定 Webhook URL: `https://eco-namecard.zeabur.app/callback`
   - 所有租戶使用相同的 URL

### Multi-Tenant Environment Variables

**管理後台專用**:

```bash
ADMIN_SECRET_KEY=<session 加密金鑰>
INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_PASSWORD=<安全密碼>
RESET_ADMIN_PASSWORD=false  # 設為 true 可重設密碼
TENANT_DB_PATH=data/tenants.db
```

**向後相容**:
現有的環境變數 (LINE_CHANNEL_ACCESS_TOKEN 等) 仍作為預設配置使用，
當 webhook 請求無法匹配任何租戶時，會 fallback 到這些預設設定。

### Database Schema

```sql
-- 租戶配置表
CREATE TABLE tenants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    is_active INTEGER DEFAULT 1,
    line_channel_id TEXT NOT NULL UNIQUE,
    line_channel_access_token_encrypted TEXT NOT NULL,
    line_channel_secret_encrypted TEXT NOT NULL,
    notion_api_key_encrypted TEXT NOT NULL,
    notion_database_id TEXT NOT NULL,
    google_api_key_encrypted TEXT,
    use_shared_google_api INTEGER DEFAULT 1,
    daily_card_limit INTEGER DEFAULT 50,
    batch_size_limit INTEGER DEFAULT 10,
    created_at TEXT,
    updated_at TEXT
);

-- 管理員帳號表
CREATE TABLE admin_users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_super_admin INTEGER DEFAULT 0,
    created_at TEXT,
    last_login TEXT
);

-- 使用統計表
CREATE TABLE usage_stats (
    tenant_id TEXT,
    date TEXT,
    cards_processed INTEGER DEFAULT 0,
    cards_saved INTEGER DEFAULT 0,
    api_calls INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    PRIMARY KEY (tenant_id, date)
);
```

### Troubleshooting Multi-Tenant

**管理後台無法登入**:

- 檢查 `ADMIN_SECRET_KEY` 環境變數是否設定
- 查看 logs 中的初始密碼

**租戶 Webhook 無回應**:

- 確認 `line_channel_id` 是 Bot 的 User ID (以 U 開頭)
- 使用管理後台的「測試連線」功能

**Notion 儲存失敗**:

- 確認 Integration 已加入 Database 共用
- 確認 Database 有必要的欄位 (Name, 公司, 電話 等)

---

## Image Processing Flow (圖片處理流程)

### Complete Flow Diagram

```
LINE 用戶上傳圖片
        ↓
┌─────────────────────────────────────────────────────────────┐
│  1. main.py: 接收 webhook, 識別租戶                         │
│     - extract_channel_id() 從 destination 取得 Bot User ID  │
│     - get_tenant_context() 查詢租戶配置                      │
│     - 創建租戶專屬的 event_handler                           │
├─────────────────────────────────────────────────────────────┤
│  2. event_handler.handle_image_message()                    │
│     - 檢查用戶是否被封鎖                                     │
│     - 檢查每日限額                                           │
│     - line_bot_api.get_message_content() 下載圖片            │
│     - security_service.validate_image_data() 驗證圖片        │
├─────────────────────────────────────────────────────────────┤
│  3. card_processor.process_image()                          │
│     - 圖片預處理 (大小調整、格式轉換)                         │
│     - Gemini AI 辨識名片內容                                 │
│     - 解析 JSON 回應，創建 BusinessCard 物件                  │
│     - 品質檢查 (confidence_score, quality_score)             │
├─────────────────────────────────────────────────────────────┤
│  4. notion_client.save_business_card()                      │
│     - 檢查 data_source_id (API 2025-09-03 必需)              │
│     - 準備 properties 和 children                            │
│     - pages.create() 創建 Notion 頁面                        │
│     - 返回 (page_id, page_url) 或 None                       │
├─────────────────────────────────────────────────────────────┤
│  5. submit_image_upload() → ImgBB                           │
│     - 條件: success_count > 0 AND saved_page_ids 不為空      │
│     - 非同步上傳圖片到 ImgBB                                  │
│     - 更新 Notion 頁面添加圖片                                │
└─────────────────────────────────────────────────────────────┘
```

### Critical Check Points

**為什麼 ImgBB 沒收到圖片？**

ImgBB 上傳只在以下條件都滿足時觸發：

```python
if success_count > 0 and saved_page_ids:
    submit_image_upload(...)
```

可能原因：

1. **Notion data_source_id 為 None**
   - API 2025-09-03 需要 data_source_id
   - 檢查: `notion_client.data_source_id`
   - Debug endpoint: `/debug/tenant/<tenant_id>/notion`

2. **save_business_card() 返回 None**
   - data_source_id 缺失
   - Notion API 權限問題
   - Database ID 錯誤

3. **AI 未識別到名片**
   - process_image() 拋出異常
   - 名片品質過低

### Debug Endpoints

```bash
# 測試預設 Notion 連接
curl https://eco-namecard.zeabur.app/debug/notion

# 測試特定租戶的 Notion 連接
curl https://eco-namecard.zeabur.app/debug/tenant/<tenant_id>/notion

# 查看最近收到的 LINE Bot User ID
curl https://eco-namecard.zeabur.app/debug/last-destination
```

### Notion API 2025-09-03

**重要變更**:

- 必須使用 `data_source_id` 而非 `database_id` 創建頁面
- 從 `databases.retrieve()` 獲取 `data_sources` 列表
- 使用 `data_sources/{id}/query` 查詢

**檢查 data_source_id**:

```python
# 在 NotionClient 初始化時獲取
db_response = client.databases.retrieve(database_id=self.database_id)
data_sources = db_response.get("data_sources", [])
self.data_source_id = data_sources[0].get("id") if data_sources else None
```

### Debug Logs (Warning Level)

上傳圖片時會產生以下 warning 級別日誌：

```json
{"event": "DEBUG_DOWNLOADING_IMAGE", "message_id": "...", ...}
{"event": "DEBUG_IMAGE_DOWNLOADED", "image_size": 12345, ...}
{"event": "DEBUG_AI_PROCESSING_START", ...}
{"event": "DEBUG_AI_PROCESSING_DONE", "cards_count": 1, ...}
{"event": "DEBUG_NOTION_SAVE_START", "data_source_id": "xxx" 或 "NONE!", ...}
{"event": "DEBUG_NOTION_SAVE_RESULT", "result_is_none": true/false, ...}
{"event": "DEBUG_BEFORE_IMGBB_CHECK", "success_count": 0/1, ...}
```

### Image Processing Flow Tests

```bash
# 執行端對端流程測試
pytest tests/test_image_processing_e2e.py -v

# 執行 Notion 連接測試
pytest tests/test_notion_connection.py -v

# 完整測試
pytest tests/test_image_processing_e2e.py tests/test_notion_connection.py -v
```

**測試覆蓋範圍**:

- `test_complete_image_processing_flow_success` - 完整成功流程
- `test_imgbb_not_triggered_when_notion_fails` - Notion 失敗時 ImgBB 不觸發
- `test_no_cards_detected` - AI 未識別到名片
- `test_data_source_id_obtained_success` - data_source_id 獲取成功
- `test_save_without_data_source_id_returns_none` - 無 data_source_id 時返回 None

### CI/CD Image Processing Tests

GitHub Actions 包含專門的圖片處理流程測試：

```yaml
image-processing-flow-test:
  runs-on: ubuntu-latest
  steps:
    - name: Run image processing flow tests
      run: |
        pytest tests/test_image_processing_e2e.py -v
        pytest tests/test_notion_connection.py -v
```

部署條件: `deploy` job 需要 `image-processing-flow-test` 通過

---

## Event Handler (事件處理器)

### UnifiedEventHandler

**位置**: `src/namecard/api/line_bot/event_handler.py`

統一的 LINE Bot 事件處理器，負責處理所有類型的用戶訊息。

**初始化參數**:

```python
UnifiedEventHandler(
    line_bot_api: LineBotApi,      # LINE Bot API 實例
    card_processor: CardProcessor,  # 名片 AI 處理器
    notion_client: NotionClient,    # Notion 儲存客戶端
    tenant_id: Optional[str] = None # 租戶 ID (多租戶模式)
)
```

### 支援的文字指令

| 指令 | 別名 | 功能 |
|------|------|------|
| `help` | `說明`, `幫助` | 顯示使用說明 |
| `批次` | `batch`, `批量` | 開始批次處理模式 |
| `狀態` | `status`, `進度` | 查看處理進度 |
| `結束批次` | `end batch`, `完成批次` | 結束批次模式並顯示總結 |
| `重試` | `retry`, `重新上傳` | 重試失敗的圖片上傳 |
| `清除失敗` | `clear failed` | 清除失敗任務記錄 |

### 核心方法

**`handle_text_message(user_id, text, reply_token)`**: 處理文字訊息，路由到對應的指令處理函數

**`handle_image_message(user_id, message_id, reply_token)`**: 處理圖片訊息

```
流程:
1. 檢查用戶封鎖狀態 (security_service.is_user_blocked)
2. 檢查每日限額 (user_service.get_user_status)
3. 下載圖片 (line_bot_api.get_message_content)
4. 驗證圖片 (security_service.validate_image_data)
5. AI 識別名片 (card_processor.process_image)
6. 儲存到 Notion (notion_client.save_business_card)
7. 回覆用戶處理結果
8. 非同步上傳圖片到 ImgBB (submit_image_upload)
```

### 私有方法

| 方法 | 功能 |
|------|------|
| `_send_help_message` | 發送說明訊息 + Quick Reply |
| `_start_batch_mode` | 開始批次模式 |
| `_show_status` | 顯示處理狀態 |
| `_end_batch_mode` | 結束批次並顯示總結 |
| `_retry_failed_uploads` | 重試失敗的上傳任務 |
| `_clear_failed_uploads` | 清除失敗任務記錄 |
| `_send_processing_result` | 發送處理結果 (Flex Message) |
| `_send_flex_message` | 發送 Flex Message |
| `_send_reply` | 發送純文字回覆 |
| `_save_user_profile` | 儲存用戶 LINE 資訊 (多租戶) |

---

## Image Upload Worker (圖片上傳工作器)

### 概述

**位置**: `src/namecard/infrastructure/storage/image_upload_worker.py`

非同步處理名片圖片上傳到 ImgBB 並更新 Notion 頁面。

**雙模式架構**:

```
┌──────────────────────────────────────────────────────┐
│                 submit_image_upload()                │
│                         │                            │
│            ┌────────────┴────────────┐               │
│            ▼                         ▼               │
│   ┌─────────────────┐     ┌──────────────────┐       │
│   │  RQ (推薦)       │     │  In-Memory Queue │       │
│   │                 │     │    (Fallback)    │       │
│   │ - Redis 持久化   │     │                  │       │
│   │ - 自動重試 3 次   │     │ - 無持久化       │       │
│   │ - 分散式處理     │     │ - 單線程處理     │       │
│   └─────────────────┘     └──────────────────┘       │
│            │                         │               │
│            └────────────┬────────────┘               │
│                         ▼                            │
│             ┌───────────────────────┐                │
│             │ 1. 上傳圖片到 ImgBB   │                │
│             │ 2. 更新 Notion 頁面   │                │
│             │ 3. 失敗記錄到 Redis   │                │
│             └───────────────────────┘                │
└──────────────────────────────────────────────────────┘
```

### RQ Worker (推薦)

**啟動方式**:

```bash
# 開發環境
python -m src.namecard.infrastructure.storage.rq_worker

# 生產環境
rq worker image_upload --url redis://localhost:6379/0
```

**任務配置**:

```python
retry=Retry(max=3, interval=[10, 30, 60])  # 重試 3 次：10s, 30s, 60s
job_timeout=300  # 5 分鐘超時
```

**核心函數**:

- `process_upload_task_rq()`: RQ 任務處理函數（必須是頂層函數才能被 pickle）
- `submit_to_rq()`: 提交任務到 RQ 隊列
- `get_rq_redis_client()`: 獲取 RQ 專用 Redis 客戶端 (`decode_responses=False`)

### In-Memory Queue Worker (Fallback)

當 RQ 或 Redis 不可用時自動使用。

**ImageUploadWorker 類**:

```python
class ImageUploadWorker:
    def start(self)   # 啟動單一背景線程
    def stop(self)    # 停止 worker
    def submit(task)  # 提交 ImageUploadTask
```

**單例模式**: 使用 `get_upload_worker()` 獲取全域實例

### Public API

```python
# 主要入口 - 自動選擇 RQ 或內存隊列
submit_image_upload(
    image_data: bytes,       # 圖片二進位資料
    page_ids: List[str],     # Notion 頁面 ID 列表
    notion_client: NotionClient,
    user_id: str
)
```

### 失敗任務管理

失敗的任務會記錄到 Redis，保留 7 天。

**Redis Key 格式**: `failed_upload:{user_id}:{task_id}`

**管理函數**:

| 函數 | 功能 |
|------|------|
| `get_failed_tasks(user_id)` | 查詢用戶的失敗任務列表 |
| `retry_failed_task(user_id, task_id, notion_client)` | 重試單一失敗任務 |
| `retry_all_failed_tasks(user_id, notion_client)` | 重試用戶所有失敗任務 |
| `clear_failed_tasks(user_id)` | 清除用戶所有失敗任務記錄 |
| `get_queue_info()` | 獲取隊列狀態（用於監控） |

### 失敗任務資料結構

```json
{
  "task_id": "abc12345",
  "user_id": "U1234567890abcdef",
  "page_ids": ["page-id-1", "page-id-2"],
  "error": "ImgBB upload failed",
  "timestamp": "2024-01-15T10:30:00",
  "image_url": null,
  "image_data_b64": "base64_encoded_image_data..."
}
```

### 環境變數

| 變數 | 說明 | 預設值 |
|------|------|--------|
| `REDIS_ENABLED` | 是否啟用 Redis | `false` |
| `REDIS_URL` | Redis 連線 URL | - |
| `REDIS_HOST` | Redis 主機 | `localhost` |
| `REDIS_PORT` | Redis 端口 | `6379` |
| `REDIS_PASSWORD` | Redis 密碼 | - |
| `REDIS_DB` | Redis 資料庫 | `0` |
| `REDIS_SOCKET_TIMEOUT` | 連線超時 | `5` |

### 監控端點

```bash
# 獲取隊列狀態
curl https://eco-namecard.zeabur.app/debug/queue-info

# 回傳範例
{
  "rq_available": true,
  "rq_enabled": true,
  "queue_name": "image_upload",
  "pending_jobs": 0,
  "failed_jobs": 2
}
```
