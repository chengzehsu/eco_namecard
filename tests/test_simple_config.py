"""
Comprehensive tests for simple_config.py configuration management
Tests environment variable loading, validation, defaults, and edge cases
"""

import pytest
import os
from unittest.mock import patch, mock_open
from simple_config import Settings


class TestSettingsConfiguration:
    """Test Settings class configuration and behavior"""
    
    def test_default_configuration_values(self):
        """Test that default values are set correctly"""
        # Create settings without any environment variables
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            
            # LINE Bot defaults
            assert settings.line_channel_access_token == ""
            assert settings.line_channel_secret == ""
            
            # Google AI defaults
            assert settings.google_api_key == ""
            assert settings.google_api_key_fallback is None
            
            # Notion defaults
            assert settings.notion_api_key == ""
            assert settings.notion_database_id == ""
            
            # Application defaults
            assert settings.app_port == 5002
            assert settings.app_host == "0.0.0.0"
            assert settings.flask_env == "production"
            assert settings.secret_key == "fallback-secret-key-change-in-production"
            
            # Security defaults
            assert settings.rate_limit_per_user == 50
            assert settings.batch_size_limit == 10
            assert settings.max_image_size == 10485760  # 10MB
            
            # Monitoring defaults
            assert settings.sentry_dsn is None
            
            # Development defaults
            assert settings.debug is False
    
    def test_environment_variable_loading(self):
        """Test that environment variables are properly loaded"""
        test_env = {
            'LINE_CHANNEL_ACCESS_TOKEN': 'test_access_token',
            'LINE_CHANNEL_SECRET': 'test_secret',
            'GOOGLE_API_KEY': 'test_google_key',
            'GOOGLE_API_KEY_FALLBACK': 'test_fallback_key',
            'NOTION_API_KEY': 'test_notion_key',
            'NOTION_DATABASE_ID': 'test_database_id',
            'PORT': '8080',
            'APP_HOST': '127.0.0.1',
            'FLASK_ENV': 'development',
            'SECRET_KEY': 'test_secret_key',
            'RATE_LIMIT_PER_USER': '100',
            'BATCH_SIZE_LIMIT': '20',
            'MAX_IMAGE_SIZE': '20971520',  # 20MB
            'SENTRY_DSN': 'https://test@sentry.io/project',
            'DEBUG': 'true'
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            settings = Settings()
            
            assert settings.line_channel_access_token == 'test_access_token'
            assert settings.line_channel_secret == 'test_secret'
            assert settings.google_api_key == 'test_google_key'
            assert settings.google_api_key_fallback == 'test_fallback_key'
            assert settings.notion_api_key == 'test_notion_key'
            assert settings.notion_database_id == 'test_database_id'
            assert settings.app_port == 8080
            assert settings.app_host == '127.0.0.1'
            assert settings.flask_env == 'development'
            assert settings.secret_key == 'test_secret_key'
            assert settings.rate_limit_per_user == 100
            assert settings.batch_size_limit == 20
            assert settings.max_image_size == 20971520
            assert settings.sentry_dsn == 'https://test@sentry.io/project'
            assert settings.debug is True
    
    def test_case_insensitive_environment_variables(self):
        """Test that environment variables are case insensitive"""
        test_env = {
            'line_channel_access_token': 'test_token_lower',
            'LINE_CHANNEL_SECRET': 'test_secret_upper',
            'Google_Api_Key': 'test_key_mixed',
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            settings = Settings()
            
            assert settings.line_channel_access_token == 'test_token_lower'
            assert settings.line_channel_secret == 'test_secret_upper'
            assert settings.google_api_key == 'test_key_mixed'
    
    def test_port_alias_environment_variable(self):
        """Test that PORT environment variable is aliased to app_port"""
        with patch.dict(os.environ, {'PORT': '3000'}, clear=True):
            settings = Settings()
            assert settings.app_port == 3000
        
        # Test that APP_PORT also works
        with patch.dict(os.environ, {'APP_PORT': '4000'}, clear=True):
            settings = Settings()
            assert settings.app_port == 4000
        
        # Test PORT takes precedence when both exist
        with patch.dict(os.environ, {'PORT': '3000', 'APP_PORT': '4000'}, clear=True):
            settings = Settings()
            assert settings.app_port == 3000
    
    def test_boolean_environment_variable_parsing(self):
        """Test parsing of boolean values from environment variables"""
        true_values = ['true', 'True', 'TRUE', '1', 'yes', 'on']
        false_values = ['false', 'False', 'FALSE', '0', 'no', 'off', '']
        
        for true_val in true_values:
            with patch.dict(os.environ, {'DEBUG': true_val}, clear=True):
                settings = Settings()
                assert settings.debug is True, f"Failed for value: {true_val}"
        
        for false_val in false_values:
            with patch.dict(os.environ, {'DEBUG': false_val}, clear=True):
                settings = Settings()
                assert settings.debug is False, f"Failed for value: {false_val}"
    
    def test_integer_environment_variable_parsing(self):
        """Test parsing of integer values from environment variables"""
        test_cases = [
            ('RATE_LIMIT_PER_USER', '75', 'rate_limit_per_user', 75),
            ('BATCH_SIZE_LIMIT', '15', 'batch_size_limit', 15),
            ('MAX_IMAGE_SIZE', '5242880', 'max_image_size', 5242880),
            ('PORT', '9000', 'app_port', 9000),
        ]
        
        for env_var, env_value, attr_name, expected_value in test_cases:
            with patch.dict(os.environ, {env_var: env_value}, clear=True):
                settings = Settings()
                actual_value = getattr(settings, attr_name)
                assert actual_value == expected_value, f"Failed for {env_var}: expected {expected_value}, got {actual_value}"
    
    def test_invalid_integer_environment_variables(self):
        """Test handling of invalid integer values in environment variables"""
        invalid_int_cases = [
            ('RATE_LIMIT_PER_USER', 'not_a_number'),
            ('BATCH_SIZE_LIMIT', '12.5'),
            ('MAX_IMAGE_SIZE', 'abc123'),
            ('PORT', 'invalid'),
        ]
        
        for env_var, invalid_value in invalid_int_cases:
            with patch.dict(os.environ, {env_var: invalid_value}, clear=True):
                with pytest.raises(ValueError):
                    Settings()
    
    def test_optional_fields_handling(self):
        """Test handling of optional fields"""
        # Test with None values
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.google_api_key_fallback is None
            assert settings.sentry_dsn is None
        
        # Test with empty string values
        with patch.dict(os.environ, {
            'GOOGLE_API_KEY_FALLBACK': '',
            'SENTRY_DSN': ''
        }, clear=True):
            settings = Settings()
            assert settings.google_api_key_fallback == ''
            assert settings.sentry_dsn == ''
        
        # Test with actual values
        with patch.dict(os.environ, {
            'GOOGLE_API_KEY_FALLBACK': 'fallback_key',
            'SENTRY_DSN': 'https://sentry.dsn'
        }, clear=True):
            settings = Settings()
            assert settings.google_api_key_fallback == 'fallback_key'
            assert settings.sentry_dsn == 'https://sentry.dsn'
    
    def test_env_file_loading(self):
        """Test loading configuration from .env file"""
        env_content = """
# LINE Bot Configuration
LINE_CHANNEL_ACCESS_TOKEN=file_access_token
LINE_CHANNEL_SECRET=file_secret

# Google AI Configuration  
GOOGLE_API_KEY=file_google_key

# Application Configuration
PORT=7000
SECRET_KEY=file_secret_key
DEBUG=true
"""
        
        with patch('builtins.open', mock_open(read_data=env_content)):
            with patch('os.path.exists', return_value=True):
                settings = Settings()
                
                # Values from .env file should be loaded
                assert settings.line_channel_access_token == 'file_access_token'
                assert settings.line_channel_secret == 'file_secret'
                assert settings.google_api_key == 'file_google_key'
                assert settings.app_port == 7000
                assert settings.secret_key == 'file_secret_key'
                assert settings.debug is True
    
    def test_environment_variables_override_env_file(self):
        """Test that environment variables take precedence over .env file"""
        env_file_content = """
LINE_CHANNEL_ACCESS_TOKEN=file_token
SECRET_KEY=file_secret
"""
        
        env_vars = {
            'LINE_CHANNEL_ACCESS_TOKEN': 'env_token',
            'SECRET_KEY': 'env_secret'
        }
        
        with patch('builtins.open', mock_open(read_data=env_file_content)):
            with patch('os.path.exists', return_value=True):
                with patch.dict(os.environ, env_vars, clear=True):
                    settings = Settings()
                    
                    # Environment variables should override .env file
                    assert settings.line_channel_access_token == 'env_token'
                    assert settings.secret_key == 'env_secret'
    
    def test_settings_immutability(self):
        """Test that settings behave consistently after creation"""
        with patch.dict(os.environ, {
            'LINE_CHANNEL_ACCESS_TOKEN': 'initial_token',
            'DEBUG': 'false'
        }, clear=True):
            settings = Settings()
            
            initial_token = settings.line_channel_access_token
            initial_debug = settings.debug
            
            # Changing environment variables after creation shouldn't affect existing instance
            os.environ['LINE_CHANNEL_ACCESS_TOKEN'] = 'changed_token'
            os.environ['DEBUG'] = 'true'
            
            assert settings.line_channel_access_token == initial_token
            assert settings.debug == initial_debug
    
    def test_settings_field_descriptions(self):
        """Test that field descriptions are properly set"""
        settings = Settings()
        
        # Get field info from the model
        model_fields = settings.model_fields
        
        # Verify some key field descriptions
        assert model_fields['line_channel_access_token'].description == "LINE Channel Access Token"
        assert model_fields['line_channel_secret'].description == "LINE Channel Secret"
        assert model_fields['google_api_key'].description == "Google API Key"
        assert model_fields['google_api_key_fallback'].description == "Fallback Google API Key"
        assert model_fields['notion_api_key'].description == "Notion API Key"
        assert model_fields['notion_database_id'].description == "Notion Database ID"
    
    def test_production_ready_configuration(self):
        """Test typical production configuration scenario"""
        production_env = {
            'LINE_CHANNEL_ACCESS_TOKEN': 'prod_line_token_12345',
            'LINE_CHANNEL_SECRET': 'prod_line_secret_67890',
            'GOOGLE_API_KEY': 'prod_google_key_abcdef',
            'GOOGLE_API_KEY_FALLBACK': 'prod_fallback_key_ghijkl',
            'NOTION_API_KEY': 'prod_notion_key_mnopqr',
            'NOTION_DATABASE_ID': 'prod_database_id_stuvwx',
            'SECRET_KEY': 'prod_super_secret_key_2024',
            'FLASK_ENV': 'production',
            'DEBUG': 'false',
            'SENTRY_DSN': 'https://prod@sentry.io/project123',
            'RATE_LIMIT_PER_USER': '50',
            'BATCH_SIZE_LIMIT': '10',
            'MAX_IMAGE_SIZE': '10485760'
        }
        
        with patch.dict(os.environ, production_env, clear=True):
            settings = Settings()
            
            # Verify all production settings are loaded correctly
            assert settings.line_channel_access_token == 'prod_line_token_12345'
            assert settings.line_channel_secret == 'prod_line_secret_67890'
            assert settings.google_api_key == 'prod_google_key_abcdef'
            assert settings.google_api_key_fallback == 'prod_fallback_key_ghijkl'
            assert settings.notion_api_key == 'prod_notion_key_mnopqr'
            assert settings.notion_database_id == 'prod_database_id_stuvwx'
            assert settings.secret_key == 'prod_super_secret_key_2024'
            assert settings.flask_env == 'production'
            assert settings.debug is False
            assert settings.sentry_dsn == 'https://prod@sentry.io/project123'
            assert settings.rate_limit_per_user == 50
            assert settings.batch_size_limit == 10
            assert settings.max_image_size == 10485760
    
    def test_development_configuration(self):
        """Test typical development configuration scenario"""
        dev_env = {
            'LINE_CHANNEL_ACCESS_TOKEN': 'dev_line_token',
            'LINE_CHANNEL_SECRET': 'dev_line_secret',
            'GOOGLE_API_KEY': 'dev_google_key',
            'NOTION_API_KEY': 'dev_notion_key',
            'NOTION_DATABASE_ID': 'dev_database_id',
            'SECRET_KEY': 'dev_secret_key',
            'FLASK_ENV': 'development',
            'DEBUG': 'true',
            'PORT': '5000',
            'APP_HOST': 'localhost',
            'RATE_LIMIT_PER_USER': '1000',  # Higher limit for dev
            'BATCH_SIZE_LIMIT': '50'  # Higher limit for dev
        }
        
        with patch.dict(os.environ, dev_env, clear=True):
            settings = Settings()
            
            assert settings.flask_env == 'development'
            assert settings.debug is True
            assert settings.app_port == 5000
            assert settings.app_host == 'localhost'
            assert settings.rate_limit_per_user == 1000
            assert settings.batch_size_limit == 50
            assert settings.sentry_dsn is None  # Often not used in dev
    
    def test_minimal_configuration(self):
        """Test with minimal required configuration"""
        minimal_env = {
            'LINE_CHANNEL_ACCESS_TOKEN': 'minimal_token',
            'LINE_CHANNEL_SECRET': 'minimal_secret',
            'GOOGLE_API_KEY': 'minimal_google_key',
            'NOTION_API_KEY': 'minimal_notion_key',
            'NOTION_DATABASE_ID': 'minimal_database_id'
        }
        
        with patch.dict(os.environ, minimal_env, clear=True):
            settings = Settings()
            
            # Required fields should be set
            assert settings.line_channel_access_token == 'minimal_token'
            assert settings.line_channel_secret == 'minimal_secret'
            assert settings.google_api_key == 'minimal_google_key'
            assert settings.notion_api_key == 'minimal_notion_key'
            assert settings.notion_database_id == 'minimal_database_id'
            
            # Optional/default fields should use defaults
            assert settings.google_api_key_fallback is None
            assert settings.sentry_dsn is None
            assert settings.debug is False
            assert settings.app_port == 5002
            assert settings.flask_env == 'production'


class TestSettingsGlobalInstance:
    """Test the global settings instance"""
    
    def test_global_settings_import(self):
        """Test that global settings instance can be imported"""
        from simple_config import settings
        
        assert isinstance(settings, Settings)
        assert hasattr(settings, 'line_channel_access_token')
        assert hasattr(settings, 'google_api_key')
        assert hasattr(settings, 'notion_api_key')
    
    def test_global_settings_singleton_behavior(self):
        """Test that multiple imports return the same instance"""
        from simple_config import settings as settings1
        from simple_config import settings as settings2
        
        # Should be the same object
        assert settings1 is settings2
    
    def test_global_settings_with_environment(self):
        """Test global settings with environment variables"""
        test_env = {
            'LINE_CHANNEL_ACCESS_TOKEN': 'global_test_token',
            'DEBUG': 'true'
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            # Re-import to get fresh instance with new env vars
            import importlib
            import simple_config
            importlib.reload(simple_config)
            
            from simple_config import settings
            
            assert settings.line_channel_access_token == 'global_test_token'
            assert settings.debug is True


class TestSettingsEdgeCases:
    """Test edge cases and error scenarios"""
    
    def test_very_long_string_values(self):
        """Test handling of very long string values"""
        long_value = 'x' * 10000  # 10KB string
        
        with patch.dict(os.environ, {
            'LINE_CHANNEL_ACCESS_TOKEN': long_value,
            'SECRET_KEY': long_value
        }, clear=True):
            settings = Settings()
            
            assert settings.line_channel_access_token == long_value
            assert settings.secret_key == long_value
    
    def test_special_characters_in_values(self):
        """Test handling of special characters in values"""
        special_values = {
            'LINE_CHANNEL_ACCESS_TOKEN': 'token_with_!@#$%^&*()_+-={}[]|\\:";\'<>?,./`~',
            'SECRET_KEY': 'secret_with_unicode_测试_🔑_emoji',
            'SENTRY_DSN': 'https://key:secret@sentry.io/project?param=value&other=test'
        }
        
        with patch.dict(os.environ, special_values, clear=True):
            settings = Settings()
            
            assert settings.line_channel_access_token == special_values['LINE_CHANNEL_ACCESS_TOKEN']
            assert settings.secret_key == special_values['SECRET_KEY']
            assert settings.sentry_dsn == special_values['SENTRY_DSN']
    
    def test_extreme_integer_values(self):
        """Test handling of extreme integer values"""
        with patch.dict(os.environ, {
            'RATE_LIMIT_PER_USER': '0',
            'BATCH_SIZE_LIMIT': '1',
            'MAX_IMAGE_SIZE': '1024',
            'PORT': '1'
        }, clear=True):
            settings = Settings()
            
            assert settings.rate_limit_per_user == 0
            assert settings.batch_size_limit == 1
            assert settings.max_image_size == 1024
            assert settings.app_port == 1
        
        # Test large values
        with patch.dict(os.environ, {
            'RATE_LIMIT_PER_USER': '999999',
            'BATCH_SIZE_LIMIT': '1000',
            'MAX_IMAGE_SIZE': '1073741824',  # 1GB
            'PORT': '65535'
        }, clear=True):
            settings = Settings()
            
            assert settings.rate_limit_per_user == 999999
            assert settings.batch_size_limit == 1000
            assert settings.max_image_size == 1073741824
            assert settings.app_port == 65535
    
    def test_negative_integer_values(self):
        """Test handling of negative integer values"""
        with patch.dict(os.environ, {
            'RATE_LIMIT_PER_USER': '-1',
            'PORT': '-100'
        }, clear=True):
            settings = Settings()
            
            # Pydantic should allow negative values (validation depends on use case)
            assert settings.rate_limit_per_user == -1
            assert settings.app_port == -100
    
    def test_empty_string_vs_none_handling(self):
        """Test distinction between empty strings and None values"""
        # Test empty strings
        with patch.dict(os.environ, {
            'LINE_CHANNEL_ACCESS_TOKEN': '',
            'GOOGLE_API_KEY_FALLBACK': '',
            'SENTRY_DSN': ''
        }, clear=True):
            settings = Settings()
            
            assert settings.line_channel_access_token == ''
            assert settings.google_api_key_fallback == ''
            assert settings.sentry_dsn == ''
        
        # Test None values (no environment variable set)
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            
            assert settings.line_channel_access_token == ''  # Has default
            assert settings.google_api_key_fallback is None  # Optional, no default
            assert settings.sentry_dsn is None  # Optional, no default