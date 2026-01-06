"""
Notion 連接測試 - 專注於 API 2025-09-03 版本的 data_source_id

這個測試模組專門測試：
1. data_source_id 的獲取流程
2. 沒有 data_source_id 時的處理
3. 多租戶 Notion 連接
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.namecard.core.models.card import BusinessCard


class TestNotionDataSourceIdFlow:
    """
    Notion API 2025-09-03 data_source_id 流程測試
    
    根據 Notion API 升級指南：
    https://developers.notion.com/docs/upgrade-guide-2025-09-03
    
    Step 1: 獲取 data_source_id
    Step 2: 使用 data_source_id 創建頁面
    Step 3: 使用 data_source 端點查詢
    """

    @patch('src.namecard.infrastructure.storage.notion_client.Client')
    @patch('src.namecard.infrastructure.storage.notion_client.settings')
    def test_data_source_id_obtained_from_database(self, mock_settings, mock_client_class):
        """
        測試從 database 獲取 data_source_id
        
        流程：
        1. 調用 databases.retrieve()
        2. 從返回的 data_sources 列表獲取 id
        """
        mock_settings.notion_api_key = "ntn_test_key"
        mock_settings.notion_database_id = "1234567890abcdef"
        
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # 模擬成功的 database 響應
        mock_client.databases.retrieve.return_value = {
            "id": "1234567890abcdef",
            "title": [{"text": {"content": "Test Database"}}],
            "data_sources": [
                {"id": "ds_abc123def456"}
            ]
        }
        
        # 模擬 data_source 端點響應
        mock_client.request.return_value = {
            "id": "ds_abc123def456",
            "properties": {
                "Name": {"id": "title", "type": "title"},
                "Email": {"id": "email", "type": "email"},
                "公司名稱": {"id": "company", "type": "rich_text"},
            }
        }
        
        from src.namecard.infrastructure.storage.notion_client import NotionClient
        client = NotionClient()
        
        # 驗證 data_source_id 獲取成功
        assert client.data_source_id == "ds_abc123def456"
        
        # 驗證 schema 緩存成功
        assert "Name" in client._db_schema
        assert "Email" in client._db_schema
        assert "公司名稱" in client._db_schema

    @patch('src.namecard.infrastructure.storage.notion_client.Client')
    @patch('src.namecard.infrastructure.storage.notion_client.settings')
    def test_empty_data_sources_list(self, mock_settings, mock_client_class):
        """
        測試 data_sources 列表為空的情況
        
        這可能發生在：
        - 舊版 database
        - API 權限問題
        - 配置錯誤
        """
        mock_settings.notion_api_key = "ntn_test_key"
        mock_settings.notion_database_id = "1234567890abcdef"
        
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # data_sources 為空
        mock_client.databases.retrieve.return_value = {
            "id": "1234567890abcdef",
            "data_sources": []  # 空列表！
        }
        
        from src.namecard.infrastructure.storage.notion_client import NotionClient
        client = NotionClient()
        
        # data_source_id 應該是 None
        assert client.data_source_id is None

    @patch('src.namecard.infrastructure.storage.notion_client.Client')
    @patch('src.namecard.infrastructure.storage.notion_client.settings')
    def test_no_data_sources_key(self, mock_settings, mock_client_class):
        """
        測試響應中沒有 data_sources 鍵的情況
        """
        mock_settings.notion_api_key = "ntn_test_key"
        mock_settings.notion_database_id = "1234567890abcdef"
        
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # 沒有 data_sources 鍵
        mock_client.databases.retrieve.return_value = {
            "id": "1234567890abcdef",
            "title": [{"text": {"content": "Test"}}],
            # 注意：沒有 data_sources
        }
        
        from src.namecard.infrastructure.storage.notion_client import NotionClient
        client = NotionClient()
        
        # data_source_id 應該是 None
        assert client.data_source_id is None

    @patch('src.namecard.infrastructure.storage.notion_client.Client')
    @patch('src.namecard.infrastructure.storage.notion_client.settings')
    def test_connection_error_handled(self, mock_settings, mock_client_class):
        """測試連接錯誤的處理"""
        mock_settings.notion_api_key = "ntn_test_key"
        mock_settings.notion_database_id = "1234567890abcdef"
        
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # 模擬連接錯誤
        mock_client.databases.retrieve.side_effect = Exception("Connection refused")
        
        from src.namecard.infrastructure.storage.notion_client import NotionClient
        
        # 不應拋出異常，應該優雅處理
        client = NotionClient()
        
        assert client.data_source_id is None


class TestSaveBusinessCardWithDataSourceId:
    """測試使用 data_source_id 保存名片"""

    def setup_method(self):
        """設置測試環境"""
        self.test_card = BusinessCard(
            name="張三",
            company="測試公司",
            title="工程師",
            phone="02-1234-5678",
            email="test@example.com",
            confidence_score=0.95,
            quality_score=0.9,
            line_user_id="test_user_123"
        )

    @patch('src.namecard.infrastructure.storage.notion_client.Client')
    @patch('src.namecard.infrastructure.storage.notion_client.settings')
    def test_save_with_data_source_id_success(self, mock_settings, mock_client_class):
        """測試有 data_source_id 時的保存"""
        mock_settings.notion_api_key = "ntn_test_key"
        mock_settings.notion_database_id = "1234567890abcdef"
        
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # 設置成功的連接
        mock_client.databases.retrieve.return_value = {
            "id": "1234567890abcdef",
            "data_sources": [{"id": "ds_abc123"}]
        }
        mock_client.request.return_value = {"properties": {}}
        
        # 設置成功的頁面創建
        mock_client.pages.create.return_value = {
            "id": "page_123456",
            "url": "https://notion.so/page_123456"
        }
        
        from src.namecard.infrastructure.storage.notion_client import NotionClient
        client = NotionClient()
        
        result = client.save_business_card(self.test_card)
        
        # 應該返回 (page_id, page_url)
        assert result is not None
        assert result[0] == "page_123456"
        assert result[1] == "https://notion.so/page_123456"
        
        # 驗證創建參數使用了 data_source_id
        call_kwargs = mock_client.pages.create.call_args[1]
        assert call_kwargs["parent"]["type"] == "data_source_id"
        assert call_kwargs["parent"]["data_source_id"] == "ds_abc123"

    @patch('src.namecard.infrastructure.storage.notion_client.Client')
    @patch('src.namecard.infrastructure.storage.notion_client.settings')
    def test_save_without_data_source_id_returns_none(self, mock_settings, mock_client_class):
        """測試沒有 data_source_id 時返回 None"""
        mock_settings.notion_api_key = "ntn_test_key"
        mock_settings.notion_database_id = "1234567890abcdef"
        
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # 沒有 data_sources
        mock_client.databases.retrieve.return_value = {
            "id": "1234567890abcdef",
            "data_sources": []
        }
        
        from src.namecard.infrastructure.storage.notion_client import NotionClient
        client = NotionClient()
        
        # data_source_id 應該是 None
        assert client.data_source_id is None
        
        # 保存應該返回 None
        result = client.save_business_card(self.test_card)
        assert result is None
        
        # pages.create 不應被調用
        mock_client.pages.create.assert_not_called()


class TestMultiTenantNotionConnection:
    """多租戶 Notion 連接測試"""

    @patch('src.namecard.infrastructure.storage.notion_client.Client')
    @patch('src.namecard.infrastructure.storage.notion_client.settings')
    def test_tenant_specific_api_key(self, mock_settings, mock_client_class):
        """測試使用租戶專用 API key"""
        mock_settings.notion_api_key = "shared_key"
        mock_settings.notion_database_id = "default_db"
        
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.databases.retrieve.return_value = {
            "data_sources": [{"id": "ds_tenant"}]
        }
        mock_client.request.return_value = {"properties": {}}
        
        from src.namecard.infrastructure.storage.notion_client import NotionClient
        
        # 使用租戶專用配置
        client = NotionClient(
            api_key="tenant_specific_key",
            database_id="tenant_database_id"
        )
        
        # 驗證使用了租戶專用配置
        assert client.database_id == "tenant_database_id"
        mock_client_class.assert_called_with(
            auth="tenant_specific_key",
            notion_version="2025-09-03"
        )

    @patch('src.namecard.infrastructure.storage.notion_client.Client')
    @patch('src.namecard.infrastructure.storage.notion_client.settings')
    def test_shared_api_key_fallback(self, mock_settings, mock_client_class):
        """測試 fallback 到共享 API key"""
        mock_settings.notion_api_key = "shared_key"
        mock_settings.notion_database_id = "default_db"
        
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.databases.retrieve.return_value = {
            "data_sources": [{"id": "ds_shared"}]
        }
        mock_client.request.return_value = {"properties": {}}
        
        from src.namecard.infrastructure.storage.notion_client import NotionClient
        
        # 不提供租戶配置，應該 fallback 到共享配置
        client = NotionClient()
        
        assert client.database_id == "default_db"
        mock_client_class.assert_called_with(
            auth="shared_key",
            notion_version="2025-09-03"
        )


class TestNotionSchemaValidation:
    """Notion Schema 驗證測試"""

    @patch('src.namecard.infrastructure.storage.notion_client.Client')
    @patch('src.namecard.infrastructure.storage.notion_client.settings')
    def test_required_fields_check(self, mock_settings, mock_client_class):
        """測試必要欄位檢查"""
        mock_settings.notion_api_key = "test_key"
        mock_settings.notion_database_id = "test_db"
        
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # 返回包含必要欄位的 schema
        mock_client.databases.retrieve.return_value = {
            "data_sources": [{"id": "ds_123"}],
            "properties": {
                "Name": {"type": "title"},
                "Email": {"type": "email"},
                "公司名稱": {"type": "rich_text"},
                "電話": {"type": "phone_number"},
            }
        }
        mock_client.request.return_value = {
            "properties": {
                "Name": {"type": "title"},
                "Email": {"type": "email"},
                "公司名稱": {"type": "rich_text"},
                "電話": {"type": "phone_number"},
            }
        }
        
        from src.namecard.infrastructure.storage.notion_client import NotionClient
        client = NotionClient()
        
        # 測試連接應該成功
        result = client.test_connection()
        assert result is True

    @patch('src.namecard.infrastructure.storage.notion_client.Client')
    @patch('src.namecard.infrastructure.storage.notion_client.settings')
    def test_empty_schema(self, mock_settings, mock_client_class):
        """測試空 schema 的處理"""
        mock_settings.notion_api_key = "test_key"
        mock_settings.notion_database_id = "test_db"
        
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_client.databases.retrieve.return_value = {
            "data_sources": [{"id": "ds_123"}]
        }
        mock_client.request.return_value = {
            "properties": {}  # 空 schema
        }
        
        from src.namecard.infrastructure.storage.notion_client import NotionClient
        client = NotionClient()
        
        # schema 應該為空
        assert client._db_schema == {}


class TestTenantContextNotionClient:
    """測試 TenantContext 創建的 NotionClient"""

    @patch('src.namecard.infrastructure.storage.notion_client.Client')
    @patch('src.namecard.infrastructure.storage.notion_client.settings')
    def test_tenant_context_creates_correct_client(self, mock_settings, mock_client_class):
        """測試 TenantContext 創建正確的 NotionClient"""
        mock_settings.notion_api_key = "shared_key"
        
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.databases.retrieve.return_value = {
            "data_sources": [{"id": "ds_tenant_123"}]
        }
        mock_client.request.return_value = {"properties": {}}
        
        from src.namecard.core.models.tenant import TenantConfig, TenantContext
        
        # 創建租戶配置
        tenant = TenantConfig(
            id="tenant_123",
            name="Test Tenant",
            slug="test-tenant",
            line_channel_access_token="test_token",
            line_channel_secret="test_secret",
            notion_api_key=None,  # 使用共享 API key
            notion_database_id="tenant_db_123",
            use_shared_notion_api=True,
        )
        
        # 創建租戶上下文
        context = TenantContext(tenant)
        
        # 獲取 Notion client（會觸發 lazy loading）
        notion_client = context.notion_client
        
        # 驗證使用了正確的配置
        assert notion_client.database_id == "tenant_db_123"

