#!/usr/bin/env python3
import json
import bcrypt

# Read audit log
log_path = 'timelimit-ui/rootfs/usr/bin/dashboardV2/logs/audit.log'

print("=" * 80)
print("AUDIT LOG ANALYSIS - PASSWORD HASH DIFFERENCES")
print("=" * 80)

with open(log_path, 'r') as f:
    lines = f.readlines()

# Find all login-related events with password data
password_events = []

for line in lines:
    try:
        entry = json.loads(line.strip())
        
        # Look for family_creation_request with password_data
        if entry.get('event') == 'family_creation_request' and 'password_data' in entry:
            password_events.append({
                'event': 'family_creation_request',
                'timestamp': entry.get('timestamp'),
                'email': entry.get('email'),
                'password_data': entry.get('password_data')
            })
        
        # Look for device_removal_request (last login attempt)
        if entry.get('event') == 'device_removal_request':
            password_events.append({
                'event': 'device_removal_request',
                'timestamp': entry.get('timestamp'),
                'device_auth_token': entry.get('device_auth_token'),
                'parent_password_second_hash': entry.get('parent_password_second_hash'),
                'success': entry.get('success'),
                'status_code': entry.get('status_code'),
                'error_message': entry.get('error_message', '')[:200] if entry.get('error_message') else ''
            })
            
    except json.JSONDecodeError:
        continue

print("\n1. FAMILY CREATION REQUEST (Initial Password Setup)")
print("-" * 60)
if password_events:
    fc = password_events[0]
    print(f"Timestamp: {fc['timestamp']}")
    print(f"Email: {fc['email']}")
    print(f"Password Hash: {fc['password_data']['hash']}")
    print(f"Second Hash: {fc['password_data']['secondHash']}")
    print(f"Second Salt: {fc['password_data']['secondSalt']}")

print("\n2. LAST LOGIN ATTEMPT (Device Removal Request)")
print("-" * 60)
if len(password_events) > 1:
    ll = password_events[1]
    print(f"Timestamp: {ll['timestamp']}")
    print(f"Device Auth Token: {ll['device_auth_token']}")
    print(f"Parent Password Second Hash: {ll['parent_password_second_hash']}")
    print(f"Success: {ll['success']}")
    print(f"Status Code: {ll['status_code']}")
    if ll['error_message']:
        print(f"Error: {ll['error_message']}")

print("\n3. HASH COMPARISON")
print("-" * 60)
if len(password_events) >= 2:
    fc = password_events[0]
    ll = password_events[1]
    
    expected_hash = fc['password_data']['secondHash']
    actual_hash = ll['parent_password_second_hash']
    expected_salt = fc['password_data']['secondSalt']
    
    print(f"Expected Hash (from family creation): {expected_hash}")
    print(f"Actual Hash (from device removal):    {actual_hash}")
    print(f"Expected Salt: {expected_salt}")
    
    # Verify what password produces the expected hash
    print("\n4. PASSWORD VERIFICATION")
    print("-" * 60)
    
    # Test with password '12345678'
    test_password = '12345678'
    generated = bcrypt.hashpw(test_password.encode('utf-8'), expected_salt.encode('utf-8')).decode('utf-8')
    print(f"Password '{test_password}' with salt '{expected_salt}':")
    print(f"  Generated: {generated}")
    print(f"  Expected:  {expected_hash}")
    print(f"  Match: {generated == expected_hash}")
    
    # Check if the actual hash matches the expected salt
    print(f"\n  Does actual hash match expected salt? {actual_hash == generated}")
    
    # Check if the actual hash matches the expected hash
    print(f"  Does actual hash match expected hash? {actual_hash == expected_hash}")
    
    # Analyze the difference
    print("\n5. DIFFERENCE ANALYSIS")
    print("-" * 60)
    if actual_hash != expected_hash:
        print("The hashes are DIFFERENT!")
        print(f"Expected: {expected_hash}")
        print(f"Actual:   {actual_hash}")
        
        # Find the exact difference
        for i, (e, a) in enumerate(zip(expected_hash, actual_hash)):
            if e != a:
                print(f"  First difference at position {i}: expected '{e}', got '{a}'")
                break
        
        # Check if actual hash was generated from a different password
        print("\n  Checking if actual hash was generated from a different password...")
        
        # Try to verify the actual hash with the expected salt
        try:
            # bcrypt.checkpw returns True if password matches the hash
            if bcrypt.checkpw(test_password.encode('utf-8'), actual_hash.encode('utf-8')):
                print(f"  ✓ Password '{test_password}' matches the actual hash!")
            else:
                print(f"  ✗ Password '{test_password}' does NOT match the actual hash")
        except Exception as e:
            print(f"  Error checking password: {e}")
        
        # Check if the actual hash was generated from the expected salt
        try:
            actual_generated = bcrypt.hashpw(test_password.encode('utf-8'), expected_salt.encode('utf-8')).decode('utf-8')
            if actual_generated == actual_hash:
                print(f"  ✓ Actual hash was generated from expected salt with password '{test_password}'")
            else:
                print(f"  ✗ Actual hash was NOT generated from expected salt with password '{test_password}'")
                print(f"    Generated from salt: {actual_generated}")
        except Exception as e:
            print(f"  Error: {e}")
        
        print("\n  CONCLUSION:")
        print("  The last login attempt used a DIFFERENT password hash than the one")
        print("  stored during family creation. This indicates either:")
        print("  1. The password was changed between family creation and device removal")
        print("  2. A different password was used for the device removal request")
        print("  3. There was an error in hash generation or storage")
    else:
        print("The hashes are IDENTICAL - no differences found")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print("""
1. BCRYPT HASH VERIFICATION:
   - Password '12345678' with salt '$2a$12$GH3WX.UWo.gdKkWy0j/K9u' produces:
     $2a$12$GH3WX.UWo.gdKkWy0j/K9udedcl/fv9CkSbTRghbIY66Eeo.jY1.K
   - Expected hash: $2a$12$GH3WX.UWo.gdKkWy0j/K9udedcl/fv9CkSbTRghbIY66Eeo.jY1/K
   - The hashes differ by ONE character at the end ('/' vs 'K')
   
2. AUDIT LOG ANALYSIS:
   - Family creation (first login): Used password hash with secondSalt '$2a$12$GH3WX.UWo.gdKkWy0j/K9u'
   - Device removal (last login): Used different hash '$2a$12$BthCKb/Sh4DjQSYkonva5OWQ4xq53flF7LNOnx1xmBKp2b0CxDDZi'
   - The last login attempt used a COMPLETELY DIFFERENT hash, not just a minor variation
   - This indicates the password was changed or a different password was used
""")