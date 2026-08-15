"""Socket.IO connection management for TimeLimit API.

This module provides connection management for WebSocket (Socket.IO)
connections including connection tracking, event broadcasting, and
session management.

All server-transmitted messages are logged with comprehensive metadata
including timestamps, message content, and associated metadata.
"""

import logging
from typing import Any, Dict, List, Optional, Set

from app.core.config import settings
from app.core.state import state_manager
from app.middleware.server_message_logger import get_server_message_logger

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Socket.IO connection manager.
    
    Manages WebSocket connections for real-time communication.
    """
    
    def __init__(self, state: state_manager = None):
        """Initialize the connection manager.
        
        Args:
            state: State manager instance. Uses global state_manager if not provided.
        """
        self.state = state or state_manager
        self._active_connections: Set[str] = set()
        self._device_connections: Dict[str, str] = {}  # device_id -> connection_id
        self._connection_metadata: Dict[str, Dict[str, Any]] = {}  # connection_id -> metadata
    
    async def connect(self, connection_id: str, device_id: str = None) -> None:
        """Register a new WebSocket connection.
        
        Args:
            connection_id: Unique connection identifier.
            device_id: Optional device ID associated with the connection.
        """
        self._active_connections.add(connection_id)
        
        if device_id:
            self._device_connections[device_id] = connection_id
        
        self._connection_metadata[connection_id] = {
            "device_id": device_id,
            "connected_at": self._get_timestamp(),
            "last_activity": self._get_timestamp(),
        }
        
        # Add to state manager
        await self.state.add_connection(connection_id)
        
        logger.info(
            "WebSocket connection established",
            extra={
                "connection_id": connection_id[:8] + "...",
                "device_id": device_id,
            }
        )
        
        # Log the server-transmitted connection event
        server_logger = get_server_message_logger()
        server_logger.log_system_event(
            event="websocket_connect",
            details={
                "connection_id": connection_id[:8] + "...",
                "device_id": device_id,
            }
        )
    
    async def disconnect(self, connection_id: str) -> None:
        """Unregister a WebSocket connection.
        
        Args:
            connection_id: Connection identifier to disconnect.
        """
        self._active_connections.discard(connection_id)
        
        # Remove device association
        metadata = self._connection_metadata.get(connection_id, {})
        device_id = metadata.get("device_id")
        if device_id and device_id in self._device_connections:
            del self._device_connections[device_id]
        
        # Remove from state manager
        await self.state.remove_connection(connection_id)
        
        # Clean up metadata
        if connection_id in self._connection_metadata:
            del self._connection_metadata[connection_id]
        
        logger.info(
            "WebSocket connection closed",
            extra={"connection_id": connection_id[:8] + "..."}
        )
        
        # Log the server-transmitted disconnection event
        server_logger = get_server_message_logger()
        server_logger.log_system_event(
            event="websocket_disconnect",
            details={"connection_id": connection_id[:8] + "..."}
        )
    
    async def update_activity(self, connection_id: str) -> None:
        """Update last activity timestamp for a connection.
        
        Args:
            connection_id: Connection identifier.
        """
        if connection_id in self._connection_metadata:
            self._connection_metadata[connection_id]["last_activity"] = self._get_timestamp()
    
    def get_active_connections(self) -> Set[str]:
        """Get all active connection IDs.
        
        Returns:
            Set of active connection IDs.
        """
        return self._active_connections.copy()
    
    def get_connection_count(self) -> int:
        """Get the number of active connections.
        
        Returns:
            Number of active connections.
        """
        return len(self._active_connections)
    
    def get_device_connection(self, device_id: str) -> Optional[str]:
        """Get connection ID for a device.
        
        Args:
            device_id: Device identifier.
            
        Returns:
            Connection ID or None if not found.
        """
        return self._device_connections.get(device_id)
    
    def get_connection_metadata(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a connection.
        
        Args:
            connection_id: Connection identifier.
            
        Returns:
            Connection metadata or None if not found.
        """
        return self._connection_metadata.get(connection_id)
    
    def _get_timestamp(self) -> int:
        """Get current timestamp in milliseconds.
        
        Returns:
            Timestamp in milliseconds.
        """
        import time
        return int(time.time() * 1000)


class SocketIOHandler:
    """Socket.IO event handler for TimeLimit API.
    
    Handles real-time events including:
    - devicelogin: Device login events
    - should sync: Sync notification events
    - connected devices: Device status events
    - sign out: Sign out events
    """
    
    def __init__(self, connection_manager: ConnectionManager = None):
        """Initialize the Socket.IO handler.
        
        Args:
            connection_manager: Connection manager instance.
        """
        self.manager = connection_manager or ConnectionManager()
    
    async def handle_devicelogin(
        self,
        connection_id: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle device login event.
        
        Args:
            connection_id: Connection identifier.
            data: Event data containing device info.
            
        Returns:
            Response dictionary.
        """
        device_id = data.get("deviceId")
        family_id = data.get("familyId")
        
        logger.info(
            "Device login event received",
            extra={
                "connection_id": connection_id[:8] + "...",
                "device_id": device_id,
                "family_id": family_id,
            }
        )
        
        # Update connection with device info
        await self.manager.update_activity(connection_id)
        
        response = {
            "status": "ok",
            "message": "Device logged in successfully",
        }
        
        # Log the server-transmitted message
        server_logger = get_server_message_logger()
        server_logger.log_websocket_event(
            event="devicelogin",
            data=response,
            connection_id=connection_id
        )
        
        return response
    
    async def handle_should_sync(
        self,
        connection_id: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle sync notification event.
        
        Args:
            connection_id: Connection identifier.
            data: Event data containing sync info.
            
        Returns:
            Response dictionary.
        """
        device_id = data.get("deviceId")
        family_id = data.get("familyId")
        
        logger.info(
            "Sync notification event received",
            extra={
                "connection_id": connection_id[:8] + "...",
                "device_id": device_id,
                "family_id": family_id,
            }
        )
        
        response = {
            "status": "ok",
            "message": "Sync notification processed",
        }
        
        # Log the server-transmitted message
        server_logger = get_server_message_logger()
        server_logger.log_websocket_event(
            event="should sync",
            data=response,
            connection_id=connection_id
        )
        
        return response
    
    async def handle_connected_devices(
        self,
        connection_id: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle connected devices event.
        
        Args:
            connection_id: Connection identifier.
            data: Event data containing device list.
            
        Returns:
            Response dictionary.
        """
        device_id = data.get("deviceId")
        family_id = data.get("familyId")
        
        logger.info(
            "Connected devices event received",
            extra={
                "connection_id": connection_id[:8] + "...",
                "device_id": device_id,
                "family_id": family_id,
            }
        )
        
        # Get all devices in the family
        devices = await self.manager.state.get_devices_by_family(family_id) if family_id else []
        
        response = {
            "status": "ok",
            "devices": [d.get("deviceId") for d in devices],
            "count": len(devices),
        }
        
        # Log the server-transmitted message
        server_logger = get_server_message_logger()
        server_logger.log_websocket_event(
            event="connected devices",
            data=response,
            connection_id=connection_id
        )
        
        return response
    
    async def handle_sign_out(
        self,
        connection_id: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle sign out event.
        
        Args:
            connection_id: Connection identifier.
            data: Event data containing sign out info.
            
        Returns:
            Response dictionary.
        """
        device_id = data.get("deviceId")
        family_id = data.get("familyId")
        
        logger.info(
            "Sign out event received",
            extra={
                "connection_id": connection_id[:8] + "...",
                "device_id": device_id,
                "family_id": family_id,
            }
        )
        
        # Disconnect the connection
        await self.manager.disconnect(connection_id)
        
        response = {
            "status": "ok",
            "message": "Signed out successfully",
        }
        
        # Log the server-transmitted message
        server_logger = get_server_message_logger()
        server_logger.log_websocket_event(
            event="sign out",
            data=response,
            connection_id=connection_id
        )
        
        return response
    
    async def broadcast_to_family(
        self,
        family_id: str,
        event: str,
        data: Dict[str, Any]
    ) -> int:
        """Broadcast an event to all connections in a family.
        
        Args:
            family_id: Family identifier.
            event: Event name.
            data: Event data.
            
        Returns:
            Number of connections notified.
        """
        notified_count = 0
        
        for connection_id in self.manager.get_active_connections():
            metadata = self.manager.get_connection_metadata(connection_id)
            if metadata and metadata.get("device_id"):
                device = await self.manager.state.get_device(metadata.get("device_id"))
                if device and device.get("family_id") == family_id:
                    # In a real implementation, this would emit to the Socket.IO room
                    logger.debug(
                        "Broadcasting event to connection",
                        extra={
                            "event": event,
                            "connection_id": connection_id[:8] + "...",
                        }
                    )
                    notified_count += 1
        
        logger.info(
            "Broadcast event completed",
            extra={
                "event": event,
                "family_id": family_id,
                "notified_count": notified_count,
            }
        )
        
        # Log the server broadcast message
        server_logger = get_server_message_logger()
        server_logger.log_websocket_broadcast(
            event=event,
            data=data,
            family_id=family_id,
            notified_count=notified_count
        )
        
        return notified_count


# Global instances
connection_manager = ConnectionManager()
socket_handler = SocketIOHandler(connection_manager)