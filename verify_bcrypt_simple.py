#!/usr/bin/env python3
import bcrypt

password = '12345678'
salt = '$2a$12$GH3WX.UWo.gdKkWy0j/K9u'
expected = '$2a$12$GH3WX.UWo.gdKkWy0j/K9udedcl/fv9CkSbTRghbIY66Eeo.jY1/K'

print('Password:', password)
print('Salt:', salt)
print('Expected:', expected)

# Generate hash using the provided salt
actual = bcrypt.hashpw(password.encode('utf-8'), salt.encode('utf-8')).decode('utf-8')
print('Actual:', actual)
print('Match:', actual == expected)