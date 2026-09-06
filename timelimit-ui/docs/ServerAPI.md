# ServerAPI.md - TimeLimit Dashboard V2 External Server API Interface Specification

This document describes all API interfaces between the TimeLimit Dashboard V2 and the external TimeLimit backend server. It serves as the definitive reference for all external server API endpoints, their request/response formats, and usage patterns.

---

## Table of Contents

1. [Overview](#overview)
2. [Server Configuration](#server-configuration)
3. [Authentication Flow](#authentication-flow)
4. [External Server API Endpoints](#external-server-api-endpoints)
5. [Dashboard Internal Endpoints](#dashboard-internal-endpoints)
6. [Sync Protocol](#sync-protocol)
7. [Data Models](#data-models)
8. [Error Handling](#error-handling)

---

## Overview

The TimeLimit Dashboard V2 communicates with the external TimeLimit backend server to manage families, devices, users, and categories. The dashboard acts as a client that:

- Authenticates users via email verification codes
- Creates and manages families
- Syncs device and user data
- Handles device registration and removal

### Key Concepts

- **device_auth_token**: Primary authentication token for all server requests
- **mail_auth_token**: Temporary token for email-based authentication
- **own_device_id**: Unique identifier for the dashboard device
- **parent_password_second_hash**: Second password hash for device removal operations
- **clientLevel**: Client version level (typically 7)

---

## Server Configuration

The dashboard can connect to different server endpoints:

| Server Key | Name | URL |
|------------|------|-----|
| `local` | 🏠 Lokaal | `http://192.168.68.30:8080` |
| `official` | 🌍 Officieel | `https://api.timelimit.io` |
| `debug` | 🐛 Debug Server | `http://192.168.68.30:8080` |

---

## Authentication Flow

### 1. Send Mail Login Code

Request a verification code to be sent to an email address.

**Endpoint:** `POST /api/v1/auth/send-mail-login-code-v2`

**Request:**
```json
{
    "mail": "user@example.com",
    "locale": "en",
    "deviceAuthToken": "optional_token"
}
```

**Response:**
```json
{
    "mailLoginToken": "token_abc123"
}
```

---

### 2. Sign In By Mail Code

Exchange the verification code for a mail auth token.

**Endpoint:** `POST /api/v1/auth/sign-in-by-mail-code`

**Request:**
```json
{
    "mailLoginToken": "token_abc123",
    "receivedCode": "Pferd Miete abwenden"
}
```

**Response:**
```json
{
    "mailAuthToken": "auth_token_xyz789"
}
```

---

### 3. Create Family

Create a new family with the parent account.

**Endpoint:** `POST /api/v1/parent/create-family`

**Request:**
```json
{
    "mailAuthToken": "auth_token_xyz789",
    "parentPassword": {
        "hash": "$2a$12$...",
        "secondHash": "$2a$12$...",
        "secondSalt": "salt...",
        "encrypted": false
    },
    "parentDevice": {
        "model": "Pixel 7"
    },
    "deviceName": "Parent's Phone",
    "timeZone": "Europe/Amsterdam",
    "parentName": "John Doe",
    "clientLevel": 7
}
```

**Response:**
```json
{
    "deviceAuthToken": "device_token_abc123",
    "ownDeviceId": "device_id_xyz789"
}
```

---

### 4. Sign In Into Family

Sign in to an existing family.

**Endpoint:** `POST /api/v1/parent/sign-in-into-family`

**Request:**
```json
{
    "mailAuthToken": "auth_token_xyz789",
    "parentDevice": {
        "model": "Pixel 7"
    },
    "deviceName": "Parent's Phone",
    "clientLevel": 7
}
```

**Note:** The `parentPasswordSecondHash` field is **optional** for email-based sign-in. It is only required for device removal operations.

**Response:**
```json
{
    "deviceAuthToken": "device_token_abc123",
    "ownDeviceId": "device_id_xyz789"
}
```

---

### 5. Recover Parent Password

Recover parent password using a mail auth token.

**Endpoint:** `POST /api/v1/parent/recover-parent-password`

**Request:**
```json
{
    "mailAuthToken": "auth_token_xyz789",
    "newPassword": {
        "hash": "$2a$12$...",
        "secondHash": "$2a$12$...",
        "secondSalt": "$2a$12$salt..."
    }
}
```

**Response:**
```json
{
    "ok": true
}
```

**Note:** The password must be pre-hashed using bcrypt with `$2a$` prefix and 12 rounds. The server sends a confirmation email after successful password recovery.

---

## Sequence Diagrams

### Authentication Flow Sequence Diagram

```mermaid
sequenceDiagram
    participant User as User
    participant UI as Dashboard UI
    participant Client as AuthClient
    participant Server as Debug Server
    participant Email as Email Service

    Note over User,Email: Step 1: Send Mail Login Code
    User->>UI: Enter email address
    UI->>Client: send_mail_login_code(mail, locale)
    Client->>Server: POST /api/v1/auth/send-mail-login-code-v2
    Server->>Email: Send 3-word verification code
    Email->>User: Email with code (e.g., "Pferd Miete abwenden")
    Server-->>Client: {mailLoginToken: "token_abc123"}
    Client-->>UI: APIResponse(success, data)
    UI->>User: Show step 2 (enter verification code)

    Note over User,Email: Step 2: Sign In By Mail Code
    User->>UI: Enter verification code
    UI->>Client: sign_in_by_mail_code(mail_login_token, received_code)
    Client->>Server: POST /api/v1/auth/sign-in-by-mail-code
    Server-->>Client: {mailAuthToken: "auth_token_xyz789"}
    Client-->>UI: APIResponse(success, data)
    UI->>User: Show step 3 (enter device info)

    Note over User,Email: Step 3: Sign In Into Family
    User->>UI: Enter device name, model, optional password hash
    UI->>Client: sign_in_into_family(mail_auth_token, device_name, device_model)
    Client->>Server: POST /api/v1/parent/sign-in-into-family
    Server-->>Client: {deviceAuthToken, ownDeviceId}
    Client-->>UI: APIResponse(success, data)
    UI->>UI: Store tokens in session & database
    UI->>Server: Trigger sync (do_sync)
    UI-->>User: Redirect to dashboard
```

### Recover Parent Password Flow Sequence Diagram

```mermaid
sequenceDiagram
    participant User as User
    participant UI as Dashboard UI
    participant Client as AuthClient
    participant Server as Debug Server
    participant DB as Database
    participant Email as Email Service

    Note over User,Email: Prerequisites: User must have mailAuthToken from email login flow

    User->>UI: Enter new password
    UI->>Client: recover_parent_password(mail_auth_token, new_password)
    Client->>Server: POST /api/v1/parent/recover-parent-password
    Note right of Server: Request: {mailAuthToken, password: {hash, secondHash, secondSalt}}

    Server->>DB: Find user by mailAuthToken
    Server->>DB: Update passwordHash, secondPasswordHash, secondPasswordSalt
    Server->>DB: Increment userListVersion
    Server->>DB: Notify clients via websocket
    Server->>Email: Send password recovery notification
    Email->>User: "Your password was changed using the password reset feature"

    Server-->>Client: {ok: true}
    Client-->>UI: APIResponse(success)
    UI->>User: Show success message
```

---

## External Server API Endpoints

### GET /time

Get the current server time.

**Request:** None

**Response:**
```json
{
    "ms": 1699900000000
}
```

---

### POST /api/v1/auth/send-mail-login-code-v2

Send a mail login code to the specified email address.

**Request:**
```json
{
    "mail": "user@example.com",
    "locale": "en",
    "deviceAuthToken": "optional_token"
}
```

**Response:**
```json
{
    "mailLoginToken": "token_abc123"
}
```

---

### POST /api/v1/auth/sign-in-by-mail-code

Sign in using a mail login token and verification code.

**Request:**
```json
{
    "mailLoginToken": "token_abc123",
    "receivedCode": "Pferd Miete abwenden"
}
```

**Response:**
```json
{
    "mailAuthToken": "auth_token_xyz789"
}
```

---

### POST /api/v1/parent/create-family

Create a new family.

**Request:**
```json
{
    "mailAuthToken": "auth_token_xyz789",
    "parentPassword": {
        "hash": "$2a$12$...",
        "secondHash": "$2a$12$...",
        "secondSalt": "salt...",
        "encrypted": false
    },
    "parentDevice": {
        "model": "Pixel 7"
    },
    "deviceName": "Parent's Phone",
    "timeZone": "Europe/Amsterdam",
    "parentName": "John Doe",
    "clientLevel": 7
}
```

**Response:**
```json
{
    "deviceAuthToken": "device_token_abc123",
    "ownDeviceId": "device_id_xyz789"
}
```

---

### POST /api/v1/parent/sign-in-into-family

Sign in to an existing family.

**Request:**
```json
{
    "mailAuthToken": "auth_token_xyz789",
    "parentDevice": {
        "model": "Pixel 7"
    },
    "deviceName": "Parent's Phone",
    "clientLevel": 7
}
```

**Response:**
```json
{
    "deviceAuthToken": "device_token_abc123",
    "ownDeviceId": "device_id_xyz789"
}
```

---

### POST /api/v1/parent/recover-parent-password

Recover parent password.

**Request:**
```json
{
    "mailAuthToken": "auth_token_xyz789",
    "password": {
        "hash": "$2a$12$...",
        "secondHash": "$2a$12$...",
        "secondSalt": "$2a$12$salt..."
    }
}
```

**Response:**
```json
{
    "ok": true
}
```

---

### POST /api/v1/parent/create-add-device-token

Create a token for adding a child device to the family.

**Request:**
```json
{
    "deviceAuthToken": "device_token_abc123",
    "parentPasswordSecondHash": "$2a$12$..."
}
```

**Response:**
```json
{
    "token": "register_token_xyz789",
    "deviceId": "device_id_123"
}
```

---

### POST /api/v1/child/add-device

Register a child device using the add-device token.

**Request:**
```json
{
    "registerToken": "register_token_xyz789",
    "deviceName": "Child's Phone",
    "deviceModel": "Pixel 6",
    "clientLevel": 7
}
```

**Response:**
```json
{
    "deviceAuthToken": "child_device_token_abc123",
    "ownDeviceId": "child_device_id_xyz789"
}
```

---

### POST /api/v1/parent/get-status-by-mail-address

Get family status by mail auth token.

**Request:**
```json
{
    "mailAuthToken": "auth_token_xyz789"
}
```

**Response:**
```json
{
    "status": "existing",
    "mail": "user@example.com"
}
```

---

### POST /api/v1/parent/remove-device

Remove a device from the family.

**Request:**
```json
{
    "deviceAuthToken": "device_token_abc123",
    "parentUserId": "user_123",
    "parentPasswordSecondHash": "$2a$12$...",
    "deviceId": "device_id_to_remove"
}
```

**Response:**
```json
{
    "ok": true
}
```

---

## Dashboard Internal Endpoints

These are internal endpoints used by the dashboard frontend for server-side rendered flows.

### GET /recover-parent-password

Render the recover parent password page with the appropriate step based on session state.

**Session State:**
- No `mail_login_token`: Step 1 - Enter email
- Has `mail_login_token`, no `mail_auth_token`: Step 2 - Enter verification code
- Has `mail_auth_token`: Step 3 - Enter new password
- Has `device_auth_token`: Redirect to dashboard

**Response:** Rendered HTML template with the appropriate step.

---

### POST /recover-parent-password

Process recover parent password form submission.

**Form Data:**
| Field | Description |
|-------|-------------|
| `step` | Current step (1, 2, or 3) |
| `mail` | Email address (step 1) |
| `receivedCode` | 3-word verification code (step 2) |
| `password` | New password (step 3) |
| `confirmPassword` | Confirm new password (step 3) |

**Flow:**
1. **Step 1**: Send mail login code to email address
2. **Step 2**: Verify the 3-word code received by email
3. **Step 3**: Hash password with bcrypt and call `/api/auth/recover-parent-password`

**Session Updates:**
- `mail_login_token`: Stored after step 1
- `mail_auth_token`: Stored after step 2
- `parent_password_second_hash`: Stored after step 3 (in session and database)

**Response:** Redirect to next step or success page.

---

## Sync Protocol

The dashboard uses a CRDT (Conflict-free Replicated Data Types) based sync protocol with HMAC-SHA256 integrity signing.

### Sync Flow

1. **Pull Status**: Request current server state with version numbers
2. **Apply Changes**: Update local database with server data
3. **Push Actions**: Send local changes to server with integrity signatures

### Action Types

Actions are encoded and signed with HMAC-SHA256. Valid AppLogicAction types (per server schema at `C:/git/timelimit-server/src/function/sync/apply-actions/dispatch-app-logic-action/index.ts`):

- `UPDATE_DEVICE_STATUS` - Update device app version
- `ADD_USED_TIME` - Add used time to a category
- `ADD_USED_TIME_V2` - Add used time (v2)
- `ADD_INSTALLED_APPS` - Add installed apps
- `FINISH_KEY_REQUEST` - Finish a key request
- `FORCE_SYNC` - Force a sync
- `REPLY_TO_KEY_REQUEST` - Reply to a key request
- `MARK_TASK_PENDING` - Mark a task as pending
- `PING` - Ping action
- `UPDATE_INSTALLED_APPS` - Update installed apps
- `REMOVE_INSTALLED_APPS` - Remove installed apps
- `SEND_KEY_REQUEST` - Send a key request
- `SIGN_OUT_AT_DEVICE` - Sign out at a device
- `TRIED_DISABLING_DEVICE_ADMIN` - Tried disabling device admin
- `UPDATE_APP_ACTIVITIES` - Update app activities
- `UPLOAD_DEVICE_PUBLIC_KEY` - Upload device public key

**Note:** `REMOVE_DEVICE` is NOT a valid AppLogicAction type. Device removal must use the REST API endpoint `/parent/remove-device` directly.

### Integrity Signing

Each action includes:
- `encodedAction`: JSON-encoded action data
- `sequenceNumber`: Monotonically increasing number
- `integrity`: HMAC-SHA256 signature
- `type`: Action type (e.g., "appLogic")
- `userId`: User ID associated with the action

---

## Data Models

### User

```typescript
interface User {
    id: string;
    name: string;
    type: "parent" | "child";
    mail: string;
    time_zone: string;
    disable_limits_until: number | null;
    current_device: string;
    password: string;
    second_password_salt: string;
    category_for_not_assigned_apps: string;
    relax_primary_device: number;
    flags: number;
    limit_login_category: string;
    pre_block_duration: number;
    last_updated: number;
}
```

### Device

```typescript
interface Device {
    id: string;
    name: string;
    model: string;
    current_user_id: string;
    current_protection_level: number;
    highest_protection_level: number;
    current_app_version: string;
    highest_app_version: string;
    public_key: string;
    platform_type: string;
    platform_level: number;
    created_at: string;
}
```

### Category

```typescript
interface Category {
    id: string;
    title: string;
    blocked_times: string;
    extra_time: number;
    extra_time_day: number;
    temp_blocked: number;
    temp_block_time: number;
    version: string;
    parent_category_id: string | null;
    block_all_notifications: number;
    time_warnings: number;
    sort_order: number;
    flags: number;
    last_updated: number;
}
```

---

## Error Handling

### Error Response Format

```json
{
    "status": "error",
    "error_code": "error_type",
    "error_message": "Human-readable error message",
    "technical_detail": "Technical details for debugging"
}
```

### Common Error Codes

| Code | Description |
|------|-------------|
| `unauthorized` | Not authenticated |
| `timeout` | Request timed out |
| `unreachable` | Cannot connect to server |
| `invalid_token` | Invalid or expired token |
| `missing_field` | Required field missing |
| `sync_failed` | Sync operation failed |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-08-28 | Initial API specification for external server communication |
| 1.1.0 | 2026-08-29 | Added dashboard internal endpoints documentation (GET /api/dashboard/devices, POST /api/dashboard/devices/remove) |
| 1.2.0 | 2026-09-03 | Added Recover Parent Password endpoint documentation, fixed Sign In Into Family request format, added sequence diagrams |
| 1.3.1 | 2026-09-04 | Fixed Recover Parent Password API field name: changed `newPassword` to `password` to match server validator |
| 1.3.0 | 2026-09-03 | Added Recover Parent Password server-side rendered flow (GET/POST /recover-parent-password), added dashboard internal endpoints section |

---

*This document serves as the basis/reference for all external server API changes. It should be extended as new features are added to the dashboard.*