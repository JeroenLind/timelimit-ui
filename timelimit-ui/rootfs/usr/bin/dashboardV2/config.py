"""Configuration module for the dashboardV2 Flask application.

This module provides configuration management with environment variable support
for cross-platform compatibility (Windows laptop and Home Assistant).

Configuration is loaded from environment variables with sensible defaults:
- DEBUG_SERVER_URL: URL of the debug-server (default: http://192.168.68.30:8080)
- FLASK_HOST: Host to bind the Flask app (default: 0.0.0.0)
- FLASK_PORT: Port to bind the Flask app (default: 8099)
- DATABASE_PATH: Path to SQLite database file (default: dashboardV2.db)
- SCHEDULER_INTERVAL: Timechecker interval in seconds (default: 10)
- HA_INGRESS: Whether running in Home Assistant ingress mode (default: false)
"""

import os
import sys
from typing import Optional


class Config:
    """Configuration class for dashboardV2 application.
    
    All settings are loaded from environment variables with fallback defaults.
    This allows the same code to run on both Windows laptop and Home Assistant.
    """
    
    # Server selection options (matching existing dashboard.html)
    SERVER_OPTIONS: dict = {
        'local': {
            'name': '🏠 Lokaal',
            'url': 'http://192.168.68.30:8080'
        },
        'official': {
            'name': '🌍 Officieel',
            'url': 'https://api.timelimit.io'
        },
        'debug': {
            'name': '🐛 Debug Server',
            'url': 'http://192.168.68.30:8080'
        }
    }
    
    # API endpoint prefix
    API_PREFIX: str = '/api/v1'
    
    # Request timeout for HTTP calls (seconds)
    REQUEST_TIMEOUT: int = 10
    
    # Maximum retries for HTTP requests
    MAX_RETRIES: int = 3
    
    # Retry delay for HTTP requests (seconds)
    RETRY_DELAY: float = 1.0
    
    # Persistence configuration
    SERVER_SELECTION_FILE: str = 'timelimit_ui_server_selection.json'
    HA_DATA_DIR: str = '/data'
    
    @property
    def DEBUG_SERVER_URL(self) -> str:
        """Debug-server API URL."""
        return os.environ.get('DEBUG_SERVER_URL', 'http://192.168.68.30:8080')
    
    @property
    def FLASK_HOST(self) -> str:
        """Flask server host."""
        return os.environ.get('FLASK_HOST', '0.0.0.0')
    
    @property
    def FLASK_PORT(self) -> int:
        """Flask server port."""
        return int(os.environ.get('FLASK_PORT', '8099'))
    
    @property
    def FLASK_DEBUG(self) -> bool:
        """Flask debug mode."""
        return os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    
    @property
    def DATABASE_PATH(self) -> str:
        """Database file path."""
        return os.environ.get('DATABASE_PATH', 'dashboardV2.db')
    
    @property
    def SCHEDULER_INTERVAL(self) -> int:
        """Scheduler interval in seconds."""
        return int(os.environ.get('SCHEDULER_INTERVAL', '10'))
    
    @property
    def SECRET_KEY(self) -> str:
        """Secret key for session signing."""
        return os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    @property
    def HA_INGRESS(self) -> bool:
        """Whether running in Home Assistant ingress environment.
        
        Detection is done via:
        1. Command-line argument --ha-ingress
        2. Environment variable HA_INGRESS=true
        
        Returns:
            True if running in HA ingress mode, False otherwise.
        """
        # Check command-line argument
        if '--ha-ingress' in sys.argv:
            return True
        # Check environment variable
        if os.environ.get('HA_INGRESS', '').lower() == 'true':
            return True
        return False
    
    @property
    def PERSISTENCE_DIR(self) -> str:
        """Directory for persistent storage.
        
        Returns:
            /data in HA mode, app directory in Windows/local development mode.
        """
        if self.HA_INGRESS:
            return self.HA_DATA_DIR
        # Windows/local development: use app directory
        module_dir = os.path.dirname(os.path.abspath(__file__))
        return module_dir
    
    # ==================== Logging Configuration Properties ====================
    
    @property
    def LOG_LEVEL(self) -> str:
        """Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)."""
        return os.environ.get('LOG_LEVEL', 'INFO')
    
    @property
    def LOG_FILE_PATH(self) -> str:
        """Base path for log files."""
        return os.environ.get('LOG_FILE_PATH', 'logs/dashboardV2.log')
    
    @property
    def LOG_MAX_BYTES(self) -> int:
        """Maximum size of each log file before rotation (10MB)."""
        return int(os.environ.get('LOG_MAX_BYTES', '10485760'))
    
    @property
    def LOG_BACKUP_COUNT(self) -> int:
        """Number of rotated backup files to keep."""
        return int(os.environ.get('LOG_BACKUP_COUNT', '5'))
    
    @property
    def LOG_FORMAT(self) -> str:
        """Output format (json or console)."""
        return os.environ.get('LOG_FORMAT', 'json')
    
    @property
    def LOG_ROTATE_ON_START(self) -> bool:
        """Rotate log file on application startup (create timestamped file)."""
        return os.environ.get('LOG_ROTATE_ON_START', 'true').lower() == 'true'
    
    @property
    def LOG_WERKZEUG_FILE_PATH(self) -> str:
        """Path to the Werkzeug log file (separate from structlog output)."""
        return os.environ.get('LOG_WERKZEUG_FILE_PATH', 'logs/werkzeug.log')
    
    @property
    def MAX_LOG_FILES(self) -> int:
        """Maximum number of timestamped log files to retain on startup."""
        return int(os.environ.get('MAX_LOG_FILES', '10'))
    
    # ==================== Message Logging Properties ====================
    
    @property
    def MESSAGE_LOGGING_ENABLED(self) -> bool:
        """Enable outgoing message logging."""
        return os.environ.get('MESSAGE_LOGGING_ENABLED', 'true').lower() == 'true'
    
    @property
    def MESSAGE_LOGGING_ASYNC(self) -> bool:
        """Use background thread for non-blocking file writes."""
        return os.environ.get('MESSAGE_LOGGING_ASYNC', 'true').lower() == 'true'
    
    @property
    def MESSAGE_LOGGING_LEVEL(self) -> str:
        """Log level for message logging."""
        return os.environ.get('MESSAGE_LOGGING_LEVEL', 'INFO')
    
    @property
    def MESSAGE_LOGGING_MAX_BUFFER_SIZE(self) -> int:
        """Maximum entries in the in-memory log buffer."""
        return int(os.environ.get('MESSAGE_LOGGING_MAX_BUFFER_SIZE', '1000'))
    
    @property
    def MESSAGE_LOGGING_SANITIZE(self) -> bool:
        """Sanitize sensitive data before logging."""
        return os.environ.get('MESSAGE_LOGGING_SANITIZE', 'true').lower() == 'true'
    
    # ==================== Log Directory Property ====================
    
    @property
    def LOG_DIR(self) -> str:
        """Directory for log files."""
        return os.environ.get('LOG_DIR', 'logs')
    
    @classmethod
    def get_database_path(cls) -> str:
        """Get the absolute path to the database file.
        
        Uses os.path for cross-platform compatibility.
        
        Returns:
            Absolute path to the SQLite database file.
        """
        # Get the directory where this module is located
        module_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(module_dir, os.environ.get('DATABASE_PATH', 'dashboardV2.db'))
    
    @classmethod
    def get_persistence_file_path(cls) -> str:
        """Get the absolute path to the server selection persistence file.
        
        Uses os.path for cross-platform compatibility.
        
        Returns:
            Absolute path to the server selection JSON file.
        """
        # Determine persistence directory based on HA mode
        if '--ha-ingress' in sys.argv or os.environ.get('HA_INGRESS', '').lower() == 'true':
            persistence_dir = cls.HA_DATA_DIR
        else:
            module_dir = os.path.dirname(os.path.abspath(__file__))
            persistence_dir = module_dir
        
        return os.path.join(persistence_dir, cls.SERVER_SELECTION_FILE)
    
    @classmethod
    def get_server_url(cls, server_key: str) -> Optional[str]:
        """Get the URL for a specific server option.
        
        Args:
            server_key: Key for the server option ('local', 'official', 'debug').
            
        Returns:
            Server URL or None if key not found.
        """
        server = cls.SERVER_OPTIONS.get(server_key)
        return server['url'] if server else None
    
    @classmethod
    def get_server_name(cls, server_key: str) -> Optional[str]:
        """Get the display name for a specific server option.
        
        Args:
            server_key: Key for the server option ('local', 'official', 'debug').
            
        Returns:
            Server display name or None if key not found.
        """
        server = cls.SERVER_OPTIONS.get(server_key)
        return server['name'] if server else None
    
    def validate(self) -> bool:
        """Validate the configuration.
        
        Returns:
            True if configuration is valid, False otherwise.
        """
        if not self.DEBUG_SERVER_URL:
            return False
        if not self.SECRET_KEY:
            return False
        if self.SCHEDULER_INTERVAL < 1:
            return False
        return True


# Create a default config instance for convenience
config = Config()