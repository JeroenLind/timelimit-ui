# Dashboard V2 Documentation

Welcome to the Dashboard V2 documentation. This is the central hub for all documentation related to the TimeLimit UI Dashboard V2 application.

## Table of Contents

### Getting Started
- [Overview](#overview) - Introduction to Dashboard V2
- [Quick Start](#quick-start) - Getting started quickly
- [System Requirements](#system-requirements) - Prerequisites for running Dashboard V2

### Architecture
- [Design Overview](architecture/design.md) - High-level architecture and design decisions
- [Data and cache](architecture/design.md#4-data-and-cache) - Cache design (schema details: `archive/design-v1-2026-09.md`)
- [Technical Stack](#technical-stack) - Technologies used in the project

### API Documentation
- [Server API](ServerAPI.md) - External server API endpoints (1000+ lines)
- [Internal API](api/internal-api.md) - Internal dashboard API endpoints
- [API Reference](api/api-reference.md) - Complete API reference with examples
- [Authentication Flow](#authentication-flow) - How authentication works
- [Sync Protocol](#sync-protocol) - CRDT-based synchronization

### User Guides
- [User Guide](guides/user-guide.md) - End-user documentation (300+ lines)
- [Admin Guide](guides/admin-guide.md) - Administrator documentation
- [Deployment Guide](guides/deployment-guide.md) - Installation and deployment instructions
- [Time Limit Rules User Guide](time-limit-rules-user-guide.md) - Time limit rules usage

### Development
- [Testing Guide](development/testing-guide.md) - Testing patterns and practices
- [UI Patterns](development/ui-patterns.md) - UI component patterns
- [Coding Standards](development/coding-standards.md) - Code style and conventions
- [Logging](logging.md) - Logging infrastructure and analysis

### Implementation Plans
- [Add User to Family](plans/add-user-to-family/) - Implementation documentation
  - [API Design](plans/add-user-to-family/api-design.md)
  - [UI Design](plans/add-user-to-family/ui-design.md)
- [Time Limit Rules](plans/time-limit-rules/) - Time limit rules implementation
  - [Implementation Plan](plans/time-limit-rules/implementation-plan.md)

### Additional Documentation
- [Dashboard V2 Implementation](dashboardV2-implementation.md) - Implementation details
- [Create Family Fixes](create-family-fixes.md) - Fixes for family creation flow

## Overview

Dashboard V2 is a Flask-based web application that provides a modern interface for managing TimeLimit families and devices. The application features:

- **Device Auth Token Authentication**: Primary authentication mechanism using device tokens
- **Offline-First Design**: Local SQLite database enables offline operation
- **CRDT Synchronization**: Conflict-free Replicated Data Type protocol with HMAC-SHA256 integrity signing
- **Server-Sent Events**: Real-time updates for connected devices
- **Time Limit Rules**: Configure time-based restrictions for child users

## Quick Start

### Accessing the Dashboard

1. Open your web browser
2. Navigate to `http://localhost:8099` (or your configured host:port)
3. You'll see the landing page with two options:
   - **Create Family** - For new users
   - **Login as Parent** - For existing families

### Creating a Family

1. Click **Create Family**
2. Enter your email address
3. Check your email for the verification code
4. Enter the 3-word verification code
5. Set your password (minimum 8 characters)
6. Enter your name and device information
7. Click **Create Family**

### Logging In as Parent

1. Click **Login as Parent**
2. Enter your email address
3. Check your email for the verification code
4. Enter the 3-word verification code
5. Enter your device info
6. Optionally set your password for device removal

## Technical Stack

| Layer | Technology |
|-------|------------|
| Backend | Flask (Python 3.x) |
| Database | SQLite |
| Frontend | HTML5, CSS3, JavaScript (ES6+) |
| Authentication | bcrypt password hashing |
| Sync Protocol | CRDT with HMAC-SHA256 |
| Logging | structlog with rotation |
| Scheduling | APScheduler |

## Authentication Flow

```
1. Enter Email → 2. Verify Code → 3. Create Family / Sign In
       │               │                     │
       ▼               ▼                     ▼
   Send Mail     Verify Code          Create Family
   Login Code    to Server            or Sign In
                 with 3-word code
```

### Key Authentication Concepts

- **device_auth_token**: Primary authentication token for all server requests
- **mail_auth_token**: Temporary token for email-based authentication
- **parent_password_second_hash**: Second password hash for device removal operations
- **clientLevel**: Client version level (typically 7)

## Sync Protocol

Dashboard V2 uses a CRDT (Conflict-free Replicated Data Type) synchronization protocol with HMAC-SHA256 integrity signing:

1. Generate unique action ID
2. Create action with HMAC signature
3. Push to server via sync endpoint
4. Server validates and applies changes
5. Pull updated state from server

## Database Schema

Dashboard V2 uses SQLite with 8 tables for local data storage:

| Table | Purpose | Primary Key |
|-------|---------|-------------|
| `server_checks` | Timechecker results | `id` (AUTOINCREMENT) |
| `families` | Family account information | `device_auth_token` |
| `devices` | Device registration data | `id` |
| `auth_tokens` | Authentication tokens | `id` (AUTOINCREMENT) |
| `users` | User data from TimeLimit sync | `id` |
| `sync_state` | Sync version tracking | `device_auth_token` |
| `categories` | TimeLimit categories | `id` |
| `connected_devices` | Real-time connected device tracking | `(device_auth_token, device_id)` |
| `time_limit_rules` | Local time limit rules | `id` |

See [Architecture – Data and cache](architecture/design.md#4-data-and-cache); the 2026-09 schema reference is `archive/design-v1-2026-09.md`.

## Server Selection

The application supports multiple server endpoints:

| Key | Server | URL |
|-----|--------|-----|
| `local` | Local development | http://192.168.68.30:8080 |
| `official` | Official TimeLimit server | https://api.timelimit.io |
| `debug` | Debug server | http://localhost:8080 |

Server selection persists across restarts via file-based storage.

## Quick Links

- [Server API Reference](ServerAPI.md) - Complete external API documentation
- [API Reference](api/api-reference.md) - Internal API endpoints
- [Testing Guide](development/testing-guide.md) - How to run tests
- [UI Patterns](development/ui-patterns.md) - UI component patterns
- [Deployment Guide](guides/deployment-guide.md) - Installation instructions

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2024 | Initial documentation structure |
| 1.1.0 | 2026 | Consolidated documentation structure |
| 1.2.0 | 2026 | Updated with comprehensive documentation |

## Contributing

When adding new documentation, please follow the existing structure and ensure all files are kept up to date with code changes.

### Documentation Style Guide

- Use clear, concise language
- Include code examples in markdown code blocks
- Use tables for structured data
- Link to related documentation
- Keep documentation version-controlled with code

## Support

For issues or questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review the [Testing Guide](development/testing-guide.md)
3. Check the [GitHub Issues](https://github.com/timelimit-ui/timelimit-ui/issues)

## Troubleshooting

### Common Issues

- **Cannot connect to server**: Check server URL and network connectivity
- **Authentication failed**: Verify email and verification code
- **Sync errors**: Check network connection and server status
- **Device not found**: Ensure device is registered in the family

### Getting Help

1. Check the [Admin Guide](guides/admin-guide.md) for device management
2. Review the [Deployment Guide](guides/deployment-guide.md) for installation issues
3. Check logs in `/data/logs/` directory