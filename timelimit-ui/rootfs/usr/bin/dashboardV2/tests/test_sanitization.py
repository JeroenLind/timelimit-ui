"""Unit tests for sensitive data sanitization.

Tests for sanitize_dict, sanitize_processor, and SENSITIVE_KEYS.
"""

import json
import os
import tempfile
from unittest.mock import patch

import pytest
import structlog

from utils.sanitization import (
    SENSITIVE_KEYS,
    sanitize_dict,
    sanitize_processor,
    is_sensitive_key,
    add_sensitive_keys,
    remove_sensitive_keys,
)


class TestSensitiveKeysConstant:
    """Tests for SENSITIVE_KEYS constant."""

    def test_sensitive_keys_defined(self):
        """Verify SENSITIVE_KEYS is defined and contains expected keys."""
        assert SENSITIVE_KEYS is not None
        assert isinstance(SENSITIVE_KEYS, set)
        # Note: 'password' is NOT in SENSITIVE_KEYS for audit logging purposes
        assert 'token' in SENSITIVE_KEYS
        assert 'secret_key' in SENSITIVE_KEYS

    def test_sensitive_keys_case_insensitive(self):
        """Verify SENSITIVE_KEYS matching is case-insensitive."""
        # Test various case variations
        assert is_sensitive_key('TOKEN')
        assert is_sensitive_key('Token')
        assert is_sensitive_key('SECRET_KEY')
        assert is_sensitive_key('secret_key')

    def test_sensitive_keys_contains_common_keys(self):
        """Verify SENSITIVE_KEYS contains common sensitive key patterns."""
        expected_keys = [
            'token', 'secret_key', 'api_key',
            'auth_token', 'private_key', 'session', 'session_id'
        ]
        for key in expected_keys:
            assert is_sensitive_key(key), f"Key '{key}' should be sensitive"

    def test_password_not_sensitive(self):
        """Verify 'password' is NOT in SENSITIVE_KEYS (for audit logging)."""
        assert is_sensitive_key('password') is False
        assert is_sensitive_key('PASSWORD') is False
        assert is_sensitive_key('hash') is False
        assert is_sensitive_key('secondHash') is False
        assert is_sensitive_key('secondSalt') is False


class TestIsSensitiveKey:
    """Tests for is_sensitive_key function."""

    def test_token_is_sensitive(self):
        """Verify 'token' is detected as sensitive."""
        assert is_sensitive_key('token') is True

    def test_secret_key_is_sensitive(self):
        """Verify 'secret_key' is detected as sensitive."""
        assert is_sensitive_key('secret_key') is True

    def test_non_sensitive_key(self):
        """Verify non-sensitive keys return False."""
        assert is_sensitive_key('username') is False
        assert is_sensitive_key('email') is False
        assert is_sensitive_key('server_url') is False
        assert is_sensitive_key('password') is False
        assert is_sensitive_key('hash') is False

    def test_case_insensitive_matching(self):
        """Verify matching is case-insensitive."""
        assert is_sensitive_key('Token') is True
        assert is_sensitive_key('SECRET_KEY') is True


class TestSanitizeDict:
    """Tests for sanitize_dict function."""

    def test_sanitize_dict_preserves_password(self):
        """Verify password is NOT redacted (for audit logging)."""
        data = {'password': 'mysecret123', 'username': 'testuser'}
        result = sanitize_dict(data)
        assert result['password'] == 'mysecret123'
        assert result['username'] == 'testuser'

    def test_sanitize_dict_removes_token(self):
        """Verify token is redacted."""
        data = {'token': 'abc123xyz', 'user_id': '123'}
        result = sanitize_dict(data)
        assert result['token'] == '***REDACTED***'
        assert result['user_id'] == '123'

    def test_sanitize_dict_removes_secret_key(self):
        """Verify secret_key is redacted."""
        data = {'secret_key': 'my-secret-key', 'name': 'test'}
        result = sanitize_dict(data)
        assert result['secret_key'] == '***REDACTED***'
        assert result['name'] == 'test'

    def test_sanitize_dict_handles_nested_dict(self):
        """Verify nested dictionaries are sanitized."""
        data = {
            'user': {
                'password': 'secret',
                'name': 'John',
                'details': {
                    'token': 'nested-token',
                    'email': 'test@example.com'
                }
            }
        }
        result = sanitize_dict(data)
        # Password is preserved for audit logging
        assert result['user']['password'] == 'secret'
        assert result['user']['name'] == 'John'
        assert result['user']['details']['token'] == '***REDACTED***'
        assert result['user']['details']['email'] == 'test@example.com'

    def test_sanitize_dict_handles_list_of_dicts(self):
        """Verify lists of dictionaries are sanitized."""
        data = {
            'items': [
                {'password': 'secret1', 'name': 'item1'},
                {'password': 'secret2', 'name': 'item2'}
            ]
        }
        result = sanitize_dict(data)
        # Passwords are preserved for audit logging
        assert result['items'][0]['password'] == 'secret1'
        assert result['items'][0]['name'] == 'item1'
        assert result['items'][1]['password'] == 'secret2'
        assert result['items'][1]['name'] == 'item2'

    def test_sanitize_dict_handles_list_of_lists(self):
        """Verify nested lists are handled."""
        data = {
            'matrix': [
                [{'password': 'secret1'}, {'token': 'token1'}],
                [{'password': 'secret2'}, {'token': 'token2'}]
            ]
        }
        result = sanitize_dict(data)
        # Passwords are preserved for audit logging
        assert result['matrix'][0][0]['password'] == 'secret1'
        assert result['matrix'][0][1]['token'] == '***REDACTED***'
        assert result['matrix'][1][0]['password'] == 'secret2'
        assert result['matrix'][1][1]['token'] == '***REDACTED***'

    def test_sanitize_dict_truncates_long_strings(self):
        """Verify long strings are truncated to MAX_STRING_LENGTH."""
        long_string = 'x' * 1000
        data = {'description': long_string}
        result = sanitize_dict(data)
        # Default MAX_STRING_LENGTH is 500, but truncation adds "...[truncated]"
        assert len(result['description']) <= 514  # 500 + len("...[truncated]")

    def test_sanitize_dict_custom_max_length(self):
        """Verify custom max_length parameter works."""
        long_string = 'x' * 100
        data = {'description': long_string}
        result = sanitize_dict(data, max_length=50)
        # Truncation adds "...[truncated]" suffix
        assert len(result['description']) <= 64  # 50 + len("...[truncated]")

    def test_sanitize_dict_preserves_non_sensitive_data(self):
        """Verify non-sensitive data is preserved."""
        data = {
            'server_url': 'http://localhost:8080',
            'port': 8080,
            'enabled': True,
            'count': 42,
            'ratio': 3.14
        }
        result = sanitize_dict(data)
        assert result['server_url'] == 'http://localhost:8080'
        assert result['port'] == 8080
        assert result['enabled'] is True
        assert result['count'] == 42
        assert result['ratio'] == 3.14

    def test_sanitize_dict_handles_empty_dict(self):
        """Verify empty dictionary is handled."""
        data = {}
        result = sanitize_dict(data)
        assert result == {}

    def test_sanitize_dict_handles_none_values(self):
        """Verify None values are preserved."""
        data = {'value': None, 'other': 'test'}
        result = sanitize_dict(data)
        assert result['value'] is None
        assert result['other'] == 'test'

    def test_sanitize_dict_handles_list_values(self):
        """Verify list values are preserved (non-dict lists)."""
        data = {'items': [1, 2, 3], 'names': ['a', 'b', 'c']}
        result = sanitize_dict(data)
        assert result['items'] == [1, 2, 3]
        assert result['names'] == ['a', 'b', 'c']

    def test_sanitize_dict_handles_dict_in_list(self):
        """Verify dictionaries within lists are sanitized."""
        data = {
            'users': [
                {'name': 'Alice', 'password': 'secret1'},
                {'name': 'Bob', 'token': 'token2'}
            ]
        }
        result = sanitize_dict(data)
        assert result['users'][0]['name'] == 'Alice'
        # Password is preserved for audit logging
        assert result['users'][0]['password'] == 'secret1'
        assert result['users'][1]['name'] == 'Bob'
        assert result['users'][1]['token'] == '***REDACTED***'

    def test_sanitize_dict_handles_special_characters(self):
        """Verify special characters in values are preserved."""
        data = {
            'message': 'Hello! @#$%^&*()',
            'password': 'secret'
        }
        result = sanitize_dict(data)
        assert result['message'] == 'Hello! @#$%^&*()'
        # Password is preserved for audit logging
        assert result['password'] == 'secret'

    def test_sanitize_dict_handles_unicode(self):
        """Verify unicode characters are preserved."""
        data = {
            'name': '用户',
            'password': 'secret'
        }
        result = sanitize_dict(data)
        assert result['name'] == '用户'
        # Password is preserved for audit logging
        assert result['password'] == 'secret'


class TestSanitizeProcessor:
    """Tests for sanitize_processor function."""

    def test_sanitize_processor_preserves_password(self):
        """Verify sanitize_processor preserves password in event dict (for audit logging)."""
        event_dict = {'event': 'login', 'password': 'secret'}
        result = sanitize_processor(None, None, event_dict)
        assert result['password'] == 'secret'

    def test_sanitize_processor_redacts_token(self):
        """Verify sanitize_processor redacts token in event dict."""
        event_dict = {'event': 'api_call', 'token': 'abc123'}
        result = sanitize_processor(None, None, event_dict)
        assert result['token'] == '***REDACTED***'

    def test_sanitize_processor_preserves_event(self):
        """Verify sanitize_processor preserves event field."""
        event_dict = {'event': 'user_action', 'password': 'secret'}
        result = sanitize_processor(None, None, event_dict)
        assert result['event'] == 'user_action'

    def test_sanitize_processor_handles_nested_dict(self):
        """Verify sanitize_processor handles nested dictionaries."""
        event_dict = {
            'event': 'complex',
            'data': {
                'password': 'secret',
                'token': 'token'
            }
        }
        result = sanitize_processor(None, None, event_dict)
        # Password is preserved for audit logging
        assert result['data']['password'] == 'secret'
        assert result['data']['token'] == '***REDACTED***'

    def test_sanitize_processor_handles_list(self):
        """Verify sanitize_processor handles lists."""
        event_dict = {
            'event': 'batch',
            'items': [
                {'password': 'secret1'},
                {'token': 'token1'}
            ]
        }
        result = sanitize_processor(None, None, event_dict)
        # Password is preserved for audit logging
        assert result['items'][0]['password'] == 'secret1'
        assert result['items'][1]['token'] == '***REDACTED***'

    def test_sanitize_processor_truncates_long_strings(self):
        """Verify sanitize_processor truncates long strings."""
        long_string = 'x' * 1000
        event_dict = {'event': 'test', 'description': long_string}
        result = sanitize_processor(None, None, event_dict)
        # Truncation adds "...[truncated]" suffix
        assert len(result['description']) <= 514  # 500 + len("...[truncated]")


class TestAddRemoveSensitiveKeys:
    """Tests for add_sensitive_keys and remove_sensitive_keys functions."""

    def test_add_sensitive_keys(self):
        """Verify add_sensitive_keys adds new keys."""
        original_count = len(SENSITIVE_KEYS)
        new_keys = {'custom_key1', 'custom_key2'}

        add_sensitive_keys(new_keys)

        assert is_sensitive_key('custom_key1')
        assert is_sensitive_key('custom_key2')

        # Cleanup
        remove_sensitive_keys(new_keys)

    def test_remove_sensitive_keys(self):
        """Verify remove_sensitive_keys removes keys."""
        # First add a key
        test_key = 'test_remove_key'
        add_sensitive_keys({test_key})
        assert is_sensitive_key(test_key)

        # Then remove it
        remove_sensitive_keys({test_key})
        assert not is_sensitive_key(test_key)


class TestSanitizationIntegration:
    """Integration tests for sanitization with structlog."""

    def test_structlog_processor_chain_sanitization(self):
        """Verify structlog processor chain includes sanitization."""
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
                import io
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

    def test_sanitization_with_multiple_sensitive_fields(self):
        """Verify multiple sensitive fields are all redacted."""
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
                import io
                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger.info(
                        'API call',
                        password='secret',
                        token='token123',
                        api_key='key456',
                        username='user'
                    )
                
                # Close handlers
                reset_structlog()

                # Parse the captured output as JSON
                output = captured_output.getvalue().strip()
                entry = json.loads(output)
                # Password is preserved for audit logging
                assert entry.get('password') == 'secret'
                assert entry.get('token') == '***REDACTED***'
                assert entry.get('api_key') == '***REDACTED***'
                assert entry.get('username') == 'user'


def reset_structlog():
    """Reset structlog configuration for clean test state."""
    import logging
    import structlog as sl
    
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
    sl.reset_defaults()