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
        """準備名片屬性用於 Notion"""
        properties = {}
        
        # 姓名 (標題)
        if card.name:
            properties["姓名"] = {
                "title": [
                    {
                        "text": {
                            "content": card.name
                        }
                    }
                ]
            }
        
        # 公司名稱
        if card.company:
            properties["公司"] = {
                "rich_text": [
                    {
                        "text": {
                            "content": card.company
                        }
                    }
                ]
            }
        
        # 職稱
        if card.title:
            properties["職稱"] = {
                "rich_text": [
                    {
                        "text": {
                            "content": card.title
                        }
                    }
                ]
            }
        
        # 電話
        if card.phone:
            properties["電話"] = {
                "phone_number": card.phone
            }
        
        # 電子郵件
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
        
        # 網站
        if card.website:
            properties["網站"] = {
                "url": card.website if card.website.startswith(('http://', 'https://')) 
                      else f"https://{card.website}"
            }
        
        # 傳真
        if card.fax:
            properties["傳真"] = {
                "rich_text": [
                    {
                        "text": {
                            "content": card.fax
                        }
                    }
                ]
            }
        
        # LINE ID
        if card.line_id:
            properties["LINE ID"] = {
                "rich_text": [
                    {
                        "text": {
                            "content": card.line_id
                        }
                    }
                ]
            }
        
        # 信心度評分
        properties["信心度"] = {
            "number": round(card.confidence_score, 2)
        }
        
        # 品質評分
        properties["品質評分"] = {
            "number": round(card.quality_score, 2)
        }
        
        # 提取時間
        properties["建立時間"] = {
            "date": {
                "start": card.extracted_at.isoformat()
            }
        }
        
        # LINE 用戶 ID (用於追蹤)
        properties["LINE用戶"] = {
            "rich_text": [
                {
                    "text": {
                        "content": card.line_user_id
                    }
                }
            ]
        }
        
        # 處理狀態
        properties["狀態"] = {
            "select": {
                "name": "已處理" if card.processed else "待處理"
            }
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