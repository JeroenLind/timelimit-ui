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
    @patch('app._push_parent_actions_safely', return_value={'synced': True, 'syncMessage': None})
    def test_post_category_apps_success(self, mock_push, auth_session):
        """Test successful POST to add apps to category."""
        db = auth_session.application.test_db
        device_auth_token = 'device_token_test123_test_post_category_apps_success'
        
        # Create a category
        save_categories(db, device_auth_token, [
            {'id': 'cat001', 'title': 'Test Category'}
        ])
        
        response = auth_session.post('/api/dashboard/categories/cat001/apps',
            data=json.dumps({'apps': ['com.example.app1', 'com.example.app2']}),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert data['categoryId'] == 'cat001'
        assert data['appsAdded'] == 2
        assert data['synced'] is True
        # one ADD_CATEGORY_APPS parent action with all packages (not one action per app)
        pushed = mock_push.call_args[0][1]
        assert pushed == [{'type': 'ADD_CATEGORY_APPS', 'categoryId': 'cat001',
                           'packageNames': ['com.example.app1', 'com.example.app2']}]
        
        # Verify apps were added
        response = auth_session.get('/api/dashboard/categories/cat001/apps')
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
    @patch('app._push_parent_actions_safely', return_value={'synced': True, 'syncMessage': None})
    def test_delete_category_apps_success(self, mock_push, auth_session):
        """Test successful DELETE to remove apps from category."""
        db = auth_session.application.test_db
        device_auth_token = 'device_token_test123_test_delete_category_apps_success'
        
        # Create a category and add apps
        save_categories(db, device_auth_token, [
            {'id': 'cat001', 'title': 'Test Category'}
        ])
        save_category_app(db, device_auth_token, 'cat001', 'com.example.app1')
        save_category_app(db, device_auth_token, 'cat001', 'com.example.app2')
        
        # Delete one app
        response = auth_session.delete('/api/dashboard/categories/cat001/apps',
            data=json.dumps({'apps': ['com.example.app1']}),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert data['categoryId'] == 'cat001'
        assert data['appsRemoved'] == 1
        assert data['synced'] is True
        pushed = mock_push.call_args[0][1]
        assert pushed == [{'type': 'REMOVE_CATEGORY_APPS', 'categoryId': 'cat001',
                           'packageNames': ['com.example.app1']}]
        
        # Verify app was removed
        response = auth_session.get('/api/dashboard/categories/cat001/apps')
        data = json.loads(response.data)
        assert len(data['apps']) == 1
        assert 'com.example.app1' not in data['apps']
        assert 'com.example.app2' in data['apps']

    @patch('app._push_parent_actions_safely',
           return_value={'synced': False, 'syncMessage': 'server did not confirm all actions'})
    def test_post_category_apps_server_does_not_confirm(self, mock_push, auth_session):
        """The change is kept locally and the response says it was not synced."""
        db = auth_session.application.test_db
        device_auth_token = 'device_token_test123_test_post_category_apps_server_does_not_confirm'
        save_categories(db, device_auth_token, [{'id': 'cat001', 'title': 'Test Category'}])

        response = auth_session.post('/api/dashboard/categories/cat001/apps',
            data=json.dumps({'apps': ['com.example.app1']}),
            content_type='application/json')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok' and data['synced'] is False
        assert 'confirm' in data['syncMessage']
        assert len(json.loads(auth_session.get('/api/dashboard/categories/cat001/apps').data)['apps']) == 1

    def test_post_category_apps_with_old_style_category_id_is_not_pushed(self, auth_session):
        """Category ids that are not 6 alphanumerics are rejected by the server; nothing is sent."""
        db = auth_session.application.test_db
        device_auth_token = 'device_token_test123_test_post_category_apps_with_old_style_category_id_is_not_pushed'
        save_categories(db, device_auth_token, [{'id': 'cat_1', 'title': 'Old'}])
        with patch('app.AuthClient') as client_class:
            response = auth_session.post('/api/dashboard/categories/cat_1/apps',
                data=json.dumps({'apps': ['com.example.app1']}),
                content_type='application/json')
            client_class.assert_not_called()
        data = json.loads(response.data)
        assert response.status_code == 200 and data['synced'] is False
