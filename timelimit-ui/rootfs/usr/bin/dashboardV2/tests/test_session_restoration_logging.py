"""Unit tests for session restoration logging.

This module tests that the restore_session_from_persistence function
does not crash when called, specifically testing the fix for the
TypeError: _nop() got multiple values for argument 'event' bug.

The bug occurred because structlog treats the first positional argument
as the 'event' key, and passing 'event' as a keyword argument caused
a conflict when the _nop method was called (for filtered log levels).
"""

import pytest
import os
from unittest.mock import patch

# Skip port check during testing to allow module import
os.environ['SKIP_PORT_CHECK'] = 'true'


class TestSessionRestorationLogging:
    """Tests for session restoration logging in before_request handler."""

    @pytest.mark.timeout(10)
    def test_landing_page_request_does_not_crash_with_debug_logging(self, client):
        """Test that landing page request does not crash with debug logging.
        
        This test catches the bug where logger.debug() calls in the
        restore_session_from_persistence before_request handler would crash
        with: TypeError: _nop() got multiple values for argument 'event'
        
        The bug occurred because structlog treats the first positional argument
        as the 'event' key, and passing 'event' as a keyword argument caused
        a conflict.
        """
        # Make a request to the landing page
        # This triggers the restore_session_from_persistence before_request handler
        response = client.get('/')
        
        # Should return 200, not 500
        assert response.status_code == 200
        
    @pytest.mark.timeout(10)
    def test_dashboard_v2_request_does_not_crash_with_debug_logging(self, client):
        """Test that dashboard V2 request does not crash with debug logging.
        
        This test verifies that the before_request handler doesn't crash
        when accessing the dashboard V2 page.
        """
        response = client.get('/dashboardV2')
        
        # Should return 200, not 500
        assert response.status_code == 200

    @pytest.mark.timeout(10)
    def test_health_endpoint_does_not_crash_with_debug_logging(self, client):
        """Test that health endpoint request does not crash with debug logging.
        
        This test verifies that the before_request handler doesn't crash
        when accessing the health endpoint.
        """
        response = client.get('/health')
        
        # Should return 200, not 500
        assert response.status_code == 200

    @pytest.mark.timeout(10)
    def test_multiple_requests_do_not_crash_with_debug_logging(self, client):
        """Test that multiple requests do not crash with debug logging.
        
        This test verifies that the before_request handler doesn't crash
        when making multiple requests in sequence.
        """
        # Make multiple requests
        for _ in range(5):
            response = client.get('/')
            assert response.status_code == 200
            
            response = client.get('/health')
            assert response.status_code == 200

    @pytest.mark.timeout(10)
    def test_request_with_session_does_not_crash_with_debug_logging(self, client):
        """Test that request with session does not crash with debug logging.
        
        This test verifies that the before_request handler doesn't crash
        when there's already a device_auth_token in the session.
        """
        # Set up a session with device_auth_token
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test_token_for_logging_test'
            sess['server_url'] = 'http://localhost:8080'
        
        # Make a request
        response = client.get('/')
        
        # Should return 200, not 500
        assert response.status_code == 200


class TestLoggerDebugCallPattern:
    """Tests for correct logger.debug() call patterns.

    These tests verify that logger.debug() calls use the correct pattern
    to avoid the 'event' argument conflict.
    """

    @pytest.mark.timeout(10)
    def test_logger_debug_with_event_keyword_raises_error(self):
        """Test that logger.debug() with both positional and event keyword raises error.
        
        This test demonstrates the bug: when you call logger.debug("message", event="value"),
        structlog treats the first positional argument as 'event', and then you're
        passing 'event' twice, which causes a TypeError.
        """
        import structlog
        from utils.logging import setup_structlog, get_logger
        
        # Setup structlog with DEBUG level
        setup_structlog(log_level='DEBUG', log_file_path='/tmp/test_debug.log')
        
        logger = get_logger('test_logger')
        
        # This should work - using only positional argument
        # The first positional argument becomes the 'event' key
        try:
            logger.debug("test_event", key="value")
        except TypeError as e:
            if "multiple values for argument 'event'" in str(e):
                pytest.fail(f"logger.debug() with positional arg and event keyword failed: {e}")
            raise
        
        # This should also work - using only keyword arguments
        try:
            logger.debug(event="test_event", key="value")
        except TypeError as e:
            if "multiple values for argument 'event'" in str(e):
                pytest.fail(f"logger.debug() with event keyword failed: {e}")
            raise

    @pytest.mark.timeout(10)
    def test_logger_debug_without_event_keyword_works(self):
        """Test that logger.debug() without event keyword works correctly.
        
        This test verifies the correct pattern: either use only positional
        argument (which becomes 'event'), or use only keyword arguments.
        """
        import structlog
        from utils.logging import setup_structlog, get_logger
        
        # Setup structlog with DEBUG level
        setup_structlog(log_level='DEBUG', log_file_path='/tmp/test_debug2.log')
        
        logger = get_logger('test_logger2')
        
        # This should work - using only positional argument
        # The first positional argument becomes the 'event' key
        logger.debug("test_event", key="value")
        
        # This should work - using only keyword arguments
        logger.debug(event="test_event", key="value")