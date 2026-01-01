"""
ImageStorage 測試
"""

import pytest
from unittest.mock import patch, MagicMock
import base64

from src.namecard.infrastructure.storage.image_storage import ImageStorage, get_image_storage


class TestImageStorage:
    """ImageStorage 單元測試"""

    def test_init_with_api_key(self):
        """應能用 API key 初始化"""
        storage = ImageStorage(api_key="test_key")
        assert storage.api_key == "test_key"
        assert storage.upload_url == "https://api.imgbb.com/1/upload"

    def test_upload_without_api_key(self):
        """沒有 API key 時應回傳 None"""
        storage = ImageStorage(api_key="")
        result = storage.upload(b"fake_image_data")
        assert result is None

    @patch('src.namecard.infrastructure.storage.image_storage.requests.post')
    def test_upload_success(self, mock_post):
        """上傳成功應回傳 URL"""
        # Mock 成功回應
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "data": {
                "url": "https://i.ibb.co/abc123/image.jpg"
            }
        }
        mock_post.return_value = mock_response

        storage = ImageStorage(api_key="test_key")
        result = storage.upload(b"fake_image_data")

        assert result == "https://i.ibb.co/abc123/image.jpg"
        mock_post.assert_called_once()

    @patch('src.namecard.infrastructure.storage.image_storage.requests.post')
    def test_upload_failure(self, mock_post):
        """上傳失敗應回傳 None"""
        # Mock 失敗回應
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_post.return_value = mock_response

        storage = ImageStorage(api_key="test_key")
        result = storage.upload(b"fake_image_data")

        assert result is None

    @patch('src.namecard.infrastructure.storage.image_storage.requests.post')
    def test_upload_request_exception(self, mock_post):
        """網路錯誤應回傳 None"""
        import requests
        mock_post.side_effect = requests.RequestException("Network error")

        storage = ImageStorage(api_key="test_key")
        result = storage.upload(b"fake_image_data")

        assert result is None

    @patch('src.namecard.infrastructure.storage.image_storage.requests.post')
    def test_upload_sends_base64(self, mock_post):
        """應以 base64 格式發送圖片"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "data": {"url": "https://i.ibb.co/test.jpg"}
        }
        mock_post.return_value = mock_response

        storage = ImageStorage(api_key="my_api_key")
        image_data = b"test_image_bytes"
        storage.upload(image_data)

        # 驗證呼叫參數
        call_args = mock_post.call_args
        assert call_args[1]["data"]["key"] == "my_api_key"
        assert call_args[1]["data"]["image"] == base64.b64encode(image_data).decode("utf-8")


