# Implementation Guide

## Overview

This document provides detailed implementation guidance for the TimeLimit Debug Server, including architecture decisions, coding standards, and development workflows.

---

## Architecture Implementation

### Layered Architecture

The server follows a six-layer architecture:

```
Client → Middleware → Controllers → Services → Models → Security
```

Each layer has distinct responsibilities:

| Layer | Responsibility | Key Files |
|-------|---------------|-----------|
| **Client** | HTTP/gzip requests, JWT tokens, Socket.IO | Android App, TimeLimit UI |
| **Middleware** | Cross-cutting concerns | `app/middleware/*.py` |
| **Controllers** | Route handling, request/response | `app/api/*.py` |
| **Services** | Business logic | `app/services/*.py` |
| **Models** | Data structures | `app/models/*.py` |
| **Security** | Crypto operations | `app/core/security.py` |

### Component Implementation Details

#### 1. Middleware Layer

**Logging Middleware** (`app/middleware/logging.py`)

```python
class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        # Generate request ID
        request_id = str(uuid.uuid4())
        
        # Log incoming request
        logger.info("request_started", 
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host
        )
        
        # Process request
        response = await call_next(request)
        
        # Log response
        logger.info("request_completed",
            request_id=request_id,
            status_code=response.status_code,
            duration_ms=duration
        )
        
        return response
```

**Auth Middleware** (`app/middleware/auth.py`)

```python
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        # Check if endpoint requires auth
        if self._requires_auth(request.url.path):
            token = self._extract_token(request)
            payload = validate_token(token)
            
            if not payload:
                raise AuthenticationError("Invalid token")
            
            # Attach to request state
            request.state.user_id = payload.get("sub")
            request.state.device_id = payload.get("device_id")
        
        return await call_next(request)
```

**Gzip Middleware** (`app/middleware/gzip.py`)

```python
class GzipMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        # Decompress request body if gzipped
        if self._is_gzipped_request(request):
            body = await request.body()
            decompressed = gzip.decompress(body)
            request = request._replace(body=decompressed)
        
        # Process request
        response = await call_next(request)
        
        # Compress response if needed
        if self._should_compress(response):
            response.body = gzip.compress(response.body)
            response.headers["Content-Encoding"] = "gzip"
        
        return response
```

#### 2. Controller Layer

Controllers handle HTTP requests and responses:

```python
# app/api/auth.py
from fastapi import APIRouter, Depends
from app.models.auth import SendMailLoginCodeRequest, SendMailLoginCodeResponse
from app.services.auth_service import AuthService

router = APIRouter()

@router.post("/auth/send-mail-login-code-v2", 
             response_model=SendMailLoginCodeResponse)
async def send_mail_login_code(
    request: SendMailLoginCodeRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    result = await auth_service.send_mail_login_code(
        mail_address=request.mailAddress
    )
    return result
```

#### 3. Service Layer

Services implement business logic:

```python
# app/services/auth_service.py
class AuthService:
    def __init__(self, state: StateManager = None):
        self.state = state
    
    async def send_mail_login_code(self, mail_address: str) -> Dict:
        # Generate verification code
        code = self._generate_code()
        
        # Store token
        token = self._generate_token()
        await self.state.store_mail_login_token(token, {
            "mailAddress": mail_address,
            "code": code
        })
        
        # Send email (simulated)
        logger.info("mail_login_code_sent", mail=mail_address)
        
        return {"status": 0, "data": {"mailLoginToken": token}}
```

#### 4. Model Layer

Models define data structures using Pydantic:

```python
# app/models/auth.py
from pydantic import BaseModel, Field
from typing import Optional

class SendMailLoginCodeRequest(BaseModel):
    mailAddress: str = Field(..., description="Email address")

class SendMailLoginCodeResponse(BaseModel):
    status: int = Field(0, description="Response status")
    data: Optional[dict] = Field(None, description="Response data")
```

#### 5. Security Layer

Security functions are centralized in `app/core/security.py`:

```python
# app/core/security.py
import bcrypt
import jwt
from cryptography.hazmat.primitives.asymmetric import x25519

def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    salt = bcrypt.gensalt(rounds=BCRYPT_COST)
    return bcrypt.hashpw(password.encode(), salt).decode()

def generate_token(subject: str, device_id: str = None, 
                   expires_delta: timedelta = None) -> str:
    """Generate JWT token."""
    to_encode = {"sub": subject, "jti": str(uuid.uuid4())}
    if device_id:
        to_encode["device_id"] = device_id
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
        to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=JWT_ALGORITHM)
```

---

## Coding Standards

### Python Style Guide

Follow PEP 8 with these additions:

```python
# Type hints on all functions
def process_action(action: Dict[str, Any]) -> ActionUploadItem:
    ...

# Google-style docstrings
def calculate_hmac_sha256(second_hash: str, seq: int, 
                           device_id: str, action: Dict) -> str:
    """Calculate HMAC-SHA256 for sync action integrity.
    
    Args:
        second_hash: Base64-encoded second hash
        seq: Sequence number
        device_id: Device identifier
        action: Action dictionary
    
    Returns:
        HMAC-SHA256 signature as hex string
    """
    ...

# Use pathlib for file operations
from pathlib import Path

LOG_FILE = Path("logs") / "debug-server.log"
```

### Import Organization

```python
# Standard library
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import uuid4

# Third-party
import bcrypt
import jwt
from cryptography.hazmat.primitives.asymmetric import x25519
from fastapi import FastAPI, Request, APIRouter
from pydantic import BaseModel, Field

# Local imports
from app.core.config import Settings
from app.core.security import hash_password
from app.models.auth import SendMailLoginCodeRequest
```

### Error Handling

```python
from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ValidationError
)

try:
    result = await service.process()
except ValueError as e:
    raise ValidationError(str(e))
except KeyError as e:
    raise NotFoundError(f"Resource not found: {e}")
```

---

## Testing Implementation

### Test Structure

```
tests/
├── conftest.py              # Pytest fixtures
├── client.py                # Test client
├── config.py                # Test configuration
├── test_crypto.py           # Crypto unit tests
├── test_auth.py             # Auth unit tests
├── test_state.py            # State management tests
├── test_gzip.py             # Gzip middleware tests
├── test_response.py         # Response model tests
├── test_auth_endpoints.py   # Auth endpoint integration tests
├── test_sync_endpoints.py   # Sync endpoint integration tests
├── test_parent_endpoints.py # Parent endpoint tests
├── test_child_endpoints.py  # Child endpoint tests
├── test_purchase_endpoints.py # Purchase endpoint tests
├── test_websocket.py        # WebSocket tests
├── test_load.py             # Load tests
├── scenarios/               # JSON test scenarios
│   ├── auth_flow.json
│   ├── sync_flow.json
│   └── crypto_flow.json
└── fixtures/                # Test fixtures
```

### Test Client Pattern

```python
# tests/client.py
class TestClient:
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.token = None
        self.device_token = None
    
    def set_token(self, token: str) -> None:
        self.token = token
    
    def set_device_token(self, token: str) -> None:
        self.device_token = token
    
    async def post(self, endpoint: str, data: Dict = None) -> Dict:
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if self.device_token:
            headers["deviceAuthToken"] = self.device_token
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}{endpoint}",
                json=data,
                headers=headers
            )
            return response.json()
```

### Unit Test Pattern

```python
# tests/test_crypto.py
class TestPasswordHash:
    def test_password_hash(self):
        """Test password hashing produces valid bcrypt hash."""
        password = "test_password_123"
        hashed = hash_password(password)
        
        # Verify hash format
        assert hashed.startswith("$2b$")
        
        # Verify password matches
        assert verify_password(password, hashed)
    
    def test_password_hash_different_salts(self):
        """Test different salts produce different hashes."""
        password = "test_password"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        
        assert hash1 != hash2
```

### Integration Test Pattern

```python
# tests/test_auth_endpoints.py
class TestAuthEndpoints:
    @pytest.mark.asyncio
    async def test_send_mail_login_code(self, client: TestClient):
        """Test sending mail login code."""
        response = await client.send_mail_login_code("test@example.com")
        
        assert response["status"] == 0
        assert "mailLoginToken" in response["data"]
```

---

## WebSocket Implementation

### Connection Manager

```python
# app/websocket/manager.py
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Dict] = {}
        self.lock = asyncio.Lock()
    
    async def connect(self, connection_id: str, device_id: str = None) -> None:
        async with self.lock:
            self.active_connections[connection_id] = {
                "device_id": device_id,
                "connected_at": time.time()
            }
    
    async def disconnect(self, connection_id: str) -> None:
        async with self.lock:
            if connection_id in self.active_connections:
                del self.active_connections[connection_id]
```

### Event Handlers

```python
# app/websocket/handlers.py
async def on_connect(sid: str, environ: Dict = None) -> Dict:
    """Handle new Socket.IO connection."""
    logger.info("socket_connected", sid=sid)
    return {"status": "connected"}

async def on_devicelogin(sid: str, data: Dict) -> Dict:
    """Handle device login via WebSocket."""
    token = data.get("authToken")
    payload = validate_token(token)
    
    if not payload:
        raise AuthenticationError("Invalid token")
    
    device_id = payload.get("device_id")
    await manager.connect(sid, device_id)
    
    return {"status": "connected", "deviceId": device_id}
```

---

## Sync Protocol Implementation

### Action-Based CRDT

The sync protocol uses action-based Conflict-free Replicated Data Types:

```python
# app/services/sync_service.py
class SyncService:
    async def process_actions(self, actions: List[Dict]) -> Dict:
        """Process sync actions with HMAC validation."""
        for action in actions:
            # Validate HMAC
            expected_hmac = calculate_hmac_sha256(
                action["second_hash"],
                action["seq"],
                action["device_id"],
                action["action"]
            )
            
            if not constant_time_compare(action["hmac"], expected_hmac):
                raise ValidationError("Invalid HMAC")
            
            # Process action
            await self._apply_action(action)
        
        return {"shouldDoFullSync": False}
```

### Version Tracking

```python
# app/core/state.py
class StateManager:
    def __init__(self):
        self.sync_versions: Dict[str, str] = {}
        self.lock = asyncio.Lock()
    
    async def increment_sync_version(self, entity_type: str) -> str:
        """Increment and return new version for entity type."""
        async with self.lock:
            current = self.sync_versions.get(entity_type, "0")
            new_version = str(int(current) + 1)
            self.sync_versions[entity_type] = new_version
            return new_version
```

---

## Crypto Implementation

### Password Hashing

```python
# app/core/security.py
BCRYPT_COST = 12

def hash_password(password: str) -> str:
    """Hash password using bcrypt with cost factor 12."""
    salt = bcrypt.gensalt(rounds=BCRYPT_COST)
    return bcrypt.hashpw(password.encode(), salt).decode()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode(),
            hashed_password.encode()
        )
    except Exception:
        return False
```

### JWT Implementation

```python
# app/core/security.py
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

def generate_token(subject: str, device_id: str = None,
                   expires_delta: timedelta = None) -> str:
    """Generate JWT token with standard claims."""
    to_encode = {
        "sub": subject,
        "jti": str(uuid4()),
        "iat": datetime.now(timezone.utc)
    }
    
    if device_id:
        to_encode["device_id"] = device_id
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode["exp"] = expire
    
    return jwt.encode(to_encode, SECRET_KEY, algorithm=JWT_ALGORITHM)
```

### HMAC Implementation

```python
# app/core/security.py
import hmac
import hashlib
import json

def calculate_hmac_sha256(second_hash: str, seq: int,
                           device_id: str, action: Dict) -> str:
    """Calculate HMAC-SHA256 for sync action integrity."""
    # Build message
    message = json.dumps({
        "secondHash": second_hash,
        "seq": seq,
        "deviceId": device_id,
        "action": action
    }, separators=(',', ':'))
    
    # Calculate HMAC
    key = base64.b64decode(second_hash)
    signature = hmac.new(
        key,
        message.encode(),
        hashlib.sha256
    ).digest()
    
    return base64.b64encode(signature).decode()
```

### AES-GCM Implementation

```python
# app/core/security.py
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def encrypt_data(plaintext: bytes, key: bytes) -> bytes:
    """Encrypt data using AES-GCM."""
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext

def decrypt_data(ciphertext: bytes, key: bytes) -> bytes:
    """Decrypt data using AES-GCM."""
    aesgcm = AESGCM(key)
    nonce = ciphertext[:12]
    actual_ciphertext = ciphertext[12:]
    return aesgcm.decrypt(nonce, actual_ciphertext, None)
```

### Curve25519 Implementation

```python
# app/core/security.py
import nacl.signing
import nacl.exceptions

def generate_keypair() -> Tuple[bytes, bytes]:
    """Generate Curve25519 key pair."""
    signing_key = nacl.signing.SigningKey.generate()
    verify_key = signing_key.verify_key
    return bytes(signing_key), bytes(verify_key)

def sign(private_key: bytes, message: bytes) -> bytes:
    """Sign message using Curve25519 private key."""
    signing_key = nacl.signing.SigningKey(private_key)
    signed = signing_key.sign(message)
    return signed.signature

def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """Verify signature using Curve25519 public key."""
    try:
        verify_key = nacl.signing.VerifyKey(public_key)
        verify_key.verify(message, signature)
        return True
    except nacl.exceptions.BadSignatureError:
        return False
```

---

## Mock Data Generation

### Seed-Based Generation

```python
# app/services/mock_data.py
class MockDataGenerator:
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
    
    def generate_family(self, family_id: str) -> Dict:
        """Generate reproducible family data."""
        # Use seed for deterministic output
        name = self.rng.choice(["Smith", "Johnson", "Williams", "Brown"])
        return {
            "id": family_id,
            "name": f"{name} Family",
            "users": [],
            "devices": []
        }
    
    def generate_device(self, device_id: str) -> Dict:
        """Generate reproducible device data."""
        types = ["phone", "tablet", "computer"]
        return {
            "id": device_id,
            "name": f"Device {device_id}",
            "type": self.rng.choice(types)
        }
```

---

## Development Workflow

### Local Development Setup

```bash
# 1. Clone repository
git clone <repo-url>
cd debug-server

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS

# 3. Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 4. Configure environment
copy .env.example .env  # Windows
cp .env.example .env    # Linux/macOS

# 5. Start development server
uvicorn app.main:app --reload
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_crypto.py -v

# Run with verbose output
pytest -v --tb=short
```

### Code Quality

```bash
# Type checking
mypy app/

# Linting
ruff check app/

# Formatting
ruff format app/
```

---

## Deployment Checklist

### Pre-Deployment

- [ ] Update version in `pyproject.toml`
- [ ] Update changelog
- [ ] Run all tests: `pytest`
- [ ] Check for security vulnerabilities: `safety check`
- [ ] Update documentation
- [ ] Create git tag: `git tag vX.Y.Z`

### Deployment

- [ ] Pull latest code on server
- [ ] Create backup
- [ ] Update dependencies
- [ ] Update configuration
- [ ] Restart server
- [ ] Verify health check

### Post-Deployment

- [ ] Run smoke tests
- [ ] Check logs for errors
- [ ] Verify API endpoints
- [ ] Update documentation if needed

---

## Troubleshooting Guide

### Common Issues

#### Import Errors

```bash
# Clear Python cache
find . -type d -name "__pycache__" -exec rm -rf {} +

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

#### Port Conflicts

```bash
# Find process using port
netstat -ano | findstr :8080  # Windows
lsof -i :8080                 # Linux/macOS

# Kill process
taskkill /PID <pid> /F       # Windows
kill -9 <pid>                # Linux/macOS
```

#### Memory Issues

```bash
# Check memory usage
ps aux | grep python

# Increase swap (Linux)
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

---

## Performance Optimization

### Profiling

```python
# Add profiling to endpoints
import cProfile

@app.get("/profile")
async def profile_endpoint():
    profiler = cProfile.Profile()
    profiler.enable()
    
    result = await some_operation()
    
    profiler.disable()
    profiler.dump_stats("profile.prof")
    
    return result
```

### Caching

```python
# Add caching for expensive operations
from functools import lru_cache

@lru_cache(maxsize=128)
def get_cached_data(key: str) -> Dict:
    return expensive_operation(key)
```

### Database Connection Pooling

```python
# For future database integration
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20
)
```

---

## Security Implementation Checklist

- [x] JWT token generation and validation
- [x] bcrypt password hashing (cost 12)
- [x] HMAC-SHA256 action integrity
- [x] AES-GCM encryption for sensitive data
- [x] Curve25519 for device signing
- [x] DH key exchange for parent passwords
- [x] Security headers on all responses
- [x] Rate limiting on auth endpoints
- [x] Input validation with Pydantic
- [x] Log sanitization for sensitive data
- [x] Secure random generation (secrets module)
- [x] Constant-time comparison for HMAC
- [x] Token expiration handling