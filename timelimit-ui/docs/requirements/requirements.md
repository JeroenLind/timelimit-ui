# TimeLimit Dashboard – Requirements

| Item | Value |
|------|-------|
| Version | 3.1 (3.0 plus the answers to the plan questions of 2026-11-07) |
| Status | **Draft for approval** – nothing is built against this version until it is approved |
| Replaces | requirements.md v2 (FR-001..007, NFR-001..004, TR-001, Test-001..004, BUG-001..004) |
| Protocol reference | `docs/ServerAPI.md` (verified against server and Android client) |
| Priorities | MoSCoW: **M**ust, **S**hould, **C**ould, **W**on't (v1) |
| Status values | Done = implemented and tested; Partial; Open = not built; Rework = exists but must change |

---

## 1. Purpose and scope

The dashboard is a web based **parent control** for the TimeLimit Android app. It talks to a TimeLimit server like a parent device does, so the family can be managed from a browser.

**Users and setting**
- One family with one or more parents. Parents also use the Android app.
- The dashboard is one extra device in the family, signed in as its own parent user called **"Dashboard"**.
- There is no dashboard login: it is a single shared instance for the household. Access is limited to the machine it runs on (see SEC-001).
- v1 runs directly on a Windows laptop (`py -3 app.py`). Later it becomes a **second Home Assistant add-on** (own container, reached through HA ingress). The dashboard works against any TimeLimit server: the official one or an alternative (own or test) server, selected in settings (FR-100).

**In scope (v1):** time limit rules, blocked-time schedule, categories and their apps, extra time and temporary blocking, used time, child devices (read only), settings, a separate test section.

**Out of scope (v1):** adding children or parents in production (done in the app), notifications and mail (stay in the app), per-app usage statistics (the server does not provide them to parents), copying rules or bulk actions across children, backup and restore, dashboard login, purchase/premium features, offline change queue.

---

## 2. Functional requirements

### 2.1 Connection and family

| ID | Pri | Requirement | Status |
|----|-----|-------------|--------|
| FR-100 | M | On first start the dashboard shows a **settings screen** where the **server is selected** with a dropdown: **Official server** (`https://api.timelimit.io`) or **Alternative server** (protocol http/https with default http, address and port). The choice is stored persistently; each server keeps its own link, cache and pending restores, so switching never mixes data and actions only reach the active server. For a real family the dashboard logs in **once** as an existing parent (the password is used once and not stored), creates the parent **"Dashboard"** itself with `ADD_USER` (FR-801) and registers itself as a **new device** (no import of an older dashboard's link). With the test-server switch on (FR-800) the screen can also **create a new family** on a fresh test server; its first parent becomes "Dashboard". The device auth token is stored. | Partial |
| FR-101 | M | The dashboard device is signed in as a separate parent user **"Dashboard"** (never as a person's own parent account). Its actions use device integrity (`integrity:"device"`). | Partial |
| FR-102 | S | On connecting, the dashboard reads the server's `apiLevel` and **warns** (never blocks) when it is not 7 or 9 (the tested range). | Open |
| FR-103 | M | Only one family per installation. Switching family means resetting the installation. | Done |
| FR-104 | S | The settings screen shows server URL, connection state, device id (not the token), dashboard version, and last sync. | Partial |

### 2.2 Synchronisation (replaces FR-001, FR-003, FR-004, BUG-001, BUG-002, BUG-003)

| ID | Pri | Requirement | Status |
|----|-----|-------------|--------|
| FR-200 | M | Sync starts **automatically** when the dashboard starts and after every change, without user action. A sync round is: push pending actions, then pull. | Partial (push and pull B4; automatic worker B5) |
| FR-201 | M | Pull sends the versions the dashboard holds (devices, users, per-category data, rules, apps, used times, tasks); the server returns only differing parts. The dashboard applies **all** returned parts to its cache. After each pull the cache equals the server state. | Partial (pull B3, push B4) |
| FR-202 | M | After `shouldDoFullSync` the dashboard forgets all versions, fully re-pulls, refreshes the UI and shows a short notice that an action was possibly not applied. | Partial (pull side B3; push side B4) |
| FR-203 | M | The server never reports a failed action (HTTP 200, `shouldDoFullSync:true`). The dashboard treats an action as **confirmed only** when the server does not request a full sync. Unconfirmed actions are reported to the user and rolled back in the UI. | Done (pusher) |
| FR-204 | M | Sequence numbers are persistent per device, start at 0, and are reserved before sending. Max 25 actions per request. | Done |
| FR-205 | M | A newly added item (e.g. a user in the test section) is shown **immediately** with the marker "waiting for server". The marker disappears on confirmation; on failure the item is removed and an error is shown. | Rework |
| FR-206 | M | Users and other entities that the server no longer reports are **kept** and flagged "no longer on server" until the parent cleans them up. | Done (B1, storage) |
| FR-207 | M | A change by another parent or by the app appears **instantly** through the server WebSocket (`should sync`). If the socket is unavailable the dashboard polls (interval configurable). | Done (backend B6; browser use in E-steps) |
| FR-208 | M | Conflicts: last writer wins. If the data being edited changed on the server in the meantime, the UI shows a warning before saving. | Open |
| FR-209 | M | If an action fails or is not confirmed, the UI change is reverted and a notice is shown (message contains the reason when known). | Partial |

### 2.3 Time limit rules (replaces FR-005, FR-006)

| ID | Pri | Requirement | Status |
|----|-----|-------------|--------|
| FR-300 | M | Per category, parents can create, view, edit and delete rules (`CREATE/UPDATE/DELETE_TIMELIMIT_RULE`). A rule has: allowed time, days, optional time window (start/end), optional maximum session length and pause, optional per-day flag, optional expiry. | Partial |
| FR-301 | M | Days use the bitmask Mon=1, Tue=2, Wed=4, Thu=8, Fri=16, Sat=32, Sun=64 (0–127; 127 = every day). The UI uses checkboxes; the bitmask is calculated in one place only. | Done |
| FR-302 | M | Time is entered in minutes (0 = no time allowed), time windows as HH:MM 24 h (0–1439 minutes of the day, start ≤ end). Input is validated before sending. | Done |
| FR-303 | M | Creating a rule uses the nested `rule` object; updating uses flat fields without `categoryId` (see ServerAPI.md 5.2). Rules pulled from the server (including `e`) are shown correctly. | Done (push) / Rework (pull) |
| FR-304 | M | **Weekly blocked-time schedule** per **category** (as the server stores it: slots per weekday, `UPDATE_CATEGORY_BLOCKED_TIMES`) can be viewed and edited. | Open |
| FR-305 | M | Deleting a rule asks for confirmation. | Open |
| FR-306 | S | The rule table shows: child, category, days, limit, window, session limit; one row per rule, sorted by category. | Partial |
| FR-307 | M | **Rule off for today.** A parent can switch a time limit rule off for the **current day only**. The dashboard does this by removing today's weekday bit from the rule's days mask (`UPDATE_TIMELIMIT_RULE`, every other field unchanged), so for the server it looks as if a parent changed the rule; at midnight the bit is put back with a second `UPDATE_TIMELIMIT_RULE`. (a) "Today" and "midnight" follow the time zone of the machine running the dashboard; when the child's time zone on the server differs, a warning names both zones and the function stays available. (b) The pending restore (rule id, the day bit, the original days, the state the dashboard set, due time) is stored in the database and survives a cache reset; it is executed at midnight while the dashboard runs, and on the next start every overdue restore runs **immediately** and a notice reports what was done. (c) At restore the dashboard compares the rule on the server with the state it set; if it differs or the rule no longer exists it changes nothing and shows a notice (the parent decides). (d) Editing or deleting such a rule in the dashboard first restores it (today's bit back), then applies the change; "off for today" ends with a short notice. (e) The parent can switch the rule on again earlier the same day. (f) Not offered for a rule that does not apply today (its weekday bit is not set); if today's bit is the only one set, the days mask becomes 0 until the restore. (g) The rule list shows the state "off for today" with the restore time; every switch-off and restore is audit-logged (FR-1100). | Open |

### 2.4 Categories and apps

| ID | Pri | Requirement | Status |
|----|-----|-------------|--------|
| FR-400 | M | Create, rename and delete categories per child. Deleting asks for confirmation and states how many apps and rules are removed. | Open |
| FR-401 | M | Set the order and the parent category of a category. | Open |
| FR-402 | M | Category settings, four groups: (1) category flags (block, show time, etc.; bit meanings taken from the server code), (2) block all notifications and time warnings, (3) battery limit (charging/mobile) and network ids (add, reset), (4) the category for unassigned apps (per child) and disable limits per category. | Open |
| FR-403 | M | Assign and remove apps for a category (`ADD_CATEGORY_APPS`, `REMOVE_CATEGORY_APPS`). Adding moves an app out of its previous category. | Partial |
| FR-404 | M | The selectable app list comes from the **child's device** (installed apps as synced by the device). If the list is encrypted for a clientLevel the dashboard cannot read, the UI says so and allows manual package names. | Open |
| FR-405 | S | Apps show their label and package name. | Open |

### 2.5 Extra time and temporary blocking

| ID | Pri | Requirement | Status |
|----|-----|-------------|--------|
| FR-500 | M | Grant extra time to a child per category with fixed buttons **+15 / +30 / +60 minutes** and free input in minutes. | Open |
| FR-501 | M | Extra time applies **to today only**. | Open |
| FR-502 | M | Extra time can be reverted/subtracted (down to zero). | Open |
| FR-503 | M | A category can be **temporarily blocked** until a chosen time. | Open |
| FR-504 | S | One-shot quick buttons, e.g. "Block now for 1 hour". | Open |
| FR-505 | S | Disable all limits of a child until a time (`disableTimelimitsUntil`) – included only if still wanted after v1 review (not chosen in the interview). | Open |

### 2.6 Used time

| ID | Pri | Requirement | Status |
|----|-----|-------------|--------|
| FR-600 | M | Show **today's** used time per category and child, against the limit. | Open |
| FR-601 | M | Show the **history per day** (7 and 30 days) per category as a list and a bar chart. The dashboard **builds its own daily totals** in the cache so the history grows to 30 days from the first use (it is lost on a cache reset, TR-310). | Open |
| FR-602 | W | Used time per app is **not** offered: the server stores used time per category per day only. | – |

### 2.7 Children and devices

| ID | Pri | Requirement | Status |
|----|-----|-------------|--------|
| FR-700 | M | Overview of all children: status, today's used time, quick actions (extra time, block). | Partial |
| FR-701 | M | Child detail screen: categories, rules, apps, blocked times, used time. | Partial |
| FR-702 | S | Child devices are shown **read only**: model, last connection, current user. | Open |
| FR-703 | W | No add/remove of children or parents in production (done in the app). | – |

### 2.8 Test section (separate)

| ID | Pri | Requirement | Status |
|----|-----|-------------|--------|
| FR-800 | M | A clearly separated "Test" section lets the parent create family members (`ADD_USER`) for a **local test server that is not linked to an app**. A switch **"This is a test server"** in settings (default off) enables it; with the switch off the menu item is absent and its routes answer 404. The page `debug_database.html` is part of this section. | Partial |
| FR-801 | M | Adding a user pushes `ADD_USER` first; a 502 is shown when the server does not confirm. Parent users need the DH-encrypted password container. | Done (child) / Partial (parent: builder and container B2, flow E10) |

### 2.9 Parent security

| ID | Pri | Requirement | Status |
|----|-----|-------------|--------|
| FR-900 | M | Rules, categories, extra time and blocking use device integrity: **no password prompt**. | Done |
| FR-901 | M | A password prompt (modal, per action, password never stored) appears only for server-required actions: change parent password, keep-signed-in (`SET_KEEP_SIGNED_IN`, HMAC). | Open |
| FR-902 | S | The "Dashboard" parent can be inspected: keep-signed-in state is visible; a warning shows when the device was signed out (`SET_DEVICE_USER`). | Open |

### 2.10 User interface

| ID | Pri | Requirement | Status |
|----|-----|-------------|--------|
| UI-001 | M | Screens: children overview, child detail, settings, test section. | Partial |
| UI-002 | M | Navigation: **fixed sidebar on desktop**, **hamburger menu on small screens**. The menu opens/closes with the button, the close button, the overlay and Escape; `aria-expanded`/`aria-hidden` are kept correct and focus returns to the button. (Replaces FR-007; BUG-004 as regression test.) | Done (D1) |
| UI-003 | M | Layout works on desktop browsers, phones and tablets. | Done (D1) |
| UI-004 | M | Dark theme (and light). | Done (D1) |
| UI-005 | M | Languages: Dutch and English, selectable in settings. Default: the browser language when it is Dutch or English, otherwise English. Theme: follows the system until the user chooses. | Partial (D1: switch in the top bar; moves into settings in E1) |
| UI-006 | M | Destructive actions (delete rule, category, remove apps) require a confirmation dialog. | Partial (D1: dialog component; used by the delete actions in E-steps) |
| UI-007 | M | Every action shows its state: pending, confirmed, failed. | Partial |
| UI-008 | W | No screen reader / WCAG target in v1 (basic ARIA only, as in UI-002). | – |

### 2.11 Server unavailable (replaces FR-002, NFR-004)

| ID | Pri | Requirement | Status |
|----|-----|-------------|--------|
| FR-1000 | M | Health check on page load with a configurable timeout (default 3 s). | Done (A7) |
| FR-1001 | M | When the server is unreachable: offline banner, **read-only view from the cache**, all change controls disabled, SSE/WebSocket closed, no requests queued. | Done (A7) |
| FR-1002 | M | Reconnection polling with exponential backoff (default 10 s → 30 s max, configurable) and a "Retry connection" button. | Done (A7) |
| FR-1003 | M | When the server is back, controls are re-enabled and data is refreshed with a sync. | Done (A7) |

### 2.12 Audit log

| ID | Pri | Requirement | Status |
|----|-----|-------------|--------|
| FR-1100 | M | Every change made through the dashboard (action type, child, result, time) is logged and shown as a tab **"Changes"** in child detail. Entries without a child (settings, test section) are stored; where they are shown is decided when E12 is detailed. | Partial |
| FR-1101 | M | Entries older than **30 days** are removed automatically. | Open |

---

## 3. Technical requirements

### 3.1 Protocol

| ID | Pri | Requirement | Status |
|----|-----|-------------|--------|
| TR-100 | M | All server calls follow `docs/ServerAPI.md`. The server code wins over the document. | – |
| TR-101 | M | Wire action types are SCREAMING_SNAKE; ids inside a family are 6 characters `[0-9a-zA-Z]`; `encodedAction` is a JSON **string**; integrity covers exactly that string. All actions are built by `action_builder.py` and validated before a sequence number is reserved. | Done |
| TR-102 | M | Password integrity: HMAC-SHA256 with key = second hash, message = uint64BE(seq) ‖ len+deviceId ‖ len+encodedAction. Verified with test vectors. | Done |
| TR-103 | M | `ClientDataStatus` contains all versions and per-category data (D10). | Done (B3) |
| TR-104 | M | The dashboard sends clientLevel 7 and only uses features available at that level. | Done |
| TR-105 | S | WebSocket (Socket.IO) per `docs/ServerAPI.md` section 6: `devicelogin`, `should sync`, `sign out`. | Done (backend B6; browser use in E-steps) |
| TR-106 | S | Requests are gzip-compressed with retry on HTTP 411, like the Android app. | Done (A6) |

### 3.2 Data and storage

| ID | Pri | Requirement | Status |
|----|-----|-------------|--------|
| TR-200 | M | **SQLite** is the cache. One file in the **data folder** (`data/` next to the app on Windows, `/data` in HA, gitignored), one per installation. The server is the source of truth. Cache key is the **server profile** plus the **family id** from the server. | Done (B1) |
| TR-201 | M | Database access is thread-safe; writes that change several tables use one transaction. `sync_state` is never replaced blindly (`INSERT OR REPLACE` is removed). | Done (B1) |
| TR-202 | M | No parent passwords are stored. Only the device auth token (and own ids) are stored locally, in the database and in the session file with backup. | Done |
| TR-204 | W | No backup/restore feature; losing the file means re-registering the device. | – |

### 3.3 Runtime, packaging and configuration

| ID | Pri | Requirement | Status |
|----|-----|-------------|--------|
| TR-300 | M | Python 3.10+; `requirements.txt` with loose version ranges. Starts with `py -3 app.py` on Windows. | Done |
| TR-301 | M | All settings (port, data directory, log level, timings) come from a config file/environment variables and the UI; no hard-coded paths, so the same code runs as an HA add-on (paths via add-on options). | Partial |
| TR-302 | S | Later: second HA add-on (**aarch64**), reached through ingress, built by GitHub Actions to `ghcr.io`; no base-URL assumptions (relative URLs). The Windows version is run locally without a GitHub build. The add-on s6 service must start the new dashboard (`dashboard-v2`), not the legacy `web_server.py`. | Open |
| TR-303 | M | Timeouts: all outgoing server requests and all browser `fetch` calls have a timeout (AbortController in the browser). Network errors are caught and shown. | Open |
| TR-304 | S | Retry for failed sync rounds: up to 2 retries after 250 ms, then back-off. Timings configurable (see FR-1000/1002). | Partial |
| TR-305 | M | Default port **8100** (configurable) and default listen address **127.0.0.1**; the HA add-on sets `0.0.0.0` for ingress. | Rework (now 8099, 0.0.0.0) |
| TR-306 | M | `SECRET_KEY` is generated randomly on first start and stored next to the database; an environment variable overrides it. | Open |
| TR-307 | M | All API routes return one error envelope `{status:"error", code, message, requestId}` with these codes and statuses: `INVALID_INPUT` 400, `SESSION_INVALID` 401, `INVALID_PASSWORD` 403, `NOT_FOUND` 404, `NOT_LINKED` 409, `CONFLICT` 409, `READ_ONLY_OFFLINE` 503, `SERVER_UNREACHABLE` 502, `SERVER_TIMEOUT` 504, `ACTION_NOT_CONFIRMED` 502, `INTERNAL_ERROR` 500. `CONFLICT`: the browser sends the version it started editing with; a mismatch with the cache gives 409 (FR-208). | Open |
| TR-308 | M | Layers: routes (thin) → services → repository (only layer with SQL); one server-client module for all HTTP to the TimeLimit server; pure domain logic without I/O. See `docs/architecture/design.md`. | Done (B7: enforced by test) |
| TR-309 | M | One sync worker thread with a queue; a user change is push then immediate pull, the request waits for the result. | Open |
| TR-310 | M | A cache reset (schema change) drops the cache and fully re-syncs, but keeps the link, settings and the **sequence counter**. | Done (B1) |
| TR-311 | M | Frontend: Jinja + vanilla JS in ES modules, no build step; CSS variables, no inline styles, dark theme follows the system; i18n through `nl.json`/`en.json` with fallback to English. | Open |
| TR-312 | M | The legacy UI layer (`frontend.py`, `web_server.py`, `api_client.py`, `check_server.py`) and the one-off scripts are removed, after the s6 service is switched. | Done (C1, C2) |

### 3.4 Logging and diagnostics

| ID | Pri | Requirement | Status |
|----|-----|-------------|--------|
| TR-400 | M | Configurable log level (debug/info/warn/error). | Done |
| TR-401 | M | Log rotation with limited size and file count. | Done |
| TR-402 | S | A **debug export** button in settings. Secrets (tokens, hashes, the typed password, the second hash) are **masked at info level and higher**; only at **debug level** everything is unmasked, also in the export; the UI warns before sharing. | Open |

### 3.5 Quality

| ID | Pri | Requirement | Status |
|----|-----|-------------|--------|
| TR-500 | M | pytest unit tests, isolated (own temporary database and log folder per test), parallel with `pytest-xdist`, 30 s timeout, no automatic retries, all green including unrelated tests (until the cut-over the old tests run apart as a legacy suite, see `docs/plan/old-tests-disposition.md`); tests that only grep source text are replaced by behaviour tests; tests of deleted code are removed. Currently 29 failures (24 isolation, 1 database isolation, 2 clear-all, 1 config, 1 landing). | Rework |
| TR-501 | M | **Contract tests**: every action the dashboard can produce is validated against the schemas generated from the server. | Done (A5, B2) |
| TR-502 | M | **Browser/UI tests** (Playwright) for the main screens: overview, child detail, rule dialog, hamburger menu, offline banner. | Open |
| TR-503 | W | A live test against a real server is not mandatory; an optional script against the local test server may exist. | – |
| TR-504 | M | Documentation stays in sync: this document, `docs/ServerAPI.md`, and design notes are updated with every feature or fix. | – |

### 3.6 Development standards (added 2026-11-07)

| ID | Pri | Requirement | Status |
|----|-----|-------------|--------|
| TR-510 | M | **One tool for style and lint:** `ruff` (lint and format), configured in `pyproject.toml`. `ruff check` and `ruff format --check` pass on the new package. | Open |
| TR-511 | M | **Line endings:** the repository uses LF (`.gitattributes` and `.editorconfig`); shell scripts and s6 services never get CRLF. | Open |
| TR-512 | M | **Time and time zones:** the domain layer only uses time-zone-aware times and receives the current time from an injected clock (never calls `now()` itself), so midnight logic (FR-307) is testable without waiting. | Done (B7: enforced by test) |
| TR-513 | M | **Secrets in code:** tokens, hashes and typed passwords pass through one `Secret` type / masking function; log masking (TR-402) is implemented only there. | Done (B7: enforced by test) |
| TR-514 | M | **Timeouts on all I/O:** every HTTP call has an explicit timeout; a test fails on any call without one. | Done (B7: enforced by test) |
| TR-515 | S | **Type hints** on public functions of `domain/`, `services/` and `client/`; `mypy` checks `domain/` and `client/` first. | Open |
| TR-516 | S | **Reproducible dependencies:** `requirements.txt` keeps loose ranges (Windows); a generated constraints file pins the versions for the HA image. | Open |
| TR-517 | S | **Pre-commit:** a local hook runs `ruff` and the fast unit tests (no Playwright); one command (`py -3 tools/check.py`) runs lint, type check and the full suite. | Open |
| TR-518 | S | **Commit convention:** short descriptive messages with the agreed trailers; one commit per plan step. | Open |
| TR-519 | S | **Decision log:** `docs/decisions/` holds short decision records (context, choice, consequences) from a template; existing decisions of the plan are backfilled as records. | Open |

---

## 4. Non-functional requirements

| ID | Pri | Requirement |
|----|-----|-------------|
| NFR-001 | M | Sync target: a change is visible within **5 s** on a local network. The target is configurable; defaults as given. |
| NFR-002 | M | Reliability: sync failures are retried with back-off (TR-304) and never leave the UI frozen. |
| NFR-003 | M | Performance: the browser stays responsive when the server is down (no growing request queue, no endless reconnect loops). |
| NFR-004 | M | Usability: all texts are available in Dutch and English; errors are clear and say what to do. |

### Security (SEC)

| ID | Pri | Requirement |
|----|-----|-------------|
| SEC-001 | M | The dashboard listens on **localhost by default** (127.0.0.1) and has no login. Remote access comes later through Home Assistant (ingress authentication). |
| SEC-002 | M | The server connection uses HTTPS when the server is not on the local network. Plain HTTP is allowed for localhost/LAN test servers. (Replaces NFR-003 "all communication HTTPS".) |
| SEC-003 | M | The device auth token is stored only on the local disk (database and session file), never sent to the browser. The browser never talks to the TimeLimit server; only the backend does. |
| SEC-004 | S | Secrets in the repository: the old test signing key stays untracked; `docs/password info.md` must not be tracked. |

---

## 5. Decisions that changed existing requirements

| Old | Change |
|-----|--------|
| FR-001 acceptance 5 (retry with empty data) | Workaround for a missing version exchange. Replaced by FR-201/TR-103. |
| FR-003 (local fallback record) vs. FR-004 (server data only) | Resolved: show immediately with marker "waiting for server" (FR-205); only server-confirmed data is permanent. |
| BUG-003 solution (preserve users not in response) | Now explicit: kept and flagged "no longer on server" (FR-206). |
| FR-005 "CRDT" | Wrong. Sync is version based (FR-201). |
| FR-006 / FR-007 | Were duplicated many times in the file; each now exists once (FR-301, UI-002). |
| FR-007 hamburger on all screens | Sidebar on desktop, hamburger on small screens (UI-002). |
| FR-002 fixed timings | Configurable with the old values as defaults. |
| NFR-003 HTTPS everywhere | HTTPS required only outside the local network (SEC-002). |
| Original goal "own server-side additions" | None exist in v1. |

## 6. Conflicts and open points to confirm

1. **Logging:** secrets are masked at info level and higher and unmasked only at debug level (decided 2026-11-07). Anyone who sets debug level and shares the export shares the token; the UI warns.
2. **Per-app usage** was dropped from v1 because the server has no per-app data for parents.
3. **FR-505** (disable all limits until a time) was not chosen; kept as Should only if wanted.
4. **Server version**: the verified references are `apiLevel` 7 and 9; other versions only give a warning (FR-102).
5. **Test isolation** (29 failing tests) and **D10/D11** (sync) block FR-200..202; they come first in the build order.
6. `docs/password info.md` is still tracked and holds a plaintext test password; untracking is pending the owner's decision.

## 7. Traceability (old → new)

| Old ID | New ID |
|--------|--------|
| FR-001 | FR-200, FR-201, FR-202 |
| FR-002 | FR-1000..1003 |
| FR-003 | FR-205 |
| FR-004 | FR-201, FR-203, FR-206, FR-209 |
| FR-005 | FR-300, FR-303, FR-306 |
| FR-006 | FR-301 |
| FR-007 | UI-002 |
| NFR-001..004 | NFR-001, NFR-002, SEC-002, NFR-003 |
| TR-001 | TR-303 |
| Test-001..004 | TR-502, TR-500 |
| BUG-001 | FR-201 |
| BUG-002 | FR-205, FR-801 |
| BUG-003 | FR-206 |
| BUG-004 | UI-002, TR-502 |

## 8. Build order (proposal, after approval)

See `docs/architecture/design.md` section 10 for the current build order. Summary: 1. foundation (development standards TR-510..519, TR-500 isolation, TR-307 error envelope, server-down handling, TR-306); 2. sync (TR-103, TR-309, TR-310, FR-200..202); 3. cleanup (TR-312, after the s6 switch); 4. features; 5. frontend (TR-311); 6. HA add-on (TR-302).

Original proposal: 1. Test isolation (TR-500) and sync correctness (TR-103, FR-200..202, TR-201).
2. Rules, blocked times, categories and apps (FR-300..305, FR-400..404).
3. Extra time, temporary blocking, used time (FR-500..503, FR-600..601).
4. Settings, WebSocket, i18n, themes, UI tests (FR-100..104, FR-207, UI-002..005, TR-502).
5. HA add-on (TR-302).
