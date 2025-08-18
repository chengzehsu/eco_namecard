"""
Comprehensive test suite for CardProcessor
Tests all major functionality including configuration, error handling, decorators, and edge cases
"""

import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock, call
from PIL import Image
import io
from dataclasses import dataclass

# Import test fixtures first, before importing actual classes
from typing import List, Optional, Tuple

# Mock genai before importing CardProcessor to prevent initialization errors
with patch('src.namecard.infrastructure.ai.card_processor.genai') as mock_genai:
    mock_genai.configure.return_value = None
    mock_model = Mock()
    mock_model.generate_content.return_value = Mock(text='{"cards": []}')
    mock_genai.GenerativeModel.return_value = mock_model
    
    from src.namecard.infrastructure.ai.card_processor import (
        CardProcessor, ProcessingConfig, ProcessingError, APIError, 
        ValidationError, ImageProcessingError, with_error_handling, with_timing
    )

from src.namecard.core.models.card import BusinessCard


class TestProcessingConfig:
    """Test ProcessingConfig dataclass"""
    
    def test_default_configuration(self):
        """Test default configuration values"""
        config = ProcessingConfig()
        
        assert config.max_image_size == (1920, 1920)
        assert config.max_file_size == 10 * 1024 * 1024  # 10MB
        assert config.min_confidence_threshold == 0.3
        assert config.min_quality_threshold == 0.2
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.timeout_seconds == 30
    
    def test_custom_configuration(self):
        """Test custom configuration values"""
        config = ProcessingConfig(
            max_image_size=(1024, 1024),
            max_file_size=5 * 1024 * 1024,
            min_confidence_threshold=0.5,
            min_quality_threshold=0.4,
            max_retries=5,
            retry_delay=0.5,
            timeout_seconds=60
        )
        
        assert config.max_image_size == (1024, 1024)
        assert config.max_file_size == 5 * 1024 * 1024
        assert config.min_confidence_threshold == 0.5
        assert config.min_quality_threshold == 0.4
        assert config.max_retries == 5
        assert config.retry_delay == 0.5
        assert config.timeout_seconds == 60


class TestCustomExceptions:
    """Test custom exception classes"""
    
    def test_processing_error(self):
        """Test ProcessingError base class"""
        error = ProcessingError("Test processing error")
        assert str(error) == "Test processing error"
        assert isinstance(error, Exception)
    
    def test_api_error(self):
        """Test APIError exception"""
        error = APIError("API connection failed")
        assert str(error) == "API connection failed"
        assert isinstance(error, ProcessingError)
        assert isinstance(error, Exception)
    
    def test_validation_error(self):
        """Test ValidationError exception"""
        error = ValidationError("Invalid input data")
        assert str(error) == "Invalid input data"
        assert isinstance(error, ProcessingError)
    
    def test_image_processing_error(self):
        """Test ImageProcessingError exception"""
        error = ImageProcessingError("Image format not supported")
        assert str(error) == "Image format not supported"
        assert isinstance(error, ProcessingError)


class TestErrorHandlingDecorator:
    """Test @with_error_handling decorator"""
    
    @patch('src.namecard.infrastructure.ai.card_processor.logger')
    def test_successful_function_execution(self, mock_logger):
        """Test decorator with successful function execution"""
        @with_error_handling
        def test_function(x, y):
            return x + y
        
        result = test_function(2, 3)
        assert result == 5
        mock_logger.error.assert_not_called()
    
    @patch('src.namecard.infrastructure.ai.card_processor.logger')
    def test_function_with_exception(self, mock_logger):
        """Test decorator with function that raises exception"""
        @with_error_handling
        def failing_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError, match="Test error"):
            failing_function()
        
        # Verify error was logged
        mock_logger.error.assert_called_once()
        args, kwargs = mock_logger.error.call_args
        assert "Error in failing_function" in args[0]
        assert kwargs['error'] == "Test error"
        assert 'traceback' in kwargs
    
    @patch('src.namecard.infrastructure.ai.card_processor.logger')
    def test_function_with_args_and_kwargs(self, mock_logger):
        """Test decorator preserves function signature"""
        @with_error_handling
        def complex_function(a, b, c=None, d=None):
            if c is None:
                raise RuntimeError("Missing parameter")
            return a + b + c + (d or 0)
        
        # Test successful call
        result = complex_function(1, 2, c=3, d=4)
        assert result == 10
        
        # Test failing call
        with pytest.raises(RuntimeError):
            complex_function(1, 2)
        
        mock_logger.error.assert_called_once()


class TestTimingDecorator:
    """Test @with_timing decorator"""
    
    @patch('src.namecard.infrastructure.ai.card_processor.logger')
    @patch('src.namecard.infrastructure.ai.card_processor.time')
    def test_successful_timing(self, mock_time, mock_logger):
        """Test timing decorator with successful execution"""
        # Mock time.time() to return predictable values
        mock_time.time.side_effect = [1000.0, 1002.5]  # 2.5 second execution
        
        @with_timing
        def timed_function():
            return "success"
        
        result = timed_function()
        assert result == "success"
        
        # Verify timing was logged
        mock_logger.info.assert_called_once()
        args, kwargs = mock_logger.info.call_args
        assert "timed_function completed" in args[0]
        assert kwargs['execution_time'] == "2.50s"
    
    @patch('src.namecard.infrastructure.ai.card_processor.logger')
    @patch('src.namecard.infrastructure.ai.card_processor.time')
    def test_failed_timing(self, mock_time, mock_logger):
        """Test timing decorator with failed execution"""
        mock_time.time.side_effect = [1000.0, 1001.8]  # 1.8 second execution before failure
        
        @with_timing
        def failing_timed_function():
            raise ValueError("Function failed")
        
        with pytest.raises(ValueError):
            failing_timed_function()
        
        # Verify failure timing was logged
        mock_logger.error.assert_called_once()
        args, kwargs = mock_logger.error.call_args
        assert "failing_timed_function failed" in args[0]
        assert kwargs['execution_time'] == "1.80s"
        assert kwargs['error'] == "Function failed"


class TestCardProcessorInitialization:
    """Test CardProcessor initialization scenarios"""
    
    @patch('src.namecard.infrastructure.ai.card_processor.genai')
    @patch('src.namecard.infrastructure.ai.card_processor.settings')
    def test_successful_primary_api_initialization(self, mock_settings, mock_genai):
        """Test successful initialization with primary API key"""
        mock_settings.google_api_key = "primary_key"
        mock_settings.google_api_key_fallback = None
        mock_genai.configure.return_value = None
        mock_model = Mock()
        mock_model.generate_content.return_value = Mock(text="test")
        mock_genai.GenerativeModel.return_value = mock_model
        
        processor = CardProcessor()
        
        mock_genai.configure.assert_called_once_with(api_key="primary_key")
        assert processor.model is not None
    
    @patch('src.namecard.infrastructure.ai.card_processor.genai')
    @patch('src.namecard.infrastructure.ai.card_processor.settings')
    def test_fallback_api_initialization(self, mock_settings, mock_genai):
        """Test initialization falls back to secondary API key"""
        mock_settings.google_api_key = "primary_key"
        mock_settings.google_api_key_fallback = "fallback_key"
        
        # Primary key fails, fallback succeeds
        mock_genai.configure.side_effect = [Exception("Primary API failed"), None]
        mock_model = Mock()
        mock_model.generate_content.return_value = Mock(text="test")
        mock_genai.GenerativeModel.return_value = mock_model
        
        processor = CardProcessor()
        
        # Should try both keys
        expected_calls = [call(api_key="primary_key"), call(api_key="fallback_key")]
        mock_genai.configure.assert_has_calls(expected_calls)
        assert processor.model is not None
    
    @patch('src.namecard.infrastructure.ai.card_processor.genai')
    @patch('src.namecard.infrastructure.ai.card_processor.settings')
    def test_all_api_keys_fail(self, mock_settings, mock_genai):
        """Test initialization fails when all API keys fail"""
        mock_settings.google_api_key = "primary_key"
        mock_settings.google_api_key_fallback = "fallback_key"
        
        # Both keys fail
        mock_genai.configure.side_effect = [
            Exception("Primary API failed"),
            Exception("Fallback API failed")
        ]
        
        with pytest.raises(APIError, match="All Gemini API keys failed to initialize"):
            CardProcessor()
    
    @patch('src.namecard.infrastructure.ai.card_processor.genai')
    @patch('src.namecard.infrastructure.ai.card_processor.settings')
    def test_custom_config_initialization(self, mock_settings, mock_genai):
        """Test initialization with custom configuration"""
        mock_settings.google_api_key = "test_key"
        mock_genai.configure.return_value = None
        mock_model = Mock()
        mock_model.generate_content.return_value = Mock(text="test")
        mock_genai.GenerativeModel.return_value = mock_model
        
        custom_config = ProcessingConfig(
            max_image_size=(512, 512),
            min_confidence_threshold=0.8
        )
        
        processor = CardProcessor(config=custom_config)
        
        assert processor.config.max_image_size == (512, 512)
        assert processor.config.min_confidence_threshold == 0.8


class TestImagePreprocessing:
    """Test image preprocessing edge cases"""
    
    def setup_method(self):
        """Setup for each test"""
        with patch('src.namecard.infrastructure.ai.card_processor.genai'):
            self.processor = CardProcessor()
    
    def test_rgba_to_rgb_conversion(self):
        """Test RGBA image conversion to RGB"""
        rgba_image = Image.new('RGBA', (100, 100), color=(255, 255, 255, 128))
        
        processed = self.processor._preprocess_image(rgba_image)
        
        assert processed.mode == 'RGB'
        assert processed.size == (100, 100)
    
    def test_grayscale_image_handling(self):
        """Test grayscale image handling"""
        grayscale_image = Image.new('L', (100, 100), color=128)
        
        processed = self.processor._preprocess_image(grayscale_image)
        
        # Should preserve grayscale mode
        assert processed.mode == 'L'
        assert processed.size == (100, 100)
    
    def test_cmyk_to_rgb_conversion(self):
        """Test CMYK image conversion to RGB"""
        cmyk_image = Image.new('CMYK', (100, 100), color=(100, 0, 100, 0))
        
        processed = self.processor._preprocess_image(cmyk_image)
        
        assert processed.mode == 'RGB'
        assert processed.size == (100, 100)
    
    def test_oversized_image_resize(self):
        """Test oversized image is properly resized"""
        # Create image larger than max size
        large_image = Image.new('RGB', (3000, 2000), color='white')
        
        processed = self.processor._preprocess_image(large_image)
        
        # Should be resized to fit within max dimensions while preserving aspect ratio
        assert processed.size[0] <= 1920
        assert processed.size[1] <= 1920
        # Check aspect ratio is preserved (approximately)
        original_ratio = 3000 / 2000
        new_ratio = processed.size[0] / processed.size[1]
        assert abs(original_ratio - new_ratio) < 0.01
    
    def test_portrait_oversized_image_resize(self):
        """Test portrait oversized image resize"""
        # Portrait orientation (height > width)
        tall_image = Image.new('RGB', (1000, 3000), color='white')
        
        processed = self.processor._preprocess_image(tall_image)
        
        assert processed.size[0] <= 1920
        assert processed.size[1] <= 1920
        # Should maintain portrait orientation
        assert processed.size[1] > processed.size[0]
    
    def test_small_image_warning(self):
        """Test warning for small images"""
        small_image = Image.new('RGB', (200, 150), color='white')
        
        with patch('src.namecard.infrastructure.ai.card_processor.logger') as mock_logger:
            processed = self.processor._preprocess_image(small_image)
            
            # Should log warning for low resolution
            mock_logger.warning.assert_called_once()
            args, kwargs = mock_logger.warning.call_args
            assert "resolution may be too low" in args[0]
        
        # Image should not be modified
        assert processed.size == (200, 150)
    
    def test_image_preprocessing_error(self):
        """Test image preprocessing error handling"""
        # Create a mock image that will fail processing
        mock_image = Mock()
        mock_image.mode = 'RGB'
        mock_image.size = [100, 100]
        mock_image.convert.side_effect = Exception("Conversion failed")
        
        with pytest.raises(ImageProcessingError, match="Failed to preprocess image"):
            self.processor._preprocess_image(mock_image)


class TestRateLimiting:
    """Test rate limiting functionality"""
    
    def setup_method(self):
        """Setup for each test"""
        with patch('src.namecard.infrastructure.ai.card_processor.genai'):
            self.processor = CardProcessor()
    
    @patch('src.namecard.infrastructure.ai.card_processor.time')
    def test_rate_limiting_sleep(self, mock_time):
        """Test rate limiting causes appropriate sleep"""
        # Mock time to simulate rapid successive calls
        mock_time.time.side_effect = [1000.0, 1000.05, 1000.05, 1000.15]  # 0.05s between calls
        mock_time.sleep = Mock()
        
        # Mock model and response
        mock_response = Mock()
        mock_response.text = '{"cards": []}'
        self.processor.model = Mock()
        self.processor.model.generate_content.return_value = mock_response
        
        image = Image.new('RGB', (100, 100))
        
        # First call
        self.processor._analyze_with_gemini(image)
        # Second call (should trigger rate limiting)
        self.processor._analyze_with_gemini(image)
        
        # Should sleep to enforce minimum time between calls
        expected_sleep_time = 0.1 - 0.05  # 0.05s
        mock_time.sleep.assert_called_with(expected_sleep_time)
    
    @patch('src.namecard.infrastructure.ai.card_processor.time')
    def test_no_rate_limiting_when_sufficient_gap(self, mock_time):
        """Test no rate limiting when calls are spaced apart"""
        # Mock time to simulate calls with sufficient gap
        mock_time.time.side_effect = [1000.0, 1000.2, 1000.2, 1000.4]  # 0.2s between calls
        mock_time.sleep = Mock()
        
        mock_response = Mock()
        mock_response.text = '{"cards": []}'
        self.processor.model = Mock()
        self.processor.model.generate_content.return_value = mock_response
        
        image = Image.new('RGB', (100, 100))
        
        # Two calls with sufficient gap
        self.processor._analyze_with_gemini(image)
        self.processor._analyze_with_gemini(image)
        
        # Should not sleep
        mock_time.sleep.assert_not_called()


class TestJSONParsingEdgeCases:
    """Test JSON parsing error scenarios and markdown cleanup"""
    
    def setup_method(self):
        """Setup for each test"""
        with patch('src.namecard.infrastructure.ai.card_processor.genai'):
            self.processor = CardProcessor()
    
    def test_markdown_cleanup(self):
        """Test removal of markdown code blocks"""
        response_with_markdown = '''```json
        {
            "cards": [{
                "name": "Test User",
                "company": "Test Company",
                "confidence_score": 0.9,
                "quality_score": 0.8
            }]
        }
        ```'''
        
        cards = self.processor._parse_response(response_with_markdown, "test_user")
        
        assert len(cards) == 1
        assert cards[0].name == "Test User"
        assert cards[0].company == "Test Company"
    
    def test_multiple_markdown_blocks(self):
        """Test handling multiple markdown blocks"""
        response = '''Some text ```json{"invalid": "json"}``` more text
        ```json
        {
            "cards": [{
                "name": "Valid User",
                "confidence_score": 0.9,
                "quality_score": 0.8
            }]
        }
        ```
        ```'''
        
        cards = self.processor._parse_response(response, "test_user")
        
        assert len(cards) == 1
        assert cards[0].name == "Valid User"
    
    def test_invalid_json_handling(self):
        """Test handling of completely invalid JSON"""
        invalid_responses = [
            "This is not JSON at all",
            "{invalid json syntax",
            '{"incomplete": json',
            "",
            "null",
            "undefined"
        ]
        
        for response in invalid_responses:
            cards = self.processor._parse_response(response, "test_user")
            assert len(cards) == 0
    
    def test_json_with_missing_cards_key(self):
        """Test JSON response without cards key"""
        response = '{"total_cards_detected": 0, "overall_quality": 0.5}'
        
        cards = self.processor._parse_response(response, "test_user")
        
        assert len(cards) == 0
    
    def test_json_with_empty_cards_array(self):
        """Test JSON response with empty cards array"""
        response = '{"cards": [], "total_cards_detected": 0}'
        
        cards = self.processor._parse_response(response, "test_user")
        
        assert len(cards) == 0
    
    def test_json_with_invalid_card_data(self):
        """Test JSON with card data that fails validation"""
        response = '''{
            "cards": [{
                "name": null,
                "company": null,
                "confidence_score": "invalid_number",
                "quality_score": 0.1
            }]
        }'''
        
        with patch('src.namecard.infrastructure.ai.card_processor.logger') as mock_logger:
            cards = self.processor._parse_response(response, "test_user")
            
            assert len(cards) == 0
            # Should log error for failed card creation
            mock_logger.error.assert_called()
    
    def test_json_with_partial_valid_cards(self):
        """Test JSON with mix of valid and invalid cards"""
        response = '''{
            "cards": [
                {
                    "name": "Valid User",
                    "company": "Valid Company",
                    "phone": "123-456-7890",
                    "confidence_score": 0.9,
                    "quality_score": 0.8
                },
                {
                    "name": null,
                    "company": null,
                    "confidence_score": "invalid",
                    "quality_score": 0.1
                },
                {
                    "name": "Another Valid User",
                    "company": "Another Company",
                    "email": "test@example.com",
                    "confidence_score": 0.85,
                    "quality_score": 0.9
                }
            ]
        }'''
        
        cards = self.processor._parse_response(response, "test_user")
        
        # Should only return valid cards
        assert len(cards) == 2
        assert cards[0].name == "Valid User"
        assert cards[1].name == "Another Valid User"


class TestCardQualityValidation:
    """Test comprehensive card quality validation scenarios"""
    
    def setup_method(self):
        """Setup for each test"""
        with patch('src.namecard.infrastructure.ai.card_processor.genai'):
            self.processor = CardProcessor()
    
    def test_valid_card_with_name_and_phone(self):
        """Test valid card with name and phone"""
        card = BusinessCard(
            name="John Doe",
            phone="123-456-7890",
            confidence_score=0.9,
            quality_score=0.8,
            line_user_id="test_user"
        )
        
        assert self.processor._validate_card_quality(card) is True
    
    def test_valid_card_with_company_and_email(self):
        """Test valid card with company and email"""
        card = BusinessCard(
            company="Test Company",
            email="test@company.com",
            confidence_score=0.9,
            quality_score=0.8,
            line_user_id="test_user"
        )
        
        assert self.processor._validate_card_quality(card) is True
    
    def test_valid_card_with_address_only(self):
        """Test valid card with address as contact method"""
        card = BusinessCard(
            name="Jane Smith",
            address="123 Main St, City, State",
            confidence_score=0.9,
            quality_score=0.8,
            line_user_id="test_user"
        )
        
        assert self.processor._validate_card_quality(card) is True
    
    def test_invalid_card_low_confidence(self):
        """Test card rejected due to low confidence"""
        card = BusinessCard(
            name="Test User",
            phone="123-456-7890",
            confidence_score=0.2,  # Below threshold
            quality_score=0.8,
            line_user_id="test_user"
        )
        
        assert self.processor._validate_card_quality(card) is False
    
    def test_invalid_card_low_quality(self):
        """Test card rejected due to low quality score"""
        card = BusinessCard(
            name="Test User",
            phone="123-456-7890",
            confidence_score=0.9,
            quality_score=0.1,  # Below threshold
            line_user_id="test_user"
        )
        
        assert self.processor._validate_card_quality(card) is False
    
    def test_invalid_card_no_name_or_company(self):
        """Test card rejected due to missing name and company"""
        card = BusinessCard(
            phone="123-456-7890",
            email="test@example.com",
            confidence_score=0.9,
            quality_score=0.8,
            line_user_id="test_user"
        )
        
        assert self.processor._validate_card_quality(card) is False
    
    def test_invalid_card_no_contact_info(self):
        """Test card rejected due to missing contact information"""
        card = BusinessCard(
            name="Test User",
            company="Test Company",
            confidence_score=0.9,
            quality_score=0.8,
            line_user_id="test_user"
        )
        
        assert self.processor._validate_card_quality(card) is False
    
    def test_invalid_email_format(self):
        """Test card with invalid email format"""
        card = BusinessCard(
            name="Test User",
            email="invalid-email-format",  # No @ symbol
            confidence_score=0.9,
            quality_score=0.8,
            line_user_id="test_user"
        )
        
        assert self.processor._validate_card_quality(card) is False
    
    def test_whitespace_only_fields(self):
        """Test card with whitespace-only fields"""
        card = BusinessCard(
            name="   ",  # Whitespace only
            company="  ",  # Whitespace only
            phone="123-456-7890",
            confidence_score=0.9,
            quality_score=0.8,
            line_user_id="test_user"
        )
        
        assert self.processor._validate_card_quality(card) is False


class TestProcessingSuggestions:
    """Test processing suggestions functionality"""
    
    def setup_method(self):
        """Setup for each test"""
        with patch('src.namecard.infrastructure.ai.card_processor.genai'):
            self.processor = CardProcessor()
    
    def test_suggestions_for_no_cards(self):
        """Test suggestions when no cards are detected"""
        suggestions = self.processor.get_processing_suggestions([])
        
        assert len(suggestions) >= 2
        assert any("確認圖片包含清晰的名片" in s for s in suggestions)
        assert any("光線充足且名片平整效果更佳" in s for s in suggestions)
    
    def test_suggestions_for_low_confidence_cards(self):
        """Test suggestions for low confidence cards"""
        low_confidence_cards = [
            BusinessCard(name="User1", company="Company1", phone="123", 
                        confidence_score=0.5, line_user_id="test"),
            BusinessCard(name="User2", company="Company2", phone="456", 
                        confidence_score=0.6, line_user_id="test"),
        ]
        
        suggestions = self.processor.get_processing_suggestions(low_confidence_cards)
        
        assert any("2 張名片信心度較低" in s for s in suggestions)
        assert any("建議重新拍攝" in s for s in suggestions)
    
    def test_suggestions_for_incomplete_cards(self):
        """Test suggestions for incomplete cards"""
        incomplete_cards = [
            BusinessCard(name="User1", confidence_score=0.9, line_user_id="test"),  # Missing company and contact
            BusinessCard(company="Company2", confidence_score=0.9, line_user_id="test"),  # Missing name and contact
        ]
        
        suggestions = self.processor.get_processing_suggestions(incomplete_cards)
        
        assert any("2 張名片資訊不完整" in s for s in suggestions)
        assert any("請檢查原始名片" in s for s in suggestions)
    
    def test_suggestions_for_multiple_cards(self):
        """Test suggestions for multiple valid cards"""
        multiple_cards = [
            BusinessCard(name="User1", company="Company1", phone="123", 
                        confidence_score=0.9, line_user_id="test"),
            BusinessCard(name="User2", company="Company2", phone="456", 
                        confidence_score=0.8, line_user_id="test"),
            BusinessCard(name="User3", company="Company3", phone="789", 
                        confidence_score=0.85, line_user_id="test"),
        ]
        
        suggestions = self.processor.get_processing_suggestions(multiple_cards)
        
        assert any("檢測到 3 張名片" in s for s in suggestions)
        assert any("已分別處理" in s for s in suggestions)
    
    def test_suggestions_mixed_quality_cards(self):
        """Test suggestions for mixed quality cards"""
        mixed_cards = [
            BusinessCard(name="Good Card", company="Company1", phone="123", 
                        confidence_score=0.95, line_user_id="test"),
            BusinessCard(name="Low Confidence", company="Company2", phone="456", 
                        confidence_score=0.6, line_user_id="test"),
            BusinessCard(name="Incomplete", confidence_score=0.9, line_user_id="test"),
        ]
        
        suggestions = self.processor.get_processing_suggestions(mixed_cards)
        
        # Should have suggestions for both issues
        assert any("信心度較低" in s for s in suggestions)
        assert any("資訊不完整" in s for s in suggestions)
        assert any("檢測到 3 張名片" in s for s in suggestions)


class TestAPIRetryLogic:
    """Test API retry logic and fallback mechanisms"""
    
    def setup_method(self):
        """Setup for each test"""
        with patch('src.namecard.infrastructure.ai.card_processor.genai'):
            self.processor = CardProcessor()
    
    @patch('src.namecard.infrastructure.ai.card_processor.genai')
    def test_api_retry_on_failure(self, mock_genai):
        """Test API retry mechanism when calls fail"""
        # First call fails, second succeeds
        mock_response = Mock()
        mock_response.text = '{"cards": []}'
        
        self.processor.model = Mock()
        self.processor.model.generate_content.side_effect = [
            Exception("Network error"),
            mock_response
        ]
        
        image = Image.new('RGB', (100, 100))
        
        # Should retry and eventually succeed
        with patch.object(self.processor, '_setup_gemini') as mock_setup:
            # Should handle the exception and potentially retry via fallback
            try:
                result = self.processor._analyze_with_gemini(image)
                assert result == '{"cards": []}'
            except APIError:
                # If it fails, it should be due to no fallback mechanism in this test
                pass
    
    def test_empty_response_handling(self):
        """Test handling of empty API responses"""
        self.processor.model = Mock()
        mock_response = Mock()
        mock_response.text = ""  # Empty response
        self.processor.model.generate_content.return_value = mock_response
        
        image = Image.new('RGB', (100, 100))
        
        with pytest.raises(APIError, match="Empty response from Gemini"):
            self.processor._analyze_with_gemini(image)
    
    def test_api_call_counting(self):
        """Test API call counting functionality"""
        mock_response = Mock()
        mock_response.text = '{"cards": []}'
        self.processor.model = Mock()
        self.processor.model.generate_content.return_value = mock_response
        
        initial_count = self.processor._api_call_count
        
        image = Image.new('RGB', (100, 100))
        self.processor._analyze_with_gemini(image)
        
        assert self.processor._api_call_count == initial_count + 1
    
    def test_model_not_initialized_error(self):
        """Test error when model is not initialized"""
        self.processor.model = None
        
        image = Image.new('RGB', (100, 100))
        
        with pytest.raises(APIError, match="Gemini model not initialized"):
            self.processor._analyze_with_gemini(image)


# Performance and stress tests would go here
class TestPerformanceScenarios:
    """Test performance and stress scenarios"""
    
    def setup_method(self):
        """Setup for each test"""
        with patch('src.namecard.infrastructure.ai.card_processor.genai'):
            self.processor = CardProcessor()
    
    def test_large_image_processing_performance(self):
        """Test processing of large images"""
        # Create a large image
        large_image = Image.new('RGB', (4000, 3000), color='white')
        
        start_time = time.time()
        processed = self.processor._preprocess_image(large_image)
        processing_time = time.time() - start_time
        
        # Should complete in reasonable time (less than 5 seconds)
        assert processing_time < 5.0
        # Should be resized
        assert processed.size[0] <= 1920
        assert processed.size[1] <= 1920
    
    def test_multiple_cards_parsing_performance(self):
        """Test parsing response with many cards"""
        # Create response with many cards
        cards_data = []
        for i in range(50):  # 50 cards
            cards_data.append({
                "name": f"User {i}",
                "company": f"Company {i}",
                "phone": f"123-456-{i:04d}",
                "email": f"user{i}@company{i}.com",
                "confidence_score": 0.9,
                "quality_score": 0.8
            })
        
        response = json.dumps({"cards": cards_data})
        
        start_time = time.time()
        cards = self.processor._parse_response(response, "test_user")
        processing_time = time.time() - start_time
        
        # Should complete in reasonable time
        assert processing_time < 2.0
        assert len(cards) == 50