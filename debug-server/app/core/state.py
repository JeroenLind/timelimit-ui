"""In-memory state management for the debug server.

This module provides thread-safe in-memory state management using asyncio.Lock
for concurrent access. It manages:
- Families (family_id -> family data)
- Users (user_id -> user data)
- Devices (device_id -> device data)
- Categories (category_id -> category data)
- Auth tokens (mail_login_token -> {mail, code}, mail_auth_token -> {mail, family_id}, device_auth_token -> {device_id, family_id})
- Add-device tokens (token -> {device_id, parent_id, expires_at})
- Pending actions (sequence_number -> action)
- Sync versions (per entity type)
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class StateManager:
    """Thread-safe in-memory state manager for the debug server."""

    def __init__(self):
        self._lock = asyncio.Lock()

        # Entity stores
        self._families: Dict[str, Dict[str, Any]] = {}
        self._users: Dict[str, Dict[str, Any]] = {}
        self._devices: Dict[str, Dict[str, Any]] = {}
        self._categories: Dict[str, Dict[str, Any]] = {}
        self._apps: Dict[str, List[str]] = {}

        # Auth token stores
        self._mail_login_tokens: Dict[str, Dict[str, Any]] = {}
        self._mail_auth_tokens: Dict[str, Dict[str, Any]] = {}
        self._device_auth_tokens: Dict[str, Dict[str, Any]] = {}

        # Add-device tokens
        self._add_device_tokens: Dict[str, Dict[str, Any]] = {}

        # Pending actions
        self._pending_actions: Dict[int, Dict[str, Any]] = {}

        # Sync versions
        self._sync_versions: Dict[str, str] = {}

        # Sequence number counter
        self._sequence_counter = 0

        # Active WebSocket connections
        self._active_connections: Set[str] = set()

    async def acquire_lock(self) -> None:
        """Acquire the state lock."""
        await self._lock.acquire()

    def release_lock(self) -> None:
        """Release the state lock."""
        self._lock.release()

    async def __aenter__(self):
        """Async context manager entry."""
        await self._lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        self._lock.release()

    # ========================================================================
    # Family Management
    # ========================================================================

    async def create_family(self, family_id: str, family_data: Dict[str, Any]) -> None:
        """Create a new family.

        Args:
            family_id: The family ID.
            family_data: The family data.
        """
        async with self:
            self._families[family_id] = family_data
            logger.info("Family created", extra={"family_id": family_id})

    async def get_family(self, family_id: str) -> Optional[Dict[str, Any]]:
        """Get a family by ID.

        Args:
            family_id: The family ID.

        Returns:
            The family data, or None if not found.
        """
        async with self:
            return self._families.get(family_id)

    async def update_family(self, family_id: str, family_data: Dict[str, Any]) -> bool:
        """Update a family.

        Args:
            family_id: The family ID.
            family_data: The updated family data.

        Returns:
            True if the family was updated, False if not found.
        """
        async with self:
            if family_id not in self._families:
                return False
            self._families[family_id].update(family_data)
            return True

    async def delete_family(self, family_id: str) -> bool:
        """Delete a family.

        Args:
            family_id: The family ID.

        Returns:
            True if the family was deleted, False if not found.
        """
        async with self:
            if family_id not in self._families:
                return False
            del self._families[family_id]
            logger.info("Family deleted", extra={"family_id": family_id})
            return True

    async def list_families(self) -> List[str]:
        """List all family IDs.

        Returns:
            List of family IDs.
        """
        async with self:
            return list(self._families.keys())

    async def get_family_by_mail(self, mail: str) -> Optional[Dict[str, Any]]:
        """Get a family by mail address.

        Args:
            mail: The email address to search for.

        Returns:
            The family data, or None if not found.
        """
        async with self:
            for family_data in self._families.values():
                if family_data.get("mail") == mail:
                    return family_data
            return None

    # ========================================================================
    # User Management
    # ========================================================================

    async def create_user(self, user_id: str, user_data: Dict[str, Any]) -> None:
        """Create a new user.

        Args:
            user_id: The user ID.
            user_data: The user data.
        """
        async with self:
            self._users[user_id] = user_data
            logger.info("User created", extra={"user_id": user_id})

    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get a user by ID.

        Args:
            user_id: The user ID.

        Returns:
            The user data, or None if not found.
        """
        async with self:
            return self._users.get(user_id)

    async def update_user(self, user_id: str, user_data: Dict[str, Any]) -> bool:
        """Update a user.

        Args:
            user_id: The user ID.
            user_data: The updated user data.

        Returns:
            True if the user was updated, False if not found.
        """
        async with self:
            if user_id not in self._users:
                return False
            self._users[user_id].update(user_data)
            return True

    async def delete_user(self, user_id: str) -> bool:
        """Delete a user.

        Args:
            user_id: The user ID.

        Returns:
            True if the user was deleted, False if not found.
        """
        async with self:
            if user_id not in self._users:
                return False
            del self._users[user_id]
            logger.info("User deleted", extra={"user_id": user_id})
            return True

    async def get_users_by_family(self, family_id: str) -> List[Dict[str, Any]]:
        """Get all users in a family.

        Args:
            family_id: The family ID.

        Returns:
            List of user data.
        """
        async with self:
            return [
                user for user in self._users.values()
                if user.get("family_id") == family_id
            ]

    # ========================================================================
    # Device Management
    # ========================================================================

    async def create_device(self, device_id: str, device_data: Dict[str, Any]) -> None:
        """Create a new device.

        Args:
            device_id: The device ID.
            device_data: The device data.
        """
        async with self:
            self._devices[device_id] = device_data
            logger.info("Device created", extra={"device_id": device_id})

    async def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get a device by ID.

        Args:
            device_id: The device ID.

        Returns:
            The device data, or None if not found.
        """
        async with self:
            return self._devices.get(device_id)

    async def update_device(self, device_id: str, device_data: Dict[str, Any]) -> bool:
        """Update a device.

        Args:
            device_id: The device ID.
            device_data: The updated device data.

        Returns:
            True if the device was updated, False if not found.
        """
        async with self:
            if device_id not in self._devices:
                return False
            self._devices[device_id].update(device_data)
            return True

    async def delete_device(self, device_id: str) -> bool:
        """Delete a device.

        Args:
            device_id: The device ID.

        Returns:
            True if the device was deleted, False if not found.
        """
        async with self:
            if device_id not in self._devices:
                return False
            del self._devices[device_id]
            logger.info("Device deleted", extra={"device_id": device_id})
            return True

    async def get_devices_by_family(self, family_id: str) -> List[Dict[str, Any]]:
        """Get all devices in a family.

        Args:
            family_id: The family ID.

        Returns:
            List of device data.
        """
        async with self:
            return [
                device for device in self._devices.values()
                if device.get("family_id") == family_id
            ]

    # ========================================================================
    # Category Management
    # ========================================================================

    async def create_category(self, category_id: str, category_data: Dict[str, Any]) -> None:
        """Create a new category.

        Args:
            category_id: The category ID.
            category_data: The category data.
        """
        async with self:
            self._categories[category_id] = category_data
            logger.info("Category created", extra={"category_id": category_id})

    async def get_category(self, category_id: str) -> Optional[Dict[str, Any]]:
        """Get a category by ID.

        Args:
            category_id: The category ID.

        Returns:
            The category data, or None if not found.
        """
        async with self:
            return self._categories.get(category_id)

    async def update_category(self, category_id: str, category_data: Dict[str, Any]) -> bool:
        """Update a category.

        Args:
            category_id: The category ID.
            category_data: The updated category data.

        Returns:
            True if the category was updated, False if not found.
        """
        async with self:
            if category_id not in self._categories:
                return False
            self._categories[category_id].update(category_data)
            return True

    async def delete_category(self, category_id: str) -> bool:
        """Delete a category.

        Args:
            category_id: The category ID.

        Returns:
            True if the category was deleted, False if not found.
        """
        async with self:
            if category_id not in self._categories:
                return False
            del self._categories[category_id]
            logger.info("Category deleted", extra={"category_id": category_id})
            return True

    async def get_categories_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all categories for a user.

        Args:
            user_id: The user ID.

        Returns:
            List of category data.
        """
        async with self:
            return [
                category for category in self._categories.values()
                if category.get("child_id") == user_id
            ]

    # ========================================================================
    # Auth Token Management
    # ========================================================================

    async def store_mail_login_token(
        self,
        token: str,
        mail: str,
        code: str,
        expires_at: Optional[datetime] = None
    ) -> None:
        """Store a mail login token.

        Args:
            token: The mail login token.
            mail: The email address.
            code: The verification code.
            expires_at: Optional expiration time.
        """
        async with self:
            self._mail_login_tokens[token] = {
                "mail": mail,
                "code": code,
                "created_at": datetime.now(timezone.utc),
                "expires_at": expires_at or datetime.now(timezone.utc) + timedelta(minutes=10),
            }
            logger.info("Mail login token stored", extra={"token": token[:8] + "..."})

    async def get_mail_login_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Get a mail login token.

        Args:
            token: The mail login token.

        Returns:
            The token data, or None if not found or expired.
        """
        async with self:
            data = self._mail_login_tokens.get(token)
            if data is None:
                return None

            if data.get("expires_at") and data["expires_at"] < datetime.now(timezone.utc):
                del self._mail_login_tokens[token]
                return None

            return data

    async def delete_mail_login_token(self, token: str) -> bool:
        """Delete a mail login token.

        Args:
            token: The mail login token.

        Returns:
            True if deleted, False if not found.
        """
        async with self:
            if token in self._mail_login_tokens:
                del self._mail_login_tokens[token]
                return True
            return False

    async def store_mail_auth_token(
        self,
        token: str,
        mail: str,
        family_id: str
    ) -> None:
        """Store a mail auth token.

        Args:
            token: The mail auth token.
            mail: The email address.
            family_id: The family ID.
        """
        async with self:
            self._mail_auth_tokens[token] = {
                "mail": mail,
                "family_id": family_id,
                "created_at": datetime.now(timezone.utc),
            }
            logger.info("Mail auth token stored", extra={"token": token[:8] + "..."})

    async def get_mail_auth_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Get a mail auth token.

        Args:
            token: The mail auth token.

        Returns:
            The token data, or None if not found.
        """
        async with self:
            return self._mail_auth_tokens.get(token)

    async def store_device_auth_token(
        self,
        token: str,
        device_id: str,
        family_id: str
    ) -> None:
        """Store a device auth token.

        Args:
            token: The device auth token.
            device_id: The device ID.
            family_id: The family ID.
        """
        async with self:
            self._device_auth_tokens[token] = {
                "device_id": device_id,
                "family_id": family_id,
                "created_at": datetime.now(timezone.utc),
            }
            logger.info("Device auth token stored", extra={"token": token[:8] + "..."})

    async def get_device_auth_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Get a device auth token.

        Args:
            token: The device auth token.

        Returns:
            The token data, or None if not found.
        """
        async with self:
            return self._device_auth_tokens.get(token)

    async def delete_device_auth_token(self, token: str) -> bool:
        """Delete a device auth token.

        Args:
            token: The device auth token.

        Returns:
            True if deleted, False if not found.
        """
        async with self:
            if token in self._device_auth_tokens:
                del self._device_auth_tokens[token]
                return True
            return False

    # ========================================================================
    # Add-Device Token Management
    # ========================================================================

    async def create_add_device_token(
        self,
        token: str,
        device_id: str,
        parent_id: str,
        expires_at: Optional[datetime] = None
    ) -> None:
        """Create an add-device token.

        Args:
            token: The token string.
            device_id: The device ID.
            parent_id: The parent user ID.
            expires_at: Optional expiration time.
        """
        async with self:
            self._add_device_tokens[token] = {
                "device_id": device_id,
                "parent_id": parent_id,
                "created_at": datetime.now(timezone.utc),
                "expires_at": expires_at or datetime.now(timezone.utc) + timedelta(hours=24),
            }
            logger.info("Add-device token created", extra={"token": token[:8] + "..."})

    async def get_add_device_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Get an add-device token.

        Args:
            token: The token string.

        Returns:
            The token data, or None if not found or expired.
        """
        async with self:
            data = self._add_device_tokens.get(token)
            if data is None:
                return None

            if data.get("expires_at") and data["expires_at"] < datetime.now(timezone.utc):
                del self._add_device_tokens[token]
                return None

            return data

    async def delete_add_device_token(self, token: str) -> bool:
        """Delete an add-device token.

        Args:
            token: The token string.

        Returns:
            True if deleted, False if not found.
        """
        async with self:
            if token in self._add_device_tokens:
                del self._add_device_tokens[token]
                return True
            return False

    # ========================================================================
    # Pending Actions
    # ========================================================================

    async def add_pending_action(self, action: Dict[str, Any]) -> int:
        """Add a pending action.

        Args:
            action: The action data.

        Returns:
            The sequence number of the action.
        """
        async with self:
            self._sequence_counter += 1
            self._pending_actions[self._sequence_counter] = action
            return self._sequence_counter

    async def get_pending_action(self, sequence_number: int) -> Optional[Dict[str, Any]]:
        """Get a pending action by sequence number.

        Args:
            sequence_number: The sequence number.

        Returns:
            The action data, or None if not found.
        """
        async with self:
            return self._pending_actions.get(sequence_number)

    async def delete_pending_action(self, sequence_number: int) -> bool:
        """Delete a pending action.

        Args:
            sequence_number: The sequence number.

        Returns:
            True if deleted, False if not found.
        """
        async with self:
            if sequence_number in self._pending_actions:
                del self._pending_actions[sequence_number]
                return True
            return False

    async def get_pending_actions(self, limit: int = 25) -> List[Dict[str, Any]]:
        """Get pending actions, limited to a maximum number.

        Args:
            limit: Maximum number of actions to return.

        Returns:
            List of action data.
        """
        async with self:
            actions = list(self._pending_actions.values())[:limit]
            return actions

    async def clear_pending_actions(self) -> None:
        """Clear all pending actions."""
        async with self:
            self._pending_actions.clear()
            self._sequence_counter = 0

    # ========================================================================
    # Sync Versions
    # ========================================================================

    async def get_sync_version(self, entity_type: str) -> str:
        """Get the sync version for an entity type.

        Args:
            entity_type: The entity type (e.g., 'users', 'devices', 'categories').

        Returns:
            The version string, or empty string if not found.
        """
        async with self:
            return self._sync_versions.get(entity_type, "")

    async def set_sync_version(self, entity_type: str, version: str) -> None:
        """Set the sync version for an entity type.

        Args:
            entity_type: The entity type.
            version: The version string.
        """
        async with self:
            self._sync_versions[entity_type] = version

    async def increment_sync_version(self, entity_type: str) -> str:
        """Increment the sync version for an entity type.

        Args:
            entity_type: The entity type.

        Returns:
            The new version string.
        """
        async with self:
            current = self._sync_versions.get(entity_type, "")
            new_version = f"{current}_{uuid.uuid4().hex[:8]}"
            self._sync_versions[entity_type] = new_version
            return new_version

    # ========================================================================
    # App Management
    # ========================================================================

    async def set_apps(self, device_id: str, apps: List[str]) -> None:
        """Set the installed apps for a device.

        Args:
            device_id: The device ID.
            apps: List of app package names.
        """
        async with self:
            self._apps[device_id] = apps

    async def get_apps(self, device_id: str) -> List[str]:
        """Get the installed apps for a device.

        Args:
            device_id: The device ID.

        Returns:
            List of app package names, or empty list if not found.
        """
        async with self:
            return self._apps.get(device_id, [])

    # ========================================================================
    # WebSocket Connections
    # ========================================================================

    async def add_connection(self, connection_id: str) -> None:
        """Add an active WebSocket connection.

        Args:
            connection_id: The connection identifier.
        """
        async with self:
            self._active_connections.add(connection_id)

    async def remove_connection(self, connection_id: str) -> None:
        """Remove a WebSocket connection.

        Args:
            connection_id: The connection identifier.
        """
        async with self:
            self._active_connections.discard(connection_id)

    async def get_active_connections(self) -> Set[str]:
        """Get all active WebSocket connections.

        Returns:
            Set of connection identifiers.
        """
        async with self:
            return self._active_connections.copy()

    # ========================================================================
    # Reset/Clear
    # ========================================================================

    async def reset(self) -> None:
        """Reset all state."""
        async with self:
            self._families.clear()
            self._users.clear()
            self._devices.clear()
            self._categories.clear()
            self._apps.clear()
            self._mail_login_tokens.clear()
            self._mail_auth_tokens.clear()
            self._device_auth_tokens.clear()
            self._add_device_tokens.clear()
            self._pending_actions.clear()
            self._sync_versions.clear()
            self._active_connections.clear()
            self._sequence_counter = 0
            logger.info("State reset completed")


# Global state manager instance
state_manager = StateManager()