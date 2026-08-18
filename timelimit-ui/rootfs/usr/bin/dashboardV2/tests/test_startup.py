"""Unit tests for application startup scenarios.

This module tests that the dashboardV2 application can be started
without crashing, specifically covering the fix for the session context
error that occurred when trying to set session values outside of a
request context in the main block.

Tests cover:
- App import without errors
- App creation via create_app() without errors
- Direct execution without session context errors
"""

import pytest
import sys
import os
import subprocess
import tempfile
import time

# Skip port check during testing to allow module import
os.environ['SKIP_PORT_CHECK'] = 'true'


class TestAppImport:
    """Tests for importing the Flask application."""
    
    @pytest.mark.timeout(10)
    def test_app_module_imports_successfully(self):
        """Test that app.py can be imported without errors.
        
        This catches issues like the RuntimeError: Working outside of
        request context that occurred when session was accessed at
        module level.
        """
        # Import should not raise any exceptions
        import importlib
        import app as app_module
        
        # Verify the app object exists
        assert hasattr(app_module, 'app')
        assert app_module.app is not None
    
    @pytest.mark.timeout(10)
    def test_app_has_required_routes(self):
        """Test that the Flask app has all required routes."""
        from app import app
        
        # Get all registered routes
        routes = [rule.rule for rule in app.url_map.iter_rules()]
        
        # Check for essential routes
        assert '/' in routes
        assert '/dashboardV2' in routes
        assert '/legacy-dashboard' in routes
        assert '/select-server' in routes
        assert '/health' in routes
        assert '/api/server-selection' in routes


class TestAppCreation:
    """Tests for Flask application creation."""
    
    @pytest.mark.timeout(10)
    def test_create_app_returns_flask_instance(self):
        """Test that create_app() returns a Flask application instance."""
        from app import create_app
        from flask import Flask
        
        app = create_app()
        
        assert isinstance(app, Flask)
    
    @pytest.mark.timeout(10)
    def test_create_app_configures_secret_key(self):
        """Test that create_app() configures SECRET_KEY."""
        from app import create_app
        
        app = create_app()
        
        assert 'SECRET_KEY' in app.config
        assert app.config['SECRET_KEY'] is not None
        assert isinstance(app.config['SECRET_KEY'], str)
    
    @pytest.mark.timeout(10)
    def test_create_app_configures_session_settings(self):
        """Test that create_app() configures session settings."""
        from app import create_app
        
        app = create_app()
        
        assert app.config.get('SESSION_COOKIE_HTTPONLY') is True
        assert app.config.get('SESSION_COOKIE_SAMESITE') == 'Lax'
        assert app.config.get('PERMANENT_SESSION_LIFETIME') is not None


class TestDirectExecution:
    """Tests for direct script execution (python app.py)."""
    
    @pytest.mark.timeout(30)
    def test_app_runs_without_session_context_error(self):
        """Test that running app.py directly does not raise RuntimeError.
        
        This test verifies the fix for the bug where the main block
        tried to set session['server_url'] outside of a request context,
        causing:
        RuntimeError: Working outside of request context.
        """
        # Get the path to app.py
        test_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app_path = os.path.join(test_dir, 'app.py')
        
        # Start the app in a subprocess
        # We use Popen to allow checking if it starts without waiting for completion
        process = subprocess.Popen(
            [sys.executable, app_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=test_dir
        )
        
        try:
            # Wait a short time for the app to start
            time.sleep(2)
            
            # Check if the process is still running (didn't crash)
            assert process.poll() is None, "App crashed during startup"
            
            # Check stderr for session context error
            # Use a non-blocking read to check for errors
            import select
            import sys as sys_module
            
            # On Windows, select doesn't work with pipes, so we use a different approach
            # Read any available stderr output
            stderr_output = ""
            try:
                # Try to read stderr with a timeout
                import threading
                stderr_lines = []
                def read_stderr():
                    while True:
                        line = process.stderr.readline()
                        if not line:
                            break
                        stderr_lines.append(line)
                thread = threading.Thread(target=read_stderr, daemon=True)
                thread.start()
                thread.join(timeout=0.5)
                stderr_output = "".join(stderr_lines)
            except Exception:
                pass
            
            # Check that we don't get the session context error
            assert 'RuntimeError' not in stderr_output
            assert 'Working outside of request context' not in stderr_output
            
        finally:
            # Terminate the process
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    
    @pytest.mark.timeout(30)
    def test_app_starts_and_listens_on_port(self):
        """Test that the app starts and begins listening on the configured port."""
        import socket
        import threading
        import time
        
        # Get the path to app.py
        test_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app_path = os.path.join(test_dir, 'app.py')
        
        # Start the app in a subprocess
        process = subprocess.Popen(
            [sys.executable, app_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=test_dir
        )
        
        try:
            # Wait for the server to start
            time.sleep(2)
            
            # Check if the process is still running (didn't crash)
            assert process.poll() is None, "App crashed during startup"
            
            # Try to connect to the port
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('127.0.0.1', 8099))
            sock.close()
            
            # Port should be open (result == 0)
            assert result == 0, "App did not start listening on port 8099"
            
        finally:
            # Terminate the process
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


class TestPersistenceIntegration:
    """Tests for persistence integration during startup."""
    
    @pytest.mark.timeout(10)
    def test_persistence_store_available_at_startup(self):
        """Test that persistence store is available when app starts."""
        from persistence import get_server_selection_store, is_ha_ingress
        
        # The store should be available
        store = get_server_selection_store()
        assert store is not None
        
        # Should be able to get server key without error
        server_key = store.get_selected_server_key()
        # server_key can be None if no selection has been made
        assert server_key is None or isinstance(server_key, str)
    
    @pytest.mark.timeout(10)
    def test_get_current_server_url_no_session_context(self):
        """Test that get_current_server_url works without session context.
        
        This verifies that the function properly falls back to config
        default when no session exists.
        """
        from app import get_current_server_url
        
        # This should not raise an error even outside of a request context
        server_url = get_current_server_url()
        
        # Should return a valid URL (either from persistence or default)
        assert server_url is not None
        assert isinstance(server_url, str)
        assert server_url.startswith('http')


class TestDatabaseInitialization:
    """Tests for database initialization during startup."""
    
    @pytest.mark.timeout(10)
    def test_database_initializes_on_import(self):
        """Test that database initializes correctly when app is imported."""
        from database import get_database
        
        db = get_database()
        assert db is not None
        
        # Database should be initialized
        # Check that we can get a connection
        conn = db.get_connection()
        assert conn is not None
        
        # Clean up
        db.close()
    
    @pytest.mark.timeout(10)
    def test_database_tables_exist(self):
        """Test that all required database tables exist."""
        from database import get_database
        
        db = get_database()
        db.init_db()
        
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Check for required tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        assert 'server_checks' in tables
        assert 'families' in tables
        assert 'devices' in tables
        assert 'auth_tokens' in tables
        
        db.close()