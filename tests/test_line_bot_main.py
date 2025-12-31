"""
Comprehensive tests for LINE Bot main.py webhook processing and event handling
Tests webhook validation, message routing, error handling, and all core functionality

Updated for multi-tenant architecture.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from flask import Flask

# Mock all external dependencies before importing
with patch('src.namecard.infrastructure.ai.card_processor.genai'):
    with patch('src.namecard.api.line_bot.main.default_line_bot_api') as mock_line_api:
        with patch('src.namecard.api.line_bot.main.default_handler') as mock_handler:
            with patch('src.namecard.api.line_bot.main.default_card_processor') as mock_card_processor:
                with patch('src.namecard.api.line_bot.main.default_notion_client') as mock_notion:
                    with patch('src.namecard.api.line_bot.main.default_event_handler') as mock_event_handler:
                        with patch('src.namecard.core.services.security.security_service') as mock_security:
                            from src.namecard.api.line_bot.main import (
                                app, callback, health_check, test_endpoint, debug_notion
                            )

from src.namecard.core.models.card import BusinessCard, BatchProcessResult
from datetime import datetime, timedelta


class TestWebhookEndpoint:
    """Test the main webhook endpoint /callback"""
    
    def setup_method(self):
        """Setup for each test"""
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
    
    def test_callback_missing_signature(self):
        """Test webhook with missing signature"""
        response = self.client.post('/callback', 
                                   data='test body',
                                   content_type='application/json')
        
        assert response.status_code == 200
        assert response.json['status'] == 'missing signature or body'
    
    def test_callback_missing_body(self):
        """Test webhook with missing body"""
        response = self.client.post('/callback',
                                   headers={'X-Line-Signature': 'test_signature'})
        
        assert response.status_code == 200
        assert response.json['status'] == 'missing signature or body'
    
    @patch('src.namecard.api.line_bot.main.settings')
    @patch('src.namecard.api.line_bot.main.security_service')
    def test_callback_production_signature_validation_success(self, mock_security, mock_settings):
        """Test webhook in production with valid signature"""
        mock_settings.flask_env = 'production'
        mock_settings.line_channel_secret = 'test_secret'
        mock_security.validate_line_signature.return_value = True
        mock_security.sanitize_input.return_value = 'sanitized_body'
        
        with patch('src.namecard.api.line_bot.main.handler') as mock_handler:
            mock_handler.handle.return_value = None
            
            response = self.client.post('/callback',
                                       data='test body',
                                       headers={'X-Line-Signature': 'valid_signature'})
            
            assert response.status_code == 200
            assert response.data.decode() == 'OK'
            mock_security.validate_line_signature.assert_called_once()
            mock_handler.handle.assert_called_once()
    
    @patch('src.namecard.api.line_bot.main.settings')
    @patch('src.namecard.api.line_bot.main.security_service')
    def test_callback_production_signature_validation_failure(self, mock_security, mock_settings):
        """Test webhook in production with invalid signature"""
        mock_settings.flask_env = 'production'
        mock_settings.line_channel_secret = 'test_secret'
        mock_security.validate_line_signature.return_value = False
        
        response = self.client.post('/callback',
                                   data='test body',
                                   headers={'X-Line-Signature': 'invalid_signature'})
        
        assert response.status_code == 200
        assert response.json['status'] == 'invalid signature'
        mock_security.log_security_event.assert_called_once()
    
    def test_callback_request_too_large(self):
        """Test webhook with oversized request"""
        large_body = 'x' * (1024 * 1024 + 1)  # > 1MB
        
        response = self.client.post('/callback',
                                   data=large_body,
                                   headers={'X-Line-Signature': 'test_signature'})
        
        assert response.status_code == 200
        assert response.json['status'] == 'request too large'
    
    @patch('src.namecard.api.line_bot.main.settings')
    @patch('src.namecard.api.line_bot.main.process_line_event_manually')
    def test_callback_non_production_manual_processing(self, mock_process_event, mock_settings):
        """Test webhook in non-production environment with manual processing"""
        mock_settings.flask_env = 'development'
        
        webhook_data = {
            "events": [
                {
                    "type": "message",
                    "message": {"type": "text", "text": "hello"},
                    "source": {"userId": "test_user"},
                    "replyToken": "test_reply_token"
                }
            ]
        }
        
        response = self.client.post('/callback',
                                   data=json.dumps(webhook_data),
                                   headers={'X-Line-Signature': 'test_signature'},
                                   content_type='application/json')
        
        assert response.status_code == 200
        assert response.data.decode() == 'OK'
        mock_process_event.assert_called_once()
    
    @patch('src.namecard.api.line_bot.main.settings')
    def test_callback_non_production_empty_body(self, mock_settings):
        """Test webhook with empty body in non-production"""
        mock_settings.flask_env = 'development'
        
        response = self.client.post('/callback',
                                   data='',
                                   headers={'X-Line-Signature': 'test_signature'})
        
        assert response.status_code == 200
        assert response.json['status'] == 'empty body'
    
    @patch('src.namecard.api.line_bot.main.settings')
    def test_callback_non_production_invalid_json(self, mock_settings):
        """Test webhook with invalid JSON in non-production"""
        mock_settings.flask_env = 'development'
        
        response = self.client.post('/callback',
                                   data='invalid json',
                                   headers={'X-Line-Signature': 'test_signature'})
        
        assert response.status_code == 200
        assert response.json['status'] == 'invalid json'
    
    @patch('src.namecard.api.line_bot.main.settings')
    def test_callback_non_production_no_events(self, mock_settings):
        """Test webhook with no events in non-production"""
        mock_settings.flask_env = 'development'
        
        webhook_data = {"events": []}
        
        response = self.client.post('/callback',
                                   data=json.dumps(webhook_data),
                                   headers={'X-Line-Signature': 'test_signature'},
                                   content_type='application/json')
        
        assert response.status_code == 200
        assert response.data.decode() == 'OK'
    
    @patch('src.namecard.api.line_bot.main.handler')
    def test_callback_line_sdk_exception(self, mock_handler):
        """Test webhook with LINE SDK exception"""
        from linebot.exceptions import InvalidSignatureError
        mock_handler.handle.side_effect = InvalidSignatureError('Invalid signature')
        
        response = self.client.post('/callback',
                                   data='test body',
                                   headers={'X-Line-Signature': 'test_signature'})
        
        assert response.status_code == 200
        assert response.json['status'] == 'invalid signature error'
    
    @patch('src.namecard.api.line_bot.main.handler')
    def test_callback_general_exception(self, mock_handler):
        """Test webhook with general exception"""
        mock_handler.handle.side_effect = Exception('General error')
        
        response = self.client.post('/callback',
                                   data='test body',
                                   headers={'X-Line-Signature': 'test_signature'})
        
        assert response.status_code == 200
        assert 'processing error' in response.json['status']
        assert response.json['error'] == 'General error'


class TestManualEventProcessing:
    """Test manual event processing functions"""
    
    @patch('src.namecard.api.line_bot.main.handle_text_message_manual')
    def test_process_line_event_manually_text_message(self, mock_handle_text):
        """Test manual processing of text message event"""
        event_data = {
            "type": "message",
            "message": {"type": "text", "text": "hello"},
            "source": {"userId": "test_user_123"},
            "replyToken": "test_reply_token"
        }
        
        process_line_event_manually(event_data)
        
        mock_handle_text.assert_called_once_with("test_user_123", "hello", "test_reply_token")
    
    @patch('src.namecard.api.line_bot.main.handle_image_message_manual')
    def test_process_line_event_manually_image_message(self, mock_handle_image):
        """Test manual processing of image message event"""
        event_data = {
            "type": "message",
            "message": {"type": "image", "id": "image_123"},
            "source": {"userId": "test_user_123"},
            "replyToken": "test_reply_token"
        }
        
        process_line_event_manually(event_data)
        
        mock_handle_image.assert_called_once_with("test_user_123", "image_123", "test_reply_token")
    
    def test_process_line_event_manually_missing_user_id(self):
        """Test manual processing with missing user ID"""
        event_data = {
            "type": "message",
            "message": {"type": "text", "text": "hello"},
            "source": {},  # Missing userId
            "replyToken": "test_reply_token"
        }
        
        # Should not raise exception, just log warning
        process_line_event_manually(event_data)
    
    def test_process_line_event_manually_missing_reply_token(self):
        """Test manual processing with missing reply token"""
        event_data = {
            "type": "message",
            "message": {"type": "text", "text": "hello"},
            "source": {"userId": "test_user_123"},
            # Missing replyToken
        }
        
        # Should not raise exception, just log warning
        process_line_event_manually(event_data)
    
    def test_process_line_event_manually_non_message_event(self):
        """Test manual processing of non-message events"""
        event_data = {
            "type": "follow",
            "source": {"userId": "test_user_123"},
            "replyToken": "test_reply_token"
        }
        
        # Should not raise exception, just ignore
        process_line_event_manually(event_data)
    
    def test_process_line_event_manually_unsupported_message_type(self):
        """Test manual processing of unsupported message types"""
        event_data = {
            "type": "message",
            "message": {"type": "video", "id": "video_123"},
            "source": {"userId": "test_user_123"},
            "replyToken": "test_reply_token"
        }
        
        # Should not raise exception, just log info
        process_line_event_manually(event_data)
    
    def test_process_line_event_manually_exception_handling(self):
        """Test exception handling in manual event processing"""
        invalid_event_data = "not_a_dict"
        
        # Should not raise exception, should log error
        process_line_event_manually(invalid_event_data)


class TestTextMessageHandling:
    """Test text message handling (both manual and LINE SDK versions)"""
    
    @patch('src.namecard.api.line_bot.main.user_service')
    @patch('src.namecard.api.line_bot.main.line_bot_api')
    @patch('src.namecard.api.line_bot.main.settings')
    def test_handle_text_message_manual_help_command(self, mock_settings, mock_line_api, mock_user_service):
        """Test manual handling of help command"""
        mock_settings.rate_limit_per_user = 50
        mock_user_service.check_rate_limit.return_value = True
        
        handle_text_message_manual("test_user", "help", "reply_token")
        
        mock_line_api.reply_message.assert_called_once()
        args, kwargs = mock_line_api.reply_message.call_args
        assert args[0] == "reply_token"
        # Check that help message contains expected content
        assert "名片識別系統" in args[1].text
    
    @patch('src.namecard.api.line_bot.main.user_service')
    @patch('src.namecard.api.line_bot.main.line_bot_api')
    @patch('src.namecard.api.line_bot.main.settings')
    def test_handle_text_message_manual_batch_start(self, mock_settings, mock_line_api, mock_user_service):
        """Test manual handling of batch start command"""
        mock_settings.rate_limit_per_user = 50
        mock_user_service.check_rate_limit.return_value = True
        mock_user_service.start_batch_mode.return_value = Mock()
        
        handle_text_message_manual("test_user", "批次", "reply_token")
        
        mock_user_service.start_batch_mode.assert_called_once_with("test_user")
        mock_line_api.reply_message.assert_called_once()
        args, kwargs = mock_line_api.reply_message.call_args
        assert "批次模式啟動" in args[1].text
    
    @patch('src.namecard.api.line_bot.main.user_service')
    @patch('src.namecard.api.line_bot.main.line_bot_api')
    @patch('src.namecard.api.line_bot.main.settings')
    def test_handle_text_message_manual_batch_end_success(self, mock_settings, mock_line_api, mock_user_service):
        """Test manual handling of batch end command with success"""
        mock_settings.rate_limit_per_user = 50
        mock_user_service.check_rate_limit.return_value = True
        
        # Mock successful batch result
        batch_result = BatchProcessResult(
            user_id="test_user",
            total_cards=5,
            successful_cards=4,
            failed_cards=1,
            started_at=datetime.now() - timedelta(minutes=5),
            completed_at=datetime.now(),
            errors=[]
        )
        mock_user_service.end_batch_mode.return_value = batch_result
        
        handle_text_message_manual("test_user", "結束批次", "reply_token")
        
        mock_user_service.end_batch_mode.assert_called_once_with("test_user")
        mock_line_api.reply_message.assert_called_once()
        args, kwargs = mock_line_api.reply_message.call_args
        assert "批次完成" in args[1].text
    
    @patch('src.namecard.api.line_bot.main.user_service')
    @patch('src.namecard.api.line_bot.main.line_bot_api')
    @patch('src.namecard.api.line_bot.main.settings')
    def test_handle_text_message_manual_batch_end_no_batch(self, mock_settings, mock_line_api, mock_user_service):
        """Test manual handling of batch end command with no active batch"""
        mock_settings.rate_limit_per_user = 50
        mock_user_service.check_rate_limit.return_value = True
        mock_user_service.end_batch_mode.return_value = None
        
        handle_text_message_manual("test_user", "結束批次", "reply_token")
        
        mock_line_api.reply_message.assert_called_once()
        args, kwargs = mock_line_api.reply_message.call_args
        assert "目前沒有進行中的批次處理" in args[1].text
    
    @patch('src.namecard.api.line_bot.main.user_service')
    @patch('src.namecard.api.line_bot.main.line_bot_api')
    @patch('src.namecard.api.line_bot.main.settings')
    def test_handle_text_message_manual_status_with_batch(self, mock_settings, mock_line_api, mock_user_service):
        """Test manual handling of status command with active batch"""
        mock_settings.rate_limit_per_user = 50
        mock_user_service.check_rate_limit.return_value = True
        mock_user_service.get_batch_status.return_value = "📦 批次進行中 - 3/10 張完成"
        
        handle_text_message_manual("test_user", "狀態", "reply_token")
        
        mock_line_api.reply_message.assert_called_once()
        args, kwargs = mock_line_api.reply_message.call_args
        assert "批次進行中" in args[1].text
    
    @patch('src.namecard.api.line_bot.main.user_service')
    @patch('src.namecard.api.line_bot.main.line_bot_api')
    @patch('src.namecard.api.line_bot.main.settings')
    def test_handle_text_message_manual_status_no_batch(self, mock_settings, mock_line_api, mock_user_service):
        """Test manual handling of status command without batch"""
        mock_settings.rate_limit_per_user = 50
        mock_user_service.check_rate_limit.return_value = True
        mock_user_service.get_batch_status.return_value = None
        
        from src.namecard.core.models.card import ProcessingStatus
        user_status = ProcessingStatus(user_id="test_user", daily_usage=15)
        mock_user_service.get_user_status.return_value = user_status
        
        handle_text_message_manual("test_user", "狀態", "reply_token")
        
        mock_line_api.reply_message.assert_called_once()
        args, kwargs = mock_line_api.reply_message.call_args
        assert "今日：15/50 張" in args[1].text
        assert "非批次模式" in args[1].text
    
    @patch('src.namecard.api.line_bot.main.user_service')
    @patch('src.namecard.api.line_bot.main.line_bot_api')
    @patch('src.namecard.api.line_bot.main.settings')
    def test_handle_text_message_manual_unknown_command(self, mock_settings, mock_line_api, mock_user_service):
        """Test manual handling of unknown command"""
        mock_settings.rate_limit_per_user = 50
        mock_user_service.check_rate_limit.return_value = True
        
        handle_text_message_manual("test_user", "unknown_command", "reply_token")
        
        mock_line_api.reply_message.assert_called_once()
        args, kwargs = mock_line_api.reply_message.call_args
        assert "不理解的指令" in args[1].text
    
    @patch('src.namecard.api.line_bot.main.user_service')
    @patch('src.namecard.api.line_bot.main.line_bot_api')
    @patch('src.namecard.api.line_bot.main.settings')
    def test_handle_text_message_manual_rate_limit_exceeded(self, mock_settings, mock_line_api, mock_user_service):
        """Test manual handling when rate limit is exceeded"""
        mock_settings.rate_limit_per_user = 50
        mock_user_service.check_rate_limit.return_value = False
        
        handle_text_message_manual("test_user", "help", "reply_token")
        
        mock_line_api.reply_message.assert_called_once()
        args, kwargs = mock_line_api.reply_message.call_args
        assert "今日使用量已達上限" in args[1].text
    
    @patch('src.namecard.api.line_bot.main.user_service')
    @patch('src.namecard.api.line_bot.main.line_bot_api')
    def test_handle_text_message_manual_exception_handling(self, mock_line_api, mock_user_service):
        """Test exception handling in manual text message processing"""
        mock_user_service.check_rate_limit.side_effect = Exception("Database error")
        
        handle_text_message_manual("test_user", "help", "reply_token")
        
        # Should send error message
        mock_line_api.reply_message.assert_called()
        args, kwargs = mock_line_api.reply_message.call_args
        assert "系統暫時無法處理" in args[1].text
    
    @patch('src.namecard.api.line_bot.main.user_service')
    @patch('src.namecard.api.line_bot.main.line_bot_api')
    def test_handle_text_message_manual_reply_token_used(self, mock_line_api, mock_user_service):
        """Test handling when reply token is already used"""
        from linebot.exceptions import LineBotApiError
        
        mock_user_service.check_rate_limit.return_value = True
        mock_line_api.reply_message.side_effect = [
            Exception("General error"),  # First call fails
            LineBotApiError("Reply token used")  # Error response fails too
        ]
        
        handle_text_message_manual("test_user", "help", "reply_token")
        
        # Should try push_message as fallback
        mock_line_api.push_message.assert_called()


class TestImageMessageHandling:
    """Test image message handling"""
    
    @patch('src.namecard.api.line_bot.main.user_service')
    @patch('src.namecard.api.line_bot.main.line_bot_api')
    @patch('src.namecard.api.line_bot.main.security_service')
    @patch('src.namecard.api.line_bot.main.card_processor')
    @patch('src.namecard.api.line_bot.main.notion_client')
    @patch('src.namecard.api.line_bot.main.settings')
    def test_handle_image_message_manual_success(self, mock_settings, mock_notion, mock_card_proc, 
                                                 mock_security, mock_line_api, mock_user_service):
        """Test successful manual image message handling"""
        # Setup mocks
        mock_settings.rate_limit_per_user = 50
        mock_settings.max_image_size = 10485760
        mock_user_service.check_rate_limit.return_value = True
        mock_security.validate_image_data.return_value = True
        
        # Mock image download
        mock_content = Mock()
        mock_content.iter_content.return_value = [b'fake_image_data']
        mock_line_api.get_message_content.return_value = mock_content
        
        # Mock card processing
        test_card = BusinessCard(
            name="Test User",
            company="Test Company", 
            phone="123-456-7890",
            line_user_id="test_user"
        )
        mock_card_proc.process_image.return_value = [test_card]
        
        # Mock Notion save
        mock_notion.save_business_card.return_value = "https://notion.so/page123"
        
        handle_image_message_manual("test_user", "message_123", "reply_token")
        
        # Verify flow
        mock_line_api.get_message_content.assert_called_once_with("message_123")
        mock_security.validate_image_data.assert_called_once()
        mock_card_proc.process_image.assert_called_once()
        mock_notion.save_business_card.assert_called_once_with(test_card)
        mock_user_service.increment_usage.assert_called_once_with("test_user")
        mock_user_service.add_card_to_batch.assert_called_once_with("test_user", test_card)
        
        # Check response
        mock_line_api.reply_message.assert_called_once()
        args, kwargs = mock_line_api.reply_message.call_args
        assert "成功 1/1 張" in args[1].text
    
    @patch('src.namecard.api.line_bot.main.user_service')
    @patch('src.namecard.api.line_bot.main.line_bot_api')
    @patch('src.namecard.api.line_bot.main.settings')
    def test_handle_image_message_manual_rate_limit_exceeded(self, mock_settings, mock_line_api, mock_user_service):
        """Test image handling when rate limit is exceeded"""
        mock_settings.rate_limit_per_user = 50
        mock_user_service.check_rate_limit.return_value = False
        
        handle_image_message_manual("test_user", "message_123", "reply_token")
        
        mock_line_api.reply_message.assert_called_once()
        args, kwargs = mock_line_api.reply_message.call_args
        assert "今日使用量已達上限" in args[1].text
    
    @patch('src.namecard.api.line_bot.main.user_service')
    @patch('src.namecard.api.line_bot.main.line_bot_api')
    @patch('src.namecard.api.line_bot.main.security_service')
    @patch('src.namecard.api.line_bot.main.settings')
    def test_handle_image_message_manual_invalid_image(self, mock_settings, mock_security, 
                                                       mock_line_api, mock_user_service):
        """Test image handling with invalid image data"""
        mock_settings.rate_limit_per_user = 50
        mock_settings.max_image_size = 10485760
        mock_user_service.check_rate_limit.return_value = True
        mock_security.validate_image_data.return_value = False
        
        # Mock image download
        mock_content = Mock()
        mock_content.iter_content.return_value = [b'invalid_image_data']
        mock_line_api.get_message_content.return_value = mock_content
        
        handle_image_message_manual("test_user", "message_123", "reply_token")
        
        # Verify security logging
        mock_security.log_security_event.assert_called_once_with(
            "invalid_image_upload",
            "test_user",
            {
                "image_size": len(b'invalid_image_data'),
                "max_allowed": 10485760,
                "message_id": "message_123"
            }
        )
        
        # Check error response
        mock_line_api.reply_message.assert_called_once()
        args, kwargs = mock_line_api.reply_message.call_args
        assert "圖片檔案無效或過大" in args[1].text
    
    @patch('src.namecard.api.line_bot.main.user_service')
    @patch('src.namecard.api.line_bot.main.line_bot_api')
    @patch('src.namecard.api.line_bot.main.security_service')
    @patch('src.namecard.api.line_bot.main.card_processor')
    @patch('src.namecard.api.line_bot.main.settings')
    def test_handle_image_message_manual_no_cards_detected(self, mock_settings, mock_card_proc,
                                                           mock_security, mock_line_api, mock_user_service):
        """Test image handling when no cards are detected"""
        mock_settings.rate_limit_per_user = 50
        mock_user_service.check_rate_limit.return_value = True
        mock_security.validate_image_data.return_value = True
        
        # Mock image download
        mock_content = Mock()
        mock_content.iter_content.return_value = [b'fake_image_data']
        mock_line_api.get_message_content.return_value = mock_content
        
        # No cards detected
        mock_card_proc.process_image.return_value = []
        
        handle_image_message_manual("test_user", "message_123", "reply_token")
        
        mock_line_api.reply_message.assert_called_once()
        args, kwargs = mock_line_api.reply_message.call_args
        assert "無法識別名片內容" in args[1].text
    
    @patch('src.namecard.api.line_bot.main.user_service')
    @patch('src.namecard.api.line_bot.main.line_bot_api')
    @patch('src.namecard.api.line_bot.main.security_service')
    @patch('src.namecard.api.line_bot.main.card_processor')
    @patch('src.namecard.api.line_bot.main.notion_client')
    @patch('src.namecard.api.line_bot.main.settings')
    def test_handle_image_message_manual_multiple_cards(self, mock_settings, mock_notion, mock_card_proc,
                                                        mock_security, mock_line_api, mock_user_service):
        """Test image handling with multiple cards"""
        mock_settings.rate_limit_per_user = 50
        mock_user_service.check_rate_limit.return_value = True
        mock_security.validate_image_data.return_value = True
        
        # Mock image download
        mock_content = Mock()
        mock_content.iter_content.return_value = [b'fake_image_data']
        mock_line_api.get_message_content.return_value = mock_content
        
        # Multiple cards
        cards = [
            BusinessCard(name="User 1", company="Company 1", phone="111", line_user_id="test_user"),
            BusinessCard(name="User 2", company="Company 2", phone="222", line_user_id="test_user"),
            BusinessCard(name="User 3", company="Company 3", phone="333", line_user_id="test_user"),
        ]
        mock_card_proc.process_image.return_value = cards
        
        # Mock successful saves
        mock_notion.save_business_card.return_value = "https://notion.so/page"
        
        handle_image_message_manual("test_user", "message_123", "reply_token")
        
        # Check response mentions multiple cards
        mock_line_api.reply_message.assert_called_once()
        args, kwargs = mock_line_api.reply_message.call_args
        assert "成功 3/3 張" in args[1].text
        assert "共 3 張名片" in args[1].text
    
    @patch('src.namecard.api.line_bot.main.user_service')
    @patch('src.namecard.api.line_bot.main.line_bot_api')
    @patch('src.namecard.api.line_bot.main.security_service')
    @patch('src.namecard.api.line_bot.main.card_processor')
    @patch('src.namecard.api.line_bot.main.notion_client')
    @patch('src.namecard.api.line_bot.main.settings')
    def test_handle_image_message_manual_partial_success(self, mock_settings, mock_notion, mock_card_proc,
                                                         mock_security, mock_line_api, mock_user_service):
        """Test image handling with partial success"""
        mock_settings.rate_limit_per_user = 50
        mock_user_service.check_rate_limit.return_value = True
        mock_security.validate_image_data.return_value = True
        
        # Mock image download
        mock_content = Mock()
        mock_content.iter_content.return_value = [b'fake_image_data']
        mock_line_api.get_message_content.return_value = mock_content
        
        # Multiple cards
        cards = [
            BusinessCard(name="Success", company="Success Co", phone="111", line_user_id="test_user"),
            BusinessCard(name="Failure", company="Failure Co", phone="222", line_user_id="test_user"),
        ]
        mock_card_proc.process_image.return_value = cards
        
        # Mock mixed results
        mock_notion.save_business_card.side_effect = ["https://notion.so/page", None]
        
        handle_image_message_manual("test_user", "message_123", "reply_token")
        
        # Check response shows partial success
        mock_line_api.reply_message.assert_called_once()
        args, kwargs = mock_line_api.reply_message.call_args
        assert "成功 1/2 張" in args[1].text


class TestUtilityFunctions:
    """Test utility functions"""
    
    def test_create_help_message(self):
        """Test help message creation"""
        message = create_help_message()
        
        assert "名片識別系統" in message.text
        assert "上傳名片照片" in message.text
        assert "批次" in message.text
        assert "狀態" in message.text
        assert message.quick_reply is not None
        assert len(message.quick_reply.items) == 2
    
    def test_create_batch_summary_message(self):
        """Test batch summary message creation"""
        batch_result = BatchProcessResult(
            user_id="test_user",
            total_cards=10,
            successful_cards=8,
            failed_cards=2,
            started_at=datetime.now() - timedelta(minutes=5, seconds=30),
            completed_at=datetime.now(),
            errors=["Error processing card 1", "Error processing card 2"]
        )
        
        message = create_batch_summary_message(batch_result)
        
        assert "批次完成" in message.text
        assert "總計：10 張" in message.text
        assert "成功：8 張 (80%)" in message.text
        assert "時間：5:30" in message.text
        assert "Error processing card 1" in message.text
    
    def test_create_batch_summary_message_no_errors(self):
        """Test batch summary message without errors"""
        batch_result = BatchProcessResult(
            user_id="test_user",
            total_cards=5,
            successful_cards=5,
            failed_cards=0,
            started_at=datetime.now() - timedelta(minutes=2),
            completed_at=datetime.now(),
            errors=[]
        )
        
        message = create_batch_summary_message(batch_result)
        
        assert "批次完成" in message.text
        assert "總計：5 張" in message.text
        assert "成功：5 張 (100%)" in message.text
        assert "⚠️" not in message.text  # No error section


class TestAPIEndpoints:
    """Test API endpoints"""
    
    def setup_method(self):
        """Setup for each test"""
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
    
    def test_health_check_endpoint(self):
        """Test health check endpoint"""
        response = self.client.get('/health')
        
        assert response.status_code == 200
        data = response.json
        assert data['status'] == 'healthy'
        assert data['service'] == 'LINE Bot 名片識別系統'
        assert data['version'] == '1.0.0'
        assert 'timestamp' in data
    
    @patch('src.namecard.api.line_bot.main.settings')
    def test_test_endpoint(self, mock_settings):
        """Test configuration test endpoint"""
        mock_settings.rate_limit_per_user = 50
        mock_settings.batch_size_limit = 10
        mock_settings.max_image_size = 10485760
        mock_settings.flask_env = 'development'
        mock_settings.line_channel_access_token = 'test_token_1234567890'
        mock_settings.line_channel_secret = 'test_secret_1234567890'
        mock_settings.google_api_key = 'test_google_key_1234567890'
        mock_settings.notion_api_key = 'test_notion_key_1234567890'
        mock_settings.notion_database_id = 'test_db_id_1234567890'
        mock_settings.sentry_dsn = 'https://test@sentry.io/project'
        
        response = self.client.get('/test')
        
        assert response.status_code == 200
        data = response.json
        assert data['message'] == 'LINE Bot 服務運行正常'
        assert data['config']['rate_limit'] == 50
        assert data['config']['batch_limit'] == 10
        assert data['config']['max_image_size'] == '10MB'
        assert data['config']['flask_env'] == 'development'
        assert data['config']['line_channel_configured'] is True
        assert data['config']['google_api_configured'] is True
        assert data['config']['notion_api_configured'] is True
        assert data['config']['sentry_configured'] is True
    
    def test_debug_webhook_endpoint(self):
        """Test debug webhook endpoint"""
        test_data = {"test": "data"}
        
        response = self.client.post('/debug/webhook',
                                   data=json.dumps(test_data),
                                   content_type='application/json',
                                   headers={'Custom-Header': 'test_value'})
        
        assert response.status_code == 200
        data = response.json
        assert data['status'] == 'received'
        assert 'headers' in data
        assert 'Custom-Header' in data['headers']
        assert 'body_length' in data
    
    @patch('src.namecard.api.line_bot.main.settings')
    def test_debug_sentry_endpoint(self, mock_settings):
        """Test debug sentry endpoint"""
        mock_settings.sentry_dsn = 'https://test@sentry.io/project'
        mock_settings.flask_env = 'development'
        
        with patch('os.getenv') as mock_getenv:
            mock_getenv.return_value = 'https://test@sentry.io/project'
            with patch('os.environ.keys') as mock_keys:
                mock_keys.return_value = ['SENTRY_DSN', 'OTHER_VAR']
                
                response = self.client.get('/debug/sentry')
        
        assert response.status_code == 200
        data = response.json
        assert data['sentry_dsn_env'] is True
        assert data['sentry_dsn_settings'] is True
        assert data['flask_env'] == 'development'
        assert 'SENTRY_DSN' in data['all_env_vars']
    
    @patch('src.namecard.api.line_bot.main.notion_client')
    @patch('src.namecard.api.line_bot.main.settings')
    def test_debug_notion_endpoint_success(self, mock_settings, mock_notion):
        """Test debug notion endpoint success"""
        mock_settings.notion_database_id = 'test_db_id'
        
        # Mock database info
        mock_database_info = {
            'title': [{'plain_text': 'Test Database'}],
            'properties': {
                '姓名': {'type': 'title', 'id': 'name_id'},
                '公司': {'type': 'rich_text', 'id': 'company_id'},
                '狀態': {
                    'type': 'select',
                    'id': 'status_id',
                    'select': {
                        'options': [
                            {'name': '進行中'},
                            {'name': '完成'}
                        ]
                    }
                }
            }
        }
        
        mock_notion.client.databases.retrieve.return_value = mock_database_info
        
        response = self.client.get('/debug/notion')
        
        assert response.status_code == 200
        data = response.json
        assert data['status'] == 'success'
        assert data['database_id'] == 'test_db_id'
        assert data['database_title'] == 'Test Database'
        assert '姓名' in data['properties']
        assert data['properties']['姓名']['type'] == 'title'
        assert data['properties']['狀態']['type'] == 'select'
        assert '進行中' in data['properties']['狀態']['options']
    
    @patch('src.namecard.api.line_bot.main.notion_client')
    @patch('src.namecard.api.line_bot.main.settings')
    def test_debug_notion_endpoint_error(self, mock_settings, mock_notion):
        """Test debug notion endpoint error"""
        mock_settings.notion_database_id = 'test_db_id'
        mock_notion.client.databases.retrieve.side_effect = Exception("Database not found")
        
        response = self.client.get('/debug/notion')
        
        assert response.status_code == 200
        data = response.json
        assert data['status'] == 'error'
        assert data['error'] == 'Database not found'
        assert data['database_id'] == 'test_db_id'


class TestErrorHandlingScenarios:
    """Test various error handling scenarios"""
    
    @patch('src.namecard.api.line_bot.main.user_service')
    @patch('src.namecard.api.line_bot.main.line_bot_api')
    def test_text_message_service_unavailable(self, mock_line_api, mock_user_service):
        """Test text message handling when user service is unavailable"""
        mock_user_service.check_rate_limit.side_effect = Exception("Service unavailable")
        
        handle_text_message_manual("test_user", "help", "reply_token")
        
        # Should send error message
        mock_line_api.reply_message.assert_called()
        args, kwargs = mock_line_api.reply_message.call_args
        assert "系統暫時無法處理" in args[1].text
    
    @patch('src.namecard.api.line_bot.main.user_service')
    @patch('src.namecard.api.line_bot.main.line_bot_api')
    def test_image_message_download_failure(self, mock_line_api, mock_user_service):
        """Test image message handling when download fails"""
        mock_user_service.check_rate_limit.return_value = True
        mock_line_api.get_message_content.side_effect = Exception("Download failed")
        
        handle_image_message_manual("test_user", "message_123", "reply_token")
        
        # Should send error message
        mock_line_api.reply_message.assert_called()
        args, kwargs = mock_line_api.reply_message.call_args
        assert "處理失敗" in args[1].text
    
    @patch('src.namecard.api.line_bot.main.user_service')
    @patch('src.namecard.api.line_bot.main.line_bot_api')
    @patch('src.namecard.api.line_bot.main.security_service')
    @patch('src.namecard.api.line_bot.main.card_processor')
    @patch('src.namecard.api.line_bot.main.settings')
    def test_image_message_ai_processing_failure(self, mock_settings, mock_card_proc,
                                                mock_security, mock_line_api, mock_user_service):
        """Test image message handling when AI processing fails"""
        mock_settings.rate_limit_per_user = 50
        mock_user_service.check_rate_limit.return_value = True
        mock_security.validate_image_data.return_value = True
        
        # Mock image download
        mock_content = Mock()
        mock_content.iter_content.return_value = [b'fake_image_data']
        mock_line_api.get_message_content.return_value = mock_content
        
        # AI processing fails
        mock_card_proc.process_image.side_effect = Exception("AI service unavailable")
        
        handle_image_message_manual("test_user", "message_123", "reply_token")
        
        # Should send error message
        mock_line_api.reply_message.assert_called()
        args, kwargs = mock_line_api.reply_message.call_args
        assert "處理失敗" in args[1].text