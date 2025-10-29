"""
Notion Database 欄位名稱常數

此模組定義所有 Notion 資料庫欄位的標準名稱，確保程式碼中的一致性。
根據實際 Notion 資料庫的欄位名稱設定。

使用方法:
    from src.namecard.infrastructure.storage.notion_fields import NotionFields

    properties[NotionFields.NAME] = {...}
    filter = {"property": NotionFields.NAME, ...}
"""


class NotionFields:
    """Notion 資料庫欄位名稱常數"""

    # === 自動填寫欄位（由系統填入） ===

    # 基本資訊
    NAME = "Name"                    # 姓名 (title) - 必填
    EMAIL = "Email"                  # Email (email)
    COMPANY = "公司名稱"              # 公司名稱 (rich_text)
    PHONE = "電話"                    # 電話 (phone_number)
    ADDRESS = "地址"                  # 地址 (rich_text)

    # 職務資訊
    TITLE = "職稱"                    # 職稱 (select)
    DEPARTMENT = "部門"               # 部門 (rich_text)

    # 其他資訊
    NOTES = "備註"                    # 備註 (rich_text) - 用於存儲額外資訊

    # === 人工填寫欄位（保留空白） ===

    # 決策相關
    DECISION_INFLUENCE = "決策影響力"  # 決策影響力 (select) - 人工評估
    PAIN_POINTS = "窗口的困擾或 KPI"   # 窗口的困擾或 KPI (rich_text) - 人工填寫

    # 聯絡管理
    CONTACT_SOURCE = "取得聯絡來源"    # 取得聯絡來源 (rich_text) - 人工填寫
    CONTACT_NOTES = "聯絡注意事項"     # 聯絡注意事項 (rich_text) - 人工填寫
    RESPONSIBLE = "負責業務"          # 負責業務 (people) - 人工指派

    # 系統欄位（如果存在）
    LINE_USER = "LINE用戶"           # LINE 用戶 ID (rich_text)
    CREATED_TIME = "建立時間"         # 建立時間 (created_time)


class NotionFieldTypes:
    """Notion 欄位類型常數"""

    TITLE = "title"
    RICH_TEXT = "rich_text"
    EMAIL = "email"
    PHONE_NUMBER = "phone_number"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    PEOPLE = "people"
    DATE = "date"
    CREATED_TIME = "created_time"
    NUMBER = "number"


# 欄位分組 - 方便批量操作
class NotionFieldGroups:
    """欄位分組定義"""

    # 自動填寫的欄位
    AUTO_FILL = [
        NotionFields.NAME,
        NotionFields.EMAIL,
        NotionFields.COMPANY,
        NotionFields.PHONE,
        NotionFields.ADDRESS,
        NotionFields.TITLE,
        NotionFields.DEPARTMENT,
        NotionFields.NOTES,
    ]

    # 需要人工填寫的欄位
    MANUAL_FILL = [
        NotionFields.DECISION_INFLUENCE,
        NotionFields.PAIN_POINTS,
        NotionFields.CONTACT_SOURCE,
        NotionFields.CONTACT_NOTES,
        NotionFields.RESPONSIBLE,
    ]

    # 必填欄位
    REQUIRED = [
        NotionFields.NAME,
    ]

    # 聯絡方式欄位（至少需要一個）
    CONTACT_INFO = [
        NotionFields.EMAIL,
        NotionFields.PHONE,
        NotionFields.ADDRESS,
    ]


def validate_field_name(field_name: str) -> bool:
    """
    驗證欄位名稱是否有效

    Args:
        field_name: 欄位名稱

    Returns:
        是否為有效的欄位名稱
    """
    valid_fields = [
        getattr(NotionFields, attr)
        for attr in dir(NotionFields)
        if not attr.startswith('_')
    ]
    return field_name in valid_fields


def get_field_description(field_name: str) -> str:
    """
    獲取欄位說明

    Args:
        field_name: 欄位名稱

    Returns:
        欄位說明文字
    """
    descriptions = {
        NotionFields.NAME: "聯絡人姓名（必填）",
        NotionFields.EMAIL: "電子郵件地址",
        NotionFields.COMPANY: "公司/組織名稱",
        NotionFields.PHONE: "聯絡電話",
        NotionFields.ADDRESS: "地址",
        NotionFields.TITLE: "職稱",
        NotionFields.DEPARTMENT: "部門",
        NotionFields.NOTES: "備註（系統自動填入額外資訊）",
        NotionFields.DECISION_INFLUENCE: "決策影響力評估（人工填寫）",
        NotionFields.PAIN_POINTS: "客戶痛點或 KPI（人工填寫）",
        NotionFields.CONTACT_SOURCE: "聯絡來源（人工填寫）",
        NotionFields.CONTACT_NOTES: "聯絡注意事項（人工填寫）",
        NotionFields.RESPONSIBLE: "負責業務人員（人工指派）",
    }
    return descriptions.get(field_name, "未知欄位")
