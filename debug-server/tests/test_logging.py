"""Unit tests for logging configuration.

This module tests the logging setup functionality including handler configuration,
log file path, log level settings, timestamped log file creation, retention policy,
and server message logging functionality.
"""

import glob
import logging
import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from app.core.logging import (
    setup_logging,
    get_current_log_file_path,
    _current_log_file_path,
)
from app.core.config import settings
from app.utils.log_rotation import (
    generate_timestamped_filename,
    generate_unique_log_path,
    get_log_files,
    rotate_log_files,
    cleanup_old_logs,
    get_log_files_info,
    ensure_log_directory,
    DEFAULT_MAX_LOG_FILES,
)
from app.middleware.server_message_logger import (
    ServerMessageLogger,
    MessageType,
    get_server_message_logger,
    reset_server_message_logger,
)


def close_all_handlers():
    """Close all handlers on the root logger to release file handles."""
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        handler.close()
        root_logger.removeHandler(handler)


class TestLogRotation:
    """Tests for log rotation utility functions."""

    def test_generate_timestamped_filename(self):
        """Verify that generate_timestamped_filename creates correct format."""
        filename = generate_timestamped_filename("debug-server")
        
        # Should match pattern: debug-server-YYYY-MM-DD_HH-MM-SS.log
        pattern = r"^debug-server-\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.log$"
        assert re.match(pattern, filename), f"Filename '{filename}' doesn't match expected pattern"

    def test_generate_timestamped_filename_custom_base(self):
        """Verify custom base name in timestamped filename."""
        filename = generate_timestamped_filename("myapp")
        assert filename.startswith("myapp-")
        assert filename.endswith(".log")

    def test_generate_unique_log_path_creates_directory(self):
        """Verify that generate_unique_log_path creates the log directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = os.path.join(tmpdir, "logs", "subdir")
            log_path = generate_unique_log_path(log_dir, "test-server")
            
            # Directory should be created
            assert os.path.exists(log_dir)
            assert log_path.startswith(log_dir)
            assert "test-server-" in log_path
            assert log_path.endswith(".log")

    def test_generate_unique_log_path_no_conflict(self):
        """Verify unique path generation when no conflict exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = generate_unique_log_path(tmpdir, "test-server")
            
            # File should not exist yet (just the path is generated)
            # The actual file is created by setup_logging
            assert log_path.startswith(tmpdir)

    def test_get_log_files_empty_directory(self):
        """Verify get_log_files returns empty list for non-existent directory."""
        files = get_log_files("/nonexistent/directory")
        assert files == []

    def test_get_log_files_sorted_by_mtime(self):
        """Verify get_log_files returns files sorted by modification time (oldest first)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create multiple log files with different timestamps
            for i in range(3):
                log_file = os.path.join(tmpdir, f"debug-server-2023-01-0{i+1}_12-00-00.log")
                Path(log_file).touch()
                # Small delay to ensure different mtime
                import time
                time.sleep(0.01)
            
            files = get_log_files(tmpdir)
            
            # Should be sorted by mtime (oldest first)
            assert len(files) == 3
            # Files should be in chronological order
            for i in range(len(files) - 1):
                assert os.path.getmtime(files[i]) <= os.path.getmtime(files[i + 1])

    def test_rotate_log_files_removes_oldest(self):
        """Verify rotate_log_files removes oldest files when count exceeds max."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create 15 log files with the correct pattern
            for i in range(15):
                log_file = os.path.join(tmpdir, f"debug-server-2023-01-{(i % 28) + 1:02d}_12-00-0{i}.log")
                Path(log_file).touch()
                # Small delay to ensure different mtime
                import time
                time.sleep(0.01)
            
            # Rotate with max 10 files
            removed = rotate_log_files(tmpdir, max_files=10)
            
            # Should have removed 5 files
            assert len(removed) == 5
            
            # Should have 10 files remaining
            remaining = get_log_files(tmpdir)
            assert len(remaining) == 10

    def test_rotate_log_files_fewer_than_max(self):
        """Verify rotate_log_files does nothing when files < max."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create 5 log files
            for i in range(5):
                log_file = os.path.join(tmpdir, f"debug-server-2023-01-0{i+1}_12-00-00.log")
                Path(log_file).touch()
            
            # Rotate with max 10 files
            removed = rotate_log_files(tmpdir, max_files=10)
            
            # Should have removed nothing
            assert len(removed) == 0
            
            # Should have all 5 files remaining
            remaining = get_log_files(tmpdir)
            assert len(remaining) == 5

    def test_cleanup_old_logs_returns_statistics(self):
        """Verify cleanup_old_logs returns correct statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create 12 log files with the correct pattern
            for i in range(12):
                log_file = os.path.join(tmpdir, f"debug-server-2023-01-{(i % 28) + 1:02d}_12-00-0{i}.log")
                Path(log_file).touch()
                import time
                time.sleep(0.01)
            
            stats = cleanup_old_logs(tmpdir, max_files=10)
            
            assert stats["total_files_before"] == 12
            assert stats["total_files_after"] == 10
            assert stats["files_removed"] == 2
            assert len(stats["removed_files"]) == 2

    def test_get_log_files_info(self):
        """Verify get_log_files_info returns correct file information."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a log file
            log_file = os.path.join(tmpdir, "debug-server-2023-10-05_14-30-00.log")
            Path(log_file).touch()
            
            files_info = get_log_files_info(tmpdir)
            
            assert len(files_info) == 1
            assert files_info[0]["path"] == log_file
            assert "size_bytes" in files_info[0]
            assert "mtime" in files_info[0]
            assert "ctime" in files_info[0]

    def test_ensure_log_directory(self):
        """Verify ensure_log_directory creates directory and returns absolute path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = os.path.join(tmpdir, "logs", "nested", "dir")
            result = ensure_log_directory(log_dir)
            
            assert os.path.exists(log_dir)
            assert result == os.path.abspath(log_dir)


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_logging_creates_timestamped_file(self):
        """Verify setup_logging creates a timestamped log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Change to temp directory so logs go there
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                log_path = setup_logging(
                    log_level="INFO",
                    log_file_path=None,  # Will generate timestamped path
                )
                
                # Should create a file in logs directory
                assert log_path is not None
                assert "debug-server-" in log_path
                assert log_path.endswith(".log")
                
                # File should exist
                assert os.path.exists(log_path)
            finally:
                close_all_handlers()
                os.chdir(original_cwd)

    def test_setup_logging_with_custom_path(self):
        """Verify setup_logging uses custom path when provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_path = os.path.join(tmpdir, "custom.log")
            log_path = setup_logging(log_file_path=custom_path)
            
            assert log_path == custom_path
            assert os.path.exists(custom_path)
            close_all_handlers()

    def test_setup_logging_configures_handlers(self):
        """Verify setup_logging configures both StreamHandler and FileHandler."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = setup_logging(log_file_path=os.path.join(tmpdir, "test.log"))
            
            root_logger = logging.getLogger()
            
            # Verify root logger has handlers
            assert root_logger.handlers is not None
            assert len(root_logger.handlers) > 0
            
            # Verify at least one StreamHandler exists
            stream_handlers = [h for h in root_logger.handlers if isinstance(h, logging.StreamHandler)]
            assert len(stream_handlers) > 0
            
            # Verify at least one FileHandler exists
            file_handlers = [h for h in root_logger.handlers if isinstance(h, logging.FileHandler)]
            assert len(file_handlers) > 0
            close_all_handlers()

    def test_setup_logging_sets_level(self):
        """Verify setup_logging sets the correct log level."""
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_logging(log_level="DEBUG", log_file_path=os.path.join(tmpdir, "test.log"))
            
            root_logger = logging.getLogger()
            # The level should be DEBUG (10)
            assert root_logger.level == logging.DEBUG
            close_all_handlers()

    def test_get_current_log_file_path(self):
        """Verify get_current_log_file_path returns the current log file path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = setup_logging(log_file_path=os.path.join(tmpdir, "test.log"))
            
            current_path = get_current_log_file_path()
            assert current_path == log_path
            close_all_handlers()


class TestLogRetention:
    """Tests for log retention policy."""

    def test_retention_keeps_only_10_most_recent(self):
        """Verify retention policy keeps only 10 most recent log files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create 15 log files with different timestamps
            for i in range(15):
                timestamp = datetime(2023, 1, (i % 28) + 1, 12, 0, 0)
                log_file = os.path.join(
                    tmpdir, 
                    f"debug-server-{timestamp.strftime('%Y-%m-%d_%H-%M-%S')}.log"
                )
                Path(log_file).touch()
                import time
                time.sleep(0.01)
            
            # Setup logging should trigger rotation
            log_path = setup_logging(log_file_path=os.path.join(tmpdir, "new.log"))
            
            # Should have at most 10 files
            remaining = get_log_files(tmpdir)
            assert len(remaining) <= 10
            close_all_handlers()

    def test_retention_handles_fewer_than_max(self):
        """Verify retention handles fewer than max log files gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create only 3 log files
            for i in range(3):
                log_file = os.path.join(tmpdir, f"debug-server-2023-01-0{i+1}_12-00-00.log")
                Path(log_file).touch()
            
            # Setup logging should not remove any files
            log_path = setup_logging(log_file_path=os.path.join(tmpdir, "new.log"))
            
            # Should still have 3 files
            remaining = get_log_files(tmpdir)
            assert len(remaining) == 3
            close_all_handlers()

    def test_retention_maintains_chronological_order(self):
        """Verify retention maintains chronological order of log files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create log files
            for i in range(12):
                log_file = os.path.join(tmpdir, f"debug-server-2023-01-{(i % 10) + 1:02d}_12-00-00.log")
                Path(log_file).touch()
                import time
                time.sleep(0.01)
            
            # Setup logging triggers rotation
            setup_logging(log_file_path=os.path.join(tmpdir, "new.log"))
            
            # Get remaining files
            remaining = get_log_files(tmpdir)
            
            # Should be sorted by mtime (oldest first)
            for i in range(len(remaining) - 1):
                assert os.path.getmtime(remaining[i]) <= os.path.getmtime(remaining[i + 1])
            close_all_handlers()

    def test_retention_applied_to_custom_log_directory(self):
        """Verify retention is applied to custom log directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = os.path.join(tmpdir, "logs")
            
            # Create the directory first
            os.makedirs(log_dir, exist_ok=True)
            
            # Create 15 log files in the custom directory
            for i in range(15):
                timestamp = datetime(2023, 1, (i % 28) + 1, 12, 0, 0)
                log_file = os.path.join(
                    log_dir, 
                    f"debug-server-{timestamp.strftime('%Y-%m-%d_%H-%M-%S')}.log"
                )
                Path(log_file).touch()
                import time
                time.sleep(0.01)
            
            # Setup logging with custom path in the same directory
            log_path = setup_logging(log_file_path=os.path.join(log_dir, "new.log"))
            
            # Should have at most 10 files
            remaining = get_log_files(log_dir)
            assert len(remaining) <= 10
            close_all_handlers()


class TestLogFilePath:
    """Tests for log file path configuration."""

    def test_log_file_path_from_settings(self):
        """Verify log file path uses settings.LOG_FILE_PATH when provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_path = os.path.join(tmpdir, "debug-server.log")
            log_path = setup_logging(log_file_path=custom_path)
            
            assert log_path == custom_path
            close_all_handlers()

    def test_default_log_directory(self):
        """Verify default log directory is 'logs'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Change to temp directory
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                log_path = setup_logging()
                
                # Should create logs directory
                assert "logs" in log_path
                assert os.path.exists(os.path.dirname(log_path))
            finally:
                close_all_handlers()
                os.chdir(original_cwd)


class TestIntegration:
    """Integration tests for logging system."""

    def test_full_logging_workflow(self):
        """Test complete logging workflow with timestamped files and retention."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create initial log files
            for i in range(5):
                log_file = os.path.join(tmpdir, f"debug-server-2023-01-0{i+1}_12-00-00.log")
                Path(log_file).touch()
                import time
                time.sleep(0.01)
            
            # Setup logging (should create new file and rotate old ones)
            log_path = setup_logging(log_file_path=os.path.join(tmpdir, "new.log"))
            
            # Verify new file was created
            assert os.path.exists(log_path)
            
            # Verify the path is the one we provided
            assert log_path == os.path.join(tmpdir, "new.log")
            
            # Verify retention (should have at most 10 files)
            remaining = get_log_files(tmpdir)
            assert len(remaining) <= 10
            close_all_handlers()

    def test_logging_writes_to_file(self):
        """Verify logging actually writes to the log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = setup_logging(log_file_path=os.path.join(tmpdir, "test.log"))
            
            # Write a log message
            logger = logging.getLogger("test-logger")
            logger.info("Test log message")
            
            # Flush handlers
            for handler in logging.getLogger().handlers:
                handler.flush()
            
            # Verify file has content
            with open(log_path, 'r') as f:
                content = f.read()
                assert "Test log message" in content
            close_all_handlers()

    def test_startup_log_entry_present(self):
        """Verify startup log entry 'Debug server started' is written to log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = setup_logging(log_file_path=os.path.join(tmpdir, "test.log"))
            
            # Verify file exists
            assert os.path.exists(log_path)
            
            # Read the log file content
            with open(log_path, 'r') as f:
                content = f.read()
            
            # Verify startup log entry is present
            assert "Debug server started" in content, \
                f"Startup log entry 'Debug server started' not found in log file. Content: {content}"
            
            # Verify the log entry has a timestamp (check for date pattern)
            import re
            # The log format is: %(asctime)s - %(name)s - %(levelname)s - %(message)s
            # asctime format is typically: YYYY-MM-DD HH:MM:SS,mmm
            timestamp_pattern = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'
            assert re.search(timestamp_pattern, content), \
                f"Timestamp not found in log entry. Content: {content}"
            
            close_all_handlers()

    def test_startup_log_entry_with_timestamped_file(self):
        """Verify startup log entry is written to timestamped log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Change to temp directory so logs go there
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                log_path = setup_logging()
                
                # Verify file exists
                assert os.path.exists(log_path)
                
                # Read the log file content
                with open(log_path, 'r') as f:
                    content = f.read()
                
                # Verify startup log entry is present
                assert "Debug server started" in content, \
                    f"Startup log entry 'Debug server started' not found in log file. Content: {content}"
                
                # Verify the log entry has a timestamp
                import re
                timestamp_pattern = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'
                assert re.search(timestamp_pattern, content), \
                    f"Timestamp not found in log entry. Content: {content}"
            finally:
                close_all_handlers()
                os.chdir(original_cwd)


class TestServerMessageLoggerIntegration:
    """Integration tests for server message logging with the logging system."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()

    def test_server_message_logger_with_setup_logging(self):
        """Verify server message logger works with setup_logging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = setup_logging(log_file_path=os.path.join(tmpdir, "test.log"))
            
            # Get the server message logger
            server_logger = get_server_message_logger(log_path)
            
            # Log a message
            server_logger.log_message(
                message_type=MessageType.API_RESPONSE,
                content={"status": "ok"},
                metadata={"path": "/test"}
            )
            
            # Verify the log file contains the message
            with open(log_path, 'r') as f:
                content = f.read()
                assert "[SERVER]" in content
                assert "api_response" in content
            
            close_all_handlers()

    def test_server_message_logger_logs_to_same_file(self):
        """Verify server message logger writes to the same log file as setup_logging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = setup_logging(log_file_path=os.path.join(tmpdir, "test.log"))
            
            # Get the server message logger
            server_logger = get_server_message_logger(log_path)
            
            # Log a message
            server_logger.log_api_response(
                content={"status": "ok"},
                status_code=200
            )
            
            # Verify the log file contains both startup and server message
            with open(log_path, 'r') as f:
                content = f.read()
                assert "Debug server started" in content
                assert "[SERVER]" in content
            
            close_all_handlers()

    def test_server_message_logger_timestamp_format(self):
        """Verify server message logger uses correct timestamp format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = setup_logging(log_file_path=os.path.join(tmpdir, "test.log"))
            
            server_logger = get_server_message_logger(log_path)
            
            before_time = datetime.now()
            server_logger.log_message(
                message_type=MessageType.API_RESPONSE,
                content={"status": "ok"}
            )
            after_time = datetime.now()
            
            # Flush to ensure message is written
            server_logger.flush()
            
            with open(log_path, 'r') as f:
                content = f.read()
            
            # Extract timestamp from server log entry
            match = re.search(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\] \[SERVER\]', content)
            assert match, f"Server message timestamp not found. Content: {content}"
            
            log_timestamp_str = match.group(1)
            log_timestamp = datetime.strptime(log_timestamp_str, "%Y-%m-%d %H:%M:%S.%f")
            
            # Convert to millisecond precision for comparison
            before_ms = before_time.replace(microsecond=(before_time.microsecond // 1000) * 1000)
            after_ms = after_time.replace(microsecond=(after_time.microsecond // 1000) * 1000)
            
            # Verify timestamp is within the expected window (at millisecond precision)
            assert before_ms <= log_timestamp <= after_ms
            
            close_all_handlers()

    def test_server_message_logger_data_integrity(self):
        """Verify server message logger preserves data integrity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = setup_logging(log_file_path=os.path.join(tmpdir, "test.log"))
            
            server_logger = get_server_message_logger(log_path)
            
            # Log a complex message
            content = {
                "user": {
                    "id": 12345,
                    "email": "test@example.com",
                    "profile": {
                        "name": "Test User",
                        "preferences": ["email", "sms"]
                    }
                },
                "action": "update_profile",
                "timestamp": "2024-01-15T10:30:00Z"
            }
            
            server_logger.log_message(
                message_type=MessageType.API_RESPONSE,
                content=content,
                metadata={"request_id": "req_123"}
            )
            
            with open(log_path, 'r') as f:
                log_content = f.read()
            
            # Verify key data is preserved
            assert "12345" in log_content
            assert "test@example.com" in log_content
            assert "update_profile" in log_content
            assert "req_123" in log_content
            
            close_all_handlers()
