"""Unit tests for logging configuration.

This module tests the logging setup functionality including handler configuration,
log file path, and log level settings.
"""

import logging
import os
import pytest
from app.core.logging import setup_logging
from app.core.config import settings


def test_setup_logging():
    """Verify that setup_logging() properly configures logging handlers.
    
    This test:
    - Calls setup_logging()
    - Verifies root logger has handlers
    - Verifies at least one StreamHandler exists
    - Verifies at least one FileHandler exists
    """
    # Call setup_logging to configure logging
    setup_logging()
    
    # Get the root logger
    root_logger = logging.getLogger()
    
    # Verify root logger has handlers
    assert root_logger.handlers is not None, "Root logger should have handlers"
    assert len(root_logger.handlers) > 0, "Root logger should have at least one handler"
    
    # Verify at least one StreamHandler exists
    stream_handlers = [h for h in root_logger.handlers if isinstance(h, logging.StreamHandler)]
    assert len(stream_handlers) > 0, "Root logger should have at least one StreamHandler"
    
    # Verify at least one FileHandler exists
    file_handlers = [h for h in root_logger.handlers if isinstance(h, logging.FileHandler)]
    assert len(file_handlers) > 0, "Root logger should have at least one FileHandler"


def test_log_file_path():
    """Verify that the log file path is correctly configured.
    
    This test:
    - Calls setup_logging()
    - Checks that logs/debug-server.log file path is used in FileHandler
    """
    # Call setup_logging to configure logging
    setup_logging()
    
    # Get the root logger
    root_logger = logging.getLogger()
    
    # Find the FileHandler
    file_handlers = [h for h in root_logger.handlers if isinstance(h, logging.FileHandler)]
    assert len(file_handlers) > 0, "Root logger should have at least one FileHandler"
    
    # Get the file path from the first FileHandler
    file_handler = file_handlers[0]
    log_file_path = file_handler.baseFilename
    
    # Verify the log file path matches settings
    # Normalize paths for comparison (handles Windows vs Unix path separators)
    expected_path = settings.LOG_FILE_PATH
    normalized_log_path = os.path.normpath(log_file_path)
    normalized_expected_path = os.path.normpath(expected_path)
    
    # Check that the expected path is in the log file path
    assert normalized_expected_path in normalized_log_path, \
        f"Log file path should contain '{expected_path}', got '{log_file_path}'"
    
    # Verify the expected log file path is used
    assert normalized_log_path.endswith(normalized_expected_path), \
        f"Log file path '{log_file_path}' should end with expected path '{expected_path}'"


def test_log_level():
    """Verify that the log level is correctly configured.
    
    This test:
    - Calls setup_logging()
    - Verifies root logger level matches settings.LOG_LEVEL
    """
    # Call setup_logging to configure logging
    setup_logging()
    
    # Get the root logger
    root_logger = logging.getLogger()
    
    # Get the expected log level from settings
    expected_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    
    # Verify root logger level matches settings
    assert root_logger.level == expected_level, \
        f"Root logger level should be {expected_level} ({settings.LOG_LEVEL}), got {root_logger.level}"