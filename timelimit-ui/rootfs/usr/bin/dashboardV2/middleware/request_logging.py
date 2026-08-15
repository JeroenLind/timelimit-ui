"""Flask request/response logging middleware for dashboardV2.

This module provides structured logging for HTTP requests and responses,
including request ID generation, header sanitization, and timing information.

Features:
- UUID-based request IDs (8 characters) stored in Flask's g object
- Structured JSON logging via structlog
- Sanitized headers (Authorization, cookies, tokens, etc.)
- Request/response size tracking
- Duration calculation in milliseconds
- Non-blocking async file writes via queue
"""

import json
import queue
import threading
import time
import uuid
from contextvars import ContextVar
from typing import Any, Callable, Dict, Optional

from flask import Flask, g, request, after_this_request
from werkzeug.wrappers import Response

from utils.sanitization import SENSITIVE_KEYS, sanitize_dict
from utils.logging import get_logger

# Context variable for request ID (for async contexts)
_request_id_ctx: ContextVar[Optional[str]] = ContextVar('request_id', default=None)

# Thread-safe queue for async logging
_log_queue: queue.Queue = queue.Queue()
_log_thread: Optional[threading.Thread] = None
_log_shutdown_event = threading.Event()


def _start_log_worker() -> None:
    """Start the background log worker thread for async writes."""
    global _log_thread
    
    if _log_thread is not None and _log_thread.is_alive():
        return
    
    def _log_worker():
        """Background worker that processes log entries from the queue."""
        logger = get_logger(__name__)
        while not _log_shutdown_event.is_set():
            try:
                # Get log entry with timeout to allow checking shutdown
                entry = _log_queue.get(timeout=0.1)
                if entry is None:
                    continue
                
                log_level = entry.get('level', 'info')
                message = entry.get('message', '')
                data = entry.get('data', {})
                
                # Log the entry
                getattr(logger, log_level)(message, **data)
                _log_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                # Log error but don't fail
                logger.error(f"Error in log worker: {e}")
    
    _log_thread = threading.Thread(target=_log_worker, daemon=True, name='log-worker')
    _log_thread.start()


def _queue_log(level: str, message: str, data: Dict[str, Any]) -> None:
    """Queue a log entry for async writing.
    
    Args:
        level: Log level (debug, info, warning, error, critical).
        message: Log message.
        data: Additional data to include in the log.
    """
    _log_queue.put({
        'level': level,
        'message': message,
        'data': data,
    })


def generate_request_id() -> str:
    """Generate a unique 8-character request ID.
    
    Uses UUID4 and takes the first 8 characters for a short, unique ID.
    
    Returns:
        8-character request ID string.
    """
    return str(uuid.uuid4())[:8]


def get_request_id() -> Optional[str]:
    """Get the current request ID from context.
    
    Returns:
        Current request ID or None if not in a request context.
    """
    # Try to get from context variable first (works outside Flask context)
    request_id = _request_id_ctx.get()
    if request_id:
        return request_id
    
    # Try to get from Flask's g object (only works within Flask context)
    try:
        return getattr(g, 'request_id', None)
    except RuntimeError:
        # Flask g object is not available outside of application context
        return None


def _get_client_ip() -> str:
    """Get the client IP address from the request.
    
    Checks X-Forwarded-For, X-Real-IP headers for proxy support,
    then falls back to the direct client IP.
    
    Returns:
        Client IP address string.
    """
    # Check for X-Forwarded-For header (behind proxy)
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    
    # Check for X-Real-IP header
    real_ip = request.headers.get('X-Real-IP')
    if real_ip:
        return real_ip
    
    # Use direct client IP
    if request.remote_addr:
        return request.remote_addr
    
    return 'unknown'


def _sanitize_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """Sanitize headers by redacting sensitive values.
    
    Args:
        headers: Dictionary of header names to values.
        
    Returns:
        Sanitized headers dictionary with sensitive values redacted.
    """
    sensitive_headers = {
        'authorization',
        'cookie',
        'x-auth-token',
        'x-api-key',
        'x-device-auth-token',
        'x-mail-auth-token',
        'x-mail-login-token',
        'x-identity-token',
        'x-secret-key',
        'x-password',
        'x-csrf-token',
    }
    
    sanitized = {}
    for key, value in headers.items():
        if key.lower() in sensitive_headers:
            sanitized[key] = '***REDACTED***'
        else:
            sanitized[key] = value
    
    return sanitized


def _get_request_body_size() -> int:
    """Get the size of the request body in bytes.
    
    For POST, PUT, PATCH, DELETE requests, reads the content length.
    For other methods, returns 0.
    
    Returns:
        Request body size in bytes.
    """
    if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
        try:
            # Try to get content length first (more efficient)
            content_length = request.content_length
            if content_length:
                return content_length
            
            # Fall back to reading the data
            if request.data:
                return len(request.data)
        except Exception:
            pass
    return 0


def _get_query_string() -> str:
    """Get the query string from the request.
    
    Returns:
        Query string with leading '?' or empty string if none.
    """
    if request.query_string:
        return f'?{request.query_string.decode("utf-8", errors="replace")}'
    return ''


class RequestLoggingMiddleware:
    """Flask middleware for structured request/response logging.
    
    This middleware logs:
    - Incoming requests: method, path, query string, client IP, headers (sanitized), body size
    - Outgoing responses: status code, response size, duration in milliseconds
    - Request ID for correlation (stored in Flask's g object and propagated via X-Request-ID header)
    
    Uses structlog for structured JSON logging with async queue-based writes.
    """
    
    def __init__(self, app: Flask):
        """Initialize the middleware.
        
        Args:
            app: The Flask application instance.
        """
        self.app = app
        self.logger = get_logger(__name__)
        
        # Start the async log worker
        _start_log_worker()
        
        # Register the middleware
        self._register_middleware()
    
    def _register_middleware(self) -> None:
        """Register the middleware with Flask's before/after request hooks."""
        
        @self.app.before_request
        def _before_request():
            """Process request before it reaches the handler."""
            # Generate request ID
            request_id = generate_request_id()
            
            # Store in Flask's g object
            g.request_id = request_id
            
            # Store in context variable for async access
            _request_id_ctx.set(request_id)
            
            # Record start time
            g._request_start_time = time.time()
            
            # Get client IP
            client_ip = _get_client_ip()
            
            # Get sanitized headers
            sanitized_headers = _sanitize_headers(dict(request.headers))
            
            # Get request body size
            body_size = _get_request_body_size()
            
            # Get query string
            query_string = _get_query_string()
            
            # Log the incoming request
            _queue_log(
                level='info',
                message='Request started',
                data={
                    'request_id': request_id,
                    'method': request.method,
                    'path': request.path,
                    'query': query_string,
                    'client_ip': client_ip,
                    'headers': sanitized_headers,
                    'body_size': body_size,
                }
            )
        
        @self.app.after_request
        def _after_request(response: Response) -> Response:
            """Process response after the handler completes."""
            # Get request ID from g object
            request_id = getattr(g, 'request_id', None)
            
            if request_id is None:
                # Generate one if not set
                request_id = generate_request_id()
                g.request_id = request_id
            
            # Calculate duration
            start_time = getattr(g, '_request_start_time', time.time())
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Get response size
            response_size = 0
            if hasattr(response, 'content_length') and response.content_length:
                response_size = response.content_length
            elif hasattr(response, 'data'):
                response_size = len(response.data) if response.data else 0
            
            # Add X-Request-ID header to response
            response.headers['X-Request-ID'] = request_id
            
            # Log the outgoing response
            _queue_log(
                level='info',
                message='Request completed',
                data={
                    'request_id': request_id,
                    'method': request.method,
                    'path': request.path,
                    'status_code': response.status_code,
                    'duration_ms': duration_ms,
                    'response_size': response_size,
                }
            )
            
            return response
    
    def __call__(self, environ, start_response):
        """WSGI callable for middleware.
        
        This allows the middleware to be used as WSGI middleware.
        
        Args:
            environ: WSGI environment dictionary.
            start_response: WSGI start_response callable.
            
        Returns:
            WSGI response iterator.
        """
        return self.app(environ, start_response)


def init_request_logging(app: Flask) -> RequestLoggingMiddleware:
    """Initialize request logging middleware for a Flask app.
    
    This is the recommended way to add request logging to a Flask application.
    
    Args:
        app: The Flask application instance.
        
    Returns:
        The RequestLoggingMiddleware instance.
        
    Example:
        >>> from flask import Flask
        >>> from dashboardV2.middleware import init_request_logging
        >>> 
        >>> app = Flask(__name__)
        >>> init_request_logging(app)
    """
    return RequestLoggingMiddleware(app)


def shutdown_log_worker() -> None:
    """Shutdown the async log worker thread.
    
    Call this during application shutdown to ensure all queued logs are processed.
    """
    _log_shutdown_event.set()
    if _log_thread is not None:
        _log_thread.join(timeout=2.0)