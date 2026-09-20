"""Persistence abstraction for server selection storage.

This module provides a persistence abstraction that supports different storage
implementations for Windows (development) and Home Assistant (production) environments.

The HA environment is detected via a command-line argument (--ha-ingress) passed
from the HA start script.

Auth token persistence uses SQLite database as primary storage with JSON file
as fallback for backward compatibility and offline scenarios.

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

# Import database functions for auth token persistence
# Note: This import is done at module level to allow database operations
# The database module handles its own initialization
try:
    from database import get_database, get_latest_device_auth_token, get_latest_device_auth_token_with_mail, get_latest_own_device_id, delete_all_device_auth_tokens
    _db_available = True
except ImportError:
    _db_available = False
    logger.warning(
        "Database module not available for auth token persistence",
        component="persistence",
        error="ImportError"
    )


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


def clear_server_selection() -> None:
    """Clear the server selection from persistent storage.
    
    This removes the saved server_key and server_url, allowing the user
    to start fresh with server selection.
    """
    store = get_server_selection_store()
    with store._lock:
        data = store._read()
        data.pop('server_key', None)
        data.pop('server_url', None)
        data['updated_at'] = int(datetime.now(timezone.utc).timestamp() * 1000)
        store._write(data)
        logger.info(
            "Server selection cleared from persistence",
            component="persistence",
            file_path=store.file_path
        )


# ============================================================================
# Auth Token Persistence (for session restoration)
# Uses SQLite database as primary storage with JSON file fallback
# ============================================================================

def get_persisted_device_auth_token() -> Optional[Dict[str, Any]]:
    """Get the persisted device_auth_token and associated mail from persistent storage.
    
    This is used to restore the session on application startup.
    Uses SQLite database as primary storage, with JSON file as fallback.
    
    Returns:
        Dictionary with 'token' and 'mail' keys, or None if not set.
        Example: {'token': 'abc123...', 'mail': 'user@example.com'}
    """
    logger.debug(
        "session_restore_check",
        component="persistence"
    )
    
    # Try database first (primary storage)
    if _db_available:
        try:
            db = get_database()
            result = get_latest_device_auth_token_with_mail(db)
            if result:
                logger.debug(
                    "Retrieved device_auth_token and mail from database",
                    component="persistence",
                    token_found=True,
                    token_preview=result['token'][:8] + '...' if len(result['token']) > 8 else result['token'],
                    mail_found=bool(result.get('mail'))
                )
                return result
            else:
                logger.debug(
                    "token_not_found_in_db",
                    component="persistence"
                )
        except Exception as e:
            logger.warning(
                "Failed to retrieve device_auth_token from database, falling back to JSON file",
                component="persistence",
                error=str(e),
                error_type=type(e).__name__
            )
    
    # Fallback to JSON file
    store = get_server_selection_store()
    with store._lock:
        data = store._read()
        token = data.get('device_auth_token')
        mail = data.get('mail')
        if token:
            logger.debug(
                "Retrieved device_auth_token from JSON file (fallback)",
                component="persistence",
                file_path=store.file_path,
                token_found=True,
                token_preview=token[:8] + '...' if len(token) > 8 else token,
                mail_found=bool(mail)
            )
        else:
            logger.debug(
                "token_not_found_in_json",
                component="persistence",
                file_path=store.file_path
            )
        return {'token': token, 'mail': mail} if token else None


def set_persisted_device_auth_token(token: str, own_device_id: Optional[str] = None, mail: Optional[str] = None) -> None:
    """Save the device_auth_token to persistent storage.
    
    This allows session restoration on application restart.
    Saves to both SQLite database (primary) and JSON file (fallback).
    Also creates a backup file for recovery in case of database loss.
    
    Args:
        token: The device_auth_token to save.
        own_device_id: Optional own_device_id to also save.
        mail: Optional email address to save (for family email display).
    """
    # Save to database (primary storage)
    if _db_available:
        try:
            db = get_database()
            from database import store_auth_token
            store_auth_token(
                db=db,
                token_type='device_auth_token',
                token_value=token,
                device_id=own_device_id,
                mail=mail
            )
            logger.debug(
                "Device auth token saved to database",
                component="persistence",
                mail_saved=bool(mail)
            )
        except Exception as e:
            logger.warning(
                "Failed to save device_auth_token to database",
                component="persistence",
                error=str(e),
                error_type=type(e).__name__
            )
    
    # Also save to JSON file (fallback)
    store = get_server_selection_store()
    with store._lock:
        data = store._read()
        data['device_auth_token'] = token
        if own_device_id:
            data['own_device_id'] = own_device_id
        if mail:
            data['mail'] = mail
        data['updated_at'] = int(datetime.now(timezone.utc).timestamp() * 1000)
        store._write(data)
        logger.info(
            "Device auth token persisted to JSON file",
            component="persistence",
            file_path=store.file_path,
            updated_at=data['updated_at'],
            mail_saved=bool(mail)
        )
    
    # Create backup file for recovery
    try:
        backup_data = {
            'timestamp': int(datetime.now(timezone.utc).timestamp() * 1000),
            'device_auth_token': token,
            'own_device_id': own_device_id,
            'mail': mail,
            'backup_successful': True,
            'error': None
        }
        backup_path = get_auth_token_backup_path()
        backup_dir = os.path.dirname(backup_path)
        if backup_dir:
            os.makedirs(backup_dir, exist_ok=True)
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2)
        logger.info(
            "Auth token backup created",
            component="persistence",
            backup_path=backup_path,
            mail_saved=bool(mail)
        )
    except Exception as e:
        logger.warning(
            "Failed to create auth token backup",
            component="persistence",
            error=str(e),
            error_type=type(e).__name__
        )


def get_persisted_own_device_id() -> Optional[str]:
    """Get the persisted own_device_id from persistent storage.
    
    Uses SQLite database as primary storage, with JSON file as fallback.
    
    Returns:
        The own_device_id string or None if not set.
    """
    logger.debug(
        "device_id_restore_check",
        component="persistence"
    )
    
    # Try database first (primary storage)
    if _db_available:
        try:
            db = get_database()
            device_id = get_latest_own_device_id(db)
            if device_id:
                logger.debug(
                    "Retrieved own_device_id from database",
                    component="persistence",
                    device_id_found=True,
                    device_id=device_id
                )
                return device_id
            else:
                logger.debug(
                    "device_id_not_found_in_db",
                    component="persistence"
                )
        except Exception as e:
            logger.warning(
                "Failed to retrieve own_device_id from database, falling back to JSON file",
                component="persistence",
                error=str(e),
                error_type=type(e).__name__
            )
    
    # Fallback to JSON file
    store = get_server_selection_store()
    with store._lock:
        data = store._read()
        device_id = data.get('own_device_id')
        if device_id:
            logger.debug(
                "Retrieved own_device_id from JSON file (fallback)",
                component="persistence",
                file_path=store.file_path,
                device_id_found=True,
                device_id=device_id
            )
        else:
            logger.debug(
                "device_id_not_found_in_json",
                component="persistence",
                file_path=store.file_path
            )
        return device_id


def set_persisted_own_device_id(device_id: str) -> None:
    """Save the own_device_id to persistent storage.
    
    Saves to both SQLite database (primary) and JSON file (fallback).
    
    Args:
        device_id: The own_device_id to save.
    """
    # Save to JSON file (database doesn't have a direct own_device_id field,
    # but we can store it in the auth_tokens table as a reference)
    store = get_server_selection_store()
    with store._lock:
        data = store._read()
        data['own_device_id'] = device_id
        data['updated_at'] = int(datetime.now(timezone.utc).timestamp() * 1000)
        store._write(data)
        logger.info(
            "Own device ID persisted to JSON file",
            component="persistence",
            file_path=store.file_path,
            updated_at=data['updated_at']
        )


def clear_persisted_auth_tokens() -> None:
    """Clear persisted auth tokens from storage.
    
    Called when user logs out or session is cleared.
    Clears from both SQLite database, JSON file, and backup file.
    """
    logger.info(
        "sign_out_start",
        component="persistence"
    )
    
    # Clear from database (primary storage)
    if _db_available:
        try:
            db = get_database()
            # Check what tokens exist before clearing
            from database import get_auth_token
            cursor = db.get_connection().cursor()
            cursor.execute("SELECT COUNT(*) FROM auth_tokens WHERE token_type = 'device_auth_token'")
            count_before = cursor.fetchone()[0]
            logger.debug(
                "Auth tokens in database before clearing",
                component="persistence",
                count=count_before
            )
            
            delete_all_device_auth_tokens(db)
            
            # Verify tokens were cleared
            cursor.execute("SELECT COUNT(*) FROM auth_tokens WHERE token_type = 'device_auth_token'")
            count_after = cursor.fetchone()[0]
            logger.info(
                "Auth tokens cleared from database",
                component="persistence",
                count_before=count_before,
                count_after=count_after,
                tokens_deleted=count_before - count_after
            )
        except Exception as e:
            logger.warning(
                "Failed to clear auth tokens from database",
                component="persistence",
                error=str(e),
                error_type=type(e).__name__
            )
    else:
        logger.warning(
            "Database not available for clearing auth tokens",
            component="persistence"
        )
    
    # Also clear from JSON file (fallback)
    store = get_server_selection_store()
    with store._lock:
        data = store._read()
        token_before = data.get('device_auth_token')
        device_id_before = data.get('own_device_id')
        
        data.pop('device_auth_token', None)
        data.pop('own_device_id', None)
        data['updated_at'] = int(datetime.now(timezone.utc).timestamp() * 1000)
        store._write(data)
        
        logger.info(
            "Auth tokens cleared from JSON file",
            component="persistence",
            file_path=store.file_path,
            token_cleared=(token_before is not None),
            device_id_cleared=(device_id_before is not None)
        )
    
    # Also clear the backup file
    try:
        backup_path = get_auth_token_backup_path()
        if os.path.exists(backup_path):
            os.unlink(backup_path)
            logger.info(
                "Auth token backup cleared",
                component="persistence",
                backup_path=backup_path
            )
        else:
            logger.debug(
                "Auth token backup file does not exist",
                component="persistence",
                backup_path=backup_path
            )
    except Exception as e:
        logger.warning(
            "Failed to clear auth token backup",
            component="persistence",
            error=str(e),
            error_type=type(e).__name__
        )
    
    logger.info(
        "sign_out_complete",
        component="persistence"
    )


# ============================================================================
# Auth Token Backup and Restore
# ============================================================================

# Backup file name for auth tokens
AUTH_TOKEN_BACKUP_FILE = 'auth_token_backup.json'


def get_auth_token_backup_path() -> str:
    """Get the path to the auth token backup file.
    
    Returns:
        Path to the backup file in the persistence directory.
    """
    persistence_dir = get_persistence_dir()
    return os.path.join(persistence_dir, AUTH_TOKEN_BACKUP_FILE)


def backup_auth_tokens() -> Dict[str, Any]:
    """Create a backup of all auth tokens to a JSON file.
    
    This function creates a backup of the device_auth_token and own_device_id
    to a separate JSON file, allowing for recovery if the database is lost.
    
    Returns:
        Dictionary with backup status and data.
    """
    backup_data = {
        'timestamp': int(datetime.now(timezone.utc).timestamp() * 1000),
        'device_auth_token': None,
        'own_device_id': None,
        'backup_successful': False,
        'error': None
    }
    
    try:
        # Get current tokens from database
        if _db_available:
            try:
                db = get_database()
                from database import get_latest_device_auth_token, get_latest_own_device_id
                backup_data['device_auth_token'] = get_latest_device_auth_token(db)
                backup_data['own_device_id'] = get_latest_own_device_id(db)
            except Exception as e:
                logger.warning(
                    "Failed to read tokens from database for backup",
                    component="persistence",
                    error=str(e),
                    error_type=type(e).__name__
                )
        
        # Also check JSON file as fallback
        store = get_server_selection_store()
        with store._lock:
            data = store._read()
            if backup_data['device_auth_token'] is None:
                backup_data['device_auth_token'] = data.get('device_auth_token')
            if backup_data['own_device_id'] is None:
                backup_data['own_device_id'] = data.get('own_device_id')
        
        # Write backup file
        backup_path = get_auth_token_backup_path()
        backup_dir = os.path.dirname(backup_path)
        if backup_dir:
            os.makedirs(backup_dir, exist_ok=True)
        
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2)
        
        backup_data['backup_successful'] = True
        logger.info(
            "Auth tokens backed up successfully",
            component="persistence",
            backup_path=backup_path,
            has_device_auth_token=backup_data['device_auth_token'] is not None,
            has_own_device_id=backup_data['own_device_id'] is not None
        )
        
    except Exception as e:
        backup_data['error'] = str(e)
        logger.error(
            "Failed to backup auth tokens",
            component="persistence",
            error=str(e),
            error_type=type(e).__name__
        )
    
    return backup_data


def restore_auth_tokens() -> Dict[str, Any]:
    """Restore auth tokens from the backup file.
    
    This function restores the device_auth_token and own_device_id from
    the backup file to the database and session.
    
    Returns:
        Dictionary with restore status and data.
    """
    restore_data = {
        'timestamp': int(datetime.now(timezone.utc).timestamp() * 1000),
        'device_auth_token': None,
        'own_device_id': None,
        'restore_successful': False,
        'error': None
    }
    
    try:
        backup_path = get_auth_token_backup_path()
        
        if not os.path.exists(backup_path):
            logger.warning(
                "No auth token backup file found",
                component="persistence",
                backup_path=backup_path
            )
            restore_data['error'] = 'No backup file found'
            return restore_data
        
        # Read backup file
        with open(backup_path, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        restore_data['device_auth_token'] = backup_data.get('device_auth_token')
        restore_data['own_device_id'] = backup_data.get('own_device_id')
        
        # Restore to database
        if restore_data['device_auth_token']:
            if _db_available:
                try:
                    db = get_database()
                    from database import store_auth_token
                    store_auth_token(
                        db=db,
                        token_type='device_auth_token',
                        token_value=restore_data['device_auth_token'],
                        device_id=restore_data['own_device_id']
                    )
                    logger.info(
                        "Device auth token restored from backup",
                        component="persistence"
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to restore device auth token to database",
                        component="persistence",
                        error=str(e),
                        error_type=type(e).__name__
                    )
        
        # Also restore to JSON file
        store = get_server_selection_store()
        with store._lock:
            data = store._read()
            if restore_data['device_auth_token']:
                data['device_auth_token'] = restore_data['device_auth_token']
            if restore_data['own_device_id']:
                data['own_device_id'] = restore_data['own_device_id']
            data['updated_at'] = int(datetime.now(timezone.utc).timestamp() * 1000)
            store._write(data)
        
        restore_data['restore_successful'] = True
        logger.info(
            "Auth tokens restored successfully from backup",
            component="persistence",
            backup_timestamp=backup_data.get('timestamp')
        )
        
    except Exception as e:
        restore_data['error'] = str(e)
        logger.error(
            "Failed to restore auth tokens from backup",
            component="persistence",
            error=str(e),
            error_type=type(e).__name__
        )
    
    return restore_data


def clear_auth_token_backup() -> bool:
    """Clear the auth token backup file.
    
    This should be called when the user logs out or explicitly clears
    their authentication data.
    
    Returns:
        True if backup was cleared, False otherwise.
    """
    try:
        backup_path = get_auth_token_backup_path()
        if os.path.exists(backup_path):
            os.unlink(backup_path)
            logger.info(
                "Auth token backup cleared",
                component="persistence",
                backup_path=backup_path
            )
        return True
    except Exception as e:
        logger.warning(
            "Failed to clear auth token backup",
            component="persistence",
            error=str(e),
            error_type=type(e).__name__
        )
        return False


# ============================================================================
# Session Data Sync to Database
# ============================================================================

def sync_session_to_database() -> Dict[str, Any]:
    """Sync session data from JSON file to database.
    
    This function is called during startup to ensure that session data
    persisted in the JSON file is also stored in the database. This is
    useful after database migrations or if the database was cleared.
    
    Returns:
        Dictionary with sync results:
        - 'device_auth_token_synced': bool - Whether device_auth_token was synced
        - 'own_device_id_synced': bool - Whether own_device_id was synced
        - 'errors': list - Any errors that occurred during sync
    """
    result = {
        'device_auth_token_synced': False,
        'own_device_id_synced': False,
        'errors': []
    }
    
    # Get data from JSON file (fallback storage)
    store = get_server_selection_store()
    with store._lock:
        data = store._read()
    
    device_auth_token = data.get('device_auth_token')
    own_device_id = data.get('own_device_id')
    
    # Check if device_auth_token needs to be synced to database
    if device_auth_token:
        # Check if it's already in the database
        db_token_result = get_persisted_device_auth_token()
        db_token = db_token_result.get('token') if db_token_result else None
        if db_token != device_auth_token:
            # Token not in database or different, sync it
            try:
                set_persisted_device_auth_token(device_auth_token, own_device_id)
                result['device_auth_token_synced'] = True
                logger.info(
                    "Session data synced to database",
                    component="persistence",
                    device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None
                )
            except Exception as e:
                result['errors'].append(f"Failed to sync device_auth_token: {str(e)}")
                logger.warning(
                    "Failed to sync session data to database",
                    component="persistence",
                    error=str(e)
                )
    
    # Check if own_device_id needs to be synced
    if own_device_id:
        try:
            from database import get_latest_own_device_id
            db = get_database()
            db_device_id = get_latest_own_device_id(db)
            if db_device_id != own_device_id:
                # Device ID not in database or different, update it
                set_persisted_own_device_id(own_device_id)
                result['own_device_id_synced'] = True
                logger.debug(
                    "Own device ID synced to database",
                    component="persistence",
                    device_id=own_device_id
                )
        except Exception as e:
            result['errors'].append(f"Failed to sync own_device_id: {str(e)}")
            logger.warning(
                "Failed to sync own device ID to database",
                component="persistence",
                error=str(e)
            )
    
    return result


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