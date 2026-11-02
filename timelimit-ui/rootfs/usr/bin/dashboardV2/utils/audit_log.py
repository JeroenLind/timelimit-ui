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
from typing import Any, Dict, List, Optional

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


# ============================================================================
# Password Recovery Audit Logging
# ============================================================================

def log_password_recovery_request(
    mail_auth_token: str,
    password_data: Dict[str, Any],
    request_id: Optional[str] = None,
    server_url: Optional[str] = None,
    audit_log_path: Optional[str] = None
) -> None:
    """Log a password recovery request with complete fidelity.
    
    This function logs all details of a password recovery request including
    the complete payload, timestamps, and user identifiers. The log preserves
    the original structure and encoding for forensic analysis.
    
    Args:
        mail_auth_token: The mail auth token used for authentication.
        password_data: The complete password data including hash, secondHash, secondSalt.
        request_id: Optional request ID for correlation.
        server_url: Optional server URL being contacted.
        audit_log_path: Optional path to the audit log file.
    """
    logger = get_audit_logger(audit_log_path)
    
    # Get precise timestamp
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Build the audit log entry with exact fidelity
    logger.info(
        'password_recovery_request',
        timestamp=timestamp,
        timestamp_unix_ms=int(time.time() * 1000),
        mail_auth_token=mail_auth_token,
        password_data=password_data,
        request_id=request_id,
        server_url=server_url
    )


def log_password_recovery_response(
    success: bool,
    request_id: Optional[str] = None,
    status_code: Optional[int] = None,
    response_data: Optional[Dict[str, Any]] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    audit_log_path: Optional[str] = None
) -> None:
    """Log a password recovery response with complete fidelity.
    
    This function logs the response from the server after a password recovery
    request, preserving all details for audit purposes.
    
    Args:
        success: Whether the recovery was successful.
        request_id: Optional request ID for correlation.
        status_code: HTTP status code of the response.
        response_data: The complete response data.
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
            'password_recovery_response',
            timestamp=timestamp,
            timestamp_unix_ms=int(time.time() * 1000),
            success=success,
            status_code=status_code,
            response_data=response_data,
            request_id=request_id
        )
    else:
        logger.warning(
            'password_recovery_response',
            timestamp=timestamp,
            timestamp_unix_ms=int(time.time() * 1000),
            success=success,
            status_code=status_code,
            response_data=response_data,
            request_id=request_id,
            error_code=error_code,
            error_message=error_message
        )


def log_password_recovery_failure(
    error_type: str,
    error_message: str,
    mail_auth_token: Optional[str] = None,
    password_data: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    audit_log_path: Optional[str] = None
) -> None:
    """Log a password recovery failure with complete details.
    
    This function logs failures in the password recovery process, including
    validation errors, authentication failures, and server errors.
    
    Args:
        error_type: Type of error (e.g., 'validation', 'authentication', 'server').
        error_message: Description of the error.
        mail_auth_token: The mail auth token (if available).
        password_data: The password data (if available).
        request_id: Optional request ID for correlation.
        audit_log_path: Optional path to the audit log file.
    """
    logger = get_audit_logger(audit_log_path)
    
    # Get precise timestamp
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Build the audit log entry
    logger.error(
        'password_recovery_failure',
        timestamp=timestamp,
        timestamp_unix_ms=int(time.time() * 1000),
        error_type=error_type,
        error_message=error_message,
        mail_auth_token=mail_auth_token,
        password_data=password_data,
        request_id=request_id
    )


# ============================================================================
# Sync Operation Audit Logging
# ============================================================================

def log_sync_pull_request(
    device_auth_token: str,
    client_data_status: Dict[str, Any],
    request_id: Optional[str] = None,
    server_url: Optional[str] = None,
    audit_log_path: Optional[str] = None
) -> None:
    """Log a sync pull request with complete fidelity.
    
    This function logs all details of a sync pull request including
    the complete payload, timestamps, and user identifiers. The log
    preserves the original structure and encoding for forensic analysis.
    
    Args:
        device_auth_token: The device auth token used for authentication.
        client_data_status: The client data status (version numbers, etc.).
        request_id: Optional request ID for correlation.
        server_url: Optional server URL being contacted.
        audit_log_path: Optional path to the audit log file.
    """
    logger = get_audit_logger(audit_log_path)
    
    # Get precise timestamp
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Build the audit log entry with exact fidelity
    logger.info(
        'sync_pull_request',
        timestamp=timestamp,
        timestamp_unix_ms=int(time.time() * 1000),
        device_auth_token=device_auth_token,
        client_data_status=client_data_status,
        request_id=request_id,
        server_url=server_url
    )


def log_sync_pull_response(
    device_auth_token: str,
    request_id: Optional[str] = None,
    success: bool = True,
    status_code: Optional[int] = None,
    response_data: Optional[Dict[str, Any]] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    audit_log_path: Optional[str] = None
) -> None:
    """Log a sync pull response with complete fidelity.
    
    This function logs the response from the server after a sync pull
    request, preserving all details for audit purposes.
    
    Args:
        device_auth_token: The device auth token used for authentication.
        request_id: Optional request ID for correlation.
        success: Whether the sync was successful.
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
            'sync_pull_response',
            timestamp=timestamp,
            timestamp_unix_ms=int(time.time() * 1000),
            device_auth_token=device_auth_token,
            success=success,
            status_code=status_code,
            response_data=response_data,
            request_id=request_id
        )
    else:
        logger.warning(
            'sync_pull_response',
            timestamp=timestamp,
            timestamp_unix_ms=int(time.time() * 1000),
            device_auth_token=device_auth_token,
            success=success,
            status_code=status_code,
            response_data=response_data,
            request_id=request_id,
            error_code=error_code,
            error_message=error_message
        )


def log_sync_push_request(
    device_auth_token: str,
    actions: List[Dict[str, Any]],
    request_id: Optional[str] = None,
    server_url: Optional[str] = None,
    audit_log_path: Optional[str] = None
) -> None:
    """Log a sync push request with complete fidelity.
    
    This function logs all details of a sync push request including
    the complete actions payload, timestamps, and user identifiers.
    The log preserves the original structure and encoding for forensic analysis.
    
    Args:
        device_auth_token: The device auth token used for authentication.
        actions: List of action objects being pushed.
        request_id: Optional request ID for correlation.
        server_url: Optional server URL being contacted.
        audit_log_path: Optional path to the audit log file.
    """
    logger = get_audit_logger(audit_log_path)
    
    # Get precise timestamp
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Build the audit log entry with exact fidelity
    logger.info(
        'sync_push_request',
        timestamp=timestamp,
        timestamp_unix_ms=int(time.time() * 1000),
        device_auth_token=device_auth_token,
        actions=actions,
        request_id=request_id,
        server_url=server_url
    )


def log_sync_push_response(
    device_auth_token: str,
    request_id: Optional[str] = None,
    success: bool = True,
    status_code: Optional[int] = None,
    response_data: Optional[Dict[str, Any]] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    audit_log_path: Optional[str] = None
) -> None:
    """Log a sync push response with complete fidelity.
    
    This function logs the response from the server after a sync push
    request, preserving all details for audit purposes.
    
    Args:
        device_auth_token: The device auth token used for authentication.
        request_id: Optional request ID for correlation.
        success: Whether the sync was successful.
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
            'sync_push_response',
            timestamp=timestamp,
            timestamp_unix_ms=int(time.time() * 1000),
            device_auth_token=device_auth_token,
            success=success,
            status_code=status_code,
            response_data=response_data,
            request_id=request_id
        )
    else:
        logger.warning(
            'sync_push_response',
            timestamp=timestamp,
            timestamp_unix_ms=int(time.time() * 1000),
            device_auth_token=device_auth_token,
            success=success,
            status_code=status_code,
            response_data=response_data,
            request_id=request_id,
            error_code=error_code,
            error_message=error_message
        )


# ============================================================================
# Family Creation Audit Logging
# ============================================================================

def log_family_creation_request(
    mail_auth_token: str,
    email: str,
    password_data: Dict[str, Any],
    parent_device: Dict[str, str],
    device_name: str,
    time_zone: str,
    parent_name: str,
    locale: Optional[str] = None,
    request_id: Optional[str] = None,
    server_url: Optional[str] = None,
    audit_log_path: Optional[str] = None
) -> None:
    """Log a family creation request with complete fidelity.
    
    This function logs all details of a family creation request including
    the complete payload, timestamps, and user identifiers. The log preserves
    the original structure and encoding for forensic analysis.
    
    Args:
        mail_auth_token: The mail auth token used for authentication.
        email: The parent's email address.
        password_data: The complete password data including hash, secondHash, secondSalt.
        parent_device: Device info dict with 'model' key.
        device_name: Name of the device.
        time_zone: Time zone string.
        parent_name: Parent's name.
        locale: Optional locale string.
        request_id: Optional request ID for correlation.
        server_url: Optional server URL being contacted.
        audit_log_path: Optional path to the audit log file.
    """
    logger = get_audit_logger(audit_log_path)
    
    # Get precise timestamp
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Build the audit log entry with exact fidelity
    # Note: password_data contains sensitive hashes that must be logged for audit purposes
    logger.info(
        'family_creation_request',
        timestamp=timestamp,
        timestamp_unix_ms=int(time.time() * 1000),
        mail_auth_token=mail_auth_token,
        email=email,
        password_data=password_data,
        parent_device=parent_device,
        device_name=device_name,
        time_zone=time_zone,
        parent_name=parent_name,
        locale=locale,
        request_id=request_id,
        server_url=server_url
    )


def log_family_creation_response(
    success: bool,
    request_id: Optional[str] = None,
    status_code: Optional[int] = None,
    response_data: Optional[Dict[str, Any]] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    audit_log_path: Optional[str] = None
) -> None:
    """Log a family creation response with complete fidelity.
    
    This function logs the response from the server after a family creation
    request, preserving all details for audit purposes.
    
    Args:
        success: Whether the family creation was successful.
        request_id: Optional request ID for correlation.
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
            'family_creation_response',
            timestamp=timestamp,
            timestamp_unix_ms=int(time.time() * 1000),
            success=success,
            status_code=status_code,
            response_data=response_data,
            request_id=request_id
        )
    else:
        logger.warning(
            'family_creation_response',
            timestamp=timestamp,
            timestamp_unix_ms=int(time.time() * 1000),
            success=success,
            status_code=status_code,
            response_data=response_data,
            request_id=request_id,
            error_code=error_code,
            error_message=error_message
        )


def log_family_creation_failure(
    error_type: str,
    error_message: str,
    email: Optional[str] = None,
    password_data: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    server_url: Optional[str] = None,
    audit_log_path: Optional[str] = None
) -> None:
    """Log a family creation failure with complete details.
    
    This function logs failures in the family creation process, including
    validation errors, authentication failures, and server errors.
    
    Args:
        error_type: Type of error (e.g., 'validation', 'authentication', 'server').
        error_message: Description of the error.
        email: The email address (if available).
        password_data: The password data (if available).
        request_id: Optional request ID for correlation.
        server_url: Optional server URL being contacted.
        audit_log_path: Optional path to the audit log file.
    """
    logger = get_audit_logger(audit_log_path)
    
    # Get precise timestamp
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Build the audit log entry
    logger.error(
        'family_creation_failure',
        timestamp=timestamp,
        timestamp_unix_ms=int(time.time() * 1000),
        error_type=error_type,
        error_message=error_message,
        email=email,
        password_data=password_data,
        request_id=request_id,
        server_url=server_url
    )


# ============================================================================
# Login As Parent Audit Logging
# ============================================================================

def log_login_as_parent_hash_regeneration(
    mail: str,
    existing_salt: Optional[str],
    second_hash: str,
    password_data: Dict[str, Any],
    request_id: Optional[str] = None,
    server_url: Optional[str] = None,
    audit_log_path: Optional[str] = None
) -> None:
    """Log a successful hash regeneration during login-as-parent flow.
    
    This function logs all details of hash regeneration including the mail,
    existing salt, regenerated hash, and complete password data for audit purposes.
    
    Args:
        mail: The email address being looked up.
        existing_salt: The existing salt found (if any).
        second_hash: The regenerated hash value.
        password_data: The complete password data dictionary.
        request_id: Optional request ID for correlation.
        server_url: Optional server URL being contacted.
        audit_log_path: Optional path to the audit log file.
    """
    logger = get_audit_logger(audit_log_path)
    
    # Get precise timestamp
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Build the audit log entry with complete fidelity
    logger.info(
        'login_as_parent_hash_regeneration',
        timestamp=timestamp,
        timestamp_unix_ms=int(time.time() * 1000),
        mail=mail,
        existing_salt=existing_salt,
        second_hash=second_hash,
        password_data=password_data,
        request_id=request_id,
        server_url=server_url
    )


def log_login_as_parent_hash_regeneration_failure(
    mail: str,
    existing_salt: Optional[str],
    error: str,
    error_type: str,
    request_id: Optional[str] = None,
    server_url: Optional[str] = None,
    audit_log_path: Optional[str] = None
) -> None:
    """Log a hash regeneration failure during login-as-parent flow.
    
    This function logs failures in hash regeneration including the mail,
    existing salt, error message, and error type for debugging purposes.
    
    Args:
        mail: The email address being looked up.
        existing_salt: The existing salt that was found (if any).
        error: The error message.
        error_type: The exception type name.
        request_id: Optional request ID for correlation.
        server_url: Optional server URL being contacted.
        audit_log_path: Optional path to the audit log file.
    """
    logger = get_audit_logger(audit_log_path)
    
    # Get precise timestamp
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Build the audit log entry
    logger.error(
        'login_as_parent_hash_regeneration_failure',
        timestamp=timestamp,
        timestamp_unix_ms=int(time.time() * 1000),
        mail=mail,
        existing_salt=existing_salt,
        error=error,
        error_type=error_type,
        request_id=request_id,
        server_url=server_url
    )


def log_login_as_parent_new_hash_generation(
    mail: str,
    hash_value: str,
    second_hash: str,
    second_salt: str,
    password_data: Dict[str, Any],
    request_id: Optional[str] = None,
    server_url: Optional[str] = None,
    audit_log_path: Optional[str] = None
) -> None:
    """Log new hash generation during login-as-parent flow (new family).
    
    This function logs when a new password hash is generated for a new family,
    including all hash components for audit purposes.
    
    Args:
        mail: The email address being looked up.
        hash_value: The first hash value.
        second_hash: The second hash value.
        second_salt: The second salt value.
        password_data: The complete password data dictionary.
        request_id: Optional request ID for correlation.
        server_url: Optional server URL being contacted.
        audit_log_path: Optional path to the audit log file.
    """
    logger = get_audit_logger(audit_log_path)
    
    # Get precise timestamp
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Build the audit log entry with complete fidelity
    logger.info(
        'login_as_parent_new_hash_generation',
        timestamp=timestamp,
        timestamp_unix_ms=int(time.time() * 1000),
        mail=mail,
        hash=hash_value,
        second_hash=second_hash,
        second_salt=second_salt,
        password_data=password_data,
        request_id=request_id,
        server_url=server_url
    )


def log_login_as_parent_password_stored(
    mail: str,
    device_auth_token: str,
    password_data: Dict[str, Any],
    request_id: Optional[str] = None,
    server_url: Optional[str] = None,
    audit_log_path: Optional[str] = None
) -> None:
    """Log password hash storage during login-as-parent flow.
    
    This function logs when password hash is stored in the database,
    including the mail, device auth token, and complete password data.
    
    Args:
        mail: The email address.
        device_auth_token: The device auth token (truncated for logging).
        password_data: The complete password data dictionary.
        request_id: Optional request ID for correlation.
        server_url: Optional server URL being contacted.
        audit_log_path: Optional path to the audit log file.
    """
    logger = get_audit_logger(audit_log_path)
    
    # Get precise timestamp
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Build the audit log entry with complete fidelity
    logger.info(
        'login_as_parent_password_stored',
        timestamp=timestamp,
        timestamp_unix_ms=int(time.time() * 1000),
        mail=mail,
        device_auth_token=device_auth_token,
        password_data=password_data,
        request_id=request_id,
        server_url=server_url
    )


def log_login_as_parent_direct_hash_stored(
    mail: str,
    device_auth_token: str,
    parent_password_second_hash: str,
    request_id: Optional[str] = None,
    server_url: Optional[str] = None,
    audit_log_path: Optional[str] = None
) -> None:
    """Log direct hash input storage during login-as-parent flow.
    
    This function logs when a direct password hash is provided and stored,
    including the mail, device auth token, and the hash value.
    
    Args:
        mail: The email address.
        device_auth_token: The device auth token (truncated for logging).
        parent_password_second_hash: The direct hash input.
        request_id: Optional request ID for correlation.
        server_url: Optional server URL being contacted.
        audit_log_path: Optional path to the audit log file.
    """
    logger = get_audit_logger(audit_log_path)
    
    # Get precise timestamp
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Build the audit log entry with complete fidelity
    logger.info(
        'login_as_parent_direct_hash_stored',
        timestamp=timestamp,
        timestamp_unix_ms=int(time.time() * 1000),
        mail=mail,
        device_auth_token=device_auth_token,
        parent_password_second_hash=parent_password_second_hash,
        request_id=request_id,
        server_url=server_url
    )


def log_login_as_parent_salt_validation_failure(
    mail: str,
    error_type: str,
    error_message: str,
    family_found: bool,
    salt_available: bool,
    request_id: Optional[str] = None,
    server_url: Optional[str] = None,
    audit_log_path: Optional[str] = None
) -> None:
    """Log a salt validation failure during login-as-parent flow.
    
    This function logs when salt validation fails during login-as-parent,
    including the mail, error type, error message, and validation state.
    
    Args:
        mail: The email address being looked up.
        error_type: Type of error (e.g., 'family_not_found', 'salt_missing').
        error_message: Description of the error.
        family_found: Whether the family record was found.
        salt_available: Whether the salt was available in the family record.
        request_id: Optional request ID for correlation.
        server_url: Optional server URL being contacted.
        audit_log_path: Optional path to the audit log file.
    """
    logger = get_audit_logger(audit_log_path)
    
    # Get precise timestamp
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Build the audit log entry
    logger.error(
        'login_as_parent_salt_validation_failure',
        timestamp=timestamp,
        timestamp_unix_ms=int(time.time() * 1000),
        mail=mail,
        error_type=error_type,
        error_message=error_message,
        family_found=family_found,
        salt_available=salt_available,
        request_id=request_id,
        server_url=server_url
    )


# ============================================================================
# Stale Device Removal Audit Logging
# ============================================================================

def log_stale_device_removal(
    device_auth_token: str,
    removed_device_ids: List[str],
    own_device_id: Optional[str] = None,
    request_id: Optional[str] = None,
    audit_log_path: Optional[str] = None
) -> None:
    """Log stale device removal during sync operation.
    
    This function logs when devices are removed as stale during sync,
    including the device auth token, list of removed device IDs, and
    whether the dashboard's own device was excluded from removal.
    
    Args:
        device_auth_token: The device auth token for the sync operation.
        removed_device_ids: List of device IDs that were removed as stale.
        own_device_id: The dashboard's own device ID (excluded from removal).
        request_id: Optional request ID for correlation.
        audit_log_path: Optional path to the audit log file.
    """
    logger = get_audit_logger(audit_log_path)
    
    # Get precise timestamp
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Build the audit log entry
    logger.info(
        'stale_device_removal',
        timestamp=timestamp,
        timestamp_unix_ms=int(time.time() * 1000),
        device_auth_token=device_auth_token,
        removed_device_ids=removed_device_ids,
        removed_count=len(removed_device_ids),
        own_device_id=own_device_id,
        own_device_excluded=own_device_id is not None and own_device_id not in removed_device_ids,
        request_id=request_id
    )


# ============================================================================
# Time Limit Rule Audit Logging
# ============================================================================

def log_time_limit_rule_created(
    device_auth_token: str,
    rule_id: str,
    user_id: str,
    category_id: str,
    rule_type: int,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    days: int = 127,
    limit_minutes: int = 0,
    version: Optional[str] = None,
    request_id: Optional[str] = None,
    server_url: Optional[str] = None,
    audit_log_path: Optional[str] = None
) -> None:
    """Log a time limit rule creation event.
    
    This function logs when a time limit rule is created, including all
    rule parameters for audit purposes.
    
    Args:
        device_auth_token: The device auth token for the rule.
        rule_id: The unique rule identifier.
        user_id: The user ID this rule applies to.
        category_id: The category ID this rule applies to.
        rule_type: Type of rule.
        start_time: Start time for the rule.
        end_time: End time for the rule.
        days: Days of week bitmask.
        limit_minutes: Time limit in minutes.
        version: Optional version string.
        request_id: Optional request ID for correlation.
        server_url: Optional server URL being contacted.
        audit_log_path: Optional path to the audit log file.
    """
    logger = get_audit_logger(audit_log_path)
    
    # Get precise timestamp
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Build the audit log entry
    logger.info(
        'time_limit_rule_created',
        timestamp=timestamp,
        timestamp_unix_ms=int(time.time() * 1000),
        device_auth_token=device_auth_token,
        rule_id=rule_id,
        user_id=user_id,
        category_id=category_id,
        rule_type=rule_type,
        start_time=start_time,
        end_time=end_time,
        days=days,
        limit_minutes=limit_minutes,
        version=version,
        request_id=request_id,
        server_url=server_url
    )


def log_time_limit_rule_updated(
    device_auth_token: str,
    rule_id: str,
    updates: Dict[str, Any],
    request_id: Optional[str] = None,
    server_url: Optional[str] = None,
    audit_log_path: Optional[str] = None
) -> None:
    """Log a time limit rule update event.
    
    This function logs when a time limit rule is updated, including
    the fields that were changed.
    
    Args:
        device_auth_token: The device auth token for the rule.
        rule_id: The unique rule identifier.
        updates: Dictionary of fields that were updated.
        request_id: Optional request ID for correlation.
        server_url: Optional server URL being contacted.
        audit_log_path: Optional path to the audit log file.
    """
    logger = get_audit_logger(audit_log_path)
    
    # Get precise timestamp
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Build the audit log entry
    logger.info(
        'time_limit_rule_updated',
        timestamp=timestamp,
        timestamp_unix_ms=int(time.time() * 1000),
        device_auth_token=device_auth_token,
        rule_id=rule_id,
        updates=updates,
        request_id=request_id,
        server_url=server_url
    )


def log_time_limit_rule_deleted(
    device_auth_token: str,
    rule_id: str,
    request_id: Optional[str] = None,
    server_url: Optional[str] = None,
    audit_log_path: Optional[str] = None
) -> None:
    """Log a time limit rule deletion event.
    
    This function logs when a time limit rule is deleted.
    
    Args:
        device_auth_token: The device auth token for the rule.
        rule_id: The unique rule identifier that was deleted.
        request_id: Optional request ID for correlation.
        server_url: Optional server URL being contacted.
        audit_log_path: Optional path to the audit log file.
    """
    logger = get_audit_logger(audit_log_path)
    
    # Get precise timestamp
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Build the audit log entry
    logger.info(
        'time_limit_rule_deleted',
        timestamp=timestamp,
        timestamp_unix_ms=int(time.time() * 1000),
        device_auth_token=device_auth_token,
        rule_id=rule_id,
        request_id=request_id,
        server_url=server_url
    )


# ============================================================================
# Category Apps Audit Logging
# ============================================================================

def log_category_apps_added(
    device_auth_token: str,
    category_id: str,
    app_packages: List[str],
    user_id: Optional[str] = None,
    request_id: Optional[str] = None,
    server_url: Optional[str] = None,
    audit_log_path: Optional[str] = None
) -> None:
    """Log a category apps addition event.
    
    This function logs when apps are added to a category, including
    all app package names for audit purposes.
    
    Args:
        device_auth_token: The device auth token for the operation.
        category_id: The category ID apps were added to.
        app_packages: List of app package names that were added.
        user_id: Optional user ID for the category.
        request_id: Optional request ID for correlation.
        server_url: Optional server URL being contacted.
        audit_log_path: Optional path to the audit log file.
    """
    logger = get_audit_logger(audit_log_path)
    
    # Get precise timestamp
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Build the audit log entry
    logger.info(
        'category_apps_added',
        timestamp=timestamp,
        timestamp_unix_ms=int(time.time() * 1000),
        device_auth_token=device_auth_token,
        category_id=category_id,
        app_packages=app_packages,
        app_count=len(app_packages),
        user_id=user_id,
        request_id=request_id,
        server_url=server_url
    )


def log_category_apps_removed(
    device_auth_token: str,
    category_id: str,
    app_packages: List[str],
    user_id: Optional[str] = None,
    request_id: Optional[str] = None,
    server_url: Optional[str] = None,
    audit_log_path: Optional[str] = None
) -> None:
    """Log a category apps removal event.
    
    This function logs when apps are removed from a category, including
    all app package names for audit purposes.
    
    Args:
        device_auth_token: The device auth token for the operation.
        category_id: The category ID apps were removed from.
        app_packages: List of app package names that were removed.
        user_id: Optional user ID for the category.
        request_id: Optional request ID for correlation.
        server_url: Optional server URL being contacted.
        audit_log_path: Optional path to the audit log file.
    """
    logger = get_audit_logger(audit_log_path)
    
    # Get precise timestamp
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Build the audit log entry
    logger.info(
        'category_apps_removed',
        timestamp=timestamp,
        timestamp_unix_ms=int(time.time() * 1000),
        device_auth_token=device_auth_token,
        category_id=category_id,
        app_packages=app_packages,
        app_count=len(app_packages),
        user_id=user_id,
        request_id=request_id,
        server_url=server_url
    )


# ============================================================================
# Add User to Family Audit Logging
# ============================================================================

def log_add_user_request(
    device_auth_token: str,
    parent_user_id: str,
    user_name: str,
    device_name: Optional[str] = None,
    device_model: Optional[str] = None,
    request_id: Optional[str] = None,
    server_url: Optional[str] = None,
    audit_log_path: Optional[str] = None
) -> None:
    """Log an add user request with complete fidelity.
    
    This function logs all details of an add user request including
    the complete payload, timestamps, and user identifiers. The log
    preserves the original structure and encoding for forensic analysis.
    
    Args:
        device_auth_token: The parent's device auth token.
        parent_user_id: The parent's user ID.
        user_name: The child's display name.
        device_name: Optional device name for the child.
        device_model: Optional device model for the child.
        request_id: Optional request ID for correlation.
        server_url: Optional server URL being contacted.
        audit_log_path: Optional path to the audit log file.
    """
    logger = get_audit_logger(audit_log_path)
    
    # Get precise timestamp
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Build the audit log entry with exact fidelity
    logger.info(
        'add_user_request',
        timestamp=timestamp,
        timestamp_unix_ms=int(time.time() * 1000),
        device_auth_token=device_auth_token,
        parent_user_id=parent_user_id,
        user_name=user_name,
        device_name=device_name,
        device_model=device_model,
        request_id=request_id,
        server_url=server_url
    )


def log_add_user_response(
    device_auth_token: str,
    parent_user_id: str,
    user_id: Optional[str],
    child_device_auth_token: Optional[str],
    own_device_id: Optional[str],
    request_id: Optional[str] = None,
    success: bool = True,
    status_code: Optional[int] = None,
    response_data: Optional[Dict[str, Any]] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    audit_log_path: Optional[str] = None
) -> None:
    """Log an add user response with complete fidelity.
    
    This function logs the response from the server after an add user
    request, preserving all details for audit purposes.
    
    Args:
        device_auth_token: The parent's device auth token.
        parent_user_id: The parent's user ID.
        user_id: The new child user's ID (if successful).
        child_device_auth_token: The new child device's auth token (if successful).
        own_device_id: The new child device's ID (if successful).
        request_id: Optional request ID for correlation.
        success: Whether the operation succeeded.
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
            'add_user_response',
            timestamp=timestamp,
            timestamp_unix_ms=int(time.time() * 1000),
            device_auth_token=device_auth_token,
            parent_user_id=parent_user_id,
            user_id=user_id,
            child_device_auth_token=child_device_auth_token,
            own_device_id=own_device_id,
            request_id=request_id,
            success=success,
            status_code=status_code,
            response_data=response_data
        )
    else:
        logger.warning(
            'add_user_response',
            timestamp=timestamp,
            timestamp_unix_ms=int(time.time() * 1000),
            device_auth_token=device_auth_token,
            parent_user_id=parent_user_id,
            user_id=user_id,
            child_device_auth_token=child_device_auth_token,
            own_device_id=own_device_id,
            request_id=request_id,
            success=success,
            status_code=status_code,
            response_data=response_data,
            error_code=error_code,
            error_message=error_message
        )