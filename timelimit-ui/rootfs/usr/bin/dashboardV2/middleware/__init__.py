"""Middleware modules for dashboardV2.

This package contains middleware components including:
- request_logging: Flask request/response logging middleware with structured JSON logging
"""

from .request_logging import (
    RequestLoggingMiddleware,
    generate_request_id,
    get_request_id,
    init_request_logging,
    shutdown_log_worker,
)

__all__ = [
    "RequestLoggingMiddleware",
    "generate_request_id",
    "get_request_id",
    "init_request_logging",
    "shutdown_log_worker",
]