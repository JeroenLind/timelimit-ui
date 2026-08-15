"""Persistence abstraction for server selection storage.

This module provides a persistence abstraction that supports different storage
implementations for Windows (development) and Home Assistant (production) environments.

The HA environment is detected via a command-line argument (--ha-ingress) passed
from the HA start script.

Usage:
    from persistence import get_server_selection_store
    
    store = get_server_selection_store()
    server_key = store.get_selected_server_key()
    store.set_selected_server_key('local')
"""

import json
import os
import sys
import threading
import tempfile
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from utils.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# Abstract Base Class
# ============================================================================

class ServerSelectionStore(ABC):
    """Abstract base class for server selection persistence.
    
    Provides an interface for storing and retrieving the selected server key
    and URL. Implementations can use different storage mechanisms (file, database, etc.).
    """
    
    @abstractmethod
    def get_selected_server_key(self) -> Optional[str]:
        """Get the last selected server key.
        
        Returns:
            The server key (e.g., 'local', 'official', 'debug') or None if not set.
        """
        pass
    
    @abstractmethod
    def set_selected_server_key(self, key: str) -> None:
        """Save the selected server key.
        
        Args:
            key: The server key to save.
        """
        pass
    
    @abstractmethod
    def get_selected_server_url(self) -> Optional[str]:
        """Get the last selected server URL.
        
        Returns:
            The server URL or None if not set.
        """
        pass
    
    @abstractmethod
    def set_selected_server_url(self, url: str) -> None:
        """Save the selected server URL.
        
        Args:
            url: The server URL to save.
        """
        pass


# ============================================================================
# File-Based Implementation
# ============================================================================

class FileServerSelectionStore(ServerSelectionStore):
    """File-based implementation of server selection persistence.
    
    Stores server selection in a JSON file with atomic writes.
    Thread-safe with file locking.
    
    Attributes:
        file_path: Path to the JSON file for storage.
    """
    
    def __init__(self, file_path: str):
        """Initialize the file-based store.
        
        Args:
            file_path: Path to the JSON file for storage.
        """
        self.file_path = file_path
        self._lock = threading.Lock()
        self._data: Optional[Dict[str, Any]] = None
        logger.debug(
            "FileServerSelectionStore initialized",
            component="persistence",
            file_path=file_path
        )
    
    def _read(self) -> Dict[str, Any]:
        """Read data from the JSON file.
        
        Returns:
            Dictionary with stored data, or empty dict if file doesn't exist.
        """
        if self._data is not None:
            return self._data
        
        if not os.path.exists(self.file_path):
            logger.debug(
                "Persistence file does not exist, returning empty data",
                component="persistence",
                file_path=self.file_path
            )
            return {}
        
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._data = data
                logger.debug(
                    "Successfully read persistence file",
                    component="persistence",
                    file_path=self.file_path
                )
                return data
        except json.JSONDecodeError as e:
            logger.warning(
                "Failed to decode JSON from persistence file",
                component="persistence",
                file_path=self.file_path,
                error=str(e),
                error_type="json_decode_error"
            )
            return {}
        except IOError as e:
            logger.warning(
                "Failed to read persistence file",
                component="persistence",
                file_path=self.file_path,
                error=str(e),
                error_type="io_error"
            )
            return {}
    
    def _write(self, data: Dict[str, Any]) -> None:
        """Write data to the JSON file atomically.
        
        Uses atomic write pattern: write to temp file, then rename.
        
        Args:
            data: Dictionary to write.
        """
        # Ensure directory exists
        dir_path = os.path.dirname(self.file_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        
        # Write to temp file first (atomic write pattern)
        fd, temp_path = tempfile.mkstemp(
            dir=dir_path or '.',
            prefix='.tmp_',
            suffix='.json'
        )
        
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            # Atomic rename
            os.replace(temp_path, self.file_path)
            self._data = data
            logger.debug(
                "Successfully wrote to persistence file",
                component="persistence",
                file_path=self.file_path
            )
        except Exception as e:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            logger.error(
                "Failed to write to persistence file",
                component="persistence",
                file_path=self.file_path,
                error=str(e),
                error_type=type(e).__name__
            )
            raise e
    
    def get_selected_server_key(self) -> Optional[str]:
        """Get the last selected server key.
        
        Returns:
            The server key or None if not set.
        """
        with self._lock:
            data = self._read()
            key = data.get('server_key')
            logger.debug(
                "Retrieved server key from persistence",
                component="persistence",
                file_path=self.file_path,
                server_key=key
            )
            return key
    
    def set_selected_server_key(self, key: str) -> None:
        """Save the selected server key.
        
        Args:
            key: The server key to save.
        """
        with self._lock:
            data = self._read()
            data['server_key'] = key
            data['server_url'] = None  # Will be set separately
            data['updated_at'] = int(datetime.now(timezone.utc).timestamp() * 1000)
            self._write(data)
            logger.info(
                "Server key persisted",
                component="persistence",
                file_path=self.file_path,
                server_key=key,
                updated_at=data['updated_at']
            )
    
    def get_selected_server_url(self) -> Optional[str]:
        """Get the last selected server URL.
        
        Returns:
            The server URL or None if not set.
        """
        with self._lock:
            data = self._read()
            url = data.get('server_url')
            logger.debug(
                "Retrieved server URL from persistence",
                component="persistence",
                file_path=self.file_path,
                server_url=url
            )
            return url
    
    def set_selected_server_url(self, url: str) -> None:
        """Save the selected server URL.
        
        Args:
            url: The server URL to save.
        """
        with self._lock:
            data = self._read()
            data['server_url'] = url
            data['updated_at'] = int(datetime.now(timezone.utc).timestamp() * 1000)
            self._write(data)
            logger.info(
                "Server URL persisted",
                component="persistence",
                file_path=self.file_path,
                server_url=url,
                updated_at=data['updated_at']
            )

    def get_log_level(self) -> Optional[str]:
        """Get the persisted log level.

        Returns:
            The log level string or None if not set.
        """
        with self._lock:
            data = self._read()
            level = data.get('log_level')
            logger.debug(
                "Retrieved log level from persistence",
                component="persistence",
                file_path=self.file_path,
                log_level=level
            )
            return level

    def set_log_level(self, level: str) -> None:
        """Save the log level to persistent storage.

        Args:
            level: The log level to save (e.g., 'DEBUG', 'INFO').
        """
        with self._lock:
            data = self._read()
            data['log_level'] = level
            data['updated_at'] = int(datetime.now(timezone.utc).timestamp() * 1000)
            self._write(data)
            logger.info(
                "Log level persisted",
                component="persistence",
                file_path=self.file_path,
                log_level=level,
                updated_at=data['updated_at']
            )


# ============================================================================
# HA Ingress Implementation
# ============================================================================

class HaIngressServerSelectionStore(FileServerSelectionStore):
    """HA Ingress implementation of server selection persistence.
    
    Extends FileServerSelectionStore to use HA's persistent /data directory.
    The file path is /data/timelimit_ui_server_selection.json which survives
    container restarts.
    """
    
    HA_DATA_DIR = '/data'
    DEFAULT_FILE_NAME = 'timelimit_ui_server_selection.json'
    
    def __init__(self, file_path: Optional[str] = None):
        """Initialize the HA ingress store.
        
        Args:
            file_path: Optional custom file path. Defaults to /data/timelimit_ui_server_selection.json
        """
        if file_path is None:
            file_path = os.path.join(self.HA_DATA_DIR, self.DEFAULT_FILE_NAME)
        super().__init__(file_path)


# ============================================================================
# Persistence Factory
# ============================================================================

def is_ha_ingress() -> bool:
    """Check if running in Home Assistant ingress environment.
    
    Detection is done via:
    1. Command-line argument --ha-ingress
    2. Environment variable HA_INGRESS=true
    
    Returns:
        True if running in HA ingress environment, False otherwise.
    """
    # Check command-line argument
    if '--ha-ingress' in sys.argv:
        logger.info(
            "HA ingress mode detected via command-line argument",
            component="persistence",
            detection_method="cli_argument"
        )
        return True
    
    # Check environment variable
    if os.environ.get('HA_INGRESS', '').lower() == 'true':
        logger.info(
            "HA ingress mode detected via environment variable",
            component="persistence",
            detection_method="environment_variable"
        )
        return True
    
    logger.debug(
        "HA ingress mode not detected",
        component="persistence"
    )
    return False


def get_persistence_dir() -> str:
    """Get the directory for persistent storage.
    
    Returns:
        Path to the persistence directory:
        - /data in HA ingress mode
        - App directory in Windows/local development mode
    """
    if is_ha_ingress():
        return '/data'
    
    # Windows/local development: use app directory
    module_dir = os.path.dirname(os.path.abspath(__file__))
    return module_dir


def get_server_selection_store() -> ServerSelectionStore:
    """Factory function to get the appropriate server selection store.
    
    Returns:
        HaIngressServerSelectionStore in HA mode, FileServerSelectionStore otherwise.
    """
    if is_ha_ingress():
        return HaIngressServerSelectionStore()
    else:
        persistence_dir = get_persistence_dir()
        file_path = os.path.join(persistence_dir, 'server_selection.json')
        return FileServerSelectionStore(file_path)


# ============================================================================
# Convenience Functions
# ============================================================================

def get_current_server_key() -> Optional[str]:
    """Get the current server key from persistent storage.
    
    Returns:
        The server key or None if not set.
    """
    store = get_server_selection_store()
    return store.get_selected_server_key()


def set_current_server_key(key: str) -> None:
    """Save the current server key to persistent storage.
    
    Args:
        key: The server key to save.
    """
    store = get_server_selection_store()
    store.set_selected_server_key(key)


def get_current_server_url() -> Optional[str]:
    """Get the current server URL from persistent storage.
    
    Returns:
        The server URL or None if not set.
    """
    store = get_server_selection_store()
    return store.get_selected_server_url()


def set_current_server_url(url: str) -> None:
    """Save the current server URL to persistent storage.
    
    Args:
        url: The server URL to save.
    """
    store = get_server_selection_store()
    store.set_selected_server_url(url)


def get_current_log_level() -> Optional[str]:
    """Get the current log level from persistent storage.

    Returns:
        The log level string or None if not set.
    """
    store = get_server_selection_store()
    return store.get_log_level()


def set_current_log_level(level: str) -> None:
    """Save the current log level to persistent storage.

    Args:
        level: The log level to save (e.g., 'DEBUG', 'INFO').
    """
    store = get_server_selection_store()
    store.set_log_level(level)


# ============================================================================
# Module-level convenience variables
# ============================================================================

# Create default store instance for convenience
_default_store: Optional[ServerSelectionStore] = None


def _get_default_store() -> ServerSelectionStore:
    """Get or create the default store instance."""
    global _default_store
    if _default_store is None:
        _default_store = get_server_selection_store()
    return _default_store