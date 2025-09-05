"""
圖片託管服務 - ImageBB 整合
提供外部圖片託管功能，用於在 Notion 中嵌入圖片
"""

import structlog
import requests
import base64
from typing import Optional
from simple_config import settings

logger = structlog.get_logger()


class ImageHostingService:
    """圖片託管服務"""
    
    def __init__(self):
        self.api_key = settings.imagebb_api_key
        self.upload_url = "https://api.imgbb.com/1/upload"
    
    def is_available(self) -> bool:
        """檢查服務是否可用"""
        return bool(self.api_key and len(self.api_key) > 0)
    
    def upload_image(self, image_data: bytes, name: str = "namecard") -> Optional[str]:
        """
        上傳圖片到 ImageBB 並返回 URL
        
        Args:
            image_data: 圖片二進位資料
            name: 圖片名稱
            
        Returns:
            圖片 URL 或 None（如果失敗）
        """
        if not self.is_available():
            logger.warning("ImageBB API key not configured")
            return None
        
        try:
            # 將圖片轉換為 base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # 準備請求資料
            payload = {
                'key': self.api_key,
                'image': image_base64,
                'name': name,
                'expiration': 15552000  # 180 天過期
            }
            
            # 發送請求
            response = requests.post(
                self.upload_url, 
                data=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    image_url = result['data']['url']
                    logger.info("Image uploaded successfully", 
                              image_url=image_url,
                              size=len(image_data))
                    return image_url
                else:
                    logger.error("ImageBB upload failed", 
                               error=result.get('error', 'Unknown error'))
                    return None
            else:
                logger.error("ImageBB request failed", 
                           status_code=response.status_code,
                           response=response.text[:200])
                return None
                
        except requests.RequestException as e:
            logger.error("Network error during image upload", error=str(e))
            return None
        except Exception as e:
            logger.error("Unexpected error during image upload", error=str(e))
            return None