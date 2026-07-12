"""安全服務測試"""

import time
import hmac
import hashlib
import base64
from src.namecard.core.services.security import SecurityService, ErrorHandler


class TestSecurityService:
    """SecurityService 測試"""

    def setup_method(self):
        """每個測試方法前的設置"""
        self.security = SecurityService()
        self.test_user_id = "test_user_123"

    def test_validate_line_signature_success(self):
        """測試 LINE 簽名驗證成功"""
        body = "test message body"
        channel_secret = "test_secret"

        # 計算正確的簽名
        hash_value = hmac.new(
            channel_secret.encode('utf-8'),
            body.encode('utf-8'),
            hashlib.sha256
        ).digest()
        expected_signature = base64.b64encode(hash_value).decode('utf-8')

        result = self.security.validate_line_signature(body, expected_signature, channel_secret)

        assert result is True

    def test_validate_line_signature_failure(self):
        """測試 LINE 簽名驗證失敗"""
        body = "test message body"
        channel_secret = "test_secret"
        invalid_signature = "invalid_signature"

        result = self.security.validate_line_signature(body, invalid_signature, channel_secret)

        assert result is False

    def test_validate_line_signature_exception(self):
        """測試 LINE 簽名驗證異常處理"""
        # 使用會導致異常的參數
        result = self.security.validate_line_signature(None, "sig", "secret")

        assert result is False

    def test_sanitize_input_normal_text(self):
        """測試清理正常文字"""
        clean_text = "這是正常的文字 123"
        result = self.security.sanitize_input(clean_text)

        assert result == clean_text

    def test_sanitize_input_dangerous_chars(self):
        """測試清理危險字元"""
        dangerous_text = "Hello <script>alert('xss')</script> & \"quotes\""
        result = self.security.sanitize_input(dangerous_text)

        # 危險字元應該被移除
        assert "<" not in result
        assert ">" not in result
        assert "&" not in result
        assert '"' not in result
        assert "'" not in result

    def test_sanitize_input_length_limit(self):
        """測試文字長度限制"""
        long_text = "A" * 2000
        result = self.security.sanitize_input(long_text, max_length=100)

        assert len(result) == 100

    def test_sanitize_input_empty_none(self):
        """測試清理空值"""
        assert self.security.sanitize_input("") == ""
        assert self.security.sanitize_input(None) == ""

    def test_sanitize_input_strip_whitespace(self):
        """測試去除空白字元"""
        text_with_whitespace = "  \n  Hello World  \t  "
        result = self.security.sanitize_input(text_with_whitespace)

        assert result == "Hello World"

    def test_validate_image_data_valid_png(self):
        """測試驗證有效 PNG 圖片"""
        png_header = b'\x89PNG\r\n\x1a\n' + b'0' * 100  # 模擬 PNG 資料

        result = self.security.validate_image_data(png_header, max_size=1000)
        assert result is True

    def test_validate_image_data_valid_jpeg(self):
        """測試驗證有效 JPEG 圖片"""
        jpeg_header = b'\xff\xd8' + b'0' * 100  # 模擬 JPEG 資料

        result = self.security.validate_image_data(jpeg_header, max_size=1000)
        assert result is True

    def test_validate_image_data_valid_gif(self):
        """測試驗證有效 GIF 圖片"""
        gif_header = b'GIF89a' + b'0' * 100  # 模擬 GIF 資料

        result = self.security.validate_image_data(gif_header, max_size=1000)
        assert result is True

    def test_validate_image_data_too_large(self):
        """測試圖片檔案過大"""
        large_image = b'\x89PNG' + b'0' * 2000000  # 2MB 圖片

        result = self.security.validate_image_data(large_image, max_size=1000000)  # 1MB 限制
        assert result is False

    def test_validate_image_data_invalid_format(self):
        """測試無效圖片格式"""
        invalid_data = b'Not an image file'

        result = self.security.validate_image_data(invalid_data)
        assert result is False

    def test_validate_image_data_exception(self):
        """測試圖片驗證異常處理"""
        result = self.security.validate_image_data(None)
        assert result is False

    def test_log_security_event(self):
        """測試記錄安全事件"""
        # 這個測試主要確保方法不會拋出異常
        self.security.log_security_event(
            "test_event",
            self.test_user_id,
            {"detail": "test detail"}
        )

        # 如果沒有異常，測試通過
        assert True


class TestErrorHandler:
    """ErrorHandler 測試"""

    def setup_method(self):
        """每個測試方法前的設置"""
        self.error_handler = ErrorHandler()
        self.test_user_id = "test_user_123"

    def test_handle_ai_error_quota_exceeded(self):
        """測試處理 AI 配額超過錯誤"""
        quota_error = Exception("API quota exceeded")

        message = self.error_handler.handle_ai_error(quota_error, self.test_user_id)

        assert "AI 服務暫時繁忙" in message
        assert self.error_handler._error_counts["Exception"] == 1

    def test_handle_ai_error_network_issue(self):
        """測試處理 AI 網路錯誤"""
        network_error = Exception("Network timeout occurred")

        message = self.error_handler.handle_ai_error(network_error, self.test_user_id)

        assert "網路連線問題" in message

    def test_handle_ai_error_generic(self):
        """測試處理一般 AI 錯誤"""
        generic_error = Exception("Unknown AI error")

        message = self.error_handler.handle_ai_error(generic_error, self.test_user_id)

        assert "圖片分析失敗" in message

    def test_handle_notion_error_unauthorized(self):
        """測試處理 Notion 未授權錯誤"""
        auth_error = Exception("Unauthorized access")

        message = self.error_handler.handle_notion_error(auth_error, self.test_user_id)

        assert "資料庫存取權限問題" in message

    def test_handle_notion_error_not_found(self):
        """測試處理 Notion 找不到錯誤"""
        not_found_error = Exception("Database not_found")

        message = self.error_handler.handle_notion_error(not_found_error, self.test_user_id)

        assert "找不到指定的資料庫" in message

    def test_handle_notion_error_generic(self):
        """測試處理一般 Notion 錯誤"""
        generic_error = Exception("Unknown Notion error")

        message = self.error_handler.handle_notion_error(generic_error, self.test_user_id)

        assert "資料儲存失敗" in message

    def test_handle_line_error(self):
        """測試處理 LINE API 錯誤"""
        line_error = Exception("LINE API error")

        message = self.error_handler.handle_line_error(line_error, self.test_user_id)

        # LINE API 錯誤通常不回應使用者
        assert message is None
        assert self.error_handler._error_counts["Exception"] == 1

    def test_get_error_stats(self):
        """測試獲取錯誤統計"""
        # 產生一些錯誤
        self.error_handler.handle_ai_error(Exception("AI Error 1"), self.test_user_id)
        self.error_handler.handle_ai_error(ValueError("AI Error 2"), self.test_user_id)
        self.error_handler.handle_notion_error(Exception("Notion Error"), self.test_user_id)

        stats = self.error_handler.get_error_stats()

        assert "error_counts" in stats
        assert "last_errors" in stats
        assert "total_errors" in stats

        # 檢查錯誤計數
        assert stats["error_counts"]["Exception"] == 2  # AI + Notion
        assert stats["error_counts"]["ValueError"] == 1
        assert stats["total_errors"] == 3

        # 檢查最後錯誤時間
        assert "Exception" in stats["last_errors"]
        assert "ValueError" in stats["last_errors"]

    def test_error_count_increment(self):
        """測試錯誤計數遞增"""
        error_type = "TestError"
        test_error = type(error_type, (Exception,), {})()

        # 多次產生同類型錯誤
        for i in range(3):
            self.error_handler.handle_ai_error(test_error, self.test_user_id)

        assert self.error_handler._error_counts[error_type] == 3

    def test_last_error_timestamp_update(self):
        """測試最後錯誤時間戳更新"""
        error1 = Exception("First error")
        error2 = Exception("Second error")

        # 第一個錯誤
        self.error_handler.handle_ai_error(error1, self.test_user_id)
        first_timestamp = self.error_handler._last_errors["Exception"]

        # 等待一點時間
        time.sleep(0.01)

        # 第二個錯誤
        self.error_handler.handle_ai_error(error2, self.test_user_id)
        second_timestamp = self.error_handler._last_errors["Exception"]

        # 時間戳應該更新
        assert second_timestamp > first_timestamp
