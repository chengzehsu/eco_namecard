"""
LINE Bot 名片識別系統 - 主應用（多租戶版）

支援多租戶模式：根據 LINE Channel ID 動態路由到對應的租戶配置。
向後相容：如果沒有找到租戶配置，則使用全域預設設定。
"""

from flask import Flask, request, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, ImageMessage
import structlog
import os
import sys
import json
from datetime import datetime
from typing import Optional

# 添加項目根目錄到 Python 路徑
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../..'))

from simple_config import settings
from src.namecard.core.services.security import security_service
from src.namecard.infrastructure.ai.card_processor import CardProcessor
from src.namecard.infrastructure.storage.notion_client import NotionClient
from src.namecard.api.line_bot.event_handler import UnifiedEventHandler

# 多租戶支援
from src.namecard.core.models.tenant import TenantConfig, TenantContext
from src.namecard.core.services.tenant_service import get_tenant_service

logger = structlog.get_logger()

# #region agent log
import os as _os_for_debug
_DEBUG_LOG_PATH = _os_for_debug.path.join(_os_for_debug.path.dirname(_os_for_debug.path.abspath(__file__)), "../../../../.cursor", "debug.log")
try:
    _os_for_debug.makedirs(_os_for_debug.path.dirname(_DEBUG_LOG_PATH), exist_ok=True)
except Exception:
    pass
def _debug_log(hypothesis_id: str, location: str, message: str, data: dict = None):
    try:
        import json, time
        log_entry = {"hypothesisId": hypothesis_id, "location": location, "message": message, "data": data or {}, "timestamp": int(time.time() * 1000), "sessionId": "debug-session"}
        with open(_DEBUG_LOG_PATH, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception:
        # 如果無法寫入文件，打印到 stdout
        import json
        print(f"DEBUG_LOG: {json.dumps({'h': hypothesis_id, 'l': location, 'm': message, 'd': data})}")

_debug_log("D", "main.py:module_start", "LINE_BOT_MAIN_MODULE_START", {})
# #endregion

app = Flask(__name__)

# ==================== 預設單租戶服務 (向後相容) ====================

# #region agent log
_debug_log("D", "main.py:before_linebot_init", "INITIALIZING_DEFAULT_LINEBOT", {
    "token_length": len(settings.line_channel_access_token) if settings.line_channel_access_token else 0,
    "secret_length": len(settings.line_channel_secret) if settings.line_channel_secret else 0,
    "token_empty": not settings.line_channel_access_token,
    "secret_empty": not settings.line_channel_secret
})
# #endregion

# 初始化預設 LINE Bot (使用全域設定) - 容錯模式
default_line_bot_api = None
default_handler = None
default_card_processor = None
default_notion_client = None
default_event_handler = None

try:
    print("[INIT] Initializing LINE Bot API...", flush=True)
    default_line_bot_api = LineBotApi(settings.line_channel_access_token or "dummy_token")
    default_handler = WebhookHandler(settings.line_channel_secret or "dummy_secret")
    print("[INIT] LINE Bot API initialized OK", flush=True)
except Exception as _linebot_err:
    print(f"[INIT] LINE Bot API init failed (non-fatal): {_linebot_err}", flush=True)

# 初始化預設服務 - 容錯模式
try:
    print("[INIT] Initializing CardProcessor...", flush=True)
    default_card_processor = CardProcessor()
    print("[INIT] CardProcessor initialized OK", flush=True)
except Exception as _card_err:
    print(f"[INIT] CardProcessor init failed (non-fatal): {_card_err}", flush=True)

try:
    print("[INIT] Initializing NotionClient...", flush=True)
    default_notion_client = NotionClient()
    print("[INIT] NotionClient initialized OK", flush=True)
except Exception as _notion_err:
    print(f"[INIT] NotionClient init failed (non-fatal): {_notion_err}", flush=True)

# 預設事件處理器 - 只有在所有服務都初始化成功時才創建
if default_line_bot_api and default_card_processor and default_notion_client:
    try:
        default_event_handler = UnifiedEventHandler(
            line_bot_api=default_line_bot_api,
            card_processor=default_card_processor,
            notion_client=default_notion_client
        )
        print("[INIT] UnifiedEventHandler initialized OK", flush=True)
    except Exception as _handler_err:
        print(f"[INIT] UnifiedEventHandler init failed (non-fatal): {_handler_err}", flush=True)
else:
    print("[INIT] Skipping UnifiedEventHandler (missing dependencies)", flush=True)

print("[INIT] All initialization complete - app ready to serve", flush=True)


# ==================== 多租戶工具函數 ====================

# 儲存最近收到的 webhook destination（用於 debug）
_last_destination = {"value": None, "timestamp": None}

def extract_channel_id(body: str) -> Optional[str]:
    """
    從 webhook body 中提取 LINE Channel ID

    LINE webhook 的 destination 欄位包含接收此事件的 Bot 的 User ID，
    但我們需要 Channel ID。這裡我們從事件中提取。

    注意：LINE Platform 不直接在 webhook 中提供 Channel ID，
    但我們可以用 destination (Bot User ID) 來識別租戶。
    在設定租戶時，需要使用 Bot User ID 作為 line_channel_id。
    """
    try:
        data = json.loads(body)
        # destination 是接收此 webhook 的 Bot 的 User ID
        destination = data.get('destination')
        if destination:
            # 儲存到全域變數供 debug endpoint 使用
            global _last_destination
            _last_destination["value"] = destination
            _last_destination["timestamp"] = str(datetime.now())
            # #region agent log
            # 明確記錄收到的 Bot User ID，方便用戶配置
            logger.warning("WEBHOOK_RECEIVED", bot_user_id=destination, hint="Use this value as line_channel_id in tenant config")
            # #endregion
            return destination
        else:
            logger.warning("No destination in webhook body")
    except json.JSONDecodeError:
        logger.error("Failed to parse webhook body as JSON")
    return None


def get_tenant_context(channel_id: str) -> Optional[TenantContext]:
    """
    根據 Channel ID 獲取租戶上下文

    Args:
        channel_id: LINE Channel ID (實際上是 Bot User ID)

    Returns:
        TenantContext 如果找到租戶，否則 None
    """
    try:
        tenant_service = get_tenant_service()
        tenant = tenant_service.get_tenant_by_channel_id(channel_id)
        # #region agent log
        logger.warning("DEBUG_TENANT_LOOKUP", channel_id=channel_id, tenant_found=tenant is not None, tenant_name=tenant.name if tenant else None, tenant_is_active=tenant.is_active if tenant else None)
        # #endregion
        if tenant and tenant.is_active:
            return TenantContext(tenant)
    except Exception as e:
        logger.warning("Failed to get tenant context", channel_id=channel_id, error=str(e))
    return None


def get_event_handler_for_tenant(context: TenantContext) -> UnifiedEventHandler:
    """
    為租戶創建事件處理器

    Args:
        context: TenantContext

    Returns:
        UnifiedEventHandler 配置為使用租戶的服務
    """
    return UnifiedEventHandler(
        line_bot_api=context.line_bot_api,
        card_processor=context.card_processor,
        notion_client=context.notion_client,
        tenant_id=context.tenant_id
    )


def try_auto_activate_tenant(body: str, signature: str, channel_id: str) -> Optional[TenantContext]:
    """
    嘗試自動匹配並啟用 pending 狀態的租戶

    當 webhook 收到來自未知 channel_id 的請求時，遍歷所有 pending 租戶，
    使用各自的 channel_secret 驗證簽名。如果驗證成功，表示這個 Bot
    屬於該租戶，自動綁定並啟用。

    Args:
        body: Webhook 請求體
        signature: LINE 簽名
        channel_id: LINE Bot User ID (destination)

    Returns:
        啟用成功的 TenantContext，否則 None
    """
    try:
        tenant_service = get_tenant_service()
        pending_tenants = tenant_service.get_pending_tenants()

        if not pending_tenants:
            logger.debug("No pending tenants to match")
            return None

        logger.info("Attempting auto-activation", pending_count=len(pending_tenants), channel_id=channel_id[:10] + "...")

        for tenant in pending_tenants:
            # 使用該租戶的 channel_secret 驗證簽名
            if security_service.validate_line_signature(body, signature, tenant.line_channel_secret):
                # 簽名驗證成功！這個 Bot 屬於這個租戶
                logger.info(
                    "Auto-activation signature match found",
                    tenant_id=tenant.id,
                    tenant_name=tenant.name
                )

                # 啟用租戶並綁定 channel_id
                activated_tenant = tenant_service.activate_tenant_with_channel_id(tenant.id, channel_id)

                if activated_tenant:
                    logger.info(
                        "Tenant auto-activated successfully",
                        tenant_id=activated_tenant.id,
                        tenant_name=activated_tenant.name,
                        channel_id=channel_id[:10] + "..."
                    )
                    return TenantContext(activated_tenant)

        logger.debug("No pending tenant matched the signature")
        return None

    except Exception as e:
        logger.error("Auto-activation failed", error=str(e))
        return None


# ==================== Webhook 端點 ====================

@app.route("/callback", methods=['POST'])
def callback():
    """
    LINE Webhook 回調端點（多租戶版）

    處理來自 LINE 平台的所有事件，包括訊息、圖片等。
    根據 Channel ID 動態路由到對應的租戶配置。
    """
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)

    # 基本輸入驗證
    if not signature or not body:
        logger.warning("Missing signature or body in webhook request")
        return jsonify({"status": "missing signature or body"}), 200

    # 檢查請求大小（1MB 限制）
    if len(body) > 1024 * 1024:
        logger.warning("Webhook request too large", size=len(body))
        return jsonify({"status": "request too large"}), 200

    # 嘗試識別租戶
    channel_id = extract_channel_id(body)
    tenant_context = get_tenant_context(channel_id) if channel_id else None

    # 如果找不到租戶，嘗試自動匹配 pending 租戶
    if not tenant_context and channel_id:
        tenant_context = try_auto_activate_tenant(body, signature, channel_id)

    # #region agent log
    logger.warning("DEBUG_ROUTING", channel_id=channel_id, tenant_found=tenant_context is not None, mode="multi-tenant" if tenant_context else "default")
    if not tenant_context and channel_id:
        logger.info("DEBUG_TENANT_NOT_FOUND", webhook_destination=channel_id, hint="No matching tenant found, falling back to default mode")
    # #endregion
    if tenant_context:
        # 多租戶模式
        logger.info("Multi-tenant mode",
                   tenant_id=tenant_context.tenant_id,
                   tenant_name=tenant_context.tenant_name)
        return process_multi_tenant(body, signature, tenant_context)
    else:
        # 向後相容：使用預設配置
        logger.info("Default mode (no tenant found)")
        return process_default(body, signature)


def process_multi_tenant(body: str, signature: str, context: TenantContext):
    """
    多租戶模式處理

    使用租戶專屬的配置驗證簽名和處理事件。
    """
    # #region agent log
    logger.warning("DEBUG_MULTI_TENANT_START", tenant_id=context.tenant_id, tenant_name=context.tenant_name)
    # #endregion
    # 驗證簽名（使用租戶的 secret）
    if settings.flask_env == "production":
        if not security_service.validate_line_signature(
            body, signature, context.tenant.line_channel_secret
        ):
            logger.error("LINE webhook signature validation failed",
                        tenant_id=context.tenant_id)
            return jsonify({"status": "invalid signature"}), 200

    try:
        # 創建租戶專屬的事件處理器
        # #region agent log
        logger.warning("DEBUG_CREATING_EVENT_HANDLER", tenant_id=context.tenant_id)
        # #endregion
        event_handler = get_event_handler_for_tenant(context)
        # #region agent log
        logger.warning("DEBUG_EVENT_HANDLER_CREATED", tenant_id=context.tenant_id)
        # #endregion

        # 記錄使用統計
        tenant_service = get_tenant_service()
        tenant_service.record_usage(context.tenant_id, api_calls=1)

        # 處理事件
        # #region agent log
        logger.warning("DEBUG_BEFORE_PROCESS_EVENTS", tenant_id=context.tenant_id)
        # #endregion
        process_events_with_handler(body, event_handler, context.line_bot_api)
        # #region agent log
        logger.warning("DEBUG_AFTER_PROCESS_EVENTS", tenant_id=context.tenant_id)
        # #endregion

    except Exception as e:
        # #region agent log
        logger.error("DEBUG_MULTI_TENANT_ERROR", tenant_id=context.tenant_id, error=str(e), error_type=type(e).__name__)
        # #endregion
        logger.error("Multi-tenant webhook processing error",
                    tenant_id=context.tenant_id,
                    error=str(e))
        # 記錄錯誤
        try:
            tenant_service = get_tenant_service()
            tenant_service.record_usage(context.tenant_id, errors=1)
        except Exception:
            pass
        return jsonify({"status": "processing error"}), 200

    return 'OK'


def process_default(body: str, signature: str):
    """
    預設模式處理（向後相容）

    使用全域配置驗證簽名和處理事件。
    """
    # 驗證簽名（生產環境）
    if settings.flask_env == "production":
        if not security_service.validate_line_signature(
            body, signature, settings.line_channel_secret
        ):
            logger.error("LINE webhook signature validation failed")
            security_service.log_security_event(
                "invalid_webhook_signature",
                "unknown",
                {"signature": signature[:20] + "..."}
            )
            return jsonify({"status": "invalid signature"}), 200
    else:
        logger.info("Signature validation skipped in non-production environment")

    try:
        # 開發環境：手動解析
        if settings.flask_env != "production":
            process_events_manually(body)
        else:
            # 生產環境：使用 LINE SDK
            body = security_service.sanitize_input(body, max_length=10000)
            default_handler.handle(body, signature)

    except InvalidSignatureError:
        logger.error("Invalid LINE signature")
        return jsonify({"status": "invalid signature error"}), 200

    except Exception as e:
        logger.error("Webhook processing error",
                    error=str(e),
                    error_type=type(e).__name__)
        return jsonify({"status": "processing error"}), 200

    return 'OK'


def process_events_with_handler(body: str, event_handler: UnifiedEventHandler, line_bot_api: LineBotApi):
    """
    使用指定的 event_handler 處理事件

    Args:
        body: Webhook 請求體
        event_handler: 事件處理器
        line_bot_api: LINE Bot API 實例
    """
    try:
        webhook_data = json.loads(body)
        events = webhook_data.get('events', [])

        # #region agent log
        logger.warning("DEBUG_PROCESS_EVENTS_START", event_count=len(events))
        # #endregion

        for event_data in events:
            event_type = event_data.get('type')

            if event_type != 'message':
                logger.info("Ignoring non-message event", event_type=event_type)
                continue

            # 提取事件資訊
            message = event_data.get('message', {})
            message_type = message.get('type')
            source = event_data.get('source', {})
            user_id = source.get('userId')
            reply_token = event_data.get('replyToken')

            # #region agent log
            logger.warning("DEBUG_MESSAGE_RECEIVED", message_type=message_type, user_id=user_id[:10] + "..." if user_id else None)
            # #endregion

            if not user_id or not reply_token:
                logger.warning("Missing user_id or reply_token")
                continue

            # 處理訊息
            if message_type == 'text':
                text = message.get('text', '').strip()
                event_handler.handle_text_message(user_id, text, reply_token)

            elif message_type == 'image':
                message_id = message.get('id')
                # #region agent log
                logger.warning("DEBUG_CALLING_HANDLE_IMAGE", message_id=message_id, user_id=user_id[:10] + "...")
                # #endregion
                event_handler.handle_image_message(user_id, message_id, reply_token)
                # #region agent log
                logger.warning("DEBUG_HANDLE_IMAGE_RETURNED", message_id=message_id)
                # #endregion

            else:
                logger.info("Unsupported message type", message_type=message_type)

        logger.info("Event processing completed")

    except json.JSONDecodeError as e:
        logger.error("Failed to parse webhook JSON", error=str(e))
    except Exception as e:
        # #region agent log
        logger.error("DEBUG_PROCESS_EVENTS_ERROR", error=str(e), error_type=type(e).__name__)
        # #endregion
        logger.error("Event processing error", error=str(e))


def process_events_manually(body: str):
    """
    手動處理 LINE 事件（開發環境，向後相容）

    使用預設的事件處理器。
    """
    process_events_with_handler(body, default_event_handler, default_line_bot_api)


# ==================== LINE SDK 事件處理器（生產環境，向後相容）====================

@default_handler.add(MessageEvent, message=TextMessage)
def handle_text_message_event(event):
    """處理文字訊息事件（LINE SDK，預設模式）"""
    try:
        user_id = event.source.user_id
        text = event.message.text.strip()
        reply_token = event.reply_token

        logger.info("Processing text message via SDK",
                   user_id=user_id[:10] + "...",
                   text=text[:50])

        default_event_handler.handle_text_message(user_id, text, reply_token)

    except Exception as e:
        logger.error("SDK text message handling failed", error=str(e))


@default_handler.add(MessageEvent, message=ImageMessage)
def handle_image_message_event(event):
    """處理圖片訊息事件（LINE SDK，預設模式）"""
    try:
        user_id = event.source.user_id
        message_id = event.message.id
        reply_token = event.reply_token

        logger.info("Processing image message via SDK",
                   user_id=user_id[:10] + "...",
                   message_id=message_id)

        default_event_handler.handle_image_message(user_id, message_id, reply_token)

    except Exception as e:
        logger.error("SDK image message handling failed", error=str(e))


# ==================== 健康檢查和測試端點 ====================

@app.route("/health", methods=['GET'])
def health_check():
    """健康檢查端點 - 極簡版本，確保永遠成功"""
    # #region agent log
    print("[HEALTH] Health check called", flush=True)
    # #endregion
    
    # 極簡回應，不做任何可能失敗的操作
    try:
        # 嘗試獲取租戶數量，但失敗也不影響健康狀態
        tenant_count = 0
        try:
            tenant_service = get_tenant_service()
            stats = tenant_service.get_overall_stats()
            tenant_count = stats.get("total_tenants", 0)
        except Exception as e:
            print(f"[HEALTH] Stats fetch failed (non-critical): {e}", flush=True)
        
        return jsonify({
            "status": "healthy",
            "service": "LINE Bot Namecard System",
            "version": "3.0.0",
            "multi_tenant": True,
            "active_tenants": tenant_count,
            "timestamp": str(datetime.now())
        })
    except Exception as e:
        # 即使 jsonify 失敗，也返回純文字 200
        print(f"[HEALTH] Error in health check: {e}", flush=True)
        return "OK", 200


@app.route("/test", methods=['GET'])
def test_endpoint():
    """測試端點 - 顯示系統配置"""
    return jsonify({
        "status": "ok",
        "environment": settings.flask_env,
        "timestamp": str(datetime.now()),
        "config": {
            "line_bot_configured": bool(settings.line_channel_access_token),
            "google_ai_configured": bool(settings.google_api_key),
            "notion_configured": bool(settings.notion_api_key),
            "redis_enabled": settings.redis_enabled if hasattr(settings, 'redis_enabled') else False,
            "multi_tenant_enabled": True
        }
    })


@app.route("/debug/notion", methods=['GET'])
def debug_notion():
    """測試 Notion 連接"""
    try:
        result = default_notion_client.test_connection()
        return jsonify({
            "status": "success" if result else "failed",
            "message": "Notion connection test completed",
            "result": result
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@app.route("/debug/tenants", methods=['GET'])
def debug_tenants():
    """列出所有租戶（僅開發環境）"""
    if settings.flask_env == "production":
        return jsonify({"error": "Not available in production"}), 403

    try:
        tenant_service = get_tenant_service()
        tenants = tenant_service.list_tenants(include_inactive=True)
        return jsonify({
            "status": "ok",
            "count": len(tenants),
            "tenants": [
                {
                    "id": t.id,
                    "name": t.name,
                    "slug": t.slug,
                    "is_active": t.is_active,
                    "line_channel_id": t.line_channel_id[:10] + "..." if t.line_channel_id else None
                }
                for t in tenants
            ]
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/debug/last-destination", methods=['GET'])
def debug_last_destination():
    """
    顯示最近收到的 LINE webhook destination

    用於幫助用戶找到正確的 line_channel_id 值。
    發送訊息給 LINE Bot 後訪問此 endpoint 即可查看。
    """
    return jsonify({
        "status": "ok",
        "last_destination": _last_destination["value"],
        "received_at": _last_destination["timestamp"],
        "hint": "Use this value as line_channel_id when creating tenant" if _last_destination["value"] else "Send a message to your LINE Bot first"
    })


if __name__ == '__main__':
    # 僅用於本地測試，生產環境使用 gunicorn
    app.run(
        host=settings.app_host,
        port=settings.app_port,
        debug=settings.debug
    )
