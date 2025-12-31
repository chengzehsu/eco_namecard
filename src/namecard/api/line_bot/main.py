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

app = Flask(__name__)

# ==================== 預設單租戶服務 (向後相容) ====================

# 初始化預設 LINE Bot (使用全域設定)
default_line_bot_api = LineBotApi(settings.line_channel_access_token)
default_handler = WebhookHandler(settings.line_channel_secret)

# 初始化預設服務
default_card_processor = CardProcessor()
default_notion_client = NotionClient()

# 預設事件處理器
default_event_handler = UnifiedEventHandler(
    line_bot_api=default_line_bot_api,
    card_processor=default_card_processor,
    notion_client=default_notion_client
)


# ==================== 多租戶工具函數 ====================

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
            logger.info("=== LINE WEBHOOK DESTINATION ===",
                       destination=destination,
                       hint="Use this value as line_channel_id when creating tenant")
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
        event_handler = get_event_handler_for_tenant(context)

        # 記錄使用統計
        tenant_service = get_tenant_service()
        tenant_service.record_usage(context.tenant_id, api_calls=1)

        # 處理事件
        process_events_with_handler(body, event_handler, context.line_bot_api)

    except Exception as e:
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

        logger.info("Processing events", event_count=len(events))

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

            if not user_id or not reply_token:
                logger.warning("Missing user_id or reply_token")
                continue

            # 處理訊息
            if message_type == 'text':
                text = message.get('text', '').strip()
                event_handler.handle_text_message(user_id, text, reply_token)

            elif message_type == 'image':
                message_id = message.get('id')
                event_handler.handle_image_message(user_id, message_id, reply_token)

            else:
                logger.info("Unsupported message type", message_type=message_type)

        logger.info("Event processing completed")

    except json.JSONDecodeError as e:
        logger.error("Failed to parse webhook JSON", error=str(e))
    except Exception as e:
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
    """健康檢查端點"""
    try:
        tenant_service = get_tenant_service()
        stats = tenant_service.get_overall_stats()
        tenant_count = stats.get("total_tenants", 0)
    except Exception:
        tenant_count = 0

    return jsonify({
        "status": "healthy",
        "service": "LINE Bot Namecard System",
        "version": "3.0.0",
        "multi_tenant": True,
        "active_tenants": tenant_count,
        "timestamp": str(datetime.now())
    })


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


if __name__ == '__main__':
    # 僅用於本地測試，生產環境使用 gunicorn
    app.run(
        host=settings.app_host,
        port=settings.app_port,
        debug=settings.debug
    )
