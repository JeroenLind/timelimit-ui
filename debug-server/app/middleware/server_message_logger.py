"""Server message logging for comprehensive message flow visibility.

This module provides logging functionality for messages transmitted by the server,
including timestamps, message content, and associated metadata.
"""

import json
import logging
import queue
import threading
from datetime import datetime
from typing import Any, Dict, Optional, Union
from enum import Enum

logger = logging.getLogger(__name__)


# Sensitive keys that should be redacted in logs
SENSITIVE_KEYS = {
    'password', 'password_hash', 'second_hash', 'second_salt',
    'token', 'access_token', 'refresh_token', 'device_auth_token',
    'mail_auth_token', 'mail_login_token', 'secret_key', 'jwt_secret',
    'api_key', 'private_key', 'signature', 'encrypted',
    'parentpassword', 'secondhash', 'secondsalt', 'deviceauthtoken',
    'mailauthtoken', 'maillogintoken', 'identitytoken',
    'secondHash', 'parentPassword', 'deviceAuthToken', 'mailAuthToken',
    'mailLoginToken', 'identityToken',
}


class MessageType(Enum):
    """Enumeration of message types for server-transmitted messages."""
    API_RESPONSE = "api_response"
    WEBSOCKET_EVENT = "websocket_event"
    WEBSOCKET_BROADCAST = "websocket_broadcast"
    SYNC_ACTION = "sync_action"
    AUTH_EVENT = "auth_event"
    SYSTEM_EVENT = "system_event"


class ServerMessageLogger:
    """Logger for server-transmitted messages with comprehensive metadata.
    
    This class captures and records all messages transmitted by the server,
    including timestamps, message content, and associated metadata, ensuring
    comprehensive visibility into the entire message flow.
    
    Log format:
    [YYYY-MM-DD HH:MM:SS.mmm] [SERVER] {message_type} - {metadata} - {content}
    
    Features:
    - Sensitive data sanitization
    - Async logging mode for minimal performance impact
    - In-memory log buffer for testing and analysis
    - Configurable log level
    """
    
    def __init__(
        self,
        log_file_path: Optional[str] = None,
        async_mode: bool = True,
        log_level: int = logging.INFO,
        max_buffer_size: int = 1000,
        sanitize: bool = True
    ):
        """Initialize the server message logger.
        
        Args:
            log_file_path: Optional path to the log file. If not provided,
                          logs will be written via the standard logger.
            async_mode: If True, use background thread for file writes.
            log_level: Minimum log level for message logging.
            max_buffer_size: Maximum entries in the in-memory log buffer.
            sanitize: If True, sanitize sensitive data before logging.
        """
        self.log_file_path = log_file_path
        self.async_mode = async_mode
        self.log_level = log_level
        self.max_buffer_size = max_buffer_size
        self.sanitize = sanitize
        self._log_buffer: list = []
        self._log_buffer_lock = threading.Lock()
        
        # Async logging components
        self._log_queue: Optional[queue.Queue] = None
        self._log_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        if async_mode:
            self._start_async_logging()
    
    def _start_async_logging(self) -> None:
        """Start the background logging thread."""
        self._log_queue = queue.Queue()
        self._stop_event.clear()
        self._log_thread = threading.Thread(
            target=self._async_log_worker,
            daemon=True,
            name="ServerMessageLogger-AsyncWorker"
        )
        self._log_thread.start()
    
    def _async_log_worker(self) -> None:
        """Background worker that processes log messages from the queue."""
        while not self._stop_event.is_set():
            try:
                # Wait for a message with timeout to allow checking stop event
                message = self._log_queue.get(timeout=0.1)
                if message is None:
                    break
                self._write_to_log_file(message)
                self._log_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in async log worker: {e}")
    
    def flush(self) -> None:
        """Flush the async log queue and wait for all messages to be written."""
        if self._log_queue is not None:
            # Wait for queue to be empty
            self._log_queue.join()
    
    def stop_async_logging(self) -> None:
        """Stop the background logging thread."""
        if self._log_thread is not None and self._log_thread.is_alive():
            self._stop_event.set()
            if self._log_queue is not None:
                self._log_queue.put(None)  # Sentinel to wake up the thread
            self._log_thread.join(timeout=5.0)
            self._log_thread = None
    
    def _sanitize_content(self, content: Any) -> Any:
        """Recursively sanitize sensitive data from content.
        
        Args:
            content: The content to sanitize.
            
        Returns:
            Sanitized content with sensitive values replaced by ***REDACTED***.
        """
        if isinstance(content, dict):
            result = {}
            for key, value in content.items():
                if key.lower() in SENSITIVE_KEYS:
                    result[key] = '***REDACTED***'
                elif isinstance(value, (dict, list)):
                    result[key] = self._sanitize_content(value)
                elif isinstance(value, str) and len(value) > 500:
                    result[key] = value[:500] + '...[truncated]'
                else:
                    result[key] = value
            return result
        elif isinstance(content, list):
            return [self._sanitize_content(item) for item in content]
        else:
            return content
    
    def log_message(
        self,
        message_type: MessageType,
        content: Any,
        metadata: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        connection_id: Optional[str] = None,
        duration_ms: Optional[int] = None,
        status_code: Optional[int] = None,
        error: Optional[Exception] = None
    ) -> None:
        """Log a server-transmitted message with comprehensive metadata.
        
        Args:
            message_type: The type of message being logged.
            content: The message content (will be serialized to JSON if possible).
            metadata: Additional metadata associated with the message.
            request_id: Optional request ID for correlation.
            connection_id: Optional connection ID (for WebSocket messages).
            duration_ms: Optional duration in milliseconds (for API responses).
            status_code: Optional HTTP status code (for API responses).
            error: Optional exception if the message represents an error.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        # Build metadata dict
        meta_dict = metadata or {}
        if request_id:
            meta_dict["request_id"] = request_id
        if connection_id:
            meta_dict["connection_id"] = connection_id[:8] + "..." if len(connection_id) > 8 else connection_id
        if duration_ms is not None:
            meta_dict["duration_ms"] = duration_ms
        if status_code is not None:
            meta_dict["status_code"] = status_code
        if error:
            meta_dict["error"] = str(error)
            meta_dict["error_type"] = type(error).__name__
        
        # Sanitize content if enabled
        content_to_log = content
        if self.sanitize:
            content_to_log = self._sanitize_content(content)
        
        # Serialize content
        content_str = self._serialize_content(content_to_log)
        
        # Build log message
        meta_str = json.dumps(meta_dict, ensure_ascii=False) if meta_dict else "{}"
        log_message = f"[{timestamp}] [SERVER] {message_type.value} - {meta_str} - {content_str}"
        
        # Create structured entry for buffer
        structured_entry = {
            "timestamp": timestamp,
            "message_type": message_type.value,
            "metadata": meta_dict,
            "content": content_to_log,
            "log_message": log_message
        }
        
        # Add to buffer with size limit
        with self._log_buffer_lock:
            self._log_buffer.append(structured_entry)
            if len(self._log_buffer) > self.max_buffer_size:
                self._log_buffer = self._log_buffer[-self.max_buffer_size:]
        
        # Log via standard logger at configured level
        logger.log(self.log_level, log_message)
        
        # Write to log file
        if self.log_file_path:
            if self.async_mode and self._log_queue is not None:
                self._log_queue.put(log_message)
            else:
                self._write_to_log_file(log_message)
    
    def log_api_response(
        self,
        content: Any,
        status_code: int,
        request_id: Optional[str] = None,
        path: Optional[str] = None,
        method: Optional[str] = None,
        duration_ms: Optional[int] = None
    ) -> None:
        """Log an API response message.
        
        Args:
            content: The response content.
            status_code: HTTP status code.
            request_id: Optional request ID for correlation.
            path: Optional request path.
            method: Optional HTTP method.
            duration_ms: Optional duration in milliseconds.
        """
        metadata = {}
        if path:
            metadata["path"] = path
        if method:
            metadata["method"] = method
        
        self.log_message(
            message_type=MessageType.API_RESPONSE,
            content=content,
            metadata=metadata,
            request_id=request_id,
            status_code=status_code,
            duration_ms=duration_ms
        )
    
    def log_websocket_event(
        self,
        event: str,
        data: Any,
        connection_id: Optional[str] = None,
        sid: Optional[str] = None
    ) -> None:
        """Log a WebSocket event message.
        
        Args:
            event: The event name.
            data: The event data.
            connection_id: Optional connection ID.
            sid: Optional Socket.IO session ID.
        """
        metadata = {"event": event}
        if sid:
            metadata["sid"] = sid[:8] + "..." if len(sid) > 8 else sid
        
        self.log_message(
            message_type=MessageType.WEBSOCKET_EVENT,
            content=data,
            metadata=metadata,
            connection_id=connection_id
        )
    
    def log_websocket_broadcast(
        self,
        event: str,
        data: Any,
        family_id: Optional[str] = None,
        notified_count: Optional[int] = None
    ) -> None:
        """Log a WebSocket broadcast message.
        
        Args:
            event: The event name.
            data: The broadcast data.
            family_id: Optional family ID.
            notified_count: Optional count of notified connections.
        """
        metadata = {"event": event, "broadcast": True}
        if family_id:
            metadata["family_id"] = family_id
        if notified_count is not None:
            metadata["notified_count"] = notified_count
        
        self.log_message(
            message_type=MessageType.WEBSOCKET_BROADCAST,
            content=data,
            metadata=metadata
        )
    
    def log_sync_action(
        self,
        action_type: str,
        action_data: Any,
        sequence_number: Optional[int] = None,
        user_id: Optional[str] = None,
        family_id: Optional[str] = None
    ) -> None:
        """Log a sync action message.
        
        Args:
            action_type: The type of sync action.
            action_data: The action data.
            sequence_number: Optional sequence number.
            user_id: Optional user ID.
            family_id: Optional family ID.
        """
        metadata = {"action_type": action_type}
        if sequence_number is not None:
            metadata["sequence_number"] = sequence_number
        if user_id:
            metadata["user_id"] = user_id
        if family_id:
            metadata["family_id"] = family_id
        
        self.log_message(
            message_type=MessageType.SYNC_ACTION,
            content=action_data,
            metadata=metadata
        )
    
    def log_auth_event(
        self,
        event_type: str,
        user_id: Optional[str] = None,
        device_id: Optional[str] = None,
        family_id: Optional[str] = None,
        success: Optional[bool] = None
    ) -> None:
        """Log an authentication event message.
        
        Args:
            event_type: The type of auth event.
            user_id: Optional user ID.
            device_id: Optional device ID.
            family_id: Optional family ID.
            success: Optional success status.
        """
        metadata = {"event_type": event_type}
        if user_id:
            metadata["user_id"] = user_id
        if device_id:
            metadata["device_id"] = device_id
        if family_id:
            metadata["family_id"] = family_id
        if success is not None:
            metadata["success"] = success
        
        self.log_message(
            message_type=MessageType.AUTH_EVENT,
            content={},
            metadata=metadata
        )
    
    def log_system_event(
        self,
        event: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a system event message.
        
        Args:
            event: The event name.
            details: Optional event details.
        """
        self.log_message(
            message_type=MessageType.SYSTEM_EVENT,
            content=details or {},
            metadata={"event": event}
        )
    
    def _serialize_content(self, content: Any) -> str:
        """Serialize content to a string representation.
        
        Args:
            content: The content to serialize.
            
        Returns:
            String representation of the content.
        """
        if content is None:
            return "null"
        
        if isinstance(content, (str, int, float, bool)):
            return str(content)
        
        if isinstance(content, dict):
            try:
                return json.dumps(content, ensure_ascii=False, indent=None)
            except (TypeError, ValueError):
                return str(content)
        
        if isinstance(content, (list, tuple)):
            try:
                return json.dumps(list(content), ensure_ascii=False, indent=None)
            except (TypeError, ValueError):
                return str(content)
        
        # For other types, try to convert to dict or use string representation
        try:
            if hasattr(content, 'model_dump'):
                # Pydantic model
                return json.dumps(content.model_dump(), ensure_ascii=False, indent=None)
            if hasattr(content, 'dict'):
                # Pydantic v1 model
                return json.dumps(content.dict(), ensure_ascii=False, indent=None)
        except Exception:
            pass
        
        return str(content)
    
    def _write_to_log_file(self, message: str) -> None:
        """Write a message directly to the log file.
        
        Args:
            message: The message to write.
        """
        import os
        from pathlib import Path
        
        try:
            if self.log_file_path:
                # Ensure the log directory exists
                log_dir = os.path.dirname(self.log_file_path)
                if log_dir:
                    Path(log_dir).mkdir(parents=True, exist_ok=True)
                else:
                    # If no directory component, create in current directory
                    log_dir = "."
                
                # Append to the log file
                with open(self.log_file_path, "a", encoding="utf-8") as f:
                    f.write(message + "\n")
        except Exception as e:
            logger.error(f"Failed to write to log file: {e}")
    
    def get_log_buffer(self) -> list:
        """Get the log buffer contents.
        
        Returns:
            List of structured log entries.
        """
        with self._log_buffer_lock:
            return self._log_buffer.copy()
    
    def clear_log_buffer(self) -> None:
        """Clear the log buffer."""
        with self._log_buffer_lock:
            self._log_buffer.clear()


# Global instance for convenience
_server_message_logger: Optional[ServerMessageLogger] = None


def get_server_message_logger(
    log_file_path: Optional[str] = None,
    async_mode: bool = True,
    log_level: int = logging.INFO,
    max_buffer_size: int = 1000,
    sanitize: bool = True
) -> ServerMessageLogger:
    """Get or create the global server message logger instance.
    
    Args:
        log_file_path: Optional path to the log file.
        async_mode: If True, use background thread for file writes.
        log_level: Minimum log level for message logging.
        max_buffer_size: Maximum entries in the in-memory log buffer.
        sanitize: If True, sanitize sensitive data before logging.
        
    Returns:
        ServerMessageLogger instance.
    """
    global _server_message_logger
    if _server_message_logger is None:
        _server_message_logger = ServerMessageLogger(
            log_file_path=log_file_path,
            async_mode=async_mode,
            log_level=log_level,
            max_buffer_size=max_buffer_size,
            sanitize=sanitize
        )
    return _server_message_logger


def reset_server_message_logger() -> None:
    """Reset the global server message logger instance."""
    global _server_message_logger
    if _server_message_logger is not None:
        _server_message_logger.stop_async_logging()
    _server_message_logger = None