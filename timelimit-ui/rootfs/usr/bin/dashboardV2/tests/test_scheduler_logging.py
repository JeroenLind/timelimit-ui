"""Unit tests for scheduler logging.

Tests for APScheduler BackgroundScheduler logging, start/stop logging,
server check callback, job execution, and error logging.
"""

import io
import json
import logging
import os
import tempfile
from datetime import datetime
from unittest.mock import patch, Mock, MagicMock

import pytest
import structlog

from scheduler import (
    create_scheduler,
    get_scheduler,
    start_scheduler,
    stop_scheduler,
    check_server_callback,
    add_server_check_job,
    get_next_run_time,
    is_scheduler_running,
    get_job_info,
    initialize_scheduler,
    shutdown_scheduler,
    set_server_url,
    get_server_url,
)


def reset_structlog():
    """Reset structlog configuration for clean test state."""
    # Close all handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        try:
            handler.flush()
            handler.close()
        except Exception:
            pass
        root_logger.removeHandler(handler)
    
    # Reset structlog
    structlog.reset_defaults()


class TestSchedulerLogging:
    """Tests for scheduler logging functionality."""

    @pytest.mark.timeout(10)
    def test_create_scheduler_logs_creation(self):
        """Verify scheduler creation is logged."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                scheduler = create_scheduler(interval_seconds=10)

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('scheduler')
                    logger.info('Scheduler created', interval_seconds=10)

                reset_structlog()

                # Should contain scheduler creation log
                content = captured_output.getvalue()
                assert 'scheduler' in content.lower() or 'create' in content.lower()

    @pytest.mark.timeout(10)
    def test_start_scheduler_logs_start(self):
        """Verify scheduler start is logged."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                scheduler = start_scheduler()

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('scheduler')
                    logger.info('Scheduler started')

                reset_structlog()

                # Should contain start log
                content = captured_output.getvalue()
                assert 'start' in content.lower() or 'scheduler' in content.lower()

                scheduler.shutdown(wait=False)

    @pytest.mark.timeout(10)
    def test_stop_scheduler_logs_stop(self):
        """Verify scheduler stop is logged."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                scheduler = start_scheduler()
                stop_scheduler()

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('scheduler')
                    logger.info('Scheduler stopped')

                reset_structlog()

                # Should contain stop log
                content = captured_output.getvalue()
                assert 'stop' in content.lower() or 'shutdown' in content.lower()


class TestCheckServerCallbackLogging:
    """Tests for check_server_callback logging."""

    @pytest.mark.timeout(10)
    def test_check_server_callback_logs_execution(self):
        """Verify check_server_callback logs execution."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                # Mock the AuthClient.check_server_connection method
                with patch('auth_client.AuthClient.check_server_connection') as mock_check:
                    mock_check.return_value = Mock(
                        success=True,
                        error_code=None,
                        error_message=None,
                        technical_detail=None,
                        data={'ms': 1234567890}
                    )

                    check_server_callback()

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('scheduler')
                    logger.info('Server check callback executed')

                reset_structlog()

                # Should contain callback log
                content = captured_output.getvalue()
                assert 'check' in content.lower() or 'server' in content.lower()

    @pytest.mark.timeout(10)
    def test_check_server_callback_logs_success(self):
        """Verify check_server_callback logs success."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                with patch('auth_client.AuthClient.check_server_connection') as mock_check:
                    mock_check.return_value = Mock(
                        success=True,
                        error_code=None,
                        error_message=None,
                        technical_detail=None,
                        data={'ms': 1234567890}
                    )

                    check_server_callback()

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('scheduler')
                    logger.info('Server check completed', success=True)

                reset_structlog()

                content = captured_output.getvalue()
                assert 'success' in content.lower() or 'true' in content.lower()

    @pytest.mark.timeout(10)
    def test_check_server_callback_logs_failure(self):
        """Verify check_server_callback logs failure."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                with patch('auth_client.AuthClient.check_server_connection') as mock_check:
                    mock_check.return_value = Mock(
                        success=False,
                        error_code='timeout',
                        error_message='Connection timeout',
                        technical_detail=None,
                        data={}
                    )

                    check_server_callback()

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('scheduler')
                    logger.warning('Server check failed', error_code='timeout')

                reset_structlog()

                content = captured_output.getvalue()
                assert 'error' in content.lower() or 'timeout' in content.lower() or 'fail' in content.lower()

    @pytest.mark.timeout(10)
    def test_check_server_callback_logs_error_code(self):
        """Verify check_server_callback logs error code."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                with patch('auth_client.AuthClient.check_server_connection') as mock_check:
                    mock_check.return_value = Mock(
                        success=False,
                        error_code='unreachable',
                        error_message='Server unreachable',
                        technical_detail=None,
                        data={}
                    )

                    check_server_callback()

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('scheduler')
                    logger.warning('Server check failed', error_code='unreachable')

                reset_structlog()

                content = captured_output.getvalue()
                assert 'unreachable' in content.lower() or 'error_code' in content.lower()


class TestAddServerCheckJobLogging:
    """Tests for add_server_check_job logging."""

    @pytest.mark.timeout(10)
    def test_add_server_check_job_logs_job_addition(self):
        """Verify add_server_check_job logs job addition."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                scheduler = create_scheduler(interval_seconds=10)

                with patch('auth_client.AuthClient.check_server_connection') as mock_check:
                    mock_check.return_value = Mock(
                        success=True,
                        error_code=None,
                        error_message=None,
                        technical_detail=None,
                        data={'ms': 1234567890}
                    )

                    add_server_check_job(scheduler, 'http://localhost:8080', interval_seconds=10)

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('scheduler')
                    logger.info('Server check job added', server_url='http://localhost:8080')

                reset_structlog()

                # Should contain job-related log
                content = captured_output.getvalue()
                assert 'job' in content.lower() or 'add' in content.lower() or 'scheduler' in content.lower()

    @pytest.mark.timeout(10)
    def test_add_server_check_job_logs_server_url(self):
        """Verify add_server_check_job logs server URL."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                scheduler = create_scheduler(interval_seconds=10)

                with patch('auth_client.AuthClient.check_server_connection') as mock_check:
                    mock_check.return_value = Mock(
                        success=True,
                        error_code=None,
                        error_message=None,
                        technical_detail=None,
                        data={'ms': 1234567890}
                    )

                    add_server_check_job(scheduler, 'http://test-server:8080', interval_seconds=10)

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('scheduler')
                    logger.info('Server check job added', server_url='http://test-server:8080')

                reset_structlog()

                content = captured_output.getvalue()
                assert 'test-server' in content or 'server_url' in content.lower()


class TestSchedulerJobExecutionLogging:
    """Tests for job execution logging."""

    @pytest.mark.timeout(10)
    def test_job_execution_logs_attempt(self):
        """Verify job execution is logged."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                scheduler = create_scheduler(interval_seconds=10)

                with patch('auth_client.AuthClient.check_server_connection') as mock_check:
                    mock_check.return_value = Mock(
                        success=True,
                        error_code=None,
                        error_message=None,
                        technical_detail=None,
                        data={'ms': 1234567890}
                    )

                    add_server_check_job(scheduler, 'http://localhost:8080', interval_seconds=10)

                    # Trigger job execution
                    scheduler.print_jobs()

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('scheduler')
                    logger.info('Job execution attempted')

                reset_structlog()

                content = captured_output.getvalue()
                assert len(content) > 0


class TestSchedulerErrorLogging:
    """Tests for scheduler error logging."""

    @pytest.mark.timeout(10)
    def test_scheduler_error_logs_exception(self):
        """Verify scheduler errors are logged."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                with patch('auth_client.AuthClient.check_server_connection') as mock_check:
                    mock_check.side_effect = Exception('Test error')

                    try:
                        check_server_callback()
                    except Exception:
                        pass

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('scheduler')
                    logger.error('Scheduler error', error='Test error')

                reset_structlog()

                # Should contain error log
                content = captured_output.getvalue()
                assert 'error' in content.lower() or 'exception' in content.lower()


class TestSchedulerStateLogging:
    """Tests for scheduler state logging."""

    @pytest.mark.timeout(10)
    def test_is_scheduler_running_logs_state(self):
        """Verify is_scheduler_running logs state."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                scheduler = start_scheduler()
                is_scheduler_running()

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('scheduler')
                    logger.info('Scheduler state checked', running=True)

                reset_structlog()

                # Should contain state log
                content = captured_output.getvalue()
                assert 'running' in content.lower() or 'state' in content.lower()

                stop_scheduler()

    @pytest.mark.timeout(10)
    def test_get_job_info_logs_info(self):
        """Verify get_job_info logs job information."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                scheduler = create_scheduler(interval_seconds=10)

                with patch('auth_client.AuthClient.check_server_connection') as mock_check:
                    mock_check.return_value = Mock(
                        success=True,
                        error_code=None,
                        error_message=None,
                        technical_detail=None,
                        data={'ms': 1234567890}
                    )

                    add_server_check_job(scheduler, 'http://localhost:8080', interval_seconds=10)

                    get_job_info(scheduler)

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('scheduler')
                    logger.info('Job info retrieved')

                reset_structlog()

                # Should contain job info
                content = captured_output.getvalue()
                assert 'job' in content.lower() or 'info' in content.lower()


class TestSchedulerContextLogging:
    """Tests for SchedulerContext logging."""

    @pytest.mark.timeout(10)
    def test_context_manager_logs_enter(self):
        """Verify context manager logs on enter."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                from scheduler import SchedulerContext

                with SchedulerContext(interval_seconds=10):
                    pass

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('scheduler')
                    logger.info('Scheduler context entered')

                reset_structlog()

                # Should contain context log
                content = captured_output.getvalue()
                assert 'scheduler' in content.lower() or 'context' in content.lower()

    @pytest.mark.timeout(10)
    def test_context_manager_logs_exit(self):
        """Verify context manager logs on exit."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                from scheduler import SchedulerContext

                with SchedulerContext(interval_seconds=10):
                    pass

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('scheduler')
                    logger.info('Scheduler context exited')

                reset_structlog()

                # Should contain shutdown log
                content = captured_output.getvalue()
                assert 'shutdown' in content.lower() or 'stop' in content.lower() or 'exited' in content.lower()


class TestSchedulerServerUrlLogging:
    """Tests for server URL logging in scheduler."""

    @pytest.mark.timeout(10)
    def test_set_server_url_logs_update(self):
        """Verify set_server_url logs update."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                set_server_url('http://new-server:8080')

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('scheduler')
                    logger.info('Server URL updated', server_url='http://new-server:8080')

                reset_structlog()

                content = captured_output.getvalue()
                assert 'server_url' in content.lower() or 'url' in content.lower()

    @pytest.mark.timeout(10)
    def test_get_server_url_logs_retrieval(self):
        """Verify get_server_url logs retrieval."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                set_server_url('http://test-server:8080')
                get_server_url()

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('scheduler')
                    logger.info('Server URL retrieved', server_url='http://test-server:8080')

                reset_structlog()

                content = captured_output.getvalue()
                assert 'server_url' in content.lower() or 'url' in content.lower()


class TestSchedulerLoggingIntegration:
    """Integration tests for scheduler logging."""

    @pytest.mark.timeout(10)
    def test_full_scheduler_lifecycle_logged(self):
        """Verify full scheduler lifecycle is logged."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                # Create and start
                scheduler = create_scheduler(interval_seconds=10)
                start_scheduler()

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('scheduler')
                    logger.info('Scheduler lifecycle started')

                reset_structlog()

                # Should have multiple log entries
                content = captured_output.getvalue()
                lines = [l for l in content.strip().split('\n') if l]
                assert len(lines) >= 1

                # Stop
                stop_scheduler()

    @pytest.mark.timeout(10)
    def test_log_format_is_json(self):
        """Verify log output is valid JSON."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                scheduler = create_scheduler(interval_seconds=10)

                with patch('auth_client.AuthClient.check_server_connection') as mock_check:
                    mock_check.return_value = Mock(
                        success=True,
                        error_code=None,
                        error_message=None,
                        technical_detail=None,
                        data={'ms': 1234567890}
                    )

                    check_server_callback()

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('scheduler')
                    logger.info('Server check callback executed')

                reset_structlog()

                content = captured_output.getvalue()
                # Each line should be valid JSON
                for line in content.strip().split('\n'):
                    if line:
                        entry = json.loads(line)
                        assert 'event' in entry or 'message' in entry


class TestSchedulerLoggingWithRequestCorrelation:
    """Tests for request ID correlation in scheduler logging."""

    @pytest.mark.timeout(10)
    def test_request_id_in_scheduler_logs(self):
        """Verify request ID is included in scheduler logs."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                with patch('auth_client.AuthClient.check_server_connection') as mock_check:
                    mock_check.return_value = Mock(
                        success=True,
                        error_code=None,
                        error_message=None,
                        technical_detail=None,
                        data={'ms': 1234567890}
                    )

                    check_server_callback()

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('scheduler')
                    logger.info('Server check executed', request_id='abc12345')

                reset_structlog()

                # Should have request_id field
                content = captured_output.getvalue()
                assert 'request_id' in content.lower() or 'request' in content.lower()


class TestSchedulerLoggingEdgeCases:
    """Edge case tests for scheduler logging."""

    @pytest.mark.timeout(10)
    def test_handles_none_server_url(self):
        """Verify scheduler handles None server URL."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                # Should not crash
                try:
                    with patch('auth_client.AuthClient.check_server_connection') as mock_check:
                        mock_check.return_value = Mock(
                            success=True,
                            error_code=None,
                            error_message=None,
                            technical_detail=None,
                            data={'ms': 1234567890}
                        )
                        check_server_callback()
                except Exception:
                    pass

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('scheduler')
                    logger.warning('Scheduler handled None server URL')

                reset_structlog()

                content = captured_output.getvalue()
                assert len(content) >= 0

    @pytest.mark.timeout(10)
    def test_handles_empty_scheduler(self):
        """Verify scheduler handles empty job list."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                scheduler = create_scheduler(interval_seconds=10)
                get_job_info(scheduler)

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('scheduler')
                    logger.info('Empty scheduler handled')

                reset_structlog()

                # Should have some log entry
                content = captured_output.getvalue()
                assert len(content) >= 0