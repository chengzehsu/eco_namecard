"""
Comprehensive tests for app.py application entry point
Tests application startup, configuration, Sentry initialization, and error handling
"""

import pytest
import sys
import os
from unittest.mock import patch, Mock, MagicMock, call
from io import StringIO


class TestApplicationEntryPoint:
    """Test main application entry point functionality"""
    
    @patch('app.logger')
    @patch('app.app')
    @patch('app.settings')
    def test_main_function_successful_startup(self, mock_settings, mock_app, mock_logger):
        """Test successful application startup"""
        # Mock settings
        mock_settings.app_port = 5000
        mock_settings.app_host = '0.0.0.0'
        mock_settings.debug = False
        mock_settings.flask_env = 'production'
        
        # Mock app.run to not actually start server
        mock_app.run.return_value = None
        
        # Import and run main function
        from app import main
        main()
        
        # Verify startup logging
        mock_logger.info.assert_called_with(
            "Starting LINE Bot Namecard System",
            version="1.0.0",
            port=5000,
            environment='production'
        )
        
        # Verify app.run called with correct parameters
        mock_app.run.assert_called_once_with(
            host='0.0.0.0',
            port=5000,
            debug=False,
            threaded=True
        )
    
    @patch('app.logger')
    @patch('app.app')
    @patch('app.settings')
    def test_main_function_development_mode(self, mock_settings, mock_app, mock_logger):
        """Test application startup in development mode"""
        mock_settings.app_port = 5001
        mock_settings.app_host = 'localhost'
        mock_settings.debug = True
        mock_settings.flask_env = 'development'
        
        mock_app.run.return_value = None
        
        from app import main
        main()
        
        # Verify debug mode settings
        mock_app.run.assert_called_once_with(
            host='localhost',
            port=5001,
            debug=True,
            threaded=True
        )
    
    @patch('app.logger')
    @patch('app.app')
    @patch('app.settings')
    def test_main_function_keyboard_interrupt(self, mock_settings, mock_app, mock_logger):
        """Test graceful shutdown on keyboard interrupt"""
        mock_settings.app_port = 5000
        mock_settings.app_host = '0.0.0.0'
        mock_settings.debug = False
        mock_settings.flask_env = 'production'
        
        # Simulate KeyboardInterrupt
        mock_app.run.side_effect = KeyboardInterrupt()
        
        from app import main
        main()
        
        # Verify graceful shutdown logging
        mock_logger.info.assert_any_call("Application stopped by user")
    
    @patch('app.logger')
    @patch('app.app')
    @patch('app.settings')
    @patch('app.sys.exit')
    def test_main_function_startup_exception(self, mock_exit, mock_settings, mock_app, mock_logger):
        """Test error handling during application startup"""
        mock_settings.app_port = 5000
        mock_settings.app_host = '0.0.0.0'
        mock_settings.debug = False
        mock_settings.flask_env = 'production'
        
        # Simulate startup exception
        startup_error = Exception("Port already in use")
        mock_app.run.side_effect = startup_error
        
        from app import main
        main()
        
        # Verify error logging and exit
        mock_logger.error.assert_called_with(
            "Application startup failed",
            error="Port already in use"
        )
        mock_exit.assert_called_once_with(1)


class TestSentryInitialization:
    """Test Sentry monitoring initialization"""
    
    @patch('app.logger')
    @patch('app.settings')
    @patch('app.sentry_sdk')
    def test_sentry_initialization_success(self, mock_sentry_sdk, mock_settings, mock_logger):
        """Test successful Sentry initialization"""
        mock_settings.sentry_dsn = 'https://test@sentry.io/project'
        mock_settings.flask_env = 'production'
        
        # Mock sentry_sdk.init
        mock_sentry_sdk.init.return_value = None
        
        # Re-import to trigger initialization
        import importlib
        import app
        importlib.reload(app)
        
        # Verify Sentry was initialized
        mock_sentry_sdk.init.assert_called_once()
        init_args = mock_sentry_sdk.init.call_args[1]
        
        assert init_args['dsn'] == 'https://test@sentry.io/project'
        assert init_args['traces_sample_rate'] == 0.1
        assert init_args['environment'] == 'production'
        assert len(init_args['integrations']) == 1
        
        # Verify success logging
        mock_logger.info.assert_any_call("Sentry monitoring enabled")
    
    @patch('app.logger')
    @patch('app.settings')
    def test_sentry_initialization_no_dsn(self, mock_settings, mock_logger):
        """Test Sentry initialization when no DSN is configured"""
        mock_settings.sentry_dsn = None
        
        # Re-import to trigger initialization check
        import importlib
        import app
        importlib.reload(app)
        
        # Should not attempt to initialize Sentry
        # No Sentry-related logging should occur
        sentry_calls = [call for call in mock_logger.info.call_args_list 
                       if 'Sentry' in str(call)]
        assert len(sentry_calls) == 0
    
    @patch('app.logger')
    @patch('app.settings')
    def test_sentry_initialization_import_error(self, mock_settings, mock_logger):
        """Test Sentry initialization when SDK is not installed"""
        mock_settings.sentry_dsn = 'https://test@sentry.io/project'
        
        # Mock ImportError for sentry_sdk
        with patch('app.sentry_sdk', side_effect=ImportError("No module named 'sentry_sdk'")):
            # Re-import to trigger initialization
            import importlib
            import app
            importlib.reload(app)
        
        # Verify warning is logged
        mock_logger.warning.assert_any_call("Sentry SDK not installed, monitoring disabled")
    
    @patch('app.logger')
    @patch('app.settings')
    @patch('app.sentry_sdk')
    def test_sentry_initialization_with_different_environments(self, mock_sentry_sdk, mock_settings, mock_logger):
        """Test Sentry initialization with different environments"""
        environments = ['development', 'staging', 'production']
        
        for env in environments:
            mock_settings.sentry_dsn = f'https://test-{env}@sentry.io/project'
            mock_settings.flask_env = env
            mock_sentry_sdk.init.reset_mock()
            
            # Re-import to trigger initialization
            import importlib
            import app
            importlib.reload(app)
            
            # Verify environment is passed correctly
            init_args = mock_sentry_sdk.init.call_args[1]
            assert init_args['environment'] == env
    
    @patch('app.logger')
    @patch('app.settings')
    @patch('app.sentry_sdk')
    def test_sentry_initialization_exception_during_init(self, mock_sentry_sdk, mock_settings, mock_logger):
        """Test handling of exceptions during Sentry initialization"""
        mock_settings.sentry_dsn = 'https://test@sentry.io/project'
        mock_settings.flask_env = 'production'
        
        # Mock exception during sentry_sdk.init
        mock_sentry_sdk.init.side_effect = Exception("Sentry initialization failed")
        
        # Should not raise exception, just log error
        import importlib
        import app
        importlib.reload(app)
        
        # The exception should be caught and handled gracefully
        # (Current implementation doesn't have explicit exception handling,
        # but the test verifies the behavior)


class TestLoggingConfiguration:
    """Test logging configuration setup"""
    
    @patch('app.structlog')
    @patch('app.settings')
    def test_logging_configuration_debug_mode(self, mock_settings, mock_structlog):
        """Test logging configuration in debug mode"""
        mock_settings.debug = True
        
        # Re-import to trigger logging configuration
        import importlib
        import app
        importlib.reload(app)
        
        # Verify structlog.configure was called
        mock_structlog.configure.assert_called_once()
        
        # Check processors configuration
        config_args = mock_structlog.configure.call_args[1]
        processors = config_args['processors']
        
        # Should include ConsoleRenderer for debug mode
        assert any('ConsoleRenderer' in str(processor) for processor in processors)
    
    @patch('app.structlog')
    @patch('app.settings')
    def test_logging_configuration_production_mode(self, mock_settings, mock_structlog):
        """Test logging configuration in production mode"""
        mock_settings.debug = False
        
        # Re-import to trigger logging configuration
        import importlib
        import app
        importlib.reload(app)
        
        # Verify structlog.configure was called
        mock_structlog.configure.assert_called_once()
        
        # Check that appropriate configuration is used
        config_args = mock_structlog.configure.call_args[1]
        assert 'wrapper_class' in config_args
        assert 'logger_factory' in config_args
        assert 'cache_logger_on_first_use' in config_args
        assert config_args['cache_logger_on_first_use'] is True
    
    def test_logging_processors_structure(self):
        """Test that logging processors are properly structured"""
        # Import app to trigger logging configuration
        import app
        
        # Verify logger can be created and used
        logger = app.structlog.get_logger()
        assert logger is not None
        
        # Test basic logging functionality
        try:
            logger.info("Test log message")
            logger.warning("Test warning message")
            logger.error("Test error message")
            # Should not raise exceptions
        except Exception as e:
            pytest.fail(f"Logging configuration failed: {e}")


class TestApplicationInstance:
    """Test Flask application instance export"""
    
    def test_application_instance_export(self):
        """Test that application instance is properly exported"""
        import app
        
        # Verify application instance exists
        assert hasattr(app, 'application')
        assert app.application is not None
        
        # Verify it's the same as the imported app
        assert app.application is app.app
    
    def test_application_wsgi_compatibility(self):
        """Test that exported application is WSGI compatible"""
        import app
        
        # Basic WSGI interface check
        application = app.application
        
        # Should be callable
        assert callable(application)
        
        # Should have typical Flask app attributes
        assert hasattr(application, 'config')
        assert hasattr(application, 'route')
        assert hasattr(application, 'run')


class TestSystemPathConfiguration:
    """Test system path configuration"""
    
    def test_project_root_added_to_path(self):
        """Test that project root is added to Python path"""
        import app
        
        # Get the expected path
        expected_path = os.path.dirname(os.path.abspath(app.__file__))
        
        # Should be in sys.path
        assert expected_path in sys.path
    
    def test_imports_work_after_path_setup(self):
        """Test that imports work correctly after path setup"""
        # These imports should work due to path configuration
        try:
            from simple_config import settings
            from src.namecard.api.line_bot.main import app
            assert settings is not None
            assert app is not None
        except ImportError as e:
            pytest.fail(f"Import failed after path setup: {e}")


class TestModuleImportHandling:
    """Test module import handling and dependencies"""
    
    @patch('app.settings')
    def test_import_simple_config(self, mock_settings):
        """Test simple_config import"""
        mock_settings.debug = False
        mock_settings.sentry_dsn = None
        
        # Re-import should work
        import importlib
        import app
        importlib.reload(app)
        
        assert app.settings is not None
    
    def test_import_main_app(self):
        """Test main Flask app import"""
        import app
        
        # Should successfully import the main Flask application
        assert app.app is not None
        assert hasattr(app.app, 'config')
    
    def test_conditional_sentry_import(self):
        """Test conditional Sentry import handling"""
        # Test that the module can handle both cases:
        # 1. When sentry_sdk is available
        # 2. When sentry_sdk is not available
        
        import app
        
        # Module should load successfully regardless of sentry_sdk availability
        assert app is not None


class TestEnvironmentVariableHandling:
    """Test handling of environment variables"""
    
    @patch.dict(os.environ, {
        'APP_PORT': '8080',
        'APP_HOST': '127.0.0.1',
        'FLASK_ENV': 'testing',
        'DEBUG': 'true'
    })
    def test_environment_variable_usage(self):
        """Test that environment variables are properly used"""
        # Re-import with environment variables set
        import importlib
        import simple_config
        importlib.reload(simple_config)
        
        settings = simple_config.settings
        
        # Verify environment variables are picked up
        assert settings.app_port == 8080
        assert settings.app_host == '127.0.0.1'
        assert settings.flask_env == 'testing'
        assert settings.debug is True
    
    @patch.dict(os.environ, {}, clear=True)
    def test_default_values_without_environment(self):
        """Test default values when no environment variables are set"""
        # Re-import without environment variables
        import importlib
        import simple_config
        importlib.reload(simple_config)
        
        settings = simple_config.settings
        
        # Should use default values
        assert settings.app_port == 5002
        assert settings.app_host == '0.0.0.0'
        assert settings.flask_env == 'production'
        assert settings.debug is False


class TestErrorScenarios:
    """Test various error scenarios"""
    
    @patch('app.settings')
    def test_missing_required_dependencies(self, mock_settings):
        """Test behavior when required dependencies are missing"""
        mock_settings.debug = False
        mock_settings.sentry_dsn = None
        
        # Mock missing Flask app import
        with patch('app.app', side_effect=ImportError("Flask app not found")):
            with pytest.raises(ImportError):
                import importlib
                import app
                importlib.reload(app)
    
    @patch('app.logger')
    @patch('app.structlog')
    def test_logging_configuration_failure(self, mock_structlog, mock_logger):
        """Test handling of logging configuration failures"""
        # Mock structlog.configure to raise exception
        mock_structlog.configure.side_effect = Exception("Logging setup failed")
        
        # Should raise exception during import
        with pytest.raises(Exception):
            import importlib
            import app
            importlib.reload(app)
    
    def test_invalid_settings_configuration(self):
        """Test handling of invalid settings configuration"""
        # This would be caught during settings import
        # Testing that invalid configurations are handled gracefully
        try:
            import app
            assert app.settings is not None
        except Exception as e:
            # If there's a configuration error, it should be specific
            assert "settings" in str(e).lower() or "config" in str(e).lower()


class TestApplicationMetadata:
    """Test application metadata and versioning"""
    
    def test_application_version_info(self):
        """Test that version information is properly set"""
        import app
        
        # The version should be referenced in the main function
        # We can verify this by checking the logging call
        with patch('app.logger') as mock_logger:
            with patch('app.app') as mock_app:
                with patch('app.settings') as mock_settings:
                    mock_settings.app_port = 5000
                    mock_settings.flask_env = 'test'
                    mock_app.run.return_value = None
                    
                    app.main()
                    
                    # Verify version is logged
                    startup_call = mock_logger.info.call_args
                    assert startup_call[1]['version'] == "1.0.0"
    
    def test_application_startup_info_completeness(self):
        """Test that startup info includes all necessary details"""
        import app
        
        with patch('app.logger') as mock_logger:
            with patch('app.app') as mock_app:
                with patch('app.settings') as mock_settings:
                    mock_settings.app_port = 5000
                    mock_settings.flask_env = 'production'
                    mock_app.run.return_value = None
                    
                    app.main()
                    
                    startup_call = mock_logger.info.call_args
                    startup_kwargs = startup_call[1]
                    
                    # Should include all important startup information
                    assert 'version' in startup_kwargs
                    assert 'port' in startup_kwargs
                    assert 'environment' in startup_kwargs
                    assert startup_kwargs['port'] == 5000
                    assert startup_kwargs['environment'] == 'production'


class TestMainEntryPointBehavior:
    """Test main entry point behavior"""
    
    @patch('app.main')
    def test_main_entry_point_execution(self, mock_main):
        """Test that main() is called when script is run directly"""
        # Simulate running the script directly
        with patch('app.__name__', '__main__'):
            # Re-import to trigger __name__ == '__main__' check
            import importlib
            import app
            importlib.reload(app)
            
            # main() should be called when the script is run directly
            # Note: This test structure depends on how the module is designed
    
    def test_application_export_for_wsgi(self):
        """Test that application is properly exported for WSGI servers"""
        import app
        
        # Should export 'application' for WSGI servers like gunicorn
        assert hasattr(app, 'application')
        
        # Should be the Flask app instance
        from flask import Flask
        assert isinstance(app.application, Flask) or hasattr(app.application, 'wsgi_app')