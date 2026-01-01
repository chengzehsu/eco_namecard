"""
ImgBB 圖片儲存服務

提供圖片上傳功能，用於將名片圖片存儲到 ImgBB 並獲取公開 URL。
"""

import os
import sys
import base64
import requests
import structlog
from typing import Optional

# Add project root to path for simple_config import
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../..'))

logger = structlog.get_logger()


class ImageStorage:
    """ImgBB 圖片儲存服務"""

    def __init__(self, api_key: str):
        """
        初始化圖片儲存服務

        Args:
            api_key: ImgBB API Key
        """
        self.api_key = api_key
        self.upload_url = "https://api.imgbb.com/1/upload"

    def upload(self, image_data: bytes) -> Optional[str]:
        """
        上傳圖片到 ImgBB

        Args:
            image_data: 圖片的二進位資料

        Returns:
            圖片的公開 URL，失敗時回傳 None
        """
        if not self.api_key:
            logger.warning("ImgBB API key not configured, skipping image upload")
            return None

        try:
            # 將圖片轉為 base64
            image_base64 = base64.b64encode(image_data).decode("utf-8")

            # 上傳到 ImgBB
            response = requests.post(
                self.upload_url,
                data={
                    "key": self.api_key,
                    "image": image_base64,
                },
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    image_url = result["data"]["url"]
                    logger.info("Image uploaded successfully",
                               url=image_url[:50] + "...")
                    return image_url

            # 上傳失敗
            logger.error("ImgBB upload failed",
                        status_code=response.status_code,
                        response=response.text[:200])
            return None

        except requests.RequestException as e:
            logger.error("ImgBB upload request failed", error=str(e))
            return None
        except Exception as e:
            logger.error("Unexpected error during image upload", error=str(e))
            return None


# 全域實例（延遲初始化）
_image_storage: Optional[ImageStorage] = None


def get_image_storage() -> Optional[ImageStorage]:
    """
    獲取圖片儲存服務實例

    Returns:
        ImageStorage 實例，如果未配置 API Key 則回傳 None
    """
    global _image_storage

    if _image_storage is None:
        # #region agent log
        import json
        with open('/Users/user/Ecofirst_namecard/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"location": "image_storage.py:get_image_storage", "message": "BEFORE import simple_config", "hypothesisId": "H1", "runId": "post-fix"}) + '\n')
        # #endregion
        from simple_config import settings
        # #region agent log
        with open('/Users/user/Ecofirst_namecard/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"location": "image_storage.py:get_image_storage", "message": "AFTER import simple_config SUCCESS", "hypothesisId": "H1", "runId": "post-fix"}) + '\n')
        # #endregion

        api_key = getattr(settings, 'imgbb_api_key', None)
        if api_key:
            _image_storage = ImageStorage(api_key)
            logger.info("ImageStorage initialized with ImgBB")
        else:
            logger.info("ImgBB API key not configured, image upload disabled")

    return _image_storage
