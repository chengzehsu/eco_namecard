"""
統一的 LINE Bot 事件處理器

此模組提供統一的事件處理邏輯，消除手動解析和 SDK 處理的重複程式碼。
"""

import structlog
from typing import Optional, Callable, Union
from linebot import LineBotApi
from linebot.models import TextSendMessage, FlexSendMessage, QuickReply, QuickReplyButton, MessageAction
from linebot.exceptions import LineBotApiError

from src.namecard.core.services.user_service import user_service
from src.namecard.api.line_bot.flex_templates import (
    create_card_result_message,
    create_batch_complete_message,
)
from src.namecard.core.services.security import security_service, error_handler
from src.namecard.infrastructure.ai.card_processor import CardProcessor
from src.namecard.infrastructure.storage.notion_client import NotionClient
from src.namecard.infrastructure.storage.image_storage import get_image_storage
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
                    f"⚠️ 已達每日上限（{status.daily_usage}/50）\n"
                    f"📅 每日凌晨 04:00 重置\n"
                    f"💬 如需提高上限，請聯繫管理員"
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
                # 記錄圖片驗證失敗的錯誤（多租戶模式）
                if self.tenant_id:
                    self._record_error(user_id, error_type="image_validation")
                self._send_reply(
                    reply_token,
                    "❌ 圖片格式錯誤或檔案過大\n請上傳 10MB 以內的 JPG/PNG 圖片"
                )
                return

            # 處理圖片（現在會拋出具體異常而非返回空列表）
            logger.info("Starting image processing", user_id=user_id)
            cards = self.card_processor.process_image(image_data, user_id)

            # 上傳圖片到 ImgBB（如果有配置）
            image_url = None
            image_storage = get_image_storage()
            # #region agent log
            logger.warning("DEBUG_IMAGE_STORAGE", storage_available=image_storage is not None, cards_count=len(cards) if cards else 0)
            # #endregion
            if image_storage and cards:
                try:
                    image_url = image_storage.upload(image_data)
                    # #region agent log
                    logger.warning("DEBUG_IMAGE_UPLOAD_RESULT", image_url_exists=bool(image_url), url_preview=image_url[:50] if image_url else None)
                    # #endregion
                    if image_url:
                        # 將圖片 URL 設定到所有識別出的名片
                        for card in cards:
                            card.image_url = image_url
                except Exception as e:
                    logger.warning("Failed to upload image to ImgBB", error=str(e))
                    # 圖片上傳失敗不影響名片儲存

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

                    # 獲取並儲存用戶資訊（名稱、頭像）
                    self._save_user_profile(user_id, tenant_service)
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
            # 記錄 LINE API 錯誤（多租戶模式）
            if self.tenant_id:
                self._record_error(user_id, error_type="line_api")
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
            # 記錄 AI 識別失敗錯誤（多租戶模式）
            if self.tenant_id:
                self._record_error(user_id, error_type="ai_processing")
            self._send_error_message(reply_token, error_msg)

    def _send_help_message(self, reply_token: str) -> None:
        """發送說明訊息"""
        help_text = """🎯 名片識別系統

📱 上傳名片照片 → 自動識別存入資料庫
📦 輸入「批次」→ 批次處理模式
📊 輸入「狀態」→ 查看進度

⚡ 支援多張名片同時識別
📋 每日限制：50 張（凌晨 04:00 重置）"""

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
批次模式：{'開啟' if status.is_batch_mode else '關閉'}
📅 凌晨 04:00 重置"""

        self._send_reply(reply_token, status_text)

    def _end_batch_mode(self, user_id: str, reply_token: str) -> None:
        """結束批次模式（使用 Flex Message）"""
        batch_result = user_service.end_batch_mode(user_id)

        if not batch_result:
            self._send_reply(reply_token, "⚠️ 目前不在批次模式")
            return

        # 使用 Flex Message 卡片顯示批次結果
        flex_message = create_batch_complete_message(batch_result)
        self._send_reply(reply_token, flex_message)

        logger.info("Batch mode ended",
                   user_id=user_id,
                   total_cards=batch_result.total_cards,
                   success_rate=batch_result.success_rate * 100)

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
        """發送處理結果訊息（使用 Flex Message）"""
        if success_count > 0:
            # 成功 - 使用 Flex Message 卡片
            batch_progress = None
            if status.is_batch_mode and status.current_batch:
                batch_progress = status.current_batch.total_cards

            flex_message = create_card_result_message(
                cards=cards,
                is_batch_mode=status.is_batch_mode,
                batch_progress=batch_progress
            )
            self._send_reply(reply_token, flex_message)

        elif failed_count > 0:
            # 全部失敗 - 維持純文字錯誤訊息
            error_text = error_messages[0] if error_messages else "❌ 儲存失敗，請稍後重試"
            self._send_reply(reply_token, error_text)

    def _send_error_message(self, reply_token: str, error_msg: str) -> None:
        """發送錯誤訊息"""
        self._send_reply(reply_token, error_msg)

    def _record_error(self, user_id: str, error_type: str = "unknown") -> None:
        """
        記錄錯誤到統計（多租戶模式）

        Args:
            user_id: LINE 用戶 ID
            error_type: 錯誤類型（用於日誌追蹤）
        """
        if not self.tenant_id:
            return

        try:
            from src.namecard.core.services.tenant_service import get_tenant_service
            tenant_service = get_tenant_service()

            # 記錄租戶級別錯誤
            tenant_service.record_usage(self.tenant_id, errors=1)

            # 記錄用戶級別錯誤
            tenant_service.record_user_usage(
                tenant_id=self.tenant_id,
                line_user_id=user_id,
                errors=1
            )

            logger.info("Error recorded to stats",
                       tenant_id=self.tenant_id,
                       user_id=user_id,
                       error_type=error_type)
        except Exception as e:
            logger.warning("Failed to record error stats", error=str(e))

    def _save_user_profile(self, user_id: str, tenant_service=None) -> None:
        """
        獲取並儲存 LINE 用戶資訊（名稱、頭像）

        Args:
            user_id: LINE 用戶 ID
            tenant_service: TenantService 實例（可選，避免重複 import）
        """
        if not self.tenant_id:
            return

        try:
            # 獲取用戶 profile
            profile = self.line_bot_api.get_profile(user_id)
            display_name = profile.display_name
            picture_url = profile.picture_url

            # 取得 tenant_service
            if tenant_service is None:
                from src.namecard.core.services.tenant_service import get_tenant_service
                tenant_service = get_tenant_service()

            # 儲存用戶資訊
            tenant_service.save_line_user(
                tenant_id=self.tenant_id,
                line_user_id=user_id,
                display_name=display_name,
                picture_url=picture_url
            )

            logger.debug("User profile saved",
                        tenant_id=self.tenant_id,
                        user_id=user_id,
                        display_name=display_name)
        except LineBotApiError as e:
            # 某些情況下無法獲取用戶 profile（如用戶未加好友）
            logger.debug("Could not get user profile", user_id=user_id, error=str(e))
        except Exception as e:
            logger.warning("Failed to save user profile", user_id=user_id, error=str(e))

    def _send_reply(
        self,
        reply_token: str,
        message: Union[str, FlexSendMessage],
        quick_reply: Optional[QuickReply] = None
    ) -> None:
        """
        統一的回覆發送方法

        Args:
            reply_token: 回覆 token
            message: 訊息內容（字串或 FlexSendMessage）
            quick_reply: 快速回覆選項（可選）
        """
        try:
            if isinstance(message, str):
                # 純文字訊息
                send_message = TextSendMessage(text=message, quick_reply=quick_reply)
            elif isinstance(message, FlexSendMessage):
                # Flex Message - 附加 quick_reply
                message.quick_reply = quick_reply
                send_message = message
            else:
                raise ValueError(f"不支援的訊息類型: {type(message)}")

            self.line_bot_api.reply_message(reply_token, send_message)
        except LineBotApiError as e:
            logger.error("Failed to send reply",
                        error=str(e),
                        reply_token=reply_token[:20] + "...")
            raise
