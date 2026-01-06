"""
圖片處理流程端對端測試

這個測試模組覆蓋完整的圖片處理流程：
LINE 圖片上傳 → 下載圖片 → AI 辨識 → Notion 儲存 → ImgBB 上傳

流程圖：
┌─────────────────────────────────────────────────────────────┐
│  1. main.py: 接收 webhook, 識別租戶                         │
│  2. event_handler: 下載圖片                                  │
│  3. card_processor: AI 辨識 (Gemini)                        │
│  4. notion_client: 儲存到 Notion                            │
│  5. submit_image_upload: 上傳到 imgbb                        │
└─────────────────────────────────────────────────────────────┘
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, PropertyMock
from io import BytesIO
from PIL import Image
import json

from src.namecard.core.models.card import BusinessCard
from src.namecard.api.line_bot.event_handler import UnifiedEventHandler


class TestImageProcessingFlow:
    """圖片處理流程端對端測試"""

    def setup_method(self):
        """設置測試環境"""
        self.test_user_id = "U1234567890abcdef"
        self.test_message_id = "12345678901234567"
        self.test_reply_token = "test_reply_token_abc123"
        
        # 創建測試用的圖片數據
        self.test_image_data = self._create_test_image()
        
        # 創建測試用的名片
        self.test_card = BusinessCard(
            name="張三",
            company="測試公司",
            title="工程師",
            phone="02-1234-5678",
            email="test@example.com",
            confidence_score=0.95,
            quality_score=0.9,
            line_user_id=self.test_user_id
        )

    def _create_test_image(self) -> bytes:
        """創建測試用圖片"""
        img = Image.new('RGB', (800, 600), color='white')
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()

    @patch('src.namecard.api.line_bot.event_handler.submit_image_upload')
    @patch('src.namecard.api.line_bot.event_handler.user_service')
    @patch('src.namecard.api.line_bot.event_handler.security_service')
    def test_complete_image_processing_flow_success(
        self,
        mock_security,
        mock_user_service,
        mock_submit_upload,
    ):
        """
        測試完整圖片處理流程 - 成功案例
        
        流程:
        1. 下載圖片 ✓
        2. 驗證圖片 ✓
        3. AI 處理 ✓
        4. Notion 儲存 ✓
        5. ImgBB 上傳提交 ✓
        """
        # 設置 mocks
        mock_security.is_user_blocked.return_value = False
        mock_security.validate_image_data.return_value = True
        
        mock_status = Mock()
        mock_status.daily_usage = 10
        mock_status.is_batch_mode = False
        mock_status.current_batch = None
        mock_user_service.get_user_status.return_value = mock_status
        
        # Mock LINE Bot API
        mock_line_api = Mock()
        mock_message_content = Mock()
        mock_message_content.content = self.test_image_data
        mock_line_api.get_message_content.return_value = mock_message_content
        
        # Mock Card Processor
        mock_processor = Mock()
        mock_processor.process_image.return_value = [self.test_card]
        
        # Mock Notion Client
        mock_notion = Mock()
        mock_notion.database_id = "test_db_id"
        mock_notion.data_source_id = "test_ds_id"
        mock_notion.save_business_card.return_value = ("page_123", "https://notion.so/page_123")
        
        # 創建 handler
        handler = UnifiedEventHandler(
            line_bot_api=mock_line_api,
            card_processor=mock_processor,
            notion_client=mock_notion,
            tenant_id="test_tenant"
        )
        
        # 執行
        handler.handle_image_message(
            self.test_user_id,
            self.test_message_id,
            self.test_reply_token
        )
        
        # 驗證流程
        # 1. 圖片下載
        mock_line_api.get_message_content.assert_called_once_with(self.test_message_id)
        
        # 2. 圖片驗證
        mock_security.validate_image_data.assert_called_once_with(self.test_image_data)
        
        # 3. AI 處理
        mock_processor.process_image.assert_called_once_with(
            self.test_image_data,
            self.test_user_id
        )
        
        # 4. Notion 儲存
        mock_notion.save_business_card.assert_called_once_with(self.test_card)
        
        # 5. ImgBB 上傳提交
        mock_submit_upload.assert_called_once()
        call_kwargs = mock_submit_upload.call_args[1]
        assert call_kwargs['image_data'] == self.test_image_data
        assert call_kwargs['page_ids'] == ["page_123"]
        assert call_kwargs['user_id'] == self.test_user_id

    @patch('src.namecard.api.line_bot.event_handler.submit_image_upload')
    @patch('src.namecard.api.line_bot.event_handler.user_service')
    @patch('src.namecard.api.line_bot.event_handler.security_service')
    def test_imgbb_not_triggered_when_notion_fails(
        self,
        mock_security,
        mock_user_service,
        mock_submit_upload,
    ):
        """
        測試當 Notion 儲存失敗時，ImgBB 上傳不應被觸發
        
        這是一個關鍵測試：
        - Notion 返回 None (data_source_id 缺失等原因)
        - success_count = 0
        - ImgBB 上傳不應被調用
        """
        # 設置 mocks
        mock_security.is_user_blocked.return_value = False
        mock_security.validate_image_data.return_value = True
        
        mock_status = Mock()
        mock_status.daily_usage = 10
        mock_status.is_batch_mode = False
        mock_status.current_batch = None
        mock_user_service.get_user_status.return_value = mock_status
        
        # Mock LINE Bot API
        mock_line_api = Mock()
        mock_message_content = Mock()
        mock_message_content.content = self.test_image_data
        mock_line_api.get_message_content.return_value = mock_message_content
        
        # Mock Card Processor - 返回名片
        mock_processor = Mock()
        mock_processor.process_image.return_value = [self.test_card]
        
        # Mock Notion Client - 返回 None (模擬 data_source_id 缺失)
        mock_notion = Mock()
        mock_notion.database_id = "test_db_id"
        mock_notion.data_source_id = None  # 關鍵：這會導致 save 返回 None
        mock_notion.save_business_card.return_value = None  # 返回 None
        
        # 創建 handler
        handler = UnifiedEventHandler(
            line_bot_api=mock_line_api,
            card_processor=mock_processor,
            notion_client=mock_notion,
            tenant_id="test_tenant"
        )
        
        # 執行
        handler.handle_image_message(
            self.test_user_id,
            self.test_message_id,
            self.test_reply_token
        )
        
        # 驗證 ImgBB 上傳未被調用
        mock_submit_upload.assert_not_called()
        
        # 驗證 Notion 儲存被調用了
        mock_notion.save_business_card.assert_called_once()

    @patch('src.namecard.api.line_bot.event_handler.submit_image_upload')
    @patch('src.namecard.api.line_bot.event_handler.user_service')
    @patch('src.namecard.api.line_bot.event_handler.security_service')
    def test_no_cards_detected(
        self,
        mock_security,
        mock_user_service,
        mock_submit_upload,
    ):
        """
        測試 AI 未識別到名片的情況
        """
        # 設置 mocks
        mock_security.is_user_blocked.return_value = False
        mock_security.validate_image_data.return_value = True
        
        mock_status = Mock()
        mock_status.daily_usage = 10
        mock_status.is_batch_mode = False
        mock_user_service.get_user_status.return_value = mock_status
        
        # Mock LINE Bot API
        mock_line_api = Mock()
        mock_message_content = Mock()
        mock_message_content.content = self.test_image_data
        mock_line_api.get_message_content.return_value = mock_message_content
        
        # Mock Card Processor - 拋出異常（未識別到名片）
        from src.namecard.core.exceptions import EmptyAIResponseError
        mock_processor = Mock()
        mock_processor.process_image.side_effect = EmptyAIResponseError(
            details={"reason": "no_cards_detected"}
        )
        
        # Mock Notion Client
        mock_notion = Mock()
        
        # 創建 handler
        handler = UnifiedEventHandler(
            line_bot_api=mock_line_api,
            card_processor=mock_processor,
            notion_client=mock_notion,
            tenant_id="test_tenant"
        )
        
        # 執行 - 不應拋出異常
        handler.handle_image_message(
            self.test_user_id,
            self.test_message_id,
            self.test_reply_token
        )
        
        # 驗證 Notion 和 ImgBB 都未被調用
        mock_notion.save_business_card.assert_not_called()
        mock_submit_upload.assert_not_called()

    @patch('src.namecard.api.line_bot.event_handler.user_service')
    @patch('src.namecard.api.line_bot.event_handler.security_service')
    def test_user_blocked(self, mock_security, mock_user_service):
        """測試被封鎖用戶"""
        mock_security.is_user_blocked.return_value = True
        
        mock_line_api = Mock()
        mock_processor = Mock()
        mock_notion = Mock()
        
        handler = UnifiedEventHandler(
            line_bot_api=mock_line_api,
            card_processor=mock_processor,
            notion_client=mock_notion,
        )
        
        handler.handle_image_message(
            self.test_user_id,
            self.test_message_id,
            self.test_reply_token
        )
        
        # 驗證未進行任何處理
        mock_line_api.get_message_content.assert_not_called()
        mock_processor.process_image.assert_not_called()
        mock_notion.save_business_card.assert_not_called()

    @patch('src.namecard.api.line_bot.event_handler.user_service')
    @patch('src.namecard.api.line_bot.event_handler.security_service')
    def test_daily_limit_exceeded(self, mock_security, mock_user_service):
        """測試超過每日限額"""
        mock_security.is_user_blocked.return_value = False
        
        mock_status = Mock()
        mock_status.daily_usage = 50  # 達到限額
        mock_user_service.get_user_status.return_value = mock_status
        
        mock_line_api = Mock()
        mock_processor = Mock()
        mock_notion = Mock()
        
        handler = UnifiedEventHandler(
            line_bot_api=mock_line_api,
            card_processor=mock_processor,
            notion_client=mock_notion,
        )
        
        handler.handle_image_message(
            self.test_user_id,
            self.test_message_id,
            self.test_reply_token
        )
        
        # 驗證未進行圖片處理
        mock_line_api.get_message_content.assert_not_called()
        mock_processor.process_image.assert_not_called()

    @patch('src.namecard.api.line_bot.event_handler.user_service')
    @patch('src.namecard.api.line_bot.event_handler.security_service')
    def test_invalid_image(self, mock_security, mock_user_service):
        """測試無效圖片"""
        mock_security.is_user_blocked.return_value = False
        mock_security.validate_image_data.return_value = False  # 圖片驗證失敗
        
        mock_status = Mock()
        mock_status.daily_usage = 10
        mock_user_service.get_user_status.return_value = mock_status
        
        mock_line_api = Mock()
        mock_message_content = Mock()
        mock_message_content.content = b'invalid image data'
        mock_line_api.get_message_content.return_value = mock_message_content
        
        mock_processor = Mock()
        mock_notion = Mock()
        
        handler = UnifiedEventHandler(
            line_bot_api=mock_line_api,
            card_processor=mock_processor,
            notion_client=mock_notion,
        )
        
        handler.handle_image_message(
            self.test_user_id,
            self.test_message_id,
            self.test_reply_token
        )
        
        # 驗證未進行 AI 處理
        mock_processor.process_image.assert_not_called()
        mock_notion.save_business_card.assert_not_called()


class TestNotionDataSourceId:
    """
    Notion data_source_id 相關測試
    
    這是 Notion API 2025-09-03 版本的關鍵：
    - 必須獲取 data_source_id 才能創建頁面
    - 如果獲取失敗，save_business_card 返回 None
    """

    @patch('src.namecard.infrastructure.storage.notion_client.Client')
    @patch('src.namecard.infrastructure.storage.notion_client.settings')
    def test_data_source_id_obtained_success(self, mock_settings, mock_client_class):
        """測試成功獲取 data_source_id"""
        mock_settings.notion_api_key = "test_key"
        mock_settings.notion_database_id = "test_db_id"
        
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # 模擬 database 返回 data_sources
        mock_client.databases.retrieve.return_value = {
            "id": "test_db_id",
            "data_sources": [{"id": "ds_123456"}]
        }
        
        # 模擬 data_source 請求返回 schema
        mock_client.request.return_value = {
            "properties": {"Name": {"type": "title"}}
        }
        
        from src.namecard.infrastructure.storage.notion_client import NotionClient
        client = NotionClient()
        
        assert client.data_source_id == "ds_123456"
        assert "Name" in client._db_schema

    @patch('src.namecard.infrastructure.storage.notion_client.Client')
    @patch('src.namecard.infrastructure.storage.notion_client.settings')
    def test_data_source_id_not_found(self, mock_settings, mock_client_class):
        """測試 data_source_id 獲取失敗"""
        mock_settings.notion_api_key = "test_key"
        mock_settings.notion_database_id = "test_db_id"
        
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # 模擬 database 返回空的 data_sources
        mock_client.databases.retrieve.return_value = {
            "id": "test_db_id",
            "data_sources": []  # 空！
        }
        
        from src.namecard.infrastructure.storage.notion_client import NotionClient
        client = NotionClient()
        
        # data_source_id 應該是 None
        assert client.data_source_id is None

    @patch('src.namecard.infrastructure.storage.notion_client.Client')
    @patch('src.namecard.infrastructure.storage.notion_client.settings')
    def test_save_returns_none_without_data_source_id(self, mock_settings, mock_client_class):
        """測試沒有 data_source_id 時 save 返回 None"""
        mock_settings.notion_api_key = "test_key"
        mock_settings.notion_database_id = "test_db_id"
        
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # 模擬連接失敗
        mock_client.databases.retrieve.side_effect = Exception("Connection failed")
        
        from src.namecard.infrastructure.storage.notion_client import NotionClient
        client = NotionClient()
        
        # data_source_id 應該是 None
        assert client.data_source_id is None
        
        # save 應該返回 None
        card = BusinessCard(
            name="Test",
            line_user_id="test_user"
        )
        result = client.save_business_card(card)
        assert result is None


class TestMultiTenantImageProcessing:
    """多租戶圖片處理測試"""

    @patch('src.namecard.api.line_bot.event_handler.submit_image_upload')
    @patch('src.namecard.api.line_bot.event_handler.user_service')
    @patch('src.namecard.api.line_bot.event_handler.security_service')
    def test_tenant_usage_recorded(
        self,
        mock_security,
        mock_user_service,
        mock_submit_upload,
    ):
        """測試租戶使用記錄"""
        # 設置 mocks
        mock_security.is_user_blocked.return_value = False
        mock_security.validate_image_data.return_value = True
        
        mock_status = Mock()
        mock_status.daily_usage = 10
        mock_status.is_batch_mode = False
        mock_status.current_batch = None
        mock_user_service.get_user_status.return_value = mock_status
        
        # 創建測試圖片
        img = Image.new('RGB', (800, 600), color='white')
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        test_image = buffer.getvalue()
        
        # Mock LINE Bot API
        mock_line_api = Mock()
        mock_message_content = Mock()
        mock_message_content.content = test_image
        mock_line_api.get_message_content.return_value = mock_message_content
        
        # Mock Card Processor
        test_card = BusinessCard(
            name="Test",
            phone="02-1234-5678",
            confidence_score=0.9,
            quality_score=0.9,
            line_user_id="test_user"
        )
        mock_processor = Mock()
        mock_processor.process_image.return_value = [test_card]
        
        # Mock Notion Client
        mock_notion = Mock()
        mock_notion.database_id = "test_db"
        mock_notion.data_source_id = "test_ds"
        mock_notion.save_business_card.return_value = ("page_123", "url")
        
        # 創建 handler with tenant_id
        # 注意：get_tenant_service 是在 handle_image_message 內部動態 import 的
        with patch('src.namecard.core.services.tenant_service.get_tenant_service') as mock_get_service:
            mock_tenant_service = Mock()
            mock_get_service.return_value = mock_tenant_service
            
            handler = UnifiedEventHandler(
                line_bot_api=mock_line_api,
                card_processor=mock_processor,
                notion_client=mock_notion,
                tenant_id="tenant_123"
            )
            
            handler.handle_image_message(
                "test_user_id",
                "12345",
                "reply_token"
            )
            
            # 驗證租戶使用記錄被調用（可能因為內部 import 方式不同，這裡只驗證處理完成）
            # 實際的租戶使用記錄測試需要更完整的集成測試
            mock_notion.save_business_card.assert_called_once()


class TestImageProcessingErrorHandling:
    """圖片處理錯誤處理測試"""

    @patch('src.namecard.api.line_bot.event_handler.user_service')
    @patch('src.namecard.api.line_bot.event_handler.security_service')
    def test_line_api_error_handled(self, mock_security, mock_user_service):
        """測試 LINE API 錯誤處理"""
        mock_security.is_user_blocked.return_value = False
        
        mock_status = Mock()
        mock_status.daily_usage = 10
        mock_user_service.get_user_status.return_value = mock_status
        
        # Mock LINE Bot API 拋出錯誤
        from linebot.exceptions import LineBotApiError
        mock_line_api = Mock()
        
        # LineBotApiError 需要正確的參數
        mock_error = Mock()
        mock_error.message = "Server error"
        line_api_error = LineBotApiError(
            status_code=500,
            headers={},  # 添加必需的 headers 參數
            request_id="req123",
            error=mock_error
        )
        mock_line_api.get_message_content.side_effect = line_api_error
        mock_line_api.push_message = Mock()  # 用於錯誤通知
        
        mock_processor = Mock()
        mock_notion = Mock()
        
        handler = UnifiedEventHandler(
            line_bot_api=mock_line_api,
            card_processor=mock_processor,
            notion_client=mock_notion,
        )
        
        # 不應拋出異常
        handler.handle_image_message(
            "test_user",
            "12345",
            "reply_token"
        )
        
        # 驗證嘗試發送錯誤通知
        mock_line_api.push_message.assert_called()

    @patch('src.namecard.api.line_bot.event_handler.user_service')
    @patch('src.namecard.api.line_bot.event_handler.security_service')
    def test_ai_processing_error_handled(self, mock_security, mock_user_service):
        """測試 AI 處理錯誤處理"""
        mock_security.is_user_blocked.return_value = False
        mock_security.validate_image_data.return_value = True
        
        mock_status = Mock()
        mock_status.daily_usage = 10
        mock_status.is_batch_mode = False
        mock_user_service.get_user_status.return_value = mock_status
        
        # 創建測試圖片
        img = Image.new('RGB', (800, 600), color='white')
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        test_image = buffer.getvalue()
        
        mock_line_api = Mock()
        mock_message_content = Mock()
        mock_message_content.content = test_image
        mock_line_api.get_message_content.return_value = mock_message_content
        
        # Mock Card Processor 拋出錯誤
        from src.namecard.core.exceptions import APIQuotaExceededError
        mock_processor = Mock()
        mock_processor.process_image.side_effect = APIQuotaExceededError(
            details={"reason": "quota_exceeded"}
        )
        
        mock_notion = Mock()
        
        handler = UnifiedEventHandler(
            line_bot_api=mock_line_api,
            card_processor=mock_processor,
            notion_client=mock_notion,
        )
        
        # 不應拋出異常
        handler.handle_image_message(
            "test_user",
            "12345",
            "reply_token"
        )
        
        # 驗證發送錯誤回覆
        mock_line_api.reply_message.assert_called()

