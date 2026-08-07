"""Request/response logging middleware for TimeLimit API.

This module provides structured logging for HTTP requests and responses,
including request ID generation, header sanitization, and timing information.
"""

import logging
import time
import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class RequestResponseLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses.
    
    Logs:
    - Incoming request: method, path, headers (sanitized), body size, client IP
    - Outgoing response: status code, response size, duration
    - Request ID for correlation
    """
    
    def __init__(self, app: ASGIApp):
        """Initialize the middleware.
        
        Args:
            app: The ASGI application.
        """
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and log it.
        
        Args:
            request: The incoming request.
            call_next: The next middleware or handler.
            
        Returns:
            The response.
        """
        # Generate request ID
        request_id = str(uuid.uuid4())
        
        # Log request start
        start_time = time.time()
        
        # Get client IP
        client_ip = self._get_client_ip(request)
        
        # Get sanitized headers
        sanitized_headers = self._sanitize_headers(request.headers)
        
        # Get request body size (if available)
        body_size = 0
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                body_size = len(body)
            except Exception:
                body_size = 0
        
        # Log request
        logger.info(
            "Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query": str(request.url.query),
                "client_ip": client_ip,
                "headers": sanitized_headers,
                "body_size": body_size,
            }
        )
        
        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            # Log exception
            logger.error(
                "Request failed with exception",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "exception": str(e),
                    "exception_type": type(e).__name__,
                }
            )
            raise
        
        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Get response size
        response_size = 0
        if hasattr(response, "body"):
            response_size = len(response.body) if response.body else 0
        
        # Log response
        logger.info(
            "Request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "response_size": response_size,
            }
        )
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Get the client IP address from the request.
        
        Args:
            request: The incoming request.
            
        Returns:
            Client IP address.
        """
        # Check for X-Forwarded-For header (behind proxy)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        # Check for X-Real-IP header
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Use client host
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _sanitize_headers(self, headers) -> dict:
        """Sanitize headers by removing sensitive data.
        
        Args:
            headers: The request headers.
            
        Returns:
            Sanitized headers dictionary.
        """
        sensitive_headers = {
            "authorization",
            "cookie",
            "x-auth-token",
            "x-api-key",
            "x-device-auth-token",
            "x-mail-auth-token",
            "x-mail-login-token",
            "x-identity-token",
            "x-secret-key",
            "x-password",
        }
        
        sanitized = {}
        for key, value in headers.items():
            if key.lower() in sensitive_headers:
                sanitized[key] = "***REDACTED***"
            else:
                sanitized[key] = value
        
        return sanitized


def get_request_id(request: Request) -> str:
    """Get the request ID from the response headers.
    
    Args:
        request: The request object.
        
    Returns:
        Request ID or empty string if not found.
    """
    # This would typically be stored in request state
    return request.state.get("request_id", "") if hasattr(request.state, "get") else ""