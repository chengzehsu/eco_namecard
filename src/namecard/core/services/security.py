"""安全性和錯誤處理服務"""

import hashlib
import hmac
import time
import secrets
from typing import Dict, Optional, Any
from collections import defaultdict
from datetime import datetime, timedelta
import structlog
from cryptography.fernet import Fernet
import base64
import os

logger = structlog.get_logger()


class SecurityService:
    """安全性服務"""
    
    def __init__(self):
        self._rate_limits: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self._blocked_users: Dict[str, datetime] = {}
        self._encryption_key = self._get_or_create_encryption_key()
        self._cipher = Fernet(self._encryption_key)
    
    def _get_or_create_encryption_key(self) -> bytes:
        """獲取或建立加密金鑰"""
        # 在生產環境中，這應該從安全的環境變數或密鑰管理服務獲取
        key_env = os.environ.get('ENCRYPTION_KEY')
        if key_env:
            try:
                return base64.urlsafe_b64decode(key_env)
            except Exception:
                logger.warning("Invalid encryption key in environment, generating new one")
        
        # 生成新的金鑰
        key = Fernet.generate_key()
        logger.warning("Generated new encryption key, set ENCRYPTION_KEY environment variable")
        return key
    
    def validate_line_signature(self, body: str, signature: str, channel_secret: str) -> bool:
        """驗證 LINE webhook 簽名"""
        try:
            hash_value = hmac.new(
                channel_secret.encode('utf-8'),
                body.encode('utf-8'),
                hashlib.sha256
            ).digest()
            
            expected_signature = base64.b64encode(hash_value).decode('utf-8')
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error("Signature validation failed", error=str(e))
            return False
    
    def check_rate_limit(self, user_id: str, limit: int = 10, window: int = 60) -> bool:
        """
        檢查速率限制
        
        Args:
            user_id: 用戶 ID
            limit: 限制次數
            window: 時間窗口（秒）
        """
        now = time.time()
        user_data = self._rate_limits[user_id]
        
        # 清理過期記錄
        if 'requests' not in user_data:
            user_data['requests'] = []
        
        # 移除過期的請求記錄
        user_data['requests'] = [
            req_time for req_time in user_data['requests']
            if now - req_time < window
        ]
        
        # 檢查是否超過限制
        if len(user_data['requests']) >= limit:
            logger.warning("Rate limit exceeded", 
                         user_id=user_id, 
                         requests=len(user_data['requests']),
                         limit=limit)
            return False
        
        # 記錄新請求
        user_data['requests'].append(now)
        return True
    
    def is_user_blocked(self, user_id: str) -> bool:
        """檢查用戶是否被封鎖"""
        if user_id in self._blocked_users:
            unblock_time = self._blocked_users[user_id]
            if datetime.now() < unblock_time:
                return True
            else:
                # 解除封鎖
                del self._blocked_users[user_id]
                logger.info("User unblocked", user_id=user_id)
        
        return False
    
    def block_user(self, user_id: str, duration_minutes: int = 60) -> None:
        """封鎖用戶"""
        unblock_time = datetime.now() + timedelta(minutes=duration_minutes)
        self._blocked_users[user_id] = unblock_time
        
        logger.warning("User blocked", 
                      user_id=user_id, 
                      duration_minutes=duration_minutes,
                      unblock_time=unblock_time)
    
    def encrypt_sensitive_data(self, data: str) -> str:
        """加密敏感資料"""
        try:
            encrypted = self._cipher.encrypt(data.encode('utf-8'))
            return base64.urlsafe_b64encode(encrypted).decode('utf-8')
        except Exception as e:
            logger.error("Encryption failed", error=str(e))
            raise
    
    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """解密敏感資料"""
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
            decrypted = self._cipher.decrypt(encrypted_bytes)
            return decrypted.decode('utf-8')
        except Exception as e:
            logger.error("Decryption failed", error=str(e))
            raise
    
    def generate_secure_token(self, length: int = 32) -> str:
        """生成安全令牌"""
        return secrets.token_urlsafe(length)
    
    def sanitize_input(self, text: str, max_length: int = 1000) -> str:
        """清理輸入文字"""
        if not text:
            return ""
        
        # 限制長度
        text = text[:max_length]
        
        # 移除潛在危險字符
        dangerous_chars = ['<', '>', '"', "'", '&', '\x00']
        for char in dangerous_chars:
            text = text.replace(char, '')
        
        return text.strip()
    
    def validate_image_data(self, image_data: bytes, max_size: int = 10485760) -> bool:
        """驗證圖片資料"""
        try:
            # 檢查大小
            if len(image_data) > max_size:
                logger.warning("Image too large", size=len(image_data), max_size=max_size)
                return False
            
            # 檢查圖片格式（簡單檢查）
            if not image_data.startswith((b'\xff\xd8', b'\x89PNG', b'GIF')):
                logger.warning("Invalid image format")
                return False
            
            return True
            
        except Exception as e:
            logger.error("Image validation failed", error=str(e))
            return False
    
    def log_security_event(self, event_type: str, user_id: str, details: Dict[str, Any]) -> None:
        """記錄安全事件"""
        logger.warning("Security event", 
                      event_type=event_type,
                      user_id=user_id,
                      details=details,
                      timestamp=datetime.now().isoformat())


class ErrorHandler:
    """錯誤處理器"""
    
    def __init__(self):
        self._error_counts: Dict[str, int] = defaultdict(int)
        self._last_errors: Dict[str, datetime] = {}
    
    def handle_ai_error(self, error: Exception, user_id: str) -> str:
        """處理 AI 相關錯誤"""
        error_type = type(error).__name__
        self._error_counts[error_type] += 1
        self._last_errors[error_type] = datetime.now()
        
        logger.error("AI processing error", 
                    error_type=error_type,
                    error_message=str(error),
                    user_id=user_id,
                    count=self._error_counts[error_type])
        
        # 根據錯誤類型返回友善訊息
        if "quota" in str(error).lower() or "limit" in str(error).lower():
            return "⚠️ AI 服務暫時繁忙，請稍後再試"
        elif "network" in str(error).lower() or "timeout" in str(error).lower():
            return "🌐 網路連線問題，請檢查網路後重試"
        else:
            return "❌ 圖片分析失敗，請確認圖片清晰後重試"
    
    def handle_notion_error(self, error: Exception, user_id: str) -> str:
        """處理 Notion 相關錯誤"""
        error_type = type(error).__name__
        self._error_counts[error_type] += 1
        
        logger.error("Notion storage error",
                    error_type=error_type,
                    error_message=str(error),
                    user_id=user_id)
        
        if "unauthorized" in str(error).lower():
            return "🔐 資料庫存取權限問題，請聯繫管理員"
        elif "not_found" in str(error).lower():
            return "📁 找不到指定的資料庫，請聯繫管理員"
        else:
            return "💾 資料儲存失敗，請稍後重試"
    
    def handle_line_error(self, error: Exception, user_id: str) -> Optional[str]:
        """處理 LINE API 相關錯誤"""
        error_type = type(error).__name__
        self._error_counts[error_type] += 1
        
        logger.error("LINE API error",
                    error_type=error_type,
                    error_message=str(error),
                    user_id=user_id)
        
        # LINE API 錯誤通常不需要回應用戶
        return None
    
    def get_error_stats(self) -> Dict[str, Any]:
        """獲取錯誤統計"""
        return {
            "error_counts": dict(self._error_counts),
            "last_errors": {
                error_type: timestamp.isoformat()
                for error_type, timestamp in self._last_errors.items()
            },
            "total_errors": sum(self._error_counts.values())
        }


# 全域實例
security_service = SecurityService()
error_handler = ErrorHandler()