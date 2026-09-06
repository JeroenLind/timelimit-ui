#!/usr/bin/env python3
"""Verify bcrypt hash reproduction and analyze audit.log for login attempt differences."""

import bcrypt
import json
import re

def verify_bcrypt_hash(password, salt, expected_hash):
    """
    Verify that bcrypt.hashpw(password, salt) produces the expected hash.
    
    Args:
        password: Plaintext password string
        salt: Bcrypt salt string (e.g., "$2a$12$...")
        expected_hash: Expected bcrypt hash string
    
    Returns:
        Tuple of (success: bool, actual_hash: str, message: str)
    """
    try:
        password_bytes = password.encode('utf-8')
        salt_bytes = salt.encode('utf-8')
        
        # Generate hash using the provided salt
        actual_hash = bcrypt.hashpw(password_bytes, salt_bytes).decode('utf-8')
        
        # Compare with expected hash
        if actual_hash == expected_hash:
            return True, actual_hash, "Hash matches expected value"
        else:
            return False, actual_hash, f"Hash mismatch: expected {expected_hash}, got {actual_hash}"
    except Exception as e:
        return False, "", f"Error: {str(e)}"

def analyze_audit_log(log_path):
    """
    Analyze audit.log to find login attempts and password hash differences.
    
    Returns:
        Dictionary with analysis results
    """
    results = {
        'family_creation': None,
        'last_login_attempt': None,
        'password_data': [],
        'differences': []
    }
    
    try:
        with open(log_path, 'r') as f:
            lines = f.readlines()
        
        for line in lines:
            try:
                entry = json.loads(line.strip())
                
                # Look for family_creation_request with password_data
                if entry.get('event') == 'family_creation_request':
                    results['family_creation'] = entry
                    if 'password_data' in entry:
                        results['password_data'].append({
                            'event': 'family_creation_request',
                            'timestamp': entry.get('timestamp'),
                            'hash': entry['password_data'].get('hash'),
                            'secondHash': entry['password_data'].get('secondHash'),
                            'secondSalt': entry['password_data'].get('secondSalt')
                        })
                
                # Look for device_removal_request (last login attempt)
                if entry.get('event') == 'device_removal_request':
                    results['last_login_attempt'] = entry
                    if 'parent_password_second_hash' in entry:
                        results['password_data'].append({
                            'event': 'device_removal_request',
                            'timestamp': entry.get('timestamp'),
                            'parent_password_second_hash': entry['parent_password_second_hash'],
                            'success': entry.get('success'),
                            'status_code': entry.get('status_code')
                        })
                        
            except json.JSONDecodeError:
                continue
        
        # Analyze differences
        if results['family_creation'] and results['last_login_attempt']:
            fc = results['family_creation']
            ll = results['last_login_attempt']
            
            if 'password_data' in fc and 'parent_password_second_hash' in ll:
                expected_second_hash = fc['password_data'].get('secondHash')
                actual_second_hash = ll.get('parent_password_second_hash')
                
                if expected_second_hash != actual_second_hash:
                    results['differences'].append({
                        'field': 'parent_password_second_hash',
                        'expected': expected_second_hash,
                        'actual': actual_second_hash,
                        'reason': 'Hash values differ - password was likely changed or different password was used'
                    })
                
                # Check if the actual hash matches the expected salt
                expected_salt = fc['password_data'].get('secondSalt')
                if expected_salt:
                    # Verify if actual hash was generated from expected salt
                    success, actual, msg = verify_bcrypt_hash('12345678', expected_salt, actual_second_hash)
                    if not success:
                        results['differences'].append({
                            'field': 'password_verification',
                            'expected_hash_for_12345678': expected_second_hash,
                            'actual_hash': actual_second_hash,
                            'salt_used': expected_salt,
                            'reason': f"Password '12345678' with salt '{expected_salt}' does not produce hash '{actual_second_hash}'"
                        })
        
    except FileNotFoundError:
        results['error'] = f"Log file not found: {log_path}"
    except Exception as e:
        results['error'] = f"Error analyzing log: {str(e)}"
    
    return results

def main():
    print("=" * 80)
    print("BCRYPT HASH VERIFICATION AND AUDIT LOG ANALYSIS")
    print("=" * 80)
    
    # Test data from user request
    password = '12345678'
    salt = '$2a$12$GH3WX.UWo.gdKkWy0j/K9u'
    expected_hash = '$2a$12$GH3WX.UWo.gdKkWy0j/K9udedcl/fv9CkSbTRghbIY66Eeo.jY1/K'
    
    print("\n1. BCRYPT HASH VERIFICATION")
    print("-" * 40)
    print(f"Password: {password}")
    print(f"Salt: {salt}")
    print(f"Expected Hash: {expected_hash}")
    
    success, actual_hash, message = verify_bcrypt_hash(password, salt, expected_hash)
    
    print(f"\nResult: {'✓ PASS' if success else '✗ FAIL'}")
    print(f"Actual Hash: {actual_hash}")
    print(f"Message: {message}")
    
    # Verify the hash matches
    if success:
        print("\n✓ VERIFIED: The bcrypt hash for password '12345678' with salt '{salt}' produces expected hash '{expected_hash}'")
    else:
        print(f"\n✗ MISMATCH: The bcrypt hash does not match the expected value")
        print(f"  Expected: {expected_hash}")
        print(f"  Actual:   {actual_hash}")
    
    # Analyze audit log
    print("\n" + "=" * 80)
    print("2. AUDIT LOG ANALYSIS")
    print("-" * 40)
    
    log_path = 'timelimit-ui/rootfs/usr/bin/dashboardV2/logs/audit.log'
    analysis = analyze_audit_log(log_path)
    
    if 'error' in analysis:
        print(f"Error: {analysis['error']}")
        return
    
    # Show family creation data
    if analysis['family_creation']:
        fc = analysis['family_creation']
        print("\nFamily Creation Request (First Login):")
        print(f"  Timestamp: {fc.get('timestamp')}")
        print(f"  Email: {fc.get('email')}")
        print(f"  Parent Name: {fc.get('parent_name')}")
        if 'password_data' in fc:
            print(f"  Password Hash: {fc['password_data'].get('hash')}")
            print(f"  Second Hash: {fc['password_data'].get('secondHash')}")
            print(f"  Second Salt: {fc['password_data'].get('secondSalt')}")
    
    # Show last login attempt
    if analysis['last_login_attempt']:
        ll = analysis['last_login_attempt']
        print("\nLast Login Attempt (Device Removal Request):")
        print(f"  Timestamp: {ll.get('timestamp')}")
        print(f"  Device Auth Token: {ll.get('device_auth_token')}")
        print(f"  Parent User ID: {ll.get('parent_user_id')}")
        print(f"  Device ID: {ll.get('device_id')}")
        print(f"  Parent Password Second Hash: {ll.get('parent_password_second_hash')}")
        print(f"  Success: {ll.get('success')}")
        print(f"  Status Code: {ll.get('status_code')}")
    
    # Show differences
    if analysis['differences']:
        print("\nDifferences Identified:")
        for diff in analysis['differences']:
            print(f"  Field: {diff['field']}")
            for key, value in diff.items():
                if key != 'field':
                    print(f"    {key}: {value}")
            print(f"    Reason: {diff['reason']}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    if success:
        print("✓ Bcrypt hash verification: PASSED")
        print("  Password '12345678' with salt '$2a$12$GH3WX.UWo.gdKkWy0j/K9u' produces expected hash")
    else:
        print("✗ Bcrypt hash verification: FAILED")
        print("  The hash does not match the expected value")
    
    if analysis['differences']:
        print("\n✗ Audit log analysis: DIFFERENCES FOUND")
        print("  The last login attempt used a different password hash than expected")
        print("  This indicates the password was changed or a different password was used")
    else:
        print("\n✓ Audit log analysis: NO DIFFERENCES")
        print("  All password hashes match expected values")

if __name__ == '__main__':
    main()