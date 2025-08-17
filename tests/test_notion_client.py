"""Notion 客戶端測試"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from src.namecard.infrastructure.storage.notion_client import NotionClient
from src.namecard.core.models.card import BusinessCard


class TestNotionClient:
    """NotionClient 測試"""
    
    def setup_method(self):
        """每個測試方法前的設置"""
        with patch('src.namecard.infrastructure.storage.notion_client.Client'):
            self.client = NotionClient()
        self.test_user_id = "test_user_123"
    
    @patch('src.namecard.infrastructure.storage.notion_client.Client')
    def test_init_success(self, mock_client_class):
        """測試初始化成功"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.databases.retrieve.return_value = {"id": "test_db"}
        
        with patch('src.namecard.infrastructure.storage.notion_client.settings') as mock_settings:
            mock_settings.notion_api_key = "test_key"
            mock_settings.notion_database_id = "test_db_id"
            
            client = NotionClient()
            
            mock_client_class.assert_called_with(auth="test_key")
            assert client.database_id == "test_db_id"
    
    def test_prepare_card_properties_complete_card(self):
        """測試準備完整名片屬性"""
        card = BusinessCard(
            name="張三",
            company="測試公司",
            title="工程師",
            phone="02-1234-5678",
            email="test@example.com",
            address="台北市信義區",
            website="https://example.com",
            fax="02-8765-4321",
            line_id="test_line_id",
            confidence_score=0.95,
            quality_score=0.9,
            line_user_id=self.test_user_id
        )
        
        properties = self.client._prepare_card_properties(card)
        
        # 檢查所有屬性都正確設置
        assert properties["姓名"]["title"][0]["text"]["content"] == "張三"
        assert properties["公司"]["rich_text"][0]["text"]["content"] == "測試公司"
        assert properties["職稱"]["rich_text"][0]["text"]["content"] == "工程師"
        assert properties["電話"]["phone_number"] == "02-1234-5678"
        assert properties["Email"]["email"] == "test@example.com"
        assert properties["地址"]["rich_text"][0]["text"]["content"] == "台北市信義區"
        assert properties["網站"]["url"] == "https://example.com"
        assert properties["傳真"]["rich_text"][0]["text"]["content"] == "02-8765-4321"
        assert properties["LINE ID"]["rich_text"][0]["text"]["content"] == "test_line_id"
        assert properties["信心度"]["number"] == 0.95
        assert properties["品質評分"]["number"] == 0.9
        assert properties["LINE用戶"]["rich_text"][0]["text"]["content"] == self.test_user_id
        assert properties["狀態"]["select"]["name"] == "待處理"
    
    def test_prepare_card_properties_minimal_card(self):
        """測試準備最小名片屬性"""
        card = BusinessCard(
            name="簡單名片",
            confidence_score=0.8,
            quality_score=0.7,
            line_user_id=self.test_user_id
        )
        
        properties = self.client._prepare_card_properties(card)
        
        # 只應該包含有值的屬性
        assert "姓名" in properties
        assert "信心度" in properties
        assert "品質評分" in properties
        assert "LINE用戶" in properties
        assert "狀態" in properties
        assert "建立時間" in properties
        
        # 不應該包含空值屬性
        assert "公司" not in properties
        assert "電話" not in properties
        assert "Email" not in properties
    
    def test_prepare_card_properties_website_protocol(self):
        """測試網站 URL 協議處理"""
        # 測試沒有協議的網站
        card = BusinessCard(
            name="測試",
            website="example.com",
            line_user_id=self.test_user_id
        )
        
        properties = self.client._prepare_card_properties(card)
        assert properties["網站"]["url"] == "https://example.com"
        
        # 測試已有協議的網站
        card.website = "http://example.com"
        properties = self.client._prepare_card_properties(card)
        assert properties["網站"]["url"] == "http://example.com"
    
    def test_prepare_card_properties_processed_status(self):
        """測試處理狀態設置"""
        # 測試未處理狀態
        card = BusinessCard(
            name="測試",
            processed=False,
            line_user_id=self.test_user_id
        )
        properties = self.client._prepare_card_properties(card)
        assert properties["狀態"]["select"]["name"] == "待處理"
        
        # 測試已處理狀態
        card.processed = True
        properties = self.client._prepare_card_properties(card)
        assert properties["狀態"]["select"]["name"] == "已處理"
    
    @patch.object(NotionClient, '_prepare_card_properties')
    def test_save_business_card_success(self, mock_prepare):
        """測試成功儲存名片"""
        # 設置 mock
        mock_prepare.return_value = {"test": "properties"}
        self.client.client.pages.create.return_value = {
            "id": "page_123",
            "url": "https://notion.so/page_123"
        }
        
        card = BusinessCard(
            name="測試名片",
            company="測試公司",
            line_user_id=self.test_user_id
        )
        
        result_url = self.client.save_business_card(card)
        
        assert result_url == "https://notion.so/page_123"
        self.client.client.pages.create.assert_called_once()
        mock_prepare.assert_called_once_with(card)
    
    def test_save_business_card_failure(self):
        """測試儲存名片失敗"""
        self.client.client.pages.create.side_effect = Exception("API Error")
        
        card = BusinessCard(
            name="測試名片",
            line_user_id=self.test_user_id
        )
        
        result_url = self.client.save_business_card(card)
        
        assert result_url is None
    
    def test_create_database_if_not_exists_exists(self):
        """測試資料庫存在檢查"""
        self.client.client.databases.retrieve.return_value = {"id": "test_db"}
        
        result = self.client.create_database_if_not_exists()
        
        assert result is True
        self.client.client.databases.retrieve.assert_called_once()
    
    def test_create_database_if_not_exists_not_found(self):
        """測試資料庫不存在"""
        self.client.client.databases.retrieve.side_effect = Exception("Not found")
        
        result = self.client.create_database_if_not_exists()
        
        assert result is False
    
    def test_get_database_schema_success(self):
        """測試獲取資料庫結構成功"""
        expected_schema = {"name": {"title": {}}, "company": {"rich_text": {}}}
        self.client.client.databases.retrieve.return_value = {
            "properties": expected_schema
        }
        
        schema = self.client.get_database_schema()
        
        assert schema == expected_schema
    
    def test_get_database_schema_failure(self):
        """測試獲取資料庫結構失敗"""
        self.client.client.databases.retrieve.side_effect = Exception("API Error")
        
        schema = self.client.get_database_schema()
        
        assert schema == {}
    
    def test_search_cards_by_name_success(self):
        """測試按姓名搜尋成功"""
        expected_results = [{"id": "card1"}, {"id": "card2"}]
        self.client.client.databases.query.return_value = {
            "results": expected_results
        }
        
        results = self.client.search_cards_by_name("張三", limit=5)
        
        assert results == expected_results
        self.client.client.databases.query.assert_called_once()
        
        # 檢查查詢參數
        call_args = self.client.client.databases.query.call_args
        assert call_args[1]["filter"]["property"] == "姓名"
        assert call_args[1]["filter"]["title"]["contains"] == "張三"
        assert call_args[1]["page_size"] == 5
    
    def test_search_cards_by_name_failure(self):
        """測試按姓名搜尋失敗"""
        self.client.client.databases.query.side_effect = Exception("API Error")
        
        results = self.client.search_cards_by_name("張三")
        
        assert results == []
    
    def test_search_cards_by_company_success(self):
        """測試按公司搜尋成功"""
        expected_results = [{"id": "card1"}]
        self.client.client.databases.query.return_value = {
            "results": expected_results
        }
        
        results = self.client.search_cards_by_company("測試公司")
        
        assert results == expected_results
        
        # 檢查查詢參數
        call_args = self.client.client.databases.query.call_args
        assert call_args[1]["filter"]["property"] == "公司"
        assert call_args[1]["filter"]["rich_text"]["contains"] == "測試公司"
    
    def test_get_user_cards_success(self):
        """測試獲取用戶名片成功"""
        expected_results = [{"id": "card1"}, {"id": "card2"}]
        self.client.client.databases.query.return_value = {
            "results": expected_results
        }
        
        results = self.client.get_user_cards(self.test_user_id, limit=20)
        
        assert results == expected_results
        
        # 檢查查詢參數
        call_args = self.client.client.databases.query.call_args
        assert call_args[1]["filter"]["property"] == "LINE用戶"
        assert call_args[1]["filter"]["rich_text"]["equals"] == self.test_user_id
        assert call_args[1]["page_size"] == 20
        
        # 檢查排序
        sorts = call_args[1]["sorts"]
        assert len(sorts) == 1
        assert sorts[0]["property"] == "建立時間"
        assert sorts[0]["direction"] == "descending"
    
    def test_get_user_cards_failure(self):
        """測試獲取用戶名片失敗"""
        self.client.client.databases.query.side_effect = Exception("API Error")
        
        results = self.client.get_user_cards(self.test_user_id)
        
        assert results == []
    
    def test_get_database_stats_success(self):
        """測試獲取資料庫統計成功"""
        self.client.client.databases.query.return_value = {"results": []}
        
        stats = self.client.get_database_stats()
        
        assert "total_cards" in stats
        assert "database_url" in stats
        assert "last_updated" in stats
        assert stats["database_url"] == self.client.database_url
    
    def test_get_database_stats_failure(self):
        """測試獲取資料庫統計失敗"""
        self.client.client.databases.query.side_effect = Exception("API Error")
        
        stats = self.client.get_database_stats()
        
        assert stats == {}
    
    def test_test_connection_success(self):
        """測試連接測試成功"""
        self.client.client.databases.retrieve.return_value = {"id": "test_db"}
        
        # 應該不拋出異常
        self.client._test_connection()
        
        self.client.client.databases.retrieve.assert_called_once()
    
    def test_test_connection_failure(self):
        """測試連接測試失敗"""
        self.client.client.databases.retrieve.side_effect = Exception("Connection failed")
        
        # 應該不拋出異常，但會記錄錯誤
        self.client._test_connection()
    
    def test_database_url_format(self):
        """測試資料庫 URL 格式"""
        with patch('src.namecard.infrastructure.storage.notion_client.settings') as mock_settings:
            mock_settings.notion_database_id = "12345678-1234-1234-1234-123456789abc"
            
            with patch('src.namecard.infrastructure.storage.notion_client.Client'):
                client = NotionClient()
                
                expected_url = "https://notion.so/123456781234123412341234567890abc"
                assert client.database_url == expected_url