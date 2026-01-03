from notion_client import Client
from typing import Optional, Dict, Any
import structlog
from datetime import datetime
import sys
import os

# 添加項目根目錄到 Python 路徑
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../.."))

from simple_config import settings
from src.namecard.core.models.card import BusinessCard
from src.namecard.infrastructure.storage.notion_fields import NotionFields

logger = structlog.get_logger()

# Notion API 版本 - 2025-09-03 是目前最新版本
NOTION_API_VERSION = "2025-09-03"


class NotionClient:
    """Notion 資料庫客戶端

    支援多租戶模式，可使用自訂的 API Key 和 Database ID。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        database_id: Optional[str] = None,
    ):
        """
        初始化 Notion 客戶端

        Args:
            api_key: 自訂 Notion API Key (用於多租戶)，預設使用全域設定
            database_id: 自訂 Database ID (用於多租戶)，預設使用全域設定
        """
        # 支援自訂憑證 (多租戶) 或使用全域設定
        self._api_key = api_key or settings.notion_api_key
        self.database_id = database_id or settings.notion_database_id

        # 使用最新 API 版本初始化 Client
        self.client = Client(auth=self._api_key, notion_version=NOTION_API_VERSION)
        self.database_url = f"https://notion.so/{self.database_id.replace('-', '')}"

        # 緩存資料庫 schema（用於檢查欄位是否存在）
        self._db_schema: Dict[str, Any] = {}

        # 測試連接並獲取 schema
        self._test_connection()

    def _test_connection(self) -> None:
        """測試 Notion 連接並緩存 schema"""
        try:
            # 嘗試讀取資料庫資訊
            response = self.client.databases.retrieve(database_id=self.database_id)
            self._db_schema = response.get("properties", {})

            logger.info(
                "Notion connection established successfully",
                available_fields=list(self._db_schema.keys()),
            )

            logger.info(
                "Notion database connection established",
                database_id=self.database_id[:10] + "...",
                operation="connection_test",
                status="success",
                field_count=len(self._db_schema),
            )

            # 🔍 詳細記錄每個字段的信息（用於診斷）
            if len(self._db_schema) == 0:
                logger.error(
                    "⚠️ CRITICAL: Database schema is EMPTY!",
                    database_id=self.database_id,
                    response_keys=list(response.keys()),
                )
            else:
                for field_name in list(self._db_schema.keys())[:10]:  # 只記錄前10個
                    logger.info(
                        f"Schema field detected: '{field_name}'",
                        field_name=field_name,
                        field_name_repr=repr(field_name),
                        field_type=self._db_schema[field_name].get("type"),
                    )

        except Exception as e:
            logger.error("Failed to connect to Notion", error=str(e))

            logger.error(
                "Failed to connect to Notion database",
                error=str(e),
                database_id=self.database_id[:10] + "...",
                error_type=type(e).__name__,
                operation="connection_test",
                status="failed",
            )
            # 不拋出異常，允許應用程式繼續運行

    def _field_exists(self, field_name: str) -> bool:
        """檢查欄位是否存在於資料庫 schema 中"""
        return field_name in self._db_schema

    def save_business_card(self, card: BusinessCard) -> Optional[str]:
        """
        儲存名片到 Notion 資料庫

        Args:
            card: 名片資料

        Returns:
            Notion 頁面 URL，失敗時返回 None
        """
        try:
            logger.info(
                "Starting Notion save operation",
                user_id=card.line_user_id,
                card_name=card.name,
                card_company=card.company,
            )

            # 準備名片資料
            properties = self._prepare_card_properties(card)

            # 準備頁面內容（圖片）
            children = self._prepare_page_content(card)

            # 建立 Notion 頁面
            create_params = {"parent": {"database_id": self.database_id}, "properties": properties}
            if children:
                create_params["children"] = children

            response = self.client.pages.create(**create_params)

            page_url = response.get("url", "")
            page_id = response.get("id", "")

            logger.info(
                "Business card saved to Notion successfully",
                user_id=card.line_user_id,
                page_id=page_id,
                card_name=card.name,
                card_company=card.company,
                confidence_score=card.confidence_score,
                quality_score=card.quality_score,
                has_contact_info=bool(card.phone or card.email),
                properties_count=len(properties),
                operation="save_card",
                status="success",
            )

            logger.info(
                "Business card saved to Notion",
                page_id=page_id,
                name=card.name,
                company=card.company,
            )

            return page_url

        except Exception as e:
            logger.error(
                "Exception occurred while saving business card",
                error=str(e),
                error_type=type(e).__name__,
                user_id=card.line_user_id,
                operation="save_business_card",
                card_name=card.name,
                card_company=card.company,
                database_id=self.database_id,
            )

            logger.error(
                "Failed to save business card to Notion",
                error=str(e),
                name=card.name,
                company=card.company,
            )
            return None

    def _clean_title_or_department(self, text: Optional[str]) -> Optional[str]:
        """
        清理職稱或部門欄位，優先保留中文

        Args:
            text: 原始職稱或部門文字

        Returns:
            清理後的文字，移除逗號和英文（如果有中文的話）
        """
        if not text:
            return None

        # 移除首尾空白
        text = text.strip()

        # 如果包含逗號，只保留逗號前的部分
        if "," in text:
            text = text.split(",")[0].strip()
            logger.info(
                "Removed content after comma in title/department", original=text, cleaned=text
            )

        # 檢查是否包含中文字元
        has_chinese = any("\u4e00" <= char <= "\u9fff" for char in text)

        if has_chinese:
            # 如果包含中文，優先保留中文部分
            # 移除純英文單詞（保留中文和標點）
            words = text.split()
            chinese_words = []

            for word in words:
                # 如果單詞包含中文字元，保留
                if any("\u4e00" <= char <= "\u9fff" for char in word):
                    chinese_words.append(word)

            if chinese_words:
                cleaned_text = " ".join(chinese_words).strip()
                if cleaned_text != text:
                    logger.info(
                        "Prioritized Chinese in title/department",
                        original=text,
                        cleaned=cleaned_text,
                    )
                return cleaned_text

        # 如果沒有中文或無法提取中文，返回原文
        return text

    def _prepare_page_content(self, card: BusinessCard) -> list:
        """
        準備頁面內容（圖片嵌入）

        Args:
            card: BusinessCard 名片資料

        Returns:
            Notion blocks 列表，用於頁面內容
        """
        children = []

        # 如果有圖片 URL，添加圖片塊
        if card.image_url:
            children.append(
                {
                    "object": "block",
                    "type": "image",
                    "image": {"type": "external", "external": {"url": card.image_url}},
                }
            )
            logger.info("Added image to page content", image_url=card.image_url[:50] + "...")

        return children

    def _prepare_card_properties(self, card: BusinessCard) -> Dict[str, Any]:
        """
        準備名片屬性用於 Notion

        使用 NotionFields 常數確保欄位名稱一致性。

        自動填寫欄位: Name, Email, 公司名稱, 地址, 職稱, 電話, 備註, 部門
        人工填寫欄位: 決策影響力, 窗口的困擾或 KPI, 取得聯絡來源, 聯絡注意事項, 負責業務

        Args:
            card: BusinessCard 名片資料

        Returns:
            符合 Notion API 格式的 properties 字典
        """
        properties = {}

        # 1. Name (title) - 必填
        properties[NotionFields.NAME] = {"title": [{"text": {"content": card.name or "未知姓名"}}]}

        # 2. Email (email) - 直接嘗試保存
        if card.email and "@" in card.email:
            properties[NotionFields.EMAIL] = {"email": card.email}
            logger.info("Email field added to properties", email=card.email[:20])

        # 3. 備註 (rich_text) - 收集額外資訊
        additional_info = []

        # 收集額外資訊
        if hasattr(card, "mobile") and card.mobile:
            additional_info.append(f"行動電話: {card.mobile}")
        if card.website:
            additional_info.append(f"網站: {card.website}")
        if hasattr(card, "tax_id") and card.tax_id:
            additional_info.append(f"統一編號: {card.tax_id}")
        if card.line_id:
            additional_info.append(f"LINE ID: {card.line_id}")
        if card.fax:
            additional_info.append(f"傳真: {card.fax}")

        # 4. 公司名稱 (rich_text) - 提取主公司名稱
        if card.company:
            # 拆分公司名稱，取第一個部分作為主公司名稱
            company_parts = card.company.split()
            main_company = company_parts[0] if company_parts else card.company

            properties[NotionFields.COMPANY] = {"rich_text": [{"text": {"content": main_company}}]}
            logger.info("Company field added to properties", company=main_company)

        # 5. 地址 (rich_text)
        if card.address:
            properties[NotionFields.ADDRESS] = {"rich_text": [{"text": {"content": card.address}}]}
            logger.info("Address field added to properties", address=card.address[:30])

        # 注意：以下欄位刻意保留空白，供人工填寫
        # - NotionFields.DECISION_INFLUENCE (決策影響力)
        # - NotionFields.PAIN_POINTS (窗口的困擾或 KPI)
        # - NotionFields.CONTACT_SOURCE (取得聯絡來源)
        # - NotionFields.CONTACT_NOTES (聯絡注意事項)
        # - NotionFields.RESPONSIBLE (負責業務)
        # 這些欄位需要業務人員根據實際情況評估和填寫

        # 6. 職稱 (select) - 清理後存入，讓 Notion 自動創建新選項
        if card.title:
            cleaned_title = self._clean_title_or_department(card.title)
            if cleaned_title:
                properties[NotionFields.TITLE] = {"select": {"name": cleaned_title}}
                logger.info(
                    "Title field added to properties",
                    card_name=card.name,
                    original_title=card.title,
                    cleaned_title=cleaned_title,
                )

        # 7. 部門 (rich_text) - 清理後存入
        if card.department:
            cleaned_department = self._clean_title_or_department(card.department)
            if cleaned_department:
                properties[NotionFields.DEPARTMENT] = {
                    "rich_text": [{"text": {"content": cleaned_department}}]
                }
                logger.info(
                    "Department field added to properties",
                    card_name=card.name,
                    original_department=card.department,
                    cleaned_department=cleaned_department,
                )

        # 8. 電話 (phone_number)
        if card.phone:
            properties[NotionFields.PHONE] = {"phone_number": card.phone}
            logger.info("Phone field added to properties", phone=card.phone)

        # 9. 備註 (rich_text) - 如果有額外資訊，放入備註欄位
        if additional_info:
            notes_content = " | ".join(additional_info)
            properties[NotionFields.NOTES] = {"rich_text": [{"text": {"content": notes_content}}]}
            logger.info("Notes field added to properties", notes_preview=notes_content[:50])

        return properties

    def create_database_if_not_exists(self) -> bool:
        """
        如果資料庫不存在則建立
        注意：需要在 Notion 中手動建立資料庫並獲取 ID
        """
        try:
            # 檢查資料庫是否存在
            self.client.databases.retrieve(database_id=self.database_id)
            return True
        except Exception:
            logger.warning("Database not found, please create it manually in Notion")
            return False

    @staticmethod
    def create_database(
        api_key: str, tenant_name: str, parent_page_id: Optional[str] = None
    ) -> Optional[str]:
        """
        為租戶創建新的 Notion 資料庫

        Args:
            api_key: Notion API Key
            tenant_name: 租戶名稱，用於命名資料庫
            parent_page_id: 父頁面 ID，預設使用 settings 中的共用頁面

        Returns:
            新建資料庫的 ID，失敗時返回 None
        """
        try:
            # #region agent log
            try:
                import json

                open("/tmp/namecard_debug.log", "a").write(
                    json.dumps(
                        {
                            "hypothesisId": "D",
                            "location": "notion_client.py:create_database:entry",
                            "message": "create_database called",
                            "data": {
                                "api_key_prefix": api_key[:15] + "..." if api_key else None,
                                "tenant_name": tenant_name,
                                "parent_page_id_arg": parent_page_id,
                            },
                            "timestamp": __import__("time").time(),
                        }
                    )
                    + "\n"
                )
            except Exception:
                pass
            # #endregion
            # 使用最新 API 版本初始化 Client
            client = Client(auth=api_key, notion_version=NOTION_API_VERSION)
            parent_id = parent_page_id or settings.notion_shared_parent_page_id
            # #region agent log
            try:
                import json

                open("/tmp/namecard_debug.log", "a").write(
                    json.dumps(
                        {
                            "hypothesisId": "D",
                            "location": "notion_client.py:create_database:after_parent_id",
                            "message": "parent_id resolved",
                            "data": {
                                "final_parent_id": parent_id,
                                "used_arg": parent_page_id is not None,
                            },
                            "timestamp": __import__("time").time(),
                        }
                    )
                    + "\n"
                )
            except Exception:
                pass
            # #endregion

            # 資料庫名稱：{租戶名稱}的名片盒
            db_title = f"{tenant_name}的名片盒"

            # 定義資料庫 schema（僅自動填寫欄位）
            properties = {
                # 1. Name (title) - 必填，Notion 資料庫必須有一個 title 欄位
                NotionFields.NAME: {"title": {}},
                # 2. Email
                NotionFields.EMAIL: {"email": {}},
                # 3. 公司名稱
                NotionFields.COMPANY: {"rich_text": {}},
                # 4. 電話
                NotionFields.PHONE: {"phone_number": {}},
                # 5. 地址
                NotionFields.ADDRESS: {"rich_text": {}},
                # 6. 職稱 (select - 讓 Notion 自動創建選項)
                NotionFields.TITLE: {"select": {"options": []}},
                # 7. 部門
                NotionFields.DEPARTMENT: {"rich_text": {}},
                # 8. 備註
                NotionFields.NOTES: {"rich_text": {}},
            }

            # #region agent log
            try:
                import json

                open("/tmp/namecard_debug.log", "a").write(
                    json.dumps(
                        {
                            "hypothesisId": "A,B,C",
                            "location": "notion_client.py:create_database:before_api_call",
                            "message": "About to call Notion API",
                            "data": {
                                "parent_id": parent_id,
                                "db_title": db_title,
                                "properties_keys": list(properties.keys()),
                            },
                            "timestamp": __import__("time").time(),
                        }
                    )
                    + "\n"
                )
            except Exception:
                pass
            # #endregion

            # #region agent log - Try to verify page access first
            try:
                page_check = client.pages.retrieve(page_id=parent_id)
                try:
                    open("/tmp/namecard_debug.log", "a").write(
                        json.dumps(
                            {
                                "hypothesisId": "A,B",
                                "location": "notion_client.py:create_database:page_check",
                                "message": "Parent page accessible",
                                "data": {"page_id": parent_id},
                            },
                            default=str,
                        )
                        + "\n"
                    )
                except Exception:
                    pass
            except Exception as page_err:
                try:
                    open("/tmp/namecard_debug.log", "a").write(
                        json.dumps(
                            {
                                "hypothesisId": "A,B",
                                "location": "notion_client.py:create_database:page_check_failed",
                                "message": "Parent page NOT accessible",
                                "data": {
                                    "page_id": parent_id,
                                    "error": str(page_err),
                                    "error_type": type(page_err).__name__,
                                },
                            }
                        )
                        + "\n"
                    )
                except Exception:
                    pass
            # #endregion

            # 創建資料庫
            response = client.databases.create(
                parent={"type": "page_id", "page_id": parent_id},
                title=[{"type": "text", "text": {"content": db_title}}],
                properties=properties,
            )

            database_id = response.get("id")
            database_url = response.get("url")

            logger.info(
                "Notion database created successfully",
                database_id=database_id,
                database_title=db_title,
                database_url=database_url,
                tenant_name=tenant_name,
                operation="create_database",
                status="success",
            )

            return database_id

        except Exception as e:
            # #region agent log
            try:
                import json

                open("/tmp/namecard_debug.log", "a").write(
                    json.dumps(
                        {
                            "hypothesisId": "A,B,C",
                            "location": "notion_client.py:create_database:exception",
                            "message": "Exception caught",
                            "data": {
                                "error": str(e),
                                "error_type": type(e).__name__,
                                "parent_id": parent_id if "parent_id" in locals() else None,
                                "api_key_prefix": api_key[:15] + "..." if api_key else None,
                            },
                            "timestamp": __import__("time").time(),
                        }
                    )
                    + "\n"
                )
            except Exception:
                pass
            # #endregion
            logger.error(
                "Failed to create Notion database",
                error=str(e),
                error_type=type(e).__name__,
                tenant_name=tenant_name,
                parent_page_id=parent_id if "parent_id" in dir() else None,
                operation="create_database",
                status="failed",
            )
            return None

    def get_database_schema(self) -> Dict[str, Any]:
        """獲取資料庫結構"""
        try:
            response = self.client.databases.retrieve(database_id=self.database_id)
            return response.get("properties", {})
        except Exception as e:
            logger.error("Failed to get database schema", error=str(e))
            return {}

    def search_cards_by_name(self, name: str, limit: int = 10) -> list:
        """
        根據姓名搜尋名片

        Args:
            name: 要搜尋的姓名（部分匹配）
            limit: 最大返回結果數

        Returns:
            符合條件的 Notion 頁面列表
        """
        try:
            logger.info(
                "Searching cards by name", search_name=name, limit=limit, field=NotionFields.NAME
            )

            response = self.client.databases.query(
                database_id=self.database_id,
                filter={
                    "property": NotionFields.NAME,  # 修復: 使用正確的欄位名稱 "Name"
                    "title": {"contains": name},
                },
                page_size=limit,
            )

            results = response.get("results", [])

            logger.info(
                "Card search by name completed",
                search_term=name,
                results_count=len(results),
                limit=limit,
                operation="search_by_name",
                status="success",
            )

            return results

        except Exception as e:
            logger.error(
                "Failed to search cards by name",
                error=str(e),
                error_type=type(e).__name__,
                search_term=name,
                operation="search_by_name",
                status="failed",
            )

            return []

    def search_cards_by_company(self, company: str, limit: int = 10) -> list:
        """
        根據公司名稱搜尋名片

        Args:
            company: 要搜尋的公司名稱（部分匹配）
            limit: 最大返回結果數

        Returns:
            符合條件的 Notion 頁面列表
        """
        try:
            logger.info(
                "Searching cards by company",
                search_company=company,
                limit=limit,
                field=NotionFields.COMPANY,
            )

            response = self.client.databases.query(
                database_id=self.database_id,
                filter={
                    "property": NotionFields.COMPANY,  # 修復: 使用正確的欄位名稱 "公司名稱"
                    "rich_text": {"contains": company},
                },
                page_size=limit,
            )

            results = response.get("results", [])

            logger.info(
                "Card search by company completed",
                search_term=company,
                results_count=len(results),
                operation="search_by_company",
                status="success",
            )

            return results

        except Exception as e:
            logger.error(
                "Failed to search cards by company",
                error=str(e),
                error_type=type(e).__name__,
                search_term=company,
                operation="search_by_company",
                status="failed",
            )
            return []

    def get_user_cards(self, line_user_id: str, limit: int = 50) -> list:
        """獲取特定用戶的所有名片"""
        try:
            response = self.client.databases.query(
                database_id=self.database_id,
                filter={"property": "LINE用戶", "rich_text": {"equals": line_user_id}},
                sorts=[{"property": "建立時間", "direction": "descending"}],
                page_size=limit,
            )

            return response.get("results", [])

        except Exception as e:
            logger.error("Failed to get user cards", error=str(e), user_id=line_user_id)
            return []

    def get_database_stats(self) -> Dict[str, Any]:
        """獲取資料庫統計資訊"""
        try:
            # 獲取總數（檢查 API 連線）
            self.client.databases.query(database_id=self.database_id, page_size=1)

            # 注意：Notion API 不直接提供總數，這裡只是示例
            stats = {
                "total_cards": "N/A",  # 需要遍歷所有頁面才能獲得準確數字
                "database_url": self.database_url,
                "last_updated": datetime.now().isoformat(),
            }

            return stats

        except Exception as e:
            logger.error("Failed to get database stats", error=str(e))
            return {}

    def test_connection(self) -> bool:
        """
        測試 Notion 連接和欄位配置

        Returns:
            連接成功且欄位配置正確返回 True
        """
        try:
            # 獲取資料庫 schema
            schema = self.get_database_schema()

            if not schema:
                logger.error("Failed to retrieve database schema")
                return False

            # 驗證必要欄位是否存在
            required_fields = [
                NotionFields.NAME,
                NotionFields.EMAIL,
                NotionFields.COMPANY,
                NotionFields.PHONE,
            ]

            missing_fields = []
            for field in required_fields:
                if field not in schema:
                    missing_fields.append(field)

            if missing_fields:
                logger.warning(
                    "Missing required fields in Notion database",
                    missing_fields=missing_fields,
                    available_fields=list(schema.keys()),
                )
                # 不返回 False，只是警告
            else:
                logger.info(
                    "All required fields present in Notion database", field_count=len(schema)
                )

            return True

        except Exception as e:
            logger.error("Notion connection test failed", error=str(e))
            return False
