"""Flask application for dashboardV2.

This module provides the main Flask application with all routes and logic
for the new dashboard. It handles:
- Session management
- Server selection with persistence
- API proxy endpoints
- Static file serving

The application is designed to run on both Windows laptop and Home Assistant
as an ingress app.

Key change: Using device_auth_token as primary key instead of family_id,
matching the official Android app's approach where the server looks up
family from device using deviceAuthToken.
"""

import atexit
import json
import os
import queue
import re
import secrets
import socket
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from flask import Flask, jsonify, redirect, render_template, request, session, url_for, send_from_directory, g, Response
from werkzeug.middleware.proxy_fix import ProxyFix

from auth_client import AuthClient, APIResponse
from config import Config
from database import (
    Database, get_database, reset_database, store_auth_token,
    get_users_by_device_auth_token, get_devices_by_device_auth_token, get_categories_by_device_auth_token, get_connected_devices,
    get_device_auth_tokens, upsert_family_password_hash, get_parent_password_hash, get_parent_password_second_salt, get_parent_user_id, clear_all_tables,
    get_all_tables_data, clear_server_checks, get_family_by_mail, create_family_record, update_family_salt,
    save_users, get_sync_state, save_sync_state, get_family, update_family_parent_user_id, create_user,
    create_default_category
)
from middleware.request_logging import init_request_logging, shutdown_log_worker, get_request_id
from persistence import (
    get_server_selection_store, is_ha_ingress, get_current_log_level, set_current_log_level,
    get_persisted_device_auth_token, set_persisted_device_auth_token,
    get_persisted_own_device_id, set_persisted_own_device_id, clear_persisted_auth_tokens,
    backup_auth_tokens, restore_auth_tokens, clear_auth_token_backup, clear_server_selection,
    sync_session_to_database
)
from scheduler import start_scheduler, stop_scheduler, set_server_url
from sync_manager import SyncManager, create_sync_manager, get_event_queue
from utils.logging import setup_structlog, get_logger, set_log_level, get_log_level
from utils.family_logging import log_family_creation, ensure_troubleshooting_section_exists
from utils.audit_log import (
    log_login_as_parent_hash_regeneration,
    log_login_as_parent_hash_regeneration_failure,
    log_login_as_parent_new_hash_generation,
    log_login_as_parent_password_stored,
    log_login_as_parent_direct_hash_stored,
    log_login_as_parent_salt_validation_failure,
    log_add_user_request,
    log_add_user_response
)
from key_manager import get_or_create_signing_key

# Add parent directory to sys.path for crypto_utils import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crypto_utils import generate_family_hashes, regenerate_second_hash

# Path to the legacy dashboard.html file (in parent directory)
LEGACY_DASHBOARD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'dashboard.html')

# Setup structured logging
setup_structlog(
    log_level=Config().LOG_LEVEL,
    log_file_path=Config().LOG_FILE_PATH,
    log_max_bytes=Config().LOG_MAX_BYTES,
    log_backup_count=Config().LOG_BACKUP_COUNT,
    log_format=Config().LOG_FORMAT,
    rotate_on_start=Config().LOG_ROTATE_ON_START,
    werkzeug_log_file_path=Config().LOG_WERKZEUG_FILE_PATH,
)

# Get logger instance
logger = get_logger(__name__)

# Create Flask app
app = Flask(__name__, template_folder='templates', static_folder='static')

# Create config instance for accessing properties
config = Config()

# Configure app
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# Apply proxy fix for Home Assistant ingress
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Initialize request logging middleware
init_request_logging(app)

# Initialize persistence store
persistence_store = get_server_selection_store()


# ============================================================================
# Session Restoration (before_request handler)
# ============================================================================

@app.before_request
def restore_session_from_persistence():
    """Restore session from persistent storage on each request.
    
    This is done in a before_request handler because Flask sessions
    can only be accessed within a request context.
    
    This allows users to remain authenticated after app restart by
    restoring the device_auth_token from persistent storage.
    
    IMPORTANT: We verify the token exists in the database to ensure
    the session is valid and not stale. This prevents inconsistent
    authentication states where the session has a token but it's no
    longer valid on the server.
    """
    # Only restore if not already authenticated
    if 'device_auth_token' not in session:
        persisted_device_auth_token = get_persisted_device_auth_token()
        
        if persisted_device_auth_token:
            # Extract token from the dict returned by get_persisted_device_auth_token()
            token = persisted_device_auth_token.get('token') if isinstance(persisted_device_auth_token, dict) else persisted_device_auth_token
            if token:
                # Verify the token is still valid in the database
                # This prevents restoring stale/invalid tokens
                db = get_database()
                from database import get_auth_token
                db_token_record = get_auth_token(db, token)
                
                if db_token_record:
                    # Token is valid in database, restore session
                    session['device_auth_token'] = token
                    # Also store mail if available
                    mail = persisted_device_auth_token.get('mail') if isinstance(persisted_device_auth_token, dict) else None
                    if mail:
                        session['mail'] = mail
                    # Also restore own_device_id when device_auth_token is found
                    # This ensures consistency: own_device_id is only present when authenticated
                    persisted_own_device_id = get_persisted_own_device_id()
                    if persisted_own_device_id:
                        session['own_device_id'] = persisted_own_device_id
                    logger.debug(
                        "Session restored from persistence",
                        component="session",
                        token_restored=True
                    )
                else:
                    # Token not found or expired in database - clear it
                    logger.warning(
                        "Persisted token not found or expired in database, not restoring session",
                        component="session",
                        token_preview=token[:8] + '...' if len(token) > 8 else token
                    )
    
    # Sync session data to database if needed
    # This ensures data is persisted after migrations or database resets
    sync_result = sync_session_to_database()
    if sync_result.get('device_auth_token_synced'):
        logger.info(
            "Session data synced to database during startup",
            component="session",
            device_auth_token=session.get('device_auth_token', '')[:8] + '...'
        )


# ============================================================================
# Port Availability Check
# ============================================================================

def check_port_available(host: str, port: int) -> bool:
    """Check if a port is available for binding.
    
    Attempts to bind a socket to the specified host and port to verify
    availability. If the port is already in use, logs an error and exits.
    
    Args:
        host: The host address to bind to.
        port: The port number to check.
        
    Returns:
        True if the port is available (function does not return on failure).
        
    Raises:
        SystemExit: If the port is already in use (exits with code 1).
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    
    try:
        sock.bind((host, port))
        sock.close()
        return True
    except OSError as e:
        sock.close()
        error_message = str(e)
        logger.error(
            f"Port {port} on host {host} is already in use. Another instance of the dashboard or another server is already running on this port.",
            port=port,
            host=host,
            error=error_message,
            suggestion="Stop the other process using the port, or change the port by setting the FLASK_PORT environment variable to a different port number."
        )
        # Print plain text error message to stderr for immediate console visibility
        plain_text_error = (
            f"ERROR: Port {port} on host {host} is already in use. "
            f"Another instance of the dashboard or another server is already running on this port. "
            f"Stop the process using the port or change the FLASK_PORT environment variable."
        )
        print(plain_text_error, file=sys.stderr)
        sys.exit(1)


# ============================================================================
# Session Management
# ============================================================================

def get_current_server_url() -> str:
    """Get the currently selected server URL.
    
    Checks persistent storage first, then session, then falls back to config default.
    This ensures server selection persists across container restarts in HA.
    
    Returns:
        Server URL string.
    """
    # Check persistent storage first (survives container restarts)
    # First check if server_url is directly stored
    stored_server_url = persistence_store.get_selected_server_url()
    if stored_server_url:
        return stored_server_url
    
    # Then check if server_key is stored and look up URL from config
    server_key = persistence_store.get_selected_server_key()
    if server_key:
        server_url = Config.get_server_url(server_key)
        if server_url:
            return server_url
    
    # Fall back to session (only if in request context)
    try:
        if 'server_url' in session:
            return session['server_url']
    except RuntimeError:
        # Working outside of request context, skip session check
        pass
    
    # Final fallback to config default
    return config.DEBUG_SERVER_URL


def set_current_server_url(url: str) -> None:
    """Set the currently selected server URL in session.
    
    Args:
        url: Server URL to set.
    """
    session['server_url'] = url


def get_server_selection() -> Dict[str, str]:
    """Get the server selection options.
    
    Returns:
        Dictionary of server key -> URL mappings.
    """
    return Config.SERVER_OPTIONS

def get_current_server_key() -> Optional[str]:
    """Get the currently selected server key from persistent storage.
    
    Returns:
        Server key or None if not set.
    """
    return persistence_store.get_selected_server_key()


def set_current_server_key(key: str) -> None:
    """Save the server key to persistent storage.
    
    Args:
        key: Server key to save.
    """
    persistence_store.set_selected_server_key(key)
    logger.info("Server key persisted", server_key=key, request_id=get_request_id())


# ============================================================================
# Routes
# ============================================================================

@app.route('/')
def index():
    """Landing page with toggle/dropdown for legacy vs new dashboard.
    
    Returns:
        Rendered landing page template.
    """
    request_id = get_request_id()
    is_authenticated = session.get('device_auth_token') is not None

    # Get current log level (from persistence or runtime default)
    persisted_level = get_current_log_level()
    current_log_level = persisted_level if persisted_level else get_log_level()

    logger.info(
        "Landing page rendered",
        is_authenticated=is_authenticated,
        request_id=request_id,
        log_level=current_log_level
    )
    
    return render_template('landing.html', is_authenticated=is_authenticated, current_log_level=current_log_level)


@app.route('/legacy-dashboard')
def legacy_dashboard():
    """Redirect to the legacy dashboard.
    
    Returns:
        Redirect response to legacy dashboard.
    """
    request_id = get_request_id()
    logger.info("Legacy dashboard redirect requested", request_id=request_id)
    return redirect('/dashboard.html')


@app.route('/dashboard.html')
def serve_legacy_dashboard():
    """Serve the legacy dashboard HTML file.
    
    Returns:
        The legacy dashboard.html file.
    """
    request_id = get_request_id()
    logger.info("Serving legacy dashboard", request_id=request_id)
    legacy_dir = os.path.dirname(LEGACY_DASHBOARD_PATH)
    return send_from_directory(legacy_dir, 'dashboard.html')


@app.route('/dashboardV2')
def dashboard_v2():
    """New dashboard page.
    
    Returns:
        Rendered dashboard page template.
    """
    request_id = get_request_id()
    device_auth_token = session.get('device_auth_token')
    server_url = get_current_server_url()
    is_authenticated = device_auth_token is not None
    
    # Trigger sync if authenticated but has no local data
    # This ensures users see their data after login or session restore
    if is_authenticated and device_auth_token and server_url:
        db = get_database()
        users = get_users_by_device_auth_token(db, device_auth_token)
        devices = get_devices_by_device_auth_token(db, device_auth_token)
        
        # If no local data, trigger a sync to fetch from server
        if not users and not devices:
            logger.info(
                "Triggering sync on dashboard load - no local data found",
                request_id=request_id,
                device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None
            )
            sync_manager = create_sync_manager(db)
            own_device_id = session.get("own_device_id")
            sync_success = sync_manager.do_sync(device_auth_token, server_url, own_device_id)
            if sync_success:
                logger.info("Sync completed on dashboard load", request_id=request_id)
            else:
                logger.warning("Sync failed on dashboard load", request_id=request_id)
    
    logger.info(
        "Dashboard V2 page rendered",
        is_authenticated=is_authenticated,
        request_id=request_id
    )
    
    return render_template('dashboardV2.html', is_authenticated=is_authenticated)


@app.route('/select-server', methods=['POST'])
def select_server():
    """Select a server from the dropdown options.
    
    Expects JSON body with 'server_key' field.
    
    Returns:
        JSON response with status and selected server URL.
    """
    start_time = time.time()
    request_id = get_request_id()
    data = request.get_json() or {}
    server_key = data.get('server_key')
    
    if not server_key:
        logger.error(
            "Server selection failed: missing server_key",
            request_id=request_id,
            error="Missing server_key"
        )
        return jsonify({'status': 'error', 'error': 'Missing server_key'}), 400
    
    server_url = Config.get_server_url(server_key)
    if not server_url:
        logger.error(
            "Server selection failed: invalid server key",
            server_key=server_key,
            request_id=request_id,
            error="Invalid server key"
        )
        return jsonify({'status': 'error', 'error': 'Invalid server key'}), 400
    
    # Store in session
    set_current_server_url(server_url)
    
    # Persist to file (survives container restarts)
    set_current_server_key(server_key)
    persistence_store.set_selected_server_url(server_url)
    
    # Update the scheduler to use the selected server URL
    set_server_url(server_url)
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    logger.info(
        "Server selected successfully",
        server_key=server_key,
        server_url=server_url,
        server_name=Config.get_server_name(server_key),
        duration_ms=duration_ms,
        request_id=request_id
    )
    
    return jsonify({
        'status': 'ok',
        'server_url': server_url,
        'server_name': Config.get_server_name(server_key),
        'server_key': server_key
    })


@app.route('/api/log-level', methods=['POST'])
def set_log_level_route():
    """Set the log level at runtime.

    Expects JSON body with 'log_level' field.
    Persists the setting so it survives application restarts.

    Returns:
        JSON response with status and the applied log level.
    """
    start_time = time.time()
    request_id = get_request_id()
    data = request.get_json() or {}
    log_level = data.get('log_level', '').upper()

    if not log_level:
        logger.error(
            "Log level update failed: missing log_level",
            request_id=request_id,
            error="Missing log_level"
        )
        return jsonify({'status': 'error', 'error': 'Missing log_level'}), 400

    if not set_log_level(log_level):
        logger.error(
            "Log level update failed: invalid log level",
            request_id=request_id,
            log_level=log_level,
            error="Invalid log level"
        )
        return jsonify({'status': 'error', 'error': f'Invalid log level: {log_level}'}), 400

    # Persist the log level
    set_current_log_level(log_level)

    duration_ms = int((time.time() - start_time) * 1000)

    logger.info(
        "Log level updated",
        log_level=log_level,
        duration_ms=duration_ms,
        request_id=request_id
    )

    return jsonify({
        'status': 'ok',
        'log_level': log_level
    })


@app.route('/api/server-selection', methods=['GET'])
def get_server_selection():
    """Get the current server selection.
    
    Returns:
        JSON response with current server_key and server_url.
    """
    request_id = get_request_id()
    server_key = get_current_server_key()
    server_url = get_current_server_url()
    
    logger.info(
        "Server selection retrieved",
        server_key=server_key,
        server_url=server_url,
        request_id=request_id
    )
    
    return jsonify({
        'server_key': server_key,
        'server_url': server_url
    })


@app.route('/api/time', methods=['POST'])
def api_time():
    """Proxy to debug-server /api/v1/time endpoint.
    
    Returns:
        JSON response with server time.
    """
    start_time = time.time()
    request_id = get_request_id()
    server_url = get_current_server_url()
    
    logger.info(
        "Time API request",
        server_url=server_url,
        request_id=request_id
    )
    
    client = AuthClient(base_url=server_url)
    response = client.get_server_time()
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    if response.success:
        logger.info(
            "Time API response successful",
            server_url=server_url,
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id
        )
        return jsonify({
            'status': 'ok',
            'time': response.data.get('ms')
        })
    else:
        logger.error(
            "Time API response failed",
            server_url=server_url,
            status_code=response.status_code,
            error_code=response.error_code,
            error_message=response.error_message,
            duration_ms=duration_ms,
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error_code': response.error_code,
            'error_message': response.error_message,
            'technical_detail': response.technical_detail
        }), 502 if response.error_code in ['timeout', 'unreachable'] else 500


@app.route('/api/auth/send-mail-login-code', methods=['POST'])
def api_send_mail_login_code():
    """Proxy to debug-server /api/v1/auth/send-mail-login-code-v2 endpoint.
    
    Expects JSON body with 'mail' field.
    
    Returns:
        JSON response with mailLoginToken.
    """
    start_time = time.time()
    request_id = get_request_id()
    data = request.get_json() or {}
    mail = data.get('mail')
    locale = data.get('locale', 'en')
    
    if not mail:
        logger.error(
            "Send mail login code failed: missing mail field",
            request_id=request_id,
            error="Missing mail field"
        )
        return jsonify({'status': 'error', 'error': 'Missing mail field'}), 400
    
    server_url = get_current_server_url()
    
    logger.info(
        "Send mail login code request",
        server_url=server_url,
        mail=mail,
        locale=locale,
        request_id=request_id
    )
    
    client = AuthClient(base_url=server_url)
    response = client.send_mail_login_code(mail=mail, locale=locale)
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    if response.success:
        logger.info(
            "Send mail login code successful",
            server_url=server_url,
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id
        )
        return jsonify(response.data)
    else:
        logger.error(
            "Send mail login code failed",
            server_url=server_url,
            status_code=response.status_code,
            error_code=response.error_code,
            error_message=response.error_message,
            duration_ms=duration_ms,
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error_code': response.error_code,
            'error_message': response.error_message
        }), 400


@app.route('/api/auth/sign-in-by-mail-code', methods=['POST'])
def api_sign_in_by_mail_code():
    """Proxy to debug-server /api/v1/auth/sign-in-by-mail-code endpoint.
    
    Expects JSON body with 'mailLoginToken' and 'receivedCode' fields.
    
    Returns:
        JSON response with mailAuthToken.
    """
    start_time = time.time()
    request_id = get_request_id()
    data = request.get_json() or {}
    mail_login_token = data.get('mailLoginToken')
    received_code = data.get('receivedCode')
    
    if not mail_login_token or not received_code:
        logger.error(
            "Sign in by mail code failed: missing required fields",
            request_id=request_id,
            error="Missing required fields"
        )
        return jsonify({'status': 'error', 'error': 'Missing required fields'}), 400
    
    server_url = get_current_server_url()
    
    logger.info(
        "Sign in by mail code request",
        server_url=server_url,
        request_id=request_id
    )
    
    client = AuthClient(base_url=server_url)
    response = client.sign_in_by_mail_code(
        mail_login_token=mail_login_token,
        received_code=received_code
    )
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    if response.success:
        # Store mail auth token in session
        session['mail_auth_token'] = response.data.get('mailAuthToken')
        
        logger.info(
            "Sign in by mail code successful",
            server_url=server_url,
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id
        )
        return jsonify(response.data)
    else:
        logger.error(
            "Sign in by mail code failed",
            server_url=server_url,
            status_code=response.status_code,
            error_code=response.error_code,
            error_message=response.error_message,
            duration_ms=duration_ms,
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error_code': response.error_code,
            'error_message': response.error_message
        }), 401


@app.route('/api/auth/create-family', methods=['POST'])
def api_create_family():
    """Proxy to debug-server /api/v1/parent/create-family endpoint.
    
    Expects JSON body with:
        - mailAuthToken: Mail auth token from sign-in
        - parentPassword: Password data with hash, secondHash, secondSalt, encrypted
        - parentDevice: Device info dict with 'model' key
        - deviceName: Device name
        - timeZone: Time zone string
        - parentName: Parent name
        - locale: Optional locale string
    
    Returns:
        JSON response with deviceAuthToken and ownDeviceId.
    """
    start_time = time.time()
    request_id = get_request_id()
    data = request.get_json() or {}
    mail_auth_token = data.get('mailAuthToken')
    parent_password = data.get('parentPassword')
    parent_device = data.get('parentDevice', {'model': 'Unknown'})
    device_name = data.get('deviceName', 'Unknown Device')
    time_zone = data.get('timeZone', 'Europe/Amsterdam')
    parent_name = data.get('parentName', 'Parent')
    locale = data.get('locale')
    email = data.get('mail')  # Optional email for audit logging
    
    if not mail_auth_token or not parent_password:
        logger.error(
            "Create family failed: missing required fields",
            request_id=request_id,
            error="Missing required fields"
        )
        return jsonify({'status': 'error', 'error': 'Missing required fields'}), 400
    
    server_url = get_current_server_url()
    
    logger.info(
        "Create family request",
        server_url=server_url,
        parent_name=parent_name,
        time_zone=time_zone,
        request_id=request_id
    )
    
    client = AuthClient(base_url=server_url)
    response = client.create_family(
        mail_auth_token=mail_auth_token,
        parent_password=parent_password,
        parent_device=parent_device,
        device_name=device_name,
        time_zone=time_zone,
        parent_name=parent_name,
        locale=locale,
        email=email
    )
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    if response.success:
        # Store device auth token in session
        session['device_auth_token'] = response.data.get('deviceAuthToken')
        session['own_device_id'] = response.data.get('ownDeviceId')
        
        # Persist auth token to file for session restoration after restart
        if response.data.get('deviceAuthToken'):
            set_persisted_device_auth_token(response.data.get('deviceAuthToken'))
            set_persisted_own_device_id(response.data.get('ownDeviceId'))
        
        logger.info(
            "Create family successful",
            server_url=server_url,
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id
        )
        return jsonify(response.data)
    else:
        logger.error(
            "Create family failed",
            server_url=server_url,
            status_code=response.status_code,
            error_code=response.error_code,
            error_message=response.error_message,
            duration_ms=duration_ms,
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error_code': response.error_code,
            'error_message': response.error_message
        }), 401


@app.route('/api/families', methods=['POST'])
def api_create_family_rest():
    """Create a new family (RESTful alias for POST /parent/create-family).
    
    This endpoint is a RESTful alias that proxies to the debug-server's
    /parent/create-family endpoint.
    
    Expects JSON body with:
        - mailAuthToken: Mail auth token from sign-in
        - parentPassword: Password data with hash, secondHash, secondSalt, encrypted
        - parentDevice: Device info dict with 'model' key
        - deviceName: Device name
        - timeZone: Time zone string
        - parentName: Parent name
        - locale: Optional locale string
    
    Returns:
        JSON response with deviceAuthToken and ownDeviceId.
    """
    start_time = time.time()
    request_id = get_request_id()
    data = request.get_json() or {}
    mail_auth_token = data.get('mailAuthToken')
    parent_password = data.get('parentPassword')
    parent_device = data.get('parentDevice', {'model': 'Unknown'})
    device_name = data.get('deviceName', 'Unknown Device')
    time_zone = data.get('timeZone', 'Europe/Amsterdam')
    parent_name = data.get('parentName', 'Parent')
    locale = data.get('locale')
    email = data.get('mail')  # Optional email for audit logging
    
    if not mail_auth_token or not parent_password:
        logger.error(
            "Create family (REST) failed: missing required fields",
            request_id=request_id,
            error="Missing required fields"
        )
        return jsonify({'status': 'error', 'error': 'Missing required fields'}), 400
    
    server_url = get_current_server_url()
    
    logger.info(
        "Create family (REST) request",
        server_url=server_url,
        parent_name=parent_name,
        time_zone=time_zone,
        request_id=request_id
    )
    
    client = AuthClient(base_url=server_url)
    response = client.create_family_rest(
        mail_auth_token=mail_auth_token,
        parent_password=parent_password,
        parent_device=parent_device,
        device_name=device_name,
        time_zone=time_zone,
        parent_name=parent_name,
        locale=locale,
        email=email
    )
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    if response.success:
        # Store device auth token in session
        session['device_auth_token'] = response.data.get('deviceAuthToken')
        session['own_device_id'] = response.data.get('ownDeviceId')
        
        # Persist auth token to file for session restoration after restart
        if response.data.get('deviceAuthToken'):
            set_persisted_device_auth_token(response.data.get('deviceAuthToken'))
            set_persisted_own_device_id(response.data.get('ownDeviceId'))
        
        logger.info(
            "Create family (REST) successful",
            server_url=server_url,
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id
        )
        return jsonify(response.data)
    else:
        logger.error(
            "Create family (REST) failed",
            server_url=server_url,
            status_code=response.status_code,
            error_code=response.error_code,
            error_message=response.error_message,
            duration_ms=duration_ms,
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error_code': response.error_code,
            'error_message': response.error_message
        }), 401


@app.route('/api/auth/sign-in-into-family', methods=['POST'])
def api_sign_in_into_family():
    """Proxy to debug-server /api/v1/parent/sign-in-into-family endpoint.
    
    Expects JSON body with 'mailAuthToken' and 'parentPasswordSecondHash' fields.
    
    Returns:
        JSON response with deviceAuthToken and ownDeviceId.
    """
    start_time = time.time()
    request_id = get_request_id()
    data = request.get_json() or {}
    mail_auth_token = data.get('mailAuthToken')
    parent_password_second_hash = data.get('parentPasswordSecondHash')
    
    if not mail_auth_token or not parent_password_second_hash:
        logger.error(
            "Sign in into family failed: missing required fields",
            request_id=request_id,
            error="Missing required fields"
        )
        return jsonify({'status': 'error', 'error': 'Missing required fields'}), 400
    
    server_url = get_current_server_url()
    
    logger.info(
        "Sign in into family request",
        server_url=server_url,
        request_id=request_id
    )
    
    client = AuthClient(base_url=server_url)
    response = client.sign_in_into_family(
        mail_auth_token=mail_auth_token,
        parent_password_second_hash=parent_password_second_hash
    )
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    if response.success:
        # Store device auth token in session
        session['device_auth_token'] = response.data.get('deviceAuthToken')
        session['own_device_id'] = response.data.get('ownDeviceId')
        
        # Store parent password second hash in session for subsequent operations
        # (e.g., adding users to family)
        if parent_password_second_hash:
            session['parent_password_second_hash'] = parent_password_second_hash
        
        # Persist auth token to file for session restoration after restart
        if response.data.get('deviceAuthToken'):
            set_persisted_device_auth_token(response.data.get('deviceAuthToken'))
            set_persisted_own_device_id(response.data.get('ownDeviceId'))
        
        logger.info(
            "Sign in into family successful",
            server_url=server_url,
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id
        )
        return jsonify(response.data)
    else:
        logger.error(
            "Sign in into family failed",
            server_url=server_url,
            status_code=response.status_code,
            error_code=response.error_code,
            error_message=response.error_message,
            duration_ms=duration_ms,
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error_code': response.error_code,
            'error_message': response.error_message
        }), 401


# ============================================================================
# Password Hash Regeneration Endpoint
# ============================================================================

@app.route('/api/auth/regenerate-hash', methods=['POST'])
def api_regenerate_hash():
    """Regenerate password hash from password and existing salt.
    
    This endpoint allows users to set their password after login,
    enabling device removal functionality.
    
    Expects JSON body with 'mail' and 'password' fields.
    
    Returns:
        JSON response with the regenerated hash.
    """
    start_time = time.time()
    request_id = get_request_id()
    data = request.get_json() or {}
    mail = data.get('mail', '').strip()
    password = data.get('password', '').strip()
    
    if not mail or not password:
        logger.error(
            "Regenerate hash failed: missing required fields",
            request_id=request_id,
            error="Missing mail or password"
        )
        return jsonify({
            'status': 'error',
            'error_code': 'validation',
            'error_message': 'Mail and password are required'
        }), 400
    
    # Validate password length
    if len(password) < 8:
        logger.warning(
            "Regenerate hash failed: password too short",
            mail=mail,
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error_code': 'validation',
            'error_message': 'Password must be at least 8 characters'
        }), 400
    
    server_url = get_current_server_url()
    device_auth_token = session.get('device_auth_token')
    
    if not device_auth_token:
        logger.warning(
            "Regenerate hash failed: not authenticated",
            mail=mail,
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error_code': 'unauthorized',
            'error_message': 'Not authenticated'
        }), 401
    
    db = get_database()
    
    # Look up family by mail to get existing salt
    logger.info("Regenerate hash: looking up family", mail=mail, request_id=request_id)
    family = get_family_by_mail(db, mail)
    
    if not family:
        logger.error(
            "Regenerate hash failed: family not found",
            mail=mail,
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error_code': 'not_found',
            'error_message': 'Family not found for this email'
        }), 404
    
    existing_salt = family.get('parent_password_second_salt')
    
    if not existing_salt:
        logger.error(
            "Regenerate hash failed: salt missing",
            mail=mail,
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error_code': 'validation',
            'error_message': 'Password salt not available for this family'
        }), 400
    
    # Regenerate the hash using the existing salt
    try:
        second_hash = regenerate_second_hash(password, existing_salt)
        password_data = {
            'hash': generate_family_hashes(password)['hash'],
            'secondHash': second_hash,
            'secondSalt': existing_salt
        }
        
        # Store in database
        upsert_family_password_hash(
            db=db,
            device_auth_token=device_auth_token,
            parent_password_hash=password_data['hash'],
            parent_password_second_hash=password_data['secondHash'],
            parent_password_second_salt=password_data['secondSalt']
        )
        
        # Store in session
        session['parent_password_second_hash'] = password_data['secondHash']
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            "Regenerate hash successful",
            mail=mail,
            device_auth_token=device_auth_token[:8] + '...',
            duration_ms=duration_ms,
            request_id=request_id
        )
        
        # Log to audit log
        log_login_as_parent_password_stored(
            mail=mail,
            device_auth_token=device_auth_token,
            password_data=password_data,
            request_id=request_id,
            server_url=server_url
        )
        
        return jsonify({
            'status': 'ok',
            'secondHash': password_data['secondHash'],
            'hash': password_data['hash'],
            'secondSalt': password_data['secondSalt']
        })
        
    except Exception as e:
        logger.error(
            "Regenerate hash failed: hash generation error",
            mail=mail,
            error=str(e),
            error_type=type(e).__name__,
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error_code': 'server_error',
            'error_message': 'Failed to generate password hash'
        }), 500


# ============================================================================
# Create Family Routes (Server-Side Rendered)
# ============================================================================

@app.route('/create-family', methods=['GET'])
def get_create_family():
    """Render the create family page with the appropriate step.
    
    The page shows different forms based on session state:
    - No mail_login_token: Step 1 - Enter email
    - Has mail_login_token, no mail_auth_token: Step 2 - Enter verification code
    - Has mail_auth_token, no device_auth_token: Step 3 - Enter password
    - Has device_auth_token: Already authenticated, redirect to dashboard
    
    Returns:
        Rendered HTML template with the appropriate step.
    """
    request_id = get_request_id()
    
    # Check if already authenticated
    if session.get('device_auth_token'):
        logger.info("User already authenticated, redirecting to dashboard", request_id=request_id)
        return redirect('/dashboardV2?message=already_authenticated')
    
    # Determine current step based on session state
    has_mail_login_token = session.get('mail_login_token') is not None
    has_mail_auth_token = session.get('mail_auth_token') is not None
    
    if not has_mail_login_token:
        # Step 1: Enter email
        step = 1
        error = session.pop('create_family_error', None)
        logger.info("Rendering create family step 1 (email)", request_id=request_id)
        return render_template('create_family.html', step=step, error=error)
    elif not has_mail_auth_token:
        # Step 2: Enter verification code
        step = 2
        error = session.pop('create_family_error', None)
        logger.info("Rendering create family step 2 (code)", request_id=request_id)
        return render_template('create_family.html', step=step, error=error)
    else:
        # Step 3: Enter password
        step = 3
        error = session.pop('create_family_error', None)
        logger.info("Rendering create family step 3 (password)", request_id=request_id)
        return render_template('create_family.html', step=step, error=error)


@app.route('/create-family', methods=['POST'])
def post_create_family():
    """Process create family form submission.
    
    Handles all three steps of the create family flow:
    - Step 1: Send mail login code
    - Step 2: Sign in by mail code
    - Step 3: Create family
    
    Returns:
        Redirect to next step or dashboard on success.
    """
    start_time = time.time()
    request_id = get_request_id()
    step = request.form.get('step', '1')
    
    server_url = get_current_server_url()
    
    if step == '1':
        # Step 1: Send mail login code
        mail = request.form.get('mail', '').strip()
        
        if not mail:
            session['create_family_error'] = 'Email is required'
            logger.warning("Create family step 1 failed: missing email", request_id=request_id)
            return redirect('/create-family')
        
        # Validate email format
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, mail):
            session['create_family_error'] = 'Invalid email format'
            logger.warning("Create family step 1 failed: invalid email", request_id=request_id)
            return redirect('/create-family')
        
        locale = 'en'  # Default locale
        logger.info("Create family step 1: sending mail login code", server_url=server_url, mail=mail, locale=locale, request_id=request_id)
        
        client = AuthClient(base_url=server_url)
        response = client.send_mail_login_code(mail=mail, locale=locale)
        
        if response.success:
            session['mail_login_token'] = response.data.get('mailLoginToken')
            session['mail'] = mail  # Store email for later use in step 3
            logger.info("Create family step 1 successful", request_id=request_id)
            return redirect('/create-family')
        else:
            session['create_family_error'] = response.error_message or 'Failed to send verification code'
            logger.error("Create family step 1 failed", server_url=server_url, error_code=response.error_code, request_id=request_id)
            return redirect('/create-family')
    
    elif step == '2':
        # Step 2: Sign in by mail code
        mail_login_token = session.get('mail_login_token')
        received_code = request.form.get('receivedCode', '').strip()
        
        if not mail_login_token:
            session['create_family_error'] = 'Session expired. Please start again.'
            logger.warning("Create family step 2 failed: missing mail_login_token", request_id=request_id)
            return redirect('/create-family')
        
        if not received_code:
            session['create_family_error'] = 'Verification code is required'
            logger.warning("Create family step 2 failed: missing code", request_id=request_id)
            return redirect('/create-family')
        
        # Validate code format (3-word passphrase)
        # The official server uses randomWords(3) to generate a 3-word passphrase
        # like "Pferd Miete abwenden"
        code_words = received_code.split()
        if len(code_words) != 3:
            session['create_family_error'] = 'Invalid verification code format (expected 3 words)'
            logger.warning("Create family step 2 failed: invalid code format", request_id=request_id)
            return redirect('/create-family')
        
        logger.info("Create family step 2: verifying code", server_url=server_url, request_id=request_id)
        
        client = AuthClient(base_url=server_url)
        response = client.sign_in_by_mail_code(
            mail_login_token=mail_login_token,
            received_code=received_code
        )
        
        if response.success:
            session['mail_auth_token'] = response.data.get('mailAuthToken')
            logger.info("Create family step 2 successful", request_id=request_id)
            return redirect('/create-family')
        else:
            session['create_family_error'] = response.error_message or 'Invalid verification code'
            logger.error("Create family step 2 failed", server_url=server_url, error_code=response.error_code, request_id=request_id)
            return redirect('/create-family')
    
    elif step == '3':
        # Step 3: Create family
        mail_auth_token = session.get('mail_auth_token')
        mail = session.get('mail', 'unknown')  # Retrieve email from session
        password = request.form.get('password', '').strip()
        second_password = request.form.get('secondPassword', '').strip()
        parent_name = request.form.get('parentName', '').strip()
        time_zone = request.form.get('timeZone', 'Europe/Amsterdam').strip()
        device_model = request.form.get('deviceModel', '').strip()
        device_name = request.form.get('deviceName', '').strip()
        locale = request.form.get('locale', 'en').strip()
        
        if not mail_auth_token:
            session['create_family_error'] = 'Session expired. Please start again.'
            logger.warning("Create family step 3 failed: missing mail_auth_token", request_id=request_id)
            return redirect('/create-family')
        
        if not password:
            session['create_family_error'] = 'Password is required'
            logger.warning("Create family step 3 failed: missing password", request_id=request_id)
            return redirect('/create-family')
        
        if not second_password:
            session['create_family_error'] = 'Second password is required'
            logger.warning("Create family step 3 failed: missing second password", request_id=request_id)
            return redirect('/create-family')
        
        if password != second_password:
            session['create_family_error'] = 'Passwords do not match'
            logger.warning("Create family step 3 failed: password mismatch", request_id=request_id)
            return redirect('/create-family')
        
        # Validate password meets minimum requirements
        if len(password) < 8:
            session['create_family_error'] = 'Password must be at least 8 characters long'
            logger.warning("Create family step 3 failed: password too short", request_id=request_id)
            return redirect('/create-family')
        
        if not parent_name:
            session['create_family_error'] = 'Parent name is required'
            logger.warning("Create family step 3 failed: missing parent name", request_id=request_id)
            return redirect('/create-family')
        
        if not time_zone:
            session['create_family_error'] = 'Time zone is required'
            logger.warning("Create family step 3 failed: missing time zone", request_id=request_id)
            return redirect('/create-family')
        
        if not device_model:
            session['create_family_error'] = 'Device model is required'
            logger.warning("Create family step 3 failed: missing device model", request_id=request_id)
            return redirect('/create-family')
        
        if not device_name:
            session['create_family_error'] = 'Device name is required'
            logger.warning("Create family step 3 failed: missing device name", request_id=request_id)
            return redirect('/create-family')
        
        # Generate password hashes
        try:
            password_data = generate_family_hashes(password)
        except ValueError as e:
            # Handle specific validation errors
            error_msg = str(e)
            session['create_family_error'] = f'Password validation error: {error_msg}'
            logger.error("Create family step 3 failed: password validation error", error=error_msg, request_id=request_id)
            return redirect('/create-family')
        except Exception as e:
            # Handle unexpected errors with detailed logging
            error_msg = str(e)
            error_type = type(e).__name__
            session['create_family_error'] = f'Failed to generate password hashes: {error_type}'
            logger.error(
                "Create family step 3 failed: hash generation error",
                error=error_msg,
                error_type=error_type,
                request_id=request_id
            )
            return redirect('/create-family')
        
        # Build parent device info
        parent_device = {'model': device_model}
        
        logger.info("Create family step 3: creating family", server_url=server_url, parent_name=parent_name, time_zone=time_zone, request_id=request_id)
        
        client = AuthClient(base_url=server_url)
        response = client.create_family_rest(
            mail_auth_token=mail_auth_token,
            parent_password=password_data,
            parent_device=parent_device,
            device_name=device_name,
            time_zone=time_zone,
            parent_name=parent_name,
            locale=locale if locale else None,
            email=mail
        )
        
        if response.success:
            # Store device auth token in session
            session['device_auth_token'] = response.data.get('deviceAuthToken')
            session['own_device_id'] = response.data.get('ownDeviceId')
            
            # Store auth token in database for later lookup
            if response.data.get('deviceAuthToken'):
                db = get_database()
                store_auth_token(
                    db=db,
                    token_type='device_auth_token',
                    token_value=response.data.get('deviceAuthToken'),
                    device_id=response.data.get('ownDeviceId')
                )
                logger.info("Auth token stored in database", request_id=request_id)
                
                # Persist auth token to file for session restoration after restart
                set_persisted_device_auth_token(response.data.get('deviceAuthToken'))
                set_persisted_own_device_id(response.data.get('ownDeviceId'))
            
            # Clear temporary session data
            session.pop('mail_login_token', None)
            session.pop('mail_auth_token', None)
            
            # Trigger sync to fetch family data (users, devices, categories)
            # This matches the Android app's behavior of calling pullChanges after create/sign-in
            # IMPORTANT: Sync must succeed to update lastConnectivity on the server,
            # otherwise the cleanup worker may delete the family
            device_auth_token = response.data.get('deviceAuthToken')
            own_device_id = response.data.get('ownDeviceId')
            
            if device_auth_token:
                db = get_database()
                sync_manager = create_sync_manager(db)
                
                # Retry sync up to 3 times with exponential backoff
                max_retries = 3
                retry_delay = 1
                sync_success = False
                
                for attempt in range(max_retries):
                    sync_success = sync_manager.do_sync(device_auth_token, server_url, own_device_id)
                    if sync_success:
                        # Small delay to ensure lastConnectivity is updated on server
                        time.sleep(2)
                        logger.info("Sync completed after family creation", request_id=request_id)
                        break
                    else:
                        if attempt < max_retries - 1:
                            logger.warning(
                                "Sync failed after family creation, retrying...",
                                request_id=request_id,
                                attempt=attempt + 1
                            )
                            time.sleep(retry_delay)
                            retry_delay *= 2
                
                if not sync_success:
                    logger.error(
                        "Sync failed after family creation after all retries",
                        request_id=request_id
                    )
                    session['create_family_error'] = 'Failed to sync with server. Please try again.'
                    return redirect('/create-family')
                
                # Store password hash in database for session restoration
                upsert_family_password_hash(
                    db=db,
                    device_auth_token=device_auth_token,
                    parent_password_hash=password_data.get('hash'),
                    parent_password_second_hash=password_data.get('secondHash'),
                    parent_password_second_salt=password_data.get('secondSalt')
                )
                logger.info("Password hash stored in database", request_id=request_id)
            
            # Log family creation to KeyFamilyData.md
            family_id = response.data.get('deviceAuthToken')
            if family_id:
                log_family_creation(
                    family_id=family_id,
                    parent_name=parent_name,
                    email=mail,
                    password_data=password_data,
                    device_name=device_name,
                    device_model=device_model,
                    time_zone=time_zone,
                    server_url=server_url,
                    locale=locale,
                    request_id=request_id
                )
            
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info("Create family successful", server_url=server_url, duration_ms=duration_ms, request_id=request_id)
            return redirect('/dashboardV2')
        else:
            session['create_family_error'] = response.error_message or 'Failed to create family'
            logger.error("Create family step 3 failed", server_url=server_url, error_code=response.error_code, request_id=request_id)
            return redirect('/create-family')
    
    else:
        session['create_family_error'] = 'Invalid step'
        return redirect('/create-family')


@app.route('/create-family/cancel', methods=['POST'])
def cancel_create_family():
    """Cancel create family flow and clear session.
    
    Returns:
        Redirect to dashboard.
    """
    request_id = get_request_id()
    
    # Clear all create family session data
    session.pop('mail_login_token', None)
    session.pop('mail_auth_token', None)
    session.pop('mail', None)
    session.pop('device_auth_token', None)
    session.pop('own_device_id', None)
    session.pop('create_family_error', None)
    
    logger.info("Create family cancelled", request_id=request_id)
    return redirect('/dashboardV2')


# ============================================================================
# Login as Parent Routes (Server-Side Rendered)
# ============================================================================

@app.route('/login-as-parent', methods=['GET'])
def get_login_as_parent():
    """Render the login as parent page with the appropriate step.
    
    The page shows different forms based on session state:
    - No mail_login_token: Step 1 - Enter email
    - Has mail_login_token, no mail_auth_token: Step 2 - Enter verification code
    - Has mail_auth_token, no device_auth_token: Step 3 - Enter device info
    - Has device_auth_token, no password: Step 4 - Enter password (optional)
    - Has device_auth_token and password: Already authenticated, redirect to dashboard
    
    Returns:
        Rendered HTML template with the appropriate step.
    """
    request_id = get_request_id()
    
    # Check if already authenticated with password
    if session.get('device_auth_token') and session.get('parent_password_second_hash'):
        logger.info("User already authenticated with password, redirecting to dashboard", request_id=request_id)
        return redirect('/dashboardV2?message=already_authenticated')
    
    # Check if already authenticated (without password)
    if session.get('device_auth_token'):
        # User is logged in but hasn't set password yet - show step 4
        step = 4
        error = session.pop('login_as_parent_error', None)
        success = session.pop('login_as_parent_success', None)
        logger.info("Rendering login as parent step 4 (password optional)", request_id=request_id)
        return render_template('login_as_parent.html', step=step, error=error, success=success)
    
    # Determine current step based on session state
    has_mail_login_token = session.get('mail_login_token') is not None
    has_mail_auth_token = session.get('mail_auth_token') is not None
    
    if not has_mail_login_token:
        # Step 1: Enter email
        step = 1
        error = session.pop('login_as_parent_error', None)
        logger.info("Rendering login as parent step 1 (email)", request_id=request_id)
        return render_template('login_as_parent.html', step=step, error=error)
    elif not has_mail_auth_token:
        # Step 2: Enter verification code
        step = 2
        error = session.pop('login_as_parent_error', None)
        logger.info("Rendering login as parent step 2 (code)", request_id=request_id)
        return render_template('login_as_parent.html', step=step, error=error)
    else:
        # Step 3: Enter device info
        step = 3
        error = session.pop('login_as_parent_error', None)
        logger.info("Rendering login as parent step 3 (device)", request_id=request_id)
        return render_template('login_as_parent.html', step=step, error=error)


@app.route('/login-as-parent', methods=['POST'])
def post_login_as_parent():
    """Process login as parent form submission.
    
    Handles the 2-step login flow:
    - Step 1: Send mail login code
    - Step 2: Sign in by mail code
    - Step 3: Sign in to family (password optional)
    - Step 4: Regenerate hash from password (optional)
    
    Returns:
        Redirect to next step or dashboard on success.
    """
    start_time = time.time()
    request_id = get_request_id()
    step = request.form.get('step', '1')
    
    server_url = get_current_server_url()
    
    if step == '1':
        # Step 1: Send mail login code
        mail = request.form.get('mail', '').strip()
        
        if not mail:
            session['login_as_parent_error'] = 'Email is required'
            logger.warning("Login as parent step 1 failed: missing email", request_id=request_id)
            return redirect('/login-as-parent')
        
        # Validate email format
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, mail):
            session['login_as_parent_error'] = 'Invalid email format'
            logger.warning("Login as parent step 1 failed: invalid email", request_id=request_id)
            return redirect('/login-as-parent')
        
        locale = 'en'  # Default locale
        logger.info("Login as parent step 1: sending mail login code", server_url=server_url, mail=mail, locale=locale, request_id=request_id)
        
        client = AuthClient(base_url=server_url)
        response = client.send_mail_login_code(mail=mail, locale=locale)
        
        if response.success:
            session['mail_login_token'] = response.data.get('mailLoginToken')
            session['mail'] = mail  # Store mail for later use in step 3
            logger.info("Login as parent step 1 successful", request_id=request_id)
            return redirect('/login-as-parent')
        else:
            session['login_as_parent_error'] = response.error_message or 'Failed to send verification code'
            logger.error("Login as parent step 1 failed", server_url=server_url, error_code=response.error_code, request_id=request_id)
            return redirect('/login-as-parent')
    
    elif step == '2':
        # Step 2: Sign in by mail code
        mail_login_token = session.get('mail_login_token')
        received_code = request.form.get('receivedCode', '').strip()
        
        if not mail_login_token:
            session['login_as_parent_error'] = 'Session expired. Please start again.'
            logger.warning("Login as parent step 2 failed: missing mail_login_token", request_id=request_id)
            return redirect('/login-as-parent')
        
        if not received_code:
            session['login_as_parent_error'] = 'Verification code is required'
            logger.warning("Login as parent step 2 failed: missing code", request_id=request_id)
            return redirect('/login-as-parent')
        
        # Validate code format (3-word passphrase)
        code_words = received_code.split()
        if len(code_words) != 3:
            session['login_as_parent_error'] = 'Invalid verification code format (expected 3 words)'
            logger.warning("Login as parent step 2 failed: invalid code format", request_id=request_id)
            return redirect('/login-as-parent')
        
        logger.info("Login as parent step 2: verifying code", server_url=server_url, request_id=request_id)
        
        client = AuthClient(base_url=server_url)
        response = client.sign_in_by_mail_code(
            mail_login_token=mail_login_token,
            received_code=received_code
        )
        
        if response.success:
            session['mail_auth_token'] = response.data.get('mailAuthToken')
            logger.info("Login as parent step 2 successful", request_id=request_id)
            return redirect('/login-as-parent')
        else:
            session['login_as_parent_error'] = response.error_message or 'Invalid verification code'
            logger.error("Login as parent step 2 failed", server_url=server_url, error_code=response.error_code, request_id=request_id)
            return redirect('/login-as-parent')
    
    elif step == '3':
        # Step 3: Sign in to family (password is optional)
        mail_auth_token = session.get('mail_auth_token')
        device_model = request.form.get('deviceModel', '').strip()
        device_name = request.form.get('deviceName', '').strip()
        password = request.form.get('password', '').strip()
        parent_password_second_hash = request.form.get('parentPasswordSecondHash', '').strip()
        
        if not mail_auth_token:
            session['login_as_parent_error'] = 'Session expired. Please start again.'
            logger.warning("Login as parent step 3 failed: missing mail_auth_token", request_id=request_id)
            return redirect('/login-as-parent')
        
        if not device_model:
            session['login_as_parent_error'] = 'Device model is required'
            logger.warning("Login as parent step 3 failed: missing device model", request_id=request_id)
            return redirect('/login-as-parent')
        
        if not device_name:
            session['login_as_parent_error'] = 'Device name is required'
            logger.warning("Login as parent step 3 failed: missing device name", request_id=request_id)
            return redirect('/login-as-parent')
        
        logger.info("Login as parent step 3: signing in to family", server_url=server_url, device_name=device_name, device_model=device_model, request_id=request_id)
        
        client = AuthClient(base_url=server_url)
        response = client.sign_in_into_family(
            mail_auth_token=mail_auth_token,
            parent_password_second_hash=parent_password_second_hash,
            device_name=device_name,
            device_model=device_model,
            client_level=7  # Matches Android app's ClientDataStatus.CLIENT_LEVEL_VALUE
        )
        
        if not response.success:
            session['login_as_parent_error'] = response.error_message or 'Failed to sign in to family'
            logger.error("Login as parent step 3 failed", server_url=server_url, error_code=response.error_code, request_id=request_id)
            return redirect('/login-as-parent')
        
        # Store device auth token in session
        session['device_auth_token'] = response.data.get('deviceAuthToken')
        session['own_device_id'] = response.data.get('ownDeviceId')
        
        # Store auth token in database for later lookup
        device_auth_token = response.data.get('deviceAuthToken')
        own_device_id = response.data.get('ownDeviceId')
        
        if device_auth_token:
            db = get_database()
            store_auth_token(
                db=db,
                token_type='device_auth_token',
                token_value=device_auth_token,
                device_id=own_device_id
            )
            logger.info("Auth token stored in database", request_id=request_id)
            
            # Persist auth token to file for session restoration after restart
            set_persisted_device_auth_token(device_auth_token)
            set_persisted_own_device_id(own_device_id)
            
            # Create family record with minimal data (device_auth_token and mail)
            # This ensures the family record exists before password processing
            mail = session.get('mail')
            if mail:
                family_created = create_family_record(db, device_auth_token, mail)
                if family_created:
                    logger.info("Family record created after sign-in", mail=mail, device_auth_token=device_auth_token[:8] + '...', request_id=request_id)
        
        # Now process password if provided
        # Generate password hash using existing salt from family record (if available)
        # STRICT SALT VALIDATION: Never generate a new random salt during login
        # Only use the existing salt from the family record or fetch from server
        password_hash_to_send = None
        password_data_to_store = None
        if password:
            db = get_database()
            mail = session.get('mail')
            
            if not mail:
                # No mail in session - cannot look up family
                error_msg = 'Session error: email not available for salt lookup'
                logger.error(
                    "Salt validation failed: no mail in session",
                    mail=mail,
                    request_id=request_id
                )
                log_login_as_parent_salt_validation_failure(
                    mail=mail or 'unknown',
                    error_type='session_error',
                    error_message=error_msg,
                    family_found=False,
                    salt_available=False,
                    request_id=request_id,
                    server_url=server_url
                )
                session['login_as_parent_error'] = error_msg
                return redirect('/login-as-parent')
            
            # Look up family by mail to get existing salt
            logger.info("Looking up family by mail for salt validation", mail=mail, request_id=request_id)
            family = get_family_by_mail(db, mail)
            
            if not family:
                # Family not found - cannot validate salt
                error_msg = 'Family not found for this email. Please verify you have an existing family.'
                logger.error(
                    "Salt validation failed: family not found",
                    mail=mail,
                    request_id=request_id
                )
                log_login_as_parent_salt_validation_failure(
                    mail=mail,
                    error_type='family_not_found',
                    error_message=error_msg,
                    family_found=False,
                    salt_available=False,
                    request_id=request_id,
                    server_url=server_url
                )
                session['login_as_parent_error'] = error_msg
                return redirect('/login-as-parent')
            
            existing_salt = family.get('parent_password_second_salt')
            
            if not existing_salt:
                # Salt is missing from family record - this is expected if sync hasn't completed yet
                # The salt will be fetched from the server during sync
                logger.info("Salt not yet available in family record, will be fetched from server during sync", mail=mail, request_id=request_id)
                # Generate a new hash for now - it will be updated after sync
                # But we should NOT generate a new random salt - use a deterministic approach
                # For now, we'll proceed without the salt and update it after sync
                # This is a fallback for the case where the user provides a password in Step 3
                # and the sync hasn't completed yet
                error_msg = 'Password salt not yet available. Please enter your password in Step 4 after sync completes.'
                logger.warning(
                    "Salt not available in family record - user should use Step 4",
                    mail=mail,
                    request_id=request_id
                )
                session['login_as_parent_error'] = error_msg
                return redirect('/login-as-parent')
            
            # Salt is available - regenerate the hash using the existing salt
            logger.info("Salt validation successful - found existing salt", mail=mail, salt=existing_salt, request_id=request_id)
            try:
                second_hash = regenerate_second_hash(password, existing_salt)
                password_hash_to_send = second_hash
                password_data_to_store = {
                    'hash': generate_family_hashes(password)['hash'],  # First hash can be new
                    'secondHash': second_hash,
                    'secondSalt': existing_salt
                }
                logger.info("Successfully regenerated hash using existing salt",
                            mail=mail,
                            salt=existing_salt,
                            secondHash=second_hash,
                            password_data=password_data_to_store,
                            request_id=request_id)
                # Log to audit log for complete visibility
                log_login_as_parent_hash_regeneration(
                    mail=mail,
                    existing_salt=existing_salt,
                    second_hash=second_hash,
                    password_data=password_data_to_store,
                    request_id=request_id,
                    server_url=server_url
                )
            except Exception as e:
                logger.error("Failed to regenerate hash with existing salt",
                             mail=mail,
                             salt=existing_salt,
                             error=str(e),
                             error_type=type(e).__name__,
                             request_id=request_id)
                # Log failure to audit log with error details
                log_login_as_parent_hash_regeneration_failure(
                    mail=mail,
                    existing_salt=existing_salt,
                    error=str(e),
                    error_type=type(e).__name__,
                    request_id=request_id,
                    server_url=server_url
                )
                # Hash regeneration failed - cannot proceed
                error_msg = 'Failed to regenerate password hash. Please try again.'
                session['login_as_parent_error'] = error_msg
                return redirect('/login-as-parent')
        
        # Store password hash in database if provided
        if password_data_to_store:
            upsert_family_password_hash(
                db=db,
                device_auth_token=response.data.get('deviceAuthToken'),
                parent_password_hash=password_data_to_store['hash'],
                parent_password_second_hash=password_data_to_store['secondHash'],
                parent_password_second_salt=password_data_to_store['secondSalt']
            )
            session['parent_password_second_hash'] = password_data_to_store['secondHash']
            logger.info(
                "Parent password hash stored in database (from password)",
                mail=session.get('mail'),
                device_auth_token=response.data.get('deviceAuthToken')[:8] + '...',
                password_data=password_data_to_store,
                request_id=request_id
            )
            # Log to audit log for complete visibility
            log_login_as_parent_password_stored(
                mail=session.get('mail'),
                device_auth_token=response.data.get('deviceAuthToken'),
                password_data=password_data_to_store,
                request_id=request_id,
                server_url=server_url
            )
        elif parent_password_second_hash:
            # Direct hash input - store only secondHash for backward compatibility
            upsert_family_password_hash(
                db=db,
                device_auth_token=response.data.get('deviceAuthToken'),
                parent_password_second_hash=parent_password_second_hash
            )
            session['parent_password_second_hash'] = parent_password_second_hash
            logger.info(
                "Parent password hash stored in database (from direct input)",
                mail=session.get('mail'),
                device_auth_token=response.data.get('deviceAuthToken')[:8] + '...',
                parent_password_second_hash=parent_password_second_hash,
                request_id=request_id
            )
            # Log to audit log for complete visibility
            log_login_as_parent_direct_hash_stored(
                mail=session.get('mail'),
                device_auth_token=response.data.get('deviceAuthToken'),
                parent_password_second_hash=parent_password_second_hash,
                request_id=request_id,
                server_url=server_url
            )
        
        # Clear temporary session data
        session.pop('mail_login_token', None)
        session.pop('mail_auth_token', None)
        
        # Trigger sync to fetch family data (users, devices, categories)
        # This matches the Android app's behavior of calling pullChanges after create/sign-in
        # IMPORTANT: Sync must succeed to update lastConnectivity on the server,
        # and pass own_device_id to add dashboard to connected devices
        device_auth_token = response.data.get('deviceAuthToken')
        own_device_id = response.data.get('ownDeviceId')
        
        if device_auth_token:
            db = get_database()
            sync_manager = create_sync_manager(db)
            
            # Retry sync up to 3 times with exponential backoff
            max_retries = 3
            retry_delay = 1
            sync_success = False
            
            for attempt in range(max_retries):
                sync_success = sync_manager.do_sync(device_auth_token, server_url, own_device_id)
                if sync_success:
                    # Small delay to ensure lastConnectivity is updated on server
                    time.sleep(2)
                    logger.info("Sync completed after login", request_id=request_id)
                    break
                else:
                    if attempt < max_retries - 1:
                        logger.warning(
                            "Sync failed after login, retrying...",
                            request_id=request_id,
                            attempt=attempt + 1
                        )
                        time.sleep(retry_delay)
                        retry_delay *= 2
            
            if not sync_success:
                logger.error(
                    "Sync failed after login after all retries",
                    request_id=request_id
                )
                session['login_as_parent_error'] = 'Failed to sync with server. Please try again.'
                return redirect('/login-as-parent')
        
        # Check if password was provided - if so, redirect to dashboard
        # If not, show step 4 to optionally set password
        if password_data_to_store:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info("Login as parent successful with password", server_url=server_url, duration_ms=duration_ms, request_id=request_id)
            return redirect('/dashboardV2')
        else:
            # Password not provided - show step 4 to optionally set password
            logger.info("Login as parent successful without password - showing password step", request_id=request_id)
            return redirect('/login-as-parent')
    
    elif step == '4':
        # Step 4: Regenerate hash from password (optional)
        password = request.form.get('password', '').strip()
        
        if not password:
            session['login_as_parent_error'] = 'Password is required'
            logger.warning("Login as parent step 4 failed: missing password", request_id=request_id)
            return redirect('/login-as-parent')
        
        db = get_database()
        mail = session.get('mail')
        device_auth_token = session.get('device_auth_token')
        
        if not mail:
            session['login_as_parent_error'] = 'Session error: email not available for salt lookup'
            logger.error("Step 4 failed: no mail in session", request_id=request_id)
            return redirect('/login-as-parent')
        
        if not device_auth_token:
            session['login_as_parent_error'] = 'Session error: device_auth_token not available'
            logger.error("Step 4 failed: no device_auth_token in session", request_id=request_id)
            return redirect('/login-as-parent')
        
        # Look up family by mail to get existing salt
        logger.info("Step 4: looking up family for salt", mail=mail, request_id=request_id)
        family = get_family_by_mail(db, mail)
        
        if not family:
            error_msg = 'Family not found for this email'
            logger.error("Step 4 failed: family not found", mail=mail, request_id=request_id)
            session['login_as_parent_error'] = error_msg
            return redirect('/login-as-parent')
        
        existing_salt = family.get('parent_password_second_salt')
        
        if not existing_salt:
            error_msg = 'Password salt not available for this family. Please contact support.'
            logger.error("Step 4 failed: salt missing", mail=mail, request_id=request_id)
            session['login_as_parent_error'] = error_msg
            return redirect('/login-as-parent')
        
        # Regenerate the hash using the existing salt
        try:
            second_hash = regenerate_second_hash(password, existing_salt)
            password_data_to_store = {
                'hash': generate_family_hashes(password)['hash'],
                'secondHash': second_hash,
                'secondSalt': existing_salt
            }
            
            # Store in database
            upsert_family_password_hash(
                db=db,
                device_auth_token=device_auth_token,
                parent_password_hash=password_data_to_store['hash'],
                parent_password_second_hash=password_data_to_store['secondHash'],
                parent_password_second_salt=password_data_to_store['secondSalt']
            )
            session['parent_password_second_hash'] = password_data_to_store['secondHash']
            
            logger.info("Step 4: password hash regenerated and stored",
                        mail=mail,
                        device_auth_token=device_auth_token[:8] + '...',
                        request_id=request_id)
            
            # Log to audit log
            log_login_as_parent_password_stored(
                mail=mail,
                device_auth_token=device_auth_token,
                password_data=password_data_to_store,
                request_id=request_id,
                server_url=server_url
            )
            
            # Show success message
            session['login_as_parent_success'] = 'Password saved successfully! You can now remove devices using your password.'
            return redirect('/login-as-parent')
            
        except Exception as e:
            logger.error("Step 4 failed: hash regeneration error",
                         mail=mail,
                         error=str(e),
                         error_type=type(e).__name__,
                         request_id=request_id)
            session['login_as_parent_error'] = 'Failed to regenerate password hash. Please try again.'
            return redirect('/login-as-parent')
    
    else:
        session['login_as_parent_error'] = 'Invalid step'
        return redirect('/login-as-parent')


@app.route('/login-as-parent/cancel', methods=['POST'])
def cancel_login_as_parent():
    """Cancel login as parent flow and clear session.
    
    Returns:
        Redirect to dashboard.
    """
    request_id = get_request_id()
    
    # Clear all login as parent session data
    session.pop('mail_login_token', None)
    session.pop('mail_auth_token', None)
    session.pop('device_auth_token', None)
    session.pop('own_device_id', None)
    session.pop('login_as_parent_error', None)
    
    logger.info("Login as parent cancelled", request_id=request_id)
    return redirect('/dashboardV2')


# ============================================================================
# Recover Parent Password Routes (Server-Side Rendered)
# ============================================================================

@app.route('/recover-parent-password', methods=['GET'])
def get_recover_parent_password():
    """Render the recover parent password page with the appropriate step.
    
    The page shows different forms based on session state:
    - No mail_login_token: Step 1 - Enter email
    - Has mail_login_token, no mail_auth_token: Step 2 - Enter verification code
    - Has mail_auth_token: Step 3 - Enter new password
    - Already has device_auth_token: Redirect to dashboard
    
    Returns:
        Rendered HTML template with the appropriate step.
    """
    request_id = get_request_id()
    
    # Check if already authenticated
    if session.get('device_auth_token'):
        logger.info("User already authenticated, cannot recover password", request_id=request_id)
        # Show error on the recover password page instead of redirecting
        error = "You are already logged in. Please sign out first if you need to recover your password."
        return render_template('recover_parent_password.html', step=1, error=error)
    
    # Determine current step based on session state
    has_mail_login_token = session.get('mail_login_token') is not None
    has_mail_auth_token = session.get('mail_auth_token') is not None
    
    if not has_mail_login_token:
        # Step 1: Enter email
        step = 1
        error = session.pop('recover_parent_password_error', None)
        logger.info("Rendering recover parent password step 1 (email)", request_id=request_id)
        return render_template('recover_parent_password.html', step=step, error=error)
    elif not has_mail_auth_token:
        # Step 2: Enter verification code
        step = 2
        error = session.pop('recover_parent_password_error', None)
        logger.info("Rendering recover parent password step 2 (code)", request_id=request_id)
        return render_template('recover_parent_password.html', step=step, error=error)
    else:
        # Step 3: Enter new password
        step = 3
        error = session.pop('recover_parent_password_error', None)
        success = session.pop('recover_parent_password_success', None)
        logger.info("Rendering recover parent password step 3 (password)", request_id=request_id)
        return render_template('recover_parent_password.html', step=step, error=error, success=success)


@app.route('/recover-parent-password', methods=['POST'])
def post_recover_parent_password():
    """Process recover parent password form submission.
    
    Handles all three steps of the recover parent password flow:
    - Step 1: Send mail login code
    - Step 2: Sign in by mail code
    - Step 3: Recover parent password
    
    Returns:
        Redirect to next step or dashboard on success.
    """
    start_time = time.time()
    request_id = get_request_id()
    step = request.form.get('step', '1')
    
    server_url = get_current_server_url()
    
    if step == '1':
        # Step 1: Send mail login code
        mail = request.form.get('mail', '').strip()
        
        if not mail:
            session['recover_parent_password_error'] = 'Email is required'
            logger.warning("Recover parent password step 1 failed: missing email", request_id=request_id)
            return redirect('/recover-parent-password')
        
        # Validate email format
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, mail):
            session['recover_parent_password_error'] = 'Invalid email format'
            logger.warning("Recover parent password step 1 failed: invalid email", request_id=request_id)
            return redirect('/recover-parent-password')
        
        locale = 'en'  # Default locale
        logger.info("Recover parent password step 1: sending mail login code", server_url=server_url, mail=mail, locale=locale, request_id=request_id)
        
        client = AuthClient(base_url=server_url)
        response = client.send_mail_login_code(mail=mail, locale=locale)
        
        if response.success:
            session['mail_login_token'] = response.data.get('mailLoginToken')
            logger.info("Recover parent password step 1 successful", request_id=request_id)
            return redirect('/recover-parent-password')
        else:
            session['recover_parent_password_error'] = response.error_message or 'Failed to send verification code'
            logger.error("Recover parent password step 1 failed", server_url=server_url, error_code=response.error_code, request_id=request_id)
            return redirect('/recover-parent-password')
    
    elif step == '2':
        # Step 2: Sign in by mail code
        mail_login_token = session.get('mail_login_token')
        received_code = request.form.get('receivedCode', '').strip()
        
        if not mail_login_token:
            session['recover_parent_password_error'] = 'Session expired. Please start again.'
            logger.warning("Recover parent password step 2 failed: missing mail_login_token", request_id=request_id)
            return redirect('/recover-parent-password')
        
        if not received_code:
            session['recover_parent_password_error'] = 'Verification code is required'
            logger.warning("Recover parent password step 2 failed: missing code", request_id=request_id)
            return redirect('/recover-parent-password')
        
        # Validate code format (3-word passphrase)
        code_words = received_code.split()
        if len(code_words) != 3:
            session['recover_parent_password_error'] = 'Invalid verification code format (expected 3 words)'
            logger.warning("Recover parent password step 2 failed: invalid code format", request_id=request_id)
            return redirect('/recover-parent-password')
        
        logger.info("Recover parent password step 2: verifying code", server_url=server_url, request_id=request_id)
        
        client = AuthClient(base_url=server_url)
        response = client.sign_in_by_mail_code(
            mail_login_token=mail_login_token,
            received_code=received_code
        )
        
        if response.success:
            session['mail_auth_token'] = response.data.get('mailAuthToken')
            logger.info("Recover parent password step 2 successful", request_id=request_id)
            return redirect('/recover-parent-password')
        else:
            session['recover_parent_password_error'] = response.error_message or 'Invalid verification code'
            logger.error("Recover parent password step 2 failed", server_url=server_url, error_code=response.error_code, request_id=request_id)
            return redirect('/recover-parent-password')
    
    elif step == '3':
        # Step 3: Recover parent password
        mail_auth_token = session.get('mail_auth_token')
        new_password = request.form.get('newPassword', '').strip()
        confirm_password = request.form.get('confirmPassword', '').strip()
        
        if not mail_auth_token:
            session['recover_parent_password_error'] = 'Session expired. Please start again.'
            logger.warning("Recover parent password step 3 failed: missing mail_auth_token", request_id=request_id)
            return redirect('/recover-parent-password')
        
        if not new_password:
            session['recover_parent_password_error'] = 'New password is required'
            logger.warning("Recover parent password step 3 failed: missing new password", request_id=request_id)
            return redirect('/recover-parent-password')
        
        if new_password != confirm_password:
            session['recover_parent_password_error'] = 'Passwords do not match'
            logger.warning("Recover parent password step 3 failed: password mismatch", request_id=request_id)
            return redirect('/recover-parent-password')
        
        # Generate password hashes using bcrypt with $2a$ prefix
        logger.info("Recover parent password step 3: generating password hashes", server_url=server_url, request_id=request_id)
        
        password_hashes = generate_family_hashes(new_password)
        new_password_data = {
            'hash': password_hashes['hash'],
            'secondHash': password_hashes['secondHash'],
            'secondSalt': password_hashes['secondSalt']
        }
        
        # Call the API to recover password on the server
        logger.info("Recover parent password step 3: calling server API", server_url=server_url, request_id=request_id)
        
        client = AuthClient(base_url=server_url)
        response = client.recover_parent_password(
            mail_auth_token=mail_auth_token,
            new_password=new_password_data
        )
        
        if response.success:
            # Get device_auth_token from session if available
            device_auth_token = session.get('device_auth_token')
            
            # Update local database with new password hash
            if device_auth_token:
                db = get_database()
                upsert_family_password_hash(
                    db=db,
                    device_auth_token=device_auth_token,
                    parent_password_hash=password_hashes['hash'],
                    parent_password_second_hash=password_hashes['secondHash'],
                    parent_password_second_salt=password_hashes['secondSalt']
                )
                session['parent_password_second_hash'] = password_hashes['secondHash']
                logger.info("Recover parent password: password hash updated in database", request_id=request_id)
            
            # Clear temporary session data
            session.pop('mail_login_token', None)
            session.pop('mail_auth_token', None)
            session.pop('mail', None)
            
            # Show success message
            session['recover_parent_password_success'] = 'Password recovered successfully! You can now remove devices using your new password.'
            
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info("Recover parent password successful", server_url=server_url, duration_ms=duration_ms, request_id=request_id)
            
            # Redirect to dashboard if authenticated, otherwise show success on recover page
            if session.get('device_auth_token'):
                return redirect('/dashboardV2?message=password_recovered')
            else:
                return redirect('/recover-parent-password')
        else:
            session['recover_parent_password_error'] = response.error_message or 'Failed to recover password'
            logger.error("Recover parent password step 3 failed", server_url=server_url, error_code=response.error_code, request_id=request_id)
            return redirect('/recover-parent-password')
    
    else:
        session['recover_parent_password_error'] = 'Invalid step'
        return redirect('/recover-parent-password')


@app.route('/api/parent/create-add-device-token', methods=['POST'])
def api_create_add_device_token():
    """Proxy to debug-server /api/v1/parent/create-add-device-token endpoint.
    
    Expects JSON body with 'deviceAuthToken', 'parentId', and 'parentPasswordSecondHash' fields.
    
    Returns:
        JSON response with token and deviceId.
    """
    start_time = time.time()
    request_id = get_request_id()
    data = request.get_json() or {}
    device_auth_token = data.get('deviceAuthToken')
    parent_id = data.get('parentId')
    parent_password_second_hash = data.get('parentPasswordSecondHash')
    
    if not device_auth_token or not parent_id or not parent_password_second_hash:
        logger.error(
            "Create add device token failed: missing required fields",
            request_id=request_id,
            error="Missing required fields"
        )
        return jsonify({'status': 'error', 'error': 'Missing required fields'}), 400
    
    server_url = get_current_server_url()
    
    logger.info(
        "Create add device token request",
        server_url=server_url,
        request_id=request_id
    )
    
    client = AuthClient(base_url=server_url)
    response = client.create_add_device_token(
        device_auth_token=device_auth_token,
        parent_id=parent_id,
        parent_password_second_hash=parent_password_second_hash
    )
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    if response.success:
        logger.info(
            "Create add device token successful",
            server_url=server_url,
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id
        )
        return jsonify(response.data)
    else:
        logger.error(
            "Create add device token failed",
            server_url=server_url,
            status_code=response.status_code,
            error_code=response.error_code,
            error_message=response.error_message,
            duration_ms=duration_ms,
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error_code': response.error_code,
            'error_message': response.error_message
        }), 401


@app.route('/api/child/add-device', methods=['POST'])
def api_add_device():
    """Proxy to debug-server /api/v1/child/add-device endpoint.
    
    Expects JSON body with 'registerToken' field.
    
    Returns:
        JSON response with deviceAuthToken and ownDeviceId.
    """
    start_time = time.time()
    request_id = get_request_id()
    data = request.get_json() or {}
    register_token = data.get('registerToken')
    
    if not register_token:
        logger.error(
            "Add device failed: missing registerToken field",
            request_id=request_id,
            error="Missing registerToken field"
        )
        return jsonify({'status': 'error', 'error': 'Missing registerToken field'}), 400
    
    server_url = get_current_server_url()
    
    logger.info(
        "Add device request",
        server_url=server_url,
        request_id=request_id
    )
    
    client = AuthClient(base_url=server_url)
    response = client.add_device(
        register_token=register_token,
        device_name=data.get('deviceName'),
        device_model=data.get('deviceModel'),
        client_level=7  # Default client level (matches Android app's ClientDataStatus.CLIENT_LEVEL_VALUE)
    )
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    if response.success:
        # Store child device auth token in session
        session['child_device_auth_token'] = response.data.get('deviceAuthToken')
        
        logger.info(
            "Add device successful",
            server_url=server_url,
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id
        )
        return jsonify(response.data)
    else:
        logger.error(
            "Add device failed",
            server_url=server_url,
            status_code=response.status_code,
            error_code=response.error_code,
            error_message=response.error_message,
            duration_ms=duration_ms,
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error_code': response.error_code,
            'error_message': response.error_message
        }), 400


@app.route('/api/auth/get-status-by-mail-address', methods=['POST'])
def api_get_status_by_mail_address():
    """Proxy to debug-server /api/v1/parent/get-status-by-mail-address endpoint.
    
    Expects JSON body with 'mailAuthToken' field.
    
    Returns:
        JSON response with family status.
    """
    start_time = time.time()
    request_id = get_request_id()
    data = request.get_json() or {}
    mail_auth_token = data.get('mailAuthToken')
    
    if not mail_auth_token:
        logger.error(
            "Get status by mail address failed: missing mailAuthToken field",
            request_id=request_id,
            error="Missing mailAuthToken field"
        )
        return jsonify({'status': 'error', 'error': 'Missing mailAuthToken field'}), 400
    
    server_url = get_current_server_url()
    
    logger.info(
        "Get status by mail address request",
        server_url=server_url,
        request_id=request_id
    )
    
    client = AuthClient(base_url=server_url)
    response = client.get_status_by_mail_address(mail_auth_token=mail_auth_token)
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    if response.success:
        logger.info(
            "Get status by mail address successful",
            server_url=server_url,
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id
        )
        return jsonify(response.data)
    else:
        logger.error(
            "Get status by mail address failed",
            server_url=server_url,
            status_code=response.status_code,
            error_code=response.error_code,
            error_message=response.error_message,
            duration_ms=duration_ms,
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error_code': response.error_code,
            'error_message': response.error_message
        }), 401


@app.route('/api/auth/recover-parent-password', methods=['POST'])
def api_recover_parent_password():
    """Proxy to debug-server /api/v1/parent/recover-parent-password endpoint.
    
    Expects JSON body with 'mailAuthToken' and 'password' fields.
    
    Returns:
        JSON response with status.
    """
    start_time = time.time()
    request_id = get_request_id()
    data = request.get_json() or {}
    mail_auth_token = data.get('mailAuthToken')
    new_password = data.get('password')
    
    if not mail_auth_token or not new_password:
        logger.error(
            "Recover parent password failed: missing required fields",
            request_id=request_id,
            error="Missing required fields"
        )
        return jsonify({'status': 'error', 'error': 'Missing required fields'}), 400
    
    server_url = get_current_server_url()
    
    logger.info(
        "Recover parent password request",
        server_url=server_url,
        request_id=request_id
    )
    
    client = AuthClient(base_url=server_url)
    response = client.recover_parent_password(
        mail_auth_token=mail_auth_token,
        new_password=new_password
    )
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    if response.success:
        logger.info(
            "Recover parent password successful",
            server_url=server_url,
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id
        )
        
        # Update local database with new password hash if device_auth_token is in session
        device_auth_token = session.get('device_auth_token')
        if device_auth_token and new_password:
            db = get_database()
            password_hash = new_password.get('hash')
            second_hash = new_password.get('secondHash')
            second_salt = new_password.get('secondSalt')
            if password_hash and second_hash and second_salt:
                upsert_family_password_hash(
                    db=db,
                    device_auth_token=device_auth_token,
                    parent_password_hash=password_hash,
                    parent_password_second_hash=second_hash,
                    parent_password_second_salt=second_salt
                )
                session['parent_password_second_hash'] = second_hash
                logger.info("Recover parent password: password hash updated in database", request_id=request_id)
        
        return jsonify(response.data)
    else:
        logger.error(
            "Recover parent password failed",
            server_url=server_url,
            status_code=response.status_code,
            error_code=response.error_code,
            error_message=response.error_message,
            duration_ms=duration_ms,
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error_code': response.error_code,
            'error_message': response.error_message
        }), 401


# ============================================================================
# Session Management Routes
# ============================================================================

@app.route('/api/session/clear', methods=['POST'])
def clear_session():
    """Clear the current session.
    
    Returns:
        JSON response with status.
    """
    start_time = time.time()
    request_id = get_request_id()
    
    logger.info("Session clear request", request_id=request_id)
    
    session.clear()
    
    # Also clear persisted auth tokens
    clear_persisted_auth_tokens()
    
    duration_ms = int((time.time() - start_time) * 1000)
    logger.info(
        "Session cleared successfully",
        duration_ms=duration_ms,
        request_id=request_id
    )
    
    return jsonify({'status': 'ok'})


# ============================================================================
# Session Status Route
# ============================================================================

@app.route('/api/session/status', methods=['GET'])
def session_status():
    """Get the current session status.
    
    Returns:
        JSON response with session status.
    """
    start_time = time.time()
    request_id = get_request_id()
    server_url = get_current_server_url()
    
    # Get device_auth_token from session
    device_auth_token = session.get('device_auth_token')
    
    # Verify the token is valid in the database
    # This ensures consistency between session state and actual authentication
    # by checking if the token exists and hasn't expired
    is_token_valid = False
    if device_auth_token:
        db = get_database()
        from database import get_auth_token
        token_record = get_auth_token(db, device_auth_token)
        is_token_valid = token_record is not None
    
    # Check for parent password hash in session first, then fall back to database
    parent_password_second_hash = session.get('parent_password_second_hash')
    if not parent_password_second_hash and is_token_valid:
        db = get_database()
        parent_password_second_hash = get_parent_password_hash(db, device_auth_token)
    
    # Check if signing key exists (by checking if the key file exists)
    # The signing key is generated during sync operations
    has_signing_key = False
    try:
        persistence_dir = config.PERSISTENCE_DIR
        key_file_path = os.path.join(persistence_dir, 'dashboard_signing_key.json')
        has_signing_key = os.path.exists(key_file_path)
    except Exception as e:
        logger.warning("Failed to check signing key status", error=str(e), request_id=request_id)
    
    # Use verified token validity for authentication status
    # This ensures authenticated is true only when the token is actually valid
    status = {
        'authenticated': is_token_valid,
        'server_url': server_url,
        'has_mail_auth_token': 'mail_auth_token' in session,
        'has_device_auth_token': is_token_valid,
        'has_child_device_auth_token': 'child_device_auth_token' in session,
        'device_auth_token': device_auth_token if is_token_valid else None,
        'mail_auth_token': session.get('mail_auth_token'),
        'own_device_id': session.get('own_device_id') if is_token_valid else None,
        'login_error': session.get('login_error'),
        'configured_app_version': 226,
        'has_parent_password_second_hash': parent_password_second_hash is not None,
        'parent_password_second_hash': parent_password_second_hash,
        'has_signing_key': has_signing_key
    }
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    logger.info(
        "Session status retrieved",
        status=status,
        duration_ms=duration_ms,
        request_id=request_id
    )
    
    return jsonify(status)


# ============================================================================
# Dashboard API Routes
# ============================================================================

@app.route('/api/sync/pull', methods=['POST'])
def api_sync_pull():
    """Trigger a manual sync with the TimeLimit server.
    
    Returns:
        JSON response with sync result.
    """
    start_time = time.time()
    request_id = get_request_id()
    
    # Check authentication
    if 'device_auth_token' not in session:
        logger.warning(
            "Sync pull attempted without authentication",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error_code': 'unauthorized',
            'error': 'Not authenticated'
        }), 401
    
    device_auth_token = session.get('device_auth_token')
    if not device_auth_token:
        logger.warning(
            "Sync pull attempted without device_auth_token",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error_code': 'no_device_auth_token',
            'error': 'No device auth token'
        }), 400
    
    server_url = get_current_server_url()
    
    logger.info(
        "Sync pull requested",
        request_id=request_id,
        device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
        server_url=server_url
    )
    
    try:
        db = get_database()
        manager = create_sync_manager(db)
        own_device_id = session.get('own_device_id')
        success = manager.do_sync(device_auth_token, server_url, own_device_id)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        if success:
            logger.info(
                "Sync pull completed successfully",
                duration_ms=duration_ms,
                request_id=request_id
            )
            return jsonify({
                'status': 'ok',
                'synced': True
            })
        else:
            logger.error(
                "Sync pull failed",
                duration_ms=duration_ms,
                request_id=request_id
            )
            return jsonify({
                'status': 'error',
                'error_code': 'sync_failed',
                'error': 'Sync failed'
            }), 500
            
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "Sync pull error",
            duration_ms=duration_ms,
            request_id=request_id,
            error=str(e)
        )
        return jsonify({
            'status': 'error',
            'error_code': 'sync_error',
            'error': 'Sync error'
        }), 500


@app.route('/api/dashboard/users', methods=['GET'])
def api_dashboard_users():
    """Get users for the current device auth token.
    
    Returns:
        JSON response with users list.
    """
    start_time = time.time()
    request_id = get_request_id()
    
    # Check authentication
    if 'device_auth_token' not in session:
        logger.warning(
            "Users request without authentication",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'Not authenticated'
        }), 401
    
    device_auth_token = session.get('device_auth_token')
    if not device_auth_token:
        logger.warning(
            "Users request without device_auth_token",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'No device auth token'
        }), 400
    
    logger.info(
        "Users request",
        request_id=request_id,
        device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None
    )
    
    try:
        db = get_database()
        users = get_users_by_device_auth_token(db, device_auth_token)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            "Users retrieved",
            duration_ms=duration_ms,
            request_id=request_id,
            count=len(users)
        )
        
        return jsonify({
            'status': 'ok',
            'count': len(users),
            'users': users
        })
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "Users request error",
            duration_ms=duration_ms,
            request_id=request_id,
            error=str(e)
        )
        return jsonify({
            'status': 'error',
            'error': 'Failed to retrieve users'
        }), 500


@app.route('/api/dashboard/devices', methods=['GET'])
def api_dashboard_devices():
    """Get devices for the current device auth token.
    
    Returns:
        JSON response with devices list and own_device_id for highlighting current device.
    """
    start_time = time.time()
    request_id = get_request_id()
    
    # Check authentication
    if 'device_auth_token' not in session:
        logger.warning(
            "Devices request without authentication",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'Not authenticated'
        }), 401
    
    device_auth_token = session.get('device_auth_token')
    if not device_auth_token:
        logger.warning(
            "Devices request without device_auth_token",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'No device auth token'
        }), 400
    
    # Get own_device_id for highlighting the current device
    own_device_id = session.get('own_device_id')
    
    # Check for parent password hash (needed for device removal)
    # Check session first, then fall back to database
    parent_password_second_hash = session.get('parent_password_second_hash')
    if not parent_password_second_hash:
        parent_password_second_hash = get_parent_password_hash(db=get_database(), device_auth_token=device_auth_token)
    has_parent_password_second_hash = parent_password_second_hash is not None
    
    logger.info(
        "Devices request",
        request_id=request_id,
        device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
        has_own_device_id=own_device_id is not None,
        has_parent_password_second_hash=has_parent_password_second_hash
    )
    
    try:
        db = get_database()
        devices = get_devices_by_device_auth_token(db, device_auth_token)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            "Devices retrieved",
            duration_ms=duration_ms,
            request_id=request_id,
            count=len(devices),
            own_device_id=own_device_id,
            has_parent_password_second_hash=has_parent_password_second_hash
        )
        
        return jsonify({
            'status': 'ok',
            'count': len(devices),
            'devices': devices,
            'own_device_id': own_device_id,
            'has_parent_password_second_hash': has_parent_password_second_hash
        })
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "Devices request error",
            duration_ms=duration_ms,
            request_id=request_id,
            error=str(e)
        )
        return jsonify({
            'status': 'error',
            'error': 'Failed to retrieve devices'
        }), 500


@app.route('/api/dashboard/categories', methods=['GET'])
def api_dashboard_categories():
    """Get categories for the current device auth token.
    
    Returns:
        JSON response with categories list.
    """
    start_time = time.time()
    request_id = get_request_id()
    
    # Check authentication
    if 'device_auth_token' not in session:
        logger.warning(
            "Categories request without authentication",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'Not authenticated'
        }), 401
    
    device_auth_token = session.get('device_auth_token')
    if not device_auth_token:
        logger.warning(
            "Categories request without device_auth_token",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'No device auth token'
        }), 400
    
    logger.info(
        "Categories request",
        request_id=request_id,
        device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None
    )
    
    try:
        db = get_database()
        categories = get_categories_by_device_auth_token(db, device_auth_token)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            "Categories retrieved",
            duration_ms=duration_ms,
            request_id=request_id,
            count=len(categories)
        )
        
        return jsonify({
            'status': 'ok',
            'count': len(categories),
            'categories': categories
        })
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "Categories request error",
            duration_ms=duration_ms,
            request_id=request_id,
            error=str(e)
        )
        return jsonify({
            'status': 'error',
            'error': 'Failed to retrieve categories'
        }), 500


@app.route('/api/dashboard/categories/default', methods=['POST'])
def api_create_default_category():
    """Create a default category if none exists.
    
    This is used when a family is first created and the server
    returns an empty categoryBase array.
    
    Returns:
        JSON response with the created category or existing category.
    """
    start_time = time.time()
    request_id = get_request_id()
    
    # Check authentication
    if 'device_auth_token' not in session:
        logger.warning(
            "Create default category request without authentication",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'Not authenticated'
        }), 401
    
    device_auth_token = session.get('device_auth_token')
    if not device_auth_token:
        logger.warning(
            "Create default category request without device_auth_token",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'No device auth token'
        }), 400
    
    logger.info(
        "Create default category request",
        request_id=request_id,
        device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None
    )
    
    try:
        db = get_database()
        
        # Check if categories already exist
        existing_categories = get_categories_by_device_auth_token(db, device_auth_token)
        if existing_categories:
            logger.info(
                "Default category already exists",
                request_id=request_id,
                device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
                count=len(existing_categories)
            )
            return jsonify({
                'status': 'ok',
                'message': 'Categories already exist',
                'categories': existing_categories
            })
        
        # Create default category
        category = create_default_category(db, device_auth_token)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            "Default category created",
            duration_ms=duration_ms,
            request_id=request_id,
            device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
            category_id=category['id'] if category else None
        )
        
        if category:
            return jsonify({
                'status': 'ok',
                'category': category
            })
        else:
            return jsonify({
                'status': 'error',
                'error': 'Failed to create default category'
            }), 500
            
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "Create default category error",
            duration_ms=duration_ms,
            request_id=request_id,
            error=str(e)
        )
        return jsonify({
            'status': 'error',
            'error': 'Failed to create default category'
        }), 500


@app.route('/api/dashboard/categories', methods=['POST'])
def api_create_category():
    """Create a new category with the given title.
    
    This endpoint allows creating a new category with a free-format title.
    If a category with the same title already exists for this device,
    the existing category is returned instead of creating a new one.
    
    Request Body:
        title: The category title (free-format string, required)
        childId: Optional child ID for the category
    
    Returns:
        JSON response with the created or existing category.
    """
    start_time = time.time()
    request_id = get_request_id()
    
    # Check authentication
    if 'device_auth_token' not in session:
        logger.warning(
            "Create category request without authentication",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'Not authenticated'
        }), 401
    
    device_auth_token = session.get('device_auth_token')
    if not device_auth_token:
        logger.warning(
            "Create category request without device_auth_token",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'No device auth token'
        }), 400
    
    data = request.get_json() or {}
    
    # Validate required fields
    title = data.get('title', '').strip()
    if not title:
        return jsonify({
            'status': 'error',
            'error': 'Missing or empty title'
        }), 400
    
    child_id = data.get('childId')
    
    logger.info(
        "Create category request",
        request_id=request_id,
        device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
        title=title
    )
    
    try:
        from database import (
            get_database,
            get_categories_by_device_auth_token,
            create_category,
            get_category_by_title
        )
        
        db = get_database()
        
        # Check if a category with this title already exists
        existing_category = get_category_by_title(db, device_auth_token, title)
        if existing_category:
            logger.info(
                "Category with title already exists, returning existing",
                request_id=request_id,
                title=title,
                category_id=existing_category.get('id')
            )
            return jsonify({
                'status': 'ok',
                'category': existing_category,
                'message': 'Category already exists'
            })
        
        # Create new category
        category = create_category(
            db=db,
            device_auth_token=device_auth_token,
            title=title,
            child_id=child_id
        )
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            "Category created",
            duration_ms=duration_ms,
            request_id=request_id,
            device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
            category_id=category['id'],
            title=title
        )
        
        return jsonify({
            'status': 'ok',
            'category': category
        })
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "Create category error",
            duration_ms=duration_ms,
            request_id=request_id,
            error=str(e)
        )
        return jsonify({
            'status': 'error',
            'error': 'Failed to create category'
        }), 500


@app.route('/api/dashboard/connected-devices', methods=['GET'])
def api_dashboard_connected_devices():
    """Get connected devices for the current device auth token.
    
    Returns:
        JSON response with connected devices list.
    """
    start_time = time.time()
    request_id = get_request_id()
    
    # Check authentication
    if 'device_auth_token' not in session:
        logger.warning(
            "Connected devices request without authentication",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'Not authenticated'
        }), 401
    
    device_auth_token = session.get('device_auth_token')
    if not device_auth_token:
        logger.warning(
            "Connected devices request without device_auth_token",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'No device auth token'
        }), 400
    
    logger.info(
        "Connected devices request",
        request_id=request_id,
        device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None
    )
    
    try:
        db = get_database()
        devices = get_connected_devices(db, device_auth_token)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            "Connected devices retrieved",
            duration_ms=duration_ms,
            request_id=request_id,
            count=len(devices)
        )
        
        return jsonify({
            'status': 'ok',
            'count': len(devices),
            'devices': devices
        })
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "Connected devices request error",
            duration_ms=duration_ms,
            request_id=request_id,
            error=str(e)
        )
        return jsonify({
            'status': 'error',
            'error': 'Failed to retrieve connected devices'
        }), 500


@app.route('/api/dashboard/stream')
def api_dashboard_stream():
    """SSE endpoint for real-time dashboard updates.
    
    Returns:
        Server-Sent Events stream.
    """
    start_time = time.time()
    request_id = get_request_id()
    
    # Check authentication
    if 'device_auth_token' not in session:
        logger.warning(
            "SSE stream request without authentication",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'Not authenticated'
        }), 401
    
    device_auth_token = session.get('device_auth_token')
    if not device_auth_token:
        logger.warning(
            "SSE stream request without device_auth_token",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'No device auth token'
        }), 400
    
    logger.info(
        "SSE stream request",
        request_id=request_id,
        device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None
    )
    
    def event_stream():
        """Generator for SSE events."""
        q = get_event_queue(device_auth_token)
        max_keepalives = int(os.environ.get('TEST_MAX_KEEPALIVES', 0))
        keepalive_count = 0
        
        while True:
            try:
                event = q.get(timeout=30)
                data = json.dumps(event)
                yield f"data: {data}\n\n"
            except queue.Empty:
                # Send keepalive if configured
                if max_keepalives > 0:
                    keepalive_count += 1
                    if keepalive_count > max_keepalives:
                        break
                yield ": keepalive\n\n"
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    logger.info(
        "SSE stream started",
        duration_ms=duration_ms,
        request_id=request_id
    )
    
    return Response(event_stream(), mimetype='text/event-stream')


# ============================================================================
# Unified View API Route
# ============================================================================
@app.route('/api/dashboard/unified-view', methods=['GET'])
def api_dashboard_unified_view():
    """Get unified view data with users, rules, and devices.
    
    Returns:
        JSON response with unified view data including:
        - users: List of users with their associated rules and devices
        - categories: Dictionary mapping category_id to category title
        - own_device_id: The current device ID (for highlighting)
    """
    start_time = time.time()
    request_id = get_request_id()
    
    # Check authentication
    if 'device_auth_token' not in session:
        logger.warning(
            "Unified view request without authentication",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'Not authenticated'
        }), 401
    
    device_auth_token = session.get('device_auth_token')
    if not device_auth_token:
        logger.warning(
            "Unified view request without device_auth_token",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'No device auth token'
        }), 400
    
    logger.info(
        "Unified view request",
        request_id=request_id,
        device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None
    )
    
    try:
        from database import get_unified_view_data
        db = get_database()
        unified_data = get_unified_view_data(db, device_auth_token)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            "Unified view retrieved",
            duration_ms=duration_ms,
            request_id=request_id,
            users_count=len(unified_data.get('users', [])),
            categories_count=len(unified_data.get('categories', {}))
        )
        
        return jsonify({
            'status': 'ok',
            'users': unified_data.get('users', []),
            'categories': unified_data.get('categories', {}),
            'own_device_id': unified_data.get('own_device_id')
        })
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "Unified view request error",
            duration_ms=duration_ms,
            request_id=request_id,
            error=str(e)
        )
        return jsonify({
            'status': 'error',
            'error': 'Failed to retrieve unified view data'
        }), 500


# ============================================================================
# Time Limit Rules API Routes
# ============================================================================
@app.route('/api/dashboard/time-limit-rules', methods=['GET'])
def api_dashboard_time_limit_rules():
    """Get all time limit rules for the current device auth token.
    
    Returns:
        JSON response with list of rules.
    """
    start_time = time.time()
    request_id = get_request_id()
    
    # Check authentication
    if 'device_auth_token' not in session:
        logger.warning(
            "Time limit rules request without authentication",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'Not authenticated'
        }), 401
    
    device_auth_token = session.get('device_auth_token')
    if not device_auth_token:
        logger.warning(
            "Time limit rules request without device_auth_token",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'No device auth token'
        }), 400
    
    logger.info(
        "Time limit rules request",
        request_id=request_id,
        device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None
    )
    
    try:
        from database import (
            get_time_limit_rules_by_device_auth_token,
            get_users_by_device_auth_token,
            get_categories_by_device_auth_token,
            get_category_apps_by_device
        )
        db = get_database()
        rules = get_time_limit_rules_by_device_auth_token(db, device_auth_token)
        users = get_users_by_device_auth_token(db, device_auth_token)
        categories = get_categories_by_device_auth_token(db, device_auth_token)
        category_apps = get_category_apps_by_device(db, device_auth_token)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            "Time limit rules retrieved",
            duration_ms=duration_ms,
            request_id=request_id,
            count=len(rules),
            users_count=len(users),
            categories_count=len(categories),
            apps_count=sum(len(apps) for apps in category_apps.values())
        )
        
        return jsonify({
            'status': 'ok',
            'count': len(rules),
            'rules': rules,
            'users': users,
            'categories': categories,
            'categoryApps': category_apps
        })
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "Time limit rules request error",
            duration_ms=duration_ms,
            request_id=request_id,
            error=str(e)
        )
        return jsonify({
            'status': 'error',
            'error': 'Failed to retrieve time limit rules'
        }), 500


@app.route('/api/dashboard/time-limit-rules', methods=['POST'])
def api_create_time_limit_rule():
    """Create a new time limit rule.
    
    Request Body:
        userId: User ID the rule applies to
        categoryId: Category ID the rule applies to
        rule: Rule object with type, startTime, endTime, days, limitMinutes
    
    Returns:
        JSON response with the created rule ID.
    """
    start_time = time.time()
    request_id = get_request_id()
    
    # Check authentication
    if 'device_auth_token' not in session:
        logger.warning(
            "Create time limit rule request without authentication",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'Not authenticated'
        }), 401
    
    device_auth_token = session.get('device_auth_token')
    if not device_auth_token:
        logger.warning(
            "Create time limit rule request without device_auth_token",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'No device auth token'
        }), 400
    
    data = request.get_json() or {}
    
    # Validate required fields
    user_id = data.get('userId')
    if not user_id:
        return jsonify({
            'status': 'error',
            'error': 'Missing userId'
        }), 400
    
    category_id = data.get('categoryId')
    if not category_id:
        return jsonify({
            'status': 'error',
            'error': 'Missing categoryId'
        }), 400
    
    rule = data.get('rule')
    if not rule:
        return jsonify({
            'status': 'error',
            'error': 'Missing rule'
        }), 400
    
    # Validate rule fields
    start_time_str = rule.get('startTime')
    if start_time_str:
        import re
        if not re.match(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', start_time_str):
            return jsonify({
                'status': 'error',
                'error': 'Invalid startTime format'
            }), 400
    
    end_time_str = rule.get('endTime')
    if end_time_str:
        import re
        if not re.match(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', end_time_str):
            return jsonify({
                'status': 'error',
                'error': 'Invalid endTime format'
            }), 400
    
    days = rule.get('days', 127)
    if days is not None and (days < 0 or days > 127):
        return jsonify({
            'status': 'error',
            'error': 'Invalid days value'
        }), 400
    
    limit_minutes = rule.get('limitMinutes', 0)
    if limit_minutes is not None and limit_minutes < 0:
        return jsonify({
            'status': 'error',
            'error': 'Invalid limitMinutes'
        }), 400
    
    logger.info(
        "Create time limit rule request",
        request_id=request_id,
        device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
        user_id=user_id,
        category_id=category_id
    )
    
    try:
        from database import (
            save_time_limit_rule,
            get_database,
            get_parent_password_second_salt,
            get_parent_user_id,
            increment_sequence_number
        )
        from utils.audit_log import log_time_limit_rule_created
        
        db = get_database()
        
        # Generate rule ID
        import secrets
        rule_id = f'rule_{secrets.token_hex(8)}'
        
        save_time_limit_rule(
            db=db,
            rule_id=rule_id,
            device_auth_token=device_auth_token,
            user_id=user_id,
            category_id=category_id,
            rule_type=rule.get('type', 0),
            start_time=start_time_str,
            end_time=end_time_str,
            days=days,
            limit_minutes=limit_minutes,
            version=rule.get('version')
        )
        
        # Get parent's second password hash for sync integrity
        parent_password_second_hash = get_parent_password_second_salt(db, device_auth_token)
        parent_user_id = get_parent_user_id(db, device_auth_token)
        
        # Get sequence number for sync
        sequence_number = increment_sequence_number(db, device_auth_token)
        
        # Prepare rule data for sync
        sync_rule = {
            'type': rule.get('type', 0),
            'startTime': start_time_str,
            'endTime': end_time_str,
            'days': days,
            'limitMinutes': limit_minutes
        }
        
        # Push to server via sync protocol
        if parent_password_second_hash:
            auth_client = AuthClient()
            sync_response = auth_client.add_time_limit_rule(
                device_auth_token=device_auth_token,
                user_id=user_id,
                category_id=category_id,
                rule=sync_rule,
                sequence_number=sequence_number,
                parent_password_second_hash=parent_password_second_hash
            )
            
            if not sync_response.success:
                logger.warning(
                    "Failed to push time limit rule to server",
                    request_id=request_id,
                    rule_id=rule_id,
                    error_code=sync_response.error_code,
                    error_message=sync_response.error_message
                )
        
        # Log the rule creation for audit
        log_time_limit_rule_created(
            device_auth_token=device_auth_token,
            rule_id=rule_id,
            user_id=user_id,
            category_id=category_id,
            rule_type=rule.get('type', 0),
            start_time=start_time_str,
            end_time=end_time_str,
            days=days,
            limit_minutes=limit_minutes,
            version=rule.get('version'),
            request_id=request_id
        )
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            "Time limit rule created",
            duration_ms=duration_ms,
            request_id=request_id,
            rule_id=rule_id
        )
        
        return jsonify({
            'status': 'ok',
            'ruleId': rule_id
        })
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "Create time limit rule error",
            duration_ms=duration_ms,
            request_id=request_id,
            error=str(e)
        )
        return jsonify({
            'status': 'error',
            'error': 'Failed to create time limit rule'
        }), 500


@app.route('/api/dashboard/time-limit-rules/<rule_id>', methods=['PUT'])
def api_update_time_limit_rule(rule_id):
    """Update an existing time limit rule.
    
    Args:
        rule_id: The rule ID to update.
    
    Request Body:
        rule: Rule object with fields to update
    
    Returns:
        JSON response indicating success or failure.
    """
    start_time = time.time()
    request_id = get_request_id()
    
    # Check authentication
    if 'device_auth_token' not in session:
        logger.warning(
            "Update time limit rule request without authentication",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'Not authenticated'
        }), 401
    
    device_auth_token = session.get('device_auth_token')
    if not device_auth_token:
        logger.warning(
            "Update time limit rule request without device_auth_token",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'No device auth token'
        }), 400
    
    data = request.get_json() or {}
    rule_updates = data.get('rule', {})
    
    if not rule_updates:
        return jsonify({
            'status': 'error',
            'error': 'No updates provided'
        }), 400
    
    # Map JSON field names to database column names
    field_mapping = {
        'type': 'rule_type',
        'startTime': 'start_time',
        'endTime': 'end_time',
        'limitMinutes': 'limit_minutes',
        'userId': 'user_id',
        'categoryId': 'category_id',
        'version': 'version',
        'days': 'days'
    }
    
    mapped_updates = {}
    for json_key, value in rule_updates.items():
        if json_key in field_mapping:
            mapped_updates[field_mapping[json_key]] = value
        else:
            mapped_updates[json_key] = value
    
    logger.info(
        "Update time limit rule request",
        request_id=request_id,
        device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
        rule_id=rule_id
    )
    
    try:
        from database import (
            get_time_limit_rule_by_id,
            update_time_limit_rule,
            get_database,
            get_parent_password_second_salt,
            increment_sequence_number
        )
        from utils.audit_log import log_time_limit_rule_updated
        
        db = get_database()
        
        # Check if rule exists
        rule = get_time_limit_rule_by_id(db, rule_id)
        if not rule:
            return jsonify({
                'status': 'error',
                'error': 'Rule not found'
            }), 404
        
        # Update the rule
        result = update_time_limit_rule(db, rule_id, mapped_updates)
        
        if not result:
            return jsonify({
                'status': 'error',
                'error': 'No updates applied'
            }), 400
        
        # Get parent's second password hash for sync integrity
        parent_password_second_hash = get_parent_password_second_salt(db, device_auth_token)
        
        # Get sequence number for sync
        sequence_number = increment_sequence_number(db, device_auth_token)
        
        # Push update to server via sync protocol
        if parent_password_second_hash:
            auth_client = AuthClient()
            
            # Build update action for sync
            sync_updates = {}
            for json_key, value in mapped_updates.items():
                if json_key in ['rule_type', 'start_time', 'end_time', 'days', 'limit_minutes', 'version']:
                    # Map back to JSON field names
                    reverse_mapping = {
                        'rule_type': 'type',
                        'start_time': 'startTime',
                        'end_time': 'endTime',
                        'days': 'days',
                        'limit_minutes': 'limitMinutes',
                        'version': 'version'
                    }
                    sync_key = reverse_mapping.get(json_key, json_key)
                    sync_updates[sync_key] = value
            
            sync_response = auth_client.update_time_limit_rule(
                device_auth_token=device_auth_token,
                rule_id=rule_id,
                updates=sync_updates,
                sequence_number=sequence_number,
                parent_password_second_hash=parent_password_second_hash
            )
            
            if not sync_response.success:
                logger.warning(
                    "Failed to push time limit rule update to server",
                    request_id=request_id,
                    rule_id=rule_id,
                    error_code=sync_response.error_code,
                    error_message=sync_response.error_message
                )
        
        # Log the rule update for audit
        log_time_limit_rule_updated(
            device_auth_token=device_auth_token,
            rule_id=rule_id,
            updates=mapped_updates,
            request_id=request_id
        )
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            "Time limit rule updated",
            duration_ms=duration_ms,
            request_id=request_id,
            rule_id=rule_id
        )
        
        return jsonify({
            'status': 'ok',
            'message': 'Rule updated successfully'
        })
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "Update time limit rule error",
            duration_ms=duration_ms,
            request_id=request_id,
            error=str(e)
        )
        return jsonify({
            'status': 'error',
            'error': 'Failed to update time limit rule'
        }), 500


@app.route('/api/dashboard/time-limit-rules/<rule_id>', methods=['DELETE'])
def api_delete_time_limit_rule(rule_id):
    """Delete a time limit rule.
    
    Args:
        rule_id: The rule ID to delete.
    
    Returns:
        JSON response indicating success or failure.
    """
    start_time = time.time()
    request_id = get_request_id()
    
    # Check authentication
    if 'device_auth_token' not in session:
        logger.warning(
            "Delete time limit rule request without authentication",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'Not authenticated'
        }), 401
    
    device_auth_token = session.get('device_auth_token')
    if not device_auth_token:
        logger.warning(
            "Delete time limit rule request without device_auth_token",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'No device auth token'
        }), 400
    
    logger.info(
        "Delete time limit rule request",
        request_id=request_id,
        device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
        rule_id=rule_id
    )
    
    try:
        from database import (
            delete_time_limit_rule,
            get_database,
            get_time_limit_rule_by_id,
            get_parent_password_second_salt,
            increment_sequence_number
        )
        from utils.audit_log import log_time_limit_rule_deleted
        
        db = get_database()
        
        # Get the rule first to retrieve user_id for sync
        rule = get_time_limit_rule_by_id(db, rule_id)
        if not rule:
            return jsonify({
                'status': 'error',
                'error': 'Rule not found'
            }), 404
        
        user_id = rule.get('user_id')
        
        result = delete_time_limit_rule(db, rule_id)
        
        if not result:
            return jsonify({
                'status': 'error',
                'error': 'Rule not found'
            }), 404
        
        # Get parent's second password hash for sync integrity
        parent_password_second_hash = get_parent_password_second_salt(db, device_auth_token)
        
        # Get sequence number for sync
        sequence_number = increment_sequence_number(db, device_auth_token)
        
        # Push deletion to server via sync protocol
        if parent_password_second_hash:
            auth_client = AuthClient()
            sync_response = auth_client.remove_time_limit_rule(
                device_auth_token=device_auth_token,
                user_id=user_id,
                rule_id=rule_id,
                sequence_number=sequence_number,
                parent_password_second_hash=parent_password_second_hash
            )
            
            if not sync_response.success:
                logger.warning(
                    "Failed to push time limit rule deletion to server",
                    request_id=request_id,
                    rule_id=rule_id,
                    error_code=sync_response.error_code,
                    error_message=sync_response.error_message
                )
        
        # Log the rule deletion for audit
        log_time_limit_rule_deleted(
            device_auth_token=device_auth_token,
            rule_id=rule_id,
            request_id=request_id
        )
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            "Time limit rule deleted",
            duration_ms=duration_ms,
            request_id=request_id,
            rule_id=rule_id
        )
        
        return jsonify({
            'status': 'ok',
            'message': 'Rule deleted successfully'
        })
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "Delete time limit rule error",
            duration_ms=duration_ms,
            request_id=request_id,
            error=str(e)
        )
        return jsonify({
            'status': 'error',
            'error': 'Failed to delete time limit rule'
        }), 500


# ============================================================================
# Category Apps API Routes
# ============================================================================
@app.route('/api/dashboard/categories/<category_id>/apps', methods=['GET'])
def api_get_category_apps(category_id):
    """Get apps assigned to a category.
    
    Args:
        category_id: The category ID to get apps for.
    
    Returns:
        JSON response with list of app package names.
    """
    start_time = time.time()
    request_id = get_request_id()
    
    # Check authentication
    if 'device_auth_token' not in session:
        logger.warning(
            "Get category apps request without authentication",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'Not authenticated'
        }), 401
    
    device_auth_token = session.get('device_auth_token')
    if not device_auth_token:
        logger.warning(
            "Get category apps request without device_auth_token",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'No device auth token'
        }), 400
    
    logger.info(
        "Get category apps request",
        request_id=request_id,
        device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
        category_id=category_id
    )
    
    try:
        from database import (
            get_category_apps,
            get_database
        )
        db = get_database()
        apps = get_category_apps(db, device_auth_token, category_id)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            "Category apps retrieved",
            duration_ms=duration_ms,
            request_id=request_id,
            category_id=category_id,
            count=len(apps)
        )
        
        return jsonify({
            'status': 'ok',
            'categoryId': category_id,
            'apps': [app['app_package'] for app in apps]
        })
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "Get category apps error",
            duration_ms=duration_ms,
            request_id=request_id,
            error=str(e)
        )
        return jsonify({
            'status': 'error',
            'error': 'Failed to get category apps'
        }), 500


@app.route('/api/dashboard/categories/<category_id>/apps', methods=['POST'])
def api_add_apps_to_category(category_id):
    """Add apps to a category.
    
    Request Body:
        apps: List of app package names to add
        userId: User ID for the category (optional)
    
    Returns:
        JSON response indicating success or failure.
    """
    start_time = time.time()
    request_id = get_request_id()
    
    # Check authentication
    if 'device_auth_token' not in session:
        logger.warning(
            "Add apps to category request without authentication",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'Not authenticated'
        }), 401
    
    device_auth_token = session.get('device_auth_token')
    if not device_auth_token:
        logger.warning(
            "Add apps to category request without device_auth_token",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'No device auth token'
        }), 400
    
    data = request.get_json() or {}
    app_packages = data.get('apps', [])
    
    if not app_packages:
        return jsonify({
            'status': 'error',
            'error': 'No apps provided'
        }), 400
    
    user_id = data.get('userId')
    
    logger.info(
        "Add apps to category request",
        request_id=request_id,
        device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
        category_id=category_id,
        app_count=len(app_packages)
    )
    
    try:
        from database import (
            save_category_apps,
            get_database,
            get_parent_password_second_salt,
            get_parent_user_id,
            increment_sequence_number
        )
        from utils.audit_log import log_category_apps_added
        from auth_client import AuthClient
        
        db = get_database()
        
        # Save to database
        save_category_apps(
            db=db,
            device_auth_token=device_auth_token,
            category_id=category_id,
            app_packages=app_packages,
            user_id=user_id
        )
        
        # Get parent's second password hash for sync integrity
        parent_password_second_hash = get_parent_password_second_salt(db, device_auth_token)
        parent_user_id = get_parent_user_id(db, device_auth_token)
        
        # Get sequence number for sync
        sequence_number = increment_sequence_number(db, device_auth_token)
        
        # Push to server via sync protocol
        if parent_password_second_hash:
            auth_client = AuthClient()
            for app_package in app_packages:
                sync_response = auth_client.add_category_app(
                    device_auth_token=device_auth_token,
                    category_id=category_id,
                    app_package=app_package,
                    user_id=parent_user_id or user_id or '',
                    sequence_number=sequence_number,
                    parent_password_second_hash=parent_password_second_hash
                )
                
                if not sync_response.success:
                    logger.warning(
                        "Failed to push category app to server",
                        request_id=request_id,
                        category_id=category_id,
                        app_package=app_package,
                        error_code=sync_response.error_code,
                        error_message=sync_response.error_message
                    )
        
        # Log the operation for audit
        log_category_apps_added(
            device_auth_token=device_auth_token,
            category_id=category_id,
            app_packages=app_packages,
            user_id=user_id,
            request_id=request_id
        )
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            "Apps added to category",
            duration_ms=duration_ms,
            request_id=request_id,
            category_id=category_id,
            app_count=len(app_packages)
        )
        
        return jsonify({
            'status': 'ok',
            'categoryId': category_id,
            'appsAdded': len(app_packages)
        })
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "Add apps to category error",
            duration_ms=duration_ms,
            request_id=request_id,
            error=str(e)
        )
        return jsonify({
            'status': 'error',
            'error': 'Failed to add apps to category'
        }), 500


@app.route('/api/dashboard/categories/<category_id>/apps', methods=['DELETE'])
def api_remove_apps_from_category(category_id):
    """Remove apps from a category.
    
    Request Body:
        apps: List of app package names to remove
        userId: User ID for the category (optional)
    
    Returns:
        JSON response indicating success or failure.
    """
    start_time = time.time()
    request_id = get_request_id()
    
    # Check authentication
    if 'device_auth_token' not in session:
        logger.warning(
            "Remove apps from category request without authentication",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'Not authenticated'
        }), 401
    
    device_auth_token = session.get('device_auth_token')
    if not device_auth_token:
        logger.warning(
            "Remove apps from category request without device_auth_token",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'No device auth token'
        }), 400
    
    data = request.get_json() or {}
    app_packages = data.get('apps', [])
    
    if not app_packages:
        return jsonify({
            'status': 'error',
            'error': 'No apps provided'
        }), 400
    
    user_id = data.get('userId')
    
    logger.info(
        "Remove apps from category request",
        request_id=request_id,
        device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
        category_id=category_id,
        app_count=len(app_packages)
    )
    
    try:
        from database import (
            remove_category_apps,
            get_database,
            get_parent_password_second_salt,
            get_parent_user_id,
            increment_sequence_number
        )
        from utils.audit_log import log_category_apps_removed
        from auth_client import AuthClient
        
        db = get_database()
        
        # Remove from database
        removed_count = remove_category_apps(
            db=db,
            device_auth_token=device_auth_token,
            category_id=category_id,
            app_packages=app_packages
        )
        
        # Get parent's second password hash for sync integrity
        parent_password_second_hash = get_parent_password_second_salt(db, device_auth_token)
        parent_user_id = get_parent_user_id(db, device_auth_token)
        
        # Get sequence number for sync
        sequence_number = increment_sequence_number(db, device_auth_token)
        
        # Push to server via sync protocol
        if parent_password_second_hash:
            auth_client = AuthClient()
            for app_package in app_packages:
                sync_response = auth_client.remove_category_app(
                    device_auth_token=device_auth_token,
                    category_id=category_id,
                    app_package=app_package,
                    user_id=parent_user_id or user_id or '',
                    sequence_number=sequence_number,
                    parent_password_second_hash=parent_password_second_hash
                )
                
                if not sync_response.success:
                    logger.warning(
                        "Failed to push remove category app to server",
                        request_id=request_id,
                        category_id=category_id,
                        app_package=app_package,
                        error_code=sync_response.error_code,
                        error_message=sync_response.error_message
                    )
        
        # Log the operation for audit
        log_category_apps_removed(
            device_auth_token=device_auth_token,
            category_id=category_id,
            app_packages=app_packages,
            user_id=user_id,
            request_id=request_id
        )
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            "Apps removed from category",
            duration_ms=duration_ms,
            request_id=request_id,
            category_id=category_id,
            app_count=removed_count
        )
        
        return jsonify({
            'status': 'ok',
            'categoryId': category_id,
            'appsRemoved': removed_count
        })
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "Remove apps from category error",
            duration_ms=duration_ms,
            request_id=request_id,
            error=str(e)
        )
        return jsonify({
            'status': 'error',
            'error': 'Failed to remove apps from category'
        }), 500


# ============================================================================
# Add User to Family API Route
# ============================================================================
@app.route('/api/dashboard/users/add', methods=['POST'])
def api_add_user_to_family():
    """Add a new user (child) to the family.
    
    This endpoint implements the add-device flow:
    1. Create add-device token on the server
    2. Register the child device
    3. Sync users from the server
    4. Save users to the database
    
    Request Body:
        name: The child's display name (required)
        deviceName: Optional device name
        deviceModel: Optional device model
    
    Returns:
        JSON response with userId, deviceAuthToken, and ownDeviceId on success.
    """
    start_time = time.time()
    request_id = get_request_id()
    
    # Check authentication
    if 'device_auth_token' not in session:
        logger.warning(
            "Add user request without authentication",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'Not authenticated'
        }), 401
    
    device_auth_token = session.get('device_auth_token')
    if not device_auth_token:
        logger.warning(
            "Add user request without device_auth_token",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'No device auth token'
        }), 400
    
    # Check for parent password second hash
    parent_password_second_hash = session.get('parent_password_second_hash')
    if not parent_password_second_hash:
        # Fall back to database (same as session_status endpoint)
        db = get_database()
        parent_password_second_hash = get_parent_password_hash(db, device_auth_token)
    
    if not parent_password_second_hash:
        logger.warning(
            "Add user request without parent_password_second_hash",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'Missing parent_password_second_hash'
        }), 400
    
    data = request.get_json() or {}
    user_name = data.get('name')
    if not user_name:
        return jsonify({
            'status': 'error',
            'error': 'Missing user name'
        }), 400
    
    device_name = data.get('deviceName')
    device_model = data.get('deviceModel')
    
    # Convert empty strings to None for optional device info
    # This ensures consistent behavior with the add_device method
    if device_name == '':
        device_name = None
    if device_model == '':
        device_model = None
    
    # Get parent user ID from database
    db = get_database()
    parent_user_id = get_parent_user_id(db, device_auth_token)
    if not parent_user_id:
        logger.error(
            "Parent user ID not found for device_auth_token",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error_code': 'server_error',
            'error': 'Parent user ID not found'
        }), 500
    
    logger.info(
        "Add user request",
        request_id=request_id,
        device_auth_token=device_auth_token[:8] + '...',
        parent_user_id=parent_user_id,
        user_name=user_name
    )
    
    # Log the request
    log_add_user_request(
        device_auth_token=device_auth_token,
        parent_user_id=parent_user_id,
        user_name=user_name,
        device_name=device_name,
        device_model=device_model,
        request_id=request_id,
        server_url=get_current_server_url()
    )
    
    try:
        # Create AuthClient
        server_url = get_current_server_url()
        client = AuthClient(base_url=server_url)
        
        # Step 1: Create add-device token
        token_response = client.create_add_device_token(
            device_auth_token=device_auth_token,
            parent_id=parent_user_id,
            parent_password_second_hash=parent_password_second_hash
        )
        
        if not token_response.success:
            log_add_user_response(
                device_auth_token=device_auth_token,
                parent_user_id=parent_user_id,
                user_id=None,
                child_device_auth_token=None,
                own_device_id=None,
                success=False,
                error_code=token_response.error_code,
                error_message=token_response.error_message,
                request_id=request_id
            )
            return jsonify({
                'status': 'error',
                'error_code': token_response.error_code,
                'error': token_response.error_message
            }), 500
        
        register_token = token_response.data.get('token')
        
        # Step 2: Add device (register child)
        add_device_response = client.add_device(
            register_token=register_token,
            device_name=device_name,
            device_model=device_model,
            client_level=7  # Default client level
        )
        
        if not add_device_response.success:
            log_add_user_response(
                device_auth_token=device_auth_token,
                parent_user_id=parent_user_id,
                user_id=None,
                child_device_auth_token=None,
                own_device_id=None,
                success=False,
                error_code=add_device_response.error_code,
                error_message=add_device_response.error_message,
                request_id=request_id
            )
            return jsonify({
                'status': 'error',
                'error_code': add_device_response.error_code,
                'error': add_device_response.error_message
            }), 500
        
        child_device_auth_token = add_device_response.data.get('deviceAuthToken')
        own_device_id = add_device_response.data.get('ownDeviceId')
        
        # Step 3: Pull status to get users
        # Use parent's device_auth_token to fetch users that belong to the family
        # Force a full sync with empty versions to ensure the newly created user is returned
        # The server only returns changes based on version hashes, so we need to send
        # empty versions to get all users including the newly added one
        empty_client_status = {
            "clientLevel": 7,
            "devices": "",
            "users": "",
            "apps": {},
            "categories": {}
        }
        pull_response = client.pull_status(device_auth_token=device_auth_token, client_data_status=empty_client_status)
        
        if not pull_response.success:
            log_add_user_response(
                device_auth_token=device_auth_token,
                parent_user_id=parent_user_id,
                user_id=None,
                child_device_auth_token=None,
                own_device_id=None,
                success=False,
                error_code=pull_response.error_code,
                error_message=pull_response.error_message,
                request_id=request_id
            )
            return jsonify({
                'status': 'error',
                'error_code': pull_response.error_code,
                'error': pull_response.error_message
            }), 500
        
        # Step 4: Save users to database
        # Users are saved with the parent's device_auth_token so they can be retrieved
        # by the dashboard when querying with the parent's token
        users_data = pull_response.data.get('users', {}).get('data', [])
        
        # Log the users data received from pull_status
        logger.debug(
            "Pull status returned users data",
            request_id=request_id,
            device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
            users_count=len(users_data),
            users=[{"id": u.get('id'), "name": u.get('name'), "type": u.get('type')} for u in users_data]
        )
        
        if users_data:
            save_users(db=db, device_auth_token=device_auth_token, users_data=users_data)
        
        # Find the new user
        new_user = None
        for user in users_data:
            if user.get('name') == user_name:
                new_user = user
                break
        
        user_id = new_user.get('id') if new_user else None
        
        # If user not found in pull_status response, create a user record locally
        # This handles the case where the server hasn't yet propagated the user
        # (timing issue between device creation and user availability)
        if user_id is None:
            # Create a user record with the device ID as the user ID
            # The server creates a user for each device, so the user ID should be the device ID
            device_id = own_device_id
            if device_id:
                # Create a minimal user record for the new device
                create_user(
                    db=db,
                    user_id=device_id,
                    device_auth_token=device_auth_token,
                    name=user_name,
                    user_type='child'
                )
                user_id = device_id
                logger.info(
                    "Created user record locally for newly added device",
                    request_id=request_id,
                    user_id=user_id,
                    user_name=user_name
                )
        
        # Update sync state to record the last sync timestamp
        # This ensures the family overview shows the correct last_sync time
        device_version = pull_response.data.get('devices', {}).get('version')
        user_version = pull_response.data.get('users', {}).get('version')
        save_sync_state(db=db, device_auth_token=device_auth_token, device_list_version=device_version, user_list_version=user_version)
        logger.info(
            "Sync state updated after adding user",
            request_id=request_id,
            device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
            device_version=device_version,
            user_version=user_version
        )
        
        client.close()
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        log_add_user_response(
            device_auth_token=device_auth_token,
            parent_user_id=parent_user_id,
            user_id=user_id,
            child_device_auth_token=child_device_auth_token,
            own_device_id=own_device_id,
            success=True,
            status_code=200,
            request_id=request_id
        )
        
        logger.info(
            "Add user successful",
            duration_ms=duration_ms,
            request_id=request_id,
            user_id=user_id
        )
        
        return jsonify({
            'status': 'ok',
            'userId': user_id,
            'deviceAuthToken': child_device_auth_token,
            'ownDeviceId': own_device_id
        })
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "Add user error",
            duration_ms=duration_ms,
            request_id=request_id,
            error=str(e)
        )
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


# ============================================================================
# Family Overview API Route
# ============================================================================
@app.route('/api/dashboard/family-overview', methods=['GET'])
def api_dashboard_family_overview():
    """Get family overview data.
    
    Returns:
        JSON response with family_email, devices_count, users_count, last_sync.
    """
    start_time = time.time()
    request_id = get_request_id()
    
    # Check authentication
    if 'device_auth_token' not in session:
        logger.warning(
            "Family overview request without authentication",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'Not authenticated'
        }), 401
    
    device_auth_token = session.get('device_auth_token')
    if not device_auth_token:
        logger.warning(
            "Family overview request without device_auth_token",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'No device auth token'
        }), 400
    
    logger.info(
        "Family overview request",
        request_id=request_id,
        device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None
    )
    
    try:
        db = get_database()
        # Get family record
        family = get_family(db, device_auth_token)
        family_email = family.get('mail') if family else None
        
        # Fall back to session mail if database has pending@unknown
        session_mail = session.get('mail')
        if family_email == 'pending@unknown' and session_mail:
            family_email = session_mail
        
        # Get devices count
        devices = get_devices_by_device_auth_token(db, device_auth_token)
        devices_count = len(devices) if devices else 0
        
        # Get users count
        users = get_users_by_device_auth_token(db, device_auth_token)
        users_count = len(users) if users else 0
        
        # Get last sync timestamp
        sync_state = get_sync_state(db, device_auth_token)
        last_sync_timestamp = sync_state.get('last_sync_timestamp') if sync_state else None
        
        # Convert timestamp to ISO string for JavaScript
        last_sync = None
        if last_sync_timestamp:
            last_sync = datetime.fromtimestamp(last_sync_timestamp / 1000, tz=timezone.utc).isoformat()
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            "Family overview retrieved",
            duration_ms=duration_ms,
            request_id=request_id,
            devices_count=devices_count,
            users_count=users_count
        )
        
        return jsonify({
            'status': 'ok',
            'family_email': family_email,
            'devices_count': devices_count,
            'users_count': users_count,
            'last_sync': last_sync
        })
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "Family overview error",
            duration_ms=duration_ms,
            request_id=request_id,
            error=str(e)
        )
        return jsonify({
            'status': 'error',
            'error': 'Failed to retrieve family overview'
        }), 500


# ============================================================================
# Timechecker Dashboard Routes
# ============================================================================
@app.route('/api/timechecker/status', methods=['GET'])
def timechecker_status():
    """Get the current server check status.
    
    Returns:
        JSON response with the current server check result.
    """
    start_time = time.time()
    request_id = get_request_id()
    server_url = get_current_server_url()
    
    logger.info(
        "Timechecker status request",
        server_url=server_url,
        request_id=request_id
    )
    
    # Perform a server check
    client = AuthClient(base_url=server_url)
    response = client.check_server_connection()
    client.close()
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    if response.success:
        logger.info(
            "Timechecker status check successful",
            server_url=server_url,
            success=True,
            duration_ms=duration_ms,
            request_id=request_id
        )
    else:
        logger.error(
            "Timechecker status check failed",
            server_url=server_url,
            success=False,
            error_code=response.error_code,
            error_message=response.error_message,
            duration_ms=duration_ms,
            request_id=request_id
        )
    
    return jsonify({
        'success': response.success,
        'server_time': response.data.get('ms') if response.success else None,
        'error_code': response.error_code,
        'error_message': response.error_message,
        'timestamp': int(datetime.now().timestamp() * 1000),
        'attempts': 1
    })

@app.route('/api/timechecker/history', methods=['GET'])
def timechecker_history():
    """Get historical server check results.
    
    Note: Server checks are no longer stored in the database.
    This endpoint returns an empty list.
    
    Query Parameters:
        limit: Maximum number of results to return (default: 10) - ignored
    
    Returns:
        JSON response with empty checks array.
    """
    start_time = time.time()
    request_id = get_request_id()
    server_url = get_current_server_url()
    limit = request.args.get('limit', 10, type=int)
    
    logger.info(
        "Timechecker history request",
        server_url=server_url,
        limit=limit,
        request_id=request_id
    )
    
    # Server checks are no longer stored, return empty list
    server_checks = []
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    logger.info(
        "Timechecker history retrieved",
        server_url=server_url,
        total_checks=0,
        duration_ms=duration_ms,
        request_id=request_id
    )
    
    return jsonify({
        'checks': server_checks,
        'total': 0
    })




# ============================================================================
# Health Check
# ============================================================================

@app.route('/health')
def health():
    """Health check endpoint.
    
    Returns:
        JSON response with health status.
    """
    request_id = get_request_id()
    
    logger.info("Health check requested", request_id=request_id)
    
    return jsonify({'status': 'healthy'})


# ============================================================================
# Debug Database Viewer Route
# ============================================================================

@app.route('/debug/database')
def debug_database():
    """Render the database viewer page.
    
    This route renders the debug_database.html template which displays
    all tables and their contents for debugging purposes.
    
    Returns:
        Rendered HTML template with database contents.
    """
    request_id = get_request_id()
    
    logger.info("Debug database page requested", request_id=request_id)
    
    try:
        db = get_database()
        tables_data = get_all_tables_data(db)
        
        # Extract table names for the template
        tables = list(tables_data.keys())
        
        logger.info(
            "Database data retrieved for debug view",
            request_id=request_id,
            table_count=len(tables_data)
        )
        
        return render_template('debug_database.html', tables=tables, table_data=tables_data)
    except Exception as e:
        logger.error(
            "Failed to retrieve database data for debug view",
            request_id=request_id,
            error=str(e)
        )
        return jsonify({
            'status': 'error',
            'error': 'Failed to retrieve database data'
        }), 500


# ============================================================================
# Set Parent Password Routes (Server-Side Rendered)
# ============================================================================

@app.route('/set-parent-password', methods=['GET'])
def get_set_parent_password():
    """Render the set parent password page.
    
    Returns:
        Rendered HTML template with the password form.
    """
    request_id = get_request_id()
    
    # Check if authenticated
    if 'device_auth_token' not in session:
        logger.info("User not authenticated, redirecting to dashboard", request_id=request_id)
        return redirect('/dashboardV2')
    
    logger.info("Rendering set parent password page", request_id=request_id)
    return render_template('set_parent_password.html')


@app.route('/set-parent-password', methods=['POST'])
def post_set_parent_password():
    """Process set parent password form submission.
    
    Handles two cases:
    1. Direct hash input via parentPasswordSecondHash field
    2. Password hashing via password field
    
    Returns:
        Redirect to dashboard on success.
    """
    start_time = time.time()
    request_id = get_request_id()
    
    # Check authentication
    if 'device_auth_token' not in session:
        logger.warning("Set parent password attempted without authentication", request_id=request_id)
        return redirect('/dashboardV2')
    
    device_auth_token = session.get('device_auth_token')
    if not device_auth_token:
        logger.warning("Set parent password attempted without device_auth_token", request_id=request_id)
        return redirect('/dashboardV2')
    
    # Get form data
    password = request.form.get('password', '').strip()
    parent_password_second_hash = request.form.get('parentPasswordSecondHash', '').strip()
    
    # Determine which input was provided
    if parent_password_second_hash:
        # Direct hash input - use as-is (only secondHash is provided)
        hash_to_store = parent_password_second_hash
        hash_to_store_full = None
    elif password:
        # Password provided - hash it using generate_family_hashes
        try:
            password_data = generate_family_hashes(password)
            hash_to_store = password_data['secondHash']
            hash_to_store_full = password_data
        except Exception as e:
            session['set_parent_password_error'] = f'Failed to hash password: {str(e)}'
            logger.error("Failed to hash password", error=str(e), request_id=request_id)
            return redirect('/set-parent-password')
    else:
        session['set_parent_password_error'] = 'Either password or hash is required'
        logger.warning("Set parent password: missing password and hash", request_id=request_id)
        return redirect('/set-parent-password')
    
    # Store hash in session
    session['parent_password_second_hash'] = hash_to_store
    
    # Store hash in database
    db = get_database()
    if hash_to_store_full:
        # Store all three hash components when password was provided
        upsert_family_password_hash(
            db=db,
            device_auth_token=device_auth_token,
            parent_password_second_hash=hash_to_store,
            parent_password_hash=hash_to_store_full['hash'],
            parent_password_second_salt=hash_to_store_full['secondSalt']
        )
    else:
        # Store only secondHash when direct hash input was provided
        upsert_family_password_hash(
            db=db,
            device_auth_token=device_auth_token,
            parent_password_second_hash=hash_to_store
        )
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    logger.info(
        "Parent password hash set successfully",
        device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
        duration_ms=duration_ms,
        request_id=request_id
    )
    
    session['set_parent_password_success'] = 'Password hash saved successfully'
    return redirect('/dashboardV2')


# ============================================================================
# Clear All Data Endpoint
# ============================================================================

@app.route('/api/clear-all', methods=['POST'])
def api_clear_all():
    """Clear all data from the dashboard.
    
    This endpoint clears:
    - All database tables
    - Session data
    - Auth tokens from persistence
    - Server selection
    
    Returns:
        JSON response with status and details of cleared data.
    """
    start_time = time.time()
    request_id = get_request_id()
    
    logger.info("Clear all data request", request_id=request_id)
    
    # Clear database tables
    db = get_database()
    tables_cleared = clear_all_tables(db)
    
    # Clear session
    session.clear()
    
    # Clear persisted auth tokens
    clear_persisted_auth_tokens()
    
    # Clear server selection
    clear_server_selection()
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    logger.info(
        "Clear all data completed",
        tables_cleared=tables_cleared,
        duration_ms=duration_ms,
        request_id=request_id
    )
    
    return jsonify({
        'status': 'ok',
        'tables_cleared': tables_cleared,
        'message': 'All data cleared successfully',
        'duration_ms': duration_ms
    })


# ============================================================================
# Clear Server Checks Endpoint
# ============================================================================

@app.route('/api/clear-server-checks', methods=['POST'])
def api_clear_server_checks():
    """Clear all server check records from the database.
    
    This endpoint removes all historical server check records from the
    server_checks table. This is useful when the user wants to start fresh
    without historical data.
    
    Returns:
        JSON response with status and count of cleared records.
    """
    start_time = time.time()
    request_id = get_request_id()
    
    logger.info("Clear server checks request", request_id=request_id)
    
    # Clear server checks from database
    db = get_database()
    count = clear_server_checks(db)
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    logger.info(
        "Clear server checks completed",
        rows_deleted=count,
        duration_ms=duration_ms,
        request_id=request_id
    )
    
    return jsonify({
        'status': 'ok',
        'rows_deleted': count,
        'message': f'Server checks cleared successfully ({count} records removed)',
        'duration_ms': duration_ms
    })


# ============================================================================
# Auth Token Backup Endpoints
# ============================================================================

@app.route('/api/auth/backup', methods=['POST'])
def api_auth_backup():
    """Create a backup of auth tokens.
    
    Returns:
        JSON response with backup status and token information.
    """
    start_time = time.time()
    request_id = get_request_id()
    
    logger.info("Auth token backup request", request_id=request_id)
    
    # Create backup
    backup_result = backup_auth_tokens()
    
    # Fallback: check session for own_device_id if not found in database/JSON
    if backup_result.get('own_device_id') is None:
        session_own_device_id = session.get('own_device_id')
        if session_own_device_id is not None:
            backup_result['own_device_id'] = session_own_device_id
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    logger.info(
        "Auth token backup completed",
        backup_successful=backup_result.get('backup_successful'),
        has_device_auth_token=backup_result.get('device_auth_token') is not None,
        has_own_device_id=backup_result.get('own_device_id') is not None,
        duration_ms=duration_ms,
        request_id=request_id
    )
    
    return jsonify({
        'status': 'ok',
        'backup_successful': backup_result.get('backup_successful', False),
        'device_auth_token': backup_result.get('device_auth_token'),
        'own_device_id': backup_result.get('own_device_id'),
        'has_device_auth_token': backup_result.get('device_auth_token') is not None,
        'has_own_device_id': backup_result.get('own_device_id') is not None,
        'error': backup_result.get('error')
    })


@app.route('/api/auth/restore', methods=['POST'])
def api_auth_restore():
    """Restore auth tokens from backup.
    
    Returns:
        JSON response with restore status.
    """
    start_time = time.time()
    request_id = get_request_id()
    
    logger.info("Auth token restore request", request_id=request_id)
    
    # Restore from backup
    restore_result = restore_auth_tokens()
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    logger.info(
        "Auth token restore completed",
        restore_successful=restore_result.get('restore_successful'),
        has_device_auth_token=restore_result.get('device_auth_token') is not None,
        has_own_device_id=restore_result.get('own_device_id') is not None,
        duration_ms=duration_ms,
        request_id=request_id
    )
    
    return jsonify({
        'status': 'ok',
        'restore_successful': restore_result.get('restore_successful', False),
        'device_auth_token': restore_result.get('device_auth_token'),
        'own_device_id': restore_result.get('own_device_id'),
        'error': restore_result.get('error')
    })


@app.route('/api/auth/clear-backup', methods=['POST'])
def api_auth_clear_backup():
    """Clear the auth token backup file.
    
    Returns:
        JSON response with clear status.
    """
    start_time = time.time()
    request_id = get_request_id()
    
    logger.info("Auth token backup clear request", request_id=request_id)
    
    # Clear backup
    cleared = clear_auth_token_backup()
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    logger.info(
        "Auth token backup clear completed",
        cleared=cleared,
        duration_ms=duration_ms,
        request_id=request_id
    )
    
    return jsonify({
        'status': 'ok',
        'cleared': cleared
    })


# ============================================================================
# Dashboard Device Removal Endpoint
# ============================================================================

@app.route('/api/dashboard/devices/remove', methods=['POST'])
def api_dashboard_devices_remove():
    """Remove a device from the family.
    
    Expects JSON body with 'deviceId' field.
    
    Returns:
        JSON response with status.
    """
    start_time = time.time()
    request_id = get_request_id()
    
    # Check authentication
    if 'device_auth_token' not in session:
        logger.warning("Device removal attempted without authentication", request_id=request_id)
        return jsonify({
            'status': 'error',
            'error': 'Not authenticated'
        }), 401
    
    device_auth_token = session.get('device_auth_token')
    if not device_auth_token:
        logger.warning("Device removal attempted without device_auth_token", request_id=request_id)
        return jsonify({
            'status': 'error',
            'error': 'No device auth token'
        }), 400
    
    # Get request data
    data = request.get_json() or {}
    device_id = data.get('deviceId')
    
    if not device_id:
        logger.warning("Device removal attempted without deviceId", request_id=request_id)
        return jsonify({
            'status': 'error',
            'error': 'Missing deviceId'
        }), 400
    
    # Get parent password hash from session
    parent_password_second_hash = session.get('parent_password_second_hash')
    if not parent_password_second_hash:
        logger.warning("Device removal attempted without parent password hash", request_id=request_id)
        return jsonify({
            'status': 'error',
            'error': 'Parent password hash not set. Please set it first via /set-parent-password'
        }), 400
    
    # Get own_device_id to prevent self-removal
    own_device_id = session.get('own_device_id')
    if own_device_id and own_device_id == device_id:
        logger.warning("Device removal attempted for own device", request_id=request_id)
        return jsonify({
            'status': 'error',
            'error': 'Cannot remove the current device'
        }), 400
    
    # Get parent_user_id from session or database
    parent_user_id = session.get('parent_user_id')
    if not parent_user_id:
        db = get_database()
        parent_user_id = get_parent_user_id(db, device_auth_token)
    
    if not parent_user_id:
        logger.warning("Device removal attempted without parent_user_id", request_id=request_id)
        return jsonify({
            'status': 'error',
            'error': 'Parent user ID not found'
        }), 400
    
    # Get server URL
    server_url = get_current_server_url()
    
    logger.info(
        "Device removal request",
        device_id=device_id,
        parent_user_id=parent_user_id,
        device_auth_token=device_auth_token[:8] + '...',
        request_id=request_id
    )
    
    # Call the server's remove-device endpoint
    client = AuthClient(base_url=server_url)
    response = client.remove_device(
        device_auth_token=device_auth_token,
        parent_user_id=parent_user_id,
        parent_password_second_hash=parent_password_second_hash,
        device_id=device_id
    )
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    if response.success:
        logger.info(
            "Device removed successfully",
            device_id=device_id,
            duration_ms=duration_ms,
            request_id=request_id
        )
        return jsonify({
            'status': 'ok',
            'message': 'Device removed successfully'
        })
    else:
        logger.error(
            "Device removal failed",
            device_id=device_id,
            error_code=response.error_code,
            error_message=response.error_message,
            duration_ms=duration_ms,
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error_code': response.error_code,
            'error_message': response.error_message
        }), response.status_code


# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    request_id = get_request_id()
    
    logger.error(
        "404 Not Found",
        path=request.path,
        method=request.method,
        request_id=request_id
    )
    
    return jsonify({'status': 'error', 'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    request_id = get_request_id()
    
    logger.error(
        "500 Internal Server Error",
        path=request.path,
        method=request.method,
        error=str(error),
        request_id=request_id
    )
    
    return jsonify({'status': 'error', 'error': 'Internal server error'}), 500


# ============================================================================
# Application Factory
# ============================================================================

def create_app(config_class: Optional[type] = None) -> Flask:
    """Create and configure the Flask application.
    
    Args:
        config_class: Optional configuration class to use.
        
    Returns:
        Configured Flask application instance.
    """
    if config_class:
        app.config.from_object(config_class)
    
    # Initialize database
    db = get_database()
    db.init_db()
    
    # Note: Server selection persistence is handled via:
    # 1. The /api/server-selection endpoint for saving selections
    # 2. The get_current_server_url() function which checks persistent storage first
    # 3. Flask session for request-scoped server URL
    
    logger.info(
        "Flask application created",
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG,
        secret_key_set=bool(config.SECRET_KEY),
        database_path=config.DATABASE_PATH
    )
    
    return app


# ============================================================================
# Scheduler Initialization
# ============================================================================

# Check port availability before starting the scheduler (fail fast)
# This ensures we exit early if the port is already in use, before
# any resources (like the scheduler) are allocated.
# Skip port check during testing (set SKIP_PORT_CHECK=true in environment)
if os.environ.get('SKIP_PORT_CHECK', 'false').lower() != 'true':
    check_port_available(config.FLASK_HOST, config.FLASK_PORT)

# Get the persisted server URL (if any) to initialize the scheduler
persisted_server_url = get_current_server_url()
if persisted_server_url != config.DEBUG_SERVER_URL:
    logger.info(
        "Initializing scheduler with persisted server URL",
        server_url=persisted_server_url
    )

# Start the background scheduler for periodic server checks
start_scheduler()

# Update the scheduler with the correct server URL
# (either persisted or default)
set_server_url(persisted_server_url)

# Register shutdown handler to stop the scheduler gracefully
atexit.register(stop_scheduler)


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == '__main__':
    # Initialize database
    db = get_database()
    db.init_db()
    
    # Create config instance
    config = Config()
    
    # Log application startup
    logger.info(
        "Dashboard V2 application starting",
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG,
        database_path=config.DATABASE_PATH,
        server_url=config.DEBUG_SERVER_URL,
        secret_key_set=bool(config.SECRET_KEY),
        ha_ingress=config.HA_INGRESS
    )
    
    # Log server selection options
    logger.info(
        "Server selection options configured",
        server_options=list(Config.SERVER_OPTIONS.keys())
    )
    
    # Log route registration
    logger.info(
        "Routes registered",
        routes=[
            '/', '/legacy-dashboard', '/dashboard.html', '/dashboardV2',
            '/select-server', '/api/server-selection', '/api/time',
            '/api/auth/send-mail-login-code', '/api/auth/sign-in-by-mail-code',
            '/api/auth/create-family', '/api/families', '/api/auth/sign-in-into-family',
            '/api/parent/create-add-device-token', '/api/child/add-device',
            '/api/auth/get-status-by-mail-address', '/api/auth/recover-parent-password',
            '/api/session/clear', '/api/session/status',
            '/api/sync/pull',
            '/api/dashboard/users', '/api/dashboard/devices', '/api/dashboard/categories',
            '/api/dashboard/connected-devices', '/api/dashboard/stream',
            '/api/dashboard/unified-view', '/api/dashboard/time-limit-rules',
            '/api/dashboard/time-limit-rules/<rule_id>', '/api/dashboard/users/add',
            '/api/dashboard/family-overview',
            '/api/timechecker/status', '/api/timechecker/history',
            '/health',
            '/create-family', '/create-family/cancel'
        ]
    )
    
    # Run the Flask app
    # Note: Server selection persistence is handled via the /api/server-selection endpoint
    # and the get_current_server_url() function which checks persistent storage first
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG,
        threaded=True
    )