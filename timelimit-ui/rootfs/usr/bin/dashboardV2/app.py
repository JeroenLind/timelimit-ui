"""Flask application for dashboardV2.

This module provides the main Flask application with all routes and logic
for the new dashboard. It handles:
- Session management
- Server selection with persistence
- API proxy endpoints
- Static file serving

The application is designed to run on both Windows laptop and Home Assistant
as an ingress app.
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
    Database, get_database, reset_database, save_server_check, get_server_checks, get_latest_server_check, store_auth_token,
    get_users_by_family, get_devices_by_family, get_categories_by_family, get_connected_devices
)
from middleware.request_logging import init_request_logging, shutdown_log_worker, get_request_id
from persistence import get_server_selection_store, is_ha_ingress, get_current_log_level, set_current_log_level
from scheduler import start_scheduler, stop_scheduler
from sync_manager import SyncManager, create_sync_manager, get_event_queue
from utils.logging import setup_structlog, get_logger, set_log_level, get_log_level

# Add parent directory to sys.path for crypto_utils import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crypto_utils import generate_family_hashes

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
    server_key = persistence_store.get_selected_server_key()
    if server_key:
        server_url = Config.get_server_url(server_key)
        if server_url:
            return server_url
    
    # Fall back to session
    if 'server_url' in session:
        return session['server_url']
    
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
    is_authenticated = device_auth_token is not None
    
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
        locale=locale
    )
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    if response.success:
        # Store device auth token in session
        session['device_auth_token'] = response.data.get('deviceAuthToken')
        session['own_device_id'] = response.data.get('ownDeviceId')
        
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
        locale=locale
    )
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    if response.success:
        # Store device auth token in session
        session['device_auth_token'] = response.data.get('deviceAuthToken')
        session['own_device_id'] = response.data.get('ownDeviceId')
        
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
            locale=locale if locale else None
        )
        
        if response.success:
            # Store device auth token in session
            session['device_auth_token'] = response.data.get('deviceAuthToken')
            session['own_device_id'] = response.data.get('ownDeviceId')
            
            # Extract and store family_id from initialData if present
            initial_data = response.data.get('initialData', {})
            family_id = initial_data.get('familyId')
            
            # If family_id not in initialData, check data field
            if not family_id:
                data_field = response.data.get('data', {})
                family_id = data_field.get('familyId')
            
            # If still not found, perform pull_status to get family_id
            if not family_id:
                logger.info("Family ID not in response, performing pull_status", request_id=request_id)
                pull_response = client.pull_status(
                    device_auth_token=response.data.get('deviceAuthToken')
                )
                if pull_response.success:
                    # Extract family_id from pull_status response
                    # The response may have familyId at the top level or in data
                    family_id = pull_response.data.get('familyId')
                    if not family_id:
                        data_field = pull_response.data.get('data', {})
                        family_id = data_field.get('familyId')
                    
                    # If still not found, set error for user feedback
                    if not family_id:
                        error_msg = 'Failed to retrieve family information from server'
                        session['login_error'] = error_msg
                        logger.warning("Family ID not found in pull_status response", error_message=error_msg, request_id=request_id)
                else:
                    # Store the pull_status error for user feedback
                    # Error message may be in error_message or data field
                    error_msg = pull_response.error_message
                    if not error_msg and pull_response.data:
                        # Extract error from HTML response in data field
                        data_str = str(pull_response.data)
                        if 'BadRequestError' in data_str:
                            error_msg = 'Server error: Invalid request format'
                        else:
                            error_msg = 'Failed to retrieve family information'
                    # Ensure we have an error message
                    error_msg = error_msg or 'Failed to retrieve family information'
                    session['login_error'] = error_msg
                    logger.warning("Failed to pull server status during family creation", error_message=error_msg, request_id=request_id)
            
            if family_id:
                session['family_id'] = family_id
                logger.info("Family ID extracted and stored in session", family_id=family_id, request_id=request_id)
                
                # Store auth token in database for later lookup
                if response.data.get('deviceAuthToken'):
                    db = get_database()
                    store_auth_token(
                        db=db,
                        token_type='device_auth_token',
                        token_value=response.data.get('deviceAuthToken'),
                        device_id=response.data.get('ownDeviceId'),
                        family_id=family_id
                    )
                    logger.info("Auth token stored in database", family_id=family_id, request_id=request_id)
            
            # Clear temporary session data
            session.pop('mail_login_token', None)
            session.pop('mail_auth_token', None)
            
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
    session.pop('device_auth_token', None)
    session.pop('own_device_id', None)
    session.pop('family_id', None)
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
    
    Handles all three steps of the login as parent flow:
    - Step 1: Send mail login code
    - Step 2: Sign in by mail code
    - Step 3: Sign in to family
    
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
        # Step 3: Sign in to family
        mail_auth_token = session.get('mail_auth_token')
        device_model = request.form.get('deviceModel', '').strip()
        device_name = request.form.get('deviceName', '').strip()
        
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
            device_name=device_name,
            device_model=device_model,
            client_level=7  # Matches Android app's ClientDataStatus.CLIENT_LEVEL_VALUE
        )
        
        if response.success:
            # Store device auth token in session
            session['device_auth_token'] = response.data.get('deviceAuthToken')
            session['own_device_id'] = response.data.get('ownDeviceId')
            
            # Extract family_id from response
            # The sign-in-into-family endpoint may return familyId in initialData or data
            initial_data = response.data.get('initialData', {})
            family_id = initial_data.get('familyId')
            
            # If family_id not in initialData, check data field
            if not family_id:
                data_field = response.data.get('data', {})
                family_id = data_field.get('familyId')
            
            # If still not found, perform pull_status to get family_id
            if not family_id:
                logger.info("Family ID not in response, performing pull_status", request_id=request_id)
                pull_response = client.pull_status(
                    device_auth_token=response.data.get('deviceAuthToken')
                )
                if pull_response.success:
                    # Extract family_id from pull_status response
                    # The response may have familyId at the top level or in data
                    family_id = pull_response.data.get('familyId')
                    if not family_id:
                        data_field = pull_response.data.get('data', {})
                        family_id = data_field.get('familyId')
                    
                    # If still not found, set error for user feedback
                    if not family_id:
                        error_msg = 'Failed to retrieve family information from server'
                        session['login_error'] = error_msg
                        logger.warning("Family ID not found in pull_status response", error_message=error_msg, request_id=request_id)
                else:
                    # Store the pull_status error for user feedback
                    # Error message may be in error_message or data field
                    error_msg = pull_response.error_message
                    if not error_msg and pull_response.data:
                        # Extract error from HTML response in data field
                        data_str = str(pull_response.data)
                        if 'BadRequestError' in data_str:
                            error_msg = 'Server error: Invalid request format'
                        else:
                            error_msg = 'Failed to retrieve family information'
                    # Ensure we have an error message
                    error_msg = error_msg or 'Failed to retrieve family information'
                    session['login_error'] = error_msg
                    logger.warning("Failed to pull server status during login", error_message=error_msg, request_id=request_id)
            
            # Only store family_id if it's a valid string (not a MagicMock or other non-string type)
            if isinstance(family_id, str):
                session['family_id'] = family_id
                # Clear any previous login error since we now have family_id
                session.pop('login_error', None)
                logger.info("Family ID extracted and stored in session", family_id=family_id, request_id=request_id)
                
                # Store auth token in database for later lookup
                db = get_database()
                store_auth_token(
                    db=db,
                    token_type='device_auth_token',
                    token_value=response.data.get('deviceAuthToken'),
                    device_id=response.data.get('ownDeviceId'),
                    family_id=family_id
                )
                logger.info("Auth token stored in database", family_id=family_id, request_id=request_id)
            
            # Clear temporary session data
            session.pop('mail_login_token', None)
            session.pop('mail_auth_token', None)
            
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info("Login as parent successful", server_url=server_url, duration_ms=duration_ms, request_id=request_id)
            return redirect('/dashboardV2')
        else:
            session['login_as_parent_error'] = response.error_message or 'Failed to sign in to family'
            logger.error("Login as parent step 3 failed", server_url=server_url, error_code=response.error_code, request_id=request_id)
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
    session.pop('family_id', None)
    session.pop('login_as_parent_error', None)
    session.pop('login_error', None)
    
    logger.info("Login as parent cancelled", request_id=request_id)
    return redirect('/dashboardV2')


@app.route('/api/parent/create-add-device-token', methods=['POST'])
def api_create_add_device_token():
    """Proxy to debug-server /api/v1/parent/create-add-device-token endpoint.
    
    Expects JSON body with 'deviceAuthToken' and 'parentPasswordSecondHash' fields.
    
    Returns:
        JSON response with token and deviceId.
    """
    start_time = time.time()
    request_id = get_request_id()
    data = request.get_json() or {}
    device_auth_token = data.get('deviceAuthToken')
    parent_password_second_hash = data.get('parentPasswordSecondHash')
    
    if not device_auth_token or not parent_password_second_hash:
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
        device_model=data.get('deviceModel')
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
    
    Expects JSON body with 'mailAuthToken' and 'newPassword' fields.
    
    Returns:
        JSON response with status.
    """
    start_time = time.time()
    request_id = get_request_id()
    data = request.get_json() or {}
    mail_auth_token = data.get('mailAuthToken')
    new_password = data.get('newPassword')
    
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
    
    status = {
        'authenticated': 'device_auth_token' in session,
        'server_url': server_url,
        'has_mail_auth_token': 'mail_auth_token' in session,
        'has_device_auth_token': 'device_auth_token' in session,
        'has_child_device_auth_token': 'child_device_auth_token' in session,
        'family_id': session.get('family_id'),
        'own_device_id': session.get('own_device_id'),
        'device_auth_token': session.get('device_auth_token'),
        'mail_auth_token': session.get('mail_auth_token'),
        'login_error': session.get('login_error')
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
    
    # Check family_id
    family_id = session.get('family_id')
    if not family_id:
        logger.warning(
            "Sync pull attempted without family selected",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error_code': 'no_family',
            'error': 'No family selected'
        }), 400
    
    server_url = get_current_server_url()
    device_auth_token = session.get('device_auth_token')
    
    logger.info(
        "Sync pull requested",
        request_id=request_id,
        family_id=family_id,
        server_url=server_url
    )
    
    try:
        db = get_database()
        manager = create_sync_manager(db)
        success = manager.do_sync(device_auth_token, server_url, family_id)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        if success:
            logger.info(
                "Sync pull completed successfully",
                duration_ms=duration_ms,
                request_id=request_id,
                family_id=family_id
            )
            return jsonify({
                'status': 'ok',
                'synced': True
            })
        else:
            logger.error(
                "Sync pull failed",
                duration_ms=duration_ms,
                request_id=request_id,
                family_id=family_id
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
            family_id=family_id,
            error=str(e)
        )
        return jsonify({
            'status': 'error',
            'error_code': 'sync_error',
            'error': 'Sync error'
        }), 500


@app.route('/api/dashboard/users', methods=['GET'])
def api_dashboard_users():
    """Get users for the current family.
    
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
    
    # Check family_id
    family_id = session.get('family_id')
    if not family_id:
        logger.warning(
            "Users request without family selected",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'No family selected'
        }), 400
    
    logger.info(
        "Users request",
        request_id=request_id,
        family_id=family_id
    )
    
    try:
        db = get_database()
        users = get_users_by_family(db, family_id)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            "Users retrieved",
            duration_ms=duration_ms,
            request_id=request_id,
            family_id=family_id,
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
            family_id=family_id,
            error=str(e)
        )
        return jsonify({
            'status': 'error',
            'error': 'Failed to retrieve users'
        }), 500


@app.route('/api/dashboard/devices', methods=['GET'])
def api_dashboard_devices():
    """Get devices for the current family.
    
    Returns:
        JSON response with devices list.
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
    
    # Check family_id
    family_id = session.get('family_id')
    if not family_id:
        logger.warning(
            "Devices request without family selected",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'No family selected'
        }), 400
    
    logger.info(
        "Devices request",
        request_id=request_id,
        family_id=family_id
    )
    
    try:
        db = get_database()
        devices = get_devices_by_family(db, family_id)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            "Devices retrieved",
            duration_ms=duration_ms,
            request_id=request_id,
            family_id=family_id,
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
            "Devices request error",
            duration_ms=duration_ms,
            request_id=request_id,
            family_id=family_id,
            error=str(e)
        )
        return jsonify({
            'status': 'error',
            'error': 'Failed to retrieve devices'
        }), 500


@app.route('/api/dashboard/categories', methods=['GET'])
def api_dashboard_categories():
    """Get categories for the current family.
    
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
    
    # Check family_id
    family_id = session.get('family_id')
    if not family_id:
        logger.warning(
            "Categories request without family selected",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'No family selected'
        }), 400
    
    logger.info(
        "Categories request",
        request_id=request_id,
        family_id=family_id
    )
    
    try:
        db = get_database()
        categories = get_categories_by_family(db, family_id)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            "Categories retrieved",
            duration_ms=duration_ms,
            request_id=request_id,
            family_id=family_id,
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
            family_id=family_id,
            error=str(e)
        )
        return jsonify({
            'status': 'error',
            'error': 'Failed to retrieve categories'
        }), 500


@app.route('/api/dashboard/connected-devices', methods=['GET'])
def api_dashboard_connected_devices():
    """Get connected devices for the current family.
    
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
    
    # Check family_id
    family_id = session.get('family_id')
    if not family_id:
        logger.warning(
            "Connected devices request without family selected",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'No family selected'
        }), 400
    
    logger.info(
        "Connected devices request",
        request_id=request_id,
        family_id=family_id
    )
    
    try:
        db = get_database()
        devices = get_connected_devices(db, family_id)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            "Connected devices retrieved",
            duration_ms=duration_ms,
            request_id=request_id,
            family_id=family_id,
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
            family_id=family_id,
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
    
    # Check family_id
    family_id = session.get('family_id')
    if not family_id:
        logger.warning(
            "SSE stream request without family selected",
            request_id=request_id
        )
        return jsonify({
            'status': 'error',
            'error': 'No family selected'
        }), 400
    
    logger.info(
        "SSE stream request",
        request_id=request_id,
        family_id=family_id
    )
    
    def event_stream():
        """Generator for SSE events."""
        q = get_event_queue(family_id)
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
        request_id=request_id,
        family_id=family_id
    )
    
    return Response(event_stream(), mimetype='text/event-stream')


# ============================================================================
# Timechecker Dashboard Routes
# ============================================================================

@app.route('/api/timechecker/status', methods=['GET'])
def timechecker_status():
    """Get the current server check status.
    
    Returns:
        JSON response with the latest server check result.
    """
    start_time = time.time()
    request_id = get_request_id()
    server_url = get_current_server_url()
    force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
    
    logger.info(
        "Timechecker status request",
        server_url=server_url,
        force_refresh=force_refresh,
        request_id=request_id
    )
    
    # Get the latest server check from database (skip cache when force_refresh is True)
    latest_check = None if force_refresh else get_latest_server_check(get_database(), server_url)
    
    if latest_check:
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            "Timechecker status retrieved from database",
            server_url=server_url,
            success=bool(latest_check['success']),
            duration_ms=duration_ms,
            request_id=request_id
        )
        
        return jsonify({
            'success': bool(latest_check['success']),
            'server_time': latest_check.get('server_time'),
            'error_code': latest_check.get('error_code'),
            'error_message': latest_check.get('user_message'),
            'timestamp': latest_check['timestamp'],
            'attempts': latest_check.get('attempts', 1)
        })
    else:
        # No check results yet, perform a new check
        client = AuthClient(base_url=server_url)
        response = client.check_server_connection()
        
        # Save the result
        save_server_check(
            db=get_database(),
            success=response.success,
            error_code=response.error_code,
            user_message=response.error_message,
            technical_detail=response.technical_detail,
            server_time=response.data.get('ms') if response.success else None,
            attempts=1,
            server_url=server_url
        )
        
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
    
    Query Parameters:
        limit: Maximum number of results to return (default: 10)
    
    Returns:
        JSON response with historical check results.
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
    
    # Get checks for the current server
    checks = get_server_checks(get_database(), limit=limit)
    
    # Filter to only include checks for the current server
    server_checks = [c for c in checks if c.get('server_url') == server_url]
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    logger.info(
        "Timechecker history retrieved",
        server_url=server_url,
        total_checks=len(server_checks),
        duration_ms=duration_ms,
        request_id=request_id
    )
    
    return jsonify({
        'checks': server_checks,
        'total': len(server_checks)
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

# Start the background scheduler for periodic server checks
start_scheduler()

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