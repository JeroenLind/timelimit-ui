"""Sync Manager module for dashboardV2 application.

This module provides the SyncManager class for orchestrating periodic sync
with the TimeLimit server. It handles:
- Pulling server status via the sync protocol
- Applying server data to the local database
- Tracking sync versions
- Broadcasting SSE events for real-time updates

Key change: Using device_auth_token as primary key instead of family_id,
matching the official Android app's approach where the server looks up
family from device using deviceAuthToken.
"""

import json
import queue
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from auth_client import AuthClient, APIResponse
from config import Config
from database import (
    Database, get_database,
    save_users, get_users_by_device_auth_token,
    save_sync_state, get_sync_state,
    save_categories, get_categories_by_device_auth_token,
    save_connected_devices, get_connected_devices
)
from middleware.request_logging import get_request_id
from utils.logging import get_logger

logger = get_logger(__name__)

# In-memory event queues for SSE (per device_auth_token)
_event_queues: Dict[str, queue.Queue] = {}


class SyncManager:
    """Manages periodic sync with the TimeLimit server.
    
    This class orchestrates the sync process:
    - Pulls server status via the sync protocol
    - Applies server data to the local database
    - Tracks sync versions
    - Broadcasts SSE events for real-time updates
    """
    
    def __init__(self, db: Database):
        """Initialize the sync manager.
        
        Args:
            db: Database instance for storing sync data.
        """
        self.db = db
        self._lock = threading.RLock()
        self._config = Config()
    
    def do_sync(
        self,
        device_auth_token: str,
        server_url: str
    ) -> bool:
        """Execute one sync round: pull status, apply to database.
        
        Args:
            device_auth_token: Device auth token for authentication.
            server_url: TimeLimit server URL.
            
        Returns:
            True if sync was successful, False otherwise.
        """
        request_id = get_request_id()
        
        logger.info(
            "Starting sync",
            request_id=request_id,
            device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
            server_url=server_url
        )
        
        try:
            # Create auth client
            client = AuthClient(base_url=server_url)
            
            # Get current sync state from database
            sync_state = get_sync_state(self.db, device_auth_token)
            client_status = self._build_client_data_status(sync_state)
            
            # Pull server status
            response = client.pull_status(device_auth_token, client_status)
            
            if not response.success:
                logger.warning(
                    "Sync failed: pull_status unsuccessful",
                    request_id=request_id,
                    error_code=response.error_code,
                    error_message=response.error_message
                )
                client.close()
                return False
            
            # Apply server data to database
            self._apply_server_data_status(response.data, device_auth_token)
            
            # Update sync state
            self._update_sync_state(response.data, device_auth_token)
            
            # Close client
            client.close()
            
            # Broadcast SSE event
            self._broadcast_sync_complete(device_auth_token, response.data)
            
            logger.info(
                "Sync completed successfully",
                request_id=request_id,
                device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Sync error",
                request_id=request_id,
                error=str(e),
                error_code="sync_error"
            )
            return False
    
    def _build_client_data_status(
        self,
        sync_state: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build ClientDataStatus from stored sync state.
        
        Args:
            sync_state: Current sync state from database.
            
        Returns:
            ClientDataStatus dictionary for the pull-status request.
        """
        if sync_state is None:
            # No prior sync state - send empty status for full sync
            # Format matches Android app's ClientDataStatus.empty
            return {
                "clientLevel": 7,
                "devices": "",
                "users": "",
                "apps": {},
                "categories": {}
            }
        
        # Build from stored state
        # Format matches Android app's ClientDataStatus.serialize()
        # devices and users are strings (empty if no version), optional fields omitted when empty
        device_version = sync_state.get('device_list_version')
        user_version = sync_state.get('user_list_version')
        
        result = {
            "clientLevel": 7,
            "devices": device_version if device_version is not None else "",
            "users": user_version if user_version is not None else "",
            "apps": {},
            "categories": {}
        }
        
        return result
    
    def _apply_server_data_status(
        self,
        server_data: Dict[str, Any],
        device_auth_token: str
    ) -> None:
        """Apply ServerDataStatus to local database.
        
        Args:
            server_data: ServerDataStatus from pull-status response.
            device_auth_token: Device auth token for the data.
        """
        request_id = get_request_id()
        
        # Store devices
        if 'devices' in server_data and 'data' in server_data['devices']:
            devices = server_data['devices']['data']
            for device in devices:
                self._save_device_from_server(device, device_auth_token)
            logger.debug(
                "Devices applied from sync",
                request_id=request_id,
                device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
                count=len(devices)
            )
        
        # Store users
        if 'users' in server_data and 'data' in server_data['users']:
            users = server_data['users']['data']
            save_users(self.db, device_auth_token, users)
            logger.debug(
                "Users applied from sync",
                request_id=request_id,
                device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
                count=len(users)
            )
        
        # Store categories
        if 'categoryBase' in server_data:
            categories = server_data['categoryBase']
            save_categories(self.db, device_auth_token, categories)
            logger.debug(
                "Categories applied from sync",
                request_id=request_id,
                device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
                count=len(categories)
            )
        
        # Store connected devices (from pings if available)
        # The 'pings' field contains ServerPing objects with deviceId, token, and type
        # These represent devices that have recently communicated with the current device
        if 'pings' in server_data:
            pings = server_data['pings']
            device_ids = [p.get('deviceId') for p in pings if p.get('deviceId')]
            save_connected_devices(self.db, device_auth_token, device_ids)
            logger.debug(
                "Connected devices applied from sync",
                request_id=request_id,
                device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
                count=len(device_ids)
            )
    
    def _save_device_from_server(
        self,
        device_data: Dict[str, Any],
        device_auth_token: str
    ) -> None:
        """Save a device from server data to the database.
        
        Args:
            device_data: ServerDeviceData from server.
            device_auth_token: Device auth token for the device.
        """
        from database import create_device
        
        create_device(
            db=self.db,
            device_id=device_data.get('deviceId'),
            device_auth_token=device_auth_token,
            name=device_data.get('name'),
            model=device_data.get('model'),
            current_user_id=device_data.get('currentUserId'),
            current_protection_level=device_data.get('currentProtectionLevel', 0),
            highest_protection_level=device_data.get('highestProtectionLevel', 0),
            current_app_version=str(device_data.get('currentAppVersion', 0)),
            highest_app_version=str(device_data.get('highestAppVersion', 0)),
            public_key=device_data.get('publicKey'),
            platform_type=device_data.get('platformType'),
            platform_level=device_data.get('platformLevel', 0)
        )
    
    def _update_sync_state(
        self,
        server_data: Dict[str, Any],
        device_auth_token: str
    ) -> None:
        """Update sync state version numbers.
        
        Args:
            server_data: ServerDataStatus from pull-status response.
            device_auth_token: Device auth token for the sync state.
        """
        device_version = server_data.get('devices', {}).get('version')
        user_version = server_data.get('users', {}).get('version')
        
        save_sync_state(self.db, device_auth_token, device_version, user_version)
        
        logger.debug(
            "Sync state updated",
            device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
            device_version=device_version,
            user_version=user_version
        )
    
    def _broadcast_sync_complete(
        self,
        device_auth_token: str,
        server_data: Dict[str, Any]
    ) -> None:
        """Broadcast sync complete event via SSE.
        
        Args:
            device_auth_token: Device auth token for the event.
            server_data: ServerDataStatus from pull-status response.
        """
        # Get counts
        users_count = 0
        devices_count = 0
        
        if 'users' in server_data and 'data' in server_data['users']:
            users_count = len(server_data['users']['data'])
        
        if 'devices' in server_data and 'data' in server_data['devices']:
            devices_count = len(server_data['devices']['data'])
        
        # Get event queue for this device_auth_token
        q = _event_queues.setdefault(device_auth_token, queue.Queue())
        
        # Put event in queue
        event = {
            'type': 'sync_complete',
            'data': {
                'users_count': users_count,
                'devices_count': devices_count
            }
        }
        q.put(event)
        
        logger.debug(
            "Sync complete event broadcast",
            device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
            users_count=users_count,
            devices_count=devices_count
        )


def get_event_queue(device_auth_token: str) -> queue.Queue:
    """Get the event queue for a device auth token.
    
    Args:
        device_auth_token: Device auth token to get queue for.
        
    Returns:
        Queue for SSE events.
    """
    return _event_queues.setdefault(device_auth_token, queue.Queue())


def create_sync_manager(db: Optional[Database] = None) -> SyncManager:
    """Create a SyncManager instance.
    
    Args:
        db: Optional database instance. Uses global if not provided.
        
    Returns:
        SyncManager instance.
    """
    if db is None:
        db = get_database()
    return SyncManager(db)


# ============================================================================
# Background Sync Job
# ============================================================================

def run_background_sync(
    device_auth_token: str,
    server_url: str
) -> None:
    """Run a background sync job.
    
    This function is designed to be called by APScheduler.
    
    Args:
        device_auth_token: Device auth token for authentication.
        server_url: TimeLimit server URL.
    """
    request_id = get_request_id()
    
    logger.info(
        "Background sync job started",
        request_id=request_id,
        device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
        server_url=server_url
    )
    
    try:
        db = get_database()
        manager = SyncManager(db)
        success = manager.do_sync(device_auth_token, server_url)
        
        if success:
            logger.info(
                "Background sync job completed successfully",
                request_id=request_id,
                device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None
            )
        else:
            logger.warning(
                "Background sync job failed",
                request_id=request_id,
                device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None
            )
    except Exception as e:
        logger.error(
            "Background sync job error",
            request_id=request_id,
            error=str(e),
            error_code="background_sync_error"
        )


# ============================================================================
# Sync Credentials Storage
# ============================================================================

def store_sync_credentials(
    db: Database,
    device_auth_token: str
) -> None:
    """Store sync credentials for background jobs.
    
    Args:
        db: Database instance.
        device_auth_token: Device auth token.
    """
    from database import store_auth_token
    
    store_auth_token(
        db=db,
        token_type='sync_device_auth_token',
        token_value=device_auth_token,
        device_auth_token=device_auth_token
    )
    
    logger.info(
        "Sync credentials stored",
        device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None
    )


def get_sync_credentials(db: Database, device_auth_token: str) -> Optional[str]:
    """Get sync credentials for a device auth token.
    
    Args:
        db: Database instance.
        device_auth_token: Device auth token to look up.
        
    Returns:
        Device auth token or None if not found.
    """
    from database import get_auth_token
    
    # Look up the token by its value
    token_record = get_auth_token(db, device_auth_token)
    
    if token_record:
        return device_auth_token
    return None