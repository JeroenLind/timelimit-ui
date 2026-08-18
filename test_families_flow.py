#!/usr/bin/env python3
"""Test script for POST /api/families endpoint via dashboardV2."""

import requests
import json
import time

BASE_URL = "http://127.0.0.1:8099"
DEBUG_SERVER_URL = "http://127.0.0.1:8081"

def test_full_flow():
    """Test the full authentication flow with a unique email."""
    print("=" * 60)
    print("Testing Full Authentication Flow")
    print("=" * 60)
    
    # Use unique email to avoid "family already exists" error
    unique_email = f"test_{int(time.time())}@example.com"
    print(f"\nUsing unique email: {unique_email}")
    
    # Step 1: Send mail login code
    print("\n=== Step 1: Send mail login code ===")
    r = requests.post(f'{DEBUG_SERVER_URL}/auth/send-mail-login-code-v2', json={'mail': unique_email, 'locale': 'en'})
    print(f'Status: {r.status_code}')
    data = r.json()
    print(f'Response: {json.dumps(data, indent=2)}')
    mail_login_token = data.get('mailLoginToken')
    
    if r.status_code != 200:
        print("FAILED: Could not get mail login token")
        return False
    
    # Step 2: Sign in by mail code (using 3-word passphrase)
    print("\n=== Step 2: Sign in by mail code ===")
    verification_code = "Pferd Miete abwenden"  # 3-word passphrase
    r = requests.post(f'{DEBUG_SERVER_URL}/auth/sign-in-by-mail-code', json={'mailLoginToken': mail_login_token, 'receivedCode': verification_code})
    print(f'Status: {r.status_code}')
    data = r.json()
    print(f'Response: {json.dumps(data, indent=2)}')
    mail_auth_token = data.get('mailAuthToken')
    
    if r.status_code != 200:
        print("FAILED: Could not sign in by mail code")
        return False
    
    # Step 3: Create family via dashboardV2 (POST /api/families)
    print("\n=== Step 3: Create family via dashboardV2 (POST /api/families) ===")
    family_data = {
        'mailAuthToken': mail_auth_token,
        'parentPassword': {
            'hash': '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.VTtYA/7.J6LlZy',
            'secondHash': '$2b$12$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi',
            'secondSalt': '$2b$12$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi'
        },
        'parentDevice': {
            'model': 'Test Model'
        },
        'deviceName': 'Test Device',
        'timeZone': 'Europe/Amsterdam',
        'parentName': 'Test Parent',
        'clientLevel': 7
    }
    r = requests.post(f'{BASE_URL}/api/families', json=family_data)
    print(f'Status: {r.status_code}')
    print(f'Response: {r.text}')
    
    if r.status_code == 200:
        print("\nSUCCESS: Full flow completed successfully!")
        return True
    else:
        print(f"\nFAILED: Status code {r.status_code}")
        return False

def test_edge_cases():
    """Test edge cases."""
    print("\n" + "=" * 60)
    print("Testing Edge Cases")
    print("=" * 60)
    
    # First get a valid mailAuthToken
    r = requests.post(f'{DEBUG_SERVER_URL}/auth/send-mail-login-code-v2', json={'mail': 'test@example.com', 'locale': 'en'})
    data = r.json()
    mail_login_token = data.get('mailLoginToken')
    r = requests.post(f'{DEBUG_SERVER_URL}/auth/sign-in-by-mail-code', json={'mailLoginToken': mail_login_token, 'receivedCode': 'Pferd Miete abwenden'})
    mail_auth_token = r.json().get('mailAuthToken')
    
    # Test 1: Missing mailAuthToken
    print("\n=== Test 1: Missing mailAuthToken ===")
    family_data = {
        'parentPassword': {
            'hash': '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.VTtYA/7.J6LlZy',
            'secondHash': '$2b$12$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi',
            'secondSalt': '$2b$12$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi'
        },
        'parentDevice': {
            'model': 'Test Model'
        },
        'deviceName': 'Test Device',
        'timeZone': 'Europe/Amsterdam',
        'parentName': 'Test Parent'
    }
    r = requests.post(f'{BASE_URL}/api/families', json=family_data)
    print(f'Status: {r.status_code}')
    print(f'Response: {r.text}')
    
    # Test 2: Missing parentPassword
    print("\n=== Test 2: Missing parentPassword ===")
    family_data = {
        'mailAuthToken': mail_auth_token
    }
    r = requests.post(f'{BASE_URL}/api/families', json=family_data)
    print(f'Status: {r.status_code}')
    print(f'Response: {r.text}')
    
    # Test 3: Invalid mailAuthToken
    print("\n=== Test 3: Invalid mailAuthToken ===")
    family_data = {
        'mailAuthToken': 'invalid_token_12345',
        'parentPassword': {
            'hash': '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.VTtYA/7.J6LlZy',
            'secondHash': '$2b$12$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi',
            'secondSalt': '$2b$12$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi'
        },
        'parentDevice': {
            'model': 'Test Model'
        },
        'deviceName': 'Test Device',
        'timeZone': 'Europe/Amsterdam',
        'parentName': 'Test Parent'
    }
    r = requests.post(f'{BASE_URL}/api/families', json=family_data)
    print(f'Status: {r.status_code}')
    print(f'Response: {r.text}')
    
    # Test 4: Family already exists (run create family twice with same email)
    print("\n=== Test 4: Family already exists ===")
    family_data = {
        'mailAuthToken': mail_auth_token,
        'parentPassword': {
            'hash': '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.VTtYA/7.J6LlZy',
            'secondHash': '$2b$12$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi',
            'secondSalt': '$2b$12$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi'
        },
        'parentDevice': {
            'model': 'Test Model'
        },
        'deviceName': 'Test Device',
        'timeZone': 'Europe/Amsterdam',
        'parentName': 'Test Parent'
    }
    r = requests.post(f'{BASE_URL}/api/families', json=family_data)
    print(f'Status: {r.status_code}')
    print(f'Response: {r.text}')

if __name__ == '__main__':
    test_full_flow()
    test_edge_cases()