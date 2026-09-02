"""Family creation logging module for KeyFamilyData.md.

This module provides secure logging functionality for family creation events,
capturing all input data, derived data, and server environment details into
a structured markdown file.

Features:
- Append-only logging to KeyFamilyData.md
- Secure directory storage (/var/log/family_creation/)
- Complete input data capture (name, password, email, timestamp, server details)
- Derived data capture (hash, salt, secondhash, encryption algorithm)
- Markdown formatting for readability
- Access restriction notices for sensitive data
- Troubleshooting section for manual notes
"""

import os
import platform
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional


# Log file path - using /var/log/family_creation/ as specified
FAMILY_LOG_DIR = '/var/log/family_creation'
FAMILY_LOG_FILE = 'KeyFamilyData.md'


def get_server_environment_details() -> Dict[str, str]:
    """Get server environment details.
    
    Returns:
        Dictionary containing OS, version, and platform information.
    """
    return {
        'os': platform.system(),
        'os_version': platform.version(),
        'platform': platform.platform(),
        'python_version': platform.python_version(),
        'architecture': platform.machine(),
        'hostname': platform.node(),
    }


def ensure_log_directory() -> str:
    """Ensure the log directory exists and return the full path to the log file.
    
    Creates the directory if it doesn't exist.
    
    Returns:
        Full path to the KeyFamilyData.md file.
    """
    global FAMILY_LOG_DIR
    
    # Try to create the directory, handle permission issues gracefully
    try:
        os.makedirs(FAMILY_LOG_DIR, exist_ok=True)
    except PermissionError:
        # Fall back to a writable location if /var/log is not accessible
        fallback_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'logs')
        os.makedirs(fallback_dir, exist_ok=True)
        FAMILY_LOG_DIR = fallback_dir
    
    return os.path.join(FAMILY_LOG_DIR, FAMILY_LOG_FILE)


def format_markdown_entry(
    family_id: str,
    parent_name: str,
    email: str,
    password_data: Dict[str, str],
    device_name: str,
    device_model: str,
    time_zone: str,
    locale: Optional[str],
    server_url: str,
    request_id: Optional[str] = None
) -> str:
    """Format a family creation entry as markdown.
    
    Args:
        family_id: The device auth token/family ID.
        parent_name: Parent's name.
        email: Parent's email address.
        password_data: Dictionary containing hash, secondHash, secondSalt.
        device_name: Name of the device.
        device_model: Model of the device.
        time_zone: Time zone setting.
        locale: Locale setting (optional).
        server_url: The server URL being used.
        request_id: Optional request ID for correlation.
    
    Returns:
        Formatted markdown string for the entry.
    """
    timestamp = datetime.now(timezone.utc)
    timestamp_iso = timestamp.isoformat()
    timestamp_unix_ms = int(timestamp.timestamp() * 1000)
    
    env_details = get_server_environment_details()
    
    # Get encryption algorithm info
    encryption_algorithm = 'bcrypt'
    bcrypt_rounds = 12  # Default rounds used in generate_family_hashes
    
    # Build the markdown entry
    entry = f"""
## Family Creation Entry - {timestamp_iso}

### Timestamp
- **ISO Timestamp:** {timestamp_iso}
- **Unix Timestamp (ms):** {timestamp_unix_ms}
- **Request ID:** {request_id or 'N/A'}

### Input Data
- **Parent Name:** {parent_name}
- **Email:** {email}
- **Device Name:** {device_name}
- **Device Model:** {device_model}
- **Time Zone:** {time_zone}
- **Locale:** {locale or 'N/A'}

### Server Environment Details
- **Operating System:** {env_details['os']}
- **OS Version:** {env_details['os_version']}
- **Platform:** {env_details['platform']}
- **Python Version:** {env_details['python_version']}
- **Architecture:** {env_details['architecture']}
- **Hostname:** {env_details['hostname']}
- **Server URL:** {server_url}

### Derived Data (Password Hashes)
- **Encryption Algorithm:** {encryption_algorithm}
- **Bcrypt Rounds:** {bcrypt_rounds}
- **Hash:** `{password_data.get('hash', 'N/A')}`
- **Second Hash:** `{password_data.get('secondHash', 'N/A')}`
- **Second Salt:** `{password_data.get('secondSalt', 'N/A')}`

### Family Identifier
- **Family ID (Device Auth Token):** {family_id}

---
"""
    return entry


def log_family_creation(
    family_id: str,
    parent_name: str,
    email: str,
    password_data: Dict[str, str],
    device_name: str,
    device_model: str,
    time_zone: str,
    server_url: str,
    locale: Optional[str] = None,
    request_id: Optional[str] = None
) -> bool:
    """Log a family creation event to KeyFamilyData.md.
    
    This function appends a new entry to the KeyFamilyData.md file with
    all input data, derived data, and server environment details.
    
    Args:
        family_id: The device auth token/family ID.
        parent_name: Parent's name.
        email: Parent's email address.
        password_data: Dictionary containing hash, secondHash, secondSalt.
        device_name: Name of the device.
        device_model: Model of the device.
        time_zone: Time zone setting.
        server_url: The server URL being used.
        locale: Locale setting (optional).
        request_id: Optional request ID for correlation.
    
    Returns:
        True if logging was successful, False otherwise.
    """
    try:
        log_file_path = ensure_log_directory()
        
        # Check if file exists to determine if we need to add header
        file_exists = os.path.exists(log_file_path)
        
        # Format the entry
        entry = format_markdown_entry(
            family_id=family_id,
            parent_name=parent_name,
            email=email,
            password_data=password_data,
            device_name=device_name,
            device_model=device_model,
            time_zone=time_zone,
            locale=locale,
            server_url=server_url,
            request_id=request_id
        )
        
        # Append to file (append-only)
        with open(log_file_path, 'a', encoding='utf-8') as f:
            if not file_exists:
                # Add header and access restriction note for new file
                header = get_file_header()
                f.write(header)
            f.write(entry)
        
        return True
    except Exception as e:
        # Log error but don't fail the family creation
        print(f"Warning: Failed to log family creation: {e}", file=sys.stderr)
        return False


def get_file_header() -> str:
    """Get the header content for the KeyFamilyData.md file.
    
    Returns:
        Markdown header string with access restriction notice.
    """
    return """# KeyFamilyData.md - Family Creation Audit Log

> **⚠️ ACCESS RESTRICTION NOTICE**
> 
> This file contains sensitive data including:
> - Password hashes (bcrypt)
> - Email addresses
> - Device authentication tokens
> - Parent names
> 
> **DO NOT SHARE** this file with unauthorized personnel.
> **DO NOT COMMIT** this file to version control.
> **DO NOT EXPOSE** this file via web server or API.
> 
> Access is restricted to authorized administrators only.
> Handle in accordance with data protection regulations.

---

## Table of Contents
- [Family Creation Entries](#family-creation-entries)

---

## Family Creation Entries

"""


def get_troubleshooting_section() -> str:
    """Get the troubleshooting section for the KeyFamilyData.md file.
    
    Returns:
        Markdown troubleshooting section string.
    """
    return """

---

## Troubleshooting Notes

This section is reserved for manual troubleshooting notes and observations.

### Common Issues

1. **Family ID Not Found**
   - Verify the device_auth_token matches the server response
   - Check that the family was created successfully on the server
   - Ensure the token hasn't expired

2. **Password Hash Mismatch**
   - Verify bcrypt rounds match (default: 12)
   - Ensure hash format is correct ($2a$ prefix)
   - Check that the same password was used for both hashes

3. **Email Verification Issues**
   - Verify the mail_login_token is still valid
   - Check that the verification code was entered correctly
   - Ensure the email address is correct

### Manual Notes

_Add your troubleshooting notes here:_

"""


def append_troubleshooting_note(note: str) -> bool:
    """Append a note to the troubleshooting section.
    
    Args:
        note: The note to append.
    
    Returns:
        True if successful, False otherwise.
    """
    try:
        log_file_path = ensure_log_directory()
        
        if not os.path.exists(log_file_path):
            return False
        
        # Read current content
        with open(log_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find the troubleshooting section and append note
        troubleshooting_marker = "### Manual Notes"
        if troubleshooting_marker in content:
            # Find the position after the marker
            pos = content.find(troubleshooting_marker)
            # Find the end of the section (next --- or end of file)
            next_section = content.find("\n---\n", pos)
            if next_section == -1:
                next_section = len(content)
            
            # Insert the note
            new_content = content[:next_section] + f"\n- {note}\n" + content[next_section:]
            
            with open(log_file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            return True
        
        return False
    except Exception as e:
        print(f"Warning: Failed to append troubleshooting note: {e}", file=sys.stderr)
        return False


def ensure_troubleshooting_section_exists() -> bool:
    """Ensure the troubleshooting section exists in the log file.
    
    If the file doesn't exist, creates it with the troubleshooting section.
    If the file exists but doesn't have the troubleshooting section, appends it.
    
    Returns:
        True if successful, False otherwise.
    """
    try:
        log_file_path = ensure_log_directory()
        
        if not os.path.exists(log_file_path):
            # Create new file with header and troubleshooting section
            with open(log_file_path, 'w', encoding='utf-8') as f:
                f.write(get_file_header())
                f.write(get_troubleshooting_section())
            return True
        
        # Check if troubleshooting section exists
        with open(log_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if "## Troubleshooting Notes" not in content:
            # Append troubleshooting section
            with open(log_file_path, 'a', encoding='utf-8') as f:
                f.write(get_troubleshooting_section())
        
        return True
    except Exception as e:
        print(f"Warning: Failed to ensure troubleshooting section: {e}", file=sys.stderr)
        return False