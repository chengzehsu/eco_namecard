"""
租戶掃描配額強制執行的回歸測試

背景（bug）：
    handle_image_message 在租戶配額耗盡（check_scan_quota 回 has_quota=False）時，
    會進入「配額用完」分支去計算下次重設時間。該分支呼叫 tenant_service 取得租戶設定，
    若呼叫了不存在的方法（例如 get_tenant 而非 get_tenant_by_id），會拋出 AttributeError，
    而這個例外被外層 try/except 吞掉（只記 log、不 return），導致流程「掉出」配額檢查、
    繼續下載圖片並呼叫 card_processor.process_image —— 使用者不但沒收到配額用完訊息，
    圖片還照樣被辨識，形同配額完全失效。

回歸目標：
    配額耗盡時，使用者要收到「掃描配額已用完」訊息，且圖片「不得」進入
    card_processor.process_image / notion_client.save_business_card / ImgBB 上傳流程。

    - 未修正（呼叫 get_tenant）：TenantService 沒有此方法 → AttributeError → 被吞掉 →
      process_image 仍被呼叫 → 本測試失敗。
    - 修正後（呼叫 get_tenant_by_id）：正常送出配額訊息並 return → process_image 不被呼叫 →
      本測試通過。

    為忠實反映此 bug，tenant_service 使用 spec=TenantService 的 Mock：
    只有真實存在的 get_tenant_by_id 可被呼叫，get_tenant 會如同正式環境一樣拋 AttributeError。
"""

from io import BytesIO
from unittest.mock import Mock, patch

import pytest
from PIL import Image

from src.namecard.core.models.card import BusinessCard
from src.namecard.core.services.tenant_service import TenantService
from src.namecard.api.line_bot.event_handler import UnifiedEventHandler


def _create_test_image() -> bytes:
    """建立測試用圖片位元組"""
    img = Image.new("RGB", (800, 600), color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


class TestQuotaEnforcement:
    """租戶配額耗盡時，圖片不得進入辨識流程"""

    def setup_method(self):
        self.tenant_id = "tenant_quota_test"
        self.user_id = "U1234567890abcdef"
        self.message_id = "12345678901234567"
        self.reply_token = "test_reply_token_abc123"
        self.image_data = _create_test_image()

        self.test_card = BusinessCard(
            name="張三",
            company="測試公司",
            confidence_score=0.95,
            quality_score=0.9,
            line_user_id=self.user_id,
        )

    def _build_mocks(self):
        """建立共用的 LINE / notion / processor mock"""
        mock_line_api = Mock()
        mock_message_content = Mock()
        mock_message_content.content = self.image_data
        mock_line_api.get_message_content.return_value = mock_message_content

        mock_processor = Mock()
        mock_processor.process_image.return_value = [self.test_card]

        mock_notion = Mock()
        mock_notion.database_id = "test_db_id"
        mock_notion.data_source_id = "test_ds_id"
        mock_notion.save_business_card.return_value = ("page_123", "https://notion.so/page_123")

        return mock_line_api, mock_processor, mock_notion

    @patch("src.namecard.api.line_bot.event_handler.submit_image_upload")
    @patch("src.namecard.api.line_bot.event_handler.user_service")
    @patch("src.namecard.api.line_bot.event_handler.security_service")
    def test_quota_exhausted_blocks_image_processing(
        self,
        mock_security,
        mock_user_service,
        mock_submit_upload,
    ):
        """
        配額耗盡（has_quota=False）：
        - 使用者收到「掃描配額已用完」訊息
        - card_processor.process_image 不被呼叫
        - notion 儲存與 ImgBB 上傳都不被觸發
        """
        mock_security.validate_image_data.return_value = True

        mock_status = Mock()
        mock_status.daily_usage = 10
        mock_status.is_batch_mode = False
        mock_status.current_batch = None
        mock_user_service.get_user_status.return_value = mock_status

        mock_line_api, mock_processor, mock_notion = self._build_mocks()

        # QuotaService：配額已用完
        mock_quota_service = Mock()
        mock_quota_service.check_scan_quota.return_value = {
            "has_quota": False,
            "remaining_scans": 0,
            "total_quota": 50,
            "current_month_scans": 50,
        }

        # TenantService：以真實類別為 spec，忠實反映 bug
        # get_tenant_by_id 存在（回傳可用的租戶設定）；get_tenant 不存在會拋 AttributeError
        mock_tenant = Mock()
        mock_tenant.quota_reset_cycle = "daily"
        mock_tenant.quota_reset_day = 1

        mock_tenant_service = Mock(spec=TenantService)
        mock_tenant_service.get_tenant_by_id.return_value = mock_tenant

        handler = UnifiedEventHandler(
            line_bot_api=mock_line_api,
            card_processor=mock_processor,
            notion_client=mock_notion,
            tenant_id=self.tenant_id,
        )

        with patch(
            "src.namecard.core.services.quota_service.get_quota_service",
            return_value=mock_quota_service,
        ), patch(
            "src.namecard.core.services.tenant_service.get_tenant_service",
            return_value=mock_tenant_service,
        ):
            handler.handle_image_message(self.user_id, self.message_id, self.reply_token)

        # 1. 配額有被檢查
        mock_quota_service.check_scan_quota.assert_called_once_with(self.tenant_id)

        # 2. 核心斷言：圖片未進入 AI 辨識流程
        mock_processor.process_image.assert_not_called()

        # 3. 圖片也未進入 Notion 儲存與 ImgBB 上傳
        mock_notion.save_business_card.assert_not_called()
        mock_submit_upload.assert_not_called()

        # 4. 使用者收到「掃描配額已用完」訊息（Mock 測試模式走 _mock_api.reply_message）
        reply_texts = [
            call.args[1]
            for call in mock_line_api.reply_message.call_args_list
            if len(call.args) >= 2 and isinstance(call.args[1], str)
        ]
        assert any("掃描配額已用完" in text for text in reply_texts), (
            f"未送出配額用完訊息，實際回覆：{reply_texts}"
        )

    @patch("src.namecard.api.line_bot.event_handler.submit_image_upload")
    @patch("src.namecard.api.line_bot.event_handler.user_service")
    @patch("src.namecard.api.line_bot.event_handler.security_service")
    def test_quota_available_allows_image_processing(
        self,
        mock_security,
        mock_user_service,
        mock_submit_upload,
    ):
        """
        對照組：配額充足（has_quota=True）時，圖片應正常進入辨識流程。
        用來證明上一個測試的失敗確實來自「配額耗盡」這道閘門，而非測試把所有路徑都擋掉。
        """
        mock_security.validate_image_data.return_value = True

        mock_status = Mock()
        mock_status.daily_usage = 10
        mock_status.is_batch_mode = False
        mock_status.current_batch = None
        mock_user_service.get_user_status.return_value = mock_status

        mock_line_api, mock_processor, mock_notion = self._build_mocks()

        # QuotaService：仍有配額
        mock_quota_service = Mock()
        mock_quota_service.check_scan_quota.return_value = {
            "has_quota": True,
            "remaining_scans": 40,
            "total_quota": 50,
            "current_month_scans": 10,
        }
        mock_quota_service.consume_scan.return_value = {"success": True, "remaining_scans": 39}

        # 既有使用者 → 略過 check_user_limit
        mock_tenant_service = Mock(spec=TenantService)
        mock_tenant_service.get_line_user.return_value = {"line_user_id": self.user_id}

        handler = UnifiedEventHandler(
            line_bot_api=mock_line_api,
            card_processor=mock_processor,
            notion_client=mock_notion,
            tenant_id=self.tenant_id,
        )

        with patch(
            "src.namecard.core.services.quota_service.get_quota_service",
            return_value=mock_quota_service,
        ), patch(
            "src.namecard.core.services.tenant_service.get_tenant_service",
            return_value=mock_tenant_service,
        ):
            handler.handle_image_message(self.user_id, self.message_id, self.reply_token)

        # 配額充足 → 圖片進入辨識流程
        mock_processor.process_image.assert_called_once_with(self.image_data, self.user_id)
        mock_notion.save_business_card.assert_called_once_with(self.test_card)
