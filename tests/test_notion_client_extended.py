"""
Extended tests for notion_client.py - advanced scenarios, edge cases, and updated logic
Tests the new property mapping logic and complex business rules
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from src.namecard.infrastructure.storage.notion_client import NotionClient
from src.namecard.core.models.card import BusinessCard


class TestNotionClientAdvancedPropertyMapping:
    """Test advanced property mapping with new business logic"""
    
    def setup_method(self):
        """Setup for each test"""
        with patch('src.namecard.infrastructure.storage.notion_client.Client'):
            self.client = NotionClient()
        self.test_user_id = "test_user_123"
    
    def test_prepare_card_properties_new_mapping_complete(self):
        """Test complete card with new property mapping"""
        card = BusinessCard(
            name="張執行長",
            company="科技創新公司 研發部",
            title="執行長",
            phone="02-1234-5678",
            email="ceo@techinnov.com",
            address="台北市信義區信義路五段7號",
            website="https://techinnov.com",
            fax="02-8765-4321",
            line_id="ceo_zhang",
            confidence_score=0.95,
            quality_score=0.9,
            line_user_id=self.test_user_id
        )
        
        properties = self.client._prepare_card_properties(card)
        
        # Test new property mapping
        assert properties["Name"]["title"][0]["text"]["content"] == "張執行長"
        assert properties["Email"]["email"] == "ceo@techinnov.com"
        assert properties["公司名稱"]["rich_text"][0]["text"]["content"] == "科技創新公司"
        assert properties["部門"]["rich_text"][0]["text"]["content"] == "研發部"
        assert properties["地址"]["rich_text"][0]["text"]["content"] == "台北市信義區信義路五段7號"
        assert properties["電話"]["phone_number"] == "02-1234-5678"
        
        # Test decision influence based on title
        assert properties["決策影響力"]["select"]["name"] == "最終決策者"
        
        # Test KPI mapping
        assert properties["窗口的困擾或 KPI"]["rich_text"][0]["text"]["content"] == "營運效率最佳化"
        
        # Test notes compilation
        notes_content = properties["備註"]["rich_text"][0]["text"]["content"]
        assert "傳真: 02-8765-4321" in notes_content
        assert "網站: https://techinnov.com" in notes_content
        assert "LINE ID: ceo_zhang" in notes_content
        assert f"發送者: {self.test_user_id}" in notes_content
    
    def test_decision_influence_classification(self):
        """Test decision influence classification based on titles"""
        test_cases = [
            ("董事長", "最終決策者"),
            ("CEO", "最終決策者"), 
            ("執行長", "最終決策者"),
            ("總經理", "最終決策者"),
            ("副總經理", "關鍵影響者"),
            ("經理", "關鍵影響者"),
            ("協理", "關鍵影響者"),
            ("工程師", "技術評估者"),
            ("技術主管", "技術評估者"),
            ("業務經理", "用戶代表（場務總管）"),
            ("業務專員", "用戶代表（場務總管）"),
            ("專員", "資訊蒐集者"),
            ("助理", "中"),  # Default value
            ("", "中"),     # Empty title
        ]
        
        for title, expected_influence in test_cases:
            card = BusinessCard(
                name="測試用戶",
                title=title,
                line_user_id=self.test_user_id
            )
            
            properties = self.client._prepare_card_properties(card)
            
            assert properties["決策影響力"]["select"]["name"] == expected_influence, \
                f"Title '{title}' should map to '{expected_influence}'"
    
    def test_kpi_classification_based_on_title(self):
        """Test KPI classification based on job titles"""
        test_cases = [
            ("業務經理", "業績達成、客戶滿意度"),
            ("業務專員", "業績達成、客戶滿意度"),
            ("工程師", "技術問題解決、專案進度"),
            ("工程部經理", "技術問題解決、專案進度"),
            ("經理", "團隊績效、成本控制"),
            ("副總經理", "團隊績效、成本控制"),
            ("專員", "營運效率最佳化"),  # Default
            ("", "營運效率最佳化"),        # Empty title
        ]
        
        for title, expected_kpi in test_cases:
            card = BusinessCard(
                name="測試用戶",
                title=title,
                line_user_id=self.test_user_id
            )
            
            properties = self.client._prepare_card_properties(card)
            
            assert properties["窗口的困擾或 KPI"]["rich_text"][0]["text"]["content"] == expected_kpi, \
                f"Title '{title}' should map to KPI '{expected_kpi}'"
    
    def test_company_department_splitting(self):
        """Test company and department splitting logic"""
        test_cases = [
            ("台積電", "台積電", "總公司"),
            ("台積電 製造部", "台積電", "製造部"),
            ("鴻海精密工業 富士康事業群", "鴻海精密工業", "富士康事業群"),
            ("聯發科技股份有限公司 AI晶片部門", "聯發科技股份有限公司", "AI晶片部門"),
            ("Google Taiwan 工程部 AI團隊", "Google", "Taiwan 工程部 AI團隊"),
            ("", None, None),  # Empty company
        ]
        
        for company_input, expected_company, expected_department in test_cases:
            card = BusinessCard(
                name="測試用戶",
                company=company_input,
                line_user_id=self.test_user_id
            )
            
            properties = self.client._prepare_card_properties(card)
            
            if expected_company:
                assert properties["公司名稱"]["rich_text"][0]["text"]["content"] == expected_company
                assert properties["部門"]["rich_text"][0]["text"]["content"] == expected_department
            else:
                assert "公司名稱" not in properties
                assert "部門" not in properties
    
    def test_title_select_option_validation(self):
        """Test that only valid title options are used"""
        valid_titles = ["CEO", "總經理", "經理", "工程師", "專員"]
        invalid_titles = ["不存在的職稱", "自創職稱", ""]
        
        for title in valid_titles:
            card = BusinessCard(
                name="測試用戶",
                title=title,
                line_user_id=self.test_user_id
            )
            
            properties = self.client._prepare_card_properties(card)
            
            # Should include title property for valid titles
            assert "職稱" in properties
            assert properties["職稱"]["select"]["name"] == title
        
        for title in invalid_titles:
            card = BusinessCard(
                name="測試用戶",
                title=title,
                line_user_id=self.test_user_id
            )
            
            properties = self.client._prepare_card_properties(card)
            
            # Should not include title property for invalid titles
            assert "職稱" not in properties
    
    def test_notes_compilation_edge_cases(self):
        """Test notes compilation with various edge cases"""
        # Test with minimal information
        card = BusinessCard(
            name="簡單用戶",
            line_user_id=self.test_user_id
        )
        
        properties = self.client._prepare_card_properties(card)
        
        # Should have notes with just the sender info
        notes_content = properties["備註"]["rich_text"][0]["text"]["content"]
        assert f"發送者: {self.test_user_id}" in notes_content
        
        # Test with all optional fields
        card = BusinessCard(
            name="完整用戶",
            fax="02-1111-2222",
            website="https://example.com",
            line_id="complete_user",
            line_user_id=self.test_user_id
        )
        
        # Add custom attributes for testing
        card.mobile = "0912-345-678"
        card.tax_id = "12345678"
        
        properties = self.client._prepare_card_properties(card)
        
        notes_content = properties["備註"]["rich_text"][0]["text"]["content"]
        assert "傳真: 02-1111-2222" in notes_content
        assert "行動電話: 0912-345-678" in notes_content
        assert "網站: https://example.com" in notes_content
        assert "統一編號: 12345678" in notes_content
        assert "LINE ID: complete_user" in notes_content
        assert f"發送者: {self.test_user_id}" in notes_content
        
        # Check separator usage
        assert " | " in notes_content
    
    def test_email_validation_in_properties(self):
        """Test email validation in property mapping"""
        test_cases = [
            ("valid@example.com", True),
            ("user.name@company.co.uk", True),
            ("test+tag@domain.org", True),
            ("invalid-email", False),
            ("no-at-symbol.com", False),
            ("@domain.com", False),
            ("user@", False),
            ("", False),
            (None, False),
        ]
        
        for email, should_include in test_cases:
            card = BusinessCard(
                name="測試用戶",
                email=email,
                line_user_id=self.test_user_id
            )
            
            properties = self.client._prepare_card_properties(card)
            
            if should_include:
                assert "Email" in properties
                assert properties["Email"]["email"] == email
            else:
                assert "Email" not in properties
    
    def test_properties_with_none_values(self):
        """Test property mapping with None values"""
        card = BusinessCard(
            name="測試用戶",
            company=None,
            title=None,
            phone=None,
            email=None,
            address=None,
            website=None,
            fax=None,
            line_id=None,
            line_user_id=self.test_user_id
        )
        
        properties = self.client._prepare_card_properties(card)
        
        # Should only include Name and default properties
        required_properties = ["Name", "決策影響力", "窗口的困擾或 KPI", "備註"]
        
        for prop in required_properties:
            assert prop in properties
        
        # Should not include optional properties with None values
        optional_properties = ["Email", "公司名稱", "部門", "地址", "電話", "職稱"]
        
        for prop in optional_properties:
            assert prop not in properties


class TestNotionClientSearchAndQuery:
    """Test search and query functionality"""
    
    def setup_method(self):
        """Setup for each test"""
        with patch('src.namecard.infrastructure.storage.notion_client.Client'):
            self.client = NotionClient()
    
    def test_search_cards_by_name_with_unicode(self):
        """Test searching with Unicode characters"""
        expected_results = [{"id": "card1", "name": "張三"}]
        self.client.client.databases.query.return_value = {
            "results": expected_results
        }
        
        # Test with Chinese characters
        results = self.client.search_cards_by_name("張三", limit=5)
        
        assert results == expected_results
        
        # Verify query parameters
        call_args = self.client.client.databases.query.call_args[1]
        assert call_args["filter"]["property"] == "姓名"
        assert call_args["filter"]["title"]["contains"] == "張三"
    
    def test_search_cards_by_name_empty_query(self):
        """Test searching with empty query"""
        self.client.client.databases.query.return_value = {"results": []}
        
        results = self.client.search_cards_by_name("", limit=10)
        
        assert results == []
        # Should still make the query
        self.client.client.databases.query.assert_called_once()
    
    def test_search_cards_by_company_partial_match(self):
        """Test company search with partial matching"""
        expected_results = [
            {"id": "card1", "company": "台積電"},
            {"id": "card2", "company": "台積電製造部"}
        ]
        self.client.client.databases.query.return_value = {
            "results": expected_results
        }
        
        results = self.client.search_cards_by_company("台積", limit=20)
        
        assert results == expected_results
        
        # Verify query uses contains for partial matching
        call_args = self.client.client.databases.query.call_args[1]
        assert call_args["filter"]["rich_text"]["contains"] == "台積"
    
    def test_get_user_cards_pagination(self):
        """Test user cards retrieval with pagination"""
        expected_results = [{"id": f"card{i}"} for i in range(50)]
        self.client.client.databases.query.return_value = {
            "results": expected_results
        }
        
        results = self.client.get_user_cards("user123", limit=50)
        
        assert len(results) == 50
        assert results == expected_results
        
        # Verify sorting by creation time (descending)
        call_args = self.client.client.databases.query.call_args[1]
        sorts = call_args["sorts"]
        assert len(sorts) == 1
        assert sorts[0]["property"] == "建立時間"
        assert sorts[0]["direction"] == "descending"
    
    def test_get_user_cards_exact_match(self):
        """Test user cards uses exact match for user ID"""
        self.client.client.databases.query.return_value = {"results": []}
        
        user_id = "U1234567890abcdef"
        self.client.get_user_cards(user_id)
        
        # Verify exact match is used, not contains
        call_args = self.client.client.databases.query.call_args[1]
        assert call_args["filter"]["rich_text"]["equals"] == user_id
    
    def test_search_with_api_timeout(self):
        """Test search behavior when API times out"""
        import requests
        
        # Simulate timeout exception
        self.client.client.databases.query.side_effect = requests.Timeout("Request timeout")
        
        results = self.client.search_cards_by_name("張三")
        
        # Should return empty list gracefully
        assert results == []
    
    def test_search_with_rate_limit_error(self):
        """Test search behavior when rate limited"""
        from notion_client.errors import APIResponseError
        
        # Simulate rate limit error
        rate_limit_error = APIResponseError(
            response=Mock(status_code=429),
            message="Rate limited",
            code="rate_limited"
        )
        
        self.client.client.databases.query.side_effect = rate_limit_error
        
        results = self.client.search_cards_by_company("測試公司")
        
        # Should return empty list gracefully
        assert results == []


class TestNotionClientErrorHandling:
    """Test error handling scenarios"""
    
    def setup_method(self):
        """Setup for each test"""
        with patch('src.namecard.infrastructure.storage.notion_client.Client'):
            self.client = NotionClient()
    
    def test_save_business_card_network_error(self):
        """Test saving card with network error"""
        import requests
        
        self.client.client.pages.create.side_effect = requests.ConnectionError("Network error")
        
        card = BusinessCard(
            name="網路錯誤測試",
            line_user_id="test_user"
        )
        
        result = self.client.save_business_card(card)
        
        assert result is None
    
    def test_save_business_card_authentication_error(self):
        """Test saving card with authentication error"""
        from notion_client.errors import APIResponseError
        
        auth_error = APIResponseError(
            response=Mock(status_code=401),
            message="Unauthorized",
            code="unauthorized"
        )
        
        self.client.client.pages.create.side_effect = auth_error
        
        card = BusinessCard(
            name="認證錯誤測試",
            line_user_id="test_user"
        )
        
        result = self.client.save_business_card(card)
        
        assert result is None
    
    def test_save_business_card_validation_error(self):
        """Test saving card with validation error"""
        from notion_client.errors import APIResponseError
        
        validation_error = APIResponseError(
            response=Mock(status_code=400),
            message="Invalid property",
            code="validation_error"
        )
        
        self.client.client.pages.create.side_effect = validation_error
        
        card = BusinessCard(
            name="驗證錯誤測試",
            line_user_id="test_user"
        )
        
        result = self.client.save_business_card(card)
        
        assert result is None
    
    def test_database_schema_retrieval_error(self):
        """Test database schema retrieval error"""
        self.client.client.databases.retrieve.side_effect = Exception("Database not found")
        
        schema = self.client.get_database_schema()
        
        assert schema == {}
    
    def test_connection_test_with_invalid_database_id(self):
        """Test connection test with invalid database ID"""
        from notion_client.errors import APIResponseError
        
        not_found_error = APIResponseError(
            response=Mock(status_code=404),
            message="Database not found",
            code="object_not_found"
        )
        
        self.client.client.databases.retrieve.side_effect = not_found_error
        
        # Should not raise exception
        self.client._test_connection()
    
    @patch('src.namecard.infrastructure.storage.notion_client.logger')
    def test_error_logging_during_save(self, mock_logger):
        """Test that errors are properly logged during save operations"""
        error_message = "Specific save error"
        self.client.client.pages.create.side_effect = Exception(error_message)
        
        card = BusinessCard(
            name="記錄錯誤測試",
            company="測試公司",
            line_user_id="test_user"
        )
        
        result = self.client.save_business_card(card)
        
        # Verify error is logged with context
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        
        assert "Failed to save business card to Notion" in call_args[0][0]
        assert call_args[1]["error"] == error_message
        assert call_args[1]["name"] == "記錄錯誤測試"
        assert call_args[1]["company"] == "測試公司"
        
        assert result is None


class TestNotionClientDatabaseOperations:
    """Test database operations and management"""
    
    def setup_method(self):
        """Setup for each test"""
        with patch('src.namecard.infrastructure.storage.notion_client.Client'):
            self.client = NotionClient()
    
    def test_create_database_if_not_exists_success(self):
        """Test successful database existence check"""
        self.client.client.databases.retrieve.return_value = {
            "id": "test_database_id",
            "title": [{"plain_text": "Business Cards"}]
        }
        
        result = self.client.create_database_if_not_exists()
        
        assert result is True
        self.client.client.databases.retrieve.assert_called_once_with(
            database_id=self.client.database_id
        )
    
    def test_create_database_if_not_exists_not_found(self):
        """Test database not found scenario"""
        from notion_client.errors import APIResponseError
        
        not_found_error = APIResponseError(
            response=Mock(status_code=404),
            message="Object not found",
            code="object_not_found"
        )
        
        self.client.client.databases.retrieve.side_effect = not_found_error
        
        result = self.client.create_database_if_not_exists()
        
        assert result is False
    
    def test_get_database_stats_complete(self):
        """Test getting complete database statistics"""
        self.client.client.databases.query.return_value = {
            "results": [{"id": "dummy"}],  # Minimal response
            "has_more": False
        }
        
        stats = self.client.get_database_stats()
        
        assert "total_cards" in stats
        assert "database_url" in stats
        assert "last_updated" in stats
        assert stats["database_url"] == self.client.database_url
        assert stats["total_cards"] == "N/A"  # As noted in implementation
    
    def test_database_url_formatting(self):
        """Test database URL formatting with different ID formats"""
        test_cases = [
            ("12345678-1234-1234-1234-123456789abc", "https://notion.so/123456781234123412341234567890abc"),
            ("abcdef12-3456-7890-abcd-ef1234567890", "https://notion.so/abcdef123456789abcdef1234567890"),
            ("no-dashes-here", "https://notion.so/no-dashes-here"),
        ]
        
        for database_id, expected_url in test_cases:
            with patch('src.namecard.infrastructure.storage.notion_client.settings') as mock_settings:
                mock_settings.notion_api_key = "test_key"
                mock_settings.notion_database_id = database_id
                
                with patch('src.namecard.infrastructure.storage.notion_client.Client'):
                    client = NotionClient()
                    
                    assert client.database_url == expected_url


class TestNotionClientIntegration:
    """Test integration scenarios and complex workflows"""
    
    def setup_method(self):
        """Setup for each test"""
        with patch('src.namecard.infrastructure.storage.notion_client.Client'):
            self.client = NotionClient()
    
    def test_complete_card_lifecycle(self):
        """Test complete card save and retrieve lifecycle"""
        # Setup successful save
        save_response = {
            "id": "test_page_id",
            "url": "https://notion.so/test_page_id"
        }
        self.client.client.pages.create.return_value = save_response
        
        # Setup successful search
        search_response = {
            "results": [
                {
                    "id": "test_page_id",
                    "properties": {
                        "Name": {"title": [{"text": {"content": "測試用戶"}}]}
                    }
                }
            ]
        }
        self.client.client.databases.query.return_value = search_response
        
        # Create and save card
        card = BusinessCard(
            name="測試用戶",
            company="測試公司",
            title="經理",
            phone="02-1234-5678",
            email="test@company.com",
            line_user_id="test_user_123"
        )
        
        # Save card
        save_url = self.client.save_business_card(card)
        assert save_url == "https://notion.so/test_page_id"
        
        # Search by name
        search_results = self.client.search_cards_by_name("測試用戶")
        assert len(search_results) == 1
        assert search_results[0]["id"] == "test_page_id"
        
        # Search by company
        company_results = self.client.search_cards_by_company("測試公司")
        assert len(company_results) == 1
        
        # Get user cards
        user_cards = self.client.get_user_cards("test_user_123")
        assert len(user_cards) == 1
    
    def test_batch_card_processing(self):
        """Test processing multiple cards efficiently"""
        cards = []
        save_responses = []
        
        # Create multiple test cards
        for i in range(5):
            card = BusinessCard(
                name=f"用戶{i}",
                company=f"公司{i}",
                title="專員",
                phone=f"02-1234-567{i}",
                email=f"user{i}@company{i}.com",
                line_user_id="batch_test_user"
            )
            cards.append(card)
            
            # Setup save response
            save_response = {
                "id": f"page_id_{i}",
                "url": f"https://notion.so/page_id_{i}"
            }
            save_responses.append(save_response)
        
        # Setup mock to return different responses for each call
        self.client.client.pages.create.side_effect = save_responses
        
        # Save all cards
        saved_urls = []
        for card in cards:
            url = self.client.save_business_card(card)
            saved_urls.append(url)
        
        # Verify all saves were successful
        assert len(saved_urls) == 5
        for i, url in enumerate(saved_urls):
            assert url == f"https://notion.so/page_id_{i}"
        
        # Verify all save calls were made
        assert self.client.client.pages.create.call_count == 5
    
    def test_card_property_edge_cases_integration(self):
        """Test card property mapping with real-world edge cases"""
        # Test card with complex real-world data
        complex_card = BusinessCard(
            name="王小明 David Wang",
            company="台灣積體電路製造股份有限公司 (TSMC) 先進製程技術開發部",
            title="Principal Engineer",  # Not in the select options
            phone="03-5636688 ext. 12345",
            email="david.wang@tsmc.com",
            address="新竹科學園區力行路8號",
            website="tsmc.com",  # No protocol
            fax="03-5636000",
            line_id="david_tsmc",
            line_user_id="Uabcdef1234567890"
        )
        
        properties = self.client._prepare_card_properties(complex_card)
        
        # Verify complex company/department splitting
        assert properties["公司名稱"]["rich_text"][0]["text"]["content"] == "台灣積體電路製造股份有限公司"
        assert "先進製程技術開發部" in properties["部門"]["rich_text"][0]["text"]["content"]
        
        # Verify website protocol addition
        assert properties["備註"]["rich_text"][0]["text"]["content"].count("網站: https://tsmc.com") == 1
        
        # Verify title not included (not in valid options)
        assert "職稱" not in properties
        
        # Verify decision influence defaults to technical evaluator for engineer
        assert properties["決策影響力"]["select"]["name"] == "技術評估者"
        
        # Verify all notes are included
        notes = properties["備註"]["rich_text"][0]["text"]["content"]
        expected_notes = [
            "傳真: 03-5636000",
            "網站: https://tsmc.com", 
            "LINE ID: david_tsmc",
            "發送者: Uabcdef1234567890"
        ]
        
        for note in expected_notes:
            assert note in notes


class TestNotionClientConfiguration:
    """Test configuration and initialization scenarios"""
    
    @patch('src.namecard.infrastructure.storage.notion_client.settings')
    @patch('src.namecard.infrastructure.storage.notion_client.Client')
    def test_initialization_with_different_settings(self, mock_client_class, mock_settings):
        """Test initialization with various settings configurations"""
        mock_settings.notion_api_key = "secret_test_key_12345"
        mock_settings.notion_database_id = "test-db-id-with-dashes"
        
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.databases.retrieve.return_value = {"id": "test_db"}
        
        client = NotionClient()
        
        # Verify client initialization
        mock_client_class.assert_called_once_with(auth="secret_test_key_12345")
        assert client.database_id == "test-db-id-with-dashes"
        assert client.database_url == "https://notion.so/test-db-id-with-dashes"
        
        # Verify connection test was called
        mock_client.databases.retrieve.assert_called_once()
    
    @patch('src.namecard.infrastructure.storage.notion_client.logger')
    @patch('src.namecard.infrastructure.storage.notion_client.settings')
    @patch('src.namecard.infrastructure.storage.notion_client.Client')
    def test_initialization_connection_failure(self, mock_client_class, mock_settings, mock_logger):
        """Test initialization when connection test fails"""
        mock_settings.notion_api_key = "test_key"
        mock_settings.notion_database_id = "test_db_id"
        
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.databases.retrieve.side_effect = Exception("Connection failed")
        
        # Should not raise exception during initialization
        client = NotionClient()
        
        # Should log connection error
        mock_logger.error.assert_called_once()
        assert "Failed to connect to Notion" in mock_logger.error.call_args[0][0]
        
        # Client should still be created
        assert client.database_id == "test_db_id"
    
    @patch('src.namecard.infrastructure.storage.notion_client.settings')
    def test_database_url_generation_edge_cases(self, mock_settings):
        """Test database URL generation with edge cases"""
        edge_cases = [
            # Standard UUID format
            "12345678-1234-1234-1234-123456789abc",
            # UUID without dashes (already clean)
            "123456781234123412341234567890ab",
            # Short ID
            "short",
            # Empty string
            "",
            # Special characters
            "test-id-with-special-chars",
        ]
        
        for db_id in edge_cases:
            mock_settings.notion_api_key = "test_key"
            mock_settings.notion_database_id = db_id
            
            with patch('src.namecard.infrastructure.storage.notion_client.Client'):
                client = NotionClient()
                
                # Should always generate valid URL
                assert client.database_url.startswith("https://notion.so/")
                assert client.database_url == f"https://notion.so/{db_id.replace('-', '')}"