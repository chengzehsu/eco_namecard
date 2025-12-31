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

- `tests/test_health.py` - API endpoint health checks
- `tests/test_card_models.py` - Pydantic model validation
- `tests/test_user_service.py` - Batch processing and rate limiting
- `tests/conftest.py` - Shared fixtures and mocks

Target coverage: 70% minimum, 90%+ for core business logic.

## Deployment Configuration

**GitHub Actions** (`.github/workflows/deploy.yml`)
- Multi-stage pipeline: test → security-scan → deploy → performance-test
- Zeabur integration with service ID and API token
- Automatic health checks post-deployment

**Zeabur** (`zeabur.json`)
- Production deployment to namecard-app.zeabur.app
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
- Webhook URL: https://namecard-app.zeabur.app/callback
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

## Error Message System 🆕

**User-Friendly Error Messages** - 專為內部使用優化，方便業務回報和 IT debug

**14 種詳細錯誤類型**：

**AI 識別階段 (9 種)**：
- 🔑 API 金鑰無效 - 提示檢查 `GOOGLE_API_KEY`
- ⚠️ API 配額用完 - **自動切換到 fallback key**（透明無縫），兩個都用完才顯示錯誤
- 🛡️ 安全機制阻擋 - Gemini 安全過濾器
- 📊 名片品質過低 - 顯示信心度和品質分數
- 📝 資訊不完整 - 列出已識別和缺失的欄位
- 🖼️ 解析度過低 - 顯示目前/最低要求像素
- 📄 JSON 格式錯誤 - 提示檢查 API 回應
- 🤖 AI 未能分析 - 區分「沒名片」vs「無法識別」
- ⏱️ 處理超時 - 顯示等待時間

**Notion 儲存階段 (5 種)**：
- 🔐 權限不足 - 提示檢查 `NOTION_API_KEY` 和 Integration
- 📁 資料庫不存在 - 顯示 Database ID
- 🔧 Schema 錯誤 - 列出缺少的欄位名稱
- ⏱️ Rate Limiting - Notion API 速率限制
- 🌐 網路連線問題 - 區分 Google 和 Notion

**開發者除錯模式**：
```bash
# 在 Zeabur 環境變數中設定
VERBOSE_ERRORS=true

# 效果：顯示完整的技術錯誤訊息、異常類型、堆疊追蹤
```

**使用方式**：
- 業務人員：遇到錯誤直接截圖給 IT，訊息已包含需檢查的環境變數和設定
- IT 人員：根據錯誤訊息立即定位問題（無需查 logs）
- 開發人員：啟用 VERBOSE_ERRORS 查看完整技術細節

**Quota Fallback 機制** 🆕：
- 主要 API key quota exceeded 時，**自動且透明地**切換到 fallback key
- 用戶無感：切換過程完全透明，請求直接成功
- IT 可監控：切換事件記錄在日誌中
- 自動恢復：配額重置後（每日 00:00 UTC）自動恢復使用主要 key
- 配置方式：設定 `GOOGLE_API_KEY_FALLBACK` 環境變數即可啟用

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

**📖 完整維護指南**: 請參考 `MAINTENANCE.md` 文件，專為初學者設計

**🔧 常用檢查連結**:
- 系統健康: https://namecard-app.zeabur.app/health
- Notion 欄位: https://namecard-app.zeabur.app/debug/notion
- 系統設定: https://namecard-app.zeabur.app/test
- GitHub Actions: https://github.com/chengzehsu/eco_namecard/actions

**📋 維護重點**:
- 每月測試 LINE Bot 和 Notion 功能
- 監控 GitHub Actions 中的 CI/CD 流程
- 修改時採用小步驟原則
- 每次變更都要測試
- 記錄所有修改內容
- 檢查應用程式 logs 中的錯誤和警告訊息

**🆘 緊急修復**:
- 如果服務異常，先檢查 /health 端點
- 如果 Notion 無法儲存，檢查 /debug/notion
- 檢查 Zeabur 部署日誌中的錯誤訊息
- 程式修改出錯可用 `git reset --hard HEAD~1` 回退

Repository: https://github.com/chengzehsu/eco_namecard
Deployment: https://namecard-app.zeabur.app

## Multi-Tenant Management System

### Overview

系統支援多租戶模式，讓你可以幫多個朋友設定獨立的 LINE Bot 和 Notion Database，所有請求由單一應用程式處理。

### Admin Panel

**管理後台 URL**: https://namecard-app.zeabur.app/admin

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
   - 在 LINE Developers Console 設定 Webhook URL: `https://namecard-app.zeabur.app/callback`
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