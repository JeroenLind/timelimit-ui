"""WebSocket modules for the debug server.

This package contains WebSocket components including:
- manager: Socket.IO connection management
- handlers: Socket.IO event handlers

Provides real-time communication support for:
- devicelogin: Device login events
- should sync: Sync notification events
- connected devices: Device status events
- sign out: Sign out events
"""

from app.websocket.manager import (
    ConnectionManager,
    SocketIOHandler,
    connection_manager,
    socket_handler,
)
from app.websocket.handlers import (
    EVENT_HANDLERS,
    get_event_handler,
    on_connect,
    on_connected_devices,
    on_devicelogin,
    on_disconnect,
    on_ping,
    on_pong,
    on_should_sync,
    on_sign_out,
)

__all__ = [
    # Manager classes
    "ConnectionManager",
    "SocketIOHandler",
    "connection_manager",
    "socket_handler",
    # Event handlers
    "EVENT_HANDLERS",
    "get_event_handler",
    "on_connect",
    "on_disconnect",
    "on_devicelogin",
    "on_should_sync",
    "on_connected_devices",
    "on_sign_out",
    "on_ping",
    "on_pong",
]