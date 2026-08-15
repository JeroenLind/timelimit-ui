"""Logging configuration module.

This module provides backward-compatible logging setup that integrates
with the new structlog-based logger in app.utils.logger.

For new code, prefer using app.utils.logger.get_logger() directly.
"""

import logging
import sys
import os
from typing import Optional

from app.core.config import settings
from app.utils.log_rotation import (
    DEFAULT_MAX_LOG_FILES,
    ensure_log_directory,
    generate_unique_log_path,
    rotate_log_files,
)


# Global variable to store the current log file path
_current_log_file_path: Optional[str] = None


def _log_startup_message(log_file_path: str) -> None:
    """Write a startup log entry to the log file.
    
    Args:
        log_file_path: Path to the log file to write to.
    """
    from datetime import datetime
    
    # Get the root logger (which has the file handler configured)
    root_logger = logging.getLogger()
    
    # Write startup message
    timestamp = datetime.now().isoformat()
    root_logger.info("Debug server started")
    
    # Flush all handlers to ensure the message is written to the file
    for handler in root_logger.handlers:
        handler.flush()


def get_current_log_file_path() -> Optional[str]:
    """Get the current log file path.
    
    Returns:
        The current log file path or None if not set.
    """
    return _current_log_file_path


def setup_logging(
    log_level: Optional[str] = None,
    log_file_path: Optional[str] = None,
    max_log_files: int = DEFAULT_MAX_LOG_FILES,
) -> str:
    """Configure logging with both console and file output.
    
    This function:
    1. Creates a new timestamped log file on each server startup
    2. Rotates old log files, keeping only the most recent max_log_files
    3. Configures both StreamHandler (stdout) and FileHandler
    
    For backward compatibility, if log_file_path is provided, it will be used
    instead of generating a timestamped filename. However, retention policy
    is always applied to the log directory.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
                   Defaults to settings.LOG_LEVEL.
        log_file_path: Path to the log file. If None, generates a timestamped file.
        max_log_files: Maximum number of log files to retain (default: 10).
        
    Returns:
        The path to the log file that was created.
    """
    global _current_log_file_path
    
    # Use settings defaults if not provided
    log_level = log_level or settings.LOG_LEVEL
    
    # Determine log directory from settings or use default
    if log_file_path:
        # Use provided path (backward compatibility)
        log_dir = os.path.dirname(log_file_path)
        if log_dir:
            ensure_log_directory(log_dir)
        final_log_path = log_file_path
    else:
        # Generate timestamped log file path
        log_dir = "logs"
        final_log_path = generate_unique_log_path(log_dir, "debug-server")
    
    # Store the current log file path
    _current_log_file_path = final_log_path
    
    # Rotate old log files before creating new one
    # This ensures retention policy is always applied
    if log_dir:
        removed_files = rotate_log_files(log_dir, max_log_files)
        if removed_files:
            for removed_file in removed_files:
                print(f"[INFO] Removed old log file: {removed_file}")
    
    # Create logs directory if it doesn't exist
    log_dir_path = os.path.dirname(final_log_path)
    if log_dir_path:
        os.makedirs(log_dir_path, exist_ok=True)
    
    # Determine log level
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Get the root logger
    root_logger = logging.getLogger()
    
    # Set the level on the root logger
    root_logger.setLevel(level)
    
    # Clear any existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    root_logger.addHandler(console_handler)
    
    # Add file handler
    file_handler = logging.FileHandler(final_log_path)
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    root_logger.addHandler(file_handler)
    
    # Log startup information
    print(f"[INFO] Logging initialized with file: {final_log_path}")
    
    # Write startup log entry to the log file
    _log_startup_message(final_log_path)
    
    return final_log_path


def setup_structlog_compatible(
    log_level: Optional[str] = None,
    log_file_path: Optional[str] = None,
    max_log_files: int = DEFAULT_MAX_LOG_FILES,
) -> str:
    """Setup logging compatible with structlog configuration.
    
    This function provides the same functionality as setup_logging() but
    is designed to work with structlog-based applications.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file_path: Path to the log file. If None, generates a timestamped file.
        max_log_files: Maximum number of log files to retain (default: 10).
        
    Returns:
        The path to the log file that was created.
    """
    return setup_logging(log_level, log_file_path, max_log_files)