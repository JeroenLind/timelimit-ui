#!/usr/bin/env python3
import bcrypt

password = '12345678'
salt = '$2a$12$GH3WX.UWo.gdKkWy0j/K9u'
expected_hash = '$2a$12$GH3WX.UWo.gdKkWy0j/K9udedcl/fv9CkSbTRghbIY66Eeo.jY1/K'

password_bytes = password.encode('utf-8')
salt_bytes = salt.encode('utf-8')

actual_hash = bcrypt.hashpw(password_bytes, salt_bytes).decode('utf-8')

print('Password:', password)
print('Salt:', salt)
print('Expected Hash:', expected_hash)
print('Actual Hash:', actual_hash)
print('Expected length:', len(expected_hash))
print('Actual length:', len(actual_hash))
print('Match:', actual_hash == expected_hash)

# Check if expected hash is valid bcrypt
print()
print('Checking if expected hash is valid bcrypt format:')
print('Expected hash starts with $2a$12$:', expected_hash.startswith('$2a$12$'))
print('Expected hash length is 60:', len(expected_hash) == 60)

# Try to verify the expected hash against the password
try:
    expected_bytes = expected_hash.encode('utf-8')
    result = bcrypt.checkpw(password_bytes, expected_bytes)
    print('bcrypt.checkpw result:', result)
except Exception as e:
    print('Error checking expected hash:', e)

# Try to verify the actual hash against the password
try:
    actual_bytes = actual_hash.encode('utf-8')
    result = bcrypt.checkpw(password_bytes, actual_bytes)
    print('bcrypt.checkpw result for actual:', result)
except Exception as e:
    print('Error checking actual hash:', e)