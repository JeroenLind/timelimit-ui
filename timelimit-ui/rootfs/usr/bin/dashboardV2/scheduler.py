"""APScheduler scheduler module for dashboardV2 application.

This module provides the APScheduler BackgroundScheduler for running
the timechecker job every 10 seconds. The scheduler is designed to work
in both Windows and Home Assistant environments.

The scheduler runs ServerChecker.check() periodically and stores results
in the SQLite database.
"""

import os
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import Config
from database import Database, get_database, save_server_check
from middleware.request_logging import get_request_id
from utils.logging import get_logger

logger = get_logger(__name__)

# Create a config instance for accessing properties
_config = Config()

# Global scheduler instance
_scheduler: Optional[BackgroundScheduler] = None

# Current server URL for the scheduler (can be updated from session)
_current_server_url: Optional[str] = None


def set_server_url(url: str) -> None:
    """Set the server URL for the scheduler.
    
    Args:
        url: Server URL to use for checks.
    """
    global _current_server_url
    _current_server_url = url
    logger.debug(
        "Server URL updated for scheduler",
        component="scheduler",
        server_url=url
    )


def get_server_url() -> str:
    """Get the current server URL for the scheduler.
    
    Returns:
        Server URL string.
    """
    if _current_server_url:
        url = _current_server_url
    else:
        url = _config.DEBUG_SERVER_URL
    
    logger.debug(
        "Server URL retrieved for scheduler",
        component="scheduler",
        server_url=url
    )
    return url


def check_server_callback() -> None:
    """Callback function to check server status.
    
    This function is called by the scheduler at regular intervals.
    It checks the server status and stores the result in the database.
    """
    from auth_client import AuthClient, APIResponse
    
    request_id = get_request_id()
    server_url = get_server_url()
    
    logger.info(
        "Scheduled server check execution started",
        component="scheduler",
        server_url=server_url,
        request_id=request_id
    )
    
    try:
        # Create auth client and check server
        client = AuthClient(base_url=server_url)
        response = client.check_server_connection()
        
        # Get database instance
        db = get_database()
        
        # Save the result
        save_server_check(
            db=db,
            success=response.success,
            error_code=response.error_code,
            user_message=response.error_message,
            technical_detail=response.technical_detail,
            server_time=response.data.get('ms') if response.success else None,
            attempts=1,  # AuthClient doesn't expose attempts, default to 1
            server_url=server_url
        )
        
        if response.success:
            logger.info(
                "Scheduled server check completed successfully",
                component="scheduler",
                server_url=server_url,
                success=True,
                request_id=request_id
            )
        else:
            logger.error(
                "Scheduled server check failed",
                component="scheduler",
                server_url=server_url,
                success=False,
                error_code=response.error_code,
                error_message=response.error_message,
                technical_detail=response.technical_detail,
                request_id=request_id
            )
        
        client.close()
        
    except Exception as e:
        logger.error(
            "Scheduled server check error",
            component="scheduler",
            server_url=server_url,
            success=False,
            error=str(e),
            error_code="scheduler_error",
            request_id=request_id
        )
        raise


def create_scheduler(
    interval_seconds: Optional[int] = None,
    server_url: Optional[str] = None
) -> BackgroundScheduler:
    """Create and configure the APScheduler BackgroundScheduler.
    
    Args:
        interval_seconds: Interval between checks in seconds.
                         Uses config default if not provided.
        server_url: Server URL to check. Uses config default if not provided.
        
    Returns:
        Configured BackgroundScheduler instance.
    """
    interval = interval_seconds or _config.SCHEDULER_INTERVAL
    url = server_url or _config.DEBUG_SERVER_URL
    
    # Set the server URL for the callback
    set_server_url(url)
    
    scheduler = BackgroundScheduler()
    
    # Add the server check job
    scheduler.add_job(
        func=check_server_callback,
        trigger=IntervalTrigger(seconds=interval),
        id='server_check',
        name='Server Check Job',
        replace_existing=True
    )
    
    logger.info(
        "Scheduler created",
        component="scheduler",
        interval=interval,
        server_url=url
    )
    
    return scheduler


def get_scheduler() -> BackgroundScheduler:
    """Get the global scheduler instance.
    
    Creates the scheduler if it doesn't exist.
    
    Returns:
        BackgroundScheduler instance.
    """
    global _scheduler
    if _scheduler is None:
        _scheduler = create_scheduler()
        logger.debug(
            "Scheduler instance created",
            component="scheduler"
        )
    return _scheduler


def start_scheduler() -> BackgroundScheduler:
    """Start the global scheduler.
    
    Returns:
        Started BackgroundScheduler instance.
    """
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info(
            "Scheduler started",
            component="scheduler"
        )
    return scheduler


def stop_scheduler() -> None:
    """Stop the global scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()
        logger.info(
            "Scheduler stopped",
            component="scheduler"
        )
    _scheduler = None


def add_server_check_job(
    scheduler: BackgroundScheduler,
    server_url: str,
    interval_seconds: Optional[int] = None
) -> None:
    """Add a server check job to an existing scheduler.
    
    Args:
        scheduler: The scheduler to add the job to.
        server_url: The server URL to check.
        interval_seconds: Interval between checks in seconds.
    """
    interval = interval_seconds or _config.SCHEDULER_INTERVAL
    
    def check_with_url():
        """Check server with the specified URL."""
        from auth_client import AuthClient
        
        request_id = get_request_id()
        
        logger.debug(
            "Running scheduled server check",
            component="scheduler",
            server_url=server_url,
            request_id=request_id
        )
        
        try:
            client = AuthClient(base_url=server_url)
            response = client.check_server_connection()
            
            db = get_database()
            save_server_check(
                db=db,
                success=response.success,
                error_code=response.error_code,
                user_message=response.error_message,
                technical_detail=response.technical_detail,
                server_time=response.data.get('ms') if response.success else None,
                attempts=1,
                server_url=server_url
            )
            
            if response.success:
                logger.info(
                    "Server check completed successfully",
                    component="scheduler",
                    server_url=server_url,
                    success=True,
                    request_id=request_id
                )
            else:
                logger.error(
                    "Server check failed",
                    component="scheduler",
                    server_url=server_url,
                    success=False,
                    error_code=response.error_code,
                    error_message=response.error_message,
                    technical_detail=response.technical_detail,
                    request_id=request_id
                )
            
            client.close()
            
        except Exception as e:
            logger.error(
                "Server check error",
                component="scheduler",
                server_url=server_url,
                success=False,
                error=str(e),
                error_code="scheduler_error",
                request_id=request_id
            )
            raise
    
    scheduler.add_job(
        func=check_with_url,
        trigger=IntervalTrigger(seconds=interval),
        id=f'server_check_{server_url.replace("://", "_").replace(".", "_")}',
        name=f'Server Check Job for {server_url}',
        replace_existing=True
    )
    
    logger.debug(
        "Server check job added",
        component="scheduler",
        server_url=server_url,
        interval=interval
    )


def get_next_run_time(scheduler: BackgroundScheduler) -> Optional[datetime]:
    """Get the next scheduled run time.
    
    Args:
        scheduler: The scheduler to query.
        
    Returns:
        Next run time as datetime, or None if no jobs.
    """
    jobs = scheduler.get_jobs()
    if not jobs:
        return None
    
    # Get the next run time from the first job
    job = jobs[0]
    # next_run_time is only available when scheduler is running
    if scheduler.running and job.next_run_time:
        return job.next_run_time
    
    # Calculate next run time from trigger if scheduler not running
    if hasattr(job.trigger, 'interval') and job.trigger.interval:
        # Return a calculated next run time based on interval
        from datetime import timedelta
        interval_seconds = job.trigger.interval.total_seconds() if hasattr(job.trigger.interval, 'total_seconds') else job.trigger.interval
        return datetime.now() + timedelta(seconds=interval_seconds)
    
    return None


def is_scheduler_running() -> bool:
    """Check if the scheduler is running.
    
    Returns:
        True if scheduler is running, False otherwise.
    """
    return _scheduler is not None and _scheduler.running


def get_job_info(scheduler: BackgroundScheduler) -> dict:
    """Get information about scheduled jobs.
    
    Args:
        scheduler: The scheduler to query.
        
    Returns:
        Dictionary with job information.
    """
    jobs = scheduler.get_jobs()
    job_list = []
    for job in jobs:
        # next_run_time is only available when scheduler is running
        next_run = job.next_run_time if scheduler.running and job.next_run_time else None
        if next_run is None and hasattr(job.trigger, 'interval') and job.trigger.interval:
            # Calculate next run time from trigger if scheduler not running
            from datetime import timedelta
            interval_seconds = job.trigger.interval.total_seconds() if hasattr(job.trigger.interval, 'total_seconds') else job.trigger.interval
            next_run = datetime.now() + timedelta(seconds=interval_seconds)
        
        # Get interval in seconds
        interval_seconds = None
        if hasattr(job.trigger, 'interval') and job.trigger.interval:
            interval_seconds = job.trigger.interval.total_seconds() if hasattr(job.trigger.interval, 'total_seconds') else job.trigger.interval
        
        job_list.append({
            'id': job.id,
            'name': job.name,
            'next_run_time': next_run.isoformat() if next_run else None,
            'interval_seconds': interval_seconds
        })
    
    return {
        'running': scheduler.running,
        'job_count': len(jobs),
        'jobs': job_list
    }


# ============================================================================
# Scheduler Management Functions
# ============================================================================

def initialize_scheduler() -> BackgroundScheduler:
    """Initialize the scheduler with configuration.
    
    This function should be called during application startup.
    
    Returns:
        Initialized BackgroundScheduler instance.
    """
    global _scheduler
    
    # Reset any existing scheduler
    if _scheduler is not None:
        if _scheduler.running:
            _scheduler.shutdown()
    
    # Create new scheduler
    scheduler = create_scheduler()
    
    # Start the scheduler
    scheduler.start()
    
    # Store as global
    _scheduler = scheduler
    
    logger.info(
        "Scheduler initialized and started",
        component="scheduler"
    )
    
    return scheduler


def shutdown_scheduler() -> None:
    """Shutdown the scheduler gracefully."""
    global _scheduler
    if _scheduler is not None:
        if _scheduler.running:
            _scheduler.shutdown(wait=True)
            logger.info(
                "Scheduler shutdown complete",
                component="scheduler"
            )
        _scheduler = None


# ============================================================================
# Context Manager for Scheduler
# ============================================================================

class SchedulerContext:
    """Context manager for scheduler lifecycle.
    
    Usage:
        with SchedulerContext() as scheduler:
            # Use scheduler
            pass
        # Scheduler is automatically stopped on exit
    """
    
    def __init__(self, interval_seconds: Optional[int] = None):
        """Initialize the context manager.
        
        Args:
            interval_seconds: Interval between checks in seconds.
        """
        self.interval_seconds = interval_seconds
        self.scheduler: Optional[BackgroundScheduler] = None
    
    def __enter__(self) -> BackgroundScheduler:
        """Enter the context and start the scheduler.
        
        Returns:
            Started BackgroundScheduler instance.
        """
        self.scheduler = create_scheduler(self.interval_seconds)
        self.scheduler.start()
        return self.scheduler
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the context and stop the scheduler."""
        if self.scheduler:
            self.scheduler.shutdown(wait=True)


if __name__ == '__main__':
    # Test the scheduler
    from utils.logging import setup_structlog
    setup_structlog()
    
    # Initialize database
    db = get_database()
    db.init_db()
    
    # Start scheduler
    scheduler = start_scheduler()
    
    print(f"Scheduler started. Next run: {get_next_run_time(scheduler)}")
    
    # Keep running for a short time
    import time
    time.sleep(15)
    
    # Stop scheduler
    stop_scheduler()
    print("Scheduler stopped")