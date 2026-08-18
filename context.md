# CONTEXT.md - Project State & Memory

## Project Overview
**TimeLimit UI** is a web-based dashboard for managing TimeLimit rules and synchronization. It bridges a frontend dashboard (JavaScript) with a backend TimeLimit server (api.timelimit.io) via a Python HTTP server.

## Technical Stack
- **Backend (UI bridge)**: Python 3, `http.server`, `urllib`, `bcrypt`, `hmac`, `hashlib`
- **Frontend**: HTML, JavaScript (vanilla), CSS
- **Configuration**: `config.yaml` + `data/options.json`
- **Deployment**: Docker (Home Assistant amd64-base), S6-overlay, port 8099
- **Test Environment**: Windows 11, Python 3, local test scripts in `timelimit-ui/test/`
- **Python Command**: Use `py -3` instead of `python` on Windows

## Key Architecture
- Client-server: TimeLimit UI ↔ TimeLimit Backend Server ↔ Android App / Devices
- Sync protocol: Action-based CRDT with HMAC-SHA256 integrity signing
- Crypto: bcrypt (cost 12), Curve25519, AES-GCM, ECDH secp25619, HMAC-SHA512/SHA256
- WebSocket (Socket.IO) for real-time sync notifications
- HTTP API with gzip compression, Content-Length auto-negotiation

---

## Reference Sources (Authoritative)

**⚠️ IMPORTANT: The official app and server sources are the authoritative reference for all implementations.**

- **Official Android App Source**: `C:\git\timelimit-android`
  - HTTP API implementation: `app/src/main/java/io/timelimit/android/sync/network/api/HttpServerApi.kt`
  - Request/Response models: `app/src/main/java/io/timelimit/android/sync/network/`

- **Official Server Source**: `C:\git\timelimit-server`
  - API endpoints: `src/api/auth.ts`, `src/api/parent.ts`
  - TypeScript interfaces: `src/api/schema.ts`
  - JSON Schema validators: `src/api/validator.ts`
  - Authentication logic: `src/function/authentication/login-by-mail.ts`

**All API request formats must match these official sources exactly.**

---

## Recent Changes (2026-08-16)

### Create Family Flow Fixes

#### Root Cause: Missing `clientLevel` Field

The create family step 3 was failing with a 400 Bad Request error from the TimeLimit server. Analysis of the official Android app source (`HttpServerApi.kt`) revealed that the `clientLevel` field was missing from the API request.

**Android App Implementation (lines 306-308):**
```kotlin
if (!skipClientLevel) {
    writer.name(CLIENT_LEVEL).value(ClientDataStatus.CLIENT_LEVEL_VALUE)
}
```

**Fix Applied:**
- Added `'clientLevel': 7` to both `create_family()` and `create_family_rest()` methods in `auth_client.py`
- The value `7` matches `ClientDataStatus.CLIENT_LEVEL_VALUE` from the Android app

### Files Modified
| File | Changes |
|------|---------|
| `timelimit-ui/rootfs/usr/bin/dashboardV2/auth_client.py` | Added `clientLevel: 7` to create_family() and create_family_rest() methods |
| `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/create_family.html` | Changed time zone from text input to select dropdown with valid IANA time zones |

### Time Zone Field Change

The time zone field in Step 3 of the create family form was changed from a free-text input to a dropdown selection box. This prevents users from entering invalid time zone values like "Europe" instead of "Europe/Amsterdam".

**Available Time Zones:**
- Europe/Amsterdam (default)
- Europe/Berlin
- Europe/London
- America/New_York
- America/Los_Angeles
- America/Chicago
- Asia/Tokyo
- Asia/Shanghai
- Asia/Kolkata
- Australia/Sydney
- UTC

---

## Additional Fix: Remove `encrypted` Field from `parentPassword`

### Root Cause: Invalid `encrypted` Field in `PlaintextParentPassword`

The create family step 3 was failing with a 400 Bad Request error because the `parentPassword` object included an `encrypted` field that is not allowed by the server's validation schema.

**Server Schema (`C:\git\timelimit-server\src\api\schema.ts`):**
```typescript
export interface PlaintextParentPassword {
  hash: string
  secondHash: string
  secondSalt: string
}
```

The `PlaintextParentPassword` interface does NOT include the `encrypted` field. The `encrypted` field is only valid for `EncryptableParentPassword` type.

**Server Validator (`C:\git\timelimit-server\src\api\validator.ts`):**
```json
"PlaintextParentPassword": {
  "type": "object",
  "properties": {
    "hash": { "type": "string" },
    "secondHash": { "type": "string" },
    "secondSalt": { "type": "string" }
  },
  "additionalProperties": false,  // <-- No extra properties allowed!
  "required": ["hash", "secondHash", "secondSalt"]
}
```

**Fix Applied:**
- Removed `password_data['encrypted'] = False` from `app.py` line 1020
- The `generate_family_hashes()` function already returns the correct structure with `hash`, `secondHash`, and `secondSalt`

### Files Modified
| File | Changes |
|------|---------|
| `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py` | Removed `password_data['encrypted'] = False` line |
| `create_family_data.json` | Removed `encrypted` field from `parentPassword` |
| `test_create_family.json` | Removed `encrypted` field from `parentPassword` |
| `test_create_family_v2.json` | Removed `encrypted` field from `parentPassword` |
| `test_create_family_v3.json` | Removed `encrypted` field from `parentPassword` |
| `test_api_families.json` | Removed `encrypted` field from `parentPassword` |
| `test_families_flow.py` | Removed `encrypted` field from all test data |
| `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_create_family_integration.py` | Updated test to verify `encrypted` is NOT in password data |

---

## Additional Fix: Remove `locale` Field from Create Family Request

### Root Cause: Invalid `locale` Field in `CreateFamilyByMailTokenRequest`

The create family request was failing with a 400 Bad Request error because the `locale` field was being sent in the request body, but it's not allowed by the server's validation schema.

**Server Schema (`C:\git\timelimit-server\src/api/schema.ts`):**
```typescript
export interface CreateFamilyByMailTokenRequest {
  mailAuthToken: string
  parentPassword: PlaintextParentPassword
  parentDevice: NewDeviceInfo
  deviceName: string
  timeZone: string
  parentName: string
  clientLevel?: number
}
```

**Server Validator (`C:\git\timelimit-server\src/api/validator.ts`):**
```json
{
  "type": "object",
  "properties": {
    "mailAuthToken": { "type": "string" },
    "parentPassword": { "$ref": "#/definitions/PlaintextParentPassword" },
    "parentDevice": { "$ref": "#/definitions/NewDeviceInfo" },
    "deviceName": { "type": "string" },
    "timeZone": { "type": "string" },
    "parentName": { "type": "string" },
    "clientLevel": { "type": "number" }
  },
  "additionalProperties": false,  // <-- No extra properties allowed!
  "required": ["deviceName", "mailAuthToken", "parentDevice", "parentName", "parentPassword", "timeZone"]
}
```

The `CreateFamilyByMailTokenRequest` schema has `additionalProperties: false`, which means any extra fields like `locale` will cause validation to fail.

**Android App Implementation (lines 273-326):**
The official Android app's `createFamilyByMailToken()` function does NOT include `locale` in the request body.

**Fix Applied:**
- Removed the `locale` field from the request data in `auth_client.py` for both `create_family()` and `create_family_rest()` methods
- The `locale` parameter is kept in the function signature for API compatibility but is no longer sent to the server

### Files Modified
| File | Changes |
|------|---------|
| `timelimit-ui/rootfs/usr/bin/dashboardV2/auth_client.py` | Removed `locale` from request data in `create_family()` and `create_family_rest()` methods |
| `create_family_data.json` | Removed `locale` field, added `clientLevel: 7` |
| `test_create_family.json` | Removed `locale` field, added `clientLevel: 7` |
| `test_create_family_v2.json` | Removed `locale` field, added `clientLevel: 7` |
| `test_create_family_v3.json` | Removed `locale` field, added `clientLevel: 7` |
| `test_api_families.json` | Removed `locale` field, added `clientLevel: 7` |
| `test_families_flow.py` | Removed `locale` field from test data |
| `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_create_family_integration.py` | Updated tests to verify `locale` is NOT sent to server |

---

## Additional Fix: Bcrypt Hash Prefix Mismatch

### Root Cause: bcrypt 5.0+ prefix parameter format

The create family step 3 was failing with "Failed to generate password hashes" error because bcrypt 5.0+ requires the prefix parameter to be `b'2a'` or `b'2b'` (without dollar signs), but the code was passing `b'$2a$'` (with dollar signs).

**Error from logs:**
```json
{"error": "Supported prefixes are b'2a' or b'2b'", "event": "Create family step 3 failed: hash generation error"}
```

**bcrypt 5.0+ behavior:**
```python
# bcrypt 5.0+ expects prefix without dollar signs
bcrypt.gensalt(rounds=12, prefix=b'2a')  # Produces: $2a$12$...
```

**Python bcrypt default behavior (bcrypt 4.x and earlier):**
```python
# Python bcrypt generates $2b$ prefixed hashes by default
bcrypt.gensalt(rounds=12)  # Produces: $2b$12$...
```

**Android App (jBCrypt) behavior:**
```kotlin
// jBCrypt generates $2a$ prefixed hashes
BCrypt.gensalt()  // Produces: $2a$10$...
```

**Server Validation Regex (`C:\git\timelimit-server\src\util\password.ts`):**
```typescript
export const optionalPasswordRegex = /^(\$2a\$[123][0-9]\$[./A-Za-z0-9]{53})?$/
```

This regex only matches:
- `$2a$` prefix (not `$2b$` or `$2y$`)
- Cost factor 10-39
- 53 character hash

**Fix Applied:**
- Updated `crypto_utils.py` to use `prefix=b'2a'` (without dollar signs) for bcrypt 5.0+ compatibility
- The bcrypt library automatically adds the `$` characters when generating the salt

### Files Modified
| File | Changes |
|------|---------|
| `timelimit-ui/rootfs/usr/bin/crypto_utils.py` | Changed `prefix=b'$2a$'` to `prefix=b'2a'` for bcrypt 5.0+ compatibility |

### Password Validation on Dashboard

Added server-side and client-side password validation to prevent users from entering passwords that don't meet the minimum requirements:

**Server-side validation (`app.py`):**
- Added minimum password length check (8 characters)
- Validates password before sending to server

**Client-side validation (`create_family.html`):**
- Added `minlength="8"` and `pattern=".{8,}"` attributes to password inputs
- Added JavaScript validation to show real-time feedback

---

## Verification Complete (2026-08-17)

All fixes for the "Failed to generate password hashes" error have been verified and applied:

### ✅ Verified Fixes

1. **Bcrypt Hash Prefix Fix** (`crypto_utils.py` lines 18-19):
   - `bcrypt.gensalt(rounds=12, prefix=b'2a')` generates `$2a$` prefixed hashes
   - Compatible with bcrypt 5.0+ which expects prefix without dollar signs
   - Matches server validation regex: `/^(\$2a\$[123][0-9]\$[./A-Za-z0-9]{53})?$/`

2. **Server-Side Password Validation** (`app.py` lines 997-1001):
   - Minimum 8 character password check
   - Prevents sending invalid passwords to server

3. **Client-Side Password Validation** (`create_family.html`):
   - Password inputs have `minlength="8"` and `pattern=".{8,}"` attributes (lines 256, 262)
   - JavaScript validation provides real-time feedback (lines 294-322)

### Status: COMPLETE

The dashboard will now:
- Prevent users from entering passwords shorter than 8 characters
- Show immediate validation feedback on the client side
- Validate password length server-side before sending to the TimeLimit server
- Generate bcrypt hashes with `$2a$` prefix that the server accepts
- Work correctly with bcrypt 5.0+ library

### Next Steps
- Test the full create family flow with the official TimeLimit server
- Verify the fixes work with the actual TimeLimit API

---

## Planned: Parent Login to Existing Family (2026-08-17)

### Overview

Adding functionality to dashboardV2 that allows a parent to log in to an existing family using email-based authentication. This is different from "Create Family" which creates a new family.

### Key Finding

The `sign-in-into-family` endpoint does **NOT** require a password! It only requires:
- `mailAuthToken` (from email verification)
- `deviceName`
- `parentDevice.model`
- `clientLevel` (optional, defaults to 7)

This matches the Android app's `signInToFamilyByMailToken` implementation.

### Implementation Flow

```
Step 1: Enter Email → Send Mail Login Code
    ↓
Step 2: Enter Verification Code → Get MailAuthToken
    ↓
Step 3: Enter Device Info → Sign In to Family
    ↓
Success: Redirect to Dashboard with deviceAuthToken
```

### Files to Modify

1. `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py` - Add routes and handlers
2. `timelimit-ui/rootfs/usr/bin/dashboardV2/auth_client.py` - Fix sign_in_into_family method to use correct request format
3. `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/login_as_parent.html` - Create new template
4. `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/dashboardV2.html` - Add link to login page
5. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_login_as_parent.py` - Create tests

### Detailed Plan

See `plans/dashboardV2-parent-login-plan.md` for the complete step-by-step implementation plan with code examples.

### Status: PLANNED

The implementation plan has been created and is ready for execution.
