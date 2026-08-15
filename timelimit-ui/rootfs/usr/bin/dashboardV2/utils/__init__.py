"""Utility modules for dashboardV2 logging infrastructure.

This package provides:
- logging: Structlog configuration for structured JSON logging
- log_rotation: Log file rotation and retention management
- sanitization: Sensitive data sanitization for log records
"""

from .logging import setup_structlog, get_logger
from .log_rotation import (
    generate_timestamped_filename,
    generate_unique_log_path,
    get_log_files,
    rotate_log_files,
    cleanup_old_logs,
    get_log_files_info,
    DEFAULT_MAX_LOG_FILES,
    LOG_FILENAME_PATTERN,
)
from .sanitization import (
    SENSITIVE_KEYS,
    sanitize_dict,
    sanitize_processor,
)

__all__ = [
    # logging
    "setup_structlog",
    "get_logger",
    # log_rotation
    "generate_timestamped_filename",
    "generate_unique_log_path",
    "get_log_files",
    "rotate_log_files",
    "cleanup_old_logs",
    "get_log_files_info",
    "DEFAULT_MAX_LOG_FILES",
    "LOG_FILENAME_PATTERN",
    # sanitization
    "SENSITIVE_KEYS",
    "sanitize_dict",
    "sanitize_processor",
]