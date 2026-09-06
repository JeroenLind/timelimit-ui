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
print('Match:', actual_hash == expected_hash)

# Also verify the primary hash
primary_hash = '$2a$12$mXJZGbKUlLVlAhIleE96H.hbKUliS0Iae52DrH45JA9lD6iD4.wg.'
# The primary hash uses a different salt - let's extract it
primary_salt = primary_hash[:29]  # $2a$12$ + 22 char salt
print()
print('Primary Hash:', primary_hash)
print('Primary Salt:', primary_salt)
actual_primary = bcrypt.hashpw(password_bytes, primary_salt.encode('utf-8')).decode('utf-8')
print('Actual Primary:', actual_primary)
print('Primary Match:', actual_primary == primary_hash)