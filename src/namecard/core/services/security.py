"""安全性和錯誤處理服務"""

import hashlib
import hmac
from typing import Dict, Optional, Any
from collections import defaultdict
from datetime import datetime
import structlog
import base64
import os
import sys

# 添加專案根目錄到 Python 路徑
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

from simple_config import settings
from src.namecard.core.exceptions import (
    NamecardException,
    get_user_friendly_message,
)

logger = structlog.get_logger()


class SecurityService:
    """安全性服務（無狀態：簽名驗證、輸入清理、圖片驗證、安全事件記錄）"""

    def __init__(self):
        logger.info("SecurityService initialized")

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

    def sanitize_input(self, text: str, max_length: int = 1000) -> str:
        """清理輸入文字"""
        if not text:
            return ""

        # 限制長度
        text = text[:max_length]

        # 移除潛在危險字元
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
    """錯誤處理器（支援詳細的使用者友善錯誤訊息）"""

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
            user_id: 使用者 ID

        Returns:
            使用者友善的錯誤訊息
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

        # 向後相容：處理舊的錯誤訊息格式
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
            user_id: 使用者 ID

        Returns:
            使用者友善的錯誤訊息
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

        # 向後相容：處理舊的錯誤訊息格式
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

        # LINE API 錯誤通常不需要回應使用者
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


# 全域單例
security_service = SecurityService()
error_handler = ErrorHandler()
