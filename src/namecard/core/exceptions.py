"""
自定義異常類別，用於詳細的錯誤分類和用戶友善的錯誤訊息
"""

from typing import Optional, Dict, Any


class NamecardException(Exception):
    """基礎異常類別"""

    def __init__(self, message: str, user_message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.user_message = user_message  # 顯示給用戶的訊息
        self.details = details or {}  # 額外的除錯資訊


# ==================== AI 處理相關異常 ====================


class AIProcessingError(NamecardException):
    """AI 處理基礎異常"""

    pass


class APIKeyInvalidError(AIProcessingError):
    """Google API 金鑰無效"""

    def __init__(self, details: Optional[Dict[str, Any]] = None):
        message = "Google Gemini API key is invalid or expired"
        user_message = (
            "🔑 Google Gemini API 金鑰無效\n\n"
            "請通知 IT 檢查環境變數：\n"
            "• GOOGLE_API_KEY 是否正確設定\n"
            "• API 金鑰是否已過期"
        )
        super().__init__(message, user_message, details)


class APIQuotaExceededError(AIProcessingError):
    """API 配額已用完"""

    def __init__(self, details: Optional[Dict[str, Any]] = None):
        message = "Google Gemini API quota exceeded"

        # 檢查是否兩個 key 都用完
        both_keys_exhausted = details.get("both_keys_exhausted", False) if details else False
        already_using_fallback = details.get("already_using_fallback", False) if details else False

        if both_keys_exhausted:
            user_message = (
                "⚠️ 所有 Google Gemini API 配額已用完\n\n"
                "主要和備用 API Key 配額都已達上限\n\n"
                "請通知 IT 部門：\n"
                "• 檢查兩個 API Key 的配額狀態\n"
                "• 等待配額重置（通常每日 00:00 UTC）\n"
                "• 或升級 API 配額方案"
            )
        elif already_using_fallback:
            user_message = (
                "⚠️ Fallback API 配額已用完\n\n"
                "目前使用的是備用 API Key，配額也已達上限\n\n"
                "請通知 IT 部門：\n"
                "• 檢查 GOOGLE_API_KEY_FALLBACK 配額\n"
                "• 等待配額重置（通常每日 00:00 UTC）"
            )
        else:
            user_message = (
                "⚠️ Google Gemini API 配額已用完\n\n"
                "請通知 IT 部門檢查：\n"
                "• GOOGLE_API_KEY 配額狀態\n"
                "• 是否需要設定 GOOGLE_API_KEY_FALLBACK\n"
                "• 或等待配額重置（通常每日 00:00 UTC）"
            )

        super().__init__(message, user_message, details)


class SafetyFilterBlockedError(AIProcessingError):
    """圖片被 Gemini 安全過濾器阻擋"""

    def __init__(self, finish_reason: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        message = f"Image blocked by Gemini safety filter (finish_reason={finish_reason})"
        user_message = (
            "📷 無法識別這張圖片\n\n"
            "可能原因：\n"
            "• 圖片模糊或光線不足\n"
            "• 名片被遮擋或不完整\n"
            "• 圖片內容無法辨識\n\n"
            "💡 建議：請重新拍攝一張清晰的名片照片"
        )
        super().__init__(message, user_message, details)


class LowQualityCardError(AIProcessingError):
    """名片品質過低"""

    def __init__(
        self,
        confidence_score: Optional[float] = None,
        quality_score: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        message = f"Card quality too low (confidence={confidence_score}, quality={quality_score})"
        user_message = "📊 名片品質過低\n\n"

        if confidence_score is not None:
            user_message += f"信心度：{int(confidence_score * 100)}%\n"
        if quality_score is not None:
            user_message += f"品質分數：{int(quality_score * 100)}%\n"

        user_message += "\n建議：請重新拍攝清晰完整的名片照片"
        super().__init__(message, user_message, details)


class IncompleteCardDataError(AIProcessingError):
    """名片資訊不完整"""

    def __init__(self, missing_fields: list, found_fields: Optional[Dict[str, str]] = None, details: Optional[Dict[str, Any]] = None):
        message = f"Card data incomplete, missing: {', '.join(missing_fields)}"
        user_message = "📝 名片資訊不完整\n\n"

        if found_fields:
            user_message += "已識別：\n"
            for field, value in found_fields.items():
                user_message += f"✓ {field}：{value}\n"
            user_message += "\n"

        user_message += "缺少：\n"
        for field in missing_fields:
            user_message += f"✗ {field}\n"

        user_message += "\n請確認名片是否包含完整資訊"
        super().__init__(message, user_message, details)


class LowResolutionImageError(AIProcessingError):
    """圖片解析度過低"""

    def __init__(self, width: int, height: int, details: Optional[Dict[str, Any]] = None):
        message = f"Image resolution too low ({width}x{height})"
        user_message = (
            f"🖼️ 圖片解析度過低\n\n"
            f"目前：{width} x {height} 像素\n"
            f"最低需求：300 x 300 像素\n\n"
            f"建議：請使用更高解析度的圖片"
        )
        super().__init__(message, user_message, details)


class JSONParsingError(AIProcessingError):
    """AI 回應的 JSON 格式錯誤"""

    def __init__(self, raw_response: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        message = "Failed to parse AI response as JSON"
        user_message = (
            "📄 AI 回應格式錯誤\n\n"
            "請通知 IT 部門檢查：\n"
            "• Gemini API 回應格式\n"
            "• 是否需要更新 prompt 模板"
        )
        if raw_response:
            user_message += f"\n\n原始回應前 100 字：\n{raw_response[:100]}..."
        super().__init__(message, user_message, details)


class EmptyAIResponseError(AIProcessingError):
    """AI 回應為空"""

    def __init__(self, details: Optional[Dict[str, Any]] = None):
        message = "AI returned empty response"
        user_message = (
            "🤖 AI 未能分析此圖片\n\n"
            "可能原因：\n"
            "• 圖片中沒有名片\n"
            "• 圖片內容無法識別\n\n"
            "建議：請確認圖片包含清晰的名片"
        )
        super().__init__(message, user_message, details)


class NetworkError(AIProcessingError):
    """網路連線錯誤"""

    def __init__(self, details: Optional[Dict[str, Any]] = None):
        message = "Network connection failed"
        user_message = (
            "🌐 網路連線問題\n\n"
            "請檢查：\n"
            "• 網路連線是否正常\n"
            "• Google API 是否可訪問\n\n"
            "或稍後重試"
        )
        super().__init__(message, user_message, details)


class APITimeoutError(AIProcessingError):
    """API 請求超時"""

    def __init__(self, timeout_seconds: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        message = f"API request timeout (timeout={timeout_seconds}s)"
        user_message = "⏱️ AI 處理超時\n\n"
        if timeout_seconds:
            user_message += f"等待時間：{timeout_seconds} 秒\n\n"
        user_message += "建議：請稍後重試"
        super().__init__(message, user_message, details)


# ==================== Notion 儲存相關異常 ====================


class NotionStorageError(NamecardException):
    """Notion 儲存基礎異常"""

    pass


class NotionUnauthorizedError(NotionStorageError):
    """Notion API 權限不足"""

    def __init__(self, details: Optional[Dict[str, Any]] = None):
        message = "Notion API unauthorized"
        user_message = (
            "🔐 Notion 資料庫存取權限不足\n\n"
            "請通知 IT 檢查：\n"
            "• NOTION_API_KEY 是否有效\n"
            "• Integration 是否已分享至資料庫\n"
            "• API Token 權限設定"
        )
        super().__init__(message, user_message, details)


class NotionDatabaseNotFoundError(NotionStorageError):
    """Notion 資料庫不存在"""

    def __init__(self, database_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        message = f"Notion database not found (database_id={database_id})"
        user_message = "📁 找不到指定的 Notion 資料庫\n\n"
        if database_id:
            user_message += f"Database ID：{database_id}\n\n"
        user_message += (
            "請通知 IT 檢查：\n"
            "• NOTION_DATABASE_ID 是否正確\n"
            "• 資料庫是否已被刪除或移動"
        )
        super().__init__(message, user_message, details)


class NotionSchemaError(NotionStorageError):
    """Notion 資料庫 Schema 不匹配"""

    def __init__(self, missing_properties: Optional[list] = None, details: Optional[Dict[str, Any]] = None):
        message = f"Notion database schema mismatch (missing={missing_properties})"
        user_message = "🔧 Notion 資料庫欄位設定錯誤\n\n"

        if missing_properties:
            user_message += "缺少的欄位：\n"
            for prop in missing_properties:
                user_message += f"• {prop}\n"
            user_message += "\n"

        user_message += (
            "請通知 IT 檢查：\n"
            "• 資料庫欄位名稱是否正確\n"
            "• 欄位類型是否匹配\n"
            "• 必填欄位是否都已建立"
        )
        super().__init__(message, user_message, details)


class NotionRateLimitError(NotionStorageError):
    """Notion API 速率限制"""

    def __init__(self, details: Optional[Dict[str, Any]] = None):
        message = "Notion API rate limit exceeded"
        user_message = (
            "⏱️ Notion API 操作過於頻繁\n\n"
            "目前已達到 Notion API 速率限制\n"
            "請稍後再試（約 1-2 分鐘）"
        )
        super().__init__(message, user_message, details)


class NotionNetworkError(NotionStorageError):
    """無法連線到 Notion"""

    def __init__(self, details: Optional[Dict[str, Any]] = None):
        message = "Cannot connect to Notion API"
        user_message = (
            "🌐 無法連線到 Notion 資料庫\n\n"
            "請檢查：\n"
            "• 網路連線是否正常\n"
            "• Notion 服務是否正常\n\n"
            "或稍後重試"
        )
        super().__init__(message, user_message, details)


# ==================== 輔助函數 ====================


def get_user_friendly_message(exception: Exception, verbose: bool = False) -> str:
    """
    從異常中提取用戶友善的錯誤訊息

    Args:
        exception: 異常物件
        verbose: 是否顯示詳細的技術錯誤訊息（開發模式）

    Returns:
        用戶友善的錯誤訊息
    """
    if isinstance(exception, NamecardException):
        message = exception.user_message
        if verbose:
            message += f"\n\n【技術細節】\n錯誤類型：{type(exception).__name__}\n錯誤訊息：{str(exception)}"
            if exception.details:
                message += f"\n額外資訊：{exception.details}"
        return message

    # 非自定義異常，返回預設訊息
    if verbose:
        return f"❌ 系統錯誤\n\n【技術細節】\n{type(exception).__name__}: {str(exception)}"
    else:
        return "❌ 系統錯誤，請稍後重試"
