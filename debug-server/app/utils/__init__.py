"""Utility modules for the debug server.

This package contains utility functions including:
- logger: Structured logging setup (structlog)
- gzip_utils: Gzip compression/decompression utilities
- helpers: General utility functions
"""

from app.utils.logger import get_logger, setup_structlog

__all__ = [
    "get_logger",
    "setup_structlog",
]