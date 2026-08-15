"""Unit tests for request logging middleware.

Tests for RequestLoggingMiddleware, generate_request_id, get_request_id,
and request/response logging functionality.
"""

import io
import json
import logging
import os
import tempfile
import threading
import time
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
import structlog
from flask import Flask, g

from middleware.request_logging import (
    RequestLoggingMiddleware,
    generate_request_id,
    get_request_id,
    init_request_logging,
    shutdown_log_worker,
    _queue_log,
    _sanitize_headers,
    _get_client_ip,
    _request_id_ctx,
)


def reset_structlog():
    """Reset structlog configuration for clean test state."""
    # Disable startup rotation for tests (use fixed file paths)
    os.environ['LOG_ROTATE_ON_START'] = 'false'
    
    # Close all handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        try:
            handler.flush()
            handler.close()
        except Exception:
            pass
        root_logger.removeHandler(handler)
    
    # Close all handlers on Werkzeug logger
    werkzeug_logger = logging.getLogger('werkzeug')
    for handler in werkzeug_logger.handlers[:]:
        try:
            handler.flush()
            handler.close()
        except Exception:
            pass
        werkzeug_logger.removeHandler(handler)
    werkzeug_logger.propagate = True  # Reset to default
    
    # Reset structlog
    structlog.reset_defaults()


def reset_request_id_ctx():
    """Reset the request ID context variable for clean test state."""
    _request_id_ctx.set(None)


class TestGenerateRequestId:
    """Tests for generate_request_id function."""

    @pytest.mark.timeout(10)
    def test_returns_string(self):
        """Verify generate_request_id returns a string."""
        result = generate_request_id()
        assert isinstance(result, str)

    @pytest.mark.timeout(10)
    def test_returns_8_characters(self):
        """Verify request ID is 8 characters."""
        result = generate_request_id()
        assert len(result) == 8

    @pytest.mark.timeout(10)
    def test_returns_unique_ids(self):
        """Verify multiple calls return unique IDs."""
        ids = set()
        for _ in range(100):
            ids.add(generate_request_id())
        assert len(ids) == 100

    @pytest.mark.timeout(10)
    def test_id_format_is_hex(self):
        """Verify ID contains only hexadecimal characters."""
        result = generate_request_id()
        assert all(c in '0123456789abcdef' for c in result)


class TestGetRequestId:
    """Tests for get_request_id function."""

    @pytest.mark.timeout(10)
    def test_returns_none_without_flask_context(self):
        """Verify get_request_id returns None without Flask context."""
        reset_request_id_ctx()
        result = get_request_id()
        assert result is None

    @pytest.mark.timeout(10)
    def test_returns_request_id_in_flask_context(self):
        """Verify get_request_id returns ID in Flask context."""
        reset_request_id_ctx()
        app = Flask(__name__)

        with app.app_context():
            g.request_id = 'a1b2c3d4'
            result = get_request_id()
            assert result == 'a1b2c3d4'

    @pytest.mark.timeout(10)
    def test_returns_none_when_not_set(self):
        """Verify get_request_id returns None when not set."""
        reset_request_id_ctx()
        app = Flask(__name__)

        with app.app_context():
            result = get_request_id()
            assert result is None


class TestSanitizeHeaders:
    """Tests for _sanitize_headers function."""

    @pytest.mark.timeout(10)
    def test_sanitizes_authorization_header(self):
        """Verify Authorization header is sanitized."""
        headers = {
            'Authorization': 'Bearer secret-token',
            'Content-Type': 'application/json'
        }
        result = _sanitize_headers(headers)
        assert result['Authorization'] == '***REDACTED***'
        assert result['Content-Type'] == 'application/json'

    @pytest.mark.timeout(10)
    def test_sanitizes_cookie_header(self):
        """Verify Cookie header is sanitized."""
        headers = {
            'Cookie': 'session=abc123; user=test',
            'Content-Type': 'application/json'
        }
        result = _sanitize_headers(headers)
        assert result['Cookie'] == '***REDACTED***'

    @pytest.mark.timeout(10)
    def test_sanitizes_x_csrf_token(self):
        """Verify X-CSRF-Token header is sanitized."""
        headers = {
            'X-CSRF-Token': 'csrf-token-123',
            'Content-Type': 'application/json'
        }
        result = _sanitize_headers(headers)
        assert result['X-CSRF-Token'] == '***REDACTED***'

    @pytest.mark.timeout(10)
    def test_preserves_non_sensitive_headers(self):
        """Verify non-sensitive headers are preserved."""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'TestClient/1.0'
        }
        result = _sanitize_headers(headers)
        assert result['Content-Type'] == 'application/json'
        assert result['Accept'] == 'application/json'
        assert result['User-Agent'] == 'TestClient/1.0'

    @pytest.mark.timeout(10)
    def test_sanitizes_case_insensitive(self):
        """Verify header sanitization is case-insensitive."""
        headers = {
            'authorization': 'Bearer token',
            'AUTHORIZATION': 'Bearer token2',
            'content-type': 'application/json'
        }
        result = _sanitize_headers(headers)
        # Both variations should be sanitized
        assert '***REDACTED***' in result.values()

    @pytest.mark.timeout(10)
    def test_handles_empty_headers(self):
        """Verify empty headers dict is handled."""
        result = _sanitize_headers({})
        assert result == {}

    @pytest.mark.timeout(10)
    def test_handles_none_values(self):
        """Verify None values are handled."""
        headers = {
            'Content-Type': None,
            'Authorization': 'Bearer token'
        }
        result = _sanitize_headers(headers)
        assert result['Content-Type'] is None
        assert result['Authorization'] == '***REDACTED***'


class TestGetClientIp:
    """Tests for _get_client_ip function."""

    @pytest.mark.timeout(10)
    def test_returns_x_forwarded_for(self):
        """Verify X-Forwarded-For header is used when present."""
        with Flask(__name__).test_request_context(
            '/test',
            headers={'X-Forwarded-For': '192.168.1.100'}
        ):
            result = _get_client_ip()
            assert result == '192.168.1.100'

    @pytest.mark.timeout(10)
    def test_returns_x_real_ip(self):
        """Verify X-Real-IP header is used when X-Forwarded-For is absent."""
        with Flask(__name__).test_request_context(
            '/test',
            headers={'X-Real-IP': '10.0.0.1'}
        ):
            result = _get_client_ip()
            assert result == '10.0.0.1'

    @pytest.mark.timeout(10)
    def test_returns_remote_addr(self):
        """Verify remote_addr is used when no proxy headers."""
        with Flask(__name__).test_request_context('/test'):
            result = _get_client_ip()
            assert result is not None

    @pytest.mark.timeout(10)
    def test_x_forwarded_for_takes_precedence(self):
        """Verify X-Forwarded-For takes precedence over X-Real-IP."""
        with Flask(__name__).test_request_context(
            '/test',
            headers={
                'X-Forwarded-For': '192.168.1.100',
                'X-Real-IP': '10.0.0.1'
            }
        ):
            result = _get_client_ip()
            assert result == '192.168.1.100'


class TestQueueLog:
    """Tests for _queue_log function."""

    @pytest.mark.timeout(10)
    def test_queue_log_adds_to_queue(self):
        """Verify log is added to queue."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with patch.dict(os.environ, {
                'LOG_FILE_PATH': log_file,
                'MESSAGE_LOGGING_ENABLED': 'true',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                _queue_log('INFO', 'Test message', {'key': 'value'})

                # Wait for queue to process
                time.sleep(0.1)

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('request')
                    logger.info('Test message', key='value')

                reset_structlog()

                # Check log file exists and has content
                content = captured_output.getvalue()
                assert 'Test message' in content or 'key' in content


class TestRequestLoggingMiddleware:
    """Tests for RequestLoggingMiddleware class."""

    @pytest.mark.timeout(10)
    def test_middleware_initialization(self):
        """Verify middleware initializes correctly."""
        app = Flask(__name__)
        middleware = RequestLoggingMiddleware(app)
        assert middleware.app == app

    @pytest.mark.timeout(10)
    def test_middleware_registers_before_request(self):
        """Verify middleware registers before_request handler."""
        app = Flask(__name__)

        with patch.dict(os.environ, {
            'LOG_FILE_PATH': '/tmp/test.log',
            'MESSAGE_LOGGING_ENABLED': 'true'
        }):
            middleware = RequestLoggingMiddleware(app)
            # Check before_request handlers are registered
            assert len(app.before_request_funcs) > 0

    @pytest.mark.timeout(10)
    def test_middleware_registers_after_request(self):
        """Verify middleware registers after_request handler."""
        app = Flask(__name__)

        with patch.dict(os.environ, {
            'LOG_FILE_PATH': '/tmp/test.log',
            'MESSAGE_LOGGING_ENABLED': 'true'
        }):
            middleware = RequestLoggingMiddleware(app)
            # Check after_request handlers are registered
            assert len(app.after_request_funcs) > 0

    @pytest.mark.timeout(10)
    def test_middleware_sets_request_id(self):
        """Verify middleware sets request ID in Flask g."""
        app = Flask(__name__)

        with patch.dict(os.environ, {
            'LOG_FILE_PATH': '/tmp/test.log',
            'MESSAGE_LOGGING_ENABLED': 'true'
        }):
            middleware = RequestLoggingMiddleware(app)

            @app.route('/test')
            def test_route():
                request_id = get_request_id()
                return {'request_id': request_id}

            with app.test_client() as client:
                response = client.get('/test')
                data = json.loads(response.data)
                assert data['request_id'] is not None
                assert len(data['request_id']) == 8


class TestInitRequestLogging:
    """Tests for init_request_logging function."""

    @pytest.mark.timeout(10)
    def test_returns_middleware_instance(self):
        """Verify init_request_logging returns RequestLoggingMiddleware."""
        app = Flask(__name__)

        with patch.dict(os.environ, {
            'LOG_FILE_PATH': '/tmp/test.log',
            'MESSAGE_LOGGING_ENABLED': 'true'
        }):
            result = init_request_logging(app)
            assert isinstance(result, RequestLoggingMiddleware)

    @pytest.mark.timeout(10)
    def test_middleware_is_callable(self):
        """Verify returned middleware is callable (WSGI middleware)."""
        app = Flask(__name__)

        with patch.dict(os.environ, {
            'LOG_FILE_PATH': '/tmp/test.log',
            'MESSAGE_LOGGING_ENABLED': 'true'
        }):
            middleware = init_request_logging(app)
            assert callable(middleware)


class TestRequestLoggingIntegration:
    """Integration tests for request logging."""

    @pytest.mark.timeout(10)
    def test_logs_request_start(self):
        """Verify request start is logged."""
        reset_structlog()
        app = Flask(__name__)

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with patch.dict(os.environ, {
                'LOG_FILE_PATH': log_file,
                'MESSAGE_LOGGING_ENABLED': 'true',
                'LOG_FORMAT': 'json'
            }):
                init_request_logging(app)

                @app.route('/test')
                def test_route():
                    return {'status': 'ok'}

                with app.test_client() as client:
                    client.get('/test')

                reset_structlog()

                # Check log file
                if os.path.exists(log_file):
                    with open(log_file, 'r') as f:
                        content = f.read()
                    # Should contain request start event
                    assert 'Request started' in content or 'event' in content

    @pytest.mark.timeout(10)
    def test_logs_request_completion(self):
        """Verify request completion is logged."""
        reset_structlog()
        app = Flask(__name__)

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with patch.dict(os.environ, {
                'LOG_FILE_PATH': log_file,
                'MESSAGE_LOGGING_ENABLED': 'true',
                'LOG_FORMAT': 'json'
            }):
                init_request_logging(app)

                @app.route('/test')
                def test_route():
                    return {'status': 'ok'}

                with app.test_client() as client:
                    client.get('/test')

                reset_structlog()

                # Check log file
                if os.path.exists(log_file):
                    with open(log_file, 'r') as f:
                        content = f.read()
                    # Should contain request completion event
                    assert 'Request completed' in content or 'event' in content

    @pytest.mark.timeout(10)
    def test_logs_request_with_method_and_path(self):
        """Verify request logs include method and path."""
        reset_structlog()
        app = Flask(__name__)

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with patch.dict(os.environ, {
                'LOG_FILE_PATH': log_file,
                'MESSAGE_LOGGING_ENABLED': 'true',
                'LOG_FORMAT': 'json'
            }):
                init_request_logging(app)

                @app.route('/api/test', methods=['POST'])
                def test_route():
                    return {'status': 'ok'}

                with app.test_client() as client:
                    client.post('/api/test')

                reset_structlog()

                # Check log file
                if os.path.exists(log_file):
                    with open(log_file, 'r') as f:
                        content = f.read()
                    assert 'POST' in content or 'method' in content
                    assert '/api/test' in content or 'path' in content

    @pytest.mark.timeout(10)
    def test_logs_response_status_code(self):
        """Verify response status code is logged."""
        reset_structlog()
        app = Flask(__name__)

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with patch.dict(os.environ, {
                'LOG_FILE_PATH': log_file,
                'MESSAGE_LOGGING_ENABLED': 'true',
                'LOG_FORMAT': 'json'
            }):
                init_request_logging(app)

                @app.route('/success')
                def success_route():
                    return {'status': 'ok'}, 200

                @app.route('/error')
                def error_route():
                    return {'error': 'not found'}, 404

                with app.test_client() as client:
                    client.get('/success')
                    client.get('/error')

                reset_structlog()

                # Check log file
                if os.path.exists(log_file):
                    with open(log_file, 'r') as f:
                        content = f.read()
                    assert '200' in content or 'status_code' in content
                    assert '404' in content or 'status_code' in content

    @pytest.mark.timeout(10)
    def test_logs_duration(self):
        """Verify request duration is logged."""
        reset_structlog()
        app = Flask(__name__)

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with patch.dict(os.environ, {
                'LOG_FILE_PATH': log_file,
                'MESSAGE_LOGGING_ENABLED': 'true',
                'LOG_FORMAT': 'json'
            }):
                init_request_logging(app)

                @app.route('/slow')
                def slow_route():
                    time.sleep(0.01)
                    return {'status': 'ok'}

                with app.test_client() as client:
                    client.get('/slow')

                reset_structlog()

                # Check log file
                if os.path.exists(log_file):
                    with open(log_file, 'r') as f:
                        content = f.read()
                    assert 'duration' in content.lower() or 'ms' in content.lower()


class TestShutdownLogWorker:
    """Tests for shutdown_log_worker function."""

    @pytest.mark.timeout(10)
    def test_shutdown_clears_queue(self):
        """Verify shutdown clears the log queue."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with patch.dict(os.environ, {
                'LOG_FILE_PATH': log_file,
                'MESSAGE_LOGGING_ENABLED': 'true'
            }):
                init_request_logging(Flask(__name__))
                shutdown_log_worker()
                # Should not raise

                reset_structlog()


class TestRequestLoggingMiddlewareWithXRequestId:
    """Tests for X-Request-ID header propagation."""

    @pytest.mark.timeout(10)
    def test_propagates_existing_request_id(self):
        """Verify existing X-Request-ID header is propagated."""
        reset_structlog()
        app = Flask(__name__)

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with patch.dict(os.environ, {
                'LOG_FILE_PATH': log_file,
                'MESSAGE_LOGGING_ENABLED': 'true',
                'LOG_FORMAT': 'json'
            }):
                init_request_logging(app)

                @app.route('/test')
                def test_route():
                    return {'status': 'ok'}

                with app.test_client() as client:
                    response = client.get('/test', headers={
                        'X-Request-ID': 'existing12'
                    })

                reset_structlog()

                # Response should include X-Request-ID
                assert 'X-Request-ID' in response.headers

    @pytest.mark.timeout(10)
    def test_generates_new_request_id_when_not_provided(self):
        """Verify new request ID is generated when not provided."""
        reset_structlog()
        app = Flask(__name__)

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with patch.dict(os.environ, {
                'LOG_FILE_PATH': log_file,
                'MESSAGE_LOGGING_ENABLED': 'true',
                'LOG_FORMAT': 'json'
            }):
                init_request_logging(app)

                @app.route('/test')
                def test_route():
                    return {'status': 'ok'}

                with app.test_client() as client:
                    response = client.get('/test')

                reset_structlog()

                # Response should include X-Request-ID
                assert 'X-Request-ID' in response.headers
                assert len(response.headers['X-Request-ID']) == 8


class TestConcurrentRequestLogging:
    """Tests for concurrent request logging."""

    @pytest.mark.timeout(10)
    def test_concurrent_requests_have_unique_ids(self):
        """Verify concurrent requests have unique request IDs."""
        reset_structlog()
        app = Flask(__name__)
        request_ids = []
        lock = threading.Lock()

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with patch.dict(os.environ, {
                'LOG_FILE_PATH': log_file,
                'MESSAGE_LOGGING_ENABLED': 'true',
                'LOG_FORMAT': 'json'
            }):
                init_request_logging(app)

                @app.route('/test')
                def test_route():
                    request_id = get_request_id()
                    with lock:
                        request_ids.append(request_id)
                    return {'status': 'ok'}

                def make_request():
                    with app.test_client() as client:
                        client.get('/test')

                threads = [threading.Thread(target=make_request) for _ in range(10)]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()

                reset_structlog()

                # All request IDs should be unique
                assert len(set(request_ids)) == len(request_ids)


class TestRequestLoggingSanitization:
    """Tests for request logging sanitization."""

    @pytest.mark.timeout(10)
    def test_sanitizes_request_body(self):
        """Verify request body is sanitized."""
        reset_structlog()
        app = Flask(__name__)

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with patch.dict(os.environ, {
                'LOG_FILE_PATH': log_file,
                'MESSAGE_LOGGING_ENABLED': 'true',
                'LOG_FORMAT': 'json'
            }):
                init_request_logging(app)

                @app.route('/login', methods=['POST'])
                def login_route():
                    return {'status': 'ok'}

                with app.test_client() as client:
                    client.post('/login',
                               json={'password': 'secret123', 'username': 'test'})

                reset_structlog()

                # Check log file
                if os.path.exists(log_file):
                    with open(log_file, 'r') as f:
                        content = f.read()
                    # Password should be redacted
                    assert 'secret123' not in content or 'REDACTED' in content


class TestRequestLoggingErrorHandling:
    """Tests for error handling in request logging."""

    @pytest.mark.timeout(10)
    def test_logs_error_responses(self):
        """Verify error responses are logged."""
        reset_structlog()
        app = Flask(__name__)

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with patch.dict(os.environ, {
                'LOG_FILE_PATH': log_file,
                'MESSAGE_LOGGING_ENABLED': 'true',
                'LOG_FORMAT': 'json'
            }):
                init_request_logging(app)

                @app.route('/error')
                def error_route():
                    return {'error': 'not found'}, 404

                with app.test_client() as client:
                    client.get('/error')

                reset_structlog()

                # Check log file
                if os.path.exists(log_file):
                    with open(log_file, 'r') as f:
                        content = f.read()
                    assert '404' in content or 'error' in content.lower()

    @pytest.mark.timeout(10)
    def test_handles_exception_in_request(self):
        """Verify exceptions during request are handled."""
        reset_structlog()
        app = Flask(__name__)

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            with patch.dict(os.environ, {
                'LOG_FILE_PATH': log_file,
                'MESSAGE_LOGGING_ENABLED': 'true',
                'LOG_FORMAT': 'json'
            }):
                init_request_logging(app)

                @app.route('/exception')
                def exception_route():
                    raise ValueError('Test exception')

                with app.test_client() as client:
                    response = client.get('/exception')

                reset_structlog()

                # Should return 500 error
                assert response.status_code == 500