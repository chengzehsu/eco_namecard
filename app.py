#!/usr/bin/env python3
"""
LINE Bot 名片管理系統 - 主啟動文件（多租戶版）
智能 LINE Bot 名片管理系統，使用 Google Gemini AI 識別名片內容，並自動存入 Notion 資料庫

支援多租戶模式：
- 管理後台 (/admin) 用於管理多個 LINE Bot 租戶
- 每個租戶可有獨立的 LINE Bot 和 Notion Database
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


# 初始化 Redis 和服務
from src.namecard.infrastructure.redis_client import get_redis_client, close_redis_client
from src.namecard.core.services.user_service import user_service, create_user_service
from src.namecard.core.services.security import security_service, create_security_service

# 初始化 Redis
redis_client = get_redis_client()

# 如果 Redis 可用，重新創建服務實例
if redis_client:
    # 使用新的 user_service 實例替換全域實例
    import src.namecard.core.services.user_service as user_service_module
    import src.namecard.core.services.security as security_module

    user_service_module.user_service = create_user_service(
        redis_client=redis_client,
        use_redis=True
    )

    security_module.security_service = create_security_service(
        redis_client=redis_client,
        use_redis=True
    )

    logger.info("Services initialized with Redis backend",
               services=["UserService", "SecurityService"])
else:
    logger.info("Services using in-memory backend (Redis not available)",
               services=["UserService", "SecurityService"])

# 導入主應用（在 Redis 初始化之後）
from src.namecard.api.line_bot.main import app

# ==================== 多租戶管理後台設定 ====================

# 設定 Flask session secret key
admin_secret_key = os.environ.get("ADMIN_SECRET_KEY") or os.environ.get("SECRET_KEY", "dev-secret-key")
app.secret_key = admin_secret_key

# 註冊管理後台 Blueprint
from src.namecard.api.admin import admin_bp
app.register_blueprint(admin_bp)

# 初始化租戶資料庫
from src.namecard.infrastructure.storage.tenant_db import get_tenant_db
try:
    tenant_db = get_tenant_db()
    logger.info("Tenant database initialized", db_path=tenant_db.db_path)
except Exception as e:
    logger.warning("Failed to initialize tenant database", error=str(e))

# 初始化管理員認證（會自動建立初始管理員）
try:
    from src.namecard.api.admin.auth import get_admin_auth
    admin_auth = get_admin_auth()
    logger.info("Admin authentication initialized")
except Exception as e:
    logger.warning("Failed to initialize admin auth", error=str(e))

logger.info("Multi-tenant admin panel enabled", admin_url="/admin")

# ===========================================================

def main():
    """主函數"""
    logger.info("Starting LINE Bot Namecard System",
                version="3.0.0",
                port=settings.app_port,
                environment=settings.flask_env,
                multi_tenant=True)
    
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
    finally:
        # 清理 Redis 連接
        close_redis_client()
        logger.info("Application shutdown complete")

# 導出 Flask 應用實例供 gunicorn 使用
application = app

if __name__ == "__main__":
    main()