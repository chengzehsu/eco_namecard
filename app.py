#!/usr/bin/env python3
"""
LINE Bot 名片管理系統 - 主啟動文件
智能 LINE Bot 名片管理系統，使用 Google Gemini AI 識別名片內容，並自動存入 Notion 資料庫
"""

import os
import sys
import structlog
from datetime import datetime

# 添加項目根目錄到 Python 路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 導入配置和主應用
from simple_config import settings

# 設置日誌
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer() if settings.debug else structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    context_class=dict,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# 初始化 Sentry (如果配置了)
if settings.sentry_dsn:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            integrations=[FlaskIntegration()],
            traces_sample_rate=0.1,
            environment=settings.flask_env
        )
        logger.info("Sentry monitoring enabled")
    except ImportError:
        logger.warning("Sentry SDK not installed, monitoring disabled")

# 導入主應用
from src.namecard.api.line_bot.main import app

def main():
    """主函數"""
    logger.info("Starting LINE Bot Namecard System", 
                version="1.0.0",
                port=settings.app_port,
                environment=settings.flask_env)
    
    try:
        # 啟動 Flask 應用
        app.run(
            host=settings.app_host,
            port=settings.app_port,
            debug=settings.debug,
            threaded=True
        )
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error("Application startup failed", error=str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()