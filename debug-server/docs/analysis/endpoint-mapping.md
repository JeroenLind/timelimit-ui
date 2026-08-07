# Endpoint Mapping Analysis

## Overview

This document maps the 16 UI bridge endpoints (from `context.md`) to the 21 backend API endpoints (from `context_android_app.md`). The TimeLimit UI acts as a bridge between the frontend dashboard and the backend TimeLimit server (`api.timelimit.io`).

## UI Bridge Endpoints (context.md §307–329, §409–419)

These endpoints are served by the TimeLimit UI bridge server (`web_server.py` / `frontend.py`) on port 8099. They handle communication between the web dashboard and the backend TimeLimit server.

| # | UI Route | Method | Purpose | Auth Required |
|---|----------|--------|---------|---------------|
| 1 | `/set-server` | POST | Update server selection (set backend server URL) | No |
| 2 | `/ha-storage` | POST | HA storage shadow copy (persist UI state) | No |
| 3 | `/ha-storage` | GET | Retrieve HA storage data | No |
| 4 | `/ha-events-longpoll` | GET | Long-polling for real-time event updates (25s timeout) | No |
| 5 | `/wizard-step1` | POST | Request email login code (maps to `/auth/send-mail-login-code-v2`) | No |
| 6 | `/wizard-step2` | POST | Validate email code (maps to `/auth/sign-in-by-mail-code`) | No |
| 7 | `/wizard-step3` | POST | Finalize family setup (maps to `/parent/create-family`) | No (mail auth) |
| 8 | `/wizard-login` | POST | Sign in to existing family (maps to `/parent/sign-in-into-family`) | No (mail auth) |
| 9 | `/sync` | POST | Pull status data (maps to `/sync/pull-status`) | Yes (deviceAuthToken) |
| 10 | `/sync/push-actions` | POST | Push changes to server (maps to `/sync/push-actions`) | Yes (deviceAuthToken) |
| 11 | `/generate-hashes` | POST | Generate password hashes (bcrypt + second hash) | No |
| 12 | `/regenerate-hash` | POST | Regenerate second hash using server-provided salt | No |
| 13 | `/calculate-hmac` | POST | Calculate HMAC-SHA512 for sync action signing | No |
| 14 | `/calculate-hmac-sha256` | POST | Calculate HMAC-SHA256 (binary format) for integrity | No |
| 15 | `/calculate-sha512` | POST | Calculate SHA512 hex digest (legacy integrity) | No |
| 16 | `/debug-integrity` | POST | Debug integrity calculation for sync actions | No |
| 17 | `/get-token-device` | POST | Lookup device by token | No |

> **Note:** The plan references 16 UI bridge endpoints, but `context.md` lists 17 routes (including `/get-token-device`). The `/ha-storage` route supports both POST and GET, counted as one endpoint. The total is 17 distinct routes.

## Backend API Endpoints (context_android_app.md §125–147)

These are the 21 endpoints implemented by the TimeLimit backend server (`api.timelimit.io`). The UI bridge proxies requests to these endpoints.

| # | Method | Path | Purpose | Auth Required |
|---|--------|------|---------|---------------|
| 1 | GET | `/time` | Get server time in milliseconds | No |
| 2 | POST | `/auth/send-mail-login-code-v2` | Send email login code (with device verification on Android 7.0+) | No |
| 3 | POST | `/auth/sign-in-by-mail-code` | Sign in with email + code → returns `mailAuthToken` | No |
| 4 | POST | `/parent/get-status-by-mail-address` | Get family/mail status (check if email is linked to a family) | No (mailAuthToken) |
| 5 | POST | `/parent/create-family` | Create family with parent password (bcrypt + DH encryption) | No (mailAuthToken) |
| 6 | POST | `/parent/sign-in-into-family` | Sign in to existing family | No (mailAuthToken) |
| 7 | POST | `/parent/recover-parent-password` | Recover parent password with new password | No (mailAuthToken) |
| 8 | POST | `/child/add-device` | Register child device (using add-device token) | No (registerToken) |
| 9 | POST | `/sync/push-actions` | Push pending actions to server (batch of 25) | Yes (deviceAuthToken) |
| 10 | POST | `/sync/pull-status` | Pull server status (ClientDataStatus → ServerDataStatus) | Yes (deviceAuthToken) |
| 11 | POST | `/parent/create-add-device-token` | Create token for adding a device | Yes (deviceAuthToken) |
| 12 | POST | `/purchase/can-do-purchase` | Check purchase eligibility | Yes (deviceAuthToken) |
| 13 | POST | `/purchase/finish-purchase-by-google-play` | Finish Google Play purchase | Yes (deviceAuthToken) |
| 14 | POST | `/parent/link-mail-address` | Link email to parent account | Yes (deviceAuthToken) |
| 15 | POST | `/child/update-primary-device` | Update primary device selection | Yes (deviceAuthToken) |
| 16 | POST | `/child/logout-at-primary-device` | Sign out at primary device | Yes (deviceAuthToken) |
| 17 | POST | `/sync/report-removed` | Report device as removed | Yes (deviceAuthToken) |
| 18 | POST | `/parent/remove-device` | Remove a device from family | Yes (deviceAuthToken) |
| 19 | POST | `/sync/is-device-removed` | Check if device was removed | Yes (deviceAuthToken) |
| 20 | POST | `/parent/create-identity-token` | Create identity token (for purchases) | Yes (deviceAuthToken) |
| 21 | POST | `/parent/delete-account` | Delete account | Yes (deviceAuthToken) |

## UI Route → Backend API Path Mapping

| UI Route (context.md) | Backend API (context_android_app.md) | Method | Auth Required |
|---|---|---|---|
| `/set-server` | N/A (internal) | POST | No |
| `/ha-storage` | N/A (internal) | POST/GET | No |
| `/ha-events-longpoll` | N/A (internal) | GET | No |
| `/wizard-step1` | `/auth/send-mail-login-code-v2` | POST | No |
| `/wizard-step2` | `/auth/sign-in-by-mail-code` | POST | No |
| `/wizard-step3` | `/parent/create-family` | POST | No (mail auth) |
| `/wizard-login` | `/parent/sign-in-into-family` | POST | No (mail auth) |
| `/sync` | `/sync/pull-status` | POST | Yes (deviceAuthToken) |
| `/sync/push-actions` | `/sync/push-actions` | POST | Yes (deviceAuthToken) |
| `/generate-hashes` | N/A (internal) | POST | No |
| `/regenerate-hash` | N/A (internal) | POST | No |
| `/calculate-hmac` | N/A (internal) | POST | No |
| `/calculate-hmac-sha256` | N/A (internal) | POST | No |
| `/calculate-sha512` | N/A (internal) | POST | No |
| `/debug-integrity` | N/A (internal) | POST | No |
| `/get-token-device` | N/A (internal) | POST | No |

## HTTP Request Format

All backend API requests follow a standardized format (from `context_android_app.md` §8.3):

- **Content-Type**: `application/json; charset=utf-8`
- **Content-Encoding**: `gzip` (request bodies are gzip-compressed)
- **Content-Length**: Auto-negotiated — first request sent without `Content-Length`; if server returns HTTP 411 (Length Required), retry with `Content-Length` header
- **Body**: JSON serialized via `android.util.JsonWriter` (Android) or equivalent JSON serialization

### Device Verification (Android 7.0+)

The `send-mail-login-code-v2` endpoint supports device verification via Android Keystore attestation. A temporary EC key pair is generated with attestation, and an `X509ClientKeyManager` is used for the TLS connection. For non-Android clients (e.g., Python), this step can be skipped — the server retries without it.

## Authentication Flow

The authentication flow follows a multi-step process (from `context_android_app.md` §3.7, §8.4):

```
1. Parent creates family:
   a. Send email → receive code (POST /auth/send-mail-login-code-v2)
   b. Sign in with code → get mailAuthToken (POST /auth/sign-in-by-mail-code)
   c. Create family with parentPassword (bcrypt + DH encryption) (POST /parent/create-family)
   d. Server returns deviceAuthToken + ownDeviceId
   e. Pull initial data from server (POST /sync/pull-status)

2. Child device registration:
   a. Parent creates add-device token (POST /parent/create-add-device-token)
   b. Child uses token to register (POST /child/add-device)
   c. Server returns deviceAuthToken + ownDeviceId
   d. Pull initial data from server (POST /sync/pull-status)

3. Password recovery:
   a. Send email → receive code (POST /auth/send-mail-login-code-v2)
   b. Sign in with code → get mailAuthToken (POST /auth/sign-in-by-mail-code)
   c. Recover password with new password (POST /parent/recover-parent-password)
```

## Error Handling

HTTP status codes are mapped to typed exceptions (from `context_android_app.md` §3.2, §8.14):

| HTTP Code | Exception | Description |
|-----------|-----------|-------------|
| 400 | `BadRequestHttpError` | Invalid request format, often means `clientLevel` is not supported |
| 401 | `UnauthorizedHttpError` | Device auth token is invalid or device was removed |
| 403 | `ForbiddenHttpError` | Access denied |
| 404 | `NotFoundHttpError` | Resource not found |
| 409 | `ConflictHttpError` | Conflict (e.g., duplicate resource) |
| 410 | `GoneHttpError` | Resource no longer available |
| 429 | `TooManyRequestsHttpError` | Rate limited, wait and retry |

## WebSocket (Socket.IO) Events

The server supports Socket.IO over WebSocket transport for real-time sync notifications (from `context_android_app.md` §3.4):

| Event | Direction | Payload | Handler |
|-------|-----------|---------|---------|
| `connect` | Server → Client | — | Client emits `devicelogin` with auth token |
| `devicelogin` | Client → Server | auth token (ack) | `onConnectionEstablished()` |
| `disconnect` | Server → Client | — | `onConnectionLost()` |
| `should sync` | Server → Client | `{isImportant: Boolean}` | `onSyncRequestedByServer(important)` |
| `connected devices` | Server → Client | `[deviceId, ...]` | `onGotConnectedDeviceList(ids)` |
| `sign out` | Server → Client | — | `onGotSignOutRequest()` |

## Configuration

The UI bridge server is configured via `config.yaml` and `data/options.json` (from `context.md` §242–267):

| Variable | Type | Description |
|----------|------|-------------|
| `server_url` | str | URL of the TimeLimit backend server (e.g., `http://192.168.68.30:8080`) |
| `logging_mode` | list(standard\|verbose) | Logging verbosity |
