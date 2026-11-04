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
- Crypto: bcrypt (cost 12), Curve25519, AES-GCM, ECDH secp256r1 (prime256v1), HMAC-SHA512/SHA256
- WebSocket (Socket.IO) for real-time sync notifications
- HTTP API with gzip compression, Content-Length auto-negotiation

**Related repositories:**
- Official server code: `C:\git\timelimit-server`
- Official Android app: `C:\git\timelimit-android`

## Git Status (2026-10-04)
- **Branch**: main
- **Local commits ahead of origin**: 34+ commits
- **Working tree status**: Has local changes
- **Last commit**: `cfec45a` - "Commit current state of work"

## Documentation Hub

### Requirements
- `timelimit-ui/docs/requirements/requirements.md` - Merged requirements document (functional, non-functional, technical, and test requirements)

### Architecture
- `timelimit-ui/docs/architecture/design.md` - **COMPREHENSIVE**: Single design document containing architecture, database schema (9 tables), API documentation, security, logging, UI patterns, coding standards, testing guide, requirements, and more (1342 lines)

### API Documentation
- `timelimit-ui/docs/api/api-reference.md` - Complete API reference with examples
- `timelimit-ui/docs/api/internal-api.md` - Internal dashboard API endpoints
- `timelimit-ui/docs/ServerAPI.md` - External server API endpoints

### User Guides
- `timelimit-ui/docs/guides/user-guide.md` - End-user documentation
- `timelimit-ui/docs/guides/admin-guide.md` - Administrator documentation
- `timelimit-ui/docs/guides/deployment-guide.md` - Installation and deployment instructions

### Development
- `timelimit-ui/docs/development/testing-guide.md` - Testing patterns and practices
- `timelimit-ui/docs/development/ui-patterns.md` - UI component patterns
- `timelimit-ui/docs/development/coding-standards.md` - Code style and conventions

### Other Documentation
- `timelimit-ui/docs/README.md` - Main documentation hub
- `timelimit-ui/docs/DOCUMENTATION_INDEX.md` - Quick links index
- `timelimit-ui/docs/logging.md` - Logging infrastructure
- `timelimit-ui/docs/time-limit-rules-user-guide.md` - Time limit rules user guide
- `timelimit-ui/docs/password-hash-and-integrity.md` - Password hashing details
- `context_android_app.md` - Android app architecture reference
- `docs/requirements/requirements.md` - Functional and non-functional requirements
- `plans/*.md` - Implementation plans (historical reference)

## Recent Completed Work

### Free-Format Category Name for Time Limit Rules (2026-10-04) ✅
Implemented the ability to specify a category name as a free-format string when creating a time limit rule, instead of selecting from a dropdown.

**Changes made:**
- Added `create_category()` and `get_category_by_title()` functions to `database.py`
- Added `POST /api/dashboard/categories` endpoint in `app.py`
- Updated HTML template to use text input instead of dropdown for category
- Updated JavaScript `dashboardV2.js` to handle free-format category name (find or create category)
- Updated documentation in `docs/time-limit-rules-user-guide.md` and `docs/api/internal-api.md`

**Implementation approach:**
- When a user enters a category name, the system checks if a category with that name already exists
- If not, it creates a new category with the given name
- The category's ID is then used in the time limit rule

### JavaScript Fixes for Dashboard Issues (2026-10-04) ✅
Fixed dashboard issues where the hamburger menu button and server connection were broken after implementing the free-format category name feature.

**Root Cause:** The JavaScript file (`dashboardV2.js`) was corrupted during implementation and replaced with a minimal version missing essential functions and event listeners.

**Fix:** Restored and enhanced the JavaScript file with:
1. Added `clearFamilyOverviewContent()` function to clear family overview display
2. Added `refreshServerStatus()` function to update server status display
3. Added event listeners for sidebar elements (`add-dummy-user-btn`, `add-user-modal-close`, `add-user-submit-btn`, `signout-btn-sidebar`)
4. Updated `updateSessionOverview()` to handle sidebar login links and add dummy user button
5. Updated `loadFamilyOverview()` to check authentication and clear content on error
6. Updated `clearSession()` to call load functions to clear dashboard content

**Test Results:** All 151 relevant tests pass:
- Sign out tests: 12 passed
- Missing sign in links tests: 6 passed
- Visual responsive tests: 97 passed
- Sidebar sign out button tests: 5 passed
- Hamburger menu interaction tests: 20 passed
- JavaScript syntax tests: 2 passed

### Documentation Consolidation (2026-09-27) ✅
Consolidated all design-related documentation into a single comprehensive design document at `timelimit-ui/docs/architecture/design.md`.

### Test Logging Separation Fix (2026-09-27) ✅
Fixed unit test logs appearing in the main `logs/` directory by moving environment variable setting to the top of `conftest.py` before imports.

### Sign Out Dashboard Content Clearing Fix (2026-09-26) ✅
Fixed sign out button not clearing dashboard content sections by updating `clearSession()` and adding `clearFamilyOverviewContent()` function.

### Sidebar Sign Out Button Event Listener Fix (2026-09-26) ✅
Added missing event listener for the sidebar sign out button (`signout-btn-sidebar`).

### Add Dummy User Submit Button Event Listener Fix (2026-09-26) ✅
Added missing event listener for the "Add User" submit button in the dummy user modal.

### Console Logging Stack Trace Fix (2026-09-26) ✅
Removed noisy debug output with stack traces from `toggleMenu()` and `closeMenu()` functions.

### Database Viewer Contrast Fix (2026-09-25) ✅
Improved WCAG AA compliant contrast for the Database Viewer screen by updating text colors.

### Server Selection Contrast Fix (2026-09-25) ✅
Improved contrast for the selected server display at the top of the dashboard.

### Hamburger Menu Contrast Fix (2026-09-25) ✅
Improved visibility of the hamburger menu button with better color contrast and dimensions.

### Users & Devices Unified View Integration (2026-09-18) ✅
Integrated the unified user card view from the dashboard redesign mockup into Dashboard V2.

### Missing refreshUsers Function Fix (2026-09-19) ✅
Added `refreshUsers()` function as alias for `refreshUnifiedView()`.

### Debugging Session (2026-09-18) ✅
Fixed missing JavaScript functions referenced in HTML template and Escape key handler.

### Add Dummy User Feature (2026-09-25) ✅
Added "Add Dummy User" button in sidebar Actions section with modal dialog for testing time limit rules.

### Dashboard Sync Timestamp Fix (2026-09-26) ✅
Fixed sync timestamp not updating after adding a user by adding `save_sync_state()` call in the add user endpoint.

### Dashboard V2 Redesign Implementation (2026-09-16) ✅
Sequential implementation of Dashboard V2 redesign including HTML template, light theme, hamburger menu, and role-based visibility.

## Test Statistics

- **Total Tests**: 1277+ tests passing (151 tests for JavaScript fixes, 1126+ other tests)
- **Test Framework**: pytest
- **Coverage**: High coverage across all modules
- **Test Types**: Unit, Integration, and End-to-End tests

## Documentation Status

- **Design Document**: ✅ Updated and consolidated (2026-09-27)
- **API Documentation**: ✅ Complete
- **User Guides**: ✅ Complete
- **Development Guides**: ✅ Complete
- **Requirements**: ✅ Complete
