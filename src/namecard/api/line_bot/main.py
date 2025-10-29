"""
LINE Bot 名片識別系統 - 主應用（重構版）

使用統一的事件處理器，消除重複程式碼，提升可維護性。
"""

from flask import Flask, request, abort, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, ImageMessage
import structlog
import os
import sys
import json
from datetime import datetime

# 添加項目根目錄到 Python 路徑
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../..'))

from simple_config import settings
from src.namecard.core.services.security import security_service
from src.namecard.infrastructure.ai.card_processor import CardProcessor
from src.namecard.infrastructure.storage.notion_client import NotionClient
from src.namecard.api.line_bot.event_handler import UnifiedEventHandler

logger = structlog.get_logger()

app = Flask(__name__)

# 初始化 LINE Bot
line_bot_api = LineBotApi(settings.line_channel_access_token)
handler = WebhookHandler(settings.line_channel_secret)

# 初始化服務
card_processor = CardProcessor()
notion_client = NotionClient()

# 創建統一的事件處理器
event_handler = UnifiedEventHandler(
    line_bot_api=line_bot_api,
    card_processor=card_processor,
    notion_client=notion_client
)


@app.route("/callback", methods=['POST'])
def callback():
    """
    LINE Webhook 回調端點

    處理來自 LINE 平台的所有事件，包括訊息、圖片等。
    支援開發/生產環境的不同處理方式。
    """
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)

    # 基本輸入驗證
    if not signature or not body:
        logger.warning("Missing signature or body in webhook request")
        return jsonify({"status": "missing signature or body"}), 200

    # 驗證簽名（生產環境）
    if settings.flask_env == "production":
        if not security_service.validate_line_signature(
            body, signature, settings.line_channel_secret
        ):
            logger.error("LINE webhook signature validation failed",
                        signature_prefix=signature[:20] + "...")
            security_service.log_security_event(
                "invalid_webhook_signature",
                "unknown",
                {"signature": signature[:20] + "..."}
            )
            return jsonify({"status": "invalid signature"}), 200
    else:
        logger.info("Signature validation skipped in non-production environment")

    # 檢查請求大小（1MB 限制）
    if len(body) > 1024 * 1024:
        logger.warning("Webhook request too large", size=len(body))
        return jsonify({"status": "request too large"}), 200

    try:
        # 解析事件並處理
        if settings.flask_env != "production":
            # 開發環境：手動解析（跳過 LINE SDK 簽名驗證）
            logger.info("Using manual event processing")
            process_events_manually(body)
        else:
            # 生產環境：使用 LINE SDK
            logger.info("Using LINE SDK processing")
            body = security_service.sanitize_input(body, max_length=10000)
            handler.handle(body, signature)

    except InvalidSignatureError:
        logger.error("Invalid LINE signature")
        return jsonify({"status": "invalid signature error"}), 200

    except Exception as e:
        logger.error("Webhook processing error",
                    error=str(e),
                    error_type=type(e).__name__)
        return jsonify({"status": "processing error"}), 200

    return 'OK'


def process_events_manually(body: str):
    """
    手動處理 LINE 事件（開發環境）

    解析 webhook body 並使用統一的事件處理器處理每個事件。

    Args:
        body: Webhook 請求體（JSON 字符串）
    """
    try:
        webhook_data = json.loads(body)
        events = webhook_data.get('events', [])

        logger.info("Processing events manually", event_count=len(events))

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

            # 使用統一處理器處理訊息
            if message_type == 'text':
                text = message.get('text', '').strip()
                event_handler.handle_text_message(user_id, text, reply_token)

            elif message_type == 'image':
                message_id = message.get('id')
                event_handler.handle_image_message(user_id, message_id, reply_token)

            else:
                logger.info("Unsupported message type", message_type=message_type)

        logger.info("Manual event processing completed")

    except json.JSONDecodeError as e:
        logger.error("Failed to parse webhook JSON", error=str(e))
    except Exception as e:
        logger.error("Manual event processing error", error=str(e))


# LINE SDK 事件處理器（生產環境）

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message_event(event):
    """處理文字訊息事件（LINE SDK）"""
    try:
        user_id = event.source.user_id
        text = event.message.text.strip()
        reply_token = event.reply_token

        logger.info("Processing text message via SDK",
                   user_id=user_id[:10] + "...",
                   text=text[:50])

        # 使用統一處理器
        event_handler.handle_text_message(user_id, text, reply_token)

    except Exception as e:
        logger.error("SDK text message handling failed", error=str(e))


@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message_event(event):
    """處理圖片訊息事件（LINE SDK）"""
    try:
        user_id = event.source.user_id
        message_id = event.message.id
        reply_token = event.reply_token

        logger.info("Processing image message via SDK",
                   user_id=user_id[:10] + "...",
                   message_id=message_id)

        # 使用統一處理器
        event_handler.handle_image_message(user_id, message_id, reply_token)

    except Exception as e:
        logger.error("SDK image message handling failed", error=str(e))


# 健康檢查和測試端點

@app.route("/health", methods=['GET'])
def health_check():
    """健康檢查端點"""
    return jsonify({
        "status": "healthy",
        "service": "LINE Bot Namecard System",
        "version": "2.0.0",
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
            "redis_enabled": settings.redis_enabled if hasattr(settings, 'redis_enabled') else False
        }
    })


@app.route("/debug/notion", methods=['GET'])
def debug_notion():
    """測試 Notion 連接"""
    try:
        result = notion_client.test_connection()
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


if __name__ == '__main__':
    # 僅用於本地測試，生產環境使用 gunicorn
    app.run(
        host=settings.app_host,
        port=settings.app_port,
        debug=settings.debug
    )
