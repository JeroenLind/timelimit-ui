"""Unit tests for APScheduler scheduler functionality.

This module tests the Phase 3 scheduler implementation including:
- Scheduler creation and configuration
- Server check job execution
- Scheduler lifecycle management
- Server URL management for scheduler
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock

from scheduler import (
    create_scheduler,
    get_scheduler,
    start_scheduler,
    stop_scheduler,
    is_scheduler_running,
    get_job_info,
    get_next_run_time,
    set_server_url,
    get_server_url,
    initialize_scheduler,
    shutdown_scheduler,
    SchedulerContext,
    _scheduler,
    _current_server_url
)
from database import Database, get_database, reset_database
from config import Config


class TestSchedulerCreation:
    """Tests for scheduler creation."""
    
    def test_create_scheduler_returns_scheduler(self):
        """Test that create_scheduler returns a BackgroundScheduler."""
        scheduler = create_scheduler(interval_seconds=10)
        
        assert scheduler is not None
        assert hasattr(scheduler, 'start')
        assert hasattr(scheduler, 'shutdown')
        assert hasattr(scheduler, 'get_jobs')
        
        # Cleanup - start then shutdown to avoid SchedulerNotRunningError
        scheduler.start()
        scheduler.shutdown(wait=False)
    
    def test_create_scheduler_default_interval(self):
        """Test that create_scheduler uses default interval from config."""
        scheduler = create_scheduler()
        
        jobs = scheduler.get_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == 'server_check'
        
        # Cleanup - start then shutdown to avoid SchedulerNotRunningError
        scheduler.start()
        scheduler.shutdown(wait=False)
    
    def test_create_scheduler_custom_interval(self):
        """Test that create_scheduler uses custom interval."""
        scheduler = create_scheduler(interval_seconds=30)
        
        jobs = scheduler.get_jobs()
        assert len(jobs) == 1
        # Check the trigger interval - APScheduler returns timedelta
        interval = jobs[0].trigger.interval
        if hasattr(interval, 'total_seconds'):
            assert interval.total_seconds() == 30
        else:
            assert interval == 30
        
        # Cleanup - start then shutdown to avoid SchedulerNotRunningError
        scheduler.start()
        scheduler.shutdown(wait=False)


class TestSchedulerServerUrl:
    """Tests for server URL management in scheduler."""
    
    def test_set_and_get_server_url(self):
        """Test setting and getting server URL."""
        test_url = 'http://test-server:8080'
        set_server_url(test_url)
        
        assert get_server_url() == test_url
    
    def test_get_server_url_default(self):
        """Test getting server URL when not set returns config default."""
        # Reset the server URL
        import scheduler as scheduler_module
        scheduler_module._current_server_url = None
        
        url = get_server_url()
        
        # Use config instance to access the property
        _config = Config()
        assert url == _config.DEBUG_SERVER_URL
    
    def test_server_url_persists(self):
        """Test that server URL persists across calls."""
        test_url = 'http://persistent-server:8080'
        set_server_url(test_url)
        
        url1 = get_server_url()
        url2 = get_server_url()
        
        assert url1 == test_url
        assert url2 == test_url


class TestSchedulerLifecycle:
    """Tests for scheduler lifecycle management."""
    
    def test_get_scheduler_creates_instance(self):
        """Test that get_scheduler creates an instance if none exists."""
        # Reset scheduler
        import scheduler as scheduler_module
        scheduler_module._scheduler = None
        
        scheduler_instance = get_scheduler()
        
        assert scheduler_instance is not None
        
        # Cleanup
        scheduler_module._scheduler = None
    
    def test_get_scheduler_returns_same_instance(self):
        """Test that get_scheduler returns the same instance."""
        import scheduler as scheduler_module
        scheduler_module._scheduler = None
        
        scheduler1 = get_scheduler()
        scheduler2 = get_scheduler()
        
        assert scheduler1 is scheduler2
        
        # Cleanup
        scheduler_module._scheduler = None
    
    def test_start_scheduler(self):
        """Test starting the scheduler."""
        import scheduler as scheduler_module
        scheduler_module._scheduler = None
        
        scheduler_instance = start_scheduler()
        
        assert scheduler_instance.running is True
        
        # Cleanup
        stop_scheduler()
    
    def test_stop_scheduler(self):
        """Test stopping the scheduler."""
        import scheduler as scheduler_module
        scheduler_module._scheduler = None
        
        start_scheduler()
        stop_scheduler()
        
        assert _scheduler is None
    
    def test_is_scheduler_running(self):
        """Test checking if scheduler is running."""
        import scheduler as scheduler_module
        scheduler_module._scheduler = None
        
        assert is_scheduler_running() is False
        
        start_scheduler()
        assert is_scheduler_running() is True
        
        # Cleanup
        stop_scheduler()


class TestSchedulerJobInfo:
    """Tests for scheduler job information."""
    
    def test_get_job_info_returns_dict(self):
        """Test that get_job_info returns a dictionary."""
        import scheduler as scheduler_module
        scheduler_module._scheduler = None
        
        scheduler_instance = create_scheduler()
        info = get_job_info(scheduler_instance)
        
        assert isinstance(info, dict)
        assert 'running' in info
        assert 'job_count' in info
        assert 'jobs' in info
        
        # Cleanup - start then shutdown to avoid SchedulerNotRunningError
        scheduler_instance.start()
        scheduler_instance.shutdown(wait=False)
    
    def test_get_job_info_running_status(self):
        """Test that get_job_info reports running status."""
        import scheduler as scheduler_module
        scheduler_module._scheduler = None
        
        scheduler_instance = create_scheduler()
        info = get_job_info(scheduler_instance)
        
        assert info['running'] is False
        
        scheduler_instance.start()
        info = get_job_info(scheduler_instance)
        assert info['running'] is True
        
        # Cleanup
        scheduler_instance.shutdown(wait=False)
    
    def test_get_job_info_job_details(self):
        """Test that get_job_info includes job details."""
        import scheduler as scheduler_module
        scheduler_module._scheduler = None
        
        scheduler_instance = create_scheduler()
        info = get_job_info(scheduler_instance)
        
        assert len(info['jobs']) == 1
        job = info['jobs'][0]
        assert 'id' in job
        assert 'name' in job
        assert 'next_run_time' in job
        assert 'interval_seconds' in job
        assert job['id'] == 'server_check'
        
        # Cleanup - start then shutdown to avoid SchedulerNotRunningError
        scheduler_instance.start()
        scheduler_instance.shutdown(wait=False)


class TestSchedulerNextRunTime:
    """Tests for getting next run time."""
    
    def test_get_next_run_time_returns_datetime(self):
        """Test that get_next_run_time returns a datetime or None."""
        import scheduler as scheduler_module
        scheduler_module._scheduler = None
        
        scheduler_instance = create_scheduler()
        next_run = get_next_run_time(scheduler_instance)
        
        # Should return a datetime when scheduler has jobs
        assert next_run is not None
        
        # Cleanup - start then shutdown to avoid SchedulerNotRunningError
        scheduler_instance.start()
        scheduler_instance.shutdown(wait=False)
    
    def test_get_next_run_time_no_jobs(self):
        """Test that get_next_run_time returns None when no jobs."""
        from apscheduler.schedulers.background import BackgroundScheduler
        
        scheduler_instance = BackgroundScheduler()
        next_run = get_next_run_time(scheduler_instance)
        
        assert next_run is None


class TestSchedulerContext:
    """Tests for SchedulerContext context manager."""
    
    def test_context_manager_starts_and_stops_scheduler(self):
        """Test that context manager starts and stops scheduler."""
        with SchedulerContext(interval_seconds=10) as scheduler:
            assert scheduler.running is True
        
        # After exiting context, scheduler should be stopped
        assert scheduler.running is False
    
    def test_context_manager_returns_scheduler(self):
        """Test that context manager returns the scheduler."""
        with SchedulerContext() as scheduler:
            assert scheduler is not None
            assert hasattr(scheduler, 'get_jobs')


class TestInitializeShutdown:
    """Tests for initialize_scheduler and shutdown_scheduler functions."""
    
    def test_initialize_scheduler(self):
        """Test initialize_scheduler function."""
        import scheduler as scheduler_module
        scheduler_module._scheduler = None
        
        scheduler_instance = initialize_scheduler()
        
        assert scheduler_instance is not None
        assert scheduler_instance.running is True
        
        # Cleanup
        shutdown_scheduler()
    
    def test_shutdown_scheduler(self):
        """Test shutdown_scheduler function."""
        import scheduler as scheduler_module
        scheduler_module._scheduler = None
        
        initialize_scheduler()
        shutdown_scheduler()
        
        assert _scheduler is None


class TestSchedulerCallback:
    """Tests for the server check callback function."""
    
    @pytest.mark.timeout(10)
    def test_check_server_callback_success(self):
        """Test successful server check callback."""
        # Create temp database
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        db = Database(db_path=db_path)
        db.init_db()
        
        # Reset database singleton
        import database
        database._db_instance = db
        
        # Set server URL
        set_server_url('http://localhost:8080')
        
        # Import and call callback
        from scheduler import check_server_callback
        
        # Mock the AuthClient at the module level where it's imported
        with patch('auth_client.AuthClient') as mock_auth_client_class:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.success = True
            mock_response.error_code = None
            mock_response.error_message = None
            mock_response.technical_detail = None
            mock_response.data = {'ms': 1704067200000}
            mock_client.check_server_connection.return_value = mock_response
            mock_client.close = Mock()
            mock_auth_client_class.return_value = mock_client
            
            check_server_callback()
            
            # Verify client was called
            mock_client.check_server_connection.assert_called_once()
            mock_client.close.assert_called_once()
        
        # Cleanup
        db.close()
        os.close(db_fd)
        os.unlink(db_path)
    
    @pytest.mark.timeout(10)
    def test_check_server_callback_failure(self):
        """Test failed server check callback."""
        # Create temp database
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        db = Database(db_path=db_path)
        db.init_db()
        
        # Reset database singleton
        import database
        database._db_instance = db
        
        # Set server URL
        set_server_url('http://localhost:8080')
        
        # Import and call callback
        from scheduler import check_server_callback
        
        # Mock the AuthClient at the module level where it's imported
        with patch('auth_client.AuthClient') as mock_auth_client_class:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.success = False
            mock_response.error_code = 'timeout'
            mock_response.error_message = 'Connection timeout'
            mock_response.technical_detail = 'Timeout after 10s'
            mock_response.data = None
            mock_client.check_server_connection.return_value = mock_response
            mock_client.close = Mock()
            mock_auth_client_class.return_value = mock_client
            
            check_server_callback()
            
            # Verify client was called
            mock_client.check_server_connection.assert_called_once()
            mock_client.close.assert_called_once()
        
        # Cleanup
        db.close()
        os.close(db_fd)
        os.unlink(db_path)


class TestSchedulerIntegration:
    """Integration tests for scheduler with Flask app."""
    
    @pytest.mark.timeout(10)
    def test_scheduler_with_flask_app(self, app):
        """Test that scheduler works with Flask app context."""
        from scheduler import create_scheduler, stop_scheduler
        
        scheduler = create_scheduler(interval_seconds=10)
        
        assert scheduler is not None
        assert len(scheduler.get_jobs()) == 1
        
        # Cleanup
        stop_scheduler()
    
    @pytest.mark.timeout(10)
    def test_scheduler_uses_session_server_url(self, client):
        """Test that scheduler can use server URL from session."""
        from scheduler import set_server_url, get_server_url
        
        # Set server URL
        test_url = 'http://test-server:8080'
        set_server_url(test_url)
        
        # Verify it's set
        assert get_server_url() == test_url
        
        # Cleanup
        import scheduler as scheduler_module
        scheduler_module._current_server_url = None