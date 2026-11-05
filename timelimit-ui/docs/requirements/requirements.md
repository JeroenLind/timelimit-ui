# TimeLimit Dashboard – Requirements

| Item | Value |
|------|-------|
| Version | 3.0 (rewrite, based on the interview of 2026-11-05) |
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
- v1 runs directly on a Windows laptop (`py -3 app.py`). Later it becomes a **second Home Assistant add-on** (own container, reached through HA ingress). The HA server add-on (`JeroenLind/timelimit-ha`) wraps the unmodified official server; it adds only logging patches.

**In scope (v1):** time limit rules, blocked-time schedule, categories and their apps, extra time and temporary blocking, used time, child devices (read only), settings, a separate test section.

**Out of scope (v1):** adding children or parents in production (done in the app), notifications and mail (stay in the app), per-app usage statistics (the server does not provide them to parents), copying rules or bulk actions across children, backup and restore, dashboard login, purchase/premium features, offline change queue.

---

## 2. Functional requirements

### 2.1 Connection and family

| ID | Pri | Requirement | Status |
|----|-----|-------------|--------|
| FR-100 | M | On first start the dashboard shows a **settings screen** where the server URL is entered. The dashboard registers itself as a new device in the family (create family or add device) and stores the device auth token. | Partial |
| FR-101 | M | The dashboard device is signed in as a separate parent user **"Dashboard"** (never as a person's own parent account). Its actions use device integrity (`integrity:"device"`). | Partial |
| FR-102 | S | On connecting, the dashboard reads the server's `clientLevel`/version info and **warns** (never blocks) when it is outside the tested range. | Open |
| FR-103 | M | Only one family per installation. Switching family means resetting the installation. | Done |
| FR-104 | S | The settings screen shows server URL, connection state, device id (not the token), dashboard version, and last sync. | Partial |

### 2.2 Synchronisation (replaces FR-001, FR-003, FR-004, BUG-001, BUG-002, BUG-003)

| ID | Pri | Requirement | Status |
|----|-----|-------------|--------|
| FR-200 | M | Sync starts **automatically** when the dashboard starts and after every change, without user action. A sync round is: push pending actions, then pull. | Partial (no pull after push) |
| FR-201 | M | Pull sends the versions the dashboard holds (devices, users, per-category data, rules, apps, used times, tasks); the server returns only differing parts. The dashboard applies **all** returned parts to its cache. After each pull the cache equals the server state. | Rework (D10/D11) |
| FR-202 | M | After `shouldDoFullSync` the dashboard forgets all versions, fully re-pulls, refreshes the UI and shows a short notice that an action was possibly not applied. | Rework |
| FR-203 | M | The server never reports a failed action (HTTP 200, `shouldDoFullSync:true`). The dashboard treats an action as **confirmed only** when the server does not request a full sync. Unconfirmed actions are reported to the user and rolled back in the UI. | Done (pusher) |
| FR-204 | M | Sequence numbers are persistent per device, start at 0, and are reserved before sending. Max 25 actions per request. | Done |
| FR-205 | M | A newly added item (e.g. a user in the test section) is shown **immediately** with the marker "waiting for server". The marker disappears on confirmation; on failure the item is removed and an error is shown. | Rework |
| FR-206 | M | Users and other entities that the server no longer reports are **kept** and flagged "no longer on server" until the parent cleans them up. | Rework |
| FR-207 | M | A change by another parent or by the app appears **instantly** through the server WebSocket (`should sync`). If the socket is unavailable the dashboard polls (interval configurable). | Open |
| FR-208 | M | Conflicts: last writer wins. If the data being edited changed on the server in the meantime, the UI shows a warning before saving. | Open |
| FR-209 | M | If an action fails or is not confirmed, the UI change is reverted and a notice is shown (message contains the reason when known). | Partial |

### 2.3 Time limit rules (replaces FR-005, FR-006)

| ID | Pri | Requirement | Status |
|----|-----|-------------|--------|
| FR-300 | M | Per category, parents can create, view, edit and delete rules (`CREATE/UPDATE/DELETE_TIMELIMIT_RULE`). A rule has: allowed time, days, optional time window (start/end), optional maximum session length and pause, optional per-day flag, optional expiry. | Partial |
| FR-301 | M | Days use the bitmask Mon=1, Tue=2, Wed=4, Thu=8, Fri=16, Sat=32, Sun=64 (0–127; 127 = every day). The UI uses checkboxes; the bitmask is calculated in one place only. | Done |
| FR-302 | M | Time is entered in minutes (0 = no time allowed), time windows as HH:MM 24 h (0–1439 minutes of the day, start ≤ end). Input is validated before sending. | Done |
| FR-303 | M | Creating a rule uses the nested `rule` object; updating uses flat fields without `categoryId` (see ServerAPI.md 5.2). Rules pulled from the server (including `e`) are shown correctly. | Done (push) / Rework (pull) |
| FR-304 | M | **Weekly blocked-time schedule** per child (the app's "blocked times": slots per weekday) can be viewed and edited. | Open |
| FR-305 | M | Deleting a rule asks for confirmation. | Open |
| FR-306 | S | The rule table shows: child, category, days, limit, window, session limit; one row per rule, sorted by category. | Partial |

### 2.4 Categories and apps

| ID | Pri | Requirement | Status |
|----|-----|-------------|--------|
| FR-400 | M | Create, rename and delete categories per child. Deleting asks for confirmation and states how many apps and rules are removed. | Open |
| FR-401 | M | Set the order and the parent category of a category. | Open |
| FR-402 | M | Category settings as in the official app (e.g. block all apps, hide time information, network/extra-time options as offered by the server for the child's clientLevel). | Open |
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
| FR-601 | M | Show the **history per day** (7 and 30 days) per category as a list and a bar chart. | Open |
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
| FR-800 | M | A clearly separated "Test" section lets the parent create family members (`ADD_USER`) for a **local test server that is not linked to an app**. It is meant for testing only and hidden or disabled when the server is not marked as a test server (setting). | Partial |
| FR-801 | M | Adding a user pushes `ADD_USER` first; a 502 is shown when the server does not confirm. Parent users need the DH-encrypted password container. | Done (child) / Open (parent) |

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
| UI-002 | M | Navigation: **fixed sidebar on desktop**, **hamburger menu on small screens**. The menu opens/closes with the button, the close button, the overlay and Escape; `aria-expanded`/`aria-hidden` are kept correct and focus returns to the button. (Replaces FR-007; BUG-004 as regression test.) | Done (hamburger) / Rework (sidebar) |
| UI-003 | M | Layout works on desktop browsers, phones and tablets. | Partial |
| UI-004 | M | Dark theme (and light). | Open |
| UI-005 | M | Languages: Dutch and English, selectable in settings. | Open |
| UI-006 | M | Destructive actions (delete rule, category, remove apps) require a confirmation dialog. | Open |
| UI-007 | M | Every action shows its state: pending, confirmed, failed. | Partial |
| UI-008 | W | No screen reader / WCAG target in v1 (basic ARIA only, as in UI-002). | – |

### 2.11 Server unavailable (replaces FR-002, NFR-004)

| ID | Pri | Requirement | Status |
|----|-----|-------------|--------|
| FR-1000 | M | Health check on page load with a configurable timeout (default 3 s). | Done |
| FR-1001 | M | When the server is unreachable: offline banner, **read-only view from the cache**, all change controls disabled, SSE/WebSocket closed, no requests queued. | Partial |
| FR-1002 | M | Reconnection polling with exponential backoff (default 10 s → 30 s max, configurable) and a "Retry connection" button. | Done |
| FR-1003 | M | When the server is back, controls are re-enabled and data is refreshed with a sync. | Done |

### 2.12 Audit log

| ID | Pri | Requirement | Status |
|----|-----|-------------|--------|
| FR-1100 | M | Every change made through the dashboard (action type, child, result, time) is logged and shown in a list. | Partial |
| FR-1101 | M | Entries older than **30 days** are removed automatically. | Open |

---

## 3. Technical requirements

### 3.1 Protocol

| ID | Pri | Requirement | Status |
|----|-----|-------------|--------|
| TR-100 | M | All server calls follow `docs/ServerAPI.md`. The server code wins over the document. | – |
| TR-101 | M | Wire action types are SCREAMING_SNAKE; ids inside a family are 6 characters `[0-9a-zA-Z]`; `encodedAction` is a JSON **string**; integrity covers exactly that string. All actions are built by `action_builder.py` and validated before a sequence number is reserved. | Done |
| TR-102 | M | Password integrity: HMAC-SHA256 with key = second hash, message = uint64BE(seq) ‖ len+deviceId ‖ len+encodedAction. Verified with test vectors. | Done |
| TR-103 | M | `ClientDataStatus` contains all versions and per-category data (D10). | Open |
| TR-104 | M | The dashboard sends clientLevel 7 and only uses features available at that level. | Done |
| TR-105 | S | WebSocket (Socket.IO) per `docs/ServerAPI.md` section 6: `devicelogin`, `should sync`, `sign out`. | Open |
| TR-106 | S | Requests are gzip-compressed with retry on HTTP 411, like the Android app. | Open |

### 3.2 Data and storage

| ID | Pri | Requirement | Status |
|----|-----|-------------|--------|
| TR-200 | M | **SQLite** is the cache. One file, **next to the app**, one per installation. The server is the source of truth. | Done |
| TR-201 | M | Database access is thread-safe; writes that change several tables use one transaction. `sync_state` is never replaced blindly (`INSERT OR REPLACE` is removed). | Rework |
| TR-202 | M | No parent passwords are stored. Only the device auth token (and own ids) are stored locally. | Done |
| TR-203 | S | Schema changes use versioned migrations. | Open |
| TR-204 | W | No backup/restore feature; losing the file means re-registering the device. | – |

### 3.3 Runtime, packaging and configuration

| ID | Pri | Requirement | Status |
|----|-----|-------------|--------|
| TR-300 | M | Python 3.10+; `requirements.txt` with loose version ranges. Starts with `py -3 app.py` on Windows. | Done |
| TR-301 | M | All settings (port, data directory, log level, timings) come from a config file/environment variables and the UI; no hard-coded paths, so the same code runs as an HA add-on (paths via add-on options). | Partial |
| TR-302 | S | Later: second HA add-on, reached through ingress; no base-URL assumptions (relative URLs in templates and JS). | Open |
| TR-303 | M | Timeouts: all outgoing server requests and all browser `fetch` calls have a timeout (AbortController in the browser). Network errors are caught and shown. | Done |
| TR-304 | S | Retry for failed sync rounds: up to 2 retries after 250 ms, then back-off. Timings configurable (see FR-1000/1002). | Partial |

### 3.4 Logging and diagnostics

| ID | Pri | Requirement | Status |
|----|-----|-------------|--------|
| TR-400 | M | Configurable log level (debug/info/warn/error). | Done |
| TR-401 | M | Log rotation with limited size and file count. | Done |
| TR-402 | S | A **debug export** button in settings. Logs are **not masked** (local use); the UI warns before sharing the export. | Open |

### 3.5 Quality

| ID | Pri | Requirement | Status |
|----|-----|-------------|--------|
| TR-500 | M | pytest unit tests, isolated (temporary DB per test), all green. Currently 29 failures (24 isolation, 1 database isolation, 2 clear-all, 1 config, 1 landing). | Rework |
| TR-501 | M | **Contract tests**: every action the dashboard can produce is validated against the schemas generated from the server. | Partial |
| TR-502 | M | **Browser/UI tests** (Playwright) for the main screens: overview, child detail, rule dialog, hamburger menu, offline banner. | Open |
| TR-503 | W | A live test against a real server is not mandatory; an optional script against the local test server may exist. | – |
| TR-504 | M | Documentation stays in sync: this document, `docs/ServerAPI.md`, and design notes are updated with every feature or fix. | – |

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
| SEC-001 | M | The dashboard listens on **localhost only** and has no login. Remote access comes later through Home Assistant (ingress authentication). |
| SEC-002 | M | The server connection uses HTTPS when the server is not on the local network. Plain HTTP is allowed for localhost/LAN test servers. (Replaces NFR-003 "all communication HTTPS".) |
| SEC-003 | M | The device auth token is stored only in the local database file, never sent to the browser. |
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
| Original goal "own server-side additions" | None exist. The HA add-on wraps the official server and only adds logging patches. |

## 6. Conflicts and open points to confirm

1. **Logging not masked** (decided) vs. HA and sharing: logs and the debug export contain tokens. Acceptable for local use; revisit before the HA add-on (a leaked token gives full access to the family).
2. **Per-app usage** was dropped from v1 because the server has no per-app data for parents.
3. **FR-505** (disable all limits until a time) was not chosen; kept as Should only if wanted.
4. **Server version**: the HA add-on builds `master` of the official server without a pinned version; the verified references are `apiLevel` 7 and 9. Decide whether the add-on pins a version.
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

1. Test isolation (TR-500) and sync correctness (TR-103, FR-200..202, TR-201).
2. Rules, blocked times, categories and apps (FR-300..305, FR-400..404).
3. Extra time, temporary blocking, used time (FR-500..503, FR-600..601).
4. Settings, WebSocket, i18n, themes, UI tests (FR-100..104, FR-207, UI-002..005, TR-502).
5. HA add-on (TR-302).
