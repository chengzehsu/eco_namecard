"""
統一的 LINE Bot 事件處理器

此模組提供統一的事件處理邏輯，消除手動解析和 SDK 處理的重複程式碼。
"""

import structlog
from typing import Optional, Callable
from linebot import LineBotApi
from linebot.models import TextSendMessage, QuickReply, QuickReplyButton, MessageAction
from linebot.exceptions import LineBotApiError

from src.namecard.core.services.user_service import user_service
from src.namecard.core.services.security import security_service, error_handler
from src.namecard.infrastructure.ai.card_processor import CardProcessor
from src.namecard.infrastructure.storage.notion_client import NotionClient
from src.namecard.core.models.card import BusinessCard

logger = structlog.get_logger()


class UnifiedEventHandler:
    """統一的事件處理器，處理所有 LINE Bot 訊息

    支援多租戶模式：可選的 tenant_id 參數用於追蹤和隔離。
    """

    def __init__(
        self,
        line_bot_api: LineBotApi,
        card_processor: CardProcessor,
        notion_client: NotionClient,
        tenant_id: Optional[str] = None
    ):
        """
        初始化事件處理器

        Args:
            line_bot_api: LINE Bot API 實例
            card_processor: 名片處理器
            notion_client: Notion 客戶端
            tenant_id: 租戶 ID (多租戶模式)，預設為 None (單租戶)
        """
        self.line_bot_api = line_bot_api
        self.card_processor = card_processor
        self.notion_client = notion_client
        self.tenant_id = tenant_id

    def handle_text_message(
        self,
        user_id: str,
        text: str,
        reply_token: str
    ) -> None:
        """
        處理文字訊息

        Args:
            user_id: LINE 用戶 ID
            text: 訊息內容
            reply_token: 回覆 token
        """
        try:
            text = text.strip()
            logger.info("Processing text message",
                       user_id=user_id,
                       text=text[:50])

            # 命令處理
            if text in ['help', '說明', '幫助']:
                self._send_help_message(reply_token)

            elif text in ['批次', 'batch', '批量']:
                self._start_batch_mode(user_id, reply_token)

            elif text in ['狀態', 'status', '進度']:
                self._show_status(user_id, reply_token)

            elif text in ['結束批次', 'end batch', '完成批次']:
                self._end_batch_mode(user_id, reply_token)

            else:
                # 未知命令
                self._send_unknown_command(reply_token)

        except Exception as e:
            logger.error("Text message handling failed",
                        error=str(e),
                        user_id=user_id)
            self._send_error_message(reply_token, "處理訊息時發生錯誤")

    def handle_image_message(
        self,
        user_id: str,
        message_id: str,
        reply_token: str
    ) -> None:
        """
        處理圖片訊息

        Args:
            user_id: LINE 用戶 ID
            message_id: 訊息 ID
            reply_token: 回覆 token
        """
        try:
            logger.info("Processing image message",
                       user_id=user_id,
                       message_id=message_id)

            # 檢查用戶是否被封鎖
            if security_service.is_user_blocked(user_id):
                self._send_reply(
                    reply_token,
                    "⛔ 您已被暫時封鎖，請稍後再試"
                )
                return

            # 檢查速率限制
            status = user_service.get_user_status(user_id)
            if status.daily_usage >= 50:
                self._send_reply(
                    reply_token,
                    f"⚠️ 已達每日上限（{status.daily_usage}/50）\n請明天再試"
                )
                return

            # 下載圖片
            # #region agent log
            logger.info("DEBUG_BEFORE_GET_CONTENT", message_id=message_id, user_id=user_id, tenant_id=self.tenant_id)
            # #endregion
            message_content = self.line_bot_api.get_message_content(message_id)
            image_data = message_content.content

            # 驗證圖片
            if not security_service.validate_image_data(image_data):
                self._send_reply(
                    reply_token,
                    "❌ 圖片格式錯誤或檔案過大\n請上傳 10MB 以內的 JPG/PNG 圖片"
                )
                return

            # 處理圖片（現在會拋出具體異常而非返回空列表）
            logger.info("Starting image processing", user_id=user_id)
            cards = self.card_processor.process_image(image_data, user_id)

            # 儲存名片
            success_count = 0
            failed_count = 0
            error_messages = []

            for card in cards:
                try:
                    # 儲存到 Notion
                    saved = self.notion_client.save_business_card(card)

                    if saved:
                        success_count += 1
                        # 標記為已處理
                        card.processed = True

                        # 如果是批次模式，加入批次
                        if status.is_batch_mode:
                            user_service.add_card_to_batch(user_id, card)
                    else:
                        failed_count += 1
                        card.processed = False

                except Exception as e:
                    failed_count += 1
                    card.processed = False
                    error_msg = error_handler.handle_notion_error(e, user_id)
                    error_messages.append(error_msg)
                    logger.error("Failed to save card",
                               error=str(e),
                               user_id=user_id)

            # 增加使用計數
            user_service.increment_usage(user_id)

            # 記錄租戶和用戶使用統計（多租戶模式）
            if self.tenant_id:
                try:
                    from src.namecard.core.services.tenant_service import get_tenant_service
                    tenant_service = get_tenant_service()

                    # 記錄租戶級別統計
                    tenant_service.record_usage(
                        self.tenant_id,
                        cards_processed=len(cards),
                        cards_saved=success_count,
                        errors=failed_count
                    )

                    # 記錄用戶級別統計
                    tenant_service.record_user_usage(
                        tenant_id=self.tenant_id,
                        line_user_id=user_id,
                        cards_processed=len(cards),
                        cards_saved=success_count,
                        errors=failed_count
                    )
                except Exception as e:
                    logger.warning("Failed to record usage stats", error=str(e))

            # 生成回應訊息
            self._send_processing_result(
                reply_token,
                cards,
                success_count,
                failed_count,
                error_messages,
                status
            )

        except LineBotApiError as e:
            # #region agent log
            logger.info("DEBUG_LINE_API_ERROR", error_str=str(e)[:200], status_code=getattr(e,'status_code',None), message_id=message_id, user_id=user_id, tenant_id=self.tenant_id)
            # #endregion
            logger.error("LINE API error in image processing",
                        error=str(e),
                        user_id=user_id)
            error_handler.handle_line_error(e, user_id)
            # 嘗試用 push message 發送錯誤訊息
            try:
                self.line_bot_api.push_message(
                    user_id,
                    TextSendMessage(text="❌ 圖片下載失敗，請重試")
                )
            except:
                pass

        except Exception as e:
            logger.error("Image processing failed",
                        error=str(e),
                        user_id=user_id)
            error_msg = error_handler.handle_ai_error(e, user_id)
            self._send_error_message(reply_token, error_msg)

    def _send_help_message(self, reply_token: str) -> None:
        """發送說明訊息"""
        help_text = """🎯 名片識別系統

📱 上傳名片照片 → 自動識別存入資料庫
📦 輸入「批次」→ 批次處理模式
📊 輸入「狀態」→ 查看進度

⚡ 支援多張名片同時識別
📋 每日限制：50 張"""

        self._send_reply(
            reply_token,
            help_text,
            quick_reply=QuickReply(items=[
                QuickReplyButton(action=MessageAction(label="開始批次", text="批次")),
                QuickReplyButton(action=MessageAction(label="查看狀態", text="狀態")),
            ])
        )

    def _start_batch_mode(self, user_id: str, reply_token: str) -> None:
        """開始批次模式"""
        batch_result = user_service.start_batch_mode(user_id)

        self._send_reply(
            reply_token,
            "📦 批次模式已啟動\n\n請連續上傳多張名片照片\n完成後輸入「結束批次」",
            quick_reply=QuickReply(items=[
                QuickReplyButton(action=MessageAction(label="結束批次", text="結束批次")),
                QuickReplyButton(action=MessageAction(label="查看進度", text="狀態")),
            ])
        )

        logger.info("Batch mode started", user_id=user_id)

    def _show_status(self, user_id: str, reply_token: str) -> None:
        """顯示狀態"""
        status = user_service.get_user_status(user_id)

        # 批次狀態
        if status.is_batch_mode:
            batch_status = user_service.get_batch_status(user_id)
            if batch_status:
                self._send_reply(reply_token, batch_status)
                return

        # 一般狀態
        status_text = f"""📊 使用狀態

今日使用：{status.daily_usage} / 50 張
批次模式：{'開啟' if status.is_batch_mode else '關閉'}"""

        self._send_reply(reply_token, status_text)

    def _end_batch_mode(self, user_id: str, reply_token: str) -> None:
        """結束批次模式"""
        batch_result = user_service.end_batch_mode(user_id)

        if not batch_result:
            self._send_reply(reply_token, "⚠️ 目前不在批次模式")
            return

        # 生成總結
        duration = batch_result.completed_at - batch_result.started_at
        success_rate = batch_result.success_rate * 100

        summary_text = f"""📊 批次完成！

總計：{batch_result.total_cards} 張
成功：{batch_result.successful_cards} 張 ({success_rate:.0f}%)
失敗：{batch_result.failed_cards} 張
時間：{duration.seconds // 60}:{duration.seconds % 60:02d}"""

        if batch_result.errors:
            summary_text += f"\n\n⚠️ {batch_result.errors[0][:50]}"

        self._send_reply(reply_token, summary_text)

        logger.info("Batch mode ended",
                   user_id=user_id,
                   total_cards=batch_result.total_cards,
                   success_rate=success_rate)

    def _send_unknown_command(self, reply_token: str) -> None:
        """發送未知命令訊息"""
        self._send_reply(
            reply_token,
            "❓ 不認識的指令\n輸入「幫助」查看使用說明",
            quick_reply=QuickReply(items=[
                QuickReplyButton(action=MessageAction(label="查看說明", text="幫助")),
            ])
        )

    def _send_processing_result(
        self,
        reply_token: str,
        cards: list,
        success_count: int,
        failed_count: int,
        error_messages: list,
        status
    ) -> None:
        """發送處理結果訊息"""
        total = len(cards)

        if success_count > 0:
            # 成功訊息
            if total == 1:
                card = cards[0]
                result_text = f"""✅ 名片識別成功！

姓名：{card.name or '未識別'}
公司：{card.company or '未識別'}
職稱：{card.title or '未識別'}
電話：{card.phone or '未識別'}
Email：{card.email or '未識別'}"""
            else:
                result_text = f"""✅ 識別完成！

成功：{success_count} 張
失敗：{failed_count} 張
總計：{total} 張"""

            # 批次模式提示
            if status.is_batch_mode:
                batch = status.current_batch
                result_text += f"\n\n📦 批次進度：{batch.total_cards} 張"

            self._send_reply(reply_token, result_text)

        elif failed_count > 0:
            # 全部失敗
            error_text = error_messages[0] if error_messages else "❌ 儲存失敗，請稍後重試"
            self._send_reply(reply_token, error_text)

    def _send_error_message(self, reply_token: str, error_msg: str) -> None:
        """發送錯誤訊息"""
        self._send_reply(reply_token, error_msg)

    def _send_reply(
        self,
        reply_token: str,
        text: str,
        quick_reply: Optional[QuickReply] = None
    ) -> None:
        """
        統一的回覆發送方法

        Args:
            reply_token: 回覆 token
            text: 訊息內容
            quick_reply: 快速回覆選項（可選）
        """
        try:
            message = TextSendMessage(text=text, quick_reply=quick_reply)
            self.line_bot_api.reply_message(reply_token, message)
        except LineBotApiError as e:
            logger.error("Failed to send reply",
                        error=str(e),
                        reply_token=reply_token[:20] + "...")
            raise
