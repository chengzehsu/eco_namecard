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
        """準備名片屬性用於 Notion（完全以實際資料庫欄位為主）"""
        properties = {}
        
        # 根據您的實際 Notion 資料庫欄位結構準備資料
        
        # 1. Name (title) - 必填的標題欄位
        properties["Name"] = {
            "title": [
                {
                    "text": {
                        "content": card.name or "未知姓名"
                    }
                }
            ]
        }
        
        # 2. Email (email) - 如果有效的話
        if card.email and "@" in card.email:
            properties["Email"] = {
                "email": card.email
            }
        
        # 3. 備註 (rich_text) - AI 相關資訊
        notes = []
        notes.append(f"📊 AI識別信心度: {card.confidence_score:.1%}")
        notes.append(f"⭐ 品質評分: {card.quality_score:.1%}")
        if card.extracted_at:
            notes.append(f"🕒 識別時間: {card.extracted_at.strftime('%Y-%m-%d %H:%M')}")
        if card.line_user_id:
            notes.append(f"👤 LINE用戶: {card.line_user_id[:10]}...")
        
        properties["備註"] = {
            "rich_text": [
                {
                    "text": {
                        "content": " | ".join(notes)
                    }
                }
            ]
        }
        
        # 4. 公司名稱 (rich_text)
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
        
        # 5. 取得聯絡來源 (rich_text)
        properties["取得聯絡來源"] = {
            "rich_text": [
                {
                    "text": {
                        "content": "LINE Bot 自動識別"
                    }
                }
            ]
        }
        
        # 6. 地址 (rich_text)
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
        
        # 7. 決策影響力 (select) - 根據職稱推測
        influence_mapping = {
            "董事長": "最終決策者", "CEO": "最終決策者", "執行長": "最終決策者",
            "總經理": "最終決策者", "副總": "關鍵影響者", "經理": "關鍵影響者",
            "協理": "關鍵影響者", "課長": "技術評估者", "專員": "資訊蒐集者",
            "工程師": "技術評估者", "業務": "用戶代表（場務總管）"
        }
        
        influence = "中"  # 預設值
        if card.title:
            for title_keyword, influence_level in influence_mapping.items():
                if title_keyword in card.title:
                    influence = influence_level
                    break
        
        properties["決策影響力"] = {
            "select": {
                "name": influence
            }
        }
        
        # 8. 窗口的困擾或 KPI (rich_text) - 根據職稱推測
        kpi_mapping = {
            "業務": "業績達成、客戶滿意度",
            "工程師": "技術問題解決、專案進度",
            "經理": "團隊績效、成本控制",
            "總經理": "營收成長、市場競爭力",
            "CEO": "公司整體績效、股東價值"
        }
        
        kpi = "營運效率、成本最佳化"  # 預設值
        if card.title:
            for title_keyword, kpi_desc in kpi_mapping.items():
                if title_keyword in card.title:
                    kpi = kpi_desc
                    break
        
        properties["窗口的困擾或 KPI"] = {
            "rich_text": [
                {
                    "text": {
                        "content": kpi
                    }
                }
            ]
        }
        
        # 9. 聯絡注意事項 (rich_text)
        contact_notes = "透過 LINE Bot 自動收集，建議確認職稱與聯絡方式"
        if card.phone:
            contact_notes += f"，電話: {card.phone}"
        
        properties["聯絡注意事項"] = {
            "rich_text": [
                {
                    "text": {
                        "content": contact_notes
                    }
                }
            ]
        }
        
        # 10. 職稱 (select) - 如果在您的選項中
        title_options = ["CEO","COO","總經理","場務經理","廠長","副理","主任","廠務課長","專案協理","副總","特助","總務副理","技術科專員","總務課長","董事長 CEO","Chairman","CEO / Executive Manager","高級工程師","分析師","產品經理","資深部經理","董事長特助","業務經理","專利師／顧問","資深專利師／資深顧問","專員","副總經理","Presales Consultant","工程師","生管經理","副院長","院長","特助 / 主管","資深協理","資深經理","廠務專員","課長","業務工程師","執行長 / CEO & Co-founder","副社長","經理","業務專員","專案經理","冷凍空調技師","總監","總經理 GM","資深專案經理","客戶經理","顧問師","業務","處長","グループリーダー","アシスタントマネージャ","Director","Advanced Senior Professional","Sales Manager","SENIOR FAB DIRECTOR","Manager","Section Manager","業務專員 Sales Specialist","執行長","副總執行長 (顧問)","產品專員","監事","工程部經理","股長","業務主任","協理","資深企業發展經理","資深顧問","專案主持人","業務經理 (Business Manager)"]
        
        if card.title and card.title in title_options:
            properties["職稱"] = {
                "select": {
                    "name": card.title
                }
            }
        elif card.title:
            # 如果不在選項中，記錄但不設置（避免錯誤）
            logger.info("Title not in predefined options, skipping", title=card.title, available_count=len(title_options))
        
        # 11. 負責業務 (people) - 暫時不設置，需要具體的用戶 ID
        
        # 12. 部門 (rich_text) - 從公司名稱或職稱推測
        department = "未知部門"
        if card.company:
            if any(keyword in card.company for keyword in ["營運", "業務", "銷售"]):
                department = "業務部"
            elif any(keyword in card.company for keyword in ["技術", "工程", "IT", "資訊"]):
                department = "技術部"
            elif any(keyword in card.company for keyword in ["財務", "會計"]):
                department = "財務部"
            elif any(keyword in card.company for keyword in ["人資", "HR"]):
                department = "人力資源部"
            else:
                department = card.company  # 如果是小公司，公司名稱就是部門
        
        properties["部門"] = {
            "rich_text": [
                {
                    "text": {
                        "content": department
                    }
                }
            ]
        }
        
        # 13. 電話 (phone_number)
        if card.phone:
            properties["電話"] = {
                "phone_number": card.phone
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