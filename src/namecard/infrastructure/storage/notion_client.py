from notion_client import Client
from typing import Optional, Dict, Any
import structlog
from datetime import datetime
import sys
import os

# 添加項目根目錄到 Python 路徑
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../..'))

from simple_config import settings
from src.namecard.core.models.card import BusinessCard
from src.namecard.core.services.monitoring import (
    monitoring_service, monitor_performance,
    MonitoringEvent, EventCategory, MonitoringLevel
)

logger = structlog.get_logger()


class NotionClient:
    """Notion 資料庫客戶端"""
    
    def __init__(self):
        self.client = Client(auth=settings.notion_api_key)
        self.database_id = settings.notion_database_id
        self.database_url = f"https://notion.so/{settings.notion_database_id.replace('-', '')}"
        
        # 測試連接
        self._test_connection()
    
    def _test_connection(self) -> None:
        """測試 Notion 連接"""
        try:
            # 嘗試讀取資料庫資訊
            self.client.databases.retrieve(database_id=self.database_id)
            logger.info("Notion connection established successfully")
            
            # 記錄成功的連接
            monitoring_service.capture_event(MonitoringEvent(
                category=EventCategory.DATA_STORAGE,
                level=MonitoringLevel.INFO,
                message="Notion database connection established",
                extra_data={"database_id": self.database_id[:10] + "..."},
                tags={"operation": "connection_test", "status": "success"}
            ))
            
        except Exception as e:
            logger.error("Failed to connect to Notion", error=str(e))
            
            # 記錄連接失敗
            monitoring_service.capture_event(MonitoringEvent(
                category=EventCategory.DATA_STORAGE,
                level=MonitoringLevel.ERROR,
                message="Failed to connect to Notion database",
                extra_data={
                    "error": str(e),
                    "database_id": self.database_id[:10] + "...",
                    "error_type": type(e).__name__
                },
                tags={"operation": "connection_test", "status": "failed"}
            ))
            # 不拋出異常，允許應用程式繼續運行
    
    @monitor_performance("notion_save_card")
    def save_business_card(self, card: BusinessCard) -> Optional[str]:
        """
        儲存名片到 Notion 資料庫
        
        Args:
            card: 名片資料
            
        Returns:
            Notion 頁面 URL，失敗時返回 None
        """
        try:
            # 設定用戶上下文
            monitoring_service.set_user_context(card.line_user_id)
            monitoring_service.add_breadcrumb("Starting Notion save operation", "data_storage", {
                "card_name": card.name,
                "card_company": card.company
            })
            
            # 準備名片資料
            properties = self._prepare_card_properties(card)
            
            # 建立 Notion 頁面
            response = self.client.pages.create(
                parent={"database_id": self.database_id},
                properties=properties
            )
            
            page_url = response.get("url", "")
            page_id = response.get("id", "")
            
            # 記錄成功的儲存事件
            monitoring_service.capture_event(MonitoringEvent(
                category=EventCategory.DATA_STORAGE,
                level=MonitoringLevel.INFO,
                message="Business card saved to Notion successfully",
                user_id=card.line_user_id,
                extra_data={
                    "page_id": page_id,
                    "card_name": card.name,
                    "card_company": card.company,
                    "confidence_score": card.confidence_score,
                    "quality_score": card.quality_score,
                    "has_contact_info": bool(card.phone or card.email),
                    "properties_count": len(properties)
                },
                tags={"operation": "save_card", "status": "success"}
            ))
            
            logger.info("Business card saved to Notion", 
                       page_id=page_id,
                       name=card.name,
                       company=card.company)
            
            return page_url
            
        except Exception as e:
            # 記錄儲存失敗事件
            monitoring_service.capture_exception_with_context(
                e,
                EventCategory.DATA_STORAGE,
                user_id=card.line_user_id,
                extra_context={
                    "operation": "save_business_card",
                    "card_name": card.name,
                    "card_company": card.company,
                    "database_id": self.database_id
                }
            )
            
            logger.error("Failed to save business card to Notion", 
                        error=str(e),
                        name=card.name,
                        company=card.company)
            return None
    
    def _prepare_card_properties(self, card: BusinessCard) -> Dict[str, Any]:
        """準備名片屬性用於 Notion（嚴格對應實際資料庫欄位）"""
        properties = {}
        
        # 根據 /debug/notion 檢查的確切欄位名稱設置
        # 自動填寫：Email, Name, 備註, 公司名稱, 地址, 決策影響力, 窗口的困擾或 KPI, 職稱, 部門, 電話
        # 人工輸入：取得聯絡來源, 聯絡注意事項, 負責業務
        
        # 1. Name (title) - 必填
        properties["Name"] = {
            "title": [
                {
                    "text": {
                        "content": card.name or "未知姓名"
                    }
                }
            ]
        }
        
        # 2. Email (email)
        if card.email and "@" in card.email:
            properties["Email"] = {
                "email": card.email
            }
        
        # 3. 備註 (rich_text) - 記錄額外資訊
        notes = []
        if card.fax:
            notes.append(f"傳真: {card.fax}")
        if hasattr(card, 'mobile') and card.mobile:
            notes.append(f"行動電話: {card.mobile}")
        if card.website:
            notes.append(f"網站: {card.website}")
        if hasattr(card, 'tax_id') and card.tax_id:
            notes.append(f"統一編號: {card.tax_id}")
        if card.line_id:
            notes.append(f"LINE ID: {card.line_id}")
        if card.line_user_id:
            notes.append(f"發送者: {card.line_user_id}")
        
        if notes:
            properties["備註"] = {
                "rich_text": [
                    {
                        "text": {
                            "content": " | ".join(notes)
                        }
                    }
                ]
            }
        
        # 4. 公司名稱 (rich_text) - 提取主公司名稱
        if card.company:
            # 拆分公司名稱，取第一個部分作為主公司名稱
            company_parts = card.company.split()
            main_company = company_parts[0] if company_parts else card.company
            
            properties["公司名稱"] = {
                "rich_text": [
                    {
                        "text": {
                            "content": main_company
                        }
                    }
                ]
            }
        
        # 5. 地址 (rich_text)
        if card.address:
            properties["地址"] = {
                "rich_text": [
                    {
                        "text": {
                            "content": card.address
                        }
                    }
                ]
            }
        
        # 6. 決策影響力 (select) - 使用確切的選項值
        available_influence = ["最終決策者","關鍵影響者","技術評估者","用戶代表（場務總管）","資訊蒐集者","高","低","中"]
        
        influence = "中"  # 預設值
        if card.title:
            if any(title in card.title for title in ["董事長", "CEO", "執行長", "總經理"]):
                influence = "最終決策者"
            elif any(title in card.title for title in ["副總", "經理", "協理"]):
                influence = "關鍵影響者"
            elif any(title in card.title for title in ["工程師", "技術"]):
                influence = "技術評估者"
            elif "業務" in card.title:
                influence = "用戶代表（場務總管）"
            elif "專員" in card.title:
                influence = "資訊蒐集者"
        
        properties["決策影響力"] = {
            "select": {
                "name": influence
            }
        }
        
        # 7. 窗口的困擾或 KPI (rich_text)
        kpi = "營運效率最佳化"
        if card.title:
            if "業務" in card.title:
                kpi = "業績達成、客戶滿意度"
            elif "工程" in card.title:
                kpi = "技術問題解決、專案進度"
            elif "經理" in card.title:
                kpi = "團隊績效、成本控制"
        
        properties["窗口的困擾或 KPI"] = {
            "rich_text": [
                {
                    "text": {
                        "content": kpi
                    }
                }
            ]
        }
        
        # 8. 職稱 (select) - 只使用確定存在的選項
        title_options = ["CEO","COO","總經理","場務經理","廠長","副理","主任","廠務課長","專案協理","副總","特助","總務副理","技術科專員","總務課長","董事長 CEO","Chairman","CEO / Executive Manager","高級工程師","分析師","產品經理","資深部經理","董事長特助","業務經理","專利師／顧問","資深專利師／資深顧問","專員","副總經理","Presales Consultant","工程師","生管經理","副院長","院長","特助 / 主管","資深協理","資深經理","廠務專員","課長","業務工程師","執行長 / CEO & Co-founder","副社長","經理","業務專員","專案經理","冷凍空調技師","總監","總經理 GM","資深專案經理","客戶經理","顧問師","業務","處長","グループリーダー","アシスタントマネージャ","Director","Advanced Senior Professional","Sales Manager","SENIOR FAB DIRECTOR","Manager","Section Manager","業務專員 Sales Specialist","執行長","副總執行長 (顧問)","產品專員","監事","工程部經理","股長","業務主任","協理","資深企業發展經理","資深顧問","專案主持人","業務經理 (Business Manager)"]
        
        if card.title and card.title in title_options:
            properties["職稱"] = {
                "select": {
                    "name": card.title
                }
            }
        
        # 9. 部門 (rich_text) - 提取部門資訊
        if card.company:
            # 拆分公司名稱，取第一個部分後的內容作為部門
            company_parts = card.company.split()
            if len(company_parts) > 1:
                department = " ".join(company_parts[1:])
            else:
                department = "總公司"  # 如果沒有部門資訊，預設為總公司
            
            properties["部門"] = {
                "rich_text": [
                    {
                        "text": {
                            "content": department
                        }
                    }
                ]
            }
        
        # 10. 電話 (phone_number)
        if card.phone:
            properties["電話"] = {
                "phone_number": card.phone
            }
        
        # 以下欄位留空，供人工輸入：
        # - 取得聯絡來源 (rich_text)
        # - 聯絡注意事項 (rich_text) 
        # - 負責業務 (people)
        
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
    
    def get_database_schema(self) -> Dict[str, Any]:
        """獲取資料庫結構"""
        try:
            response = self.client.databases.retrieve(database_id=self.database_id)
            return response.get("properties", {})
        except Exception as e:
            logger.error("Failed to get database schema", error=str(e))
            return {}
    
    @monitor_performance("notion_search_by_name")
    def search_cards_by_name(self, name: str, limit: int = 10) -> list:
        """根據姓名搜尋名片"""
        try:
            monitoring_service.add_breadcrumb("Searching cards by name", "data_storage", {
                "search_name": name,
                "limit": limit
            })
            
            response = self.client.databases.query(
                database_id=self.database_id,
                filter={
                    "property": "姓名",
                    "title": {
                        "contains": name
                    }
                },
                page_size=limit
            )
            
            results = response.get("results", [])
            
            # 記錄搜尋結果
            monitoring_service.capture_event(MonitoringEvent(
                category=EventCategory.DATA_STORAGE,
                level=MonitoringLevel.INFO,
                message="Card search by name completed",
                extra_data={
                    "search_term": name,
                    "results_count": len(results),
                    "limit": limit
                },
                tags={"operation": "search_by_name", "status": "success"}
            ))
            
            return results
            
        except Exception as e:
            # 記錄搜尋失敗
            monitoring_service.capture_event(MonitoringEvent(
                category=EventCategory.DATA_STORAGE,
                level=MonitoringLevel.ERROR,
                message="Failed to search cards by name",
                extra_data={
                    "search_term": name,
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                tags={"operation": "search_by_name", "status": "failed"}
            ))
            
            logger.error("Failed to search cards", error=str(e), name=name)
            return []
    
    def search_cards_by_company(self, company: str, limit: int = 10) -> list:
        """根據公司名稱搜尋名片"""
        try:
            response = self.client.databases.query(
                database_id=self.database_id,
                filter={
                    "property": "公司",
                    "rich_text": {
                        "contains": company
                    }
                },
                page_size=limit
            )
            
            return response.get("results", [])
            
        except Exception as e:
            logger.error("Failed to search cards by company", error=str(e), company=company)
            return []
    
    def get_user_cards(self, line_user_id: str, limit: int = 50) -> list:
        """獲取特定用戶的所有名片"""
        try:
            response = self.client.databases.query(
                database_id=self.database_id,
                filter={
                    "property": "LINE用戶",
                    "rich_text": {
                        "equals": line_user_id
                    }
                },
                sorts=[
                    {
                        "property": "建立時間",
                        "direction": "descending"
                    }
                ],
                page_size=limit
            )
            
            return response.get("results", [])
            
        except Exception as e:
            logger.error("Failed to get user cards", error=str(e), user_id=line_user_id)
            return []
    
    def get_database_stats(self) -> Dict[str, Any]:
        """獲取資料庫統計資訊"""
        try:
            # 獲取總數
            response = self.client.databases.query(
                database_id=self.database_id,
                page_size=1
            )
            
            # 注意：Notion API 不直接提供總數，這裡只是示例
            stats = {
                "total_cards": "N/A",  # 需要遍歷所有頁面才能獲得準確數字
                "database_url": self.database_url,
                "last_updated": datetime.now().isoformat()
            }
            
            return stats
            
        except Exception as e:
            logger.error("Failed to get database stats", error=str(e))
            return {}