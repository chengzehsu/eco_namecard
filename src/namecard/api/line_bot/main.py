from flask import Flask, request, abort, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import (
    MessageEvent, TextMessage, ImageMessage, TextSendMessage,
    FlexSendMessage, QuickReply, QuickReplyButton, MessageAction
)
import structlog
import traceback
from typing import Optional
import os
import sys
from datetime import datetime

# 添加項目根目錄到 Python 路徑
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../..'))

from simple_config import settings
from src.namecard.core.services.user_service import user_service
from src.namecard.core.services.security import security_service
from src.namecard.infrastructure.ai.card_processor import CardProcessor
from src.namecard.infrastructure.storage.notion_client import NotionClient

logger = structlog.get_logger()

app = Flask(__name__)

# 初始化 LINE Bot
line_bot_api = LineBotApi(settings.line_channel_access_token)
handler = WebhookHandler(settings.line_channel_secret)

# 初始化服務
card_processor = CardProcessor()
notion_client = NotionClient()


def create_help_message() -> TextSendMessage:
    """建立說明訊息"""
    help_text = """🎯 名片識別系統

📱 上傳名片照片 → 自動識別存入資料庫
📦 輸入「批次」→ 批次處理模式
📊 輸入「狀態」→ 查看進度

⚡ 支援多張名片同時識別
📋 每日限制：50 張"""

    return TextSendMessage(
        text=help_text,
        quick_reply=QuickReply(items=[
            QuickReplyButton(action=MessageAction(label="開始批次", text="批次")),
            QuickReplyButton(action=MessageAction(label="查看狀態", text="狀態")),
        ])
    )


def create_batch_summary_message(batch_result) -> TextSendMessage:
    """建立批次處理總結訊息"""
    duration = batch_result.completed_at - batch_result.started_at
    success_rate = batch_result.success_rate * 100
    
    summary_text = f"""📊 批次完成！

總計：{batch_result.total_cards} 張
成功：{batch_result.successful_cards} 張 ({success_rate:.0f}%)
時間：{duration.seconds // 60}:{duration.seconds % 60:02d}"""
    
    if batch_result.errors:
        summary_text += f"\n\n⚠️ " + batch_result.errors[0][:30] + "..."
    
    return TextSendMessage(text=summary_text)


@app.route("/callback", methods=['POST'])
def callback():
    """LINE Webhook 回調端點"""
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    
    # 基本輸入驗證
    if not signature or not body:
        logger.warning("Missing signature or body in webhook request")
        abort(400)
    
    # 使用 SecurityService 驗證簽名 (臨時跳過用於測試)
    if settings.flask_env == "production" and not security_service.validate_line_signature(body, signature, settings.line_channel_secret):
        logger.error("LINE webhook signature validation failed", 
                    signature_prefix=signature[:20] + "...",
                    body_length=len(body),
                    channel_secret_length=len(settings.line_channel_secret) if settings.line_channel_secret else 0)
        security_service.log_security_event(
            "invalid_webhook_signature",
            "unknown",
            {"signature": signature[:20] + "...", "body_length": len(body)}
        )
        abort(400)
    elif settings.flask_env != "production":
        logger.warning("Signature validation skipped in non-production environment")
    
    # 檢查請求大小
    if len(body) > 1024 * 1024:  # 1MB 限制
        logger.warning("Webhook request too large", size=len(body))
        abort(413)
    
    try:
        # 清理輸入
        body = security_service.sanitize_input(body, max_length=10000)
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("Invalid LINE signature")
        abort(400)
    except Exception as e:
        logger.error("Webhook processing error", error=str(e))
        # 不要 abort，返回 200 避免 LINE 重複發送
        return 'Error processed', 200
    
    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    """處理文字訊息"""
    user_id = event.source.user_id
    text = event.message.text.strip().lower()
    
    try:
        # 檢查速率限制
        if not user_service.check_rate_limit(user_id, settings.rate_limit_per_user):
            reply_message = TextSendMessage(
                text=f"⚠️ 今日使用量已達上限 ({settings.rate_limit_per_user} 張)\n請明天再試"
            )
            line_bot_api.reply_message(event.reply_token, reply_message)
            return
        
        if text in ['help', '說明', '幫助']:
            reply_message = create_help_message()
        
        elif text in ['批次', 'batch']:
            batch_result = user_service.start_batch_mode(user_id)
            reply_message = TextSendMessage(
                text="📦 批次模式啟動\n請上傳名片，完成後輸入「結束批次」",
                quick_reply=QuickReply(items=[
                    QuickReplyButton(action=MessageAction(label="結束批次", text="結束批次")),
                    QuickReplyButton(action=MessageAction(label="查看狀態", text="狀態")),
                ])
            )
        
        elif text in ['結束批次', 'end batch', '結束']:
            batch_result = user_service.end_batch_mode(user_id)
            if batch_result:
                reply_message = create_batch_summary_message(batch_result)
            else:
                reply_message = TextSendMessage(text="❌ 目前沒有進行中的批次處理")
        
        elif text in ['狀態', 'status', '進度']:
            status_text = user_service.get_batch_status(user_id)
            if status_text:
                reply_message = TextSendMessage(text=status_text)
            else:
                user_status = user_service.get_user_status(user_id)
                reply_message = TextSendMessage(
                    text=f"📊 今日：{user_status.daily_usage}/{settings.rate_limit_per_user} 張\n非批次模式"
                )
        
        else:
            reply_message = TextSendMessage(
                text="❓ 不理解的指令\n請輸入「help」查看使用說明，或直接上傳名片照片"
            )
        
        line_bot_api.reply_message(event.reply_token, reply_message)
        
    except Exception as e:
        logger.error("Text message error", user_id=user_id, error=str(e))
        try:
            error_message = TextSendMessage(text="⚠️ 系統暫時無法處理，請稍後再試")
            line_bot_api.reply_message(event.reply_token, error_message)
        except LineBotApiError:
            # reply_token 已被使用，改用 push_message
            line_bot_api.push_message(user_id, error_message)


@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    """處理圖片訊息 - 名片識別"""
    user_id = event.source.user_id
    message_id = event.message.id
    
    try:
        # 檢查速率限制
        if not user_service.check_rate_limit(user_id, settings.rate_limit_per_user):
            reply_message = TextSendMessage(
                text=f"⚠️ 今日使用量已達上限 ({settings.rate_limit_per_user} 張)\n請明天再試"
            )
            line_bot_api.reply_message(event.reply_token, reply_message)
            return
        
        # 下載圖片
        message_content = line_bot_api.get_message_content(message_id)
        image_data = b''.join(message_content.iter_content())
        
        # 使用 SecurityService 驗證圖片
        if not security_service.validate_image_data(image_data, settings.max_image_size):
            logger.warning("Invalid image data received", 
                         user_id=user_id, 
                         size=len(image_data),
                         message_id=message_id)
            
            # 記錄安全事件
            security_service.log_security_event(
                "invalid_image_upload",
                user_id,
                {
                    "image_size": len(image_data),
                    "max_allowed": settings.max_image_size,
                    "message_id": message_id
                }
            )
            
            reply_message = TextSendMessage(
                text=f"⚠️ 圖片檔案無效或過大 (>{settings.max_image_size // 1024 // 1024}MB)\n請使用有效的圖片格式並壓縮後重新上傳"
            )
            line_bot_api.reply_message(event.reply_token, reply_message)
            return
        
        # 使用 AI 處理名片
        cards = card_processor.process_image(image_data, user_id)
        
        if not cards:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="❌ 無法識別名片內容\n請確認圖片清晰且包含名片")
            )
            return
        
        # 增加使用次數
        user_service.increment_usage(user_id)
        
        # 處理識別到的名片
        success_count = 0
        results = []
        
        for card in cards:
            try:
                # 存入 Notion
                notion_url = notion_client.save_business_card(card)
                if notion_url:
                    card.processed = True
                    success_count += 1
                    results.append(f"✅ {card.name or '未知姓名'} - {card.company or '未知公司'}")
                else:
                    results.append(f"❌ 儲存失敗: {card.name or '未知姓名'}")
                
                # 如果在批次模式，加入批次
                user_service.add_card_to_batch(user_id, card)
                
            except Exception as e:
                logger.error("Card processing error", error=str(e))
                results.append(f"❌ 處理錯誤: {str(e)[:50]}")
        
        # 建立回應訊息
        if success_count > 0:
            response_text = f"✅ 成功 {success_count}/{len(cards)} 張\n\n"
            response_text += "\n".join(results[:3])  # 最多顯示 3 個結果
            
            if len(cards) > 1:
                response_text += f"\n\n📊 共 {len(cards)} 張名片"
        else:
            response_text = "❌ 處理失敗\n" + "\n".join(results[:2])
        
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=response_text))
        
    except Exception as e:
        logger.error("Image processing error", user_id=user_id, error=str(e))
        try:
            error_message = TextSendMessage(text="⚠️ 處理失敗，請重試")
            line_bot_api.reply_message(event.reply_token, error_message)
        except LineBotApiError:
            # reply_token 已被使用，改用 push_message
            line_bot_api.push_message(user_id, error_message)


@app.route('/health', methods=['GET'])
def health_check():
    """健康檢查端點"""
    return jsonify({
        'status': 'healthy',
        'service': 'LINE Bot 名片識別系統',
        'version': '1.0.0',
        'timestamp': str(datetime.now())
    })


@app.route('/test', methods=['GET'])
def test_endpoint():
    """測試端點"""
    return jsonify({
        'message': 'LINE Bot 服務運行正常',
        'config': {
            'rate_limit': settings.rate_limit_per_user,
            'batch_limit': settings.batch_size_limit,
            'max_image_size': f"{settings.max_image_size // 1024 // 1024}MB",
            'flask_env': settings.flask_env,
            'line_channel_configured': bool(settings.line_channel_access_token),
            'line_secret_configured': bool(settings.line_channel_secret)
        }
    })

@app.route('/debug/webhook', methods=['POST'])
def debug_webhook():
    """除錯 webhook 端點"""
    logger.info("Debug webhook called", 
                headers=dict(request.headers),
                body_length=len(request.get_data()),
                method=request.method)
    return jsonify({
        'status': 'received',
        'headers': dict(request.headers),
        'body_length': len(request.get_data())
    })


if __name__ == "__main__":
    # 設置日誌
    structlog.configure(
        processors=[
            structlog.dev.ConsoleRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(30),  # INFO level
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    app.run(
        host=settings.app_host,
        port=settings.app_port,
        debug=settings.debug
    )