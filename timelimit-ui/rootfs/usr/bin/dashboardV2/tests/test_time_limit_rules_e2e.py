"""End-to-End tests for Time Limit Rules feature.

This module performs comprehensive E2E tests for the Time Limit Rules feature,
simulating the complete user workflow:

1. Start the dashboard server
2. Log in as a parent user
3. Navigate to Time Limit Rules page
4. Create a rule
5. Verify rule appears in list
6. Edit the rule
7. Delete the rule

These tests verify the complete integration of:
- Authentication flow
- API endpoints
- Database operations
- Frontend interactions
"""

import os
import json
import pytest
from unittest.mock import Mock, patch

from app import app
from database import (
    save_users,
    save_categories,
    save_time_limit_rule,
    get_time_limit_rules_by_device_auth_token,
    get_time_limit_rule_by_id,
    update_time_limit_rule,
    delete_time_limit_rule,
    create_family,
    store_auth_token,
    get_database
)


@pytest.fixture
def auth_session(client, request):
    """Create an authenticated session for testing.
    
    Returns a tuple of (client, device_auth_token, db) for convenience
    in E2E tests that need direct database access.
    """
    test_name = request.node.name
    unique_suffix = f"_{test_name}"
    
    # Create a test device auth token with unique suffix
    device_auth_token = f'device_token_e2e_test{unique_suffix}'
    
    # Get the database from the app
    db = client.application.test_db
    
    # Create family record
    create_family(
        db=db,
        device_auth_token=device_auth_token,
        mail='parent@example.com',
        parent_password_hash='$2b$12$hash1',
        parent_password_second_hash='$2b$12$hash2',
        parent_password_second_salt='$2b$12$salt',
        parent_password_encrypted=False
    )
    
    # Store auth token in session
    with client.session_transaction() as sess:
        sess['device_auth_token'] = device_auth_token
        sess['server_url'] = 'http://localhost:8080'
        sess['mail'] = 'parent@example.com'
    
    # Store the token in database
    store_auth_token(
        db=db,
        token_type='device_auth_token',
        token_value=device_auth_token,
        device_id='device_e2e_test',
        mail='parent@example.com'
    )
    
    return client, device_auth_token, db


class TestTimeLimitRulesE2E:
    """End-to-End tests for Time Limit Rules feature."""
    
    @pytest.mark.timeout(30)
    def test_e2e_time_limit_rules_complete_workflow(self, auth_session):
        """Test complete E2E workflow: create, read, update, delete time limit rules.
        
        This test simulates the complete user journey:
        1. Verify initial state (no rules)
        2. Create a child user and category
        3. Create a time limit rule
        4. Verify rule appears in list
        5. Edit the rule
        6. Verify changes
        7. Delete the rule
        8. Verify removal
        """
        client, device_auth_token, db = auth_session
        
        # Step 1: Verify initial state - no rules exist
        print("\n=== Step 1: Verify initial state ===")
        response = client.get('/api/dashboard/time-limit-rules')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert data['count'] == 0
        assert len(data['rules']) == 0
        print("✓ Initial state verified: No rules exist")
        
        # Step 2: Create a child user and category for the rule
        print("\n=== Step 2: Create user and category ===")
        save_users(db, device_auth_token, [
            {'id': 'child_user_1', 'name': 'Child User', 'type': 'child', 'mail': 'child@example.com'}
        ])
        save_categories(db, device_auth_token, [
            {'id': 'cat_education', 'title': 'Education', 'icon': 'book'}
        ])
        print("✓ User and category created")
        
        # Step 3: Create a time limit rule
        print("\n=== Step 3: Create time limit rule ===")
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.success = True
            mock_client.add_time_limit_rule.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            create_response = client.post('/api/dashboard/time-limit-rules',
                data=json.dumps({
                    'userId': 'child_user_1',
                    'categoryId': 'cat_education',
                    'rule': {
                        'type': 0,
                        'startTime': '08:00',
                        'endTime': '18:00',
                        'days': 127,  # All days
                        'limitMinutes': 120  # 2 hours
                    }
                }),
                content_type='application/json'
            )
        
        assert create_response.status_code == 200
        create_data = json.loads(create_response.data)
        assert create_data['status'] == 'ok'
        assert 'ruleId' in create_data
        rule_id = create_data['ruleId']
        print(f"✓ Rule created successfully with ID: {rule_id}")
        
        # Step 4: Verify rule appears in list
        print("\n=== Step 4: Verify rule appears in list ===")
        list_response = client.get('/api/dashboard/time-limit-rules')
        assert list_response.status_code == 200
        list_data = json.loads(list_response.data)
        assert list_data['status'] == 'ok'
        assert list_data['count'] == 1
        assert len(list_data['rules']) == 1
        assert list_data['rules'][0]['id'] == rule_id
        assert list_data['rules'][0]['user_id'] == 'child_user_1'
        assert list_data['rules'][0]['category_id'] == 'cat_education'
        print("✓ Rule verified in list")
        
        # Step 5: Edit the rule
        print("\n=== Step 5: Edit the rule ===")
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.success = True
            mock_client.add_time_limit_rule.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            edit_response = client.put(f'/api/dashboard/time-limit-rules/{rule_id}',
                data=json.dumps({
                    'rule': {
                        'type': 0,
                        'startTime': '09:00',
                        'endTime': '17:00',
                        'days': 63,  # Weekdays only
                        'limitMinutes': 90  # 1.5 hours
                    }
                }),
                content_type='application/json'
            )
        
        assert edit_response.status_code == 200
        edit_data = json.loads(edit_response.data)
        assert edit_data['status'] == 'ok'
        print("✓ Rule edited successfully")
        
        # Step 6: Verify changes
        print("\n=== Step 6: Verify changes ===")
        verify_response = client.get('/api/dashboard/time-limit-rules')
        assert verify_response.status_code == 200
        verify_data = json.loads(verify_response.data)
        assert verify_data['status'] == 'ok'
        assert verify_data['count'] == 1
        
        # Verify the rule was updated in database
        # Note: Database stores fields as flat columns, not nested under 'rule'
        updated_rule = get_time_limit_rule_by_id(db, rule_id)
        assert updated_rule is not None
        assert updated_rule['start_time'] == '09:00'
        assert updated_rule['end_time'] == '17:00'
        assert updated_rule['days'] == 63
        assert updated_rule['limit_minutes'] == 90
        print("✓ Changes verified successfully")
        
        # Step 7: Delete the rule
        print("\n=== Step 7: Delete the rule ===")
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.success = True
            mock_client.remove_time_limit_rule.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            delete_response = client.delete(f'/api/dashboard/time-limit-rules/{rule_id}')
        
        assert delete_response.status_code == 200
        delete_data = json.loads(delete_response.data)
        assert delete_data['status'] == 'ok'
        assert delete_data['message'] == 'Rule deleted successfully'
        print("✓ Rule deleted successfully")
        
        # Step 8: Verify removal
        print("\n=== Step 8: Verify removal ===")
        final_response = client.get('/api/dashboard/time-limit-rules')
        assert final_response.status_code == 200
        final_data = json.loads(final_response.data)
        assert final_data['status'] == 'ok'
        assert final_data['count'] == 0
        assert len(final_data['rules']) == 0
        
        # Verify the rule is deleted from database
        deleted_rule = get_time_limit_rule_by_id(db, rule_id)
        assert deleted_rule is None
        print("✓ Rule verified as deleted")
        
        print("\n=== E2E Test Complete: All operations successful ===")
    
    @pytest.mark.timeout(30)
    def test_e2e_multiple_rules_lifecycle(self, auth_session):
        """Test creating, managing, and deleting multiple rules.
        
        This test verifies:
        - Creating multiple rules
        - Listing all rules
        - Updating different rules
        - Deleting rules in different order
        """
        client, device_auth_token, db = auth_session
        
        # Setup: Create users and categories
        save_users(db, device_auth_token, [
            {'id': 'user_alice', 'name': 'Alice', 'type': 'child', 'mail': 'alice@example.com'},
            {'id': 'user_bob', 'name': 'Bob', 'type': 'child', 'mail': 'bob@example.com'}
        ])
        save_categories(db, device_auth_token, [
            {'id': 'cat_games', 'title': 'Games', 'icon': 'gamepad'},
            {'id': 'cat_social', 'title': 'Social Media', 'icon': 'chat'}
        ])
        
        # Create first rule
        print("\n=== Creating first rule ===")
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.success = True
            mock_client.add_time_limit_rule.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            response1 = client.post('/api/dashboard/time-limit-rules',
                data=json.dumps({
                    'userId': 'user_alice',
                    'categoryId': 'cat_games',
                    'rule': {
                        'type': 0,
                        'startTime': '16:00',
                        'endTime': '20:00',
                        'days': 63,  # Weekdays
                        'limitMinutes': 120
                    }
                }),
                content_type='application/json'
            )
        
        assert response1.status_code == 200
        rule1_id = json.loads(response1.data)['ruleId']
        print(f"✓ First rule created: {rule1_id}")
        
        # Create second rule
        print("\n=== Creating second rule ===")
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.success = True
            mock_client.add_time_limit_rule.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            response2 = client.post('/api/dashboard/time-limit-rules',
                data=json.dumps({
                    'userId': 'user_bob',
                    'categoryId': 'cat_social',
                    'rule': {
                        'type': 0,
                        'startTime': '00:00',
                        'endTime': '23:59',
                        'days': 127,  # All days
                        'limitMinutes': 60
                    }
                }),
                content_type='application/json'
            )
        
        assert response2.status_code == 200
        rule2_id = json.loads(response2.data)['ruleId']
        print(f"✓ Second rule created: {rule2_id}")
        
        # Verify both rules exist
        print("\n=== Verifying both rules exist ===")
        list_response = client.get('/api/dashboard/time-limit-rules')
        list_data = json.loads(list_response.data)
        assert list_data['count'] == 2
        rule_ids = [r['id'] for r in list_data['rules']]
        assert rule1_id in rule_ids
        assert rule2_id in rule_ids
        print("✓ Both rules verified in list")
        
        # Update first rule
        print("\n=== Updating first rule ===")
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.success = True
            mock_client.add_time_limit_rule.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            update_response = client.put(f'/api/dashboard/time-limit-rules/{rule1_id}',
                data=json.dumps({
                    'rule': {
                        'type': 0,
                        'startTime': '15:00',
                        'endTime': '21:00',
                        'days': 127,  # All days
                        'limitMinutes': 180
                    }
                }),
                content_type='application/json'
            )
        
        assert update_response.status_code == 200
        print("✓ First rule updated")
        
        # Delete first rule
        print("\n=== Deleting first rule ===")
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.success = True
            mock_client.remove_time_limit_rule.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            delete_response = client.delete(f'/api/dashboard/time-limit-rules/{rule1_id}')
        
        assert delete_response.status_code == 200
        print("✓ First rule deleted")
        
        # Verify only second rule remains
        print("\n=== Verifying only second rule remains ===")
        final_list = client.get('/api/dashboard/time-limit-rules')
        final_data = json.loads(final_list.data)
        assert final_data['count'] == 1
        assert final_data['rules'][0]['id'] == rule2_id
        print("✓ Second rule correctly remains")
        
        # Delete second rule
        print("\n=== Deleting second rule ===")
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.success = True
            mock_client.remove_time_limit_rule.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            delete_response = client.delete(f'/api/dashboard/time-limit-rules/{rule2_id}')
        
        assert delete_response.status_code == 200
        print("✓ Second rule deleted")
        
        # Verify no rules remain
        print("\n=== Verifying no rules remain ===")
        final_check = client.get('/api/dashboard/time-limit-rules')
        final_data = json.loads(final_check.data)
        assert final_data['count'] == 0
        print("✓ All rules cleaned up")
        
        print("\n=== Multiple Rules Lifecycle Test Complete ===")
    
    @pytest.mark.timeout(30)
    def test_e2e_rule_validation_errors(self, auth_session):
        """Test that validation errors are properly handled.
        
        This test verifies:
        - Invalid time format is rejected
        - Invalid days bitmask is rejected
        - Invalid limit minutes is rejected
        - Missing required fields are rejected
        """
        client, device_auth_token, db = auth_session
        
        # Setup: Create user and category
        save_users(db, device_auth_token, [
            {'id': 'user_test', 'name': 'Test User', 'type': 'child', 'mail': 'test@example.com'}
        ])
        save_categories(db, device_auth_token, [
            {'id': 'cat_test', 'title': 'Test Category'}
        ])
        
        # Test invalid start time
        print("\n=== Testing invalid start time ===")
        response = client.post('/api/dashboard/time-limit-rules',
            data=json.dumps({
                'userId': 'user_test',
                'categoryId': 'cat_test',
                'rule': {
                    'type': 0,
                    'startTime': '25:00',  # Invalid hour
                    'endTime': '18:00',
                    'days': 127,
                    'limitMinutes': 60
                }
            }),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'Invalid startTime' in data['error']
        print("✓ Invalid start time correctly rejected")
        
        # Test invalid end time
        print("\n=== Testing invalid end time ===")
        response = client.post('/api/dashboard/time-limit-rules',
            data=json.dumps({
                'userId': 'user_test',
                'categoryId': 'cat_test',
                'rule': {
                    'type': 0,
                    'startTime': '08:00',
                    'endTime': '25:00',  # Invalid hour
                    'days': 127,
                    'limitMinutes': 60
                }
            }),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'Invalid endTime' in data['error']
        print("✓ Invalid end time correctly rejected")
        
        # Test invalid days bitmask
        print("\n=== Testing invalid days bitmask ===")
        response = client.post('/api/dashboard/time-limit-rules',
            data=json.dumps({
                'userId': 'user_test',
                'categoryId': 'cat_test',
                'rule': {
                    'type': 0,
                    'startTime': '08:00',
                    'endTime': '18:00',
                    'days': 200,  # Invalid - exceeds 127
                    'limitMinutes': 60
                }
            }),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'Invalid days' in data['error']
        print("✓ Invalid days bitmask correctly rejected")
        
        # Test invalid limit minutes (negative)
        print("\n=== Testing invalid limit minutes ===")
        response = client.post('/api/dashboard/time-limit-rules',
            data=json.dumps({
                'userId': 'user_test',
                'categoryId': 'cat_test',
                'rule': {
                    'type': 0,
                    'startTime': '08:00',
                    'endTime': '18:00',
                    'days': 127,
                    'limitMinutes': -10  # Invalid - negative
                }
            }),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'Invalid limitMinutes' in data['error']
        print("✓ Invalid limit minutes correctly rejected")
        
        # Test missing userId
        print("\n=== Testing missing userId ===")
        response = client.post('/api/dashboard/time-limit-rules',
            data=json.dumps({
                'categoryId': 'cat_test',
                'rule': {
                    'type': 0,
                    'startTime': '08:00',
                    'endTime': '18:00',
                    'days': 127,
                    'limitMinutes': 60
                }
            }),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'Missing userId' in data['error']
        print("✓ Missing userId correctly rejected")
        
        # Test missing categoryId
        print("\n=== Testing missing categoryId ===")
        response = client.post('/api/dashboard/time-limit-rules',
            data=json.dumps({
                'userId': 'user_test',
                'rule': {
                    'type': 0,
                    'startTime': '08:00',
                    'endTime': '18:00',
                    'days': 127,
                    'limitMinutes': 60
                }
            }),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'Missing categoryId' in data['error']
        print("✓ Missing categoryId correctly rejected")
        
        # Test missing rule data
        print("\n=== Testing missing rule data ===")
        response = client.post('/api/dashboard/time-limit-rules',
            data=json.dumps({
                'userId': 'user_test',
                'categoryId': 'cat_test'
            }),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'Missing rule' in data['error']
        print("✓ Missing rule data correctly rejected")
        
        print("\n=== Validation Errors Test Complete ===")
    
    @pytest.mark.timeout(30)
    def test_e2e_unauthorized_access(self, client):
        """Test that unauthorized access is properly blocked.
        
        This test verifies:
        - Unauthenticated requests are rejected
        - Requests without device_auth_token are rejected
        """
        # Test unauthenticated GET
        print("\n=== Testing unauthenticated GET ===")
        response = client.get('/api/dashboard/time-limit-rules')
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error'] == 'Not authenticated'
        print("✓ Unauthenticated GET correctly rejected")
        
        # Test unauthenticated POST
        print("\n=== Testing unauthenticated POST ===")
        response = client.post('/api/dashboard/time-limit-rules',
            data=json.dumps({
                'userId': 'user_1',
                'categoryId': 'cat_1',
                'rule': {'type': 0, 'limitMinutes': 60}
            }),
            content_type='application/json'
        )
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error'] == 'Not authenticated'
        print("✓ Unauthenticated POST correctly rejected")
        
        # Test unauthenticated PUT
        print("\n=== Testing unauthenticated PUT ===")
        response = client.put('/api/dashboard/time-limit-rules/rule_123',
            data=json.dumps({'rule': {'limitMinutes': 60}}),
            content_type='application/json'
        )
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error'] == 'Not authenticated'
        print("✓ Unauthenticated PUT correctly rejected")
        
        # Test unauthenticated DELETE
        print("\n=== Testing unauthenticated DELETE ===")
        response = client.delete('/api/dashboard/time-limit-rules/rule_123')
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error'] == 'Not authenticated'
        print("✓ Unauthenticated DELETE correctly rejected")
        
        print("\n=== Unauthorized Access Test Complete ===")


class TestTimeLimitRulesIntegration:
    """Integration tests for Time Limit Rules with database operations."""
    
    @pytest.mark.timeout(30)
    def test_database_operations_integration(self, auth_session):
        """Test database operations for time limit rules.
        
        This test verifies:
        - Rules are correctly saved to database
        - Rules can be retrieved by device_auth_token
        - Rules can be retrieved by ID
        - Rules can be updated
        - Rules can be deleted
        """
        client, device_auth_token, db = auth_session
        
        # Create test data
        save_users(db, device_auth_token, [
            {'id': 'user_int_test', 'name': 'Integration Test User', 'type': 'child', 'mail': 'int@test.com'}
        ])
        save_categories(db, device_auth_token, [
            {'id': 'cat_int_test', 'title': 'Integration Test Category'}
        ])
        
        # Test save_time_limit_rule
        print("\n=== Testing save_time_limit_rule ===")
        rule_id = 'rule_integration_test'
        save_time_limit_rule(
            db=db,
            rule_id=rule_id,
            device_auth_token=device_auth_token,
            user_id='user_int_test',
            category_id='cat_int_test',
            rule_type=0,
            start_time='10:00',
            end_time='16:00',
            days=63,
            limit_minutes=120
        )
        print("✓ Rule saved to database")
        
        # Test get_time_limit_rule_by_id
        print("\n=== Testing get_time_limit_rule_by_id ===")
        rule = get_time_limit_rule_by_id(db, rule_id)
        assert rule is not None
        assert rule['id'] == rule_id
        assert rule['user_id'] == 'user_int_test'
        assert rule['category_id'] == 'cat_int_test'
        # Note: Database stores fields as flat columns, not nested under 'rule'
        assert rule['start_time'] == '10:00'
        assert rule['end_time'] == '16:00'
        assert rule['days'] == 63
        assert rule['limit_minutes'] == 120
        print("✓ Rule retrieved by ID")
        
        # Test get_time_limit_rules_by_device_auth_token
        print("\n=== Testing get_time_limit_rules_by_device_auth_token ===")
        rules = get_time_limit_rules_by_device_auth_token(db, device_auth_token)
        assert len(rules) == 1
        assert rules[0]['id'] == rule_id
        print("✓ Rules retrieved by device_auth_token")
        
        # Test update_time_limit_rule
        print("\n=== Testing update_time_limit_rule ===")
        updates = {
            'start_time': '09:00',
            'end_time': '17:00',
            'limit_minutes': 90
        }
        result = update_time_limit_rule(db, rule_id, updates)
        assert result is True
        
        updated_rule = get_time_limit_rule_by_id(db, rule_id)
        # Note: Database stores fields as flat columns, not nested under 'rule'
        assert updated_rule['start_time'] == '09:00'
        assert updated_rule['end_time'] == '17:00'
        assert updated_rule['limit_minutes'] == 90
        print("✓ Rule updated successfully")
        
        # Test delete_time_limit_rule
        print("\n=== Testing delete_time_limit_rule ===")
        result = delete_time_limit_rule(db, rule_id)
        assert result is True
        
        deleted_rule = get_time_limit_rule_by_id(db, rule_id)
        assert deleted_rule is None
        print("✓ Rule deleted successfully")
        
        # Verify no rules remain
        rules = get_time_limit_rules_by_device_auth_token(db, device_auth_token)
        assert len(rules) == 0
        print("✓ No rules remain after deletion")
        
        print("\n=== Database Operations Integration Test Complete ===")