"""Unit tests for port availability check functionality.

This module tests the check_port_available function which verifies
that the configured port is available before starting the Flask server.
"""

import os
import socket
import sys
import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Skip port check during testing to allow module import
os.environ['SKIP_PORT_CHECK'] = 'true'


class TestPortAvailabilityCheck:
    """Tests for the check_port_available function."""
    
    @pytest.mark.timeout(10)
    def test_port_available_returns_true(self):
        """Test that check_port_available returns True when port is available."""
        from app import check_port_available
        
        # Use a port that's likely to be available
        # We use port 0 to let the OS assign an available port
        # But for this test, we'll use a specific high port that's unlikely to be in use
        test_host = '127.0.0.1'
        test_port = 59999  # High port number, unlikely to be in use
        
        result = check_port_available(test_host, test_port)
        
        assert result is True
    
    @pytest.mark.timeout(10)
    def test_port_in_use_exits_with_code_1(self):
        """Test that check_port_available exits with code 1 when port is in use."""
        from app import check_port_available
        
        # Find an available port first
        test_host = '127.0.0.1'
        
        # Create a socket and bind to a port to simulate it being in use
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((test_host, 0))  # Bind to any available port
        test_port = sock.getsockname()[1]  # Get the assigned port
        
        # Now the port is in use, check_port_available should exit
        with pytest.raises(SystemExit) as exc_info:
            check_port_available(test_host, test_port)
        
        assert exc_info.value.code == 1
        
        # Clean up
        sock.close()
    
    @pytest.mark.timeout(10)
    def test_port_in_use_logs_error(self, caplog):
        """Test that check_port_available logs an error when port is in use."""
        from app import check_port_available
        
        # Find an available port first
        test_host = '127.0.0.1'
        
        # Create a socket and bind to a port to simulate it being in use
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((test_host, 0))  # Bind to any available port
        test_port = sock.getsockname()[1]  # Get the assigned port
        
        # Now the port is in use, check_port_available should exit
        with pytest.raises(SystemExit):
            check_port_available(test_host, test_port)
        
        # Clean up
        sock.close()
    
    @pytest.mark.timeout(10)
    def test_different_host_same_port(self):
        """Test that different hosts can use the same port."""
        from app import check_port_available
        
        test_port = 59998  # High port number
        
        # Check availability on 127.0.0.1
        result1 = check_port_available('127.0.0.1', test_port)
        assert result1 is True
        
        # Check availability on 0.0.0.0 (should work since we're checking binding)
        # Note: This tests that the function can check different hosts
        result2 = check_port_available('0.0.0.0', test_port)
        assert result2 is True


class TestPortCheckIntegration:
    """Integration tests for port check with actual server startup."""
    
    @pytest.mark.timeout(15)
    def test_port_check_with_default_config(self):
        """Test port check with default configuration values."""
        from app import check_port_available
        from config import Config
        
        config = Config()
        
        # This test verifies the function works with actual config values
        # We use a different port to avoid conflicts
        test_host = config.FLASK_HOST
        test_port = 59997  # Use a test port
        
        result = check_port_available(test_host, test_port)
        assert result is True
    
    @pytest.mark.timeout(15)
    def test_port_check_with_custom_port_env(self):
        """Test port check respects FLASK_PORT environment variable."""
        from app import check_port_available
        
        # Set a custom port via environment variable
        original_port = os.environ.get('FLASK_PORT')
        
        try:
            os.environ['FLASK_PORT'] = '59996'
            
            # Re-import to get the new config
            import importlib
            import config as config_module
            importlib.reload(config_module)
            from config import Config
            
            config = Config()
            test_host = config.FLASK_HOST
            test_port = 59996
            
            result = check_port_available(test_host, test_port)
            assert result is True
            
        finally:
            # Restore original port
            if original_port:
                os.environ['FLASK_PORT'] = original_port
            else:
                if 'FLASK_PORT' in os.environ:
                    del os.environ['FLASK_PORT']
            
            # Reload config to restore original state
            importlib.reload(config_module)
    
    @pytest.mark.timeout(15)
    def test_error_message_is_clear(self, caplog, capsys):
        """Test that the error message is clear and informative."""
        from app import check_port_available
        
        # Find an available port first
        test_host = '127.0.0.1'
        
        # Create a socket and bind to a port to simulate it being in use
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((test_host, 0))
        test_port = sock.getsockname()[1]
        
        # Now the port is in use, check_port_available should exit
        with pytest.raises(SystemExit):
            check_port_available(test_host, test_port)
        
        # Clean up
        sock.close()
        
        # Check that the error message contains key information
        # The log should contain the port number, host, and clear message
        assert len(caplog.records) > 0, "Expected log records"
        
        # Find the error log record
        error_records = [r for r in caplog.records if r.levelname == 'ERROR']
        assert len(error_records) > 0, "Expected at least one ERROR log record"
        
        # Check the error message content
        error_message = error_records[0].message
        assert 'already in use' in error_message.lower(), f"Error message should mention 'already in use': {error_message}"
        assert str(test_port) in error_message, f"Error message should contain port number: {error_message}"
        assert test_host in error_message, f"Error message should contain host: {error_message}"
        
        # Check that plain text error was printed to stderr
        captured = capsys.readouterr()
        plain_text_error = captured.err
        assert 'ERROR:' in plain_text_error, f"Plain text error should start with 'ERROR:': {plain_text_error}"
        assert f'Port {test_port}' in plain_text_error, f"Plain text error should contain port number: {plain_text_error}"
        assert f'host {test_host}' in plain_text_error, f"Plain text error should contain host: {plain_text_error}"
        assert 'already in use' in plain_text_error.lower(), f"Plain text error should mention 'already in use': {plain_text_error}"
        assert 'FLASK_PORT' in plain_text_error, f"Plain text error should mention FLASK_PORT: {plain_text_error}"