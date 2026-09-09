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
    save_connected_devices, get_connected_devices,
    update_device_app_version,
    get_next_sequence_number, increment_sequence_number,
    create_device, get_device, delete_auth_token,
    update_family_salt, remove_stale_devices
)
from middleware.request_logging import get_request_id
from utils.logging import get_logger
from utils.audit_log import log_stale_device_removal
from key_manager import get_or_create_signing_key

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
        server_url: str,
        own_device_id: Optional[str] = None
    ) -> bool:
        """Execute one sync round: pull status, apply to database.
        
        Args:
            device_auth_token: Device auth token for authentication.
            server_url: TimeLimit server URL.
            own_device_id: Optional own device ID for updating app version.
            
        Returns:
            True if sync was successful, False otherwise.
        """
        request_id = get_request_id()
        
        logger.info(
            "Starting sync",
            request_id=request_id,
            device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
            server_url=server_url,
            has_own_device_id=own_device_id is not None
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
                # Check if this is an authentication error (401 Unauthorized)
                # If so, clear the auth token from the database
                if response.status_code == 401:
                    logger.warning(
                        "Sync failed with 401 Unauthorized - clearing auth token",
                        request_id=request_id,
                        device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
                        error_code=response.error_code,
                        error_message=response.error_message
                    )
                    # Clear the auth token from the database
                    try:
                        delete_auth_token(self.db, device_auth_token)
                        logger.info(
                            "Auth token cleared from database due to 401 error",
                            request_id=request_id,
                            device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None
                        )
                    except Exception as e:
                        logger.warning(
                            "Failed to clear auth token from database",
                            request_id=request_id,
                            error=str(e)
                        )
                
                logger.warning(
                    "Sync failed: pull_status unsuccessful",
                    request_id=request_id,
                    error_code=response.error_code,
                    error_message=response.error_message
                )
                client.close()
                return False
            
            # Push app version action to server if own_device_id is provided
            # This ensures the server knows the dashboard's app version
            if own_device_id:
                app_version = int(self._config.APP_VERSION)
                if app_version != 0:
                    self._push_app_version_action(
                        device_auth_token=device_auth_token,
                        server_url=server_url,
                        app_version=app_version
                    )
            
            # Apply server data to database
            self._apply_server_data_status(response.data, device_auth_token, own_device_id)
            
            # Update sync state
            self._update_sync_state(response.data, device_auth_token)
            
            # Close client
            client.close()
            
            # Update own device's app version if own_device_id is provided
            # This ensures the dashboard reports the same version as the official app
            if own_device_id:
                app_version = str(self._config.APP_VERSION)
                if app_version != '0':
                    updated = update_device_app_version(
                        db=self.db,
                        device_id=own_device_id,
                        current_app_version=app_version,
                        highest_app_version=app_version
                    )
                    if updated:
                        logger.info(
                            "Updated own device app version after sync",
                            request_id=request_id,
                            device_id=own_device_id,
                            app_version=app_version
                        )
            
            # Add own device to connected devices list if own_device_id is provided
            # This ensures the dashboard appears in the connected devices section
            # matching the behavior of the official Android app
            if own_device_id:
                self._add_own_device_to_connected_devices(
                    device_auth_token=device_auth_token,
                    own_device_id=own_device_id
                )
            
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
        device_auth_token: str,
        own_device_id: Optional[str] = None
    ) -> None:
        """Apply ServerDataStatus to local database.
        
        Args:
            server_data: ServerDataStatus from pull-status response.
            device_auth_token: Device auth token for the data.
            own_device_id: Optional dashboard's own device ID to exclude from stale removal.
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
        
        # Remove stale devices (devices that exist locally but not on server)
        # Get the list of server device IDs
        server_device_ids = []
        if 'devices' in server_data and 'data' in server_data['devices']:
            server_device_ids = [d.get('id') for d in server_data['devices']['data'] if d.get('id')]
        
        # Remove stale devices and log the removal
        removed_count, removed_device_ids = remove_stale_devices(
            self.db, device_auth_token, server_device_ids, own_device_id
        )
        if removed_count > 0:
            logger.info(
                "Removed stale devices during sync",
                request_id=request_id,
                device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
                removed_count=removed_count,
                removed_device_ids=removed_device_ids
            )
            # Log to audit log for verification
            log_stale_device_removal(
                device_auth_token=device_auth_token,
                removed_device_ids=removed_device_ids,
                own_device_id=own_device_id,
                request_id=request_id
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
            
            # Update family record with salt from parent user (if available)
            # The parent user's second_password_salt is needed for password hash regeneration
            for user in users:
                if user.get('type') == 'parent' and user.get('secondPasswordSalt'):
                    salt = user.get('secondPasswordSalt')
                    if update_family_salt(self.db, device_auth_token, salt):
                        logger.debug(
                            "Family salt updated from sync",
                            request_id=request_id,
                            device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None
                        )
                    break
        
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
    
    def _add_own_device_to_connected_devices(
        self,
        device_auth_token: str,
        own_device_id: str
    ) -> None:
        """Add the dashboard's own device ID to the connected devices list.
        
        This ensures the dashboard appears in the connected devices section,
        matching the behavior of the official Android app.
        
        Also ensures the dashboard's device is registered in the devices table
        with a friendly name for display in the connected devices list.
        
        Generates a Curve25519 signing key for the dashboard device if one
        doesn't exist, and stores the public key in the device record.
        
        Args:
            device_auth_token: Device auth token for the data.
            own_device_id: The dashboard's own device ID.
        """
        from config import Config
        request_id = get_request_id()
        
        # Get or create the dashboard's signing key (Curve25519 key pair)
        # The private key is stored persistently, the public key goes in the device record
        persistence_dir = self._config.PERSISTENCE_DIR
        _, dashboard_public_key = get_or_create_signing_key(persistence_dir)
        
        # Ensure the dashboard's device is registered in the devices table
        # with a friendly name for display in the connected devices list
        # This must happen regardless of whether the device is already in
        # the connected devices list (it may have been added in a previous sync)
        existing_device = get_device(self.db, own_device_id)
        device_was_created = False
        
        # Preserve ALL existing device fields when updating the device record.
        # create_device uses INSERT OR REPLACE which overwrites the entire row,
        # so we must pass existing values to avoid losing data that was set
        # by _save_device_from_server() and update_device_app_version() earlier
        # in the do_sync() flow (e.g., model, current_user_id, app version, etc.)
        #
        # IMPORTANT: Preserve the device name from the server if it exists.
        # The name was set by _save_device_from_server() during sync and represents
        # the user's chosen device name during family login. Only use the default
        # "Dashboard" name if no name exists yet.
        if existing_device:
            # Use existing name from server if available, otherwise use default
            device_name = existing_device.get('name')
            if not device_name:
                device_name = Config.DASHBOARD_DEVICE_NAME
            
            create_device(
                db=self.db,
                device_id=own_device_id,
                device_auth_token=device_auth_token,
                name=device_name,
                model=existing_device.get('model'),
                current_user_id=existing_device.get('current_user_id'),
                current_protection_level=existing_device.get('current_protection_level', 0),
                highest_protection_level=existing_device.get('highest_protection_level', 0),
                current_app_version=existing_device.get('current_app_version'),
                highest_app_version=existing_device.get('highest_app_version'),
                public_key=existing_device.get('public_key') or dashboard_public_key,
                platform_type='dashboard',
                platform_level=1
            )
            logger.info(
                "Updated dashboard device record with platform info",
                request_id=request_id,
                device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
                own_device_id=own_device_id,
                platform_type='dashboard',
                platform_level=1,
                has_signing_key=bool(existing_device.get('public_key')),
                device_name=device_name
            )
        else:
            # No existing device record - create a new one with platform info
            create_device(
                db=self.db,
                device_id=own_device_id,
                device_auth_token=device_auth_token,
                name=Config.DASHBOARD_DEVICE_NAME,
                public_key=dashboard_public_key,
                platform_type='dashboard',
                platform_level=1
            )
            device_was_created = True
            logger.info(
                "Created dashboard device record",
                request_id=request_id,
                device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
                own_device_id=own_device_id,
                name=Config.DASHBOARD_DEVICE_NAME,
                platform_type='dashboard',
                platform_level=1,
                has_signing_key=True
            )
        
        # Get existing connected devices
        existing_devices = get_connected_devices(self.db, device_auth_token)
        existing_device_ids = [d.get('device_id') for d in existing_devices]
        
        # Add own device ID if not already present
        if own_device_id not in existing_device_ids:
            existing_device_ids.append(own_device_id)
            save_connected_devices(self.db, device_auth_token, existing_device_ids)
            logger.info(
                "Added own device to connected devices list",
                request_id=request_id,
                device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
                own_device_id=own_device_id
            )
        else:
            # Device is already in the connected devices list
            # Always re-save to ensure the name is updated from the devices table.
            # This handles the case where the device was added in a previous sync
            # (before the device record was created with a name), so the connected_devices
            # entry has name: None. When the device record is created with a name,
            # we need to update the connected_devices list.
            save_connected_devices(self.db, device_auth_token, existing_device_ids)
            device_record = get_device(self.db, own_device_id)
            if device_record and device_record.get('name'):
                logger.info(
                    "Updated connected devices with dashboard device name",
                    request_id=request_id,
                    device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
                    own_device_id=own_device_id,
                    device_name=device_record.get('name')
                )
            else:
                logger.debug(
                    "Own device already in connected devices list (name may be None)",
                    request_id=request_id,
                    device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
                    own_device_id=own_device_id
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
    
    def _build_update_device_status_action(self, app_version: int) -> Dict[str, Any]:
        """Build an UpdateDeviceStatusAction for pushing app version to server.
        
        This action is used to report the dashboard's app version to the server,
        matching the behavior of the official Android app.
        
        Args:
            app_version: The app version code to report.
            
        Returns:
            Dictionary with the action data for push_actions.
        """
        # Build the encoded action JSON
        # Format: {"type":"UPDATE_DEVICE_STATUS","appVersion":226}
        encoded_action = json.dumps({
            "type": "UPDATE_DEVICE_STATUS",
            "appVersion": app_version
        })
        
        return {
            "encodedAction": encoded_action,
            "sequenceNumber": 0,  # Will be updated by push_app_version_action
            "integrity": "",
            "type": "appLogic",
            "userId": ""
        }
    
    def _push_app_version_action(
        self,
        device_auth_token: str,
        server_url: str,
        app_version: int
    ) -> bool:
        """Push the app version action to the server.
        
        This sends an UpdateDeviceStatusAction to the server to report
        the dashboard's app version, matching the official Android app's behavior.
        
        Args:
            device_auth_token: Device auth token for authentication.
            server_url: TimeLimit server URL.
            app_version: The app version code to report.
            
        Returns:
            True if the action was pushed successfully, False otherwise.
        """
        request_id = get_request_id()
        
        try:
            # Get the next sequence number
            next_seq = get_next_sequence_number(self.db, device_auth_token)
            
            # Build the action
            action = self._build_update_device_status_action(app_version)
            action["sequenceNumber"] = next_seq
            
            # Create auth client and push the action
            client = AuthClient(base_url=server_url)
            response = client.push_actions(device_auth_token, [action])
            client.close()
            
            if response.success:
                # Increment the sequence number after successful push
                increment_sequence_number(self.db, device_auth_token)
                
                logger.info(
                    "App version action pushed successfully",
                    request_id=request_id,
                    device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
                    app_version=app_version,
                    sequence_number=next_seq
                )
                return True
            else:
                logger.warning(
                    "Failed to push app version action",
                    request_id=request_id,
                    error_code=response.error_code,
                    error_message=response.error_message
                )
                return False
                
        except Exception as e:
            logger.error(
                "Error pushing app version action",
                request_id=request_id,
                error=str(e),
                error_code="push_app_version_error"
            )
            return False


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
    server_url: str,
    own_device_id: Optional[str] = None
) -> None:
    """Run a background sync job.
    
    This function is designed to be called by APScheduler.
    
    Args:
        device_auth_token: Device auth token for authentication.
        server_url: TimeLimit server URL.
        own_device_id: Optional own device ID for device registration.
    """
    request_id = get_request_id()
    
    logger.info(
        "Background sync job started",
        request_id=request_id,
        device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
        server_url=server_url,
        has_own_device_id=own_device_id is not None
    )
    
    try:
        db = get_database()
        manager = SyncManager(db)
        success = manager.do_sync(device_auth_token, server_url, own_device_id)
        
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
        token_value=device_auth_token
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