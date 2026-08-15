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

## Recent Work (2026-08-15)

### Dashboard V2 Alert CSS Fix
Fixed the issue where alert notifications appeared empty/invisible when the server data refreshed.

**Problem**
- The alert notification bar slides in from the right with a white background (`rgba(255, 255, 255, 0.95)`)
- The text inside was invisible because the `.alert` CSS class had no `color` property
- The alert inherited white text (`color: #fff`) from the body, resulting in white text on white background

**Solution**
- Added `color: #333;` to the `.alert` CSS class in `dashboardV2.html`
- This ensures the alert text is visible against the white background

**Files Modified**
- `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/dashboardV2.html` - Added `color: #333;` to `.alert` class

### Dashboard V2 Time Endpoint Fix
Fixed the dashboard V2 endpoint issues identified in the log analysis:

**Problem**
1. **URL Construction**: `AuthClient` in `auth_client.py` prepends `API_PREFIX` (`/api/v1`) to all endpoints. When `get_server_time()` calls `/time`, it becomes `/api/v1/time`, which returns 404 on the actual TimeLimit API at `http://192.168.68.30:8080`.
2. **Response Format**: `AuthClient` expects `{"time": <int>}` but the actual API returns `{"ms": <int>}`.

**Solution (Option A: Skip prefix for time endpoint)**
- Added `skip_prefix` parameter to `_make_request()` and `_request_with_retry()` methods in `auth_client.py`
- Modified `get_server_time()` to call `/time` without the API_PREFIX
- Changed response parsing from `response.data.get('time')` to `response.data.get('ms')`

**Files Modified**
- `timelimit-ui/rootfs/usr/bin/dashboardV2/auth_client.py` - Added `skip_prefix` parameter, fixed URL construction and response format
- `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py` - Updated response parsing to use `ms` field
- `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_auth_client.py` - Updated mock responses to use `{'ms': ...}`
- `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_timechecker.py` - Updated mock responses to use `{'ms': ...}`
- `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_scheduler.py` - Updated mock responses to use `{'ms': ...}`
- `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_scheduler_logging.py` - Updated mock responses to use `{'ms': ...}`

**Test Results**
- All time endpoint tests pass (136 passed)
- 6 pre-existing test failures unrelated to this fix (URL default expectations and scheduler lifecycle test isolation)

### Debug Server API Prefix Update
Updated the debug server to use correct endpoints matching the actual TimeLimit API at `http://192.168.68.30:8080`.

**Changes Made**
1. **Config** (`debug-server/app/core/config.py`): Changed `API_V1_STR` from `/api/v1` to empty string `""`
2. **Main** (`debug-server/app/main.py`): Updated to handle empty prefix for openapi_url and docs_url
3. **Time Response Model** (`debug-server/app/models/auth.py`): Changed `TimeResponse` model to use `ms` field instead of `time`
4. **Time Endpoint** (`debug-server/app/api/time.py`): Updated to return `TimeResponse(ms=int(time.time() * 1000))`
5. **Auth Endpoints** (`debug-server/app/api/auth.py`): Removed POST /time endpoint (actual API only supports GET /time)
6. **Test Files**: Updated all test files to use new endpoints and response format
7. **Documentation** (`debug-server/docs/api.md`): Updated API documentation to reflect new endpoints and response format

**Test Results**
- All 581 tests pass

### Dashboard V2 Server Check Display Fix (2026-08-15)
Fixed the issue where the server status section showed "Checking server..." on initial page load instead of the actual server status.

**Problem**
1. **Frontend Issue**: When Dashboard V2 page loads, the server status section shows "Checking server..." because `updateStatusDisplay()` is never called on initial page load. The JavaScript only calls `fetchSessionStatus()` and `loadHistoricalData()` on DOMContentLoaded.
2. **Backend Issue**: In `scheduler.py`, the code used `response.data.get('time')` but the actual API returns `{'ms': ...}`.

**Solution**
1. **Frontend Fix**: Modified `dashboardV2.html` to call `refreshServerStatus()` on initial page load to properly display the server status.
2. **Backend Fix**: Fixed `scheduler.py` to use `response.data.get('ms')` instead of `response.data.get('time')` in both `check_server_callback()` and `add_server_check_job()` functions.

**Files Modified**
- `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/dashboardV2.html` - Added `refreshServerStatus()` call on initial page load
- `timelimit-ui/rootfs/usr/bin/dashboardV2/scheduler.py` - Fixed field name from `time` to `ms`

**Test Results**
- All timechecker tests pass (49 passed)
- 2 pre-existing test failures unrelated to this fix (scheduler lifecycle test isolation)

## Endpoint Verification Results

### Server Status
- Server at `http://192.168.68.30:8080` is running (actual TimeLimit backend, Express.js-style)
- The FastAPI debug server is NOT running (it would serve `/api/v1/time` with `{"time": <int>}`)

### Endpoint Tests (check_endpoints.sh)
| Check | Result | Details |
|-------|--------|---------|
| Server Reachability | PASS | HTTP 404 (server is reachable) |
| GET /time | PASS | HTTP 200, returns `{"ms": <timestamp_ms>}` |
| POST /time | PASS | Correctly rejected with HTTP 404 (POST not supported) |

### Test Config Files Status
| File | Status | Notes |
|------|--------|-------|
| `debug-server/tests/config.py` | ✅ Updated | Uses `http://192.168.68.30:8080` |
| `test/conftest.py` (root) | ✅ Updated | Uses `http://192.168.68.30:8080` |
| `timelimit-ui/test/config.yaml` | ✅ Updated | Uses `http://192.168.68.30:8080` |
| `timelimit-ui/rootfs/usr/bin/dashboardV2/config.py` | ✅ Updated | Uses `http://192.168.68.30:8080` |
| `timelimit-ui/test/conftest.py` | ✅ Updated | Uses `http://192.168.68.30:8080` |
| `debug-server/tests/client.py` | ✅ Updated | Uses `http://192.168.68.30:8080` |
| `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/conftest.py` | ✅ Updated | Uses `http://192.168.68.30:8080` |

## Next Steps
- Integrate logging into dashboardV2 components
- Add CI/CD pipeline configuration for automated testing

## Notes
- The actual TimeLimit API uses `/time` endpoint (not `/api/v1/time`)
- The response format is `{"ms": <timestamp_ms>}` (not `{"time": <int>}`)
- POST /time is not supported by the actual TimeLimit API
- The FastAPI debug server at `debug-server/` now uses `/` prefix with `{"ms": <int>}` format
- See `context.md` for full project structure and component overview
