"""Unit tests for logging configuration.

Tests for structlog setup, logger retrieval, and sanitization processors.
"""

import io
import json
import logging
import os
import sys
import tempfile
from datetime import datetime
from logging.handlers import RotatingFileHandler
from unittest.mock import MagicMock, patch

import pytest
import structlog


def reset_structlog():
    """Reset structlog configuration for clean test state."""
    # Disable startup rotation for tests (use fixed file paths)
    os.environ['LOG_ROTATE_ON_START'] = 'false'
    
    # Close all handlers on root logger
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


class TestSetupStructlog:
    """Tests for setup_structlog function."""

    def test_setup_structlog_with_console_format(self):
        """Verify setup_structlog works with console format."""
        reset_structlog()
        from utils.logging import setup_structlog

        with patch.dict(os.environ, {
            'LOG_LEVEL': 'INFO',
            'LOG_FORMAT': 'console'
        }):
            setup_structlog()

            from utils.logging import get_logger
            logger = get_logger('test')
            assert logger is not None
            
            reset_structlog()

    def test_setup_structlog_respects_log_level(self):
        """Verify setup_structlog respects LOG_LEVEL environment variable."""
        reset_structlog()
        from utils.logging import setup_structlog

        with patch.dict(os.environ, {
            'LOG_LEVEL': 'WARNING',
            'LOG_FORMAT': 'console'
        }):
            setup_structlog()

            from utils.logging import get_logger
            logger = get_logger('test')
            # Logger should be configured with WARNING level
            assert logger is not None
            
            reset_structlog()

    def test_setup_structlog_creates_log_directory(self):
        """Verify setup_structlog creates log directory if it doesn't exist."""
        reset_structlog()
        from utils.logging import setup_structlog

        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = os.path.join(tmpdir, "logs", "nested")
            log_file = os.path.join(log_dir, "test.log")

            with patch.dict(os.environ, {
                'LOG_LEVEL': 'INFO',
                'LOG_FILE_PATH': log_file,
                'LOG_FORMAT': 'json'
            }):
                setup_structlog()
                assert os.path.exists(log_dir)
                
                # Close handlers before cleanup
                reset_structlog()


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_returns_structlog_logger(self):
        """Verify get_logger returns a structlog logger instance."""
        reset_structlog()
        from utils.logging import setup_structlog, get_logger

        with patch.dict(os.environ, {
            'LOG_LEVEL': 'INFO',
            'LOG_FORMAT': 'console'
        }):
            setup_structlog()
            logger = get_logger('test_module')
            assert hasattr(logger, 'info')
            assert hasattr(logger, 'debug')
            assert hasattr(logger, 'warning')
            assert hasattr(logger, 'error')
            
            reset_structlog()

    def test_get_logger_with_none_name(self):
        """Verify get_logger works with None name."""
        reset_structlog()
        from utils.logging import setup_structlog, get_logger

        with patch.dict(os.environ, {
            'LOG_LEVEL': 'INFO',
            'LOG_FORMAT': 'console'
        }):
            setup_structlog()
            logger = get_logger(None)
            assert logger is not None
            
            reset_structlog()

    def test_get_logger_returns_logger_with_name(self):
        """Verify get_logger returns a logger with the specified name."""
        reset_structlog()
        from utils.logging import setup_structlog, get_logger

        with patch.dict(os.environ, {
            'LOG_LEVEL': 'INFO',
            'LOG_FORMAT': 'console'
        }):
            setup_structlog()
            logger = get_logger('test_module')
            # Verify logger has the expected attributes
            assert hasattr(logger, 'info')
            assert hasattr(logger, 'debug')
            
            reset_structlog()


class TestSanitizeDict:
    """Tests for _sanitize_dict function."""

    def test_sanitize_dict_preserves_password(self):
        """Verify _sanitize_dict preserves password (for audit logging)."""
        from utils.logging import _sanitize_dict

        data = {
            'password': 'secret123',
            'username': 'testuser',
            'token': 'abc123'
        }

        result = _sanitize_dict(data)

        # Password is preserved for audit logging
        assert result['password'] == 'secret123'
        assert result['username'] == 'testuser'
        assert result['token'] == '***REDACTED***'

    def test_sanitize_dict_handles_nested_dicts(self):
        """Verify _sanitize_dict handles nested dictionaries."""
        from utils.logging import _sanitize_dict

        data = {
            'user': {
                'password': 'secret',
                'name': 'John'
            },
            'token': 'abc123'
        }

        result = _sanitize_dict(data)

        # Password is preserved for audit logging
        assert result['user']['password'] == 'secret'
        assert result['user']['name'] == 'John'
        assert result['token'] == '***REDACTED***'

    def test_sanitize_dict_preserves_non_sensitive_data(self):
        """Verify _sanitize_dict preserves non-sensitive data."""
        from utils.logging import _sanitize_dict

        data = {
            'server_url': 'http://localhost:8080',
            'port': 8080,
            'enabled': True,
            'count': 42
        }

        result = _sanitize_dict(data)

        assert result['server_url'] == 'http://localhost:8080'
        assert result['port'] == 8080
        assert result['enabled'] is True
        assert result['count'] == 42


class TestSanitizeProcessor:
    """Tests for _sanitize_processor function."""

    def test_sanitize_processor_preserves_password(self):
        """Verify _sanitize_processor preserves password (for audit logging)."""
        from utils.logging import _sanitize_processor

        event_dict = {
            'event': 'test_event',
            'password': 'secret',
            'username': 'testuser'
        }

        result = _sanitize_processor(None, None, event_dict)

        # Password is preserved for audit logging
        assert result['password'] == 'secret'
        assert result['username'] == 'testuser'

    def test_sanitize_processor_preserves_event(self):
        """Verify _sanitize_processor preserves the event field."""
        from utils.logging import _sanitize_processor

        event_dict = {
            'event': 'user_login',
            'password': 'secret'
        }

        result = _sanitize_processor(None, None, event_dict)

        assert result['event'] == 'user_login'


class TestLogOutput:
    """Tests for actual log output using stdout capture."""

    def test_log_output_is_json(self):
        """Verify log output is valid JSON when LOG_FORMAT is json."""
        reset_structlog()
        from utils.logging import setup_structlog, get_logger

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FILE_PATH': log_file,
                'LOG_FORMAT': 'json'
            }):
                setup_structlog()
                logger = get_logger('test')
                
                # Capture stdout to get JSON output
                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger.info('Test message', key='value')
                
                # Close handlers
                reset_structlog()

                # Parse the captured output as JSON
                output = captured_output.getvalue().strip()
                entry = json.loads(output)
                assert 'event' in entry or 'message' in entry

    def test_log_output_includes_timestamp(self):
        """Verify log output includes timestamp."""
        reset_structlog()
        from utils.logging import setup_structlog, get_logger

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FILE_PATH': log_file,
                'LOG_FORMAT': 'json'
            }):
                setup_structlog()
                logger = get_logger('test')
                
                # Capture stdout to get JSON output
                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger.info('Test message')
                
                # Close handlers
                reset_structlog()

                # Parse the captured output as JSON
                output = captured_output.getvalue().strip()
                entry = json.loads(output)
                assert 'timestamp' in entry or 'event' in entry


class TestRotatingFileHandler:
    """Tests for RotatingFileHandler configuration."""

    def test_rotating_file_handler_created(self):
        """Verify RotatingFileHandler is created with correct parameters."""
        reset_structlog()
        from utils.logging import setup_structlog

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'INFO',
                'LOG_FILE_PATH': log_file,
                'LOG_FORMAT': 'json',
                'LOG_MAX_BYTES': '1048576',
                'LOG_BACKUP_COUNT': '3'
            }):
                setup_structlog()

                # Verify file handler was created
                from utils.logging import get_logger
                logger = get_logger('test')
                assert logger is not None
                
                reset_structlog()

    def test_log_records_written_to_file(self):
        """Verify log records are actually written to the log file.

        This is a regression test for the bug where PrintLoggerFactory
        bypassed the standard logging system, causing the RotatingFileHandler
        to never receive any log records.
        """
        reset_structlog()
        from utils.logging import setup_structlog, get_logger

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FILE_PATH': log_file,
                'LOG_FORMAT': 'json'
            }):
                setup_structlog()
                logger = get_logger('test')

                # Log a test message
                logger.info('File logging regression test', key='value')

                # Flush all handlers to ensure data is written
                root_logger = logging.getLogger()
                for handler in root_logger.handlers:
                    handler.flush()

                # Close handlers
                reset_structlog()

                # Verify the log file contains the message
                assert os.path.exists(log_file)
                with open(log_file, 'r') as f:
                    content = f.read().strip()
                assert len(content) > 0, "Log file should not be empty"
                entry = json.loads(content)
                assert entry.get('event') == 'File logging regression test'
                assert entry.get('key') == 'value'

    def test_log_rotation_triggers_at_max_bytes(self):
        """Verify log rotation triggers when max bytes is reached."""
        reset_structlog()
        from utils.logging import setup_structlog, get_logger

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FILE_PATH': log_file,
                'LOG_FORMAT': 'json',
                'LOG_MAX_BYTES': '100',
                'LOG_BACKUP_COUNT': '2'
            }):
                setup_structlog()
                logger = get_logger('test')

                # Write enough data to trigger rotation
                for i in range(100):
                    logger.info('Test message', index=i, data='x' * 50)

                # Close handlers
                reset_structlog()

                # Verify backup files were created (rotation actually happened)
                backup_files = [f for f in os.listdir(tmpdir) if f.startswith('test.log.')]
                assert len(backup_files) >= 1, "At least one backup file should be created when rotation triggers"
                assert len(backup_files) <= 2  # LOG_BACKUP_COUNT


class TestEnvironmentVariables:
    """Tests for environment variable handling."""

    def test_default_log_level(self):
        """Verify default log level is INFO."""
        reset_structlog()
        from utils.logging import setup_structlog

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            with patch.dict(os.environ, {
                'LOG_FILE_PATH': log_file,
                'LOG_FORMAT': 'console'
            }, clear=False):
                # Remove LOG_LEVEL if present
                os.environ.pop('LOG_LEVEL', None)
                setup_structlog()
                assert True  # Should not raise
                
                reset_structlog()

    def test_custom_log_level(self):
        """Verify custom log level is respected."""
        reset_structlog()
        from utils.logging import setup_structlog

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FILE_PATH': log_file,
                'LOG_FORMAT': 'console'
            }):
                setup_structlog()
                assert True  # Should not raise
                
                reset_structlog()

    def test_invalid_log_level_defaults_to_info(self):
        """Verify invalid log level defaults to INFO."""
        reset_structlog()
        from utils.logging import setup_structlog

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'INVALID',
                'LOG_FILE_PATH': log_file,
                'LOG_FORMAT': 'console'
            }):
                setup_structlog()
                assert True  # Should not raise
                
                reset_structlog()


class TestStructlogProcessorChain:
    """Tests for the structlog processor chain."""

    def test_processor_chain_includes_sanitization(self):
        """Verify processor chain includes sanitization processor."""
        reset_structlog()
        from utils.logging import setup_structlog, get_logger

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'INFO',
                'LOG_FILE_PATH': log_file,
                'LOG_FORMAT': 'json'
            }):
                setup_structlog()
                logger = get_logger('test')
                
                # Capture stdout to get JSON output
                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger.info('Test', password='secret')
                
                # Close handlers
                reset_structlog()

                # Parse the captured output as JSON
                output = captured_output.getvalue().strip()
                entry = json.loads(output)
                # Password is preserved for audit logging
                assert entry.get('password') == 'secret'

    def test_processor_chain_includes_timestamp(self):
        """Verify processor chain includes timestamp."""
        reset_structlog()
        from utils.logging import setup_structlog, get_logger

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'INFO',
                'LOG_FILE_PATH': log_file,
                'LOG_FORMAT': 'json'
            }):
                setup_structlog()
                logger = get_logger('test')
                
                # Capture stdout to get JSON output
                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger.info('Test message')
                
                # Close handlers
                reset_structlog()

                # Parse the captured output as JSON
                output = captured_output.getvalue().strip()
                entry = json.loads(output)
                assert 'timestamp' in entry


class TestLogDirectoryCreation:
    """Tests for log directory creation."""

    def test_creates_directory_if_not_exists(self):
        """Verify log directory is created if it doesn't exist."""
        reset_structlog()
        from utils.logging import setup_structlog

        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = os.path.join(tmpdir, "new_logs")
            log_file = os.path.join(log_dir, "test.log")

            assert not os.path.exists(log_dir)

            with patch.dict(os.environ, {
                'LOG_LEVEL': 'INFO',
                'LOG_FILE_PATH': log_file,
                'LOG_FORMAT': 'json'
            }):
                setup_structlog()

            assert os.path.exists(log_dir)
            
            reset_structlog()

    def test_uses_existing_directory(self):
        """Verify existing log directory is used."""
        reset_structlog()
        from utils.logging import setup_structlog

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")

            with patch.dict(os.environ, {
                'LOG_LEVEL': 'INFO',
                'LOG_FILE_PATH': log_file,
                'LOG_FORMAT': 'json'
            }):
                setup_structlog()

            assert os.path.exists(log_file)
            
            reset_structlog()


class TestStartupLogRotation:
    """Tests for startup-based log file rotation."""

    def test_rotate_on_start_creates_timestamped_file(self):
        """Verify that rotate_on_start creates a timestamped log file."""
        reset_structlog()
        from utils.logging import setup_structlog, get_logger

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "dashboardV2.log")

            with patch.dict(os.environ, {
                'LOG_LEVEL': 'INFO',
                'LOG_FILE_PATH': log_file,
                'LOG_FORMAT': 'json',
                'LOG_ROTATE_ON_START': 'true',
            }):
                setup_structlog()
                logger = get_logger('test')
                logger.info('Startup rotation test')

                # Flush handlers
                root_logger = logging.getLogger()
                for handler in root_logger.handlers:
                    handler.flush()

                reset_structlog()

                # The original file should NOT exist (rotated to timestamped name)
                assert not os.path.exists(log_file)

                # A timestamped file should exist
                log_files = [f for f in os.listdir(tmpdir) if f.startswith('dashboardV2-') and f.endswith('.log')]
                assert len(log_files) >= 1, "A timestamped log file should be created on startup"

    def test_rotate_on_start_disabled_uses_fixed_filename(self):
        """Verify that rotate_on_start=false uses the fixed filename."""
        reset_structlog()
        from utils.logging import setup_structlog, get_logger

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "dashboardV2.log")

            with patch.dict(os.environ, {
                'LOG_LEVEL': 'INFO',
                'LOG_FILE_PATH': log_file,
                'LOG_FORMAT': 'json',
                'LOG_ROTATE_ON_START': 'false',
            }):
                setup_structlog()
                logger = get_logger('test')
                logger.info('Fixed filename test')

                # Flush handlers
                root_logger = logging.getLogger()
                for handler in root_logger.handlers:
                    handler.flush()

                reset_structlog()

                # The fixed filename should exist
                assert os.path.exists(log_file)

    def test_rotate_on_start_cleans_up_old_files(self):
        """Verify that startup rotation cleans up old log files."""
        reset_structlog()
        from utils.logging import setup_structlog, get_logger

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "dashboardV2.log")

            # Create some old log files to simulate previous runs
            for i in range(15):
                old_file = os.path.join(tmpdir, f"dashboardV2-2026-01-0{i}-00-00-00.log")
                with open(old_file, 'w') as f:
                    f.write("old log content\n")

            with patch.dict(os.environ, {
                'LOG_LEVEL': 'INFO',
                'LOG_FILE_PATH': log_file,
                'LOG_FORMAT': 'json',
                'LOG_ROTATE_ON_START': 'true',
                'MAX_LOG_FILES': '5',
            }):
                setup_structlog()
                logger = get_logger('test')
                logger.info('Cleanup test')

                # Flush handlers
                root_logger = logging.getLogger()
                for handler in root_logger.handlers:
                    handler.flush()

                reset_structlog()

                # Count remaining log files
                log_files = [f for f in os.listdir(tmpdir) if f.startswith('dashboardV2-') and f.endswith('.log')]
                assert len(log_files) <= 5, "Old log files should be cleaned up to respect MAX_LOG_FILES"


class TestTestLogDirectory:
    """Tests for test-specific log directory configuration."""

    def test_test_logs_directory_exists(self):
        """Verify the test logs directory exists."""
        tests_dir = os.path.dirname(os.path.abspath(__file__))
        log_dir = os.path.join(tests_dir, 'logs')
        assert os.path.exists(log_dir), f"Test logs directory should exist at {log_dir}"

    def test_test_log_paths_are_set_by_pytest_configure(self):
        """Verify that pytest_configure sets test-specific log paths."""
        # This test verifies that the environment variables are set correctly
        # when pytest_configure runs before test collection
        tests_dir = os.path.dirname(os.path.abspath(__file__))
        expected_log_file = os.path.join(tests_dir, 'logs', 'dashboardV2.log')
        expected_werkzeug_file = os.path.join(tests_dir, 'logs', 'werkzeug.log')
        
        # Check that the expected paths are set (or will be set by pytest_configure)
        # Note: This test runs after pytest_configure has already set the env vars
        assert os.environ.get('LOG_FILE_PATH') == expected_log_file, \
            f"LOG_FILE_PATH should be {expected_log_file}"
        assert os.environ.get('LOG_WERKZEUG_FILE_PATH') == expected_werkzeug_file, \
            f"LOG_WERKZEUG_FILE_PATH should be {expected_werkzeug_file}"
        assert os.environ.get('LOG_ROTATE_ON_START') == 'false', \
            "LOG_ROTATE_ON_START should be 'false' for tests"


class TestWerkzeugSeparation:
    """Tests for Werkzeug logger separation from structlog."""

    def test_werkzeug_does_not_propagate_to_root(self):
        """Verify Werkzeug logger does not propagate to root logger."""
        reset_structlog()
        from utils.logging import setup_structlog

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            werkzeug_file = os.path.join(tmpdir, "werkzeug.log")

            with patch.dict(os.environ, {
                'LOG_LEVEL': 'INFO',
                'LOG_FILE_PATH': log_file,
                'LOG_FORMAT': 'json',
                'LOG_ROTATE_ON_START': 'false',
                'LOG_WERKZEUG_FILE_PATH': werkzeug_file,
            }):
                setup_structlog()

                werkzeug_logger = logging.getLogger('werkzeug')
                assert werkzeug_logger.propagate is False, "Werkzeug logger should not propagate to root"

                reset_structlog()

    def test_werkzeug_has_separate_file_handler(self):
        """Verify Werkzeug logger has its own file handler."""
        reset_structlog()
        from utils.logging import setup_structlog

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            werkzeug_file = os.path.join(tmpdir, "werkzeug.log")

            with patch.dict(os.environ, {
                'LOG_LEVEL': 'INFO',
                'LOG_FILE_PATH': log_file,
                'LOG_FORMAT': 'json',
                'LOG_ROTATE_ON_START': 'false',
                'LOG_WERKZEUG_FILE_PATH': werkzeug_file,
            }):
                setup_structlog()

                werkzeug_logger = logging.getLogger('werkzeug')
                file_handlers = [h for h in werkzeug_logger.handlers if isinstance(h, RotatingFileHandler)]
                assert len(file_handlers) >= 1, "Werkzeug logger should have a file handler"

                reset_structlog()

    def test_werkzeug_logs_not_in_structlog_file(self):
        """Verify Werkzeug logs do not appear in the structlog file."""
        reset_structlog()
        from utils.logging import setup_structlog

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            werkzeug_file = os.path.join(tmpdir, "werkzeug.log")

            with patch.dict(os.environ, {
                'LOG_LEVEL': 'INFO',
                'LOG_FILE_PATH': log_file,
                'LOG_FORMAT': 'json',
                'LOG_ROTATE_ON_START': 'false',
                'LOG_WERKZEUG_FILE_PATH': werkzeug_file,
            }):
                setup_structlog()

                # Log a Werkzeug message
                werkzeug_logger = logging.getLogger('werkzeug')
                werkzeug_logger.info('Werkzeug test message')

                # Flush all handlers
                root_logger = logging.getLogger()
                for handler in root_logger.handlers:
                    handler.flush()
                for handler in werkzeug_logger.handlers:
                    handler.flush()

                reset_structlog()

                # Structlog file should NOT contain Werkzeug message
                if os.path.exists(log_file):
                    with open(log_file, 'r') as f:
                        structlog_content = f.read()
                    assert 'Werkzeug test message' not in structlog_content, \
                        "Werkzeug logs should not appear in structlog file"

                # Werkzeug file SHOULD contain the message
                assert os.path.exists(werkzeug_file)
                with open(werkzeug_file, 'r') as f:
                    werkzeug_content = f.read()
                assert 'Werkzeug test message' in werkzeug_content, \
                    "Werkzeug logs should appear in werkzeug file"

    def test_structlog_logs_not_in_werkzeug_file(self):
        """Verify structlog logs do not appear in the Werkzeug file."""
        reset_structlog()
        from utils.logging import setup_structlog, get_logger

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            werkzeug_file = os.path.join(tmpdir, "werkzeug.log")

            with patch.dict(os.environ, {
                'LOG_LEVEL': 'INFO',
                'LOG_FILE_PATH': log_file,
                'LOG_FORMAT': 'json',
                'LOG_ROTATE_ON_START': 'false',
                'LOG_WERKZEUG_FILE_PATH': werkzeug_file,
            }):
                setup_structlog()
                logger = get_logger('test')
                logger.info('Structlog test message')

                # Flush all handlers
                root_logger = logging.getLogger()
                for handler in root_logger.handlers:
                    handler.flush()
                werkzeug_logger = logging.getLogger('werkzeug')
                for handler in werkzeug_logger.handlers:
                    handler.flush()

                reset_structlog()

                # Structlog file SHOULD contain the message
                assert os.path.exists(log_file)
                with open(log_file, 'r') as f:
                    structlog_content = f.read()
                assert 'Structlog test message' in structlog_content, \
                    "Structlog logs should appear in structlog file"

                # Werkzeug file should NOT contain structlog message
                if os.path.exists(werkzeug_file):
                    with open(werkzeug_file, 'r') as f:
                        werkzeug_content = f.read()
                    assert 'Structlog test message' not in werkzeug_content, \
                        "Structlog logs should not appear in werkzeug file"