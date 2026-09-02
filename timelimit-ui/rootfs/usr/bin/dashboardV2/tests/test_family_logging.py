"""Unit tests for family logging functionality.

This module tests the KeyFamilyData.md logging functionality for family creation events.
"""

import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from utils.family_logging import (
    log_family_creation,
    format_markdown_entry,
    get_server_environment_details,
    get_file_header,
    get_troubleshooting_section,
    ensure_troubleshooting_section_exists,
    FAMILY_LOG_DIR,
    FAMILY_LOG_FILE
)


class TestGetServerEnvironmentDetails:
    """Tests for get_server_environment_details function."""

    @pytest.mark.timeout(10)
    def test_returns_required_fields(self):
        """Test that the function returns all required environment fields."""
        env_details = get_server_environment_details()
        
        assert 'os' in env_details
        assert 'os_version' in env_details
        assert 'platform' in env_details
        assert 'python_version' in env_details
        assert 'architecture' in env_details
        assert 'hostname' in env_details

    @pytest.mark.timeout(10)
    def test_os_is_string(self):
        """Test that OS is returned as a string."""
        env_details = get_server_environment_details()
        
        assert isinstance(env_details['os'], str)
        assert len(env_details['os']) > 0


class TestFormatMarkdownEntry:
    """Tests for format_markdown_entry function."""

    @pytest.mark.timeout(10)
    def test_format_includes_timestamp(self):
        """Test that formatted entry includes timestamp."""
        entry = format_markdown_entry(
            family_id='test-family-id',
            parent_name='Test Parent',
            email='test@example.com',
            password_data={'hash': 'hash1', 'secondHash': 'hash2', 'secondSalt': 'salt'},
            device_name='Test Device',
            device_model='Test Model',
            time_zone='Europe/Amsterdam',
            server_url='http://localhost:8080',
            locale='en',
            request_id='test-request-id'
        )
        
        assert '## Family Creation Entry' in entry
        assert 'timestamp' in entry.lower()

    @pytest.mark.timeout(10)
    def test_format_includes_input_data(self):
        """Test that formatted entry includes input data."""
        entry = format_markdown_entry(
            family_id='test-family-id',
            parent_name='Test Parent',
            email='test@example.com',
            password_data={'hash': 'hash1', 'secondHash': 'hash2', 'secondSalt': 'salt'},
            device_name='Test Device',
            device_model='Test Model',
            time_zone='Europe/Amsterdam',
            server_url='http://localhost:8080',
            locale='en',
            request_id='test-request-id'
        )
        
        assert 'Test Parent' in entry
        assert 'test@example.com' in entry
        assert 'Test Device' in entry
        assert 'Test Model' in entry
        assert 'Europe/Amsterdam' in entry

    @pytest.mark.timeout(10)
    def test_format_includes_derived_data(self):
        """Test that formatted entry includes derived data."""
        entry = format_markdown_entry(
            family_id='test-family-id',
            parent_name='Test Parent',
            email='test@example.com',
            password_data={'hash': 'hash1', 'secondHash': 'hash2', 'secondSalt': 'salt'},
            device_name='Test Device',
            device_model='Test Model',
            time_zone='Europe/Amsterdam',
            server_url='http://localhost:8080',
            locale='en',
            request_id='test-request-id'
        )
        
        assert 'hash1' in entry
        assert 'hash2' in entry
        assert 'salt' in entry
        assert 'bcrypt' in entry.lower()

    @pytest.mark.timeout(10)
    def test_format_includes_server_environment(self):
        """Test that formatted entry includes server environment details."""
        entry = format_markdown_entry(
            family_id='test-family-id',
            parent_name='Test Parent',
            email='test@example.com',
            password_data={'hash': 'hash1', 'secondHash': 'hash2', 'secondSalt': 'salt'},
            device_name='Test Device',
            device_model='Test Model',
            time_zone='Europe/Amsterdam',
            server_url='http://localhost:8080',
            locale='en',
            request_id='test-request-id'
        )
        
        assert 'Operating System' in entry
        assert 'Python Version' in entry
        assert 'Architecture' in entry

    @pytest.mark.timeout(10)
    def test_format_includes_family_id(self):
        """Test that formatted entry includes family ID."""
        entry = format_markdown_entry(
            family_id='test-family-id',
            parent_name='Test Parent',
            email='test@example.com',
            password_data={'hash': 'hash1', 'secondHash': 'hash2', 'secondSalt': 'salt'},
            device_name='Test Device',
            device_model='Test Model',
            time_zone='Europe/Amsterdam',
            server_url='http://localhost:8080',
            locale='en',
            request_id='test-request-id'
        )
        
        assert 'test-family-id' in entry


class TestLogFileHeader:
    """Tests for get_file_header function."""

    @pytest.mark.timeout(10)
    def test_header_includes_access_restriction_notice(self):
        """Test that header includes access restriction notice."""
        header = get_file_header()
        
        assert 'ACCESS RESTRICTION NOTICE' in header
        assert 'sensitive' in header.lower()
        assert 'DO NOT SHARE' in header

    @pytest.mark.timeout(10)
    def test_header_includes_sensitive_data_warning(self):
        """Test that header warns about sensitive data."""
        header = get_file_header()
        
        assert 'Password hashes' in header
        assert 'Email addresses' in header
        assert 'Device authentication tokens' in header


class TestTroubleshootingSection:
    """Tests for get_troubleshooting_section function."""

    @pytest.mark.timeout(10)
    def test_section_exists(self):
        """Test that troubleshooting section is returned."""
        section = get_troubleshooting_section()
        
        assert '## Troubleshooting Notes' in section
        assert 'Common Issues' in section

    @pytest.mark.timeout(10)
    def test_section_includes_common_issues(self):
        """Test that troubleshooting section includes common issues."""
        section = get_troubleshooting_section()
        
        assert 'Family ID Not Found' in section
        assert 'Password Hash Mismatch' in section
        assert 'Email Verification Issues' in section


class TestLogFamilyCreation:
    """Tests for log_family_creation function."""

    @pytest.mark.timeout(10)
    def test_creates_log_file_if_not_exists(self, tmp_path):
        """Test that log file is created if it doesn't exist."""
        # Use a temporary directory for testing
        with patch('utils.family_logging.FAMILY_LOG_DIR', str(tmp_path)):
            result = log_family_creation(
                family_id='test-family-id',
                parent_name='Test Parent',
                email='test@example.com',
                password_data={'hash': 'hash1', 'secondHash': 'hash2', 'secondSalt': 'salt'},
                device_name='Test Device',
                device_model='Test Model',
                time_zone='Europe/Amsterdam',
                server_url='http://localhost:8080',
                locale='en',
                request_id='test-request-id'
            )
            
            assert result is True
            
            # Check that file was created
            log_file = tmp_path / 'KeyFamilyData.md'
            assert log_file.exists()

    @pytest.mark.timeout(10)
    def test_appends_to_existing_file(self, tmp_path):
        """Test that new entries are appended to existing file."""
        # Create an existing log file
        log_file = tmp_path / 'KeyFamilyData.md'
        log_file.write_text('# Existing content\n', encoding='utf-8')
        
        with patch('utils.family_logging.FAMILY_LOG_DIR', str(tmp_path)):
            result = log_family_creation(
                family_id='test-family-id',
                parent_name='Test Parent',
                email='test@example.com',
                password_data={'hash': 'hash1', 'secondHash': 'hash2', 'secondSalt': 'salt'},
                device_name='Test Device',
                device_model='Test Model',
                time_zone='Europe/Amsterdam',
                server_url='http://localhost:8080',
                locale='en',
                request_id='test-request-id'
            )
            
            assert result is True
            
            # Check that content was appended
            content = log_file.read_text(encoding='utf-8')
            assert 'Existing content' in content
            assert 'test-family-id' in content

    @pytest.mark.timeout(10)
    def test_includes_all_required_data(self, tmp_path):
        """Test that log entry includes all required data."""
        with patch('utils.family_logging.FAMILY_LOG_DIR', str(tmp_path)):
            result = log_family_creation(
                family_id='test-family-id',
                parent_name='Test Parent',
                email='test@example.com',
                password_data={'hash': 'hash1', 'secondHash': 'hash2', 'secondSalt': 'salt'},
                device_name='Test Device',
                device_model='Test Model',
                time_zone='Europe/Amsterdam',
                server_url='http://localhost:8080',
                locale='en',
                request_id='test-request-id'
            )
            
            assert result is True
            
            # Check that all required data is in the log
            content = (tmp_path / 'KeyFamilyData.md').read_text(encoding='utf-8')
            assert 'test-family-id' in content
            assert 'Test Parent' in content
            assert 'test@example.com' in content
            assert 'hash1' in content
            assert 'hash2' in content
            assert 'salt' in content
            assert 'Test Device' in content
            assert 'Test Model' in content
            assert 'Europe/Amsterdam' in content
            assert 'http://localhost:8080' in content

    @pytest.mark.timeout(10)
    def test_handles_missing_optional_fields(self, tmp_path):
        """Test that function handles missing optional fields gracefully."""
        with patch('utils.family_logging.FAMILY_LOG_DIR', str(tmp_path)):
            result = log_family_creation(
                family_id='test-family-id',
                parent_name='Test Parent',
                email='test@example.com',
                password_data={'hash': 'hash1', 'secondHash': 'hash2', 'secondSalt': 'salt'},
                device_name='Test Device',
                device_model='Test Model',
                time_zone='Europe/Amsterdam',
                server_url='http://localhost:8080',
                locale=None,  # Missing optional field
                request_id=None  # Missing optional field
            )
            
            assert result is True


class TestEnsureTroubleshootingSectionExists:
    """Tests for ensure_troubleshooting_section_exists function."""

    @pytest.mark.timeout(10)
    def test_creates_file_with_troubleshooting_section(self, tmp_path):
        """Test that function creates file with troubleshooting section if it doesn't exist."""
        with patch('utils.family_logging.FAMILY_LOG_DIR', str(tmp_path)):
            result = ensure_troubleshooting_section_exists()
            
            assert result is True
            
            log_file = tmp_path / 'KeyFamilyData.md'
            assert log_file.exists()
            
            content = log_file.read_text(encoding='utf-8')
            assert '## Troubleshooting Notes' in content

    @pytest.mark.timeout(10)
    def test_appends_troubleshooting_section_if_missing(self, tmp_path):
        """Test that function appends troubleshooting section if missing from existing file."""
        # Create a file without troubleshooting section
        log_file = tmp_path / 'KeyFamilyData.md'
        log_file.write_text('# Some content\n')
        
        with patch('utils.family_logging.FAMILY_LOG_DIR', str(tmp_path)):
            result = ensure_troubleshooting_section_exists()
            
            assert result is True
            
            content = log_file.read_text()
            assert '## Troubleshooting Notes' in content

    @pytest.mark.timeout(10)
    def test_does_not_duplicate_troubleshooting_section(self, tmp_path):
        """Test that function doesn't duplicate troubleshooting section if it already exists."""
        # Create a file with troubleshooting section
        log_file = tmp_path / 'KeyFamilyData.md'
        log_file.write_text('# Some content\n## Troubleshooting Notes\n')
        
        with patch('utils.family_logging.FAMILY_LOG_DIR', str(tmp_path)):
            result = ensure_troubleshooting_section_exists()
            
            assert result is True
            
            content = log_file.read_text()
            # Should only have one troubleshooting section
            assert content.count('## Troubleshooting Notes') == 1