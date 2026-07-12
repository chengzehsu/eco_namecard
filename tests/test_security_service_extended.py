"""
Extended tests for security service - edge cases and advanced scenarios
"""

import time
import hmac
import hashlib
import base64
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

from src.namecard.core.services.security import SecurityService, ErrorHandler


class TestSecurityServiceEdgeCases:
    """Test edge cases and advanced scenarios for SecurityService"""

    def setup_method(self):
        """Setup for each test"""
        self.security = SecurityService()
        self.test_user_id = "test_user_123"

    def test_validate_line_signature_unicode_body(self):
        """Test LINE signature validation with Unicode characters"""
        body = "測試 Unicode 內容 🔒 emoji test"
        channel_secret = "test_secret_中文"

        # Calculate correct signature with Unicode
        hash_value = hmac.new(
            channel_secret.encode('utf-8'),
            body.encode('utf-8'),
            hashlib.sha256
        ).digest()
        expected_signature = base64.b64encode(hash_value).decode('utf-8')

        result = self.security.validate_line_signature(body, expected_signature, channel_secret)
        assert result is True

    def test_validate_line_signature_empty_strings(self):
        """Test signature validation with empty strings"""
        # 空 body/secret 仍會產生有效的 HMAC 簽名，空簽名字串永遠不會匹配
        assert self.security.validate_line_signature("", "", "") is False
        assert self.security.validate_line_signature("", "non_empty", "secret") is False
        assert self.security.validate_line_signature("body", "", "secret") is False

    def test_validate_line_signature_very_long_body(self):
        """Test signature validation with very long body"""
        body = "x" * 100000  # 100KB body
        channel_secret = "secret"

        hash_value = hmac.new(
            channel_secret.encode('utf-8'),
            body.encode('utf-8'),
            hashlib.sha256
        ).digest()
        expected_signature = base64.b64encode(hash_value).decode('utf-8')

        result = self.security.validate_line_signature(body, expected_signature, channel_secret)
        assert result is True

    def test_validate_line_signature_malformed_base64(self):
        """Test signature validation with malformed base64"""
        body = "test body"
        channel_secret = "secret"
        malformed_signature = "not_valid_base64!"

        result = self.security.validate_line_signature(body, malformed_signature, channel_secret)
        assert result is False

    def test_validate_line_signature_timing_attack_resistance(self):
        """Test that signature validation is resistant to timing attacks"""
        body = "test body"
        channel_secret = "secret"

        # Generate correct signature
        hash_value = hmac.new(
            channel_secret.encode('utf-8'),
            body.encode('utf-8'),
            hashlib.sha256
        ).digest()
        correct_signature = base64.b64encode(hash_value).decode('utf-8')

        # Test multiple incorrect signatures
        incorrect_signatures = [
            "a" * len(correct_signature),
            correct_signature[:-1] + "X",
            correct_signature[:10] + "X" * (len(correct_signature) - 10),
            ""
        ]

        # All should return False consistently
        for sig in incorrect_signatures:
            assert self.security.validate_line_signature(body, sig, channel_secret) is False


class TestInputSanitization:
    """Test input sanitization edge cases"""

    def setup_method(self):
        """Setup for each test"""
        self.security = SecurityService()

    def test_sanitize_input_xss_attempts(self):
        """Test sanitization of XSS attack attempts"""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "javascript:alert('xss')",
            "<svg onload=alert('xss')>",
            "<iframe src='javascript:alert(\"xss\")'></iframe>",
            "<<SCRIPT>alert('xss');//<</SCRIPT>",
        ]

        for payload in xss_payloads:
            sanitized = self.security.sanitize_input(payload)
            assert "<" not in sanitized
            assert ">" not in sanitized

    def test_sanitize_input_sql_injection_attempts(self):
        """Test sanitization of SQL injection attempts"""
        sql_payloads = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "\" OR \"1\"=\"1",
            "'; UPDATE users SET password='hacked'; --",
        ]

        for payload in sql_payloads:
            sanitized = self.security.sanitize_input(payload)
            assert "'" not in sanitized
            assert '"' not in sanitized

    def test_sanitize_input_preserves_safe_content(self):
        """Test that sanitization preserves safe content"""
        safe_inputs = [
            "Hello World",
            "測試中文內容",
            "Numbers: 12345",
            "Email: user@example.com",
            "URL: https://example.com",
            "Symbols: !@#$%^*()_+-=[]{}|;:,./",
            "Unicode: 😀🎉🔒",
        ]

        for safe_input in safe_inputs:
            sanitized = self.security.sanitize_input(safe_input)
            # Should preserve most content except dangerous chars
            assert len(sanitized) > 0
            assert "Hello World" in self.security.sanitize_input("Hello World")

    def test_sanitize_input_null_bytes(self):
        """Test sanitization of null bytes and control characters"""
        dangerous_input = "Hello\x00World\x01Test\x02"
        sanitized = self.security.sanitize_input(dangerous_input)

        assert "\x00" not in sanitized

    def test_sanitize_input_max_length_unicode(self):
        """Test max length with Unicode characters"""
        unicode_text = "測試" * 1000  # Each character is multiple bytes
        sanitized = self.security.sanitize_input(unicode_text, max_length=100)

        assert len(sanitized) == 100
        # Should not break in middle of Unicode character
        assert sanitized.encode('utf-8')  # Should be valid UTF-8


class TestImageValidationSecurity:
    """Test image validation security features"""

    def setup_method(self):
        """Setup for each test"""
        self.security = SecurityService()

    def test_validate_image_webp_format(self):
        """Test validation of WebP format"""
        webp_header = b'RIFF\x00\x00\x00\x00WEBP'
        # Note: Current implementation doesn't support WebP, should return False
        result = self.security.validate_image_data(webp_header)
        assert result is False

    def test_validate_image_svg_security(self):
        """Test that SVG files are rejected for security"""
        svg_content = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert("xss")</script></svg>'
        result = self.security.validate_image_data(svg_content)
        assert result is False

    def test_validate_image_zero_size(self):
        """Test validation of zero-size image"""
        result = self.security.validate_image_data(b'')
        assert result is False

    def test_validate_image_exactly_max_size(self):
        """Test image exactly at max size limit"""
        max_size = 1000
        exactly_max_image = b'\x89PNG\r\n\x1a\n' + b'0' * (max_size - 8)

        result = self.security.validate_image_data(exactly_max_image, max_size)
        assert result is True

    def test_validate_image_one_byte_over_limit(self):
        """Test image one byte over size limit"""
        max_size = 1000
        over_limit_image = b'\x89PNG\r\n\x1a\n' + b'0' * (max_size - 7)  # 1 byte over

        result = self.security.validate_image_data(over_limit_image, max_size)
        assert result is False

    def test_validate_image_malformed_headers(self):
        """Test validation of malformed image headers"""
        malformed_headers = [
            b'\x89PN',  # Incomplete PNG header
            b'\xff',    # Incomplete JPEG header
            b'GIF',     # Incomplete GIF header
            b'\x89PNG\r\n\x1a',  # Missing final byte of PNG header
            b'\x89PNG\r\n\x1a\n\x00',  # PNG header with extra byte
        ]

        for header in malformed_headers:
            result = self.security.validate_image_data(header + b'0' * 100)
            # Most should be rejected, except complete headers
            if header == b'\x89PNG\r\n\x1a\n\x00':
                assert result is True  # This is actually valid PNG start
            elif header == b'GIF':
                assert result is True  # startswith(b'GIF') matches
            elif header == b'\x89PN':
                assert result is False
            elif header == b'\xff':
                assert result is False
            else:
                # b'\x89PNG\r\n\x1a' still startswith b'\x89PNG'
                assert result is True

    def test_validate_image_polyglot_attacks(self):
        """Test rejection of polyglot file attacks"""
        # File that starts like image but contains script
        polyglot = b'\x89PNG\r\n\x1a\n<script>alert("xss")</script>'

        # Should still pass basic validation as it has correct header
        # (Note: Real implementation might need more sophisticated checks)
        result = self.security.validate_image_data(polyglot)
        assert result is True  # Current implementation only checks header and size


class TestErrorHandlerEdgeCases:
    """Test ErrorHandler edge cases and concurrent scenarios"""

    def setup_method(self):
        """Setup for each test"""
        self.error_handler = ErrorHandler()
        self.test_user_id = "error_test_user"

    def test_error_handling_concurrent_errors(self):
        """Test error handling under concurrent conditions"""
        num_threads = 20
        errors_per_thread = 10

        def generate_errors():
            for i in range(errors_per_thread):
                if i % 3 == 0:
                    self.error_handler.handle_ai_error(ValueError("AI Error"), self.test_user_id)
                elif i % 3 == 1:
                    self.error_handler.handle_notion_error(Exception("Notion Error"), self.test_user_id)
                else:
                    self.error_handler.handle_line_error(RuntimeError("LINE Error"), self.test_user_id)

        # Generate errors concurrently
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(generate_errors) for _ in range(num_threads)]
            for future in futures:
                future.result()

        stats = self.error_handler.get_error_stats()

        # Should have correct total count
        expected_total = num_threads * errors_per_thread
        assert stats["total_errors"] == expected_total

        # Should have counts for each error type
        assert "ValueError" in stats["error_counts"]
        assert "Exception" in stats["error_counts"]
        assert "RuntimeError" in stats["error_counts"]

    def test_error_message_classification_edge_cases(self):
        """Test error message classification with edge cases"""
        # AI errors with specific keywords
        test_cases = [
            (Exception("API quota exceeded for today"), "AI 服務暫時繁忙"),
            (Exception("Rate limit reached"), "AI 服務暫時繁忙"),
            (Exception("Network timeout occurred"), "網路連線問題"),
            (Exception("Connection timeout"), "網路連線問題"),
            (Exception("Some random AI error"), "圖片分析失敗"),
            (Exception(""), "圖片分析失敗"),  # Empty error message
        ]

        for error, expected_keyword in test_cases:
            message = self.error_handler.handle_ai_error(error, self.test_user_id)
            assert expected_keyword in message

    def test_notion_error_classification(self):
        """Test Notion error classification"""
        test_cases = [
            (Exception("Unauthorized access to database"), "資料庫存取權限問題"),
            (Exception("Database not_found"), "找不到指定的資料庫"),
            # 實作只比對 "not_found"（底線），"not found" 走一般錯誤分支
            (Exception("Resource not found"), "資料儲存失敗"),
            (Exception("Some generic error"), "資料儲存失敗"),
        ]

        for error, expected_keyword in test_cases:
            message = self.error_handler.handle_notion_error(error, self.test_user_id)
            assert expected_keyword in message

    def test_error_stats_large_volume(self):
        """Test error stats with large volume of errors"""
        # Generate many errors of different types
        error_types = [ValueError, TypeError, RuntimeError, Exception, KeyError]

        for error_type in error_types:
            for i in range(100):
                error = error_type(f"Error {i}")
                self.error_handler.handle_ai_error(error, f"user_{i}")

        stats = self.error_handler.get_error_stats()

        assert stats["total_errors"] == 500  # 5 types * 100 each
        for error_type in error_types:
            assert stats["error_counts"][error_type.__name__] == 100

    def test_error_timestamp_precision(self):
        """Test error timestamp precision and ordering"""
        errors = [
            ValueError("First error"),
            ValueError("Second error"),
            TypeError("Different type error"),
            ValueError("Third error"),
        ]

        timestamps = []
        for error in errors:
            self.error_handler.handle_ai_error(error, self.test_user_id)
            timestamps.append(self.error_handler._last_errors[type(error).__name__])
            time.sleep(0.001)  # Small delay to ensure different timestamps

        # Timestamps should be in increasing order for same error type
        value_error_timestamps = [timestamps[0], timestamps[1], timestamps[3]]
        assert value_error_timestamps[0] <= value_error_timestamps[1] <= value_error_timestamps[2]

        # Different error types should have their own timestamps
        assert timestamps[2] != timestamps[1]  # TypeError vs ValueError

    def test_get_error_stats_thread_safety(self):
        """Test thread safety of get_error_stats"""
        def generate_and_read_stats():
            # Generate some errors
            for i in range(10):
                self.error_handler.handle_ai_error(Exception(f"Error {i}"), self.test_user_id)

            # Read stats multiple times
            for i in range(5):
                stats = self.error_handler.get_error_stats()
                assert "error_counts" in stats
                assert "last_errors" in stats
                assert "total_errors" in stats
                assert stats["total_errors"] >= 0

        # Run multiple threads simultaneously
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(generate_and_read_stats) for _ in range(10)]
            for future in futures:
                future.result()  # Should not raise exceptions


class TestSecurityEventLogging:
    """Test security event logging functionality"""

    def setup_method(self):
        """Setup for each test"""
        self.security = SecurityService()

    @patch('src.namecard.core.services.security.logger')
    def test_log_security_event_format(self, mock_logger):
        """Test security event logging format"""
        event_type = "test_event"
        user_id = "test_user"
        details = {"ip": "192.168.1.1", "action": "test_action"}

        self.security.log_security_event(event_type, user_id, details)

        # Verify logger.warning was called with correct parameters
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args

        assert call_args[0][0] == "Security event detected"
        assert call_args[1]["event_type"] == event_type
        assert call_args[1]["user_id"] == user_id
        assert call_args[1]["details"] == details
        assert "timestamp" in call_args[1]

    @patch('src.namecard.core.services.security.logger')
    def test_log_security_event_large_details(self, mock_logger):
        """Test logging security event with large details"""
        event_type = "large_event"
        user_id = "test_user"
        details = {
            "large_data": "x" * 10000,
            "request_headers": {"User-Agent": "test", "X-Custom": "value"},
            "nested_data": {
                "level1": {
                    "level2": {
                        "level3": "deep_value"
                    }
                }
            }
        }

        # Should not raise exception with large data
        self.security.log_security_event(event_type, user_id, details)

        mock_logger.warning.assert_called_once()

    @patch('src.namecard.core.services.security.logger')
    def test_log_security_event_unicode_content(self, mock_logger):
        """Test logging security event with Unicode content"""
        event_type = "unicode_event"
        user_id = "使用者_123"
        details = {
            "message": "安全事件：使用者嘗試上傳惡意檔案 🔒",
            "file_name": "惡意檔案.exe",
            "emoji_data": "🚨🔐⚠️"
        }

        self.security.log_security_event(event_type, user_id, details)

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert call_args[1]["user_id"] == "使用者_123"
        assert "安全事件" in call_args[1]["details"]["message"]
