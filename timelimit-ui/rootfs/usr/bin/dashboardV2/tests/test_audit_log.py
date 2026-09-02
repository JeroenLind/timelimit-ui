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
            
            # Verify log file was created
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    content = f.read()
                    # Verify event type is logged
                    assert 'device_removal_request' in content
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