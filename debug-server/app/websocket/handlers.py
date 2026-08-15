"""Socket.IO event handlers for TimeLimit API.

This module provides event handlers for Socket.IO events including:
- devicelogin: Device login events
- should sync: Sync notification events
- connected devices: Device status events
- sign out: Sign out events

All server-transmitted messages are logged with comprehensive metadata
including timestamps, message content, and associated metadata.
"""

import logging
from typing import Any, Dict

from app.middleware.server_message_logger import (
    get_server_message_logger,
    MessageType,
)
from app.websocket.manager import socket_handler

logger = logging.getLogger(__name__)


async def on_connect(sid: str, environ: Dict[str, Any] = None) -> Dict[str, Any]:
    """Handle Socket.IO connection event.
    
    Args:
        sid: Socket.IO session ID.
        environ: Connection environment data.
        
    Returns:
        Response dictionary.
    """
    logger.info("Socket.IO connection established", extra={"sid": sid[:8] + "..."})
    
    response = {
        "status": "connected",
        "message": "Connected to TimeLimit server",
    }
    
    # Log the server-transmitted message
    server_logger = get_server_message_logger()
    server_logger.log_websocket_event(
        event="connect",
        data=response,
        sid=sid
    )
    
    return response


async def on_disconnect(sid: str) -> None:
    """Handle Socket.IO disconnection event.
    
    Args:
        sid: Socket.IO session ID.
    """
    logger.info("Socket.IO connection closed", extra={"sid": sid[:8] + "..."})
    await socket_handler.manager.disconnect(sid)
    
    # Log the server-transmitted message
    server_logger = get_server_message_logger()
    server_logger.log_system_event(
        event="disconnect",
        details={"sid": sid[:8] + "..."}
    )


async def on_devicelogin(
    sid: str,
    data: Dict[str, Any]
) -> Dict[str, Any]:
    """Handle devicelogin event.
    
    Args:
        sid: Socket.IO session ID.
        data: Event data containing device info.
        
    Returns:
        Response dictionary.
    """
    logger.info(
        "Device login event",
        extra={
            "sid": sid[:8] + "...",
            "device_id": data.get("deviceId"),
        }
    )
    
    response = await socket_handler.handle_devicelogin(sid, data)
    
    # Log the server-transmitted message
    server_logger = get_server_message_logger()
    server_logger.log_websocket_event(
        event="devicelogin",
        data=response,
        sid=sid,
        connection_id=sid
    )
    
    return response


async def on_should_sync(
    sid: str,
    data: Dict[str, Any]
) -> Dict[str, Any]:
    """Handle should sync event.
    
    Args:
        sid: Socket.IO session ID.
        data: Event data containing sync info.
        
    Returns:
        Response dictionary.
    """
    logger.info(
        "Sync notification event",
        extra={
            "sid": sid[:8] + "...",
            "device_id": data.get("deviceId"),
        }
    )
    
    response = await socket_handler.handle_should_sync(sid, data)
    
    # Log the server-transmitted message
    server_logger = get_server_message_logger()
    server_logger.log_websocket_event(
        event="should sync",
        data=response,
        sid=sid,
        connection_id=sid
    )
    
    return response


async def on_connected_devices(
    sid: str,
    data: Dict[str, Any]
) -> Dict[str, Any]:
    """Handle connected devices event.
    
    Args:
        sid: Socket.IO session ID.
        data: Event data containing device list.
        
    Returns:
        Response dictionary.
    """
    logger.info(
        "Connected devices event",
        extra={
            "sid": sid[:8] + "...",
            "device_id": data.get("deviceId"),
        }
    )
    
    response = await socket_handler.handle_connected_devices(sid, data)
    
    # Log the server-transmitted message
    server_logger = get_server_message_logger()
    server_logger.log_websocket_event(
        event="connected devices",
        data=response,
        sid=sid,
        connection_id=sid
    )
    
    return response


async def on_sign_out(
    sid: str,
    data: Dict[str, Any]
) -> Dict[str, Any]:
    """Handle sign out event.
    
    Args:
        sid: Socket.IO session ID.
        data: Event data containing sign out info.
        
    Returns:
        Response dictionary.
    """
    logger.info(
        "Sign out event",
        extra={
            "sid": sid[:8] + "...",
            "device_id": data.get("deviceId"),
        }
    )
    
    response = await socket_handler.handle_sign_out(sid, data)
    
    # Log the server-transmitted message
    server_logger = get_server_message_logger()
    server_logger.log_websocket_event(
        event="sign out",
        data=response,
        sid=sid,
        connection_id=sid
    )
    
    return response


async def on_ping(
    sid: str,
    data: Dict[str, Any]
) -> Dict[str, Any]:
    """Handle ping event for keep-alive.
    
    Args:
        sid: Socket.IO session ID.
        data: Ping data.
        
    Returns:
        Response dictionary.
    """
    await socket_handler.manager.update_activity(sid)
    
    response = {
        "status": "ok",
        "timestamp": data.get("timestamp"),
    }
    
    # Log the server-transmitted message
    server_logger = get_server_message_logger()
    server_logger.log_websocket_event(
        event="ping",
        data=response,
        sid=sid
    )
    
    return response


async def on_pong(
    sid: str,
    data: Dict[str, Any]
) -> Dict[str, Any]:
    """Handle pong event for keep-alive.
    
    Args:
        sid: Socket.IO session ID.
        data: Pong data.
        
    Returns:
        Response dictionary.
    """
    await socket_handler.manager.update_activity(sid)
    
    response = {
        "status": "ok",
        "timestamp": data.get("timestamp"),
    }
    
    # Log the server-transmitted message
    server_logger = get_server_message_logger()
    server_logger.log_websocket_event(
        event="pong",
        data=response,
        sid=sid
    )
    
    return response


# Event handler registry
EVENT_HANDLERS = {
    "connect": on_connect,
    "disconnect": on_disconnect,
    "devicelogin": on_devicelogin,
    "should sync": on_should_sync,
    "connected devices": on_connected_devices,
    "sign out": on_sign_out,
    "ping": on_ping,
    "pong": on_pong,
}


def get_event_handler(event: str):
    """Get the handler function for an event.
    
    Args:
        event: Event name.
        
    Returns:
        Handler function or None if not found.
    """
    return EVENT_HANDLERS.get(event)