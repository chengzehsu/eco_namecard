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
import sys

# 添加項目根目錄到 Python 路徑
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

from simple_config import settings
from src.namecard.core.exceptions import (
    NamecardException,
    get_user_friendly_message,
)

logger = structlog.get_logger()


class SecurityService:
    """安全性服務 (支援 Redis 持久化)"""

    def __init__(self, redis_client=None, use_redis: bool = True):
        """
        初始化安全性服務

        Args:
            redis_client: Redis 客戶端實例，如果為 None 則使用記憶體存儲
            use_redis: 是否使用 Redis
        """
        self.redis_client = redis_client if use_redis else None
        self.use_redis = use_redis and redis_client is not None

        # Fallback to in-memory storage
        self._rate_limits: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self._blocked_users: Dict[str, datetime] = {}

        self._encryption_key = self._get_or_create_encryption_key()
        self._cipher = Fernet(self._encryption_key)

        logger.info("SecurityService initialized",
                   use_redis=self.use_redis,
                   storage_backend="Redis" if self.use_redis else "Memory")
    
    def _get_or_create_encryption_key(self) -> bytes:
        """獲取或建立加密金鑰"""
        # 優先從環境變數獲取
        key_env = os.environ.get('ENCRYPTION_KEY')
        if key_env:
            try:
                return base64.urlsafe_b64decode(key_env)
            except Exception as e:
                logger.error("Invalid encryption key in environment", error=str(e))
        
        # 嘗試從 SECRET_KEY 衍生密鑰（使用與 tenant_service.py 相同的預設值）
        # 確保與 tenant_service.py 使用完全相同的預設值以保持一致性
        DEFAULT_SECRET_KEY = 'default-secret-key-change-me'
        secret_key = os.environ.get('SECRET_KEY', DEFAULT_SECRET_KEY)

        try:
            # 使用 PBKDF2 從 SECRET_KEY 衍生穩定的加密密鑰
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

            salt = b'linebot_namecard_salt_2024'  # 固定鹽值確保一致性
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            raw_key = kdf.derive(secret_key.encode('utf-8'))
            # Fernet 需要 base64 encoded key
            key = base64.urlsafe_b64encode(raw_key)

            if secret_key == DEFAULT_SECRET_KEY:
                logger.warning("Using default SECRET_KEY - set a secure SECRET_KEY in production")
            else:
                logger.info("Derived encryption key from SECRET_KEY")
            return key
        except Exception as e:
            logger.error("Failed to derive key from SECRET_KEY", error=str(e))
            # 最後選擇：生成新的金鑰（不推薦用於生產環境）
            key = Fernet.generate_key()
            logger.warning("Generated new encryption key - data encrypted with this key will be lost on restart")
            logger.warning("Set ENCRYPTION_KEY or SECRET_KEY environment variable for persistent encryption")
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
    
    def _get_rate_limit_key(self, user_id: str) -> str:
        """生成速率限制的 Redis key"""
        return f"namecard:ratelimit:{user_id}"

    def check_rate_limit(self, user_id: str, limit: int = 10, window: int = 60) -> bool:
        """
        檢查速率限制（支援 Redis）

        Args:
            user_id: 用戶 ID
            limit: 限制次數
            window: 時間窗口（秒）
        """
        now = time.time()

        if self.use_redis:
            # 使用 Redis 的 Sorted Set 實作滑動窗口
            try:
                key = self._get_rate_limit_key(user_id)

                # 移除過期的請求記錄
                self.redis_client.zremrangebyscore(key, 0, now - window)

                # 獲取當前請求數
                request_count = self.redis_client.zcard(key)

                # 檢查是否超過限制
                if request_count >= limit:
                    logger.warning("Rate limit exceeded (Redis)",
                                 user_id=user_id,
                                 requests=request_count,
                                 limit=limit,
                                 window_seconds=window,
                                 operation="rate_limiting",
                                 security_issue="rate_limit_exceeded")
                    return False

                # 記錄新請求（使用當前時間作為 score 和 member）
                self.redis_client.zadd(key, {str(now): now})

                # 設定 key 過期時間（window + 1秒）
                self.redis_client.expire(key, window + 1)

                return True

            except Exception as e:
                logger.error("Redis rate limit check failed, falling back to memory",
                           error=str(e))
                # Fallback to memory-based rate limiting
                return self._check_rate_limit_memory(user_id, limit, window)
        else:
            return self._check_rate_limit_memory(user_id, limit, window)

    def _check_rate_limit_memory(self, user_id: str, limit: int, window: int) -> bool:
        """記憶體版本的速率限制檢查"""
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
            logger.warning("Rate limit exceeded (Memory)",
                         user_id=user_id,
                         requests=len(user_data['requests']),
                         limit=limit,
                         window_seconds=window,
                         operation="rate_limiting",
                         security_issue="rate_limit_exceeded")
            return False

        # 記錄新請求
        user_data['requests'].append(now)
        return True
    
    def _get_blocked_user_key(self, user_id: str) -> str:
        """生成被封鎖用戶的 Redis key"""
        return f"namecard:blocked:{user_id}"

    def is_user_blocked(self, user_id: str) -> bool:
        """檢查用戶是否被封鎖（支援 Redis）"""
        if self.use_redis:
            try:
                key = self._get_blocked_user_key(user_id)
                # Redis 中如果 key 存在且未過期，代表用戶被封鎖
                blocked_until = self.redis_client.get(key)
                if blocked_until:
                    # TTL 會自動處理過期，所以如果 key 存在就是被封鎖
                    return True
                return False
            except Exception as e:
                logger.error("Redis blocked user check failed, falling back to memory",
                           error=str(e))
                # Fallback to memory
                return self._is_user_blocked_memory(user_id)
        else:
            return self._is_user_blocked_memory(user_id)

    def _is_user_blocked_memory(self, user_id: str) -> bool:
        """記憶體版本的封鎖檢查"""
        if user_id in self._blocked_users:
            unblock_time = self._blocked_users[user_id]
            if datetime.now() < unblock_time:
                return True
            else:
                # 解除封鎖
                del self._blocked_users[user_id]
                logger.info("User unblocked (Memory)", user_id=user_id)
        return False

    def block_user(self, user_id: str, duration_minutes: int = 60) -> None:
        """封鎖用戶（支援 Redis）"""
        unblock_time = datetime.now() + timedelta(minutes=duration_minutes)

        if self.use_redis:
            try:
                key = self._get_blocked_user_key(user_id)
                # 儲存封鎖資訊，並設定 TTL 自動過期
                self.redis_client.setex(
                    key,
                    duration_minutes * 60,
                    unblock_time.isoformat()
                )
                logger.warning("User blocked (Redis)",
                             user_id=user_id,
                             duration_minutes=duration_minutes,
                             unblock_time=unblock_time)
            except Exception as e:
                logger.error("Redis block user failed, using memory fallback",
                           error=str(e))
                # Fallback to memory
                self._block_user_memory(user_id, unblock_time)
        else:
            self._block_user_memory(user_id, unblock_time)

    def _block_user_memory(self, user_id: str, unblock_time: datetime) -> None:
        """記憶體版本的用戶封鎖"""
        self._blocked_users[user_id] = unblock_time
        duration_minutes = int((unblock_time - datetime.now()).total_seconds() / 60)

        logger.warning("User blocked (Memory)",
                      user_id=user_id,
                      duration_minutes=duration_minutes,
                      unblock_time=unblock_time)
    
    def encrypt_sensitive_data(self, data: str) -> str:
        """加密敏感資料"""
        try:
            encrypted = self._cipher.encrypt(data.encode('utf-8'))
            return base64.urlsafe_b64encode(encrypted).decode('utf-8')
        except Exception as e:
            logger.error("Data encryption failed", 
                        error=str(e), 
                        operation="encryption",
                        security_issue="encryption_failure")
            raise
    
    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """解密敏感資料"""
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
            decrypted = self._cipher.decrypt(encrypted_bytes)
            return decrypted.decode('utf-8')
        except Exception as e:
            logger.error("Data decryption failed", 
                        error=str(e), 
                        operation="decryption",
                        security_issue="decryption_failure")
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
        logger.warning("Security event detected", 
                      event_type=event_type,
                      user_id=user_id,
                      details=details,
                      severity="medium",
                      operation="security_monitoring",
                      timestamp=datetime.now().isoformat())


class ErrorHandler:
    """錯誤處理器（支援詳細的用戶友善錯誤訊息）"""

    def __init__(self, verbose: bool = False):
        """
        初始化錯誤處理器

        Args:
            verbose: 是否顯示詳細的技術錯誤訊息（開發模式）
        """
        self._error_counts: Dict[str, int] = defaultdict(int)
        self._last_errors: Dict[str, datetime] = {}
        self.verbose = verbose

        # 從 settings 讀取 verbose 設定
        if hasattr(settings, 'verbose_errors'):
            self.verbose = settings.verbose_errors

        logger.info("ErrorHandler initialized", verbose_mode=self.verbose)

    def handle_ai_error(self, error: Exception, user_id: str) -> str:
        """
        處理 AI 相關錯誤

        Args:
            error: 異常物件
            user_id: 用戶 ID

        Returns:
            用戶友善的錯誤訊息
        """
        error_type = type(error).__name__
        self._error_counts[error_type] += 1
        self._last_errors[error_type] = datetime.now()

        logger.error("AI processing error",
                    error_type=error_type,
                    error_message=str(error),
                    user_id=user_id,
                    count=self._error_counts[error_type])

        # 使用新的異常系統
        if isinstance(error, NamecardException):
            return get_user_friendly_message(error, verbose=self.verbose)

        # 向後兼容：處理舊的錯誤訊息格式
        error_str = str(error).lower()
        if "quota" in error_str or "limit" in error_str:
            return "⚠️ AI 服務暫時繁忙，請稍後再試"
        elif "network" in error_str or "timeout" in error_str:
            return "🌐 網路連線問題，請檢查網路後重試"
        else:
            return "❌ 圖片分析失敗，請確認圖片清晰後重試"
    
    def handle_notion_error(self, error: Exception, user_id: str) -> str:
        """
        處理 Notion 相關錯誤

        Args:
            error: 異常物件
            user_id: 用戶 ID

        Returns:
            用戶友善的錯誤訊息
        """
        error_type = type(error).__name__
        self._error_counts[error_type] += 1

        logger.error("Notion storage error",
                    error_type=error_type,
                    error_message=str(error),
                    user_id=user_id)

        # 使用新的異常系統
        if isinstance(error, NamecardException):
            return get_user_friendly_message(error, verbose=self.verbose)

        # 向後兼容：處理舊的錯誤訊息格式
        error_str = str(error).lower()
        if "unauthorized" in error_str:
            return "🔐 資料庫存取權限問題，請聯繫管理員"
        elif "not_found" in error_str:
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


def create_security_service(redis_client=None, use_redis: bool = True) -> SecurityService:
    """
    工廠函數：創建 SecurityService 實例

    Args:
        redis_client: Redis 客戶端（可選）
        use_redis: 是否使用 Redis

    Returns:
        SecurityService 實例
    """
    return SecurityService(redis_client=redis_client, use_redis=use_redis)


# 全域實例（默認使用記憶體存儲，需要手動初始化 Redis）
security_service = SecurityService(redis_client=None, use_redis=False)
error_handler = ErrorHandler()