# Dashboard V2 Documentation Index

## Overview

This document provides a comprehensive index of all Dashboard V2 documentation, organized by category and purpose.

---

## Quick Links

| Category | Document | Purpose |
|----------|----------|---------|
| [Getting Started](#getting-started) | README.md | Central documentation hub |
| [Architecture](#architecture) | design.md | System architecture overview |
| [Architecture](#architecture) | data-models.md | Database schema documentation |
| [API](#api-documentation) | ServerAPI.md | External server API |
| [API](#api-documentation) | api-reference.md | Internal API reference |
| [API](#api-documentation) | internal-api.md | Internal dashboard API |
| [Guides](#user-guides) | user-guide.md | End-user documentation |
| [Guides](#user-guides) | admin-guide.md | Administrator documentation |
| [Guides](#user-guides) | deployment-guide.md | Installation instructions |
| [Development](#development) | testing-guide.md | Testing patterns |
| [Development](#development) | coding-standards.md | Code style conventions |
| [Development](#development) | ui-patterns.md | UI component patterns |
| [Development](#development) | logging.md | Logging infrastructure |

---

## Getting Started

### README.md
- **Purpose**: Central documentation hub with table of contents
- **Location**: `docs/README.md`
- **Last Updated**: 2026

### Quick Start Guide
- **Purpose**: Get started quickly with Dashboard V2
- **Location**: `docs/README.md` → Quick Start section

---

## Architecture

### Design Overview (`docs/architecture/design.md`)

**Key Topics**:
- System architecture diagram
- Key design principles
- Authentication flow
- Data flow
- Technical stack
- Environment variables
- Server selection
- Security considerations

**Key Design Principles**:
1. Device Auth Token as Primary Key
2. Offline-First Design
3. Session Persistence
4. CRDT-Based Sync

### Data Models (`docs/architecture/data-models.md`)

**Database Tables**:
| Table | Purpose | Primary Key |
|-------|---------|-------------|
| `server_checks` | Timechecker results | `id` |
| `families` | Family account info | `device_auth_token` |
| `devices` | Device registration | `id` |
| `auth_tokens` | Authentication tokens | `id` |
| `users` | User data from sync | `id` |
| `sync_state` | Sync version tracking | `device_auth_token` |
| `categories` | TimeLimit categories | `id` |
| `connected_devices` | Real-time device tracking | `(device_auth_token, device_id)` |
| `time_limit_rules` | Local time limit rules | `id` |

**Related Documents**:
- [Password Hashing](#password-hashing)
- [Days Bitmask](#days-bitmask)

---

## API Documentation

### Server API (`docs/ServerAPI.md`)

**Purpose**: External server API endpoints (1000+ lines)

**Key Sections**:
- Overview and Key Concepts
- Server Configuration
- Authentication Flow
- External Server API Endpoints
- Dashboard Internal Endpoints
- Sync Protocol
- Data Models
- Error Handling

**Authentication Flow**:
1. Send Mail Login Code
2. Sign In By Mail Code
3. Create Family / Sign In Into Family
4. Recover Parent Password

### API Reference (`docs/api/api-reference.md`)

**Purpose**: Complete API reference with examples

**Key Endpoints**:
- Authentication: `/api/auth/*`
- Family Management: `/api/family/*`
- Device Management: `/api/devices/*`
- User Management: `/api/users/*`
- Dashboard API: `/api/dashboard/*`
- Sync: `/api/sync/*`
- Utility: `/api/time`, `/api/health`

### Internal API (`docs/api/internal-api.md`)

**Purpose**: Internal dashboard API endpoints

**Key Endpoints**:
- Session Status: `GET /api/session/status`
- Server Selection: `POST /select-server`
- Sync Operations: `POST /api/sync/pull`
- Dashboard API: `/api/dashboard/*`

---

## User Guides

### User Guide (`docs/guides/user-guide.md`)

**Purpose**: End-user documentation (300+ lines)

**Key Sections**:
- Getting Started
- Creating a Family
- Logging In as Parent
- Dashboard Overview
- Time Limit Rules
- Adding a User to Family
- Device Management
- Sync Operations
- Backup and Restore
- Session Management
- Server Selection
- Troubleshooting
- Keyboard Shortcuts
- Accessibility

### Admin Guide (`docs/guides/admin-guide.md`)

**Purpose**: Administrator documentation

**Key Sections**:
- User Management
- Device Management
- Category Management
- Time Limit Rules
- Server Configuration
- Data Management
- Backup and Restore
- Password Management
- Audit Logging
- Troubleshooting
- Security Best Practices
- API Access
- Configuration
- Support

### Deployment Guide (`docs/guides/deployment-guide.md`)

**Purpose**: Installation and deployment instructions

**Deployment Options**:
1. Home Assistant Add-on
2. Standalone Deployment
3. Docker Deployment

**Key Sections**:
- Installation
- Configuration Options
- Environment Variables
- Reverse Proxy Configuration
- SSL/TLS Configuration
- Data Persistence
- Troubleshooting
- Monitoring
- Security Considerations

---

## Development

### Testing Guide (`docs/development/testing-guide.md`)

**Purpose**: Testing patterns and practices

**Test Categories**:
- Unit Tests
- Integration Tests
- End-to-End Tests

**Key Topics**:
- Pytest Configuration
- Test Patterns
- Test Data Management
- Running Tests
- Mocking External Services
- Test Fixtures
- Best Practices
- Continuous Integration

**Test Statistics**: 1028 tests passing

### Coding Standards (`docs/development/coding-standards.md`)

**Purpose**: Code style and conventions

**Languages Covered**:
- Python (Flask backend)
- JavaScript (Frontend)
- HTML/CSS

**Key Standards**:
- Indentation
- Line Length
- Naming Conventions
- Docstrings
- Type Hints
- Imports

### UI Patterns (`docs/development/ui-patterns.md`)

**Purpose**: UI component patterns

**Key Patterns**:
- Modal Dialogs
- Alert Messages
- Forms
- Tables
- Confirmation Dialogs
- Data Formatting
- Loading States
- Responsive Design
- Accessibility

### Logging (`docs/logging.md`)

**Purpose**: Logging infrastructure and analysis

**Key Topics**:
- Structured JSON Format
- Log File Locations
- Log Rotation and Retention
- Using Logs to Analyze Problems
- Audit Log Events

---

## Implementation Plans

### Time Limit Rules (`docs/plans/time-limit-rules/implementation-plan.md`)

**Purpose**: Time limit rules implementation documentation

**Key Sections**:
- Feature Description
- API Endpoints
- Database Schema
- Days Bitmask
- Time Format
- Rule Validation
- Sync Protocol
- Frontend Implementation
- Testing
- Implementation Status
- Future Enhancements

**Implementation Status**: ✅ Complete

### Add User to Family (`docs/plans/add-user-to-family/`)

**Purpose**: Add user to family implementation documentation

**Files**:
- `api-design.md` - API design specification
- `ui-design.md` - UI design specification

---

## Additional Documentation

### Create Family Fixes (`docs/create-family-fixes.md`)

**Purpose**: Documentation of fixes applied to create family flow

**Key Fixes**:
1. Add Missing `clientLevel` Field
2. Remove `encrypted` Field from `parentPassword`
3. Remove `locale` Field from Create Family Request
4. Bcrypt Hash Prefix Mismatch
5. Password Validation

### UI Patterns Analysis (`docs/ui-patterns-analysis.md`)

**Purpose**: Analysis of UI patterns for implementing features

### Dashboard V2 Implementation (`docs/dashboardV2-implementation.md`)

**Purpose**: Implementation details and status

---

## Days Bitmask Reference

Days are represented as a bitmask (0-127):

| Bit | Day | Value |
|-----|-----|-------|
| 0 | Monday | 1 |
| 1 | Tuesday | 2 |
| 2 | Wednesday | 4 |
| 3 | Thursday | 8 |
| 4 | Friday | 16 |
| 5 | Saturday | 32 |
| 6 | Sunday | 64 |

**Examples**:
- `127` = Every day
- `1` = Monday only
- `3` = Monday and Tuesday
- `62` = Tuesday through Saturday
- `96` = Weekend only

---

## Password Hashing

Dashboard V2 uses bcrypt for password hashing with the `$2a$` prefix.

### Hash Format

```
$2a$10$<22-character-salt><31-character-hash>
```

### Password Hash Fields

| Field | Purpose |
|-------|---------|
| `parent_password_hash` | First hash, used for general authentication |
| `parent_password_second_hash` | Second hash, used for device removal |
| `parent_password_second_salt` | Salt for regenerating the second hash |

---

## Server Endpoints

| Key | Server | URL |
|-----|--------|-----|
| `local` | Local development | http://192.168.68.30:8080 |
| `official` | Official TimeLimit server | https://api.timelimit.io |
| `debug` | Debug server | http://localhost:8080 |

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FLASK_HOST` | Server host | 0.0.0.0 |
| `FLASK_PORT` | Server port | 8099 |
| `FLASK_DEBUG` | Debug mode | False |
| `LOG_LEVEL` | Logging level | INFO |
| `DATABASE_PATH` | SQLite database path | /data/timelimit_ui_storage.json |
| `SKIP_PORT_CHECK` | Skip port availability check | False |

---

## Database Location

- **Default**: `/data/timelimit_ui_storage.json`
- **Configurable**: Via `DATABASE_PATH` environment variable

---

## Log Files

- **Default**: `/data/logs/dashboard.log`
- **Configurable**: Via `LOG_FILE_PATH` environment variable

---

## Support

For support:
1. Check the logs for error messages
2. Review this documentation
3. Contact TimeLimit support
4. Check GitHub issues

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2024 | Initial documentation structure |
| 1.1.0 | 2026 | Consolidated documentation structure |
| 1.2.0 | 2026 | Updated with comprehensive documentation |

---

## Contributing

When adding new documentation, please:
1. Follow the existing structure
2. Update the table of contents
3. Keep files up to date with code changes
4. Use clear, concise language
5. Include code examples in markdown code blocks