"""
統一的 LINE Bot 事件處理器

此模組提供統一的事件處理邏輯，消除手動解析和 SDK 處理的重複程式碼。
"""

import structlog
from typing import Optional, Union, TYPE_CHECKING

# LINE SDK v3 imports
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage,
    FlexMessage,
    FlexContainer,
    QuickReply,
    QuickReplyItem,
    MessageAction,
)
from linebot.v3.messaging.rest import ApiException as MessagingApiException
# 也導入舊版異常（用於向後相容和測試）
from linebot.v3.exceptions import InvalidSignatureError
try:
    from linebot.exceptions import LineBotApiError
except ImportError:
    LineBotApiError = MessagingApiException  # fallback

from simple_config import settings
from src.namecard.core.services.user_service import user_service
from src.namecard.core.services.security import security_service, error_handler
from src.namecard.infrastructure.ai.card_processor import CardProcessor
from src.namecard.infrastructure.storage.notion_client import NotionClient
from src.namecard.infrastructure.storage.image_upload_worker import (
    submit_image_upload,
    get_failed_tasks,
    retry_all_failed_tasks,
    clear_failed_tasks,
)
from src.namecard.api.line_bot.flex_templates import (
    create_card_result_message,
    create_batch_complete_message,
    create_progress_message,
    create_error_message,
)

logger = structlog.get_logger()


class UnifiedEventHandler:
    """統一的事件處理器，處理所有 LINE Bot 訊息

    支援多租戶模式：可選的 tenant_id 參數用於追蹤和隔離。
    已遷移至 LINE SDK v3 API。
    """

    def __init__(
        self,
        line_bot_api,  # v3 Configuration 物件或 access_token 字串
        card_processor: CardProcessor,
        notion_client: NotionClient,
        tenant_id: Optional[str] = None,
        channel_access_token: Optional[str] = None,
    ):
        """
        初始化事件處理器 (LINE SDK v3)

        Args:
            line_bot_api: v3 Configuration 物件，或用於測試的 Mock 物件
            card_processor: 名片處理器
            notion_client: Notion 客戶端
            tenant_id: 租戶 ID (多租戶模式)
            channel_access_token: Channel Access Token (替代 line_bot_api 使用)
        """
        # 優先使用 channel_access_token 創建 Configuration
        if channel_access_token:
            self.configuration = Configuration(access_token=channel_access_token)
        elif isinstance(line_bot_api, Configuration):
            self.configuration = line_bot_api
        else:
            # 測試模式：直接儲存 mock 物件
            self._mock_api = line_bot_api
            self.configuration = None
        
        self.card_processor = card_processor
        self.notion_client = notion_client
        self.tenant_id = tenant_id

    def handle_text_message(self, user_id: str, text: str, reply_token: str) -> None:
        """
        處理文字訊息

        Args:
            user_id: LINE 用戶 ID
            text: 訊息內容
            reply_token: 回覆 token
        """
        try:
            text = text.strip()
            logger.info("Processing text message", user_id=user_id, text=text[:50])

            # 獲取並儲存用戶資訊（頭像、暱稱）
            if self.tenant_id:
                self._save_user_profile(user_id)

            # 命令處理
            if text in ["help", "說明", "幫助"]:
                self._send_help_message(reply_token)

            elif text in ["批次", "batch", "批量"]:
                self._start_batch_mode(user_id, reply_token)

            elif text in ["狀態", "status", "進度"]:
                self._show_status(user_id, reply_token)

            elif text in ["結束批次", "end batch", "完成批次"]:
                self._end_batch_mode(user_id, reply_token)

            elif text in ["重試", "retry", "重新上傳"]:
                self._retry_failed_uploads(user_id, reply_token)

            elif text in ["清除失敗", "clear failed"]:
                self._clear_failed_uploads(user_id, reply_token)

            else:
                # 未知命令
                self._send_unknown_command(reply_token)

        except Exception as e:
            logger.error("Text message handling failed", error=str(e), user_id=user_id)
            self._send_error_message(reply_token, "處理訊息時發生錯誤")

    def handle_image_message(self, user_id: str, message_id: str, reply_token: str) -> None:
        """
        處理圖片訊息

        Args:
            user_id: LINE 用戶 ID
            message_id: 訊息 ID
            reply_token: 回覆 token
        """
        try:
            logger.warning("DEBUG_HANDLE_IMAGE_START", user_id=user_id[:10] + "...", message_id=message_id, tenant_id=self.tenant_id)

            # 檢查速率限制（向後相容的每日限制）
            status = user_service.get_user_status(user_id)
            logger.warning("DEBUG_USER_STATUS", daily_usage=status.daily_usage, is_batch_mode=status.is_batch_mode)
            
            # 如果有租戶 ID，使用 QuotaService 進行配額檢查
            if self.tenant_id:
                try:
                    from src.namecard.core.services.quota_service import get_quota_service
                    from datetime import datetime
                    quota_service = get_quota_service()
                    
                    # 檢查掃描配額
                    quota_check = quota_service.check_scan_quota(self.tenant_id)
                    logger.warning("DEBUG_QUOTA_CHECK", has_quota=quota_check.get("has_quota"), remaining=quota_check.get("remaining_scans"), total=quota_check.get("total_quota"), current_month=quota_check.get("current_month_scans"))
                    if not quota_check["has_quota"]:
                        logger.warning("DEBUG_QUOTA_EXHAUSTED", tenant_id=self.tenant_id, used=quota_check.get("current_month_scans"), total=quota_check.get("total_quota"))
                        
                        # 根據重置週期計算下次重置時間
                        from datetime import timedelta
                        from src.namecard.core.services.tenant_service import get_tenant_service
                        tenant_service = get_tenant_service()
                        tenant = tenant_service.get_tenant_by_id(self.tenant_id)
                        
                        now = datetime.now()
                        reset_cycle = getattr(tenant, 'quota_reset_cycle', 'monthly') or 'monthly'
                        reset_day = getattr(tenant, 'quota_reset_day', 1) or 1
                        
                        if reset_cycle == "daily":
                            reset_msg = "明日凌晨"
                            days_until = 1
                        elif reset_cycle == "weekly":
                            # 計算下次重置的週幾
                            weekday_names = ['一', '二', '三', '四', '五', '六', '日']
                            current_weekday = now.weekday() + 1  # 1-7
                            days_until = (reset_day - current_weekday) % 7
                            if days_until == 0:
                                days_until = 7
                            next_reset = now + timedelta(days=days_until)
                            reset_msg = f"{days_until} 天後 (週{weekday_names[reset_day-1]})"
                        else:  # monthly
                            if now.month == 12:
                                next_month = datetime(now.year + 1, 1, reset_day)
                            else:
                                next_month = datetime(now.year, now.month + 1, min(reset_day, 28))
                            days_until = (next_month - now).days
                            reset_msg = f"{days_until} 天後 ({next_month.strftime('%m/%d')})"
                        
                        if "current_month_scans" in quota_check and "total_quota" in quota_check:
                            # 正常配額用完：顯示用量與下次重置時間
                            self._send_reply(
                                reply_token,
                                f"⚠️ 掃描配額已用完\n\n"
                                f"📊 已使用 {quota_check['current_month_scans']}/{quota_check['total_quota']} 張\n"
                                f"🔄 將於 {reset_msg} 重置\n\n"
                                f"💡 需要更多配額？請洽詢服務人員升級方案"
                            )
                        else:
                            # 精簡錯誤字典（如訂閱狀態異常）：check_scan_quota 未回傳用量欄位
                            self._send_reply(
                                reply_token,
                                quota_check.get("message") or "⚠️ 目前無法使用，請洽詢服務人員"
                            )
                        return
                    
                    # 檢查用戶限制（只有新用戶時才檢查）
                    from src.namecard.core.services.tenant_service import get_tenant_service
                    tenant_service = get_tenant_service()
                    existing_user = tenant_service.get_line_user(self.tenant_id, user_id)
                    logger.warning("DEBUG_USER_CHECK", existing_user_found=existing_user is not None)
                    
                    if not existing_user:
                        user_limit_check = quota_service.check_user_limit(self.tenant_id)
                        logger.warning("DEBUG_USER_LIMIT_CHECK", allowed=user_limit_check.get("allowed"), current=user_limit_check.get("current_users"), limit=user_limit_check.get("user_limit"))
                        if not user_limit_check["allowed"]:
                            logger.warning("DEBUG_USER_LIMIT_EXCEEDED", tenant_id=self.tenant_id)
                            self._send_reply(
                                reply_token,
                                f"⚠️ 很抱歉，本服務目前用戶數已達上限\n\n"
                                f"👥 目前用戶數：{user_limit_check['current_users']}/{user_limit_check['user_limit']}\n\n"
                                f"📞 如需使用，請聯繫貴公司的服務管理員協助升級"
                            )
                            return
                except Exception as e:
                    # Fail-closed：配額檢查發生例外時，一律中止並回覆，避免放行造成配額被繞過
                    logger.warning("DEBUG_QUOTA_CHECK_EXCEPTION", error=str(e), error_type=type(e).__name__)
                    logger.error("Quota check failed, aborting to avoid fail-open", error=str(e))
                    self._send_reply(reply_token, "⚠️ 系統忙碌，請稍後再試")
                    return
            
            # 向後相容：無租戶時使用舊的每日限制
            if not self.tenant_id and status.daily_usage >= settings.rate_limit_per_user:
                logger.warning("DEBUG_DAILY_LIMIT_EXCEEDED", daily_usage=status.daily_usage)
                self._send_reply(
                    reply_token,
                    f"⚠️ 已達每日上限（{status.daily_usage}/{settings.rate_limit_per_user}）\n請明天再試",
                )
                return

            logger.warning("DEBUG_ALL_CHECKS_PASSED", tenant_id=self.tenant_id, user_id=user_id[:10] + "...")
            # 下載圖片
            logger.warning("DEBUG_DOWNLOADING_IMAGE", message_id=message_id, user_id=user_id[:10] + "...")
            image_data = self._get_message_content(message_id)
            logger.warning("DEBUG_IMAGE_DOWNLOADED", image_size=len(image_data), message_id=message_id)

            # 驗證圖片
            if not security_service.validate_image_data(image_data):
                logger.warning("DEBUG_IMAGE_VALIDATION_FAILED", image_size=len(image_data))
                self._send_reply(reply_token, "❌ 圖片格式錯誤或檔案過大\n請上傳 10MB 以內的 JPG/PNG 圖片")
                return

            # 處理圖片（現在會拋出具體異常而非返回空列表）
            logger.warning("DEBUG_AI_PROCESSING_START", user_id=user_id[:10] + "...", image_size=len(image_data))
            cards = self.card_processor.process_image(image_data, user_id)
            logger.warning("DEBUG_AI_PROCESSING_DONE", cards_count=len(cards), user_id=user_id[:10] + "...")

            # 儲存名片（先不含圖片，稍後非同步更新）
            success_count = 0
            failed_count = 0
            error_messages = []
            saved_page_ids = []  # 記錄成功儲存的頁面 ID

            for idx, card in enumerate(cards):
                try:
                    # 儲存到 Notion（不含圖片）- 返回 (page_id, page_url)
                    logger.warning("DEBUG_NOTION_SAVE_START", card_idx=idx, card_name=card.name, card_company=card.company, notion_db_id=self.notion_client.database_id[:10] + "..." if self.notion_client.database_id else None, data_source_id=self.notion_client.data_source_id[:10] + "..." if self.notion_client.data_source_id else "NONE!")
                    result = self.notion_client.save_business_card(card)
                    logger.warning("DEBUG_NOTION_SAVE_RESULT", card_idx=idx, result_is_none=result is None, page_id=result[0][:10] + "..." if result else None)

                    if result:
                        page_id, page_url = result
                        success_count += 1
                        card.processed = True

                        # 直接使用 API 返回的 page_id
                        if page_id:
                            saved_page_ids.append(page_id)

                        # 如果是批次模式，加入批次
                        if status.is_batch_mode:
                            user_service.add_card_to_batch(user_id, card)
                    else:
                        logger.warning("DEBUG_NOTION_SAVE_RETURNED_NONE", card_idx=idx, card_name=card.name)
                        failed_count += 1
                        card.processed = False

                except Exception as e:
                    failed_count += 1
                    card.processed = False
                    error_msg = error_handler.handle_notion_error(e, user_id)
                    error_messages.append(error_msg)
                    logger.warning("DEBUG_NOTION_SAVE_EXCEPTION", card_idx=idx, error=str(e), error_type=type(e).__name__)
                    logger.error("Failed to save card", error=str(e), user_id=user_id)

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
                        errors=failed_count,
                    )

                    # 記錄用戶級別統計
                    tenant_service.record_user_usage(
                        tenant_id=self.tenant_id,
                        line_user_id=user_id,
                        cards_processed=len(cards),
                        cards_saved=success_count,
                        errors=failed_count,
                    )

                    # 獲取並儲存用戶資訊（名稱、頭像）
                    self._save_user_profile(user_id, tenant_service)
                    
                    # 消耗掃描配額（只有成功處理的才消耗）
                    if success_count > 0:
                        from src.namecard.core.services.quota_service import get_quota_service
                        quota_service = get_quota_service()
                        quota_service.consume_scan(self.tenant_id, success_count)
                except Exception as e:
                    logger.warning("Failed to record usage stats", error=str(e))

            # 先回覆用戶（不等待圖片上傳）
            self._send_processing_result(
                reply_token, cards, success_count, failed_count, error_messages, status
            )

            # 使用 Queue Worker 非同步上傳圖片到 ImgBB
            logger.warning("DEBUG_BEFORE_IMGBB_CHECK", success_count=success_count, saved_page_ids_count=len(saved_page_ids), will_upload=success_count > 0 and len(saved_page_ids) > 0)
            if success_count > 0 and saved_page_ids:
                logger.warning("DEBUG_SUBMITTING_IMGBB_UPLOAD", page_ids=saved_page_ids[:3], image_size=len(image_data))
                submit_image_upload(
                    image_data=image_data,
                    page_ids=saved_page_ids,
                    notion_client=self.notion_client,
                    user_id=user_id,
                )
                logger.warning("DEBUG_IMGBB_UPLOAD_SUBMITTED", page_count=len(saved_page_ids))
            else:
                logger.warning("DEBUG_IMGBB_SKIPPED_NO_SUCCESS", success_count=success_count, saved_page_ids_count=len(saved_page_ids))

        except (MessagingApiException, LineBotApiError) as e:
            # LINE API 錯誤（下載圖片等）
            logger.error("LINE API error in image processing", error=str(e), user_id=user_id)
            error_handler.handle_line_error(e, user_id)
            try:
                self._push_message(user_id, "❌ 圖片下載失敗，請重試")
            except:
                pass

        except Exception as e:
            # AI 處理或其他錯誤
            logger.error("Image processing failed", error=str(e), user_id=user_id)
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
            quick_reply=QuickReply(
                items=[
                    QuickReplyItem(action=MessageAction(label="開始批次", text="批次")),
                    QuickReplyItem(action=MessageAction(label="查看狀態", text="狀態")),
                ]
            ),
        )

    def _start_batch_mode(self, user_id: str, reply_token: str) -> None:
        """開始批次模式"""
        user_service.start_batch_mode(user_id)

        self._send_reply(
            reply_token,
            "📦 批次模式已啟動\n\n請連續上傳多張名片照片\n完成後輸入「結束批次」",
            quick_reply=QuickReply(
                items=[
                    QuickReplyItem(action=MessageAction(label="結束批次", text="結束批次")),
                    QuickReplyItem(action=MessageAction(label="查看進度", text="狀態")),
                ]
            ),
        )

        logger.info("Batch mode started", user_id=user_id)

    def _show_status(self, user_id: str, reply_token: str) -> None:
        """顯示狀態（批次模式使用 Flex Message 進度卡片）"""
        status = user_service.get_user_status(user_id)

        # 批次狀態 - 使用 Flex Message 進度卡片
        if status.is_batch_mode and status.current_batch:
            batch = status.current_batch
            try:
                # 使用視覺化進度卡片
                flex_message = create_progress_message(
                    current=batch.total_cards,
                    total=50,  # 每日限制作為總數
                    success_count=batch.successful_cards,
                    failed_count=batch.failed_cards
                )
                self._send_flex_message(reply_token, flex_message)
                return
            except Exception as e:
                # Fallback 到純文字
                logger.warning("Progress Flex Message failed", error=str(e))
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
        """結束批次模式（使用 Flex Message 統計卡片）"""
        batch_result = user_service.end_batch_mode(user_id)

        if not batch_result:
            self._send_reply(reply_token, "⚠️ 目前不在批次模式")
            return

        success_rate = batch_result.success_rate * 100

        try:
            # 使用 Flex Message 批次完成卡片
            flex_message = create_batch_complete_message(batch_result)
            self._send_flex_message(reply_token, flex_message)
        except Exception as e:
            # Fallback 到純文字
            logger.warning("Batch complete Flex Message failed", error=str(e))
            duration = batch_result.completed_at - batch_result.started_at
            summary_text = f"""🎉 批次完成！

總計：{batch_result.total_cards} 張
成功：{batch_result.successful_cards} 張 ({success_rate:.0f}%)
失敗：{batch_result.failed_cards} 張
時間：{duration.seconds // 60}:{duration.seconds % 60:02d}"""

            if batch_result.errors:
                summary_text += f"\n\n⚠️ {batch_result.errors[0][:50]}"

            self._send_reply(reply_token, summary_text)

        logger.info(
            "Batch mode ended",
            user_id=user_id,
            total_cards=batch_result.total_cards,
            success_rate=success_rate,
        )

    def _retry_failed_uploads(self, user_id: str, reply_token: str) -> None:
        """重試失敗的圖片上傳"""
        # 先查詢失敗任務
        failed_tasks = get_failed_tasks(user_id)

        if not failed_tasks:
            self._send_reply(reply_token, "✅ 沒有失敗的上傳任務")
            return

        # 顯示失敗任務數量並開始重試
        self._send_reply(reply_token, f"🔄 發現 {len(failed_tasks)} 個失敗任務，正在重試...")

        # 執行重試
        success_count = retry_all_failed_tasks(user_id, self.notion_client)

        # 用 push message 發送結果（因為 reply_token 已用過）
        try:
            if success_count == len(failed_tasks):
                result_msg = f"✅ 全部 {success_count} 個任務重試成功！"
            elif success_count > 0:
                result_msg = f"⚠️ 重試完成：{success_count}/{len(failed_tasks)} 成功"
            else:
                result_msg = "❌ 重試失敗，請稍後再試"

            self._push_message(user_id, result_msg)
        except Exception as e:
            logger.error("Failed to send retry result", error=str(e))

        logger.info(
            "Retry failed uploads completed",
            user_id=user_id,
            total=len(failed_tasks),
            success=success_count,
        )

    def _clear_failed_uploads(self, user_id: str, reply_token: str) -> None:
        """清除失敗的上傳任務記錄"""
        cleared_count = clear_failed_tasks(user_id)

        if cleared_count > 0:
            self._send_reply(reply_token, f"🗑️ 已清除 {cleared_count} 個失敗任務記錄")
        else:
            self._send_reply(reply_token, "✅ 沒有失敗的任務需要清除")

        logger.info("Cleared failed tasks", user_id=user_id, count=cleared_count)

    def _send_unknown_command(self, reply_token: str) -> None:
        """發送未知命令訊息"""
        self._send_reply(
            reply_token,
            "❓ 不認識的指令\n輸入「幫助」查看使用說明",
            quick_reply=QuickReply(
                items=[
                    QuickReplyItem(action=MessageAction(label="查看說明", text="幫助")),
                ]
            ),
        )

    def _send_processing_result(
        self,
        reply_token: str,
        cards: list,
        success_count: int,
        failed_count: int,
        error_messages: list,
        status,
    ) -> None:
        """發送處理結果訊息（使用改善的 Flex Message）"""
        total = len(cards)

        if success_count > 0:
            try:
                # 使用 Flex Message 發送漂亮的卡片
                flex_message = create_card_result_message(
                    cards=cards,
                    is_batch_mode=status.is_batch_mode,
                    batch_progress=status.current_batch.total_cards
                    if status.is_batch_mode and status.current_batch
                    else None,
                    success_count=success_count,
                    failed_count=failed_count,
                )
                self._send_flex_message(reply_token, flex_message)
                logger.info("Sent Flex Message result", cards_count=len(cards))
            except Exception as e:
                # Flex Message 失敗時 fallback 到純文字
                logger.warning("Flex Message failed, falling back to text", error=str(e))
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
            # 全部失敗 - 使用結構化錯誤 Flex Message
            self._send_error_flex_message(reply_token, "storage_error", error_messages)

    def _send_error_message(self, reply_token: str, error_msg: str) -> None:
        """發送錯誤訊息（使用 Flex Message）"""
        # 根據錯誤訊息判斷錯誤類型
        error_key = "system_error"
        if "品質" in error_msg or "模糊" in error_msg or "解析度" in error_msg:
            error_key = "low_quality"
        elif "名片" in error_msg or "識別" in error_msg:
            error_key = "not_business_card"
        elif "額度" in error_msg or "配額" in error_msg or "上限" in error_msg:
            error_key = "quota_exceeded"
        elif "儲存" in error_msg or "Notion" in error_msg:
            error_key = "storage_error"

        try:
            flex_message = create_error_message(error_key=error_key)
            self._send_flex_message(reply_token, flex_message)
        except Exception as e:
            # Fallback 到純文字
            logger.warning("Error Flex Message failed", error=str(e))
            self._send_reply(reply_token, error_msg)

    def _send_error_flex_message(
        self, reply_token: str, error_key: str, error_messages: list = None
    ) -> None:
        """發送結構化錯誤 Flex Message"""
        try:
            flex_message = create_error_message(error_key=error_key)
            self._send_flex_message(reply_token, flex_message)
        except Exception as e:
            # Fallback 到純文字
            logger.warning("Error Flex Message failed", error=str(e))
            error_text = error_messages[0] if error_messages else "❌ 處理失敗，請稍後重試"
            self._send_reply(reply_token, error_text)

    def _send_flex_message(self, reply_token: str, flex_message) -> None:
        """
        發送 Flex Message

        Args:
            reply_token: 回覆 token
            flex_message: FlexMessage 實例
        """
        try:
            if self.configuration:
                # v3 API
                with ApiClient(self.configuration) as api_client:
                    line_bot_api = MessagingApi(api_client)
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=reply_token,
                            messages=[flex_message]
                        )
                    )
            else:
                # Mock 測試模式
                self._mock_api.reply_message(reply_token, flex_message)
        except (MessagingApiException, Exception) as e:
            logger.error(
                "Failed to send flex message", error=str(e), reply_token=reply_token[:20] + "..."
            )
            raise

    def _send_reply(
        self, reply_token: str, text: str, quick_reply: Optional[QuickReply] = None
    ) -> None:
        """
        統一的回覆發送方法（純文字）

        Args:
            reply_token: 回覆 token
            text: 訊息內容
            quick_reply: 快速回覆選項（可選）
        """
        try:
            if self.configuration:
                # v3 API
                with ApiClient(self.configuration) as api_client:
                    line_bot_api = MessagingApi(api_client)
                    message = TextMessage(text=text, quick_reply=quick_reply)
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=reply_token,
                            messages=[message]
                        )
                    )
            else:
                # Mock 測試模式
                self._mock_api.reply_message(reply_token, text)
        except (MessagingApiException, Exception) as e:
            logger.error("Failed to send reply", error=str(e), reply_token=reply_token[:20] + "...")
            raise

    def _push_message(self, user_id: str, text: str) -> None:
        """
        發送 Push Message（不需要 reply_token）

        Args:
            user_id: LINE 用戶 ID
            text: 訊息內容
        """
        try:
            if self.configuration:
                # v3 API
                with ApiClient(self.configuration) as api_client:
                    line_bot_api = MessagingApi(api_client)
                    line_bot_api.push_message(
                        PushMessageRequest(
                            to=user_id,
                            messages=[TextMessage(text=text)]
                        )
                    )
            else:
                # Mock 測試模式
                self._mock_api.push_message(user_id, text)
        except Exception as e:
            logger.error("Failed to push message", error=str(e), user_id=user_id[:10] + "...")
            raise

    def _get_message_content(self, message_id: str) -> bytes:
        """
        下載訊息內容（圖片等）

        Args:
            message_id: 訊息 ID
            
        Returns:
            bytes: 訊息內容
        """
        if self.configuration:
            # v3 API - 使用 MessagingApiBlob
            from linebot.v3.messaging import MessagingApiBlob
            with ApiClient(self.configuration) as api_client:
                blob_api = MessagingApiBlob(api_client)
                return blob_api.get_message_content(message_id)
        else:
            # Mock 測試模式
            return self._mock_api.get_message_content(message_id).content

    def _get_profile(self, user_id: str):
        """
        獲取用戶 Profile

        Args:
            user_id: LINE 用戶 ID
            
        Returns:
            Profile object with display_name and picture_url
        """
        if self.configuration:
            # v3 API
            with ApiClient(self.configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                return line_bot_api.get_profile(user_id)
        else:
            # Mock 測試模式
            return self._mock_api.get_profile(user_id)

    def _save_user_profile(self, user_id: str, tenant_service=None) -> None:
        """
        獲取並儲存 LINE 用戶資訊（名稱、頭像）

        Args:
            user_id: LINE 用戶 ID
            tenant_service: TenantService 實例（可選）
        """
        if not self.tenant_id:
            return

        try:
            profile = self._get_profile(user_id)
            display_name = profile.display_name
            picture_url = profile.picture_url

            if tenant_service is None:
                from src.namecard.core.services.tenant_service import get_tenant_service
                tenant_service = get_tenant_service()

            tenant_service.save_line_user(
                tenant_id=self.tenant_id,
                line_user_id=user_id,
                display_name=display_name,
                picture_url=picture_url,
            )

            logger.debug("User profile saved", user_id=user_id, display_name=display_name)
        except Exception as e:
            logger.warning("Failed to save user profile", error=str(e), user_id=user_id)

