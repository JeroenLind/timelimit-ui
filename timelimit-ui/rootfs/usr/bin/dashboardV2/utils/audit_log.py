"""Audit logging module for device removal operations.

This module provides audit logging functionality for device removal operations
with exact fidelity to the transmitted message. It preserves the original
structure, content, and encoding of requests for security analysis,
compliance audits, and forensic investigations.

Features:
- Complete request payload logging (not sanitized)
- Full header logging (not sanitized)
- Precise timestamps with microsecond precision
- User identifier tracking
- Dedicated audit log file with rotation
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Optional

import structlog
from structlog.processors import JSONRenderer, TimeStamper, add_log_level
from structlog.stdlib import merge_contextvars, PositionalArgumentsFormatter


# Default audit log file path
DEFAULT_AUDIT_LOG_PATH = 'logs/audit.log'

# Maximum size of each audit log file (10MB)
AUDIT_LOG_MAX_BYTES = 10485760

# Number of backup audit log files to keep
AUDIT_LOG_BACKUP_COUNT = 10


def _get_audit_logger(
    log_file_path: Optional[str] = None,
    log_level: str = 'INFO'
) -> structlog.BoundLogger:
    """Get or create the audit logger instance.
    
    Args:
        log_file_path: Path to the audit log file. Uses default if not provided.
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        
    Returns:
        A structlog BoundLogger instance configured for audit logging.
    """
    log_file_path = log_file_path or DEFAULT_AUDIT_LOG_PATH
    
    # Ensure log directory exists
    log_dir = os.path.dirname(log_file_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    
    # Create a separate structlog configuration for audit logging
    # that doesn't sanitize sensitive data
    processors = [
        merge_contextvars,
        add_log_level,
        PositionalArgumentsFormatter(),
        TimeStamper(fmt="iso", utc=True),
        JSONRenderer(indent=None),
    ]
    
    # Create a file handler for audit logs
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=AUDIT_LOG_MAX_BYTES,
        backupCount=AUDIT_LOG_BACKUP_COUNT,
    )
    file_handler.setLevel(getattr(logging, log_level.upper()))
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    
    # Create a logger factory that uses our handler
    class AuditLoggerFactory:
        def __init__(self):
            self._logger = None
            
        def __call__(self, name: str):
            if self._logger is None:
                self._logger = structlog.stdlib.LoggerFactory()(name)
                # Add our file handler
                self._logger.addHandler(file_handler)
            return self._logger
    
    # Configure structlog for audit logging
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=AuditLoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper())
        ),
        cache_logger_on_first_use=True,
    )
    
    return structlog.get_logger('audit')


# Module-level audit logger instance
_audit_logger: Optional[structlog.BoundLogger] = None


def get_audit_logger(log_file_path: Optional[str] = None) -> structlog.BoundLogger:
    """Get the audit logger instance, creating it if necessary.
    
    Args:
        log_file_path: Optional path to the audit log file.
        
    Returns:
        A structlog BoundLogger instance for audit logging.
    """
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = _get_audit_logger(log_file_path)
    return _audit_logger


def log_device_removal_request(
    device_id: str,
    parent_user_id: str,
    device_auth_token: str,
    parent_password_second_hash: str,
    request_payload: Dict[str, Any],
    request_headers: Dict[str, str],
    client_ip: Optional[str] = None,
    request_id: Optional[str] = None,
    server_url: Optional[str] = None,
    audit_log_path: Optional[str] = None
) -> None:
    """Log a device removal request with complete fidelity.
    
    This function logs all details of a device removal request including
    the complete payload, headers, timestamps, and user identifiers.
    The log preserves the original structure and encoding for forensic
    analysis.
    
    Args:
        device_id: The ID of the device being removed.
        parent_user_id: The ID of the parent user making the request.
        device_auth_token: The device auth token used for authentication.
        parent_password_second_hash: The parent's second password hash.
        request_payload: The complete request payload (will be logged as-is).
        request_headers: The complete request headers (will be logged as-is).
        client_ip: Optional client IP address.
        request_id: Optional request ID for correlation.
        server_url: Optional server URL being contacted.
        audit_log_path: Optional path to the audit log file.
    """
    logger = get_audit_logger(audit_log_path)
    
    # Get precise timestamp
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Build the audit log entry with exact fidelity
    # Note: 'event' is passed as the first positional argument to logger.info()
    # and the rest are passed as keyword arguments
    logger.info(
        'device_removal_request',
        timestamp=timestamp,
        timestamp_unix_ms=int(time.time() * 1000),
        device_id=device_id,
        parent_user_id=parent_user_id,
        device_auth_token=device_auth_token,
        parent_password_second_hash=parent_password_second_hash,
        request_payload=request_payload,
        request_headers=request_headers,
        client_ip=client_ip,
        request_id=request_id,
        server_url=server_url
    )


def log_device_removal_response(
    device_id: str,
    parent_user_id: str,
    request_id: Optional[str] = None,
    success: bool = True,
    status_code: Optional[int] = None,
    response_data: Optional[Dict[str, Any]] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    audit_log_path: Optional[str] = None
) -> None:
    """Log a device removal response with complete fidelity.
    
    This function logs the response from the server after a device removal
    request, preserving all details for audit purposes.
    
    Args:
        device_id: The ID of the device that was removed.
        parent_user_id: The ID of the parent user who made the request.
        request_id: Optional request ID for correlation.
        success: Whether the removal was successful.
        status_code: HTTP status code of the response.
        response_data: The complete response data (will be logged as-is).
        error_code: Error code if the request failed.
        error_message: Error message if the request failed.
        audit_log_path: Optional path to the audit log file.
    """
    logger = get_audit_logger(audit_log_path)
    
    # Get precise timestamp
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Build the audit log entry with exact fidelity
    if success:
        logger.info(
            'device_removal_response',
            timestamp=timestamp,
            timestamp_unix_ms=int(time.time() * 1000),
            device_id=device_id,
            parent_user_id=parent_user_id,
            success=success,
            status_code=status_code,
            response_data=response_data,
            request_id=request_id,
            error_code=error_code,
            error_message=error_message
        )
    else:
        logger.warning(
            'device_removal_response',
            timestamp=timestamp,
            timestamp_unix_ms=int(time.time() * 1000),
            device_id=device_id,
            parent_user_id=parent_user_id,
            success=success,
            status_code=status_code,
            response_data=response_data,
            request_id=request_id,
            error_code=error_code,
            error_message=error_message
        )


def log_device_removal_failure(
    device_id: str,
    parent_user_id: str,
    error_type: str,
    error_message: str,
    request_payload: Optional[Dict[str, Any]] = None,
    request_headers: Optional[Dict[str, str]] = None,
    request_id: Optional[str] = None,
    audit_log_path: Optional[str] = None
) -> None:
    """Log a device removal failure with complete details.
    
    This function logs failures in the device removal process, including
    validation errors, authentication failures, and server errors.
    
    Args:
        device_id: The ID of the device that was being removed.
        parent_user_id: The ID of the parent user who made the request.
        error_type: Type of error (e.g., 'validation', 'authentication', 'server').
        error_message: Description of the error.
        request_payload: The request payload that caused the error (if available).
        request_headers: The request headers (if available).
        request_id: Optional request ID for correlation.
        audit_log_path: Optional path to the audit log file.
    """
    logger = get_audit_logger(audit_log_path)
    
    # Get precise timestamp
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Build the audit log entry
    logger.error(
        'device_removal_failure',
        timestamp=timestamp,
        timestamp_unix_ms=int(time.time() * 1000),
        device_id=device_id,
        parent_user_id=parent_user_id,
        error_type=error_type,
        error_message=error_message,
        request_payload=request_payload,
        request_headers=request_headers,
        request_id=request_id
    )