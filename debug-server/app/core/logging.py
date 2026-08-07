"""Logging configuration module.

This module provides backward-compatible logging setup that integrates
with the new structlog-based logger in app.utils.logger.

For new code, prefer using app.utils.logger.get_logger() directly.
"""

import logging
import sys
import os
from app.core.config import settings


def setup_logging() -> None:
    """Configure logging with both console and file output.
    
    This function provides backward compatibility for existing code
    that imports setup_logging from this module. For new code,
    prefer using app.utils.logger.setup_structlog() directly.
    
    Creates log directory if it doesn't exist.
    Configures both StreamHandler (stdout) and FileHandler.
    """
    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(settings.LOG_FILE_PATH)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(settings.LOG_FILE_PATH)
        ]
    )


# Initialize logging when module is imported
setup_logging()