"""Unit tests for timechecker dashboard functionality.

This module tests the Phase 3 implementation including:
- Timechecker status endpoint
- Historical data endpoint (now returns empty since we don't store server checks)
- Dashboard template rendering
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock


class TestTimecheckerStatusEndpoint:
    """Tests for the /api/timechecker/status endpoint."""
    
    @pytest.mark.timeout(10)
    @patch('app.AuthClient')
    def test_timechecker_status_returns_200(self, mock_auth_client_class):
        """Test that timechecker status endpoint returns 200."""
        # Setup mock
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
        
        from app import app
        app.config['TESTING'] = True
        client = app.test_client()
        
        response = client.get('/api/timechecker/status')
        
        assert response.status_code == 200

    @pytest.mark.timeout(10)
    @patch('app.AuthClient')
    def test_timechecker_status_returns_json(self, mock_auth_client_class):
        """Test that timechecker status returns JSON."""
        # Setup mock
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
        
        from app import app
        app.config['TESTING'] = True
        client = app.test_client()
        
        response = client.get('/api/timechecker/status')
        
        assert response.content_type == 'application/json'

    @pytest.mark.timeout(10)
    @patch('app.AuthClient')
    def test_timechecker_status_has_required_fields(self, mock_auth_client_class):
        """Test that timechecker status has all required fields."""
        # Setup mock
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
        
        from app import app
        app.config['TESTING'] = True
        client = app.test_client()
        
        response = client.get('/api/timechecker/status')
        data = response.get_json()
        
        assert 'success' in data
        assert 'server_time' in data
        assert 'error_code' in data
        assert 'error_message' in data
        assert 'timestamp' in data
        assert 'attempts' in data

    @pytest.mark.timeout(10)
    @patch('app.AuthClient')
    def test_timechecker_status_performs_check(self, mock_auth_client_class):
        """Test that status endpoint performs a check and returns data."""
        # Setup mock
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
        
        from app import app
        app.config['TESTING'] = True
        client = app.test_client()
        
        response = client.get('/api/timechecker/status')
        data = response.get_json()
        
        # Should have performed a check and returned data
        assert 'success' in data
        assert 'timestamp' in data


class TestTimecheckerHistoryEndpoint:
    """Tests for the /api/timechecker/history endpoint."""
    
    @pytest.mark.timeout(10)
    def test_timechecker_history_returns_200(self, client):
        """Test that timechecker history endpoint returns 200."""
        response = client.get('/api/timechecker/history')
        
        assert response.status_code == 200
    
    @pytest.mark.timeout(10)
    def test_timechecker_history_returns_json(self, client):
        """Test that timechecker history returns JSON."""
        response = client.get('/api/timechecker/history')
        
        assert response.content_type == 'application/json'
    
    @pytest.mark.timeout(10)
    def test_timechecker_history_has_checks_array(self, client):
        """Test that timechecker history has checks array."""
        response = client.get('/api/timechecker/history')
        data = response.get_json()
        
        assert 'checks' in data
        assert isinstance(data['checks'], list)
    
    @pytest.mark.timeout(10)
    def test_timechecker_history_has_total_count(self, client):
        """Test that timechecker history has total count."""
        response = client.get('/api/timechecker/history')
        data = response.get_json()
        
        assert 'total' in data
        assert isinstance(data['total'], int)
    
    @pytest.mark.timeout(10)
    def test_timechecker_history_returns_empty_list(self, client):
        """Test that timechecker history returns empty list since we don't store server checks."""
        response = client.get('/api/timechecker/history')
        data = response.get_json()
        
        # Since we no longer store server checks, history should be empty
        assert len(data['checks']) == 0
        assert data['total'] == 0
    
    @pytest.mark.timeout(10)
    def test_timechecker_history_respects_limit(self, client):
        """Test that timechecker history respects limit parameter."""
        response = client.get('/api/timechecker/history?limit=5')
        data = response.get_json()
        
        # Should still be empty since we don't store server checks
        assert len(data['checks']) == 0
    
    @pytest.mark.timeout(10)
    def test_timechecker_history_default_limit(self, client):
        """Test that timechecker history has default limit of 10."""
        response = client.get('/api/timechecker/history')
        data = response.get_json()
        
        # Should be empty since we don't store server checks
        assert len(data['checks']) == 0


class TestDashboardTemplate:
    """Tests for the dashboardV2.html template."""
    
    @pytest.mark.timeout(10)
    def test_dashboard_v2_accessible_without_authentication(self, client):
        """Test that dashboardV2 is accessible without authentication."""
        response = client.get('/dashboardV2', follow_redirects=False)
        
        # Should return 200, not redirect
        assert response.status_code == 200
        assert b'TimeLimit Dashboard v2' in response.data
    
    @pytest.mark.timeout(10)
    def test_dashboard_v2_shows_content_when_authenticated(self, client):
        """Test that dashboardV2 shows content when authenticated."""
        # Set up session with device_auth_token
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test_token_123'
        
        response = client.get('/dashboardV2')
        
        assert response.status_code == 200
        assert b'TimeLimit Dashboard v2' in response.data
    
    @pytest.mark.timeout(10)
    def test_dashboard_v2_has_status_section(self, client):
        """Test that dashboardV2 has status section."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test_token_123'
        
        response = client.get('/dashboardV2')
        
        assert b'Server Status' in response.data
    
    @pytest.mark.timeout(10)
    def test_dashboard_v2_has_refresh_button(self, client):
        """Test that dashboardV2 has refresh button."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test_token_123'
        
        response = client.get('/dashboardV2')
        
        assert b'Refresh Status' in response.data
        assert b'refresh-btn' in response.data
    
    @pytest.mark.timeout(10)
    def test_dashboard_v2_has_session_info(self, client):
        """Test that dashboardV2 has session information section."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test_token_123'
        
        response = client.get('/dashboardV2')
        
        assert b'Session Information' in response.data
        assert b'Auth:' in response.data


class TestDashboardJavaScript:
    """Tests for dashboard JavaScript functionality."""
    
    @pytest.mark.timeout(10)
    def test_dashboard_v2_has_javascript(self, client):
        """Test that dashboardV2 includes JavaScript."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test_token_123'
        
        response = client.get('/dashboardV2')
        
        assert b'refreshServerStatus' in response.data
        assert b'showAlert' in response.data
    
    @pytest.mark.timeout(10)
    def test_dashboard_v2_has_api_endpoints_in_js(self, client):
        """Test that dashboardV2 JavaScript references correct API endpoints."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test_token_123'
        
        response = client.get('/dashboardV2')
        
        # Refresh button now calls sync endpoint instead of just checking status
        assert b'/api/sync/pull' in response.data


class TestDashboardCSS:
    """Tests for dashboard CSS styles."""
    
    @pytest.mark.timeout(10)
    def test_dashboard_v2_has_status_styles(self, client):
        """Test that dashboardV2 has status indicator styles."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test_token_123'
        
        response = client.get('/dashboardV2')
        
        assert b'status-indicator' in response.data
        assert b'status-success' in response.data
        assert b'status-error' in response.data
    
    @pytest.mark.timeout(10)
    def test_dashboard_v2_has_alert_styles(self, client):
        """Test that dashboardV2 has alert notification styles."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test_token_123'
        
        response = client.get('/dashboardV2')
        
        assert b'alert-container' in response.data
        assert b'alert' in response.data
    
    @pytest.mark.timeout(10)
    def test_dashboard_v2_has_responsive_styles(self, client):
        """Test that dashboardV2 has responsive design styles."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test_token_123'
        
        response = client.get('/dashboardV2')
        
        assert b'max-width: 480px' in response.data or b'max-width: 768px' in response.data