"""Sync protocol service for TimeLimit API.

This module provides the sync protocol logic for handling
push-actions and pull-status operations.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.security import calculate_hmac_sha256
from app.core.state import state_manager

logger = logging.getLogger(__name__)


class SyncService:
    """Sync protocol service for TimeLimit API.
    
    Handles the sync protocol including:
    - Action-based CRDT operations
    - Push actions (batch of 25)
    - Pull status (ClientDataStatus -> ServerDataStatus)
    - Integrity verification
    """
    
    def __init__(self, state: state_manager = None):
        """Initialize the sync service.
        
        Args:
            state: State manager instance. Uses global state_manager if not provided.
        """
        self.state = state or state_manager
    
    async def push_actions(
        self,
        device_auth_token: str,
        actions: List[Dict[str, Any]],
        second_hash: str = None
    ) -> Dict[str, Any]:
        """Push pending actions to the server.
        
        Args:
            device_auth_token: Device authentication token.
            actions: List of actions to push (batch of 25).
            second_hash: Second password hash for integrity verification.
            
        Returns:
            Response with shouldDoFullSync flag.
        """
        # Verify device auth token
        token_data = await self.state.get_device_auth_token(device_auth_token)
        if not token_data:
            raise ValueError("Invalid device auth token")
        
        device_id = token_data.get("device_id")
        family_id = token_data.get("family_id")
        
        logger.info(
            "Pushing actions",
            extra={
                "device_id": device_id,
                "family_id": family_id,
                "action_count": len(actions),
            }
        )
        
        # Process each action
        processed_count = 0
        for action in actions:
            try:
                # Verify integrity if second_hash is provided
                if second_hash and "integrity" in action:
                    expected_integrity = calculate_hmac_sha256(
                        second_hash,
                        action.get("sequenceNumber", 0),
                        device_id,
                        action.get("encodedAction", "")
                    )
                    if action.get("integrity") != expected_integrity:
                        logger.warning(
                            "Integrity mismatch for action",
                            extra={"sequence_number": action.get("sequenceNumber")}
                        )
                        continue
                
                # Store the action
                await self.state.add_pending_action(action)
                processed_count += 1
                
            except Exception as e:
                logger.error(
                    "Error processing action",
                    extra={
                        "sequence_number": action.get("sequenceNumber"),
                        "error": str(e),
                    }
                )
        
        # Determine if full sync is needed
        should_do_full_sync = processed_count < len(actions)
        
        logger.info(
            "Actions pushed successfully",
            extra={
                "device_id": device_id,
                "processed": processed_count,
                "total": len(actions),
                "should_do_full_sync": should_do_full_sync,
            }
        )
        
        return {
            "shouldDoFullSync": should_do_full_sync,
            "processedCount": processed_count,
            "totalCount": len(actions),
        }
    
    async def pull_status(
        self,
        device_auth_token: str,
        client_status: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Pull server status for the client.
        
        Args:
            device_auth_token: Device authentication token.
            client_status: Client's current sync status.
            
        Returns:
            ServerDataStatus with all family data.
        """
        # Verify device auth token
        token_data = await self.state.get_device_auth_token(device_auth_token)
        if not token_data:
            raise ValueError("Invalid device auth token")
        
        device_id = token_data.get("device_id")
        family_id = token_data.get("family_id")
        
        logger.info(
            "Pulling status",
            extra={
                "device_id": device_id,
                "family_id": family_id,
            }
        )
        
        # Get all family data
        family_data = await self.state.get_family(family_id)
        if not family_data:
            raise ValueError("Family not found")
        
        # Get users
        users = await self.state.get_users_by_family(family_id)
        users_dict = {u.get("id"): u for u in users}
        
        # Get devices
        devices = await self.state.get_devices_by_family(family_id)
        devices_dict = {d.get("deviceId"): d for d in devices}
        
        # Get categories
        categories = list(self.state._categories.values())
        
        # Get apps
        apps = []
        for device in devices:
            device_apps = await self.state.get_apps(device.get("deviceId"))
            if device_apps:
                apps.append({
                    "deviceId": device.get("deviceId"),
                    "version": "1",
                    "apps": device_apps,
                })
        
        # Get sync versions
        sync_versions = {}
        for entity_type in ["users", "devices", "categories", "apps", "rules", "tasks", "usedTimes"]:
            version = await self.state.get_sync_version(entity_type)
            if version:
                sync_versions[entity_type] = version
        
        # Build ServerDataStatus
        server_data = {
            "devices": {
                "v": sync_versions.get("devices", ""),
                "data": devices_dict,
            },
            "devices2": devices,
            "apps": apps,
            "rmCategories": [],
            "categoryBase": categories,
            "categoryApp": [],
            "usedTimes": [],
            "rules": [],
            "tasks": [],
            "users": {
                "v": sync_versions.get("users", ""),
                "data": users_dict,
            },
            "krq": [],
            "kr": [],
            "pings": [],
            "dh": {
                "v": "1",
                "k": "",
            },
            "u2f": {
                "v": "1",
                "d": [],
            },
            "fullVersion": 0,
            "message": "",
            "apiLevel": 1,
        }
        
        logger.info(
            "Status pulled successfully",
            extra={
                "device_id": device_id,
                "user_count": len(users_dict),
                "device_count": len(devices_dict),
                "category_count": len(categories),
            }
        )
        
        return server_data
    
    async def report_removed(
        self,
        device_auth_token: str
    ) -> Dict[str, Any]:
        """Report device as removed.
        
        Args:
            device_auth_token: Device authentication token.
            
        Returns:
            Response with status.
        """
        # Verify device auth token
        token_data = await self.state.get_device_auth_token(device_auth_token)
        if not token_data:
            raise ValueError("Invalid device auth token")
        
        device_id = token_data.get("device_id")
        family_id = token_data.get("family_id")
        
        logger.info(
            "Reporting device removed",
            extra={
                "device_id": device_id,
                "family_id": family_id,
            }
        )
        
        # Delete device
        await self.state.delete_device(device_id)
        
        # Delete device auth token
        await self.state.delete_device_auth_token(device_auth_token)
        
        return {"status": "ok"}
    
    async def is_device_removed(
        self,
        device_auth_token: str
    ) -> Dict[str, Any]:
        """Check if device was removed.
        
        Args:
            device_auth_token: Device authentication token.
            
        Returns:
            Response with isDeviceRemoved flag.
        """
        # Verify device auth token
        token_data = await self.state.get_device_auth_token(device_auth_token)
        if not token_data:
            # Token doesn't exist, device was removed
            return {"isDeviceRemoved": True}
        
        device_id = token_data.get("device_id")
        
        # Check if device still exists
        device = await self.state.get_device(device_id)
        is_removed = device is None
        
        logger.info(
            "Checking if device removed",
            extra={
                "device_id": device_id,
                "is_removed": is_removed,
            }
        )
        
        return {"isDeviceRemoved": is_removed}
    
    async def get_pending_actions(
        self,
        device_auth_token: str,
        limit: int = 25
    ) -> List[Dict[str, Any]]:
        """Get pending actions for a device.
        
        Args:
            device_auth_token: Device authentication token.
            limit: Maximum number of actions to return.
            
        Returns:
            List of pending actions.
        """
        # Verify device auth token
        token_data = await self.state.get_device_auth_token(device_auth_token)
        if not token_data:
            raise ValueError("Invalid device auth token")
        
        actions = await self.state.get_pending_actions(limit)
        return actions
    
    async def clear_pending_actions(
        self,
        device_auth_token: str
    ) -> None:
        """Clear pending actions for a device.
        
        Args:
            device_auth_token: Device authentication token.
        """
        # Verify device auth token
        token_data = await self.state.get_device_auth_token(device_auth_token)
        if not token_data:
            raise ValueError("Invalid device auth token")
        
        await self.state.clear_pending_actions()
        logger.info("Pending actions cleared")


# Global sync service instance
sync_service = SyncService()