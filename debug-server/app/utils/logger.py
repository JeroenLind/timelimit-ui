"""Structured logging configuration using structlog.

This module provides structured JSON logging for the debug server with:
- JSON output for easy parsing and analysis
- Console and file output support
- Log rotation with configurable max size and backup count
- Sanitization of sensitive data (passwords, tokens, etc.)
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Any, List

import structlog
from structlog.processors import (
    JSONRenderer,
    TimeStamper,
    add_log_level,
    merge_contextvars,
)
from structlog.stdlib import (
    add_log_level as stdlib_add_log_level,
    PositionalArgumentsFormatter,
    filter_by_level,
    bound_logger,
    get_logger,
    logger_factory,
    make_filtering_bound_logger,
    PositionalArgumentsFormatter,
)

from app.core.config import settings


def _sanitize_dict(data: dict) -> dict:
    """Sanitize sensitive data from log records.
    
    Removes or masks sensitive fields like passwords, tokens, and secrets.
    
    Args:
        data: Dictionary potentially containing sensitive data.
        
    Returns:
        Sanitized dictionary with sensitive data masked.
    """
    sensitive_keys = {
        'password', 'password_hash', 'second_hash', 'second_salt',
        'token', 'access_token', 'refresh_token', 'device_auth_token',
        'mail_auth_token', 'mail_login_token', 'secret_key', 'jwt_secret',
        'api_key', 'private_key', 'signature', 'encrypted',
    }
    
    result = {}
    for key, value in data.items():
        if key.lower() in sensitive_keys:
            result[key] = '***REDACTED***'
        elif isinstance(value, dict):
            result[key] = _sanitize_dict(value)
        elif isinstance(value, str) and len(value) > 50:
            # Truncate long strings to avoid log bloat
            result[key] = value[:50] + '...[truncated]'
        else:
            result[key] = value
    
    return result


def _sanitize_processor(_: Any, logger: Any, event_dict: dict) -> dict:
    """Processor to sanitize sensitive data in log events.
    
    Args:
        _: The event (unused).
        logger: The logger instance.
        event_dict: The event dictionary to sanitize.
        
    Returns:
        Sanitized event dictionary.
    """
    return _sanitize_dict(event_dict)


def setup_structlog(
    log_level: str = None,
    log_file_path: str = None,
    log_max_bytes: int = None,
    log_backup_count: int = None,
    log_format: str = None,
) -> None:
    """Configure structlog with the specified settings.
    
    Sets up structured logging with both console and file output.
    Uses JSON format by default for easy parsing and analysis.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file_path: Path to the log file.
        log_max_bytes: Maximum size of each log file in bytes.
        log_backup_count: Number of backup log files to keep.
        log_format: Output format ('json' or 'console').
    """
    # Use settings defaults if not provided
    log_level = log_level or settings.LOG_LEVEL
    log_file_path = log_file_path or settings.LOG_FILE_PATH
    log_max_bytes = log_max_bytes or settings.LOG_MAX_BYTES
    log_backup_count = log_backup_count or settings.LOG_BACKUP_COUNT
    log_format = log_format or settings.LOG_FORMAT
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(log_file_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    
    # Determine log level
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Configure standard library logging
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[],
    )
    
    # Get the root logger and clear any existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    
    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(console_handler)
    
    # Add rotating file handler
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=log_max_bytes,
        backupCount=log_backup_count,
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(file_handler)
    
    # Configure structlog processors
    processors: List[Any] = [
        merge_contextvars,
        stdlib_add_log_level,
        PositionalArgumentsFormatter(),
        _sanitize_processor,
        TimeStamper(fmt="iso", utc=True),
        JSONRenderer(indent=None) if log_format == "json" else logging.Formatter("%(message)s"),
    ]
    
    # For console output, use a different renderer
    if log_format == "console":
        processors = [
            merge_contextvars,
            stdlib_add_log_level,
            TimeStamper(fmt="iso", utc=True),
            PositionalArgumentsFormatter(),
            _sanitize_processor,
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=logger_factory,
        wrapper_class=make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = None) -> Any:
    """Get a structlog logger instance.
    
    Args:
        name: Optional logger name. If None, returns the root logger.
        
    Returns:
        A structlog logger instance.
    """
    return get_logger(name)


# Initialize logging when module is imported
setup_structlog()