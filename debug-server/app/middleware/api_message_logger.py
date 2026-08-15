"""API message logging middleware for immediate request logging.

This middleware logs incoming API messages immediately upon receipt,
before any additional processing occurs. This ensures that all API
requests are captured in the log file with timestamp and message content.

Additionally, it logs server responses with comprehensive metadata including
timestamps, message content, and associated metadata for complete message flow visibility.
"""

import json
import logging
import time
from datetime import datetime
from typing import Callable, Optional, Any, Dict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.types import ASGIApp

from app.middleware.server_message_logger import (
    ServerMessageLogger,
    MessageType,
    get_server_message_logger,
    SENSITIVE_KEYS,
)

logger = logging.getLogger(__name__)


class APIMessageLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for immediate logging of incoming API messages and server responses.
    
    This middleware logs every incoming request to the designated logfile
    with a timestamp and message content BEFORE any additional processing occurs.
    It also logs server responses with comprehensive metadata for complete
    message flow visibility.
    
    Log format for requests:
    [YYYY-MM-DD HH:MM:SS.mmm] [API] {method} {path} - {body_content}
    
    Log format for responses:
    [YYYY-MM-DD HH:MM:SS.mmm] [SERVER] api_response - {metadata} - {content}
    """
    
    def __init__(self, app: ASGIApp, log_file_path: str = None):
        """Initialize the middleware.
        
        Args:
            app: The ASGI application.
            log_file_path: Optional path to the log file. If not provided,
                          uses the default log file path from settings.
        """
        super().__init__(app)
        self.log_file_path = log_file_path
        self._server_logger: Optional[ServerMessageLogger] = None
    
    def _get_server_logger(self) -> ServerMessageLogger:
        """Get or create the server message logger instance.
        
        Returns:
            ServerMessageLogger instance.
        """
        if self._server_logger is None:
            self._server_logger = get_server_message_logger(self.log_file_path)
        return self._server_logger
    
    def _sanitize_body(self, body: Any) -> Any:
        """Sanitize sensitive data from request/response bodies.
        
        Args:
            body: The body content to sanitize.
            
        Returns:
            Sanitized body with sensitive values replaced by ***REDACTED***.
        """
        if isinstance(body, dict):
            result = {}
            for key, value in body.items():
                if key.lower() in SENSITIVE_KEYS:
                    result[key] = '***REDACTED***'
                elif isinstance(value, dict):
                    result[key] = self._sanitize_body(value)
                elif isinstance(value, list):
                    result[key] = [self._sanitize_body(item) for item in value]
                elif isinstance(value, str) and len(value) > 500:
                    result[key] = value[:500] + '...[truncated]'
                else:
                    result[key] = value
            return result
        elif isinstance(body, list):
            return [self._sanitize_body(item) for item in body]
        else:
            return body
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and log it immediately.
        
        This method logs the incoming request BEFORE calling the next handler,
        ensuring the message is captured before any processing occurs.
        It also logs the server response after processing.
        
        Args:
            request: The incoming request.
            call_next: The next middleware or handler.
            
        Returns:
            The response from the next handler.
        """
        # Record start time for duration calculation
        start_time = time.time()
        request_id = self._generate_request_id()
        
        # Log the request immediately upon receipt
        request_info = await self._log_request_immediately(request)
        
        # Continue to the next handler
        try:
            response = await call_next(request)
        except Exception as e:
            # Log the error response
            duration_ms = int((time.time() - start_time) * 1000)
            self._log_error_response(e, request_info, request_id, duration_ms)
            raise
        
        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Capture response body before logging
        # The response body needs to be consumed from the iterator
        body_parts = []
        async for part in response.body_iterator:
            body_parts.append(part)
        
        # Set the body on the response for later access
        response._body = b''.join(body_parts)
        
        # Log the server response
        self._log_response(response, request_info, request_id, duration_ms)
        
        # Restore the body iterator as an async generator for the response to be sent
        async def body_iterator():
            yield response._body
        
        response.body_iterator = body_iterator()
        
        return response
    
    def _generate_request_id(self) -> str:
        """Generate a unique request ID for correlation.
        
        Returns:
            A unique request ID string.
        """
        import uuid
        return str(uuid.uuid4())[:8]
    
    async def _log_request_immediately(self, request: Request) -> dict:
        """Log the incoming request with timestamp and content.
        
        This method reads the request body and logs it immediately,
        before any other processing occurs. Sensitive data is sanitized.
        
        Args:
            request: The incoming request to log.
            
        Returns:
            Dictionary with request information for response logging.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        method = request.method
        path = request.url.path
        
        # Get query string if present
        query = f"?{request.url.query}" if request.url.query else ""
        
        # Read request body for POST, PUT, PATCH requests
        body_content = ""
        if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
            try:
                body = await request.body()
                if body:
                    body_str = body.decode("utf-8", errors="replace")
                    # Try to pretty-print JSON if it's valid JSON
                    try:
                        body_json = json.loads(body_str)
                        # Sanitize sensitive data before logging
                        sanitized_body = self._sanitize_body(body_json)
                        body_content = json.dumps(sanitized_body, indent=None, ensure_ascii=False)
                    except (json.JSONDecodeError, ValueError):
                        # Not JSON, use raw content (truncate if too long)
                        body_content = body_str[:1000] if len(body_str) > 1000 else body_str
            except Exception as e:
                body_content = f"[Error reading body: {str(e)}]"
        
        # Format the log message
        if body_content:
            log_message = f"[{timestamp}] [API] {method} {path}{query} - {body_content}"
        else:
            log_message = f"[{timestamp}] [API] {method} {path}{query}"
        
        # Log to the standard logger (which writes to file via handlers)
        logger.info(log_message)
        
        # Also write directly to the log file if a specific path is set
        if self.log_file_path:
            await self._write_to_log_file(log_message)
        
        return {
            "method": method,
            "path": path,
            "query": query,
            "body_content": body_content,
            "timestamp": timestamp,
        }
    
    def _log_response(
        self,
        response: Response,
        request_info: dict,
        request_id: str,
        duration_ms: int
    ) -> None:
        """Log the server response with comprehensive metadata.
        
        Args:
            response: The response to log.
            request_info: Dictionary with request information.
            request_id: The request ID for correlation.
            duration_ms: Request duration in milliseconds.
        """
        # Get response body
        response_body = self._get_response_body(response)
        
        # Log via server message logger
        server_logger = self._get_server_logger()
        server_logger.log_api_response(
            content=response_body,
            status_code=response.status_code,
            request_id=request_id,
            path=request_info["path"],
            method=request_info["method"],
            duration_ms=duration_ms
        )
    
    def _get_response_body(self, response: Response) -> Any:
        """Extract the response body from a Response object.
        
        Args:
            response: The response object.
            
        Returns:
            The response body content (sanitized if JSON).
        """
        # Use _body attribute which we set in dispatch()
        body = getattr(response, '_body', None)
        
        if body is None:
            # Fallback to response.body if _body is not set
            body = getattr(response, 'body', None)
        
        if body is None:
            return None
            
        if isinstance(response, JSONResponse):
            try:
                if isinstance(body, bytes):
                    parsed_body = json.loads(body.decode('utf-8', errors='replace'))
                    # Sanitize sensitive data before logging
                    return self._sanitize_body(parsed_body)
                return self._sanitize_body(body)
            except Exception:
                return str(body)
        
        if isinstance(body, bytes):
            try:
                parsed_body = body.decode('utf-8', errors='replace')
                # Try to parse as JSON for sanitization
                try:
                    json_body = json.loads(parsed_body)
                    return self._sanitize_body(json_body)
                except (json.JSONDecodeError, ValueError):
                    return parsed_body
            except Exception:
                return str(body)
        
        return self._sanitize_body(body)
    
    def _log_error_response(
        self,
        error: Exception,
        request_info: dict,
        request_id: str,
        duration_ms: int
    ) -> None:
        """Log an error response.
        
        Args:
            error: The exception that occurred.
            request_info: Dictionary with request information.
            request_id: The request ID for correlation.
            duration_ms: Request duration in milliseconds.
        """
        server_logger = self._get_server_logger()
        
        # Sanitize error content before logging
        error_content = {
            "error": str(error),
            "error_type": type(error).__name__
        }
        sanitized_error_content = self._sanitize_body(error_content)
        
        server_logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content=sanitized_error_content,
            metadata={
                "path": request_info["path"],
                "method": request_info["method"],
                "status_code": 500,
                "request_id": request_id,
                "duration_ms": duration_ms,
            },
            request_id=request_id,
            status_code=500,
            duration_ms=duration_ms
        )
    
    async def _write_to_log_file(self, message: str) -> None:
        """Write a message directly to the log file.
        
        This ensures the message is written to the designated logfile
        even if the standard logging handlers are not configured.
        
        Args:
            message: The message to write to the log file.
        """
        import os
        from pathlib import Path
        
        try:
            # Ensure the log directory exists
            log_dir = os.path.dirname(self.log_file_path)
            if log_dir:
                Path(log_dir).mkdir(parents=True, exist_ok=True)
            
            # Append to the log file
            with open(self.log_file_path, "a", encoding="utf-8") as f:
                f.write(message + "\n")
        except Exception as e:
            # Log the error but don't fail the request
            logger.error(f"Failed to write to log file: {e}")


def get_current_log_file_path() -> str:
    """Get the current log file path from the logging module.
    
    Returns:
        The current log file path or None if not set.
    """
    from app.core.logging import get_current_log_file_path as _get_path
    return _get_path()