# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LINE Bot namecard management system that uses Google Gemini AI to recognize business card content and automatically saves to Notion database. The system supports batch processing, multi-card detection, and includes comprehensive security and error handling.

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
- Structured JSON response parsing
- Image preprocessing and size optimization

**Notion Database**
- Required properties: 姓名(Title), 公司, 職稱, 電話, Email, etc.
- Integration permissions and database sharing
- User-based data segregation

**Sentry Error Monitoring** ✅ **ACTIVE + RELEASE TRACKING**
- Real-time error tracking and notification system integrated via `sentry-sdk[flask]>=1.40.0`
- **🏷️ Release Tracking**: 每個錯誤自動關聯到 Git commit hash 和版本號 (format: 1.0.0+abc123)
- **📤 Source Context**: GitHub Actions 自動上傳 Python 原始碼到 Sentry，提供完整錯誤上下文
- **🚀 Deployment Monitoring**: 自動標記部署事件和環境變化，追蹤版本影響
- **📊 Version Management**: 自動生成和追蹤 release，支援版本回歸分析
- Performance monitoring with 10% sampling rate for production optimization
- Email notifications for new issues and high error rates
- Integration initialized in `app.py` with Flask integration and structured logging
- Debug endpoints: `/debug/sentry`, `/version`, `/deployment` for monitoring verification
- Debugging tools: `debug-sentry.py`, `test_release_tracking.py` for comprehensive troubleshooting
- **🔧 MCP Integration**: Sentry MCP server 支援在 Claude Code 中直接查詢錯誤和分析趨勢

## Development Workflow

1. Changes to `main` branch trigger automatic deployment
2. GitHub Actions runs quality checks, tests, and security scans
3. Successful builds deploy to Zeabur automatically
4. Health checks validate deployment success

## Critical Environment Variables

**Required**:
- `LINE_CHANNEL_ACCESS_TOKEN`, `LINE_CHANNEL_SECRET`
- `GOOGLE_API_KEY` (with optional `GOOGLE_API_KEY_FALLBACK`)
- `NOTION_API_KEY`, `NOTION_DATABASE_ID`
- `SECRET_KEY`
- `SENTRY_DSN` (error monitoring and alerting)

**Operational**:
- `RATE_LIMIT_PER_USER=50`, `BATCH_SIZE_LIMIT=10`
- `MAX_IMAGE_SIZE=10485760` (10MB)

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
- 版本資訊: https://namecard-app.zeabur.app/version
- 部署狀態: https://namecard-app.zeabur.app/deployment
- Notion 欄位: https://namecard-app.zeabur.app/debug/notion
- 系統設定: https://namecard-app.zeabur.app/test
- Sentry 配置: https://namecard-app.zeabur.app/debug/sentry
- 錯誤監控: https://sentry.io (需登入查看 Issues)

**📋 維護重點**:
- 每月測試 LINE Bot 和 Notion 功能
- 定期檢查 Sentry Dashboard 的錯誤趨勢
- 修改時採用小步驟原則
- 每次變更都要測試
- 記錄所有修改內容
- 監控 Sentry 錯誤率和效能指標

**🆘 緊急修復**:
- 如果服務異常，先檢查 /health 端點
- 如果 Notion 無法儲存，檢查 /debug/notion
- 如果 Sentry 錯誤監控異常，執行 `python debug-sentry.py` 診斷
- 程式修改出錯可用 `git reset --hard HEAD~1` 回退

## Sentry 錯誤監控系統

**監控 Dashboard 工作流程**:
1. **日常監控**: 每週檢查 https://sentry.io Dashboard 的 Issues 頁面
2. **錯誤分析**: 按錯誤頻率、影響用戶數和時間趨勢分析問題優先級
3. **效能監控**: 檢查 Performance 頁面的 API 回應時間和錯誤率趨勢
4. **警報設定**: 確保 Email 通知已啟用，收到高頻錯誤或新問題通知

**故障排除工具包**:
```bash
# 完整診斷 Sentry 配置
python debug-sentry.py

# 強制觸發測試錯誤
python force-sentry-test.py

# 測試 Release Tracking 功能
python test_release_tracking.py

# 檢查即時配置狀態
curl https://namecard-app.zeabur.app/debug/sentry

# 檢查版本和部署資訊
curl https://namecard-app.zeabur.app/version
curl https://namecard-app.zeabur.app/deployment
```

**常見 Sentry 問題**:
- **配置正確但無錯誤記錄**: 環境變數可能正確但 SDK 初始化失敗，檢查 Zeabur 部署日誌
- **Debug 端點 404**: 表示程式部署未成功，需重新推送到 GitHub 觸發部署
- **測試錯誤不出現**: 等待 3-5 分鐘，Sentry 有延遲，或檢查專案設定

Repository: https://github.com/chengzehsu/eco_namecard
Deployment: https://namecard-app.zeabur.app