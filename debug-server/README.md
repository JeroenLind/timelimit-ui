# Debug Server

A comprehensive debug server for TimeLimit UI testing. This server simulates the TimeLimit backend API (`api.timelimit.io`) for development, testing, and debugging purposes.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Server](#running-the-server)
- [API Documentation](#api-documentation)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Development](#development)
- [Documentation](#documentation)
- [Deployment](#deployment)
- [Maintenance](#maintenance)
- [Security](#security)
- [License](#license)

---

## Overview

The TimeLimit Debug Server provides a complete simulation of the TimeLimit backend API, enabling developers to:

- Test the TimeLimit UI without connecting to the production server
- Develop and debug TimeLimit features locally
- Run integration tests against a simulated backend
- Test authentication flows and sync protocols

### Architecture

The server follows a layered architecture with clear separation of concerns:

```
Client → Middleware → Controllers → Services → Models → Security
```

See [docs/architecture.md](docs/architecture.md) for detailed architecture documentation.

---

## Features

- ✅ Complete TimeLimit API simulation (21 endpoints)
- ✅ JWT-based authentication
- ✅ WebSocket (Socket.IO) support for real-time notifications
- ✅ Gzip compression/decompression
- ✅ HMAC-SHA256 action integrity signing
- ✅ AES-GCM encryption for sensitive data
- ✅ Curve25519 device signing
- ✅ DH key exchange for parent passwords
- ✅ Mock data generation with seed-based reproducibility
- ✅ Comprehensive test suite (42+ tests)
- ✅ Structured JSON logging
- ✅ Rate limiting on authentication endpoints

---

## Prerequisites

- **Python**: 3.11 or higher
- **pip**: Python package manager
- **Operating System**: Windows 11, Linux, or macOS

---

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd debug-server
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (Linux/macOS)
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
# Production dependencies
pip install -r requirements.txt

# Development dependencies (for testing)
pip install -r requirements-dev.txt
```

### 4. Configure Environment

```bash
# Copy example configuration
copy .env.example .env  # Windows
cp .env.example .env    # Linux/macOS

# Edit .env with your configuration
notepad .env  # Windows
nano .env     # Linux/macOS
```

### 5. Generate Secret Key

```bash
# Generate a secure secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Add the generated key to your `.env` file:

```env
SECRET_KEY=your_generated_secret_key_here
```

---

## Configuration

Environment variables are managed through the `.env` file. See [docs/deployment.md](docs/deployment.md) for detailed configuration options.

### Key Configuration Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | (required) | Secret key for JWT token signing |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 60 | JWT token expiration in minutes |
| `BCRYPT_COST` | 12 | Bcrypt hashing cost factor |
| `LOG_LEVEL` | INFO | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `SERVER_HOST` | 0.0.0.0 | Server host address |
| `SERVER_PORT` | 8080 | Server port |
| `ENABLE_WEBSOCKET` | true | Enable Socket.IO support |
| `RATE_LIMIT_ENABLED` | true | Enable rate limiting |

### Mock Data Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MOCK_FAMILY_COUNT` | 1 | Number of families to generate |
| `MOCK_CHILD_COUNT` | 2 | Children per family |
| `MOCK_DEVICE_COUNT` | 3 | Devices per family |
| `MOCK_CATEGORY_COUNT` | 3 | Categories per child |
| `MOCK_APP_COUNT` | 10 | Apps per device |

---

## Running the Server

### Using uvicorn directly

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

### Using the run script

```bash
python run.py
```

### Using the module entry point

```bash
python -m app
```

The server will be available at `http://localhost:8080`.

### Docker Deployment

```bash
# Build the image
docker build -t timelimit-debug-server .

# Run the container
docker run -d \
  --name timelimit-server \
  -p 8080:8080 \
  -v $(pwd)/.env:/app/.env \
  timelimit-debug-server
```

See [docs/deployment.md](docs/deployment.md) for detailed deployment instructions.

---

## API Documentation

Once the server is running, API documentation is available:

- **Swagger UI**: `http://localhost:8080/docs`
- **OpenAPI JSON**: `http://localhost:8080/openapi.json`

### Available Endpoints

#### Health Check

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check endpoint |
| `/ready` | GET | Readiness check endpoint |

#### Time

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/time` | POST | Get server time in milliseconds |

#### Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/send-mail-login-code-v2` | POST | Send verification code to email |
| `/auth/sign-in-by-mail-code` | POST | Sign in with verification code |
| `/parent/get-status-by-mail-address` | POST | Get family status by email |
| `/parent/create-family` | POST | Create a new family |
| `/parent/sign-in-into-family` | POST | Sign in to existing family |
| `/parent/recover-parent-password` | POST | Recover parent password |

#### Sync

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/sync/push-actions` | POST | Push sync actions to server |
| `/sync/pull-status` | POST | Pull server status |
| `/sync/report-removed` | POST | Report device as removed |
| `/sync/is-device-removed` | POST | Check if device is removed |

#### Parent

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/parent/create-add-device-token` | POST | Create add-device token |
| `/parent/remove-device` | POST | Remove a device |
| `/parent/link-mail-address` | POST | Link email to parent account |
| `/parent/create-identity-token` | POST | Create identity token |
| `/parent/delete-account` | POST | Delete parent account |

#### Child

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/child/add-device` | POST | Add a new device |
| `/child/update-primary-device` | POST | Update primary device |
| `/child/logout-at-primary-device` | POST | Logout at primary device |

#### Purchase

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/purchase/can-do-purchase` | POST | Check purchase eligibility |
| `/purchase/finish-purchase-by-google-play` | POST | Complete Google Play purchase |

See [docs/api.md](docs/api.md) for complete API documentation.

---

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_crypto.py -v

# Run specific test class
pytest tests/test_crypto.py::TestPasswordHash -v
```

### Test Categories

| Category | Description | Test Files |
|----------|-------------|------------|
| **Unit Tests** | Test individual components | `test_crypto.py`, `test_auth.py`, `test_mock_data.py`, `test_state.py`, `test_gzip.py`, `test_response.py` |
| **Integration Tests** | Test API endpoints end-to-end | `test_auth_endpoints.py`, `test_sync_endpoints.py`, `test_parent_endpoints.py`, `test_child_endpoints.py`, `test_purchase_endpoints.py` |
| **Security Tests** | JWT, HMAC, encryption validation | `test_crypto.py`, `test_auth.py` |
| **WebSocket Tests** | Socket.IO event handling | `test_websocket.py` |
| **Load Tests** | Performance under load | `test_load.py` |

### Test Client

The test client provides a convenient interface for testing:

```python
from tests.client import TestClient

client = TestClient(base_url="http://localhost:8080")

# Health check
response = client.get_health()

# Send mail login code
response = client.send_mail_login_code("test@example.com")

# Sign in with code
response = client.sign_in_by_mail_code("test@example.com", "123456")
```

See [docs/testing.md](docs/testing.md) for detailed testing documentation.

---

## Project Structure

```
debug-server/
├── app/
│   ├── __init__.py
│   ├── __main__.py              # Module entry point
│   ├── main.py                  # FastAPI application factory
│   ├── config.py                # Configuration management
│   ├── api/                     # API route definitions
│   │   ├── __init__.py
│   │   ├── auth.py              # Authentication endpoints
│   │   ├── sync.py              # Sync protocol endpoints
│   │   ├── parent.py            # Parent management endpoints
│   │   ├── child.py             # Child device endpoints
│   │   ├── purchase.py          # Purchase endpoints
│   │   ├── time.py              # Server time endpoint
│   │   ├── health.py            # Health check endpoints
│   │   └── users.py             # User management endpoints
│   ├── core/                    # Core infrastructure
│   │   ├── __init__.py
│   │   ├── config.py            # Pydantic settings
│   │   ├── logging.py           # Logging setup
│   │   ├── security.py          # JWT, bcrypt, HMAC, AES-GCM, Curve25519
│   │   ├── auth.py              # Authentication logic
│   │   ├── state.py             # In-memory state management
│   │   ├── exceptions.py        # Custom exception classes
│   │   └── deps.py              # Dependency injection
│   ├── models/                  # Data models
│   │   ├── __init__.py
│   │   ├── user.py              # User models
│   │   ├── auth.py              # Authentication models
│   │   ├── sync.py              # Sync models
│   │   ├── parent.py            # Parent models
│   │   ├── child.py             # Child models
│   │   ├── purchase.py          # Purchase models
│   │   ├── category.py          # Category models
│   │   ├── device.py            # Device models
│   │   ├── action.py            # Action models
│   │   └── response.py          # Response wrapper
│   ├── services/                # Business logic
│   │   ├── __init__.py
│   │   ├── auth_service.py      # Authentication service
│   │   ├── sync_service.py      # Sync protocol service
│   │   ├── crypto_service.py    # Crypto service wrapper
│   │   ├── mock_data.py         # Mock data generator
│   │   └── user.py              # User service
│   ├── middleware/              # Cross-cutting middleware
│   │   ├── __init__.py
│   │   ├── logging.py           # Request/response logging
│   │   ├── auth.py              # JWT authentication
│   │   ├── encryption.py        # Encryption monitoring
│   │   ├── security_headers.py  # Security headers
│   │   └── gzip.py              # Gzip compression
│   ├── websocket/               # Socket.IO support
│   │   ├── __init__.py
│   │   ├── manager.py           # Connection management
│   │   └── handlers.py          # Event handlers
│   └── utils/                   # Utility functions
│       ├── __init__.py
│       ├── logger.py            # Structured logging
│       └── helpers.py           # Helper functions
├── tests/                      # Test suite
│   ├── conftest.py              # Pytest fixtures
│   ├── client.py                # Test client
│   ├── config.py                # Test configuration
│   ├── test_crypto.py           # Crypto tests
│   ├── test_auth.py             # Auth tests
│   ├── test_state.py            # State tests
│   ├── test_gzip.py             # Gzip tests
│   ├── test_response.py         # Response tests
│   ├── test_auth_endpoints.py   # Auth endpoint tests
│   ├── test_sync_endpoints.py   # Sync endpoint tests
│   ├── test_parent_endpoints.py # Parent endpoint tests
│   ├── test_child_endpoints.py  # Child endpoint tests
│   ├── test_purchase_endpoints.py # Purchase endpoint tests
│   ├── test_websocket.py        # WebSocket tests
│   ├── test_load.py             # Load tests
│   ├── scenarios/               # Test scenarios
│   └── fixtures/                # Test fixtures
├── docs/                       # Documentation
│   ├── architecture.md          # Architecture documentation
│   ├── api.md                   # API documentation
│   ├── security.md              # Security implementation guide
│   ├── deployment.md            # Deployment instructions
│   ├── maintenance.md           # Maintenance procedures
│   ├── implementation.md        # Implementation guide
│   ├── logging.md               # Logging documentation
│   ├── testing.md               # Testing documentation
│   └── analysis/                # Analysis deliverables
├── scripts/                     # Utility scripts
│   └── analyze_logs.py          # Log analysis script
├── logs/                        # Log file storage
├── requirements.txt             # Production dependencies
├── requirements-dev.txt         # Development dependencies
├── pyproject.toml               # Python project configuration
├── pytest.ini                   # Pytest configuration
├── run.py                       # Entry point script
├── .env.example                 # Environment template
├── .env                         # Environment configuration
└── README.md                    # This file
```

---

## Development

### Code Style

- Follow PEP 8 style guide
- Use type hints on all functions
- Include docstrings on public functions (Google style)
- Use `pathlib.Path` for all file operations

### Development Setup

```bash
# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Start development server with auto-reload
uvicorn app.main:app --reload
```

### Logging

Logs are written to both console (stderr) and file (`logs/debug-server.log`). Use the `LOG_LEVEL` environment variable to control verbosity.

```bash
# View logs in real-time
tail -f logs/debug-server.log

# View recent errors
grep "ERROR" logs/debug-server.log
```

### Adding New Endpoints

1. Create a new controller file in `app/api/`
2. Define Pydantic models in `app/models/`
3. Implement business logic in `app/services/`
4. Register the router in `app/api/__init__.py`
5. Add tests in `tests/test_*_endpoints.py`
6. Update documentation in `docs/api.md`

---

## Documentation

Comprehensive documentation is available in the `docs/` directory:

| Document | Description |
|----------|-------------|
| [architecture.md](docs/architecture.md) | High-level architecture, component diagrams, design decisions |
| [api.md](docs/api.md) | Complete API endpoint documentation |
| [security.md](docs/security.md) | Security implementation guide |
| [deployment.md](docs/deployment.md) | Deployment instructions and procedures |
| [maintenance.md](docs/maintenance.md) | Maintenance procedures and troubleshooting |
| [implementation.md](docs/implementation.md) | Implementation details and coding standards |
| [logging.md](docs/logging.md) | Logging architecture and analysis |
| [testing.md](docs/testing.md) | Testing integration documentation |
| [analysis/endpoint-mapping.md](docs/analysis/endpoint-mapping.md) | Endpoint mapping (UI routes → backend API) |
| [analysis/security-requirements.md](docs/analysis/security-requirements.md) | Security requirements and crypto specifications |
| [analysis/data-models.md](docs/analysis/data-models.md) | Data model specifications |
| [analysis/data-flow-diagrams.md](docs/analysis/data-flow-diagrams.md) | Data flow diagrams (Mermaid) |

---

## Deployment

See [docs/deployment.md](docs/deployment.md) for detailed deployment instructions including:

- Quick start guide
- Docker deployment
- Production deployment (systemd, Windows Service)
- Reverse proxy setup (Nginx)
- HTTPS configuration
- Load balancing
- Monitoring and alerting

---

## Maintenance

See [docs/maintenance.md](docs/maintenance.md) for maintenance procedures including:

- Routine maintenance tasks (daily, weekly, monthly)
- Troubleshooting guide
- Upgrading and rollback procedures
- Adding new endpoints
- Log management
- Performance optimization

---

## Security

See [docs/security.md](docs/security.md) for security implementation details including:

- JWT token management
- Password hashing (bcrypt)
- HMAC integrity signing
- AES-GCM encryption
- Curve25519 cryptography
- Security headers
- Rate limiting
- Security testing

---

## Quick Reference

### Server Management

```bash
# Start server
python run.py

# Stop server (Windows)
taskkill /IM python.exe /F

# Stop server (Linux/macOS)
pkill -f "python -m app"

# Check if server is running
curl http://localhost:8080/health
```

### Common Commands

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=app --cov-report=html

# View logs
tail -f logs/debug-server.log

# Analyze logs
python scripts/analyze_logs.py

# Update dependencies
pip install -r requirements.txt --upgrade
```

### Useful Scripts

```bash
# Log analysis
python scripts/analyze_logs.py --analyze-errors
python scripts/analyze_logs.py --report

# Generate secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## License

This project is part of the TimeLimit UI ecosystem.

---

## Support

For issues and questions:

1. Check the logs: `logs/debug-server.log`
2. Review the documentation in `docs/`
3. Check GitHub issues
4. Contact the development team
