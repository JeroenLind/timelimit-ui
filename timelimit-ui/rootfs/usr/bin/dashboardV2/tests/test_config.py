"""Unit tests for configuration management.

This module tests the config module functionality including:
- Configuration loading from environment variables
- Default values
- Server options
- Path resolution
- Persistence configuration (HA detection, persistence directory)
- App version configuration
"""

import os
import pytest
from unittest.mock import patch

from config import Config


class TestConfigDefaults:
    """Tests for default configuration values."""
    
    def test_default_debug_server_url(self):
        """Test default debug server URL."""
        # Save original value
        original = os.environ.get('DEBUG_SERVER_URL')
        
        try:
            # Remove env var to test default
            if 'DEBUG_SERVER_URL' in os.environ:
                del os.environ['DEBUG_SERVER_URL']
            
            # Create new config instance
            config = Config()
            
            assert config.DEBUG_SERVER_URL == 'http://127.0.0.1:8081'
        finally:
            # Restore original value
            if original:
                os.environ['DEBUG_SERVER_URL'] = original
    
    def test_default_flask_host(self):
        """Test default Flask host."""
        original = os.environ.get('FLASK_HOST')
        
        try:
            if 'FLASK_HOST' in os.environ:
                del os.environ['FLASK_HOST']
            
            config = Config()
            
            assert config.FLASK_HOST == '0.0.0.0'
        finally:
            if original:
                os.environ['FLASK_HOST'] = original
    
    def test_default_flask_port(self):
        """Test default Flask port."""
        original = os.environ.get('FLASK_PORT')
        
        try:
            if 'FLASK_PORT' in os.environ:
                del os.environ['FLASK_PORT']
            
            config = Config()
            
            assert config.FLASK_PORT == 8099
        finally:
            if original:
                os.environ['FLASK_PORT'] = original
    
    def test_default_database_path(self):
        """Test default database path."""
        original = os.environ.get('DATABASE_PATH')
        
        try:
            if 'DATABASE_PATH' in os.environ:
                del os.environ['DATABASE_PATH']
            
            config = Config()
            
            assert config.DATABASE_PATH == 'dashboardV2.db'
        finally:
            if original:
                os.environ['DATABASE_PATH'] = original
    
    def test_default_scheduler_interval(self):
        """Test default scheduler interval."""
        original = os.environ.get('SCHEDULER_INTERVAL')
        
        try:
            if 'SCHEDULER_INTERVAL' in os.environ:
                del os.environ['SCHEDULER_INTERVAL']
            
            config = Config()
            
            assert config.SCHEDULER_INTERVAL == 60
        finally:
            if original:
                os.environ['SCHEDULER_INTERVAL'] = original


class TestConfigEnvironmentVariables:
    """Tests for environment variable configuration."""
    
    def test_debug_server_url_from_env(self):
        """Test debug server URL from environment variable."""
        with patch.dict(os.environ, {'DEBUG_SERVER_URL': 'http://custom:9000'}):
            config = Config()
            assert config.DEBUG_SERVER_URL == 'http://custom:9000'
    
    def test_flask_host_from_env(self):
        """Test Flask host from environment variable."""
        with patch.dict(os.environ, {'FLASK_HOST': '127.0.0.1'}):
            config = Config()
            assert config.FLASK_HOST == '127.0.0.1'
    
    def test_flask_port_from_env(self):
        """Test Flask port from environment variable."""
        with patch.dict(os.environ, {'FLASK_PORT': '5000'}):
            config = Config()
            assert config.FLASK_PORT == 5000
    
    def test_database_path_from_env(self):
        """Test database path from environment variable."""
        with patch.dict(os.environ, {'DATABASE_PATH': '/custom/path.db'}):
            config = Config()
            assert config.DATABASE_PATH == '/custom/path.db'
    
    def test_scheduler_interval_from_env(self):
        """Test scheduler interval from environment variable."""
        with patch.dict(os.environ, {'SCHEDULER_INTERVAL': '30'}):
            config = Config()
            assert config.SCHEDULER_INTERVAL == 30
    
    def test_secret_key_from_env(self):
        """Test secret key from environment variable."""
        with patch.dict(os.environ, {'SECRET_KEY': 'my-super-secret-key-12345'}):
            config = Config()
            assert config.SECRET_KEY == 'my-super-secret-key-12345'


class TestServerOptions:
    """Tests for server selection options."""
    
    def test_server_options_exist(self):
        """Test that server options are defined."""
        assert hasattr(Config, 'SERVER_OPTIONS')
        assert 'local' in Config.SERVER_OPTIONS
        assert 'official' in Config.SERVER_OPTIONS
        assert 'debug' in Config.SERVER_OPTIONS
    
    def test_local_server_option(self):
        """Test local server option."""
        local = Config.SERVER_OPTIONS['local']
        assert local['name'] == '🏠 Lokaal'
        assert local['url'] == 'http://192.168.68.30:8080'
    
    def test_official_server_option(self):
        """Test official server option."""
        official = Config.SERVER_OPTIONS['official']
        assert official['name'] == '🌍 Officieel'
        assert official['url'] == 'https://api.timelimit.io'
    
    def test_debug_server_option(self):
        """Test debug server option."""
        debug = Config.SERVER_OPTIONS['debug']
        assert debug['name'] == '🐛 Debug Server'
        assert debug['url'] == 'http://192.168.68.30:8080'


class TestConfigMethods:
    """Tests for Config class methods."""
    
    def test_get_database_path(self):
        """Test get_database_path method."""
        path = Config.get_database_path()
        
        # Should end with dashboardV2.db
        assert path.endswith('dashboardV2.db')
        
        # Should be an absolute path
        assert os.path.isabs(path)
    
    def test_get_server_url(self):
        """Test get_server_url method."""
        url = Config.get_server_url('local')
        assert url == 'http://192.168.68.30:8080'
        
        url = Config.get_server_url('official')
        assert url == 'https://api.timelimit.io'
        
        url = Config.get_server_url('debug')
        assert url == 'http://192.168.68.30:8080'
        
        # Invalid key returns None
        url = Config.get_server_url('invalid')
        assert url is None
    
    def test_get_server_name(self):
        """Test get_server_name method."""
        name = Config.get_server_name('local')
        assert name == '🏠 Lokaal'
        
        name = Config.get_server_name('official')
        assert name == '🌍 Officieel'
        
        name = Config.get_server_name('debug')
        assert name == '🐛 Debug Server'
        
        # Invalid key returns None
        name = Config.get_server_name('invalid')
        assert name is None
    
    def test_validate_valid_config(self):
        """Test validate method with valid config."""
        with patch.dict(os.environ, {
            'DEBUG_SERVER_URL': 'http://localhost:8080',
            'SECRET_KEY': 'test-secret-key',
            'SCHEDULER_INTERVAL': '10'
        }):
            config = Config()
            assert config.validate() is True
    
    def test_validate_missing_server_url(self):
        """Test validate method with missing server URL."""
        with patch.dict(os.environ, {
            'DEBUG_SERVER_URL': '',
            'SECRET_KEY': 'test-secret-key',
            'SCHEDULER_INTERVAL': '10'
        }):
            config = Config()
            assert config.validate() is False
    
    def test_validate_missing_secret_key(self):
        """Test validate method with missing secret key."""
        with patch.dict(os.environ, {
            'DEBUG_SERVER_URL': 'http://localhost:8080',
            'SECRET_KEY': '',
            'SCHEDULER_INTERVAL': '10'
        }):
            config = Config()
            assert config.validate() is False
    
    def test_validate_invalid_scheduler_interval(self):
        """Test validate method with invalid scheduler interval."""
        with patch.dict(os.environ, {
            'DEBUG_SERVER_URL': 'http://localhost:8080',
            'SECRET_KEY': 'test-secret-key',
            'SCHEDULER_INTERVAL': '0'
        }):
            config = Config()
            assert config.validate() is False
    
    def test_get_persistence_file_path(self):
        """Test get_persistence_file_path method."""
        path = Config.get_persistence_file_path()
        
        # Should be an absolute path
        assert os.path.isabs(path)
        
        # Should contain the persistence file name
        assert 'server_selection.json' in path


class TestConfigConstants:
    """Tests for configuration constants."""
    
    def test_api_prefix(self):
        """Test API prefix constant."""
        assert Config.API_PREFIX == ''
    
    def test_request_timeout(self):
        """Test request timeout constant."""
        assert Config.REQUEST_TIMEOUT == 10
    
    def test_max_retries(self):
        """Test max retries constant."""
        assert Config.MAX_RETRIES == 3
    
    def test_retry_delay(self):
        """Test retry delay constant."""
        assert Config.RETRY_DELAY == 1.0


class TestConfigInstance:
    """Tests for Config instance creation."""
    
    def test_config_instance_exists(self):
        """Test that a config instance can be created."""
        config = Config()
        assert config is not None
    
    def test_config_instance_attributes(self):
        """Test that config instance has expected attributes."""
        config = Config()
        
        assert hasattr(config, 'DEBUG_SERVER_URL')
        assert hasattr(config, 'FLASK_HOST')
        assert hasattr(config, 'FLASK_PORT')
        assert hasattr(config, 'DATABASE_PATH')
        assert hasattr(config, 'SCHEDULER_INTERVAL')
        assert hasattr(config, 'SECRET_KEY')
        assert hasattr(config, 'SERVER_OPTIONS')
        assert hasattr(config, 'API_PREFIX')
        assert hasattr(config, 'REQUEST_TIMEOUT')
        assert hasattr(config, 'MAX_RETRIES')
        assert hasattr(config, 'RETRY_DELAY')


class TestConfigCrossPlatform:
    """Tests for cross-platform compatibility."""
    
    def test_database_path_uses_os_path(self):
        """Test that database path uses os.path for cross-platform compatibility."""
        # The get_database_path method should use os.path.join
        path = Config.get_database_path()
        
        # Should work on both Windows and Unix
        assert isinstance(path, str)
        
        # Should contain the database filename
        assert 'dashboardV2.db' in path
    
    def test_path_separators(self):
        """Test that path separators are handled correctly."""
        # This test ensures the code doesn't hardcode Unix paths
        path = Config.get_database_path()
        
        # Should not contain hardcoded Unix paths
        assert not path.startswith('/usr/')
        assert not path.startswith('/home/')


class TestPersistenceConfig:
    """Tests for persistence-related configuration."""
    
    def test_ha_ingress_property_default(self):
        """Test HA_INGRESS property default value."""
        original_argv = os.sys.argv
        original_env = os.environ.get('HA_INGRESS')
        
        try:
            # Clear HA_INGRESS env var
            if 'HA_INGRESS' in os.environ:
                del os.environ['HA_INGRESS']
            
            # Set argv without --ha-ingress
            os.sys.argv = ['app.py']
            
            config = Config()
            assert config.HA_INGRESS is False
        finally:
            os.sys.argv = original_argv
            if original_env:
                os.environ['HA_INGRESS'] = original_env
    
    def test_ha_ingress_property_true_from_arg(self):
        """Test HA_INGRESS property when --ha-ingress is in argv."""
        original_argv = os.sys.argv
        original_env = os.environ.get('HA_INGRESS')
        
        try:
            # Clear HA_INGRESS env var
            if 'HA_INGRESS' in os.environ:
                del os.environ['HA_INGRESS']
            
            # Set argv with --ha-ingress
            os.sys.argv = ['app.py', '--ha-ingress']
            
            config = Config()
            assert config.HA_INGRESS is True
        finally:
            os.sys.argv = original_argv
            if original_env:
                os.environ['HA_INGRESS'] = original_env
    
    def test_ha_ingress_property_true_from_env(self):
        """Test HA_INGRESS property when HA_INGRESS env var is set."""
        original_argv = os.sys.argv
        original_env = os.environ.get('HA_INGRESS')
        
        try:
            # Set HA_INGRESS env var
            os.environ['HA_INGRESS'] = 'true'
            
            # Set argv without --ha-ingress
            os.sys.argv = ['app.py']
            
            config = Config()
            assert config.HA_INGRESS is True
        finally:
            os.sys.argv = original_argv
            if original_env:
                os.environ['HA_INGRESS'] = original_env
            else:
                if 'HA_INGRESS' in os.environ:
                    del os.environ['HA_INGRESS']
    
    def test_persistence_dir_windows(self):
        """Test PERSISTENCE_DIR property in Windows/local mode."""
        original_argv = os.sys.argv
        original_env = os.environ.get('HA_INGRESS')
        
        try:
            # Clear HA_INGRESS env var
            if 'HA_INGRESS' in os.environ:
                del os.environ['HA_INGRESS']
            
            # Set argv without --ha-ingress
            os.sys.argv = ['app.py']
            
            config = Config()
            persistence_dir = config.PERSISTENCE_DIR
            
            # Should be the app directory (dashboardV2)
            assert 'dashboardV2' in persistence_dir
        finally:
            os.sys.argv = original_argv
            if original_env:
                os.environ['HA_INGRESS'] = original_env
    
    def test_persistence_dir_ha(self):
        """Test PERSISTENCE_DIR property in HA mode."""
        original_argv = os.sys.argv
        original_env = os.environ.get('HA_INGRESS')
        
        try:
            # Set HA_INGRESS env var
            os.environ['HA_INGRESS'] = 'true'
            
            # Set argv with --ha-ingress
            os.sys.argv = ['app.py', '--ha-ingress']
            
            config = Config()
            persistence_dir = config.PERSISTENCE_DIR
            
            # Should be /data in HA mode
            assert persistence_dir == '/data'
        finally:
            os.sys.argv = original_argv
            if original_env:
                os.environ['HA_INGRESS'] = original_env
            else:
                if 'HA_INGRESS' in os.environ:
                    del os.environ['HA_INGRESS']
    
    def test_persistence_file_path_property(self):
        """Test SERVER_SELECTION_FILE property."""
        original_argv = os.sys.argv
        original_env = os.environ.get('HA_INGRESS')
        
        try:
            # Clear HA_INGRESS env var
            if 'HA_INGRESS' in os.environ:
                del os.environ['HA_INGRESS']
            
            # Set argv without --ha-ingress
            os.sys.argv = ['app.py']
            
            config = Config()
            file_path = config.SERVER_SELECTION_FILE
            
            # Should be in the app directory
            assert 'server_selection.json' in file_path
        finally:
            os.sys.argv = original_argv
            if original_env:
                os.environ['HA_INGRESS'] = original_env


class TestAppVersionConfig:
    """Tests for APP_VERSION configuration."""
    
    def test_app_version_default(self):
        """Test APP_VERSION property defaults to 226 when env var not set."""
        original = os.environ.get('DASHBOARD_APP_VERSION')
        
        try:
            # Remove env var to test default
            if 'DASHBOARD_APP_VERSION' in os.environ:
                del os.environ['DASHBOARD_APP_VERSION']
            
            config = Config()
            assert config.APP_VERSION == 226
        finally:
            if original:
                os.environ['DASHBOARD_APP_VERSION'] = original
    
    def test_app_version_from_env(self):
        """Test APP_VERSION property reads from environment variable."""
        original = os.environ.get('DASHBOARD_APP_VERSION')
        
        try:
            with patch.dict(os.environ, {'DASHBOARD_APP_VERSION': '123'}):
                config = Config()
                # Should be 123 from env
                assert config.APP_VERSION == 123
        finally:
            if original:
                os.environ['DASHBOARD_APP_VERSION'] = original
    
    def test_app_version_invalid_env_value(self):
        """Test APP_VERSION property falls back to default for invalid env value."""
        original = os.environ.get('DASHBOARD_APP_VERSION')
        
        try:
            with patch.dict(os.environ, {'DASHBOARD_APP_VERSION': 'invalid'}):
                config = Config()
                # Should fall back to default 226
                assert config.APP_VERSION == 226
        finally:
            if original:
                os.environ['DASHBOARD_APP_VERSION'] = original
    
    def test_app_version_env_zero(self):
        """Test APP_VERSION property accepts 0 from environment variable."""
        original = os.environ.get('DASHBOARD_APP_VERSION')
        
        try:
            with patch.dict(os.environ, {'DASHBOARD_APP_VERSION': '0'}):
                config = Config()
                # Should be 0 from env
                assert config.APP_VERSION == 0
        finally:
            if original:
                os.environ['DASHBOARD_APP_VERSION'] = original