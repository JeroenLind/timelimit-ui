"""SQLite database module for dashboardV2 application.

This module provides database setup and models for storing:
- server_checks: Timechecker results from APScheduler
- families: Family account information (keyed by device_auth_token)
- devices: Device registration data
- auth_tokens: Authentication tokens for session management
- users: User data from TimeLimit sync
- sync_state: Sync version tracking
- categories: TimeLimit categories
- connected_devices: Real-time connected device tracking

The database uses SQLite for cross-platform compatibility and simplicity.
All file paths use os.path for cross-platform compatibility.

Key change: Using device_auth_token as primary key instead of family_id,
matching the official Android app's approach where the server looks up
family from device using deviceAuthToken.
"""

import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from config import Config
from utils.logging import get_logger

logger = get_logger(__name__)


class Database:
    """SQLite database manager for dashboardV2.
    
    Provides methods for database initialization, connection management,
    and CRUD operations for all entity types.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize the database manager.
        
        Args:
            db_path: Optional path to SQLite database file.
                    Uses config default if not provided.
        """
        self.db_path = db_path or Config.get_database_path()
        self._connection: Optional[sqlite3.Connection] = None
        self._lock = threading.RLock()
        logger.info(
            "Database initialized",
            component="database",
            db_path=self.db_path
        )
    
    def get_connection(self) -> sqlite3.Connection:
        """Get or create a database connection.
        
        Returns:
            SQLite connection object.
        """
        with self._lock:
            if self._connection is None:
                # check_same_thread=False allows the connection to be used across threads
                # This is necessary for Flask's threaded mode where different requests
                # are handled by different threads
                logger.debug(
                    "Creating new database connection",
                    component="database",
                    db_path=self.db_path
                )
                self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
                self._connection.row_factory = sqlite3.Row
            return self._connection
    
    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            if self._connection:
                logger.debug(
                    "Closing database connection",
                    component="database",
                    db_path=self.db_path
                )
                self._connection.close()
                self._connection = None
    
    def init_db(self) -> None:
        """Initialize the database with all required tables.
        
        Key change: Using device_auth_token as primary key instead of family_id.
        This matches the official Android app's approach where:
        - deviceAuthToken is used for all server requests
        - Server looks up family from device entry
        - No local DB queries need family_id
        """
        with self._lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Create server_checks table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS server_checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    success INTEGER NOT NULL,
                    error_code TEXT,
                    user_message TEXT,
                    technical_detail TEXT,
                    server_time INTEGER,
                    attempts INTEGER DEFAULT 0,
                    server_url TEXT NOT NULL
                )
            ''')
            
            # Create families table - using device_auth_token as primary key
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS families (
                    device_auth_token TEXT PRIMARY KEY,
                    mail TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    parent_password_hash TEXT,
                    parent_password_second_hash TEXT,
                    parent_password_second_salt TEXT,
                    parent_password_encrypted INTEGER DEFAULT 0,
                    parent_user_id TEXT
                )
            ''')
            
            # Create devices table - using device_auth_token as foreign key
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS devices (
                    id TEXT PRIMARY KEY,
                    device_auth_token TEXT NOT NULL,
                    name TEXT,
                    model TEXT,
                    created_at TEXT NOT NULL,
                    current_user_id TEXT,
                    current_protection_level INTEGER DEFAULT 0,
                    highest_protection_level INTEGER DEFAULT 0,
                    current_app_version TEXT,
                    highest_app_version TEXT,
                    public_key TEXT,
                    platform_type TEXT,
                    platform_level INTEGER DEFAULT 0,
                    FOREIGN KEY (device_auth_token) REFERENCES families(device_auth_token)
                )
            ''')
            
            # Create auth_tokens table - using device_auth_token as foreign key
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS auth_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token_type TEXT NOT NULL,
                    token_value TEXT NOT NULL UNIQUE,
                    device_id TEXT,
                    device_auth_token TEXT,
                    mail TEXT,
                    code TEXT,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    FOREIGN KEY (device_id) REFERENCES devices(id),
                    FOREIGN KEY (device_auth_token) REFERENCES families(device_auth_token)
                )
            ''')
            
            # Create users table (for TimeLimit sync) - using device_auth_token as foreign key
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    device_auth_token TEXT NOT NULL,
                    name TEXT,
                    password TEXT,
                    second_password_salt TEXT,
                    type TEXT,
                    time_zone TEXT,
                    disable_limits_until INTEGER,
                    mail TEXT,
                    current_device TEXT,
                    category_for_not_assigned_apps TEXT,
                    relax_primary_device INTEGER DEFAULT 0,
                    flags INTEGER DEFAULT 0,
                    limit_login_category TEXT,
                    pre_block_duration INTEGER DEFAULT 0,
                    last_updated INTEGER,
                    FOREIGN KEY (device_auth_token) REFERENCES families(device_auth_token)
                )
            ''')
            
            # Create sync_state table - using device_auth_token as primary key
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sync_state (
                    device_auth_token TEXT PRIMARY KEY,
                    device_list_version TEXT,
                    user_list_version TEXT,
                    last_sync_timestamp INTEGER,
                    last_sync_success INTEGER,
                    next_sequence_number INTEGER DEFAULT 0,
                    FOREIGN KEY (device_auth_token) REFERENCES families(device_auth_token)
                )
            ''')
            
            # Create categories table (for TimeLimit categories) - using device_auth_token as foreign key
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS categories (
                    id TEXT PRIMARY KEY,
                    device_auth_token TEXT NOT NULL,
                    child_id TEXT,
                    title TEXT,
                    blocked_times TEXT,
                    extra_time INTEGER,
                    extra_time_day INTEGER,
                    temp_blocked INTEGER DEFAULT 0,
                    temp_block_time INTEGER,
                    version TEXT,
                    parent_category_id TEXT,
                    block_all_notifications INTEGER DEFAULT 0,
                    time_warnings INTEGER DEFAULT 0,
                    sort_order INTEGER DEFAULT 0,
                    flags INTEGER DEFAULT 0,
                    last_updated INTEGER,
                    FOREIGN KEY (device_auth_token) REFERENCES families(device_auth_token)
                )
            ''')
            
            # Create connected_devices table - using device_auth_token as part of primary key
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS connected_devices (
                    device_auth_token TEXT NOT NULL,
                    device_id TEXT NOT NULL,
                    last_seen INTEGER,
                    name TEXT,
                    PRIMARY KEY (device_auth_token, device_id),
                    FOREIGN KEY (device_auth_token) REFERENCES families(device_auth_token)
                )
            ''')
            
            conn.commit()
            logger.info(
                "Database initialized",
                component="database",
                db_path=self.db_path
            )
            
            # Run migrations for existing databases
            self._run_migrations()
    
    def drop_tables(self) -> None:
        """Drop all tables (for testing purposes)."""
        with self._lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('DROP TABLE IF EXISTS connected_devices')
            cursor.execute('DROP TABLE IF EXISTS categories')
            cursor.execute('DROP TABLE IF EXISTS sync_state')
            cursor.execute('DROP TABLE IF EXISTS users')
            cursor.execute('DROP TABLE IF EXISTS auth_tokens')
            cursor.execute('DROP TABLE IF EXISTS devices')
            cursor.execute('DROP TABLE IF EXISTS families')
            cursor.execute('DROP TABLE IF EXISTS server_checks')
            
            conn.commit()
            logger.info(
                "All tables dropped",
                component="database",
                db_path=self.db_path
            )
    
    def clear_all_tables(self) -> Dict[str, int]:
        """Clear all data from all tables (for fresh start).
        
        Deletes all records from all tables while preserving the schema.
        This provides a fresh start without requiring database reinitialization.
        
        Returns:
            Dictionary with table names as keys and row counts deleted as values.
        """
        with self._lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            results = {}
            
            # Delete in reverse dependency order to avoid foreign key constraints
            tables = [
                'connected_devices',
                'categories',
                'sync_state',
                'users',
                'auth_tokens',
                'devices',
                'families',
                'server_checks'
            ]
            
            for table in tables:
                try:
                    cursor.execute(f'DELETE FROM {table}')
                    count = cursor.rowcount
                    results[table] = count
                    logger.debug(
                        f"Cleared {count} rows from {table}",
                        component="database",
                        table=table,
                        count=count
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to clear table {table}",
                        component="database",
                        table=table,
                        error=str(e)
                    )
                    results[table] = 0
            
            conn.commit()
            
            logger.info(
                "All tables cleared",
                component="database",
                db_path=self.db_path,
                results=results
            )
            
            return results
    
    def _run_migrations(self) -> None:
        """Run database migrations for existing databases.
        
        This method adds new columns to existing tables that were not
        present in the original schema. It's called after init_db()
        to ensure existing databases are updated to the latest schema.
        """
        with self._lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Check if name column exists in connected_devices table
            cursor.execute("PRAGMA table_info(connected_devices)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if 'name' not in columns:
                logger.info(
                    "Running migration: adding name column to connected_devices",
                    component="database",
                    db_path=self.db_path
                )
                cursor.execute('ALTER TABLE connected_devices ADD COLUMN name TEXT')
                conn.commit()
                logger.info(
                    "Migration completed: name column added to connected_devices",
                    component="database",
                    db_path=self.db_path
                )
            
            # Migration: Add parent_user_id column to families table
            cursor.execute("PRAGMA table_info(families)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if 'parent_user_id' not in columns:
                logger.info(
                    "Running migration: adding parent_user_id column to families",
                    component="database",
                    db_path=self.db_path
                )
                cursor.execute('ALTER TABLE families ADD COLUMN parent_user_id TEXT')
                conn.commit()
                logger.info(
                    "Migration completed: parent_user_id column added to families",
                    component="database",
                    db_path=self.db_path
                )


# ============================================================================
# Server Checks Operations
# ============================================================================

def save_server_check(
    db: Database,
    success: bool,
    error_code: Optional[str],
    user_message: Optional[str],
    technical_detail: Optional[str],
    server_time: Optional[int],
    attempts: int,
    server_url: str
) -> int:
    """Save a server check result to the database.
    
    Args:
        db: Database instance.
        success: Whether the check was successful.
        error_code: Error code if failed.
        user_message: User-friendly error message.
        technical_detail: Technical details for debugging.
        server_time: Server time in milliseconds if successful.
        attempts: Number of attempts made.
        server_url: The server URL that was checked.
        
    Returns:
        The ID of the inserted row.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO server_checks
                (timestamp, success, error_code, user_message, technical_detail, server_time, attempts, server_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                int(datetime.now().timestamp() * 1000),
                1 if success else 0,
                error_code,
                user_message,
                technical_detail,
                server_time,
                attempts,
                server_url
            ))
            
            conn.commit()
            row_count = cursor.rowcount
            logger.debug(
                "Server check saved",
                component="database",
                db_path=db.db_path,
                table_name="server_checks",
                row_count=row_count,
                success=success,
                server_url=server_url
            )
            return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(
                "Failed to save server check",
                component="database",
                db_path=db.db_path,
                table_name="server_checks",
                error=str(e),
                error_code="sqlite_error"
            )
            raise


def get_server_checks(
    db: Database,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Get recent server check results.
    
    Args:
        db: Database instance.
        limit: Maximum number of results to return.
        
    Returns:
        List of server check records.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM server_checks
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))
        
        result = [dict(row) for row in cursor.fetchall()]
        logger.debug(
            "Server checks retrieved",
            component="database",
            db_path=db.db_path,
            table_name="server_checks",
            limit=limit,
            count=len(result)
        )
        return result


def get_latest_server_check(
    db: Database,
    server_url: str
) -> Optional[Dict[str, Any]]:
    """Get the most recent server check for a specific server.
    
    Args:
        db: Database instance.
        server_url: The server URL to check.
        
    Returns:
        The most recent server check record, or None if not found.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM server_checks
            WHERE server_url = ?
            ORDER BY timestamp DESC
            LIMIT 1
        ''', (server_url,))
        
        row = cursor.fetchone()
        result = dict(row) if row else None
        logger.debug(
            "Latest server check retrieved",
            component="database",
            db_path=db.db_path,
            table_name="server_checks",
            server_url=server_url,
            found=result is not None
        )
        return result


# ============================================================================
# Families Operations
# ============================================================================

def create_family(
    db: Database,
    device_auth_token: str,
    mail: str,
    parent_password_hash: str,
    parent_password_second_hash: str,
    parent_password_second_salt: str,
    parent_password_encrypted: bool = False
) -> None:
    """Create a new family record.
    
    Args:
        db: Database instance.
        device_auth_token: Unique device auth token (primary key).
        mail: Parent email address.
        parent_password_hash: Bcrypt hash of parent password.
        parent_password_second_hash: Second bcrypt hash.
        parent_password_second_salt: Salt for second hash.
        parent_password_encrypted: Whether secondHash is DH-encrypted.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO families
            (device_auth_token, mail, created_at, parent_password_hash, parent_password_second_hash,
             parent_password_second_salt, parent_password_encrypted)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            device_auth_token,
            mail,
            datetime.now(timezone.utc).isoformat(),
            parent_password_hash,
            parent_password_second_hash,
            parent_password_second_salt,
            1 if parent_password_encrypted else 0
        ))
        
        conn.commit()
        logger.info(
            "Family created",
            component="database",
            db_path=db.db_path,
            table_name="families",
            device_auth_token=device_auth_token
        )


def get_family(db: Database, device_auth_token: str) -> Optional[Dict[str, Any]]:
    """Get a family by device auth token.
    
    Args:
        db: Database instance.
        device_auth_token: The device auth token to look up.
        
    Returns:
        Family record or None if not found.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM families WHERE device_auth_token = ?', (device_auth_token,))
        row = cursor.fetchone()
        
        if row:
            result = dict(row)
            result['parent_password_encrypted'] = bool(result['parent_password_encrypted'])
            return result
        return None


def get_family_by_mail(db: Database, mail: str) -> Optional[Dict[str, Any]]:
    """Get a family by email address.
    
    Args:
        db: Database instance.
        mail: The email address to look up.
        
    Returns:
        Family record or None if not found.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM families WHERE mail = ?', (mail,))
        row = cursor.fetchone()
        
        if row:
            result = dict(row)
            result['parent_password_encrypted'] = bool(result['parent_password_encrypted'])
            return result
        return None


def update_family(
    db: Database,
    device_auth_token: str,
    updates: Dict[str, Any]
) -> bool:
    """Update a family record.
    
    Args:
        db: Database instance.
        device_auth_token: The device auth token to update.
        updates: Dictionary of fields to update.
        
    Returns:
        True if updated, False if family not found.
    """
    if not updates:
        return False
    
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [device_auth_token]
        
        cursor.execute(f'''
            UPDATE families SET {set_clause} WHERE device_auth_token = ?
        ''', values)
        
        conn.commit()
        return cursor.rowcount > 0


def delete_family(db: Database, device_auth_token: str) -> bool:
    """Delete a family record.
    
    Args:
        db: Database instance.
        device_auth_token: The device auth token to delete.
        
    Returns:
        True if deleted, False if not found.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM families WHERE device_auth_token = ?', (device_auth_token,))
        conn.commit()
        
        return cursor.rowcount > 0


# ============================================================================
# Devices Operations
# ============================================================================

def create_device(
    db: Database,
    device_id: str,
    device_auth_token: str,
    name: Optional[str] = None,
    model: Optional[str] = None,
    current_user_id: Optional[str] = None,
    current_protection_level: int = 0,
    highest_protection_level: int = 0,
    current_app_version: Optional[str] = None,
    highest_app_version: Optional[str] = None,
    public_key: Optional[str] = None,
    platform_type: Optional[str] = None,
    platform_level: int = 0
) -> None:
    """Create a new device record.
    
    Args:
        db: Database instance.
        device_id: Unique device identifier.
        device_auth_token: Device auth token this device belongs to.
        name: Device name.
        model: Device model.
        current_user_id: Current user ID.
        current_protection_level: Current protection level.
        highest_protection_level: Highest protection level.
        current_app_version: Current app version.
        highest_app_version: Highest app version.
        public_key: Public key for encryption.
        platform_type: Platform type (android, etc.).
        platform_level: Platform level.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO devices
            (id, device_auth_token, name, model, created_at, current_user_id,
             current_protection_level, highest_protection_level,
             current_app_version, highest_app_version, public_key,
             platform_type, platform_level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            device_id,
            device_auth_token,
            name,
            model,
            datetime.now(timezone.utc).isoformat(),
            current_user_id,
            current_protection_level,
            highest_protection_level,
            current_app_version,
            highest_app_version,
            public_key,
            platform_type,
            platform_level
        ))
        
        conn.commit()
        logger.info(
            "Device created",
            component="database",
            db_path=db.db_path,
            table_name="devices",
            device_id=device_id
        )


def get_device(db: Database, device_id: str) -> Optional[Dict[str, Any]]:
    """Get a device by ID.
    
    Args:
        db: Database instance.
        device_id: The device ID to look up.
        
    Returns:
        Device record or None if not found.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM devices WHERE id = ?', (device_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_devices_by_device_auth_token(db: Database, device_auth_token: str) -> List[Dict[str, Any]]:
    """Get all devices for a device auth token.
    
    Args:
        db: Database instance.
        device_auth_token: The device auth token to look up.
        
    Returns:
        List of device records.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM devices WHERE device_auth_token = ?', (device_auth_token,))
        return [dict(row) for row in cursor.fetchall()]


def delete_device(db: Database, device_id: str) -> bool:
    """Delete a device record.
    
    Args:
        db: Database instance.
        device_id: The device ID to delete.
        
    Returns:
        True if deleted, False if not found.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM devices WHERE id = ?', (device_id,))
        conn.commit()
        
        return cursor.rowcount > 0


def get_user_by_id(db: Database, user_id: str) -> Optional[Dict[str, Any]]:
    """Get a user by their ID.
    
    Args:
        db: Database instance.
        user_id: The user ID to look up.
        
    Returns:
        User record or None if not found.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def update_device_app_version(
    db: Database,
    device_id: str,
    current_app_version: str,
    highest_app_version: Optional[str] = None
) -> bool:
    """Update a device's app version.
    
    Args:
        db: Database instance.
        device_id: The device ID to update.
        current_app_version: The current app version.
        highest_app_version: The highest app version (defaults to current_app_version).
        
    Returns:
        True if updated, False if device not found.
    """
    if highest_app_version is None:
        highest_app_version = current_app_version
    
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE devices
            SET current_app_version = ?, highest_app_version = ?
            WHERE id = ?
        ''', (current_app_version, highest_app_version, device_id))
        
        conn.commit()
        return cursor.rowcount > 0


# ============================================================================
# Auth Tokens Operations
# ============================================================================

def store_auth_token(
    db: Database,
    token_type: str,
    token_value: str,
    device_id: Optional[str] = None,
    device_auth_token: Optional[str] = None,
    mail: Optional[str] = None,
    code: Optional[str] = None,
    expires_at: Optional[datetime] = None
) -> None:
    """Store an authentication token.
    
    Args:
        db: Database instance.
        token_type: Type of token (mail_login_token, mail_auth_token, device_auth_token).
        token_value: The token string.
        device_id: Associated device ID.
        device_auth_token: Associated device auth token.
        mail: Associated email.
        code: Verification code (for mail_login_token).
        expires_at: Expiration datetime.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Use INSERT OR REPLACE to handle existing tokens with the same value
        cursor.execute('''
            INSERT OR REPLACE INTO auth_tokens
            (token_type, token_value, device_id, device_auth_token, mail, code, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            token_type,
            token_value,
            device_id,
            device_auth_token,
            mail,
            code,
            datetime.now(timezone.utc).isoformat(),
            expires_at.isoformat() if expires_at else None
        ))
        
        conn.commit()
        logger.info(
            "Auth token stored",
            component="database",
            db_path=db.db_path,
            table_name="auth_tokens",
            token_type=token_type
        )


def get_auth_token(
    db: Database,
    token_value: str
) -> Optional[Dict[str, Any]]:
    """Get an auth token by value.
    
    Args:
        db: Database instance.
        token_value: The token string to look up.
        
    Returns:
        Token record or None if not found or expired.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM auth_tokens WHERE token_value = ?', (token_value,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        result = dict(row)
        
        # Check expiration
        if result.get('expires_at'):
            expires_at = datetime.fromisoformat(result['expires_at'])
            if datetime.now(timezone.utc) > expires_at:
                # Token expired, delete it
                cursor.execute('DELETE FROM auth_tokens WHERE token_value = ?', (token_value,))
                conn.commit()
                return None
        
        return result


def delete_auth_token(db: Database, token_value: str) -> bool:
    """Delete an auth token.
    
    Args:
        db: Database instance.
        token_value: The token string to delete.
        
    Returns:
        True if deleted, False if not found.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM auth_tokens WHERE token_value = ?', (token_value,))
        conn.commit()
        
        return cursor.rowcount > 0


def cleanup_expired_tokens(db: Database) -> int:
    """Remove all expired tokens from the database.
    
    Args:
        db: Database instance.
        
    Returns:
        Number of tokens removed.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM auth_tokens
            WHERE expires_at IS NOT NULL AND expires_at < ?
        ''', (datetime.now(timezone.utc).isoformat(),))
        
        conn.commit()
        count = cursor.rowcount
        
        if count > 0:
            logger.info(
                "Expired tokens cleaned up",
                component="database",
                db_path=db.db_path,
                table_name="auth_tokens",
                row_count=count
            )
        
        return count


# ============================================================================
# Users Operations (TimeLimit Sync)
# ============================================================================

def save_users(
    db: Database,
    device_auth_token: str,
    users_data: List[Dict[str, Any]]
) -> None:
    """Save users from ServerDataStatus to the database.
    
    Args:
        db: Database instance.
        device_auth_token: The device auth token.
        users_data: List of user data from ServerDataStatus.users.data.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        current_time = int(datetime.now().timestamp() * 1000)
        
        for user in users_data:
            cursor.execute('''
                INSERT OR REPLACE INTO users
                (id, device_auth_token, name, password, second_password_salt, type, time_zone,
                 disable_limits_until, mail, current_device, category_for_not_assigned_apps,
                 relax_primary_device, flags, limit_login_category, pre_block_duration, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user.get('id'),
                device_auth_token,
                user.get('name'),
                user.get('password'),
                user.get('secondPasswordSalt'),
                user.get('type'),
                user.get('timeZone'),
                user.get('disableLimitsUntil'),
                user.get('mail'),
                user.get('currentDevice'),
                user.get('categoryForNotAssignedApps'),
                user.get('relaxPrimaryDevice', 0),
                user.get('flags', 0),
                user.get('limitLoginCategory'),
                user.get('preBlockDuration', 0),
                current_time
            ))
        
        conn.commit()
        logger.info(
            "Users saved",
            component="database",
            db_path=db.db_path,
            table_name="users",
            device_auth_token=device_auth_token,
            count=len(users_data)
        )


def get_users_by_device_auth_token(db: Database, device_auth_token: str) -> List[Dict[str, Any]]:
    """Get all users for a device auth token.
    
    Args:
        db: Database instance.
        device_auth_token: The device auth token to look up.
        
    Returns:
        List of user records.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE device_auth_token = ?', (device_auth_token,))
        return [dict(row) for row in cursor.fetchall()]


def get_parent_user_id(db: Database, device_auth_token: str) -> Optional[str]:
    """Get the parent user ID for a device auth token.
    
    First checks the families table (persisted during family creation),
    then falls back to the users table (populated by sync).
    
    Args:
        db: Database instance.
        device_auth_token: The device auth token to look up.
        
    Returns:
        Parent user ID or None if not found.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # First, check the families table (persisted during family creation)
        cursor.execute('SELECT parent_user_id FROM families WHERE device_auth_token = ?', (device_auth_token,))
        row = cursor.fetchone()
        if row and row['parent_user_id']:
            return row['parent_user_id']
        
        # Fall back to users table (populated by sync)
        cursor.execute('SELECT id FROM users WHERE device_auth_token = ? AND type = ?', (device_auth_token, 'parent'))
        row = cursor.fetchone()
        return row['id'] if row else None


# ============================================================================
# Password Hash Operations
# ============================================================================

def validate_password_hash(password_hash: str) -> bool:
    """Validate that a password hash is in correct bcrypt format.
    
    Args:
        password_hash: The hash to validate.
        
    Returns:
        True if valid bcrypt hash, False otherwise.
    """
    if not password_hash:
        return False
    
    # Minimum length for a valid bcrypt hash: $2a$10$ + at least 10 chars = 15 chars
    # Real bcrypt hashes are 60 characters, but we allow shorter for testing
    if len(password_hash) < 15:
        return False
    
    # Check for valid bcrypt prefixes ($2a$, $2b$, $2y$)
    valid_prefixes = ('$2a$', '$2b$', '$2y$')
    return password_hash.startswith(valid_prefixes)


def get_parent_password_hash(db: Database, device_auth_token: str) -> Optional[str]:
    """Get the parent password hash for a device auth token.
    
    Args:
        db: Database instance.
        device_auth_token: The device auth token to look up.
        
    Returns:
        Parent password hash or None if not found.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT parent_password_second_hash FROM families WHERE device_auth_token = ?', (device_auth_token,))
        row = cursor.fetchone()
        return row['parent_password_second_hash'] if row else None


def get_family_with_valid_hash(db: Database, device_auth_token: str) -> Optional[Dict[str, Any]]:
    """Get family record with validated parent password hash.
    
    Args:
        db: Database instance.
        device_auth_token: The device auth token to look up.
        
    Returns:
        Family record with valid hash, or None if not found or invalid.
    """
    family = get_family(db, device_auth_token)
    if not family:
        return None
    
    hash_value = family.get('parent_password_second_hash')
    if not validate_password_hash(hash_value):
        logger.warning(
            "Invalid or missing parent password hash in family record",
            component="database",
            device_auth_token=device_auth_token[:8] + "..." if device_auth_token else None
        )
        return None
    
    return family


def update_family_password_hash(
    db: Database,
    device_auth_token: str,
    parent_password_second_hash: str
) -> bool:
    """Update the family's parent password hash.
    
    Args:
        db: Database instance.
        device_auth_token: The device auth token to update.
        parent_password_second_hash: The parent password hash to store.
        
    Returns:
        True if updated, False if family not found.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE families SET parent_password_second_hash = ? WHERE device_auth_token = ?
        ''', (parent_password_second_hash, device_auth_token))
        
        conn.commit()
        return cursor.rowcount > 0


def update_family_parent_user_id(
    db: Database,
    device_auth_token: str,
    parent_user_id: str
) -> bool:
    """Update the family's parent user ID.
    
    Args:
        db: Database instance.
        device_auth_token: The device auth token to update.
        parent_user_id: The parent user ID to store.
        
    Returns:
        True if updated, False if family not found.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE families SET parent_user_id = ? WHERE device_auth_token = ?
        ''', (parent_user_id, device_auth_token))
        
        conn.commit()
        return cursor.rowcount > 0


def upsert_family_password_hash(
    db: Database,
    device_auth_token: str,
    parent_password_second_hash: str,
    mail: Optional[str] = None
) -> bool:
    """Upsert the family's parent password hash.
    
    This function handles both INSERT and UPDATE cases:
    - If the family record exists, it updates the hash
    - If the family record doesn't exist, it creates a new record
    
    This is needed because the family may be created on the server first,
    and the local database record may not exist yet.
    
    Args:
        db: Database instance.
        device_auth_token: The device auth token (primary key).
        parent_password_second_hash: The parent password hash to store.
        mail: Optional email address (uses placeholder if not provided).
        
    Returns:
        True if successful, False otherwise.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Try UPDATE first
        cursor.execute('''
            UPDATE families SET parent_password_second_hash = ? WHERE device_auth_token = ?
        ''', (parent_password_second_hash, device_auth_token))
        
        if cursor.rowcount > 0:
            conn.commit()
            logger.debug(
                "Parent password hash updated in existing family record",
                component="database",
                device_auth_token=device_auth_token[:8] + "..." if device_auth_token else None
            )
            return True
        
        # If no row was updated, try INSERT
        placeholder_mail = mail or "pending@unknown"
        cursor.execute('''
            INSERT INTO families (device_auth_token, mail, created_at, parent_password_second_hash)
            VALUES (?, ?, ?, ?)
        ''', (
            device_auth_token,
            placeholder_mail,
            datetime.now(timezone.utc).isoformat(),
            parent_password_second_hash
        ))
        
        conn.commit()
        logger.debug(
            "Parent password hash inserted in new family record",
            component="database",
            device_auth_token=device_auth_token[:8] + "..." if device_auth_token else None
        )
        return True


def clear_family_password_hash(db: Database, device_auth_token: str) -> bool:
    """Clear the family's parent password hash.
    
    Args:
        db: Database instance.
        device_auth_token: The device auth token to update.
        
    Returns:
        True if updated, False if family not found.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE families SET parent_password_second_hash = NULL WHERE device_auth_token = ?
        ''', (device_auth_token,))
        
        conn.commit()
        return cursor.rowcount > 0


def has_parent_password_hash(db: Database, device_auth_token: str) -> bool:
    """Check if a valid parent password hash exists for a device.
    
    Args:
        db: Database instance.
        device_auth_token: The device auth token to check.
        
    Returns:
        True if valid hash exists, False otherwise.
    """
    hash_value = get_parent_password_hash(db, device_auth_token)
    return hash_value is not None and validate_password_hash(hash_value)


# ============================================================================
# Sync State Operations
# ============================================================================

def save_sync_state(
    db: Database,
    device_auth_token: str,
    device_list_version: Optional[str],
    user_list_version: Optional[str]
) -> None:
    """Save sync state version numbers.
    
    This function preserves the next_sequence_number value by using an UPDATE
    statement instead of INSERT OR REPLACE. This prevents the sequence number
    from being reset when save_sync_state is called after increment_sequence_number.
    
    Args:
        db: Database instance.
        device_auth_token: The device auth token.
        device_list_version: Version string for device list.
        user_list_version: Version string for user list.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        current_time = int(datetime.now().timestamp() * 1000)
        
        # Check if sync state already exists for this device
        cursor.execute('SELECT 1 FROM sync_state WHERE device_auth_token = ?', (device_auth_token,))
        exists = cursor.fetchone() is not None
        
        if exists:
            # Update existing row, preserving next_sequence_number
            cursor.execute('''
                UPDATE sync_state
                SET device_list_version = ?,
                    user_list_version = ?,
                    last_sync_timestamp = ?,
                    last_sync_success = 1
                WHERE device_auth_token = ?
            ''', (
                device_list_version,
                user_list_version,
                current_time,
                device_auth_token
            ))
        else:
            # Insert new row with next_sequence_number = 0
            cursor.execute('''
                INSERT INTO sync_state
                (device_auth_token, device_list_version, user_list_version, last_sync_timestamp, last_sync_success, next_sequence_number)
                VALUES (?, ?, ?, ?, 1, 0)
            ''', (
                device_auth_token,
                device_list_version,
                user_list_version,
                current_time
            ))
        
        conn.commit()
        logger.debug(
            "Sync state saved",
            component="database",
            db_path=db.db_path,
            table_name="sync_state",
            device_auth_token=device_auth_token
        )


def get_sync_state(db: Database, device_auth_token: str) -> Optional[Dict[str, Any]]:
    """Get sync state for a device auth token.
    
    Args:
        db: Database instance.
        device_auth_token: The device auth token to look up.
        
    Returns:
        Sync state record or None if not found.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM sync_state WHERE device_auth_token = ?', (device_auth_token,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_next_sequence_number(db: Database, device_auth_token: str) -> int:
    """Get the next sequence number for a device auth token.
    
    Args:
        db: Database instance.
        device_auth_token: The device auth token to look up.
        
    Returns:
        The next sequence number (0 if no sync state exists).
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT next_sequence_number FROM sync_state WHERE device_auth_token = ?', (device_auth_token,))
        row = cursor.fetchone()
        
        if row and row[0] is not None:
            return row[0]
        return 0


def increment_sequence_number(db: Database, device_auth_token: str) -> int:
    """Increment and return the sequence number for a device auth token.
    
    Args:
        db: Database instance.
        device_auth_token: The device auth token to update.
        
    Returns:
        The new sequence number after incrementing.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Get current sequence number (default to 0 if not exists)
        cursor.execute('SELECT next_sequence_number FROM sync_state WHERE device_auth_token = ?', (device_auth_token,))
        row = cursor.fetchone()
        
        if row and row[0] is not None:
            current_seq = row[0]
        else:
            current_seq = 0
        
        new_seq = current_seq + 1
        
        # Update or insert the sequence number
        cursor.execute('''
            INSERT OR REPLACE INTO sync_state
            (device_auth_token, next_sequence_number)
            VALUES (?, ?)
        ''', (device_auth_token, new_seq))
        
        conn.commit()
        return new_seq


# ============================================================================
# Categories Operations
# ============================================================================

def save_categories(
    db: Database,
    device_auth_token: str,
    categories_data: List[Dict[str, Any]]
) -> None:
    """Save categories from ServerDataStatus to the database.
    
    Args:
        db: Database instance.
        device_auth_token: The device auth token.
        categories_data: List of category data from ServerDataStatus.categoryBase.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        current_time = int(datetime.now().timestamp() * 1000)
        
        for cat in categories_data:
            cursor.execute('''
                INSERT OR REPLACE INTO categories
                (id, device_auth_token, child_id, title, blocked_times, extra_time, extra_time_day,
                 temp_blocked, temp_block_time, version, parent_category_id,
                 block_all_notifications, time_warnings, sort_order, flags, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                cat.get('id'),
                device_auth_token,
                cat.get('childId'),
                cat.get('title'),
                cat.get('blockedTimes'),
                cat.get('extraTime', 0),
                cat.get('extraTimeDay', 0),
                cat.get('tempBlocked', 0),
                cat.get('tempBlockTime'),
                cat.get('version'),
                cat.get('parentCategoryId'),
                cat.get('blockAllNotifications', 0),
                cat.get('timeWarnings', 0),
                cat.get('sortOrder', 0),
                cat.get('flags', 0),
                current_time
            ))
        
        conn.commit()
        logger.debug(
            "Categories saved",
            component="database",
            db_path=db.db_path,
            table_name="categories",
            device_auth_token=device_auth_token,
            count=len(categories_data)
        )


def get_categories_by_device_auth_token(db: Database, device_auth_token: str) -> List[Dict[str, Any]]:
    """Get all categories for a device auth token.
    
    Args:
        db: Database instance.
        device_auth_token: The device auth token to look up.
        
    Returns:
        List of category records.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM categories WHERE device_auth_token = ?', (device_auth_token,))
        return [dict(row) for row in cursor.fetchall()]


# ============================================================================
# Connected Devices Operations
# ============================================================================

def save_connected_devices(
    db: Database,
    device_auth_token: str,
    device_ids: List[str]
) -> None:
    """Save connected devices list for a device auth token.
    
    Looks up device names from the devices table and stores them
    alongside device IDs in the connected_devices table.
    
    Args:
        db: Database instance.
        device_auth_token: The device auth token.
        device_ids: List of connected device IDs.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        current_time = int(datetime.now().timestamp() * 1000)
        
        # Get device names from devices table
        device_names = {}
        if device_ids:
            placeholders = ','.join('?' * len(device_ids))
            cursor.execute(f'SELECT id, name FROM devices WHERE id IN ({placeholders})', device_ids)
            for row in cursor.fetchall():
                device_names[row[0]] = row[1]
        
        # Clear existing entries for this device auth token
        cursor.execute('DELETE FROM connected_devices WHERE device_auth_token = ?', (device_auth_token,))
        
        # Insert new entries with names
        for device_id in device_ids:
            device_name = device_names.get(device_id)
            cursor.execute('''
                INSERT INTO connected_devices (device_auth_token, device_id, last_seen, name)
                VALUES (?, ?, ?, ?)
            ''', (device_auth_token, device_id, current_time, device_name))
        
        conn.commit()
        logger.debug(
            "Connected devices saved",
            component="database",
            db_path=db.db_path,
            table_name="connected_devices",
            device_auth_token=device_auth_token,
            count=len(device_ids)
        )


def get_connected_devices(db: Database, device_auth_token: str) -> List[Dict[str, Any]]:
    """Get connected devices for a device auth token with last_seen timestamps.
    
    Args:
        db: Database instance.
        device_auth_token: The device auth token to look up.
        
    Returns:
        List of connected device records with device_id, last_seen, and name.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT device_id, last_seen, name FROM connected_devices WHERE device_auth_token = ?', (device_auth_token,))
        return [dict(row) for row in cursor.fetchall()]


# ============================================================================
# Auth Token Retrieval for Session Persistence
# ============================================================================

def get_device_auth_tokens(db: Database) -> List[Dict[str, Any]]:
    """Get all device_auth_tokens from the database.
    
    Used for session persistence - retrieves stored device auth tokens
    that can be restored to the session on application startup.
    
    Args:
        db: Database instance.
        
    Returns:
        List of token records with token_type='device_auth_token',
        ordered by created_at descending (most recent first).
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM auth_tokens
            WHERE token_type = 'device_auth_token'
            ORDER BY created_at DESC
        ''')
        results = [dict(row) for row in cursor.fetchall()]
        logger.debug(
            "Device auth tokens retrieved",
            component="database",
            db_path=db.db_path,
            table_name="auth_tokens",
            count=len(results)
        )
        return results


def get_latest_device_auth_token(db: Database) -> Optional[str]:
    """Get the most recent device_auth_token from the database.
    
    Used for session persistence - retrieves the most recent device auth token
    that can be restored to the session on application startup.
    
    Args:
        db: Database instance.
        
    Returns:
        The most recent device_auth_token value, or None if no tokens exist.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT token_value FROM auth_tokens
            WHERE token_type = 'device_auth_token'
            ORDER BY created_at DESC
            LIMIT 1
        ''')
        row = cursor.fetchone()
        
        if row:
            return row[0]
        return None


def get_latest_own_device_id(db: Database) -> Optional[str]:
    """Get the most recent device ID from the devices table.
    
    Used for session persistence - retrieves the most recently created device ID
    that can be restored to the session on application startup.
    
    Args:
        db: Database instance.
        
    Returns:
        The most recently created device ID, or None if no devices exist.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id FROM devices
            ORDER BY created_at DESC
            LIMIT 1
        ''')
        row = cursor.fetchone()
        
        if row:
            return row[0]
        return None


def delete_all_device_auth_tokens(db: Database) -> int:
    """Delete all device_auth_token entries from the database.
    
    Used for clearing all auth tokens when logging out or when
    authentication fails.
    
    Args:
        db: Database instance.
        
    Returns:
        Number of tokens deleted.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM auth_tokens WHERE token_type = 'device_auth_token'")
        conn.commit()
        
        count = cursor.rowcount
        logger.info(
            "All device auth tokens deleted",
            component="database",
            db_path=db.db_path,
            table_name="auth_tokens",
            row_count=count
        )
        return count


# ============================================================================
# Database Factory
# ============================================================================

_db_instance: Optional[Database] = None


def get_database() -> Database:
    """Get the singleton database instance.
    
    Returns:
        Database instance.
    """
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
        _db_instance.init_db()
        logger.debug(
            "Database instance created",
            component="database",
            db_path=_db_instance.db_path
        )
    return _db_instance


def reset_database() -> None:
    """Reset the database instance (for testing)."""
    global _db_instance
    if _db_instance:
        logger.info(
            "Database reset",
            component="database",
            db_path=_db_instance.db_path
        )
        _db_instance.close()
    _db_instance = None


def clear_all_tables(db: Database) -> Dict[str, int]:
    """Clear all data from all tables (for fresh start).
    
    This is a convenience function that calls the Database.clear_all_tables() method.
    It deletes all records from all tables while preserving the schema.
    
    Args:
        db: Database instance.
        
    Returns:
        Dictionary with table names as keys and row counts deleted as values.
    """
    return db.clear_all_tables()