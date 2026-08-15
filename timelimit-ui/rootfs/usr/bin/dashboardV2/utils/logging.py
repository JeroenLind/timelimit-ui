"""Structured logging configuration using structlog.

This module provides structured JSON logging for the dashboardV2 application with:
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
from utils.log_rotation import generate_unique_log_path, cleanup_old_logs
from structlog.processors import (
    JSONRenderer,
    TimeStamper,
    add_log_level,
)
from structlog.stdlib import (
    add_log_level as stdlib_add_log_level,
    merge_contextvars,
    PositionalArgumentsFormatter,
    filter_by_level,
    BoundLogger,
    LoggerFactory,
)


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
        'mail_auth_token', 'mail_login_token',
        'parent_password_second_hash', 'parentpasswordsecondhash',
        'secret_key', 'jwt_secret', 'api_key', 'private_key',
        'signature', 'encrypted',
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


class _DynamicStdout:
    """A stream wrapper that always writes to the current ``sys.stdout``.

    Unlike passing ``sys.stdout`` directly to ``logging.StreamHandler``,
    this wrapper resolves ``sys.stdout`` at *write time* rather than at
    handler-creation time.  This is essential for two reasons:

    1. **Test compatibility** – tests that patch ``sys.stdout`` with
       ``unittest.mock.patch('sys.stdout', ...)`` will still capture
       output because the handler delegates to the *current*
       ``sys.stdout`` at emit time.
    2. **Runtime correctness** – if ``sys.stdout`` is replaced at
       runtime (e.g. by a WSGI server or test harness), the handler
       follows the replacement automatically.
    """

    def write(self, msg: str) -> int:
        return sys.stdout.write(msg)

    def flush(self) -> None:
        sys.stdout.flush()

    def __getattr__(self, name: str) -> Any:
        # Delegate any other attribute access to the current sys.stdout
        return getattr(sys.stdout, name)


def setup_structlog(
    log_level: str = None,
    log_file_path: str = None,
    log_max_bytes: int = None,
    log_backup_count: int = None,
    log_format: str = None,
    rotate_on_start: bool = None,
    werkzeug_log_file_path: str = None,
) -> None:
    """Configure structlog with the specified settings.
    
    Sets up structured logging with both console and file output.
    Uses JSON format by default for easy parsing and analysis.
    
    Environment variables (used as defaults if not provided):
        LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). Default: INFO
        LOG_FILE_PATH: Path to the structlog log file. Default: logs/dashboardV2.log
        LOG_MAX_BYTES: Maximum size of each log file in bytes. Default: 10485760 (10MB)
        LOG_BACKUP_COUNT: Number of backup log files to keep. Default: 5
        LOG_FORMAT: Output format ('json' or 'console'). Default: json
        LOG_ROTATE_ON_START: Rotate log file on startup. Default: true
        LOG_WERKZEUG_FILE_PATH: Path to the Werkzeug log file. Default: logs/werkzeug.log
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file_path: Path to the structlog log file.
        log_max_bytes: Maximum size of each log file in bytes.
        log_backup_count: Number of backup log files to keep.
        log_format: Output format ('json' or 'console').
        rotate_on_start: If True, create a new timestamped log file on each startup
            and clean up old log files. Default: True.
        werkzeug_log_file_path: Path to the Werkzeug log file (separate from structlog).
            If None, Werkzeug logs go to console only.
    """
    # Use environment variables as defaults if not provided
    log_level = log_level or os.environ.get('LOG_LEVEL', 'INFO')
    log_file_path = log_file_path or os.environ.get('LOG_FILE_PATH', 'logs/dashboardV2.log')
    log_max_bytes = log_max_bytes or int(os.environ.get('LOG_MAX_BYTES', '10485760'))
    log_backup_count = log_backup_count or int(os.environ.get('LOG_BACKUP_COUNT', '5'))
    log_format = log_format or os.environ.get('LOG_FORMAT', 'json')
    rotate_on_start = rotate_on_start if rotate_on_start is not None else os.environ.get('LOG_ROTATE_ON_START', 'true').lower() == 'true'
    werkzeug_log_file_path = werkzeug_log_file_path or os.environ.get('LOG_WERKZEUG_FILE_PATH', 'logs/werkzeug.log')

    # Store in module-level variables for runtime log level changes
    global _current_log_level, _log_format
    _current_log_level = log_level.upper()
    _log_format = log_format
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(log_file_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    
    # Startup-based log rotation: create a new timestamped log file
    # on each application start
    if rotate_on_start:
        log_file_path = generate_unique_log_path(log_dir, "dashboardV2")
    
    # Determine log level
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Configure standard library logging
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[],
    )
    
    # Get the root logger and clear any existing handlers.
    # The root logger receives structlog output (via LoggerFactory which
    # creates stdlib loggers that propagate to root).
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)
    
    # Add console handler (uses dynamic stdout so tests that patch
    # sys.stdout still capture output)
    console_handler = logging.StreamHandler(_DynamicStdout())
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(console_handler)
    
    # Add rotating file handler for structlog output
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=log_max_bytes,
        backupCount=log_backup_count,
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(file_handler)
    
    # Enforce retention policy after creating the new log file
    # (cleanup runs after file creation so the new file is included in the count)
    if rotate_on_start:
        max_log_files = int(os.environ.get('MAX_LOG_FILES', '10'))
        cleanup_old_logs(log_dir, max_files=max_log_files)
    
    # Configure Werkzeug logger separately so its output does not
    # mix with structlog JSON output in the same file.
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.handlers.clear()
    werkzeug_logger.propagate = False  # Prevent propagation to root logger
    werkzeug_logger.setLevel(level)
    
    # Werkzeug console handler
    werkzeug_console_handler = logging.StreamHandler(_DynamicStdout())
    werkzeug_console_handler.setLevel(level)
    werkzeug_console_handler.setFormatter(logging.Formatter("%(message)s"))
    werkzeug_logger.addHandler(werkzeug_console_handler)
    
    # Werkzeug file handler (separate file from structlog)
    if werkzeug_log_file_path:
        werkzeug_log_dir = os.path.dirname(werkzeug_log_file_path)
        if werkzeug_log_dir:
            os.makedirs(werkzeug_log_dir, exist_ok=True)
        werkzeug_file_handler = RotatingFileHandler(
            werkzeug_log_file_path,
            maxBytes=log_max_bytes,
            backupCount=log_backup_count,
        )
        werkzeug_file_handler.setLevel(level)
        werkzeug_file_handler.setFormatter(logging.Formatter("%(message)s"))
        werkzeug_logger.addHandler(werkzeug_file_handler)
    
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
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = None) -> Any:
    """Get a structlog logger instance.
    
    Args:
        name: Optional logger name. If None, returns the root logger.
        
    Returns:
        A structlog logger instance.
    """
    return structlog.get_logger(name)


# Module-level variables for runtime log level management
_current_log_level: str = 'INFO'
_log_format: str = 'json'

VALID_LOG_LEVELS = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}


def set_log_level(level: str) -> bool:
    """Set the log level at runtime.

    Updates the root logger, all handlers, structlog configuration,
    and the Werkzeug logger to the specified level.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).

    Returns:
        True if the level was set successfully, False if the level is invalid.
    """
    global _current_log_level

    level = level.upper()
    if level not in VALID_LOG_LEVELS:
        return False

    _current_log_level = level
    log_level_int = getattr(logging, level)

    # Update root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level_int)

    # Update all handlers on the root logger
    for handler in root_logger.handlers:
        handler.setLevel(log_level_int)

    # Update Werkzeug logger
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(log_level_int)
    for handler in werkzeug_logger.handlers:
        handler.setLevel(log_level_int)

    # Reconfigure structlog with the new level
    if _log_format == "console":
        processors = [
            merge_contextvars,
            stdlib_add_log_level,
            TimeStamper(fmt="iso", utc=True),
            PositionalArgumentsFormatter(),
            _sanitize_processor,
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        processors = [
            merge_contextvars,
            stdlib_add_log_level,
            PositionalArgumentsFormatter(),
            _sanitize_processor,
            TimeStamper(fmt="iso", utc=True),
            JSONRenderer(indent=None),
        ]

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(log_level_int),
        cache_logger_on_first_use=True,
    )

    # Clear structlog logger cache so new loggers use the updated level
    try:
        structlog._config._clear_all_caches()
    except (AttributeError, ImportError):
        pass

    return True


def get_log_level() -> str:
    """Get the current log level.

    Returns:
        The current log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    return _current_log_level


# Initialize logging when module is imported
setup_structlog()