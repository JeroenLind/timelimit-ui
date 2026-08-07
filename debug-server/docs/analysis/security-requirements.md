# Security Requirements Analysis

## Overview

This document details the security requirements for the TimeLimit backend API simulator. It covers all cryptographic systems, authentication mechanisms, secure communication protocols, and security headers used by the TimeLimit Android app and UI bridge server.

## 1. Password Hashing (bcrypt)

**Source**: `context.md` §338–344, `context_android_app.md` §3.6, §8.10

### Requirements

- **Algorithm**: bcrypt (via jBCrypt on Android, `bcrypt` library in Python)
- **Cost Factor**: 12 (configurable via `BCRYPT_COST` environment variable)
- **Two Salts**: Each parent password is hashed twice:
  - **Primary hash**: `bcrypt.hashpw(password, bcrypt.gensalt(cost=12))` — standard bcrypt hash with auto-generated salt
  - **Secondary hash**: `bcrypt.hashpw(password, secondPasswordSalt)` — bcrypt hash with a specific salt (`secondPasswordSalt`) provided by the server

### ParentPassword Structure

```json
{
    "hash": "<bcrypt hash of password>",
    "secondHash": "<bcrypt hash with second salt, or DH-encrypted>",
    "secondSalt": "<salt for second hash>",
    "encrypted": true/false
}
```

- When DH key is available: `secondHash` is encrypted via DH handshake
- AAD for encryption: `"ParentPassword:<hash>:<secondSalt>"`

### Python Implementation

```python
import bcrypt

# Primary hash
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')

# Secondary hash with specific salt
def hash_password_with_salt(password: str, salt: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), salt.encode('utf-8')).decode('utf-8')

# Verification
def verify_password(password: str, hash_str: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hash_str.encode('utf-8'))
```

## 2. HMAC Signing

**Source**: `context.md` §338–344, `context_android_app.md` §3.6

### HMAC-SHA256 (Binary Format)

Used for sync action integrity verification.

- **Key**: `secondHash` (UTF-8 bytes)
- **Message**: `seq_bytes (8) + device_id_len (4) + device_id_bytes + action_len (4) + action_bytes`
- **Output**: `"password:" + base64(hmac_digest)`

```python
import hmac
import hashlib
import base64
import struct

def calculate_hmac_sha256(second_hash: str, sequence_number: int, device_id: str, encoded_action: str) -> str:
    key = second_hash.encode('utf-8')
    message = (
        struct.pack('>q', sequence_number) +  # 8 bytes, big-endian
        struct.pack('>i', len(device_id)) +   # 4 bytes, big-endian
        device_id.encode('utf-8') +
        struct.pack('>i', len(encoded_action)) +  # 4 bytes, big-endian
        encoded_action.encode('utf-8')
    )
    digest = hmac.new(key, message, hashlib.sha256).digest()
    return "password:" + base64.b64encode(digest).decode('utf-8')
```

### HMAC-SHA512 (Legacy)

Used for legacy sync action signing.

```python
def calculate_hmac_sha512(key_base64: str, message: str) -> str:
    key = base64.b64decode(key_base64)
    digest = hmac.new(key, message.encode('utf-8'), hashlib.sha512).digest()
    return base64.b64encode(digest).decode('utf-8')
```

### SHA512 Hex (Legacy Integrity)

Used for legacy integrity verification.

```python
def calculate_sha512_hex(message: str) -> str:
    return hashlib.sha512(message.encode('utf-8')).hexdigest()
```

## 3. AES-GCM CryptContainer

**Source**: `context.md` §344, `context_android_app.md` §3.6, §8.10

### Requirements

- **Key Size**: 16 bytes (AES-128)
- **Auth Tag**: 128 bits
- **Format Versions**:
  - `FORMAT_LEGACY (0)`
  - `FORMAT_APP_LIST_V2 (1)`
  - `FORMAT_APP_DIFF_V2 (2)`
- **Header**: generation (8 bytes) + counter (8 bytes) + IV (4 bytes) = 20 bytes
- **IV Construction**: `iv (4 bytes) + counter (8 bytes)` = 12 bytes
- **AAD**: generation + format version (2 bytes)
- **Counter**: Prevents replay attacks
- **Generation**: Allows key rotation

### Python Implementation

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os

class CryptContainer:
    FORMAT_LEGACY = 0
    FORMAT_APP_LIST_V2 = 1
    FORMAT_APP_DIFF_V2 = 2

    def encrypt_data(self, plaintext: bytes, key: bytes, generation: int, counter: int, format_version: int) -> bytes:
        iv = os.urandom(4)  # 4 bytes IV
        full_iv = iv + struct.pack('>q', counter)  # 12 bytes total
        aad = struct.pack('>q', generation) + struct.pack('>h', format_version)
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(full_iv, plaintext, aad)
        header = struct.pack('>q', generation) + struct.pack('>q', counter) + iv
        return header + ciphertext

    def decrypt_data(self, data: bytes, key: bytes) -> bytes:
        generation = struct.unpack('>q', data[:8])[0]
        counter = struct.unpack('>q', data[8:16])[0]
        iv = data[16:20]
        full_iv = data[16:20] + data[8:16]  # IV + counter
        aad = struct.pack('>q', generation) + data[20:22]  # generation + format version
        ciphertext = data[20:]
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(full_iv, ciphertext, aad)
```

## 4. Curve25519 Operations

**Source**: `context.md` §344, `context_android_app.md` §3.6, §8.10

### Requirements

- **Key Pair**: 32-byte public + 32-byte private (serialized as 64 bytes)
- **Operations**:
  - `generateKeyPair()` — Generate Curve25519 key pair
  - `getPublicKey()` / `getPrivateKey()` — Extract key components
  - `sign(private_key, message)` — Sign message (64-byte signature)
  - `validateSignature(public_key, message, signature)` — Verify signature
  - `sharedSecret(private_key, public_key)` — Compute ECDH shared secret
- **Library**: WhisperSystems Curve25519 (in Python: `pynacl` or `cryptography`)

### Usage

- **Device Signing Key**: Curve25519 key pair stored in `ConfigurationItem.SigningKey`
  - Only used when server API level ≥ 4
  - Public key uploaded to server via `UploadDevicePublicKeyAction`
  - Used for signing key requests and responses in the key request/response protocol
- **Key Request/Response Protocol**: Multi-device key exchange for sharing decryption keys (for encrypted app lists)

## 5. DH Key Exchange (ECDH secp256r1)

**Source**: `context.md` §344, `context_android_app.md` §3.6, §8.10

### Requirements

- **Curve**: secp256r1 (NIST P-256)
- **Purpose**: Encrypting parent passwords during family creation
- **Library**: `cryptography.hazmat.primitives.asymmetric.ec`

### ServerDhKey Format

```json
{
    "v": "<key version string>",
    "k": "<base64 encoded EC public key>"
}
```

### Process

1. Parse server public key from base64 (X.509 encoded EC point)
2. Generate own keypair (secp256r1)
3. Compute shared secret via ECDH
4. Encrypt data: AES-GCM with 16-byte key (first 16 bytes of shared secret), 12-byte IV, AAD for authentication
5. Output format: `base64(iv + encryptedData) + "." + base64(ownPublicKey) + "." + keyVersion`

### Python Implementation

```python
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import base64
import os

def dh_handshake(server_dh_key: dict) -> dict:
    # Parse server public key
    server_public_key_bytes = base64.b64decode(server_dh_key["k"])
    server_public_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), server_public_key_bytes)

    # Generate own keypair
    own_private_key = ec.generate_private_key(ec.SECP256R1())
    own_public_key = own_private_key.public_key()

    # Compute shared secret
    shared_secret = own_private_key.exchange(ec.ECDH(), server_public_key)

    return {
        "private_key": own_private_key,
        "public_key": own_public_key,
        "shared_secret": shared_secret,
        "key_version": server_dh_key["v"]
    }

def dh_encrypt(crypt_data: bytes, auth_data: bytes, server_dh_key: dict) -> str:
    handshake = dh_handshake(server_dh_key)
    key = handshake["shared_secret"][:16]  # First 16 bytes
    iv = os.urandom(12)
    aesgcm = AESGCM(key)
    encrypted = aesgcm.encrypt(iv, crypt_data, auth_data)
    return (
        base64.b64encode(iv + encrypted).decode('utf-8') + "." +
        base64.b64encode(handshake["public_key"].public_bytes(
            encoding=ec.Encoding.X962,
            format=ec.PublicFormat.UncompressedPoint
        )).decode('utf-8') + "." +
        handshake["key_version"]
    )
```

## 6. JWT Token Management

**Source**: `context.md` §344, `context_android_app.md` §3.7

### Requirements

- **Algorithm**: HS256 (configurable via `JWT_ALGORITHM`)
- **Library**: `python-jose[cryptography]`
- **Claims**:
  - `sub` — Subject (user ID)
  - `device_id` — Device ID
  - `exp` — Expiration timestamp
  - `iat` — Issued at timestamp
  - `jti` — JWT ID (unique identifier)
- **Expiration**: Configurable via `JWT_EXPIRATION_MINUTES` (default: 60)
- **Secret Key**: Generated via `secrets` module, stored in `JWT_SECRET_KEY`

### Token Flow

1. **Generation**: After successful authentication (family creation or device registration), server generates a JWT with device claims
2. **Validation**: Middleware extracts JWT from `Authorization: Bearer <token>` header, verifies signature, checks expiration
3. **Protected Endpoints**: `/sync/*`, `/parent/*`, `/child/*`, `/purchase/*` require valid JWT

## 7. Secure Headers

**Source**: `context.md` §344

### Requirements

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | Prevent MIME type sniffing |
| `X-Frame-Options` | `DENY` | Prevent clickjacking |
| `Content-Security-Policy` | `default-src 'none'` | Restrict resource loading |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Enforce HTTPS (if HTTPS enabled) |
| `X-XSS-Protection` | `1; mode=block` | Enable browser XSS filtering |

## 8. HTTPS/TLS Enforcement

**Source**: `context.md` §344, `context_android_app.md` §3.3

### Requirements

- **Production**: HTTPS/TLS enforced with certificate pinning
  - Pins ISRG Root X1, X2, YE, YR (Let's Encrypt) for `api.timelimit.io`, `update.timelimit.io`, and `api.timelimitapp.de`
  - Custom DNS resolver queries both `api.timelimit.io` and `api.timelimitapp.de` for redundancy
- **Development**: No certificate pinning, platform-trusted certificates only, system DNS
- **Test Server**: HTTPS configurable via `ENABLE_HTTPS` environment variable (default: `false` for local testing)

## 9. Authentication Flow Security

**Source**: `context.md` §333–344, `context_android_app.md` §3.7, §8.4

### Multi-Step Authentication

1. **Email Verification**: User enters email → server sends verification code
2. **Code Validation**: User enters code → server returns `mailAuthToken`
3. **Family Creation/Sign-in**: `mailAuthToken` used to create or join a family
4. **Device Registration**: Server returns `deviceAuthToken` for API access
5. **Session Management**: `deviceAuthToken` used for all subsequent API calls

### Security Properties

- **Login Before Data Retrieval**: All data retrieval endpoints (`/sync/*`, `/parent/*`, `/child/*`, `/purchase/*`) require a valid `deviceAuthToken`
- **Token Uniqueness**: Each device gets a unique `deviceAuthToken`
- **Token Expiration**: JWT tokens have configurable expiration (default: 60 minutes)
- **Rate Limiting**: Auth endpoints should implement rate limiting (configurable via `RATE_LIMIT_ENABLED` and `RATE_LIMIT_REQUESTS_PER_MINUTE`)

## 10. Threat Model

**Source**: `context.md` §344, `context_android_app.md` §3.6

### Potential Threats

| Threat | Description | Mitigation |
|--------|-------------|------------|
| Token Theft | JWT or deviceAuthToken intercepted | HTTPS/TLS, short token expiration, token rotation |
| Replay Attacks | Actions replayed by attacker | HMAC integrity, sequence numbers, counter in CryptContainer |
| Man-in-the-Middle | Network interception | HTTPS/TLS with certificate pinning (production) |
| Brute Force | Password guessing | bcrypt cost factor 12, rate limiting on auth endpoints |
| Data Tampering | Sync actions modified in transit | HMAC-SHA256 integrity verification |
| Unauthorized Access | Access to protected endpoints without auth | JWT validation middleware, 401 on missing/invalid tokens |

### Mitigation Strategies

- **JWT Expiration**: Tokens expire after configurable time (default: 60 minutes)
- **HTTPS**: Enforced in production, configurable for local testing
- **Rate Limiting**: Configurable rate limiting on auth endpoints
- **HMAC Integrity**: All sync actions signed with HMAC-SHA256
- **bcrypt**: Password hashing with cost factor 12
- **AES-GCM**: Authenticated encryption for sensitive data
- **Curve25519**: Device signing keys for key request/response protocol
- **DH Key Exchange**: ECDH secp256r1 for parent password encryption

## 11. Security Guidelines

**Source**: `context.md` §344, `context_android_app.md` §3.6

### Implementation Guidelines

1. **Never log passwords, tokens, or sensitive data in plaintext**
2. **Use `secrets` module for generating random tokens**
3. **Validate all input data with Pydantic models**
4. **Implement rate limiting for auth endpoints**
5. **Use secure random for JWT secret key generation**
6. **Enforce HTTPS in production (configurable for local testing)**
7. **Sanitize sensitive data in logs** (passwords, tokens, secondHash)
8. **Log request ID for correlation** (UUID per request)
9. **Log authentication attempts** (success/failure)
10. **Log token validation failures**
11. **Log rate limit violations**
12. **Log suspicious activity** (multiple failed auth attempts)
