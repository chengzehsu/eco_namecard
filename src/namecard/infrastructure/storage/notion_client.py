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
        except Exception as e:
            logger.error("Failed to connect to Notion", error=str(e))
            # 不拋出異常，允許應用程式繼續運行
    
    def save_business_card(self, card: BusinessCard) -> Optional[str]:
        """
        儲存名片到 Notion 資料庫
        
        Args:
            card: 名片資料
            
        Returns:
            Notion 頁面 URL，失敗時返回 None
        """
        try:
            # 準備名片資料
            properties = self._prepare_card_properties(card)
            
            # 建立 Notion 頁面
            response = self.client.pages.create(
                parent={"database_id": self.database_id},
                properties=properties
            )
            
            page_url = response.get("url", "")
            page_id = response.get("id", "")
            
            logger.info("Business card saved to Notion", 
                       page_id=page_id,
                       name=card.name,
                       company=card.company)
            
            return page_url
            
        except Exception as e:
            logger.error("Failed to save business card to Notion", 
                        error=str(e),
                        name=card.name,
                        company=card.company)
            return None
    
    def _prepare_card_properties(self, card: BusinessCard) -> Dict[str, Any]:
        """準備名片屬性用於 Notion（根據實際資料庫欄位）"""
        properties = {}
        
        # Name (標題) - 對應您的 Name 欄位
        if card.name:
            properties["Name"] = {
                "title": [
                    {
                        "text": {
                            "content": card.name
                        }
                    }
                ]
            }
        
        # 公司名稱 - 對應您的「公司名稱」欄位
        if card.company:
            properties["公司名稱"] = {
                "rich_text": [
                    {
                        "text": {
                            "content": card.company
                        }
                    }
                ]
            }
        
        # 職稱 - 您的欄位是 select 類型，需要從現有選項中選擇
        if card.title:
            # 檢查職稱是否在預定義選項中，如果不在則使用最接近的或預設值
            title_options = ["CEO","COO","總經理","場務經理","廠長","副理","主任","廠務課長","專案協理","副總","特助","總務副理","技術科專員","總務課長","董事長 CEO","Chairman","CEO / Executive Manager","高級工程師","分析師","產品經理","資深部經理","董事長特助","業務經理","專利師／顧問","資深專利師／資深顧問","專員","副總經理","Presales Consultant","工程師","生管經理","副院長","院長","特助 / 主管","資深協理","資深經理","廠務專員","課長","業務工程師","執行長 / CEO & Co-founder","副社長","經理","業務專員","專案經理","冷凍空調技師","總監","總經理 GM","資深專案經理","客戶經理","顧問師","業務","處長","グループリーダー","アシスタントマネージャ","Director","Advanced Senior Professional","Sales Manager","SENIOR FAB DIRECTOR","Manager","Section Manager","業務專員 Sales Specialist","執行長","副總執行長 (顧問)","產品專員","監事","工程部經理","股長","業務主任","協理","資深企業發展經理","資深顧問","專案主持人","業務經理 (Business Manager)"]
            
            # 如果職稱在選項中，直接使用；否則使用原始值（可能會失敗，但記錄下來）
            if card.title in title_options:
                properties["職稱"] = {
                    "select": {
                        "name": card.title
                    }
                }
            else:
                # 記錄未知職稱，但暫時不設置此欄位
                logger.warning("Unknown title not in select options", title=card.title)
        
        # 電話
        if card.phone:
            properties["電話"] = {
                "phone_number": card.phone
            }
        
        # Email
        if card.email:
            properties["Email"] = {
                "email": card.email
            }
        
        # 地址
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
        
        # 部門 - 如果名片有部門資訊
        if hasattr(card, 'department') and card.department:
            properties["部門"] = {
                "rich_text": [
                    {
                        "text": {
                            "content": card.department
                        }
                    }
                ]
            }
        
        # 取得聯絡來源 - 設為 LINE Bot
        properties["取得聯絡來源"] = {
            "rich_text": [
                {
                    "text": {
                        "content": "LINE Bot 名片識別"
                    }
                }
            ]
        }
        
        # 備註 - 包含信心度和品質評分資訊
        confidence_info = f"AI識別信心度: {card.confidence_score:.2f}, 品質評分: {card.quality_score:.2f}"
        if card.line_user_id:
            confidence_info += f", LINE用戶: {card.line_user_id}"
        
        properties["備註"] = {
            "rich_text": [
                {
                    "text": {
                        "content": confidence_info
                    }
                }
            ]
        }
        
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
    
    def search_cards_by_name(self, name: str, limit: int = 10) -> list:
        """根據姓名搜尋名片"""
        try:
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
            
            return response.get("results", [])
            
        except Exception as e:
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