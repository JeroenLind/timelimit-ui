"""Unified logger for all server-sent messages.

This module provides a unified facade for logging all outgoing messages
from the server, including HTTP API responses, WebSocket replies, sync actions,
auth events, and server-generated broadcasts.

The MessageSentLogger wraps ServerMessageLogger with sanitization and metadata
enrichment, providing convenience methods for each message type.
"""

import logging
from typing import Any, Dict, Optional

from app.middleware.server_message_logger import (
    ServerMessageLogger,
    MessageType,
    get_server_message_logger,
    SENSITIVE_KEYS,
)

logger = logging.getLogger(__name__)


class MessageSentLogger:
    """Unified logger for all server-sent messages.
    
    This class provides a convenient interface for logging all types of
    outgoing messages from the server, with automatic sanitization and
    metadata enrichment.
    
    Usage:
        # Get the global instance
        msg_logger = get_message_sent_logger()
        
        # Log an API reply
        msg_logger.log_api_reply(
            content={"status": "ok"},
            status_code=200,
            request_id="abc123",
            path="/sync/pull-status",
            method="POST",
            duration_ms=45
        )
        
        # Log a WebSocket reply
        msg_logger.log_websocket_reply(
            event="devicelogin",
            data={"status": "ok"},
            sid="socket_123",
            connection_id="conn_456"
        )
    """
    
    def __init__(self, server_logger: ServerMessageLogger):
        """Initialize the message sent logger.
        
        Args:
            server_logger: The underlying ServerMessageLogger instance.
        """
        self._server_logger = server_logger
    
    def log_outgoing_message(
        self,
        message_type: MessageType,
        content: Any,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> None:
        """Log any outgoing server message with sanitization.
        
        Args:
            message_type: The type of message being logged.
            content: The message content.
            metadata: Additional metadata.
            **kwargs: Additional arguments passed to log_message().
        """
        self._server_logger.log_message(
            message_type=message_type,
            content=content,
            metadata=metadata,
            **kwargs
        )
    
    def log_api_reply(
        self,
        content: Any,
        status_code: int,
        request_id: str,
        path: str,
        method: str,
        duration_ms: int
    ) -> None:
        """Log an HTTP API response (reply).
        
        Args:
            content: The response content.
            status_code: HTTP status code.
            request_id: Request ID for correlation.
            path: Request path.
            method: HTTP method.
            duration_ms: Request duration in milliseconds.
        """
        self._server_logger.log_api_response(
            content=content,
            status_code=status_code,
            request_id=request_id,
            path=path,
            method=method,
            duration_ms=duration_ms
        )
    
    def log_websocket_reply(
        self,
        event: str,
        data: Any,
        sid: Optional[str] = None,
        connection_id: Optional[str] = None
    ) -> None:
        """Log a WebSocket event reply.
        
        Args:
            event: The event name.
            data: The event data.
            sid: Optional Socket.IO session ID.
            connection_id: Optional connection ID.
        """
        self._server_logger.log_websocket_event(
            event=event,
            data=data,
            sid=sid,
            connection_id=connection_id
        )
    
    def log_broadcast(
        self,
        event: str,
        data: Any,
        family_id: Optional[str] = None,
        notified_count: Optional[int] = None
    ) -> None:
        """Log a WebSocket broadcast.
        
        Args:
            event: The event name.
            data: The broadcast data.
            family_id: Optional family ID.
            notified_count: Optional count of notified connections.
        """
        self._server_logger.log_websocket_broadcast(
            event=event,
            data=data,
            family_id=family_id,
            notified_count=notified_count
        )
    
    def log_sync_action(
        self,
        action_type: str,
        action_data: Any,
        sequence_number: Optional[int] = None,
        user_id: Optional[str] = None,
        family_id: Optional[str] = None
    ) -> None:
        """Log a sync action sent to the client.
        
        Args:
            action_type: The type of sync action.
            action_data: The action data.
            sequence_number: Optional sequence number.
            user_id: Optional user ID.
            family_id: Optional family ID.
        """
        self._server_logger.log_sync_action(
            action_type=action_type,
            action_data=action_data,
            sequence_number=sequence_number,
            user_id=user_id,
            family_id=family_id
        )
    
    def log_sync_reply(
        self,
        action_type: str,
        action_data: Any,
        sequence_number: Optional[int] = None,
        user_id: Optional[str] = None,
        family_id: Optional[str] = None
    ) -> None:
        """Log a sync action sent to the client.
        
        Args:
            action_type: The type of sync action.
            action_data: The action data.
            sequence_number: Optional sequence number.
            user_id: Optional user ID.
            family_id: Optional family ID.
        """
        self._server_logger.log_sync_action(
            action_type=action_type,
            action_data=action_data,
            sequence_number=sequence_number,
            user_id=user_id,
            family_id=family_id
        )
    
    def log_auth_reply(
        self,
        event_type: str,
        user_id: Optional[str] = None,
        device_id: Optional[str] = None,
        family_id: Optional[str] = None,
        success: Optional[bool] = None
    ) -> None:
        """Log an auth event sent to the client.
        
        Args:
            event_type: The type of auth event.
            user_id: Optional user ID.
            device_id: Optional device ID.
            family_id: Optional family ID.
            success: Optional success status.
        """
        self._server_logger.log_auth_event(
            event_type=event_type,
            user_id=user_id,
            device_id=device_id,
            family_id=family_id,
            success=success
        )
    
    def log_system_event(
        self,
        event: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a system event.
        
        Args:
            event: The event name.
            details: Optional event details.
        """
        self._server_logger.log_system_event(
            event=event,
            details=details
        )
    
    def flush(self) -> None:
        """Flush the async log queue."""
        self._server_logger.flush()
    
    def get_log_buffer(self) -> list:
        """Get the log buffer contents.
        
        Returns:
            List of structured log entries.
        """
        return self._server_logger.get_log_buffer()
    
    def clear_log_buffer(self) -> None:
        """Clear the log buffer."""
        self._server_logger.clear_log_buffer()


# Global instance
_message_sent_logger: Optional[MessageSentLogger] = None


def get_message_sent_logger(
    server_logger: Optional[ServerMessageLogger] = None
) -> MessageSentLogger:
    """Get or create the global message sent logger instance.
    
    Args:
        server_logger: Optional ServerMessageLogger instance. If not provided,
                      uses the global ServerMessageLogger instance.
    
    Returns:
        MessageSentLogger instance.
    """
    global _message_sent_logger
    if _message_sent_logger is None:
        if server_logger is None:
            server_logger = get_server_message_logger()
        _message_sent_logger = MessageSentLogger(server_logger)
    return _message_sent_logger


def reset_message_sent_logger() -> None:
    """Reset the global message sent logger instance."""
    global _message_sent_logger
    if _message_sent_logger is not None:
        _message_sent_logger._server_logger.stop_async_logging()
    _message_sent_logger = None