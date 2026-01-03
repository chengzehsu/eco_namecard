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
