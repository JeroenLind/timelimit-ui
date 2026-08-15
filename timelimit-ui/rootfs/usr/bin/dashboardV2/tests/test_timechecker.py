"""Unit tests for timechecker dashboard functionality.

This module tests the Phase 3 implementation including:
- Timechecker status endpoint
- Historical data endpoint
- Server check data storage and retrieval
- Dashboard template rendering
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

from database import save_server_check, get_server_checks, get_latest_server_check


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
    def test_timechecker_status_performs_check_when_no_data(self, mock_auth_client_class):
        """Test that status endpoint performs a check when no data exists."""
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
    def test_timechecker_history_respects_limit(self, client):
        """Test that timechecker history respects limit parameter."""
        response = client.get('/api/timechecker/history?limit=5')
        data = response.get_json()
        
        assert len(data['checks']) <= 5
    
    @pytest.mark.timeout(10)
    def test_timechecker_history_default_limit(self, client):
        """Test that timechecker history has default limit of 10."""
        response = client.get('/api/timechecker/history')
        data = response.get_json()
        
        # Default limit is 10
        assert len(data['checks']) <= 10


class TestServerCheckStorage:
    """Tests for server check data storage operations."""
    
    @pytest.fixture
    def test_db(self):
        """Create a test database."""
        import tempfile
        import os
        from database import Database
        
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        db = Database(db_path=db_path)
        db.init_db()
        yield db
        db.close()
        os.close(db_fd)
        os.unlink(db_path)
    
    @pytest.mark.timeout(10)
    def test_save_server_check_success(self, test_db):
        """Test saving a successful server check."""
        row_id = save_server_check(
            db=test_db,
            success=True,
            error_code=None,
            user_message=None,
            technical_detail=None,
            server_time=1704067200000,
            attempts=1,
            server_url='http://localhost:8080'
        )
        
        assert row_id is not None
        assert row_id > 0
    
    @pytest.mark.timeout(10)
    def test_save_server_check_failure(self, test_db):
        """Test saving a failed server check."""
        row_id = save_server_check(
            db=test_db,
            success=False,
            error_code='timeout',
            user_message='Connection timeout',
            technical_detail='Timeout after 10s',
            server_time=None,
            attempts=3,
            server_url='http://localhost:8080'
        )
        
        assert row_id is not None
        assert row_id > 0
    
    @pytest.mark.timeout(10)
    def test_get_server_checks_returns_list(self, test_db):
        """Test that get_server_checks returns a list."""
        checks = get_server_checks(test_db, limit=10)
        
        assert isinstance(checks, list)
    
    @pytest.mark.timeout(10)
    def test_get_server_checks_ordering(self, test_db):
        """Test that server checks are ordered by timestamp descending."""
        # Save multiple checks
        save_server_check(
            db=test_db,
            success=True,
            error_code=None,
            user_message=None,
            technical_detail=None,
            server_time=1704067200000,
            attempts=1,
            server_url='http://localhost:8080'
        )
        
        save_server_check(
            db=test_db,
            success=False,
            error_code='unreachable',
            user_message='Cannot connect',
            technical_detail='Connection refused',
            server_time=None,
            attempts=1,
            server_url='http://localhost:8080'
        )
        
        checks = get_server_checks(test_db, limit=10)
        
        assert len(checks) == 2
        # Most recent first
        assert checks[0]['success'] == 0
        assert checks[1]['success'] == 1
    
    @pytest.mark.timeout(10)
    def test_get_latest_server_check(self, test_db):
        """Test getting the latest server check."""
        save_server_check(
            db=test_db,
            success=True,
            error_code=None,
            user_message=None,
            technical_detail=None,
            server_time=1704067200000,
            attempts=1,
            server_url='http://localhost:8080'
        )
        
        latest = get_latest_server_check(test_db, 'http://localhost:8080')
        
        assert latest is not None
        assert latest['success'] == 1
        assert latest['server_time'] == 1704067200000
    
    @pytest.mark.timeout(10)
    def test_get_latest_server_check_not_found(self, test_db):
        """Test getting latest server check for non-existent server."""
        latest = get_latest_server_check(test_db, 'http://nonexistent:8080')
        
        assert latest is None


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
    def test_dashboard_v2_has_historical_table(self, client):
        """Test that dashboardV2 has historical data table."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test_token_123'
        
        response = client.get('/dashboardV2')
        
        assert b'Historical Data' in response.data
        assert b'historical-table' in response.data
    
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
        assert b'Authentication status' in response.data


class TestDashboardJavaScript:
    """Tests for dashboard JavaScript functionality."""
    
    @pytest.mark.timeout(10)
    def test_dashboard_v2_has_javascript(self, client):
        """Test that dashboardV2 includes JavaScript."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test_token_123'
        
        response = client.get('/dashboardV2')
        
        assert b'refreshServerStatus' in response.data
        assert b'loadHistoricalData' in response.data
        assert b'showAlert' in response.data
    
    @pytest.mark.timeout(10)
    def test_dashboard_v2_has_api_endpoints_in_js(self, client):
        """Test that dashboardV2 JavaScript references correct API endpoints."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test_token_123'
        
        response = client.get('/dashboardV2')
        
        assert b'/api/timechecker/status' in response.data
        assert b'/api/timechecker/history' in response.data


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