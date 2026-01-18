"""
ImgBB 圖片儲存服務

提供圖片上傳功能，用於將名片圖片存儲到 ImgBB 並獲取公開 URL。
支援同步和非同步上傳模式。
"""

import os
import sys
import base64
import requests
import structlog
import threading
from typing import Optional, Callable

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
        self.base_url = "https://api.imgbb.com/1/upload"
        self.timeout = 60  # 增加到 60 秒
        self.max_retries = 2

    def _do_upload(self, image_data: bytes) -> Optional[str]:
        """
        執行實際的上傳操作（帶重試）

        Args:
            image_data: 圖片的二進位資料

        Returns:
            圖片的公開 URL，失敗時回傳 None
        """
        logger.warning("DEBUG_IMGBB_DO_UPLOAD_START", image_size=len(image_data), api_key_exists=bool(self.api_key))
        
        if not self.api_key:
            logger.warning("DEBUG_IMGBB_NO_API_KEY")
            return None

        # 將圖片轉為 base64
        image_base64 = base64.b64encode(image_data).decode("utf-8")
        logger.warning("DEBUG_IMGBB_BASE64_ENCODED", base64_length=len(image_base64))
        
        # 根據官方文檔，key 放在 URL 參數中
        upload_url = f"{self.base_url}?key={self.api_key}"

        for attempt in range(self.max_retries + 1):
            try:
                logger.info("Attempting ImgBB upload", 
                           attempt=attempt + 1, 
                           max_retries=self.max_retries + 1,
                           image_size_kb=len(image_data) // 1024)

                # 使用 multipart/form-data 格式（官方推薦）
                response = requests.post(
                    upload_url,
                    data={"image": image_base64},
                    timeout=self.timeout
                )

                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        image_url = result["data"]["url"]
                        logger.info("Image uploaded successfully",
                                   url=image_url[:50] + "...",
                                   attempt=attempt + 1)
                        return image_url

                # 上傳失敗但沒有異常
                logger.warning("ImgBB upload failed",
                              status_code=response.status_code,
                              response=response.text[:200],
                              attempt=attempt + 1)

            except requests.Timeout:
                logger.warning("ImgBB upload timeout", 
                              attempt=attempt + 1,
                              timeout=self.timeout)
            except requests.RequestException as e:
                logger.warning("ImgBB upload request failed", 
                              error=str(e),
                              attempt=attempt + 1)
            except Exception as e:
                logger.error("Unexpected error during image upload", 
                            error=str(e),
                            attempt=attempt + 1)
                break  # 未知錯誤不重試

        logger.error("ImgBB upload failed after all retries",
                    max_retries=self.max_retries + 1)
        return None

    def upload(self, image_data: bytes) -> Optional[str]:
        """
        同步上傳圖片到 ImgBB

        Args:
            image_data: 圖片的二進位資料

        Returns:
            圖片的公開 URL，失敗時回傳 None
        """
        return self._do_upload(image_data)

    def upload_async(
        self, 
        image_data: bytes, 
        callback: Optional[Callable[[Optional[str]], None]] = None
    ) -> None:
        """
        非同步上傳圖片到 ImgBB（不阻塞主線程）

        Args:
            image_data: 圖片的二進位資料
            callback: 上傳完成後的回調函數，參數為圖片 URL（成功）或 None（失敗）
        """
        def _upload_thread():
            try:
                result = self._do_upload(image_data)
                if callback:
                    callback(result)
            except Exception as e:
                logger.error("Async upload thread error", error=str(e))
                if callback:
                    callback(None)

        thread = threading.Thread(target=_upload_thread, daemon=True)
        thread.start()
        logger.info("Started async image upload thread")


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
        from simple_config import settings

        api_key = getattr(settings, 'imgbb_api_key', None)
        # #region agent log
        logger.warning("DEBUG_IMGBB_CONFIG", api_key_exists=bool(api_key), api_key_length=len(api_key) if api_key else 0)
        # #endregion
        if api_key:
            _image_storage = ImageStorage(api_key)
            logger.info("ImageStorage initialized with ImgBB")
        else:
            logger.warning("ImgBB API key not configured, image upload disabled")

    return _image_storage
