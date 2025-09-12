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


## Development Workflow

1. Changes to `main` branch trigger automatic deployment
2. GitHub Actions runs quality checks, tests, and security scans
3. Successful builds deploy to Zeabur automatically
4. Health checks validate deployment success

## Qodo PR Review Agent ✅ **ACTIVE** (Google Gemini Powered)

**AI-Powered Code Review System** integrated via qodo-ai/pr-agent using Google Gemini 1.5 Flash model
- Leverages existing Google Gemini API key for seamless integration with project AI infrastructure
- Comprehensive security-focused review for LINE Bot webhook handling and API integrations
- Traditional Chinese responses tailored for Taiwan-focused namecard processing system
- Automated code suggestions for performance optimization and security hardening
- Interactive Q&A capability for technical questions about AI integration and Notion operations

**設定檔案**:
- **GitHub Workflow**: `.github/workflows/pr_agent.yml` - 自動觸發 PR 審查
- **配置檔案**: `.pr_agent.toml` - 專案特定審查規則和中文回應設定

**觸發方式**:
```bash
# 自動觸發 (PR 開啟/更新時)
git push origin feature-branch

# 手動觸發命令 (在 PR 留言中)
/review          # 完整程式碼審查  
/describe        # 生成 PR 描述
/improve         # 改進建議
/ask "問題內容"   # 技術問答
```

**審查重點領域**:
- **🔒 安全性**: Webhook 驗證、API 金鑰管理、個資保護
- **🤖 AI 整合**: Google Gemini API 錯誤處理、圖片驗證
- **📱 LINE Bot**: 批次處理、使用者體驗優化  
- **🏪 Notion 整合**: 資料庫操作效率、搜尋功能
- **✅ 測試覆蓋**: 新功能測試需求、Mock 設定驗證

**設定管理**:
```bash
# 測試 PR Agent 配置
curl -s "https://api.github.com/repos/chengzehsu/eco_namecard/contents/.pr_agent.toml"

# 檢查 GitHub Actions 狀態
gh run list --workflow="pr_agent.yml"
```

**故障排除**:
- **PR Agent 無回應**: 檢查現有的 `GOOGLE_API_KEY` 權限是否包含 Gemini API 存取
- **API 配額問題**: 與名片識別功能共用 Google API 配額，監控使用量
- **中文回應異常**: 確認 `.pr_agent.toml` 中 `response_language = "Traditional Chinese"` 設定
- **審查內容不符需求**: 更新 `.pr_agent.toml` 中的 `extra_instructions` 客製化指令

## Critical Environment Variables

**Required**:
- `LINE_CHANNEL_ACCESS_TOKEN`, `LINE_CHANNEL_SECRET`
- `GOOGLE_API_KEY` (with optional `GOOGLE_API_KEY_FALLBACK`) - 同時用於名片識別和 PR 審查
- `NOTION_API_KEY`, `NOTION_DATABASE_ID`
- `SECRET_KEY`

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
- Notion 欄位: https://namecard-app.zeabur.app/debug/notion
- 系統設定: https://namecard-app.zeabur.app/test
- GitHub Actions: https://github.com/chengzehsu/eco_namecard/actions (CI/CD 和 PR 審查)

**📋 維護重點**:
- 每月測試 LINE Bot 和 Notion 功能
- 監控 GitHub Actions 中 qodo PR 審查功能運作
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