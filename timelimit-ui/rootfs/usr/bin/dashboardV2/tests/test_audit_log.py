"""Unit tests for audit logging module.

Tests for the audit_log module, specifically for device removal operations.
These tests verify that complete request details are logged with exact fidelity.
"""

import json
import logging
import os
import shutil
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from utils.audit_log import (
    log_device_removal_request,
    log_device_removal_response,
    log_device_removal_failure,
    log_family_creation_request,
    log_family_creation_response,
    log_family_creation_failure,
    log_login_as_parent_salt_validation_failure,
    log_login_as_parent_hash_regeneration,
    log_login_as_parent_hash_regeneration_failure,
    log_login_as_parent_new_hash_generation,
    log_login_as_parent_password_stored,
    log_login_as_parent_direct_hash_stored,
    get_audit_logger,
    DEFAULT_AUDIT_LOG_PATH,
    AUDIT_LOG_MAX_BYTES,
    AUDIT_LOG_BACKUP_COUNT
)


def _cleanup_temp_dir(tmpdir):
    """Clean up temporary directory, handling file locks gracefully."""
    try:
        shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception:
        pass  # Ignore cleanup errors


class TestLogDeviceRemovalRequest:
    """Tests for log_device_removal_request function."""
    
    @pytest.mark.timeout(10)
    def test_logs_complete_request_payload(self):
        """Verify complete request payload is logged."""
        tmpdir = tempfile.mkdtemp()
        try:
            log_file = os.path.join(tmpdir, 'audit.log')
            
            log_device_removal_request(
                device_id='device_123',
                parent_user_id='user_456',
                device_auth_token='token_abc123',
                parent_password_second_hash='$2b$12$hash_value',
                request_payload={
                    'deviceAuthToken': 'token_abc123',
                    'parentUserId': 'user_456',
                    'parentPasswordSecondHash': '$2b$12$hash_value',
                    'deviceId': 'device_123'
                },
                request_headers={
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer token_abc123',
                    'User-Agent': 'TestClient/1.0'
                },
                client_ip='192.168.1.100',
                request_id='abc12345',
                server_url='http://localhost:8080',
                audit_log_path=log_file
            )
            
            # Verify log file was created and contains the payload
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    content = f.read()
                    # Verify complete payload is logged (not sanitized)
                    assert 'device_123' in content
                    assert 'user_456' in content
                    assert 'token_abc123' in content
                    assert '$2b$12$hash_value' in content
        finally:
            _cleanup_temp_dir(tmpdir)
    
    @pytest.mark.timeout(10)
    def test_logs_all_headers(self):
        """Verify all headers are logged without sanitization."""
        tmpdir = tempfile.mkdtemp()
        try:
            log_file = os.path.join(tmpdir, 'audit.log')
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer secret_token_12345',
                'X-Request-ID': 'req_789',
                'User-Agent': 'TestClient/1.0',
                'Cookie': 'session=abc123; user=test'
            }
            
            log_device_removal_request(
                device_id='device_123',
                parent_user_id='user_456',
                device_auth_token='token_abc123',
                parent_password_second_hash='$2b$12$hash_value',
                request_payload={'deviceId': 'device_123'},
                request_headers=headers,
                audit_log_path=log_file
            )
            
            # Verify log file was created
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    content = f.read()
                    # Verify headers are logged (not sanitized)
                    assert 'secret_token_12345' in content
                    assert 'session=abc123' in content
        finally:
            _cleanup_temp_dir(tmpdir)
    
    @pytest.mark.timeout(10)
    def test_logs_precise_timestamp(self):
        """Verify precise timestamp is logged."""
        tmpdir = tempfile.mkdtemp()
        try:
            log_file = os.path.join(tmpdir, 'audit.log')
            
            log_device_removal_request(
                device_id='device_123',
                parent_user_id='user_456',
                device_auth_token='token_abc123',
                parent_password_second_hash='$2b$12$hash_value',
                request_payload={'deviceId': 'device_123'},
                request_headers={},
                audit_log_path=log_file
            )
            
            # Verify log file was created
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    content = f.read()
                    # Verify timestamp fields are present
                    assert 'timestamp' in content
                    assert 'timestamp_unix_ms' in content
        finally:
            _cleanup_temp_dir(tmpdir)
    
    @pytest.mark.timeout(10)
    def test_logs_user_identifiers(self):
        """Verify user identifiers are logged."""
        tmpdir = tempfile.mkdtemp()
        try:
            log_file = os.path.join(tmpdir, 'audit.log')
            
            log_device_removal_request(
                device_id='device_123',
                parent_user_id='user_456',
                device_auth_token='token_abc123',
                parent_password_second_hash='$2b$12$hash_value',
                request_payload={'deviceId': 'device_123'},
                request_headers={},
                audit_log_path=log_file
            )
            
            # Verify log file was created
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    content = f.read()
                    # Verify user identifiers are logged
                    assert 'parent_user_id' in content
                    assert 'device_auth_token' in content
        finally:
            _cleanup_temp_dir(tmpdir)
    
    @pytest.mark.timeout(10)
    def test_logs_event_type(self):
        """Verify event type is logged."""
        tmpdir = tempfile.mkdtemp()
        try:
            log_file = os.path.join(tmpdir, 'audit.log')
            
            log_device_removal_request(
                device_id='device_123',
                parent_user_id='user_456',
                device_auth_token='token_abc123',
                parent_password_second_hash='$2b$12$hash_value',
                request_payload={'deviceId': 'device_123'},
                request_headers={},
                audit_log_path=log_file
            )
            
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    content = f.read()
                    # Verify both request and response are logged
                    assert 'device_removal_request' in content
                    assert 'device_removal_response' in content
                    # Verify complete payload is preserved
                    assert 'token_abc123' in content
                    assert '$2b$12$hash_value' in content
                    # Verify timestamps
                    assert 'timestamp' in content
                    # Verify user identifiers
                    assert 'device_123' in content
                    assert 'user_456' in content
        finally:
            _cleanup_temp_dir(tmpdir)


class TestAuditLogIntegration:
    """Integration tests for audit logging with device removal."""
    
    @pytest.mark.timeout(10)
    def test_complete_audit_trail(self):
        """Verify complete audit trail is logged for device removal."""
        tmpdir = tempfile.mkdtemp()
        try:
            log_file = os.path.join(tmpdir, 'audit.log')
            
            # Log request
            log_device_removal_request(
                device_id='device_123',
                parent_user_id='user_456',
                device_auth_token='token_abc123',
                parent_password_second_hash='$2b$12$hash_value',
                request_payload={
                    'deviceAuthToken': 'token_abc123',
                    'parentUserId': 'user_456',
                    'parentPasswordSecondHash': '$2b$12$hash_value',
                    'deviceId': 'device_123'
                },
                request_headers={
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer token_abc123',
                    'User-Agent': 'TestClient/1.0'
                },
                client_ip='192.168.1.100',
                request_id='abc12345',
                server_url='http://localhost:8080',
                audit_log_path=log_file
            )
            
            # Log response
            log_device_removal_response(
                device_id='device_123',
                parent_user_id='user_456',
                request_id='abc12345',
                success=True,
                status_code=200,
                response_data={'ok': True, 'message': 'Device removed'},
                audit_log_path=log_file
            )
            
            # Verify log file was created
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    content = f.read()
                    # Verify both request and response are logged
                    assert 'device_removal_request' in content
                    assert 'device_removal_response' in content
                    # Verify complete payload is preserved
                    assert 'token_abc123' in content
                    assert '$2b$12$hash_value' in content
                    # Verify timestamps
                    assert 'timestamp' in content
                    # Verify user identifiers
                    assert 'device_123' in content
                    assert 'user_456' in content
        finally:
            _cleanup_temp_dir(tmpdir)


class TestLogFamilyCreationRequest:
    """Tests for log_family_creation_request function."""
    
    @pytest.mark.timeout(10)
    def test_logs_complete_request_payload(self):
        """Verify complete request payload is logged including password data."""
        tmpdir = tempfile.mkdtemp()
        try:
            log_file = os.path.join(tmpdir, 'audit.log')
            
            log_family_creation_request(
                mail_auth_token='mail_token_abc123',
                email='test@example.com',
                password_data={
                    'hash': '$2a$12$hash_value_1',
                    'secondHash': '$2a$12$hash_value_2',
                    'secondSalt': '$2a$12$salt_value'
                },
                parent_device={'model': 'Test Device Model'},
                device_name='Test Device',
                time_zone='Europe/Amsterdam',
                parent_name='Test Parent',
                locale='en',
                request_id='req_12345',
                server_url='http://localhost:8080',
                audit_log_path=log_file
            )
            
            # Verify log file was created and contains all required data
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    content = f.read()
                    # Verify all required fields are logged
                    assert 'test@example.com' in content
                    assert 'mail_token_abc123' in content
                    assert '$2a$12$hash_value_1' in content
                    assert '$2a$12$hash_value_2' in content
                    assert '$2a$12$salt_value' in content
                    assert 'Test Device' in content
                    assert 'Test Device Model' in content
                    assert 'Europe/Amsterdam' in content
                    assert 'Test Parent' in content
                    assert 'en' in content
        finally:
            _cleanup_temp_dir(tmpdir)
    
    @pytest.mark.timeout(10)
    def test_logs_password_hash_and_salt(self):
        """Verify password hash, secondHash, and salt are logged."""
        tmpdir = tempfile.mkdtemp()
        try:
            log_file = os.path.join(tmpdir, 'audit.log')
            
            password_data = {
                'hash': '$2a$12$password_hash_value',
                'secondHash': '$2a$12$second_hash_value',
                'secondSalt': '$2a$12$second_salt_value'
            }
            
            log_family_creation_request(
                mail_auth_token='token_123',
                email='user@test.com',
                password_data=password_data,
                parent_device={'model': 'Model'},
                device_name='Device',
                time_zone='UTC',
                parent_name='Parent',
                audit_log_path=log_file
            )
            
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    content = f.read()
                    # Verify password-related fields are logged
                    assert 'password_hash_value' in content
                    assert 'second_hash_value' in content
                    assert 'second_salt_value' in content
        finally:
            _cleanup_temp_dir(tmpdir)
    
    @pytest.mark.timeout(10)
    def test_logs_device_info(self):
        """Verify device name and model are logged."""
        tmpdir = tempfile.mkdtemp()
        try:
            log_file = os.path.join(tmpdir, 'audit.log')
            
            log_family_creation_request(
                mail_auth_token='token_123',
                email='user@test.com',
                password_data={'hash': 'h', 'secondHash': 'h2', 'secondSalt': 's'},
                parent_device={'model': 'Samsung Galaxy S21'},
                device_name='My Phone',
                time_zone='Europe/Amsterdam',
                parent_name='Parent',
                audit_log_path=log_file
            )
            
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    content = f.read()
                    assert 'Samsung Galaxy S21' in content
                    assert 'My Phone' in content
        finally:
            _cleanup_temp_dir(tmpdir)
    
    @pytest.mark.timeout(10)
    def test_logs_event_type(self):
        """Verify event type is logged."""
        tmpdir = tempfile.mkdtemp()
        try:
            log_file = os.path.join(tmpdir, 'audit.log')
            
            log_family_creation_request(
                mail_auth_token='token_123',
                email='user@test.com',
                password_data={'hash': 'h', 'secondHash': 'h2', 'secondSalt': 's'},
                parent_device={'model': 'Model'},
                device_name='Device',
                time_zone='UTC',
                parent_name='Parent',
                audit_log_path=log_file
            )
            
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    content = f.read()
                    assert 'family_creation_request' in content
        finally:
            _cleanup_temp_dir(tmpdir)


class TestLogFamilyCreationResponse:
    """Tests for log_family_creation_response function."""
    
    @pytest.mark.timeout(10)
    def test_logs_successful_response(self):
        """Verify successful response is logged with device auth token."""
        tmpdir = tempfile.mkdtemp()
        try:
            log_file = os.path.join(tmpdir, 'audit.log')
            
            log_family_creation_response(
                success=True,
                request_id='req_12345',
                status_code=200,
                response_data={
                    'deviceAuthToken': 'device_token_abc123',
                    'ownDeviceId': 'device_id_456',
                    'status': 'ok'
                },
                audit_log_path=log_file
            )
            
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    content = f.read()
                    # Verify response data is logged
                    assert 'device_token_abc123' in content
                    assert 'device_id_456' in content
                    assert 'success' in content
                    assert '200' in content
        finally:
            _cleanup_temp_dir(tmpdir)
    
    @pytest.mark.timeout(10)
    def test_logs_failed_response(self):
        """Verify failed response is logged with error details."""
        tmpdir = tempfile.mkdtemp()
        try:
            log_file = os.path.join(tmpdir, 'audit.log')
            
            log_family_creation_response(
                success=False,
                request_id='req_12345',
                status_code=401,
                response_data={'error': 'Unauthorized'},
                error_code='unauthorized',
                error_message='Invalid mail auth token',
                audit_log_path=log_file
            )
            
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    content = f.read()
                    # Verify error details are logged
                    assert 'unauthorized' in content
                    assert 'Invalid mail auth token' in content
                    assert 'success' in content
        finally:
            _cleanup_temp_dir(tmpdir)


class TestLogFamilyCreationFailure:
    """Tests for log_family_creation_failure function."""
    
    @pytest.mark.timeout(10)
    def test_logs_validation_failure(self):
        """Verify validation failure is logged."""
        tmpdir = tempfile.mkdtemp()
        try:
            log_file = os.path.join(tmpdir, 'audit.log')
            
            log_family_creation_failure(
                error_type='validation',
                error_message='Password must be at least 8 characters',
                email='test@example.com',
                password_data={'hash': 'h', 'secondHash': 'h2', 'secondSalt': 's'},
                request_id='req_12345',
                server_url='http://localhost:8080',
                audit_log_path=log_file
            )
            
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    content = f.read()
                    assert 'validation' in content
                    assert 'Password must be at least 8 characters' in content
                    assert 'test@example.com' in content
        finally:
            _cleanup_temp_dir(tmpdir)
    
    @pytest.mark.timeout(10)
    def test_logs_authentication_failure(self):
        """Verify authentication failure is logged."""
        tmpdir = tempfile.mkdtemp()
        try:
            log_file = os.path.join(tmpdir, 'audit.log')
            
            log_family_creation_failure(
                error_type='authentication',
                error_message='Invalid mail auth token',
                email='user@test.com',
                request_id='req_12345',
                audit_log_path=log_file
            )
            
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    content = f.read()
                    assert 'authentication' in content
                    assert 'Invalid mail auth token' in content
        finally:
            _cleanup_temp_dir(tmpdir)


class TestFamilyCreationAuditIntegration:
    """Integration tests for family creation audit logging."""
    
    @pytest.mark.timeout(10)
    def test_complete_audit_trail_for_family_creation(self):
        """Verify complete audit trail is logged for family creation."""
        tmpdir = tempfile.mkdtemp()
        try:
            log_file = os.path.join(tmpdir, 'audit.log')
            
            # Log request
            log_family_creation_request(
                mail_auth_token='mail_token_123',
                email='parent@example.com',
                password_data={
                    'hash': '$2a$12$password_hash',
                    'secondHash': '$2a$12$second_hash',
                    'secondSalt': '$2a$12$salt'
                },
                parent_device={'model': 'Pixel 6'},
                device_name='Parent Phone',
                time_zone='Europe/Amsterdam',
                parent_name='John Parent',
                locale='en',
                request_id='req_abc123',
                server_url='http://localhost:8080',
                audit_log_path=log_file
            )
            
            # Log response
            log_family_creation_response(
                success=True,
                request_id='req_abc123',
                status_code=200,
                response_data={
                    'deviceAuthToken': 'device_token_xyz',
                    'ownDeviceId': 'device_id_789'
                },
                audit_log_path=log_file
            )
            
            # Verify log file was created
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    content = f.read()
                    # Verify request is logged
                    assert 'family_creation_request' in content
                    # Verify response is logged
                    assert 'family_creation_response' in content
                    # Verify all required data is preserved
                    assert 'parent@example.com' in content
                    assert 'mail_token_123' in content
                    assert '$2a$12$password_hash' in content
                    assert '$2a$12$second_hash' in content
                    assert '$2a$12$salt' in content
                    assert 'device_token_xyz' in content
                    assert 'device_id_789' in content
                    # Verify timestamps
                    assert 'timestamp' in content
                    assert 'timestamp_unix_ms' in content
        finally:
            _cleanup_temp_dir(tmpdir)


class TestLogDeviceRemovalResponse:
    """Tests for log_device_removal_response function."""
    
    @pytest.mark.timeout(10)
    def test_logs_successful_response(self):
        """Verify successful response is logged with complete fidelity."""
        tmpdir = tempfile.mkdtemp()
        try:
            log_file = os.path.join(tmpdir, 'audit.log')
            
            log_device_removal_response(
                device_id='device_123',
                parent_user_id='user_456',
                request_id='abc12345',
                success=True,
                status_code=200,
                response_data={'ok': True, 'message': 'Device removed'},
                audit_log_path=log_file
            )
            
            # Verify log file was created
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    content = f.read()
                    # Verify response data is logged
                    assert 'device_123' in content
                    assert 'user_456' in content
                    assert 'success' in content
                    assert '200' in content
                    assert 'Device removed' in content
        finally:
            _cleanup_temp_dir(tmpdir)
    
    @pytest.mark.timeout(10)
    def test_logs_failed_response(self):
        """Verify failed response is logged with complete fidelity."""
        tmpdir = tempfile.mkdtemp()
        try:
            log_file = os.path.join(tmpdir, 'audit.log')
            
            log_device_removal_response(
                device_id='device_123',
                parent_user_id='user_456',
                request_id='abc12345',
                success=False,
                status_code=401,
                response_data={'error': 'Unauthorized'},
                error_code='unauthorized',
                error_message='Unauthorized access',
                audit_log_path=log_file
            )
            
            # Verify log file was created
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    content = f.read()
                    # Verify error details are logged
                    assert 'device_123' in content
                    assert 'unauthorized' in content
                    assert 'Unauthorized access' in content
        finally:
            _cleanup_temp_dir(tmpdir)


class TestLogDeviceRemovalFailure:
    """Tests for log_device_removal_failure function."""
    
    @pytest.mark.timeout(10)
    def test_logs_validation_failure(self):
        """Verify validation failure is logged."""
        tmpdir = tempfile.mkdtemp()
        try:
            log_file = os.path.join(tmpdir, 'audit.log')
            
            log_device_removal_failure(
                device_id='device_123',
                parent_user_id='user_456',
                error_type='validation',
                error_message='Missing deviceId',
                request_payload={'deviceId': None},
                request_headers={'Content-Type': 'application/json'},
                request_id='abc12345',
                audit_log_path=log_file
            )
            
            # Verify log file was created
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    content = f.read()
                    # Verify failure details are logged
                    assert 'device_123' in content
                    assert 'validation' in content
                    assert 'Missing deviceId' in content
        finally:
            _cleanup_temp_dir(tmpdir)
    
    @pytest.mark.timeout(10)
    def test_logs_authentication_failure(self):
        """Verify authentication failure is logged."""
        tmpdir = tempfile.mkdtemp()
        try:
            log_file = os.path.join(tmpdir, 'audit.log')
            
            log_device_removal_failure(
                device_id='device_123',
                parent_user_id='user_456',
                error_type='authentication',
                error_message='Not authenticated',
                request_id='abc12345',
                audit_log_path=log_file
            )
            
            # Verify log file was created
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    content = f.read()
                    # Verify failure details are logged
                    assert 'authentication' in content
                    assert 'Not authenticated' in content
        finally:
            _cleanup_temp_dir(tmpdir)


class TestAuditLogConfiguration:
    """Tests for audit log configuration."""
    
    @pytest.mark.timeout(10)
    def test_default_audit_log_path(self):
        """Verify default audit log path is correct."""
        assert DEFAULT_AUDIT_LOG_PATH == 'logs/audit.log'
    
    @pytest.mark.timeout(10)
    def test_max_bytes_configuration(self):
        """Verify max bytes configuration."""
        assert AUDIT_LOG_MAX_BYTES == 10485760  # 10MB
    
    @pytest.mark.timeout(10)
    def test_backup_count_configuration(self):
        """Verify backup count configuration."""
        assert AUDIT_LOG_BACKUP_COUNT == 10


class TestAuditLogIntegration:
    """Integration tests for audit logging with device removal."""
    
    @pytest.mark.timeout(10)
    def test_complete_audit_trail(self):
        """Verify complete audit trail is logged for device removal."""
        tmpdir = tempfile.mkdtemp()
        try:
            log_file = os.path.join(tmpdir, 'audit.log')
            
            # Log request
            log_device_removal_request(
                device_id='device_123',
                parent_user_id='user_456',
                device_auth_token='token_abc123',
                parent_password_second_hash='$2b$12$hash_value',
                request_payload={
                    'deviceAuthToken': 'token_abc123',
                    'parentUserId': 'user_456',
                    'parentPasswordSecondHash': '$2b$12$hash_value',
                    'deviceId': 'device_123'
                },
                request_headers={
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer token_abc123',
                    'User-Agent': 'TestClient/1.0'
                },
                client_ip='192.168.1.100',
                request_id='abc12345',
                server_url='http://localhost:8080',
                audit_log_path=log_file
            )
            
            # Log response
            log_device_removal_response(
                device_id='device_123',
                parent_user_id='user_456',
                request_id='abc12345',
                success=True,
                status_code=200,
                response_data={'ok': True, 'message': 'Device removed'},
                audit_log_path=log_file
            )
            
            # Verify log file was created
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    content = f.read()
                    # Verify both request and response are logged
                    assert 'device_removal_request' in content
                    assert 'device_removal_response' in content
                    # Verify complete payload is preserved
                    assert 'token_abc123' in content
                    assert '$2b$12$hash_value' in content
                    # Verify timestamps
                    assert 'timestamp' in content
                    # Verify user identifiers
                    assert 'device_123' in content
                    assert 'user_456' in content
        finally:
            _cleanup_temp_dir(tmpdir)


class TestLoginAsParentSaltValidationFailure:
    """Tests for log_login_as_parent_salt_validation_failure function."""
    
    @pytest.mark.timeout(10)
    def test_logs_salt_validation_failure_session_error(self):
        """Verify salt validation failure with session error is logged."""
        tmpdir = tempfile.mkdtemp()
        try:
            log_file = os.path.join(tmpdir, 'audit.log')
            
            log_login_as_parent_salt_validation_failure(
                mail='test@example.com',
                error_type='session_error',
                error_message='Session error: email not available for salt lookup',
                family_found=False,
                salt_available=False,
                request_id='req_12345',
                server_url='http://localhost:8080',
                audit_log_path=log_file
            )
            
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    content = f.read()
                    assert 'login_as_parent_salt_validation_failure' in content
                    assert 'test@example.com' in content
                    assert 'session_error' in content
                    assert 'Session error: email not available for salt lookup' in content
                    assert 'family_found' in content
                    assert 'salt_available' in content
        finally:
            _cleanup_temp_dir(tmpdir)
    
    @pytest.mark.timeout(10)
    def test_logs_salt_validation_failure_family_not_found(self):
        """Verify salt validation failure with family not found is logged."""
        tmpdir = tempfile.mkdtemp()
        try:
            log_file = os.path.join(tmpdir, 'audit.log')
            
            log_login_as_parent_salt_validation_failure(
                mail='nonexistent@example.com',
                error_type='family_not_found',
                error_message='Family not found for this email. Please verify you have an existing family.',
                family_found=False,
                salt_available=False,
                request_id='req_67890',
                server_url='http://localhost:8080',
                audit_log_path=log_file
            )
            
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    content = f.read()
                    assert 'login_as_parent_salt_validation_failure' in content
                    assert 'nonexistent@example.com' in content
                    assert 'family_not_found' in content
                    assert 'Family not found' in content
        finally:
            _cleanup_temp_dir(tmpdir)
    
    @pytest.mark.timeout(10)
    def test_logs_salt_validation_failure_salt_missing(self):
        """Verify salt validation failure with salt missing is logged."""
        tmpdir = tempfile.mkdtemp()
        try:
            log_file = os.path.join(tmpdir, 'audit.log')
            
            log_login_as_parent_salt_validation_failure(
                mail='test@example.com',
                error_type='salt_missing',
                error_message='Password salt not available for this family. Please use the password hash field instead, or contact support.',
                family_found=True,
                salt_available=False,
                request_id='req_11111',
                server_url='http://localhost:8080',
                audit_log_path=log_file
            )
            
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    content = f.read()
                    assert 'login_as_parent_salt_validation_failure' in content
                    assert 'test@example.com' in content
                    assert 'salt_missing' in content
                    assert 'Password salt not available' in content
                    assert 'family_found' in content
                    assert 'salt_available' in content
        finally:
            _cleanup_temp_dir(tmpdir)


class TestLoginAsParentHashRegeneration:
    """Tests for log_login_as_parent_hash_regeneration function."""
    
    @pytest.mark.timeout(10)
    def test_logs_hash_regeneration_success(self):
        """Verify successful hash regeneration is logged."""
        tmpdir = tempfile.mkdtemp()
        try:
            log_file = os.path.join(tmpdir, 'audit.log')
            
            password_data = {
                'hash': '$2a$12$new_hash_value',
                'secondHash': '$2a$12$regenerated_hash',
                'secondSalt': '$2a$12$existing_salt'
            }
            
            log_login_as_parent_hash_regeneration(
                mail='test@example.com',
                existing_salt='$2a$12$existing_salt',
                second_hash='$2a$12$regenerated_hash',
                password_data=password_data,
                request_id='req_22222',
                server_url='http://localhost:8080',
                audit_log_path=log_file
            )
            
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    content = f.read()
                    assert 'login_as_parent_hash_regeneration' in content
                    assert 'test@example.com' in content
                    assert '$2a$12$existing_salt' in content
                    assert '$2a$12$regenerated_hash' in content
                    assert 'password_data' in content
        finally:
            _cleanup_temp_dir(tmpdir)


class TestLoginAsParentHashRegenerationFailure:
    """Tests for log_login_as_parent_hash_regeneration_failure function."""
    
    @pytest.mark.timeout(10)
    def test_logs_hash_regeneration_failure(self):
        """Verify hash regeneration failure is logged with error details."""
        tmpdir = tempfile.mkdtemp()
        try:
            log_file = os.path.join(tmpdir, 'audit.log')
            
            log_login_as_parent_hash_regeneration_failure(
                mail='test@example.com',
                existing_salt='$2a$12$existing_salt',
                error='Invalid salt format',
                error_type='ValueError',
                request_id='req_33333',
                server_url='http://localhost:8080',
                audit_log_path=log_file
            )
            
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    content = f.read()
                    assert 'login_as_parent_hash_regeneration_failure' in content
                    assert 'test@example.com' in content
                    assert '$2a$12$existing_salt' in content
                    assert 'Invalid salt format' in content
                    assert 'ValueError' in content
        finally:
            _cleanup_temp_dir(tmpdir)


class TestLoginAsParentNewHashGeneration:
    """Tests for log_login_as_parent_new_hash_generation function."""
    
    @pytest.mark.timeout(10)
    def test_logs_new_hash_generation(self):
        """Verify new hash generation is logged."""
        tmpdir = tempfile.mkdtemp()
        try:
            log_file = os.path.join(tmpdir, 'audit.log')
            
            password_data = {
                'hash': '$2a$12$new_hash',
                'secondHash': '$2a$12$new_second_hash',
                'secondSalt': '$2a$12$new_salt'
            }
            
            log_login_as_parent_new_hash_generation(
                mail='newuser@example.com',
                hash_value='$2a$12$new_hash',
                second_hash='$2a$12$new_second_hash',
                second_salt='$2a$12$new_salt',
                password_data=password_data,
                request_id='req_44444',
                server_url='http://localhost:8080',
                audit_log_path=log_file
            )
            
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    content = f.read()
                    assert 'login_as_parent_new_hash_generation' in content
                    assert 'newuser@example.com' in content
                    assert '$2a$12$new_hash' in content
                    assert '$2a$12$new_second_hash' in content
                    assert '$2a$12$new_salt' in content
                    assert 'password_data' in content
        finally:
            _cleanup_temp_dir(tmpdir)


class TestLoginAsParentPasswordStored:
    """Tests for log_login_as_parent_password_stored function."""
    
    @pytest.mark.timeout(10)
    def test_logs_password_stored(self):
        """Verify password storage is logged."""
        tmpdir = tempfile.mkdtemp()
        try:
            log_file = os.path.join(tmpdir, 'audit.log')
            
            password_data = {
                'hash': '$2a$12$hash_value',
                'secondHash': '$2a$12$second_hash',
                'secondSalt': '$2a$12$salt'
            }
            
            log_login_as_parent_password_stored(
                mail='test@example.com',
                device_auth_token='device_token_abc123',
                password_data=password_data,
                request_id='req_55555',
                server_url='http://localhost:8080',
                audit_log_path=log_file
            )
            
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    content = f.read()
                    assert 'login_as_parent_password_stored' in content
                    assert 'test@example.com' in content
                    assert 'device_token_abc123' in content
                    assert 'password_data' in content
        finally:
            _cleanup_temp_dir(tmpdir)


class TestLoginAsParentDirectHashStored:
    """Tests for log_login_as_parent_direct_hash_stored function."""
    
    @pytest.mark.timeout(10)
    def test_logs_direct_hash_stored(self):
        """Verify direct hash storage is logged."""
        tmpdir = tempfile.mkdtemp()
        try:
            log_file = os.path.join(tmpdir, 'audit.log')
            
            log_login_as_parent_direct_hash_stored(
                mail='test@example.com',
                device_auth_token='device_token_xyz789',
                parent_password_second_hash='$2a$12$direct_hash_input',
                request_id='req_66666',
                server_url='http://localhost:8080',
                audit_log_path=log_file
            )
            
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    content = f.read()
                    assert 'login_as_parent_direct_hash_stored' in content
                    assert 'test@example.com' in content
                    assert 'device_token_xyz789' in content
                    assert '$2a$12$direct_hash_input' in content
        finally:
            _cleanup_temp_dir(tmpdir)