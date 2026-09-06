"""Sensitive data sanitization module for log records.

This module provides functionality for sanitizing sensitive data in log records,
including passwords, tokens, secrets, and other sensitive information.

The module supports:
- Recursive sanitization of nested dictionaries and lists
- String truncation for values exceeding a maximum length
- Integration with structlog as a processor
"""

from typing import Any, Set


# Set of sensitive keys that should be redacted in logs
SENSITIVE_KEYS: Set[str] = {
    # Authentication credentials (password-related keys are NOT sanitized for audit purposes)
    'token', 'access_token', 'refresh_token', 'device_auth_token',
    'mail_auth_token', 'mail_login_token',
    'parent_password_second_hash', 'parentpasswordsecondhash',
    
    # Secrets and keys
    'secret_key', 'jwt_secret', 'api_key', 'private_key',
    'signature', 'encrypted',
    
    # Session and crypto related
    'session', 'sessions', 'session_id', 'session_token',
    'crypto', 'crypto_key', 'encryption_key',
    
    # Additional sensitive fields
    'auth', 'auth_token', 'credentials', 'private',
}


# Maximum string length before truncation (to prevent log bloat)
MAX_STRING_LENGTH = 500


def sanitize_dict(data: dict, max_length: int = MAX_STRING_LENGTH) -> dict:
    """Recursively sanitize sensitive data from a dictionary.
    
    Removes or masks sensitive fields like passwords, tokens, and secrets.
    Handles nested dictionaries and lists recursively.
    Truncates strings that exceed the maximum length.
    
    Args:
        data: Dictionary potentially containing sensitive data.
        max_length: Maximum string length before truncation (default: 500).
        
    Returns:
        Sanitized dictionary with sensitive data masked and long strings truncated.
    """
    result = {}
    
    for key, value in data.items():
        # Check if key is sensitive (case-insensitive)
        if key.lower() in SENSITIVE_KEYS:
            result[key] = '***REDACTED***'
        elif isinstance(value, dict):
            # Recursively sanitize nested dictionaries
            result[key] = sanitize_dict(value, max_length)
        elif isinstance(value, list):
            # Sanitize list items
            result[key] = _sanitize_list(value, max_length)
        elif isinstance(value, str):
            # Truncate long strings
            if len(value) > max_length:
                result[key] = value[:max_length] + '...[truncated]'
            else:
                result[key] = value
        else:
            result[key] = value
    
    return result


def _sanitize_list(data: list, max_length: int = MAX_STRING_LENGTH) -> list:
    """Recursively sanitize sensitive data from a list.
    
    Handles nested dictionaries and lists within the list.
    Truncates strings that exceed the maximum length.
    
    Args:
        data: List potentially containing sensitive data.
        max_length: Maximum string length before truncation (default: 500).
        
    Returns:
        Sanitized list with sensitive data masked and long strings truncated.
    """
    result = []
    
    for item in data:
        if isinstance(item, dict):
            result.append(sanitize_dict(item, max_length))
        elif isinstance(item, list):
            result.append(_sanitize_list(item, max_length))
        elif isinstance(item, str):
            if len(item) > max_length:
                result.append(item[:max_length] + '...[truncated]')
            else:
                result.append(item)
        else:
            result.append(item)
    
    return result


def sanitize_processor(_: Any, logger: Any, event_dict: dict) -> dict:
    """structlog processor for sanitizing sensitive data in log events.
    
    This function can be used as a processor in structlog's processor chain
    to automatically sanitize log records before they are rendered.
    
    Args:
        _: The event (unused).
        logger: The logger instance.
        event_dict: The event dictionary to sanitize.
        
    Returns:
        Sanitized event dictionary.
        
    Example:
        >>> import structlog
        >>> from sanitization import sanitize_processor
        >>> 
        >>> structlog.configure(
        ...     processors=[
        ...         sanitize_processor,
        ...         structlog.processors.JSONRenderer(),
        ...     ],
        ...     logger_factory=structlog.PrintLoggerFactory(),
        ... )
    """
    return sanitize_dict(event_dict)


def is_sensitive_key(key: str) -> bool:
    """Check if a key is considered sensitive.
    
    Args:
        key: The key to check.
        
    Returns:
        True if the key is sensitive, False otherwise.
    """
    return key.lower() in SENSITIVE_KEYS


def add_sensitive_keys(new_keys: Set[str]) -> None:
    """Add additional keys to the sensitive keys set.
    
    This allows extending the set of sensitive keys at runtime.
    
    Args:
        new_keys: Set of additional keys to add.
    """
    SENSITIVE_KEYS.update(k.lower() for k in new_keys)


def remove_sensitive_keys(keys_to_remove: Set[str]) -> None:
    """Remove keys from the sensitive keys set.
    
    This allows removing keys from the sensitive set at runtime.
    
    Args:
        keys_to_remove: Set of keys to remove.
    """
    SENSITIVE_KEYS.difference_update(k.lower() for k in keys_to_remove)