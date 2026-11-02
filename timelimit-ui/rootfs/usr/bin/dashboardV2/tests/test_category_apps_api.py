"""Unit tests for category apps API endpoints.

This module tests the category apps API endpoints:
- GET /api/dashboard/categories/<category_id>/apps - Get apps in a category
- POST /api/dashboard/categories/<category_id>/apps - Add apps to a category
- DELETE /api/dashboard/categories/<category_id>/apps - Remove apps from a category
"""

import pytest
import json
from unittest.mock import Mock, patch
from database import (
    save_categories,
    save_category_app
)


class TestApiCategoryApps:
    """Tests for /api/dashboard/categories/<category_id>/apps endpoints."""
    
    @pytest.mark.timeout(10)
    def test_get_category_apps_unauthenticated(self, client):
        """Test GET category apps without authentication."""
        response = client.get('/api/dashboard/categories/cat_1/apps')
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error'] == 'Not authenticated'
    
    @pytest.mark.timeout(10)
    def test_get_category_apps_no_device_auth_token(self, client):
        """Test GET category apps without device auth token in session."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = None
        
        response = client.get('/api/dashboard/categories/cat_1/apps')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error'] == 'No device auth token'
    
    @pytest.mark.timeout(10)
    def test_get_category_apps_success(self, auth_session):
        """Test successful GET of category apps."""
        db = auth_session.application.test_db
        device_auth_token = 'device_token_test123_test_get_category_apps_success'
        
        # Create a category
        save_categories(db, device_auth_token, [
            {'id': 'cat_1', 'title': 'Test Category'}
        ])
        
        # Add apps to the category
        save_category_app(db, device_auth_token, 'cat_1', 'com.example.app1')
        save_category_app(db, device_auth_token, 'cat_1', 'com.example.app2')
        
        response = auth_session.get('/api/dashboard/categories/cat_1/apps')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert data['categoryId'] == 'cat_1'
        assert 'apps' in data
        assert len(data['apps']) == 2
        assert 'com.example.app1' in data['apps']
        assert 'com.example.app2' in data['apps']
    
    @pytest.mark.timeout(10)
    def test_get_category_apps_empty(self, auth_session):
        """Test GET category apps when none exist."""
        response = auth_session.get('/api/dashboard/categories/cat_1/apps')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert data['categoryId'] == 'cat_1'
        assert data['apps'] == []
    
    @pytest.mark.timeout(10)
    def test_post_category_apps_unauthenticated(self, client):
        """Test POST category apps without authentication."""
        response = client.post('/api/dashboard/categories/cat_1/apps',
            data=json.dumps({'apps': ['com.example.app1']}),
            content_type='application/json'
        )
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error'] == 'Not authenticated'
    
    @pytest.mark.timeout(10)
    def test_post_category_apps_no_device_auth_token(self, client):
        """Test POST category apps without device auth token."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = None
        
        response = client.post('/api/dashboard/categories/cat_1/apps',
            data=json.dumps({'apps': ['com.example.app1']}),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error'] == 'No device auth token'
    
    @pytest.mark.timeout(10)
    def test_post_category_apps_missing_apps(self, auth_session):
        """Test POST category apps without apps in request body."""
        response = auth_session.post('/api/dashboard/categories/cat_1/apps',
            data=json.dumps({}),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error'] == 'No apps provided'
    
    @pytest.mark.timeout(10)
    def test_post_category_apps_empty_apps_list(self, auth_session):
        """Test POST category apps with empty apps list."""
        response = auth_session.post('/api/dashboard/categories/cat_1/apps',
            data=json.dumps({'apps': []}),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error'] == 'No apps provided'
    
    @pytest.mark.timeout(10)
    @patch('auth_client.AuthClient')
    def test_post_category_apps_success(self, mock_auth_client_class, auth_session):
        """Test successful POST to add apps to category."""
        db = auth_session.application.test_db
        device_auth_token = 'device_token_test123_test_post_category_apps_success'
        
        # Create a category
        save_categories(db, device_auth_token, [
            {'id': 'cat_1', 'title': 'Test Category'}
        ])
        
        # Mock the AuthClient
        mock_client = Mock()
        mock_response = Mock()
        mock_response.success = True
        mock_client.add_category_app.return_value = mock_response
        mock_auth_client_class.return_value = mock_client
        
        response = auth_session.post('/api/dashboard/categories/cat_1/apps',
            data=json.dumps({'apps': ['com.example.app1', 'com.example.app2']}),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert data['categoryId'] == 'cat_1'
        assert data['appsAdded'] == 2
        
        # Verify apps were added
        response = auth_session.get('/api/dashboard/categories/cat_1/apps')
        data = json.loads(response.data)
        assert len(data['apps']) == 2
    
    @pytest.mark.timeout(10)
    def test_delete_category_apps_unauthenticated(self, client):
        """Test DELETE category apps without authentication."""
        response = client.delete('/api/dashboard/categories/cat_1/apps',
            data=json.dumps({'apps': ['com.example.app1']}),
            content_type='application/json'
        )
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error'] == 'Not authenticated'
    
    @pytest.mark.timeout(10)
    def test_delete_category_apps_no_device_auth_token(self, client):
        """Test DELETE category apps without device auth token."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = None
        
        response = client.delete('/api/dashboard/categories/cat_1/apps',
            data=json.dumps({'apps': ['com.example.app1']}),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error'] == 'No device auth token'
    
    @pytest.mark.timeout(10)
    def test_delete_category_apps_missing_apps(self, auth_session):
        """Test DELETE category apps without apps in request body."""
        response = auth_session.delete('/api/dashboard/categories/cat_1/apps',
            data=json.dumps({}),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error'] == 'No apps provided'
    
    @pytest.mark.timeout(10)
    @patch('auth_client.AuthClient')
    def test_delete_category_apps_success(self, mock_auth_client_class, auth_session):
        """Test successful DELETE to remove apps from category."""
        db = auth_session.application.test_db
        device_auth_token = 'device_token_test123_test_delete_category_apps_success'
        
        # Create a category and add apps
        save_categories(db, device_auth_token, [
            {'id': 'cat_1', 'title': 'Test Category'}
        ])
        save_category_app(db, device_auth_token, 'cat_1', 'com.example.app1')
        save_category_app(db, device_auth_token, 'cat_1', 'com.example.app2')
        
        # Mock the AuthClient
        mock_client = Mock()
        mock_response = Mock()
        mock_response.success = True
        mock_client.remove_category_app.return_value = mock_response
        mock_auth_client_class.return_value = mock_client
        
        # Delete one app
        response = auth_session.delete('/api/dashboard/categories/cat_1/apps',
            data=json.dumps({'apps': ['com.example.app1']}),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert data['categoryId'] == 'cat_1'
        assert data['appsRemoved'] == 1
        
        # Verify app was removed
        response = auth_session.get('/api/dashboard/categories/cat_1/apps')
        data = json.loads(response.data)
        assert len(data['apps']) == 1
        assert 'com.example.app1' not in data['apps']
        assert 'com.example.app2' in data['apps']