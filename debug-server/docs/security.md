# Security Implementation Guide

## Overview

This document provides comprehensive documentation for the security implementation in the TimeLimit Debug Server. It covers authentication, authorization, cryptographic operations, and security best practices.

---

## Security Architecture

### Security Layers

The TimeLimit Debug Server implements a defense-in-depth security model with multiple layers:

```
┌─────────────────────────────────────────────────────────┐
│                    Client (Android App)                  │
│  JWT tokens, HMAC signatures, encrypted payloads         │
├─────────────────────────────────────────────────────────┤
│              API Gateway / Middleware Layer              │
│  AuthMiddleware, SecurityHeadersMiddleware, Rate limiting │
├─────────────────────────────────────────────────────────┤
│              Controller / Router Layer                   │
│  Request validation, response formatting                 │
├─────────────────────────────────────────────────────────┤
│              Service / Business Logic Layer              │
│  AuthService, SyncService, CryptoService               │
├─────────────────────────────────────────────────────────┤
│              Security / Crypto Layer                     │
│  JWT, bcrypt, HMAC, AES-GCM, Curve25519, DH            │
└─────────────────────────────────────────────────────────┘
```

---

## Authentication

### JWT Token Management

The server uses JWT (JSON Web Tokens) for stateless authentication.

#### Token Generation

```python
from app.core.security import generate_token

# Generate access token
token = generate_token(
    subject="user_123",
    device_id="device_456",
    expires_delta=timedelta(minutes=60)
)
```

#### Token Claims

| Claim | Type | Description |
|-------|------|-------------|
| `sub` | string | Subject (user ID) |
| `device_id` | string | Device identifier |
| `exp` | int | Expiration timestamp |
| `iat` | int | Issued at timestamp |
| `jti` | string | JWT ID (unique identifier) |

#### Token Validation

```python
from app.core.security import validate_token

# Validate token
payload = validate_token(token)
if payload:
    user_id = payload.get("sub")
    device_id = payload.get("device_id")
```

#### Token Expiration

Tokens expire after a configurable period (default: 60 minutes). The `ACCESS_TOKEN_EXPIRE_MINUTES` environment variable controls this.

### Authentication Middleware

The `AuthMiddleware` protects sensitive endpoints:

- `/sync/*` - Sync protocol endpoints
- `/parent/*` - Parent management endpoints
- `/child/*` - Child device endpoints
- `/purchase/*` - Purchase endpoints

```python
# app/middleware/auth.py
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        # Extract token from Authorization header
        # Validate token signature and expiration
        # Attach user/device info to request state
        # Return 401 if invalid
```

---

## Password Security

### Bcrypt Hashing

The server uses bcrypt for password hashing with a cost factor of 12.

#### Hashing a Password

```python
from app.core.security import hash_password

hashed = hash_password("user_password")
# Output: $2b$12$...
```

#### Verifying a Password

```python
from app.core.security import verify_password

is_valid = verify_password("user_password", hashed_password)
```

#### Two-Salt System

TimeLimit uses a two-salt system for enhanced security:

1. **Primary Salt**: Generated from user ID and device ID
2. **Secondary Salt**: Generated from server configuration

```python
from app.core.security import hash_password_with_salt

# Hash with specific salt
hashed = hash_password_with_salt("password", "salt_value")
```

### Password Requirements

- Minimum length: 6 characters
- Bcrypt cost factor: 12 (configurable via `BCRYPT_COST`)
- Two independent salts for additional security

---

## HMAC Integrity Signing

### Purpose

HMAC (Hash-based Message Authentication Code) is used to sign sync actions, ensuring data integrity and preventing tampering.

### HMAC-SHA256 for Sync Actions

```python
from app.core.security import calculate_hmac_sha256

# Calculate HMAC for sync action
hmac = calculate_hmac_sha256(
    second_hash="base64_encoded_second_hash",
    seq=123,
    device_id="device_456",
    action={"type": "AddCategoryAction", "category": {...}}
)
```

### HMAC Format

The HMAC is calculated over:
1. Second hash (base64 encoded)
2. Sequence number
3. Device ID
4. Action JSON

### HMAC-SHA512 (Legacy)

```python
from app.core.security import calculate_hmac_sha512

hmac = calculate_hmac_sha512(
    key_base64="base64_key",
    message="message_to_sign"
)
```

---

## AES-GCM Encryption

### Purpose

AES-GCM (Advanced Encryption Standard - Galois/Counter Mode) provides authenticated encryption for sensitive data like app lists and parent passwords.

### CryptContainer Format

The server supports multiple CryptContainer format versions:

| Version | Constant | Description |
|---------|----------|-------------|
| 0 | `FORMAT_LEGACY` | Legacy format |
| 1 | `FORMAT_APP_LIST_V2` | App list v2 format |
| 2 | `FORMAT_APP_DIFF_V2` | App diff v2 format |

### Encryption/Decryption

```python
from app.core.security import encrypt_data, decrypt_data

# Encrypt data
ciphertext = encrypt_data(plaintext, key)

# Decrypt data
plaintext = decrypt_data(ciphertext, key)
```

### CryptContainer Class

```python
from app.core.security import CryptContainer

# Create container
container = CryptContainer(
    format_version=CryptContainer.FORMAT_APP_LIST_V2,
    data=b"encrypted_data",
    nonce=b"nonce_value"
)

# Serialize to bytes
serialized = container.to_bytes()

# Deserialize from bytes
container = CryptContainer.from_bytes(serialized)
```

---

## Curve25519 Cryptography

### Purpose

Curve25519 is used for device signing keys and the key request/response protocol in the sync process.

### Key Pair Generation

```python
from app.core.security import generate_keypair

private_key, public_key = generate_keypair()
# private_key: 32 bytes
# public_key: 32 bytes
```

### Signing

```python
from app.core.security import sign

signature = sign(private_key, message)
```

### Verification

```python
from app.core.security import verify

is_valid = verify(public_key, message, signature)
```

### Shared Secret (ECDH)

```python
from app.core.security import shared_secret

# Compute shared secret
secret = shared_secret(private_key, public_key)
```

---

## DH Key Exchange

### Purpose

DH (Diffie-Hellman) key exchange with secp256r1 curve is used for encrypting parent passwords during family creation.

### Key Exchange Process

```python
from app.core.security import dh_handshake, dh_encrypt

# Perform DH handshake
result = dh_handshake(server_dh_key)

# Encrypt data using DH
encrypted = dh_encrypt(
    crypt_data={"password": "encrypted_password"},
    auth_data={"deviceId": "device_456"},
    server_dh_key=server_dh_key
)
```

---

## Security Headers

The `SecurityHeadersMiddleware` adds the following headers to all responses:

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | Prevents MIME type sniffing |
| `X-Frame-Options` | `DENY` | Prevents clickjacking |
| `Content-Security-Policy` | `default-src 'none'` | Restricts resource loading |
| `Strict-Transport-Security` | `max-age=31536000` | Enforces HTTPS (when enabled) |
| `X-XSS-Protection` | `1; mode=block` | XSS protection |

---

## Rate Limiting

Rate limiting protects authentication endpoints from brute-force attacks.

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `RATE_LIMIT_ENABLED` | `true` | Enable/disable rate limiting |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | `60` | Max requests per minute |

### Implementation

```python
# Rate limiting is applied to /auth/* endpoints
# Returns 429 Too Many Requests when exceeded
```

---

## Data Sanitization

### Log Sanitization

Sensitive data is sanitized in logs:

- Passwords
- JWT tokens
- Second hash values

```python
from app.utils.logger import _sanitize_dict

# Sanitize sensitive data before logging
sanitized = _sanitize_dict(data)
```

---

## Security Best Practices

### 1. Environment Variables

Never hardcode secrets. Use environment variables:

```bash
# .env file
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=60
BCRYPT_COST=12
```

### 2. HTTPS in Production

Enable HTTPS for production deployments:

```bash
ENABLE_HTTPS=true
```

### 3. Secure Token Storage

Store JWT tokens securely on the client side:

- Use secure, httpOnly cookies for web clients
- Use Android Keystore for Android apps
- Never store tokens in localStorage for web apps

### 4. Token Rotation

Implement token rotation:

- Short-lived access tokens (60 minutes default)
- Refresh tokens for longer sessions
- Invalidate tokens on logout

### 5. Input Validation

Always validate input:

```python
from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    email: EmailStr
    password: str  # Pydantic validates this
```

---

## Threat Model

### Identified Threats

| Threat | Mitigation |
|--------|------------|
| Token theft | Short expiration, secure storage |
| Brute force | Rate limiting, bcrypt cost factor |
| Data tampering | HMAC signatures, AES-GCM |
| Man-in-the-middle | HTTPS, secure random generation |
| Replay attacks | Sequence numbers, timestamps |
| Injection attacks | Pydantic validation, parameterized queries |

### Security Controls

| Control | Implementation |
|---------|----------------|
| Authentication | JWT with HS256 |
| Authorization | Device-specific tokens |
| Integrity | HMAC-SHA256 |
| Confidentiality | AES-GCM |
| Non-repudiation | Curve25519 signatures |
| Key exchange | ECDH secp256r1 |

---

## Security Testing

### Running Security Tests

```bash
# Run all security tests
pytest tests/test_crypto.py tests/test_auth.py -v

# Run specific security tests
pytest tests/test_crypto.py::TestPasswordHash -v
pytest tests/test_crypto.py::TestAccessToken -v
```

### Security Test Coverage

| Test Category | Description |
|---------------|-------------|
| Password hashing | bcrypt cost factor, salt uniqueness |
| JWT validation | Token expiration, signature verification |
| HMAC integrity | Action tampering detection |
| Encryption | AES-GCM round-trip, nonce uniqueness |
| Curve25519 | Key generation, signing, verification |
| DH key exchange | Shared secret computation |

---

## Compliance

### GDPR Considerations

- Data is stored in-memory only (no persistent storage)
- State resets on server restart
- No personal data retention policy needed

### Security Standards

The implementation follows:
- OWASP Top 10 security practices
- NIST cryptographic standards
- RFC 7519 (JWT)
- RFC 2104 (HMAC)

---

## Security Checklist

- [x] JWT tokens with expiration
- [x] bcrypt password hashing (cost 12)
- [x] HMAC-SHA256 action integrity
- [x] AES-GCM encryption for sensitive data
- [x] Curve25519 for device signing
- [x] DH key exchange for parent passwords
- [x] Security headers on all responses
- [x] Rate limiting on auth endpoints
- [x] Input validation with Pydantic
- [x] Log sanitization for sensitive data
- [x] HTTPS support (configurable)
- [x] Secure random generation (secrets module)