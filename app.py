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
import json
from datetime import datetime

# 添加項目根目錄到 Python 路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# #region agent log
import os as _os_for_debug
_DEBUG_LOG_PATH = _os_for_debug.path.join(_os_for_debug.path.dirname(_os_for_debug.path.abspath(__file__)), ".cursor", "debug.log")
_os_for_debug.makedirs(_os_for_debug.path.dirname(_DEBUG_LOG_PATH), exist_ok=True)
def _debug_log(hypothesis_id: str, location: str, message: str, data: dict = None):
    try:
        import json, time
        log_entry = {"hypothesisId": hypothesis_id, "location": location, "message": message, "data": data or {}, "timestamp": int(time.time() * 1000), "sessionId": "debug-session"}
        with open(_DEBUG_LOG_PATH, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        # 如果無法寫入文件，至少打印到 stdout（Zeabur 會捕獲）
        print(f"DEBUG_LOG: {json.dumps(log_entry) if 'log_entry' in dir() else message}")

_debug_log("A", "app.py:1", "APP_STARTUP_BEGIN", {"step": "imports", "debug_log_path": _DEBUG_LOG_PATH})
print(f"[DEBUG] APP_STARTUP_BEGIN - debug_log_path={_DEBUG_LOG_PATH}", flush=True)
# #endregion

# #region agent log
_debug_log("A", "app.py:import_config", "IMPORTING_CONFIG", {})
# #endregion

# 導入配置和主應用
from simple_config import settings

# #region agent log
_debug_log("A", "app.py:config_loaded", "CONFIG_LOADED", {"port": settings.app_port, "flask_env": settings.flask_env, "line_token_set": bool(settings.line_channel_access_token), "notion_key_set": bool(settings.notion_api_key)})
# #endregion

# 設置日誌
import logging

# 設定 Python logging 級別為 INFO，讓 structlog 可以輸出 info 級別日誌
logging.basicConfig(
    format="%(message)s",
    level=logging.INFO,  # 這是關鍵！沒有這行，默認是 WARNING
)

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

# #region agent log
_debug_log("B", "app.py:before_main_import", "IMPORTING_LINE_BOT_MAIN", {})
# #endregion

# 導入主應用（在 Redis 初始化之後）
try:
    from src.namecard.api.line_bot.main import app
    # #region agent log
    _debug_log("B", "app.py:main_imported", "LINE_BOT_MAIN_IMPORTED_OK", {})
    # #endregion
except Exception as _import_err:
    # #region agent log
    _debug_log("B", "app.py:main_import_failed", "LINE_BOT_MAIN_IMPORT_FAILED", {"error": str(_import_err), "error_type": type(_import_err).__name__})
    # #endregion
    raise

# ==================== 多租戶管理後台設定 ====================

# 設定 Flask session secret key
admin_secret_key = os.environ.get("ADMIN_SECRET_KEY") or os.environ.get("SECRET_KEY", "dev-secret-key")
app.secret_key = admin_secret_key

# 註冊管理後台 Blueprint
from src.namecard.api.admin import admin_bp
app.register_blueprint(admin_bp)

# ==================== SocketIO 初始化 ====================
from src.namecard.api.admin.socketio_events import init_socketio, get_socketio
socketio = init_socketio(app)
logger.info("SocketIO initialized for real-time sync progress")

# #region agent log
_debug_log("C", "app.py:before_tenant_db", "INITIALIZING_TENANT_DB", {})
# #endregion

# 初始化租戶資料庫
from src.namecard.infrastructure.storage.tenant_db import get_tenant_db
try:
    tenant_db = get_tenant_db()
    # #region agent log
    _debug_log("C", "app.py:tenant_db_ok", "TENANT_DB_INITIALIZED_OK", {"db_path": tenant_db.db_path})
    # #endregion
    logger.info("Tenant database initialized", db_path=tenant_db.db_path)
except Exception as e:
    # #region agent log
    _debug_log("C", "app.py:tenant_db_failed", "TENANT_DB_INIT_FAILED", {"error": str(e), "error_type": type(e).__name__})
    # #endregion
    logger.warning("Failed to initialize tenant database", error=str(e))

# 初始化管理員認證（會自動建立初始管理員）
try:
    from src.namecard.api.admin.auth import get_admin_auth
    admin_auth = get_admin_auth()
    logger.info("Admin authentication initialized")
except Exception as e:
    logger.warning("Failed to initialize admin auth", error=str(e))

logger.info("Multi-tenant admin panel enabled", admin_url="/admin")

# #region agent log
_debug_log("A", "app.py:admin_panel_enabled", "ADMIN_PANEL_ENABLED", {})

# 自動創建預設租戶（從環境變數）
def init_default_tenant():
    """Auto-create default tenant from environment variables if all required vars are set"""
    from src.namecard.core.services.tenant_service import get_tenant_service
    from src.namecard.core.models.tenant import TenantCreateRequest

    # 檢查必要環境變數是否都有設定
    if not all([
        settings.line_channel_id,
        settings.line_channel_access_token,
        settings.line_channel_secret,
        settings.notion_api_key,
        settings.notion_database_id
    ]):
        logger.info("Skipping default tenant creation (incomplete env vars)")
        return

    try:
        tenant_service = get_tenant_service()

        # 檢查該 channel_id 的租戶是否已存在
        existing = tenant_service.get_tenant_by_channel_id(settings.line_channel_id)
        if existing:
            logger.info("Default tenant already exists", tenant_id=existing.id, name=existing.name)
            return

        # 創建預設租戶
        request = TenantCreateRequest(
            name="Default Tenant",
            slug="default",
            line_channel_id=settings.line_channel_id,
            line_channel_access_token=settings.line_channel_access_token,
            line_channel_secret=settings.line_channel_secret,
            notion_api_key=settings.notion_api_key,
            notion_database_id=settings.notion_database_id,
            google_api_key=settings.google_api_key if settings.google_api_key else None,
            use_shared_google_api=True,
        )
        tenant = tenant_service.create_tenant(request)
        logger.info("Default tenant auto-created from env vars", tenant_id=tenant.id)
    except Exception as e:
        logger.error("Failed to auto-create default tenant", error=str(e))

try:
    init_default_tenant()
    # #region agent log
    _debug_log("A", "app.py:default_tenant_init", "DEFAULT_TENANT_INIT_COMPLETED", {})
    # #endregion
except Exception as e:
    # #region agent log
    _debug_log("A", "app.py:default_tenant_init_failed", "DEFAULT_TENANT_INIT_FAILED", {"error": str(e), "error_type": type(e).__name__})
    # #endregion
    logger.warning("Default tenant initialization skipped", error=str(e))

# #region agent log
_debug_log("A", "app.py:startup_complete", "APP_STARTUP_COMPLETE", {"ready_for_gunicorn": True})
print("[DEBUG] APP_STARTUP_COMPLETE - ready_for_gunicorn=True", flush=True)
# #endregion

# ===========================================================

def main():
    """主函數"""
    logger.info("Starting LINE Bot Namecard System",
                version="3.0.0",
                port=settings.app_port,
                environment=settings.flask_env,
                multi_tenant=True)
    
    try:
        # 使用 SocketIO 啟動（支援 WebSocket）
        from src.namecard.api.admin.socketio_events import get_socketio
        sio = get_socketio()
        if sio:
            sio.run(
                app,
                host=settings.app_host,
                port=settings.app_port,
                debug=settings.debug,
            )
        else:
            # Fallback to regular Flask
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