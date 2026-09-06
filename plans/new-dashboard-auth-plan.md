# New Dashboard - Auth Flow Implementation Plan

## Overview

This plan focuses on implementing a new Flask-based dashboard version based on the timechecker page,
with all backend logic in Python and a thin Jinja2 template frontend. The new dashboard will include:
- A landing page with toggle/dropdown to switch between legacy and new dashboard versions
- Server selection dropdown (3 options: Local, Official, Debug Server) matching the existing dashboard
- Family creation flow (3-step: email → code → password hashes → create-family)
- Child device login flow (parent creates add-device token → child registers via add-device)
- Timechecker dashboard with APScheduler running ServerChecker.check() every 60 seconds
- SQLite database for storing timechecker results and dashboard state
- Real-time status displays, historical data visualization, and alert notifications
- Minimal JavaScript limited to essential interactions (form submissions, data refresh)

## Implementation Notes

### No Implementation Dependencies on Debug-Server

The dashboard application is a **standalone application** with **no implementation dependencies** on the debug-server application. This means:

- **No shared code**: The dashboard does not import, include, or reuse any Python modules, utilities, or source files from the `debug-server/` directory. All code within `dashboardV2/` is self-contained.
- **HTTP API only**: Communication with the debug-server occurs exclusively through standard HTTP/HTTPS REST API calls to the debug-server's `/api/v1/` endpoints. The `auth_client.py` module is a standalone HTTP client that sends requests and parses responses — it does not import any debug-server internals.
- **Independent deployment**: The dashboard can be deployed, run, and tested independently of the debug-server. It does not require the debug-server source code to be present at build or runtime.
- **Independent dependencies**: The dashboard's Python dependencies (Flask, APScheduler, SQLite, bcrypt, requests) are managed separately from the debug-server's dependencies (FastAPI, SQLAlchemy, etc.). There is no shared `requirements.txt`, `pyproject.toml`, or virtual environment between the two applications.
- **Independent testing**: The dashboard's test suite is fully self-contained and does not import or depend on any debug-server test modules, fixtures, or test infrastructure.

The debug-server is treated as an **external service** — the dashboard is a client that consumes its API, not a consumer of its code.

### Cross-Platform Compatibility

The new dashboard must run on both **Windows laptop** and **Home Assistant** as an app:
- Flask app uses `app.run()` with configurable host/port via environment variables
- Database path is configurable (defaults to a local file, not hardcoded)
- For Home Assistant: works as an ingress app (existing timelimit-ui uses ingress_port 8099)
- For Windows: runnable standalone with `python app.py` from the `dashboardV2/` directory
- All file paths use `os.path` for cross-platform compatibility (no hardcoded Unix paths)
- APScheduler uses `BackgroundScheduler` (threaded) to work in both environments

### Responsive / Scalable Design

The dashboard page must be viewable on both **big screens** and **phones**:
- CSS uses media queries for different screen sizes (desktop, tablet, mobile)
- Flexible layouts using CSS Grid and Flexbox (no fixed pixel dimensions)
- Relative units (em, rem, %) instead of fixed pixels for sizing
- Touch-friendly elements (minimum 44px tap targets) for mobile
- Viewport meta tag for proper mobile rendering
- Historical data table uses horizontal scrolling on small screens
- Status indicators scale appropriately (larger text on big screens, compact on mobile)

## Testing Strategy

**A complete set of unit tests must be implemented alongside each implementation step.**
Tests are not deferred to Phase 6 only — each phase includes its own test file(s)
covering the routes, database operations, and API client logic for that phase.
Phase 6 serves as the final integration test pass and test infrastructure validation.

Test files per phase:
- Phase 1: `test_database.py`, `test_config.py`, `test_auth_client.py`
- Phase 2: `test_landing.py`
- Phase 3: `test_timechecker.py`, `test_scheduler.py`
- Phase 4: `test_family_creation.py`
- Phase 5: `test_child_login.py`
- Phase 6: `test_integration.py` (end-to-end flows)

All tests use `pytest` with `FlaskClient` and include timeout mechanisms.

## Architecture

**Python backend (Flask) handles ALL application logic. Thin Jinja2 templates
provide the minimal HTML frontend with only essential JavaScript for form
submissions and data refresh.**

Located in `timelimit-ui/rootfs/usr/bin/dashboardV2/` to integrate with the
existing rootfs structure alongside `check_server.py`, `crypto_utils.py`, etc.

```
timelimit-ui/rootfs/usr/bin/dashboardV2/
├── app.py              # Flask application - all routes and logic
├── config.py           # Configuration (debug-server URL, etc.)
├── scheduler.py        # APScheduler for 60-second timechecker
├── database.py         # SQLite database setup and models
├── auth_client.py      # Standalone HTTP client for debug-server API calls (no shared code)
├── templates/          # Thin Jinja2 templates (server-rendered HTML)
│   ├── base.html       # Base template with nav/toggle
│   ├── landing.html    # Landing page: toggle legacy/new dashboard
│   ├── dashboardV2.html  # New dashboard (based on check_server.html)
│   ├── create_family.html  # Family creation wizard (3 steps)
│   └── child_login.html    # Child device login flow
├── static/             # Minimal CSS/JS (only essential interactions)
│   ├── css/
│   │   └── dashboardV2.css
│   └── js/
│       └── dashboardV2.js
└── tests/
    ├── conftest.py
    ├── test_auth_flow.py
    ├── test_scheduler.py
    └── test_database.py
```

## Auth Flow Reference

### New Family Creation (3 steps)
1. **Step 1**: User enters email → `POST /api/v1/auth/send-mail-login-code-v2`
   - Request: `{"mail": "user@example.com"}`
   - Returns: `{"mailLoginToken": "...", "status": "ok", ...}`
2. **Step 2**: User enters verification code → `POST /api/v1/auth/sign-in-by-mail-code`
   - Request: `{"mailLoginToken": "...", "receivedCode": "123456"}`
   - Returns: `{"mailAuthToken": "...", "status": "ok"}`
3. **Step 3**: Server generates password hashes via `crypto_utils.generate_family_hashes()`
   - `POST /api/v1/parent/create-family` with `mailAuthToken` + `parentPassword`
   - Request: `{"mailAuthToken": "...", "parentPassword": {"hash": "...", "secondHash": "...", "secondSalt": "...", "encrypted": false}}`
   - Returns: `{"deviceAuthToken": "...", "ownDeviceId": "...", "data": {...}, "status": "ok"}`

### Child Device Login (2 steps)
1. **Step 1**: Parent (already authenticated with `deviceAuthToken`) enters password
   - Server generates `secondHash` via `crypto_utils.regenerate_second_hash()`
   - `POST /api/v1/parent/create-add-device-token` with `deviceAuthToken` + `parentPasswordSecondHash`
   - Request: `{"deviceAuthToken": "...", "parentPasswordSecondHash": "..."}`
   - Returns: `{"token": "...", "deviceId": "...", "status": "ok"}`
2. **Step 2**: Child registers using registerToken
   - `POST /api/v1/child/add-device` with `registerToken` + `deviceName` + `deviceModel`
   - Request: `{"registerToken": "...", "deviceName": "Child Device", "deviceModel": "Pixel 7"}`
   - Returns: `{"deviceAuthToken": "...", "ownDeviceId": "...", "data": {...}, "status": "ok"}`

## Key Technical Details

- **API Prefix**: All debug-server endpoints are under `/api/v1/`
- **Auth**: Device auth tokens passed via `Authorization: Bearer <token>` header
- **Password Hashing**: bcrypt cost factor 12, using `crypto_utils.generate_family_hashes()`
- **State Manager**: In-memory `StateManager` with `asyncio.Lock` in debug-server
- **Test Pattern**: `TestClient` from FastAPI, `pytest` with fixtures
- **Existing Proxy**: `web_server.py` already proxies wizard endpoints:
  - `/wizard-step1` → `/auth/send-mail-login-code-v2`
  - `/wizard-step2` → `/auth/sign-in-by-mail-code`
  - `/wizard-step3` → `/parent/create-family`
  - `/wizard-login` → `/parent/sign-in-into-family`
  - `/generate-hashes` → internal `crypto_utils.generate_family_hashes()`
- **Server Selection**: 3 options from existing dashboard.html, stored in Flask session:
  - 🏠 Lokaal: `http://192.168.68.30:8080`
  - 🌍 Officieel: `https://api.timelimit.io`
  - 🐛 Debug Server: `http://localhost:8080`
  - Selected server stored in Flask session via `/select-server` route (no external API needed)

## Execution Order

The implementation follows this order:
**Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6**

### Phase 1: Project Setup
- [ ] Create Flask application structure (`dashboardV2/` directory)
- [ ] Set up SQLite database with tables for `server_checks`, `families`, `devices`, `auth_tokens`
- [ ] Configure APScheduler for background tasks
- [ ] Create auth client module for debug-server API communication
- [ ] Set up test infrastructure (conftest.py, pytest.ini)
- [ ] Write unit tests for database, config, and auth client

### Phase 2: Landing Page & Navigation
- [ ] Create base template with toggle/dropdown for legacy vs new dashboard
- [ ] Implement landing page route (`/`)
- [ ] Implement legacy dashboard redirect (`/legacy-dashboard`)
- [ ] Implement new dashboard route (`/dashboardV2`)
- [ ] Add server selection dropdown (3 options: Local, Official, Debug Server) stored in Flask session, with `/select-server` route
- [ ] Write unit tests for landing page and server selection

### Phase 3: Timechecker Dashboard
- [ ] Create `dashboardV2.html` based on `check_server.html` design
- [ ] Implement APScheduler job: run `ServerChecker.check()` every 60 seconds
- [ ] Store check results in SQLite database
- [ ] Display real-time status, historical data table, and alert notifications
- [ ] Implement data refresh endpoint (AJAX or server-side)
- [ ] Write unit tests for timechecker dashboard and scheduler

### Phase 4: Family Creation Flow
- [ ] Create `create_family.html` template with 3-step wizard UI
- [ ] Implement Step 1 route: email input → proxy to `send-mail-login-code-v2`
- [ ] Implement Step 2 route: code verification → proxy to `sign-in-by-mail-code`
- [ ] Implement Step 3 route: password input → generate hashes → proxy to `create-family`
- [ ] Store `deviceAuthToken` in Flask session after successful creation
- [ ] Add "child login" option after family creation
- [ ] Write unit tests for family creation flow (all 3 steps)

### Phase 5: Child Device Login Flow
- [ ] Create `child_login.html` template
- [ ] Implement parent password verification step
- [ ] Implement `create-add-device-token` call (parent enters password)
- [ ] Implement `child/add-device` call (child registers with registerToken)
- [ ] Store child's `deviceAuthToken` in Flask session
- [ ] Display both parent and child device tokens
- [ ] Write unit tests for child device login flow (both steps)

### Phase 6: Tests
- [ ] Run full test suite and integration tests
- [ ] Test database operations
- [ ] Test landing page toggle functionality
- [ ] Test server selection functionality

### Phase 7: Future Dashboard Features (Placeholder)
- [ ] Implement TimeLimit rules synchronization with the server
- [ ] Implement category tree management
- [ ] Implement user management (add/remove users)
- [ ] Implement device management (add/remove devices)
- [ ] Implement app management (installed apps, categories)
- [ ] Implement rule management (time limits, categories)
- [ ] Implement sync protocol (push-actions, pull-status)
- [ ] Implement encrypted apps management
- [ ] Implement parent key pair management
- [ ] Write unit tests for all Phase 7 features

> **Note**: Phase 7 details will be specified in a future planning session.
