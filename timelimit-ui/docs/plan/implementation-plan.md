# TimeLimit Dashboard – Implementation Plan

| Item | Value |
|------|-------|
| Version | 1.0 (draft for approval) |
| Implements | `docs/requirements/requirements.md` v3.0 and `docs/architecture/design.md` v3.0 |
| Protocol | `docs/ServerAPI.md`, `docs/protocol/actions-reference.md` |
| Rule | **This plan makes no design choices.** Where a step needs one, the step is *gated* by a question in section 3. We go back to the design or requirements, record the answer there, and only then start the step. |

---

## 1. How to read this plan

**Strategy (needs your confirmation, K0).** You allowed a new setup. The plan assumes: *build the new dashboard next to the old one, reuse what is already correct, switch over at the end*.
- Reused as-is (already wire-correct and tested): `action_builder.py`, `action_pusher.py`, `crypto_utils.py`, the generated protocol docs and schemas.
- The old `dashboardV2/` application stays runnable and untouched until step G1; then it is deleted.
- If you prefer to rebuild in place, steps A–F stay the same in content but touch the existing files; step G1 disappears. Say so and I adjust.

**Test levels used in every step**

| Tag | Meaning |
|-----|---------|
| U | unit test, no I/O (pytest) |
| C | contract test: produced actions/requests validated against schemas generated from the server |
| I | integration test against the **fake TimeLimit server** (step A5), real SQLite in a temporary folder |
| E | browser test (Playwright) against the running app and the fake server |
| M | short manual check on the Windows laptop (`py -3 app.py`) |

**Definition of done (applies to every step)**
1. The step's own tests pass **and the complete suite is green**, including unrelated tests (serial; and in parallel once A2 is done).
2. Requirement statuses in `requirements.md` are updated; `design.md` and `ServerAPI.md` are updated when behaviour or a gap changes.
3. Committed and pushed to `claudeEnhancedVersion`; Project docs and memory notes are synced.
4. The step's "Result" section is demonstrable: a command or a screen anyone can run.

**Size:** S (≤ 1 day), M (1–3 days), L (> 3 days). Rough relative sizes, not promises.

**Order.** Follows `design.md` §10 (foundation → sync → cleanup → features → frontend → HA). Two additions are consequences of the strategy and are marked **[deviation]**; they need your OK (K0, K1):
- D1 (frontend base: theme, i18n, navigation) comes **before** the feature steps, so every feature view is built correctly once instead of being reworked.
- G1 (delete the old `dashboardV2/`) is new because of the build-next-to-old strategy.

---

## 2. Overview

| Phase | Step | Result in one line | Size | Gate |
|-------|------|--------------------|------|------|
| A Foundation | A1 | Baseline and working method fixed | S | K0, Q2, R1 |
| | A2 | Isolated, green, parallel test suite | M | |
| | A3 | Configuration, data folder, secret key, logging | M | Q9 |
| | A4 | One error envelope for all API routes | M | Q3 |
| | A5 | Fake TimeLimit server (test double) | L | |
| | A6 | Server client with timeouts, gzip, error mapping | M | |
| | A7 | Frontend skeleton with working server-down handling | M | |
| B Sync | B1 | Repository and cache schema keyed by family id | L | |
| | B2 | Domain: every v1 action built and validated | L | Q4, Q5 |
| | B3 | Pull with version exchange | L | |
| | B4 | Push, confirmation, rollback | M | |
| | B5 | Sync worker with queue | M | |
| | B6 | Socket listener, polling fallback, SSE hub | M | |
| | B7 | Architecture test enforcing the layers | S | |
| C Cleanup | C1 | HA s6 service starts the dashboard instead of the legacy UI | S | |
| | C2 | Legacy UI layer and one-off scripts removed | S | |
| D Frontend base | D1 | Theme, i18n, sidebar/hamburger, dialogs **[deviation]** | M | K1, Q8 |
| E Features | E1 | Settings, linking, version warning, debug export | L | Q6, Q7 |
| | E2 | Children overview, child detail, devices (read only) | M | |
| | E3 | Time limit rules | M | |
| | E4 | Pending/stale markers, conflict warning, rollback UI | M | Q3 |
| | E5 | Blocked times | M | Q4 |
| | E6 | Categories | M | Q5 |
| | E7 | Apps per category | M | |
| | E8 | Extra time and temporary blocking | M | |
| | E9 | Used time: today and history | M | Q10 |
| | E10 | Password actions and the "Dashboard" parent | M | Q6, Q13 |
| | E11 | Test section | M | Q11 |
| | E12 | Audit log | S | Q12 |
| | E13 | *Optional:* disable limits until a time (FR-505) | S | decision |
| F Home Assistant | F1 | Runs correctly under an ingress path prefix | S | |
| | F2 | aarch64 add-on with options | M | |
| | F3 | GitHub Actions build to `ghcr.io` | S | |
| G Finish | G1 | Cut-over: old `dashboardV2/` deleted **[deviation]** | S | K0 |
| | G2 | Acceptance: requirement coverage and optional live test | M | |

---

## 3. Questions to settle before the gated steps

Each question is a place where the design or the requirements do not yet decide something the plan needs. **Nothing below is decided here.** Options are listed only to make the question easy to answer.

| # | Gate for | Question | Where the gap is |
|---|----------|----------|------------------|
| K0 | A1, G1 | Build the new dashboard next to the old one (assumed), or rebuild in place? | strategy, not in design |
| K1 | D1 | May the frontend base (D1) come before the features, deviating from design §10 order? | `design.md` §10 |
| Q2 | A1 | Name and folder layout of the new code (design names components, not files or packages). | `design.md` §2 |
| Q3 | A4, E4 | The complete list of error codes with HTTP status. Design names four classes; `TR-307` says "...". FR-208 (conflict warning) also needs a code and a mechanism (e.g. version sent with the edit, answer 409). | `design.md` §6, TR-307, FR-208 |
| Q4 | B2, E5 | **Requirement mismatch:** FR-304 says blocked times are *per child*. In the protocol they are *per category* (`UPDATE_CATEGORY_BLOCKED_TIMES`, `categoryBase.blockedTimes`). Which is meant? | FR-304 vs `ServerAPI.md` |
| Q5 | B2, E6 | FR-402 "category settings as in the official app" is not specific. Which ones, from: block all apps, hide time information, block notifications, battery limit, time warnings, network ids, "category for unassigned apps", disable limits per category? | FR-402 |
| Q6 | E1, E10 | How does the "Dashboard" parent come to exist and how does the dashboard device sign in as it (FR-100/101)? Options: (a) a parent named "Dashboard" is created in the app and the dashboard registers with its credentials; (b) the dashboard creates it itself with `ADD_USER` (needs the DH password container, FR-801); (c) on a test server the dashboard creates the family and its first parent. Also: is an existing link of the old dashboard imported, or does the new dashboard register again? | FR-100, FR-101, FR-801 |
| Q7 | E1 | FR-102: what is the "tested range" that triggers the warning (which `apiLevel`, server versions)? Design says warn, not block. | FR-102 |
| Q8 | D1 | Default language when the browser language is neither Dutch nor English, and the default theme before a choice is made (design says: follow the system). | UI-005, `design.md` §7 |
| Q9 | A3 | How is a server "marked as a test server" (FR-800)? Setting name and where it is changed (add-on option, settings screen, both)? | FR-800, `design.md` §8 |
| Q10 | E9 | FR-601 wants 7 and 30 days. The protocol delivers `usedTimes` per category, but not which days. E9 starts with a check against the server code and the fake server; if the server returns fewer days, the requirement changes. | FR-601 |
| Q11 | E11 | Is the test section hidden or only disabled on a production server? Is `debug_database.html` part of it? | FR-800, `design.md` §11 |
| Q12 | E12 | UI-001 lists four screens; none shows the audit log (FR-1100). Where is it shown (a tab in child detail, a page, settings)? | UI-001, FR-1100 |
| Q13 | E10 | Logs are not masked (design §5). Does that include the parent password typed in the modal and the password HMAC key (second hash)? Design §5 says the password is never *stored*, but says nothing about logging it. | `design.md` §5 |
| R1 | A1 | **Requirement conflict:** TR-203 ("versioned migrations") contradicts TR-310 and the design (drop the cache and re-sync). Remove TR-203? | requirements |
| R2 | E2 | The cache stores tasks (design §4) but no requirement or screen uses them. Cache only, no UI in v1? | design §4 |

---

## 4. Phase A – Foundation (design §10.1)

### A1 · Baseline and working method — S
**Refs:** TR-504, `.roo/rules`. **Gate:** K0, Q2, R1.
**Work:** Tag the current commit (`pre-rebuild`). Record the baseline test run (1325 tests, 29 failed, 369 s). Add a dev requirements file (pytest, pytest-xdist, playwright). Fix the new code's folder layout (answer of Q2). Create `docs/plan/traceability.md` (requirement → step → test), filled as steps complete.
**Result (testable):**
- `py -3 -m pytest` on the **old** tree reproduces the recorded baseline numbers (a script prints "baseline OK").
- The new, empty package imports (`py -3 -c "import <package>"`) and an empty test folder for it passes in CI/local.
- `traceability.md` lists every Must requirement with its planned step (a test checks that every Must ID of `requirements.md` appears in it).

### A2 · Isolated, green, parallel tests — M
**Refs:** TR-500, `design.md` §9.
**Work:** Fixture giving every test its own temporary database and log folder; remove the shared `test_isolation.db`; fix the 29 failing tests (triage: isolation → fixture; the rest → fix the test or the code). A test that contradicts the new requirements is **not** rewritten silently: it is listed and we go back to the requirements.
**Result:**
- Full suite green **serially and with `-n auto`**, same pass count both times.
- Running the suite leaves no file in the repository tree (a test asserts the tree is unchanged: no `*.db`, no `logs/`).
- Per-test timeout 30 s is active; a deliberately hanging test is killed in the demo.

### A3 · Configuration, data folder, secret key, logging — M
**Refs:** TR-300, 301, 305, 306, 400, 401, SEC-001, SEC-004. **Gate:** Q9.
**Work:** One configuration module: precedence *environment > config file > default*; data folder (`data/` next to the app, `/data` in HA); default `127.0.0.1:8100`; secret key generated on first start and kept; log level and rotation; timing settings with their defaults (health timeout 3 s, back-off 10→30 s, sync target 5 s, browser timeout 10 s); test-server setting (answer of Q9). `data/` goes into `.gitignore`.
**Result:**
- U: precedence table (env wins, then file, then default) for every setting; invalid values give a clear error at start.
- U/I: the secret key is created once and identical after a restart; changing the env var overrides it.
- I: starting the app binds `127.0.0.1:8100`; a connection from another interface is refused (bind test on an ephemeral port).
- I: log files rotate at the configured size and file count.
- M: `py -3 app.py` on Windows creates `data/` and starts on 8100.

### A4 · One error envelope for all API routes — M
**Refs:** TR-307, `design.md` §6. **Gate:** Q3.
**Work:** One error type and handler producing `{status:"error", code, message, requestId}` with the agreed codes and HTTP status; request id per request, also in the log line. Routes added later must use it.
**Result:**
- U: every code maps to its HTTP status; unknown exceptions give the generic code and 500, with no stack trace in the response.
- I: a test iterates over **all registered API routes** with a forced failure and asserts the envelope (the test fails when a new route returns another error format).
- The `requestId` in the response is found in the log.

### A5 · Fake TimeLimit server (test double) — L
**Refs:** TR-501, `design.md` §9, `ServerAPI.md`.
**Work:** A small HTTP + Socket.IO server used only by tests. It implements the endpoints the dashboard uses (`/time`, `/auth/*`, `/sync/*`, `/child/*`, `/parent/*`) with the strict schemas generated from the server (`additionalProperties:false`), version-based `pull-status`, `push-actions` with the **silent failure** behaviour (`shouldDoFullSync:true`, HTTP 200, failed actions consume sequence numbers), integrity checks (device and password HMAC), WebSocket `should sync`. It can be told to go down, be slow, or reject an action.
**Result:**
- U/I: a conformance suite runs the *same* scenarios against the fake and checks the documented behaviour of each endpoint (request validation, sequence rules, version handling). A deliberately malformed request is rejected like the real server.
- The suite uses the two verified HMAC test vectors.
- The fake starts in < 1 s and runs on an ephemeral port (fixture).
- M (optional, once): the same conformance scenarios run against your local test server and differences are listed in `ServerAPI.md` (not required to pass step A5).

### A6 · Server client — M
**Refs:** TR-100, 103 (client part), 104, 106, 303, SEC-002, FR-1000.
**Work:** The only module that does HTTP to the TimeLimit server. Configurable timeouts, `clientLevel` 7, gzip with the retry on HTTP 411, mapping of network/HTTP failures to the error classes (`SERVER_UNREACHABLE`, `SESSION_INVALID`, …), HTTPS rule (HTTP only for localhost/LAN).
**Result:**
- I: against the fake: timeout after the configured time (fake made slow), connection refused → `SERVER_UNREACHABLE`, 401 → `SESSION_INVALID`, 411 → retry with `Content-Length`.
- U: a non-local `http://` URL is rejected with a clear message; `localhost` and LAN addresses are accepted.
- Every request carries `clientLevel` 7 (asserted on the fake).

### A7 · Frontend skeleton with server-down handling — M
**Refs:** TR-303, TR-311 (first part), FR-1000..1003, UI-002 (hamburger kept), NFR-003.
**Work:** Jinja base page and ES modules `api`, `state`, `i18n` (stub). `api` uses `AbortController`; health check on load; offline banner, read-only mode (controls disabled), reconnect polling with back-off and the retry button. A single placeholder page ("overview") with one read-only list from the cache.
**Result:**
- E (fake up/down): server up → no banner; stop the fake → banner appears within timeout + 1 s, all change controls disabled; start it again → banner disappears and data refreshes; the retry button triggers an immediate check; back-off intervals match the configuration; no request queue grows while down (counted on the fake).
- E: a request that hangs longer than 10 s is aborted and shown as `SERVER_UNREACHABLE`.
- This replaces the tests that only checked the JS text.

---

## 5. Phase B – Sync (design §10.2)

### B1 · Repository and cache schema — L
**Refs:** TR-200, 201, 202, 310, FR-103, FR-206 (storage), SEC-003, `design.md` §4.
**Work:** Repository modules are the only place with SQL. Tables for: devices, users, categories, category apps, rules, blocked times, used time per day, tasks, installed apps per device, version ids per part, audit log, settings, and the **link** (token, own device id, family id, sequence counter). Cache keyed by family id. `reset_cache()` drops the cache tables but keeps link, settings and the sequence counter. Token also kept in the session file with backup (kept behaviour). No `INSERT OR REPLACE` on sync state; multi-table writes in one transaction.
**Result:**
- U: round trip of every entity; transaction rollback leaves nothing half-written (fault injected mid-write).
- U: `reset_cache()` keeps the sequence counter, link and settings (value before = value after).
- U: a schema version mismatch at start triggers the reset and the sequence counter survives.
- U: thread-safety test (concurrent writers) without errors.
- No password is ever written (a test inspects the database file for the test password).

### B2 · Domain: every v1 action — L
**Refs:** TR-100, 101, 102, 501, FR-300..303, 400..403, 500..504, 801, 901. **Gate:** Q4, Q5.
**Work:** Extend `action_builder.py` (pure, no I/O) to all actions needed in v1: rules (done), categories (`CREATE_CATEGORY`, `DELETE_CATEGORY`, `UPDATE_CATEGORY_TITLE`, `SET_PARENT_CATEGORY`, `UPDATE_CATEGORY_SORTING`, category settings per Q5), apps (done), blocked times (`UPDATE_CATEGORY_BLOCKED_TIMES`; verify the `times` string format in the server code and write it into `ServerAPI.md`), extra time (`INCREMENT_CATEGORY_EXTRATIME`, `SET_CATEGORY_EXTRA_TIME`), temporary block (`UPDATE_CATEGORY_TEMPORARILY_BLOCKED`), users (`ADD_USER` child done; parent with the DH container), password integrity (`SET_KEEP_SIGNED_IN`, change parent password). Bitmask and blocked-times encoding as pure functions.
**Result:**
- C: for **every** builder, generated valid and invalid inputs are checked against the server schemas (valid pass, invalid raise `ActionError` before a sequence number is used).
- U: property tests: bitmask and blocked-times encode/decode round trip; boundaries (0, 1439, 127).
- U: the verified HMAC vectors still pass; a parent `ADD_USER` container decrypts with the test key pair (ECDH P-256, AES-128-GCM).
- A coverage list in `traceability.md`: every v1 action has a builder and a contract test (a test fails when an action of the v1 list lacks one).

### B3 · Pull with version exchange — L
**Refs:** FR-201, 202, TR-103, D10.
**Work:** `ClientDataStatus` carries all stored versions (devices, users, apps per device, categories `{base, apps, rules, usedTime, tasks}`); apply every part of `ServerDataStatus` (`devices`, `users`, `categoryBase`, `categoryApp`, `rules` incl. field `e`, `usedTimes`, `tasks`, `apps`, `rmCategories`, `fullVersion`, `apiLevel`); `shouldDoFullSync` handling: forget versions, full re-pull, notice.
**Result:**
- I: for a scripted server state, after a pull the cache equals the server state in every table (a helper compares the two).
- I: a second pull sends the stored versions and the fake answers with no data (asserted request body and empty response).
- I: server changes of each kind (rule changed, category deleted via `rmCategories`, app list changed, new used time) are visible in the cache after the next pull.
- I: `shouldDoFullSync` → versions cleared, one full re-pull, notice flag set.
- I: applying the same response twice is idempotent.

### B4 · Push, confirmation, rollback — M
**Refs:** FR-200, 203, 204, 209, TR-304.
**Work:** The SyncService push path: build with the domain, push with `action_pusher` (device integrity; sequence numbers reserved before sending; max 25 per request), then an immediate pull; **confirmed only when the server does not ask for a full sync**; unconfirmed → `ACTION_NOT_CONFIRMED` and the state from the pull (rollback).
**Result:**
- I: accepted action → confirmed, cache shows the result after the pull.
- I: action the fake rejects silently → not confirmed, error `ACTION_NOT_CONFIRMED`, cache equals the server (change not present).
- I: 60 actions → three requests of 25/25/10 with consecutive sequence numbers; sequence numbers keep counting after an unconfirmed action.
- U/I: restart between two pushes → the counter continues (no reuse).
- I: network failure during push → `SERVER_UNREACHABLE`, **no** sequence number is lost twice (documented rule: reserved numbers are consumed).

### B5 · Sync worker with queue — M
**Refs:** TR-309, TR-304, NFR-001/002.
**Work:** One worker thread with a job queue; all sync work (user change, socket, poller) is enqueued; jobs run strictly one at a time and in order; requests wait for their job's result; retry on failed rounds (2 retries after 250 ms, then back-off; timings from configuration).
**Result:**
- I: 20 concurrent enqueues → executed serially in order (the fake records the maximum number of parallel requests: 1).
- I: a job failing with a network error is retried as specified; after the retries the caller gets `SERVER_UNREACHABLE`.
- I: sync target: a change is visible in the cache within the configured target on the fake (measured).
- U: the worker stops cleanly on shutdown (no hanging thread; test with a timeout).

### B6 · Socket listener, polling fallback, SSE hub — M
**Refs:** FR-207, TR-105, `design.md` §3.
**Work:** Listener thread with Socket.IO (`devicelogin`, `should sync`, `sign out`) and reconnect back-off; enqueue a pull on `should sync`; polling fallback while the socket is down (interval configurable); SSE hub streaming events to the browser when the cache changed.
**Result:**
- I: the fake emits `should sync` → one pull runs → an SSE event reaches a test client within the target.
- I: stop the fake's socket → polling starts within one interval; socket back → polling stops.
- I: `sign out` event → state `SESSION_INVALID`, UI banner "link again" (E test in E1).
- I: reconnect intervals grow as configured (fake records connect times).

### B7 · Architecture test — S
**Refs:** TR-308, `design.md` §2.
**Work:** One test that reads the import graph (static analysis, not text search for names) and enforces the layer table of `design.md` §2.1: Routes do not import the repository or server client; only the repository imports `sqlite3`; only the server client imports the HTTP library; the domain imports nothing with I/O.
**Result:**
- The test passes on the new package; introducing a forbidden import in a scratch change makes it fail (shown once in the demo).

---

## 6. Phase C – Cleanup (design §10.3)

### C1 · HA s6 service starts the dashboard — S
**Refs:** TR-312, TR-302 (part), `design.md` §8.
**Work:** In the add-on, make `dashboard-v2` the enabled service and remove `web-server` from the s6 service list and the Dockerfile references. (At this point it starts the current `dashboardV2` application; the new one replaces it in G1.)
**Result:**
- U: a test parses the s6 files and asserts: `dashboard-v2` is in `user/contents.d`, `web-server` is not, and the `run` script's target file exists.
- U: the Dockerfile references no legacy file.
- M (if an HA test instance is available): the add-on starts and `GET /api/health` answers.

### C2 · Legacy UI layer and one-off scripts removed — S
**Refs:** TR-312.
**Work:** Delete `frontend.py`, `web_server.py`, `api_client.py`, `check_server.py` (in `rootfs/usr/bin`), `add_time_limit_rules*.py`, `update_database.py`, `verify_bcrypt.py`, `test_hash_verify*.py`, the loose `test_*.py` in the repository root, and the tests that only test those files.
**Result:**
- Full suite green; no import of a removed module anywhere (a test imports every remaining module).
- The suite count drops by exactly the removed tests (listed in the commit message).

---

## 7. Phase D – Frontend base (before the features) **[deviation, gate K1]**

### D1 · Theme, i18n, navigation, dialogs — M
**Refs:** UI-002, 003, 004, 005, 006, TR-311. **Gate:** Q8.
**Work:** Shared CSS with variables (no inline styles); dark theme follows the system with a manual override; `nl.json` / `en.json` with fallback to English and a language switch; sidebar on desktop, hamburger on small screens (open/close by button, close button, overlay, Escape; `aria-expanded`/`aria-hidden`; focus returns to the button); one confirmation-dialog component; responsive layout for phone and tablet.
**Result:**
- E: at 1280 px the sidebar is visible and there is no hamburger; at 390 px the hamburger shows and works by all four ways, with the right ARIA state and focus.
- E: emulated `prefers-color-scheme: dark` → dark theme; manual override wins and is remembered.
- U: every key of `en.json` exists in `nl.json` and vice versa (a test lists missing keys); a missing key shows the English text.
- E: language switch changes all visible texts of the skeleton page.
- U: no `style="` attribute in any template (test).
- E: the confirmation dialog traps focus and cancels with Escape.

---

## 8. Phase E – Features (design §10.4)

Every feature step is a **vertical slice**: domain action → service → route → view, with the same four checks: **C** (action against the schema), **I** (round trip with the fake: action pushed, confirmed, cache updated), **E** (the user scenario in the browser, including a failure case), and the offline rule (controls disabled when the server is down).

### E1 · Settings, linking, version warning, debug export — L
**Refs:** FR-100, 101 (part), 102, 103, 104, TR-402, FR-1002. **Gate:** Q6, Q7.
**Work:** Settings screen: server URL, link (register a new device as chosen in Q6), connection state, device id (not the token), versions, last sync, timings, log level, language/theme, test-server setting, debug export (unmasked, with the warning). Version/`clientLevel` check on connect (warn only). Server URL changeable in the UI. `SESSION_INVALID` shows "link again".
**Result:**
- E: first start without a link shows only the settings/link screen; entering the fake's URL links the device; the overview then loads.
- I: the link survives a restart and a cache reset.
- E: a server with an unexpected `apiLevel`/version shows a warning banner but stays usable (Q7 range).
- E: the token is never present in any page, script or API response (test scans responses).
- E: debug export downloads a file and the warning appears first.

### E2 · Children overview, child detail, devices — M
**Refs:** FR-700, 701, 702, UI-001, R2.
**Work:** Overview of children (status, today's used time, quick-action slots), child detail shell (tabs for rules, categories, apps, blocked times, usage), read-only devices (model, last connection, current user). Tasks are cached only (R2).
**Result:**
- E: with a seeded fake family (2 children, 3 categories, 2 devices) the overview and each child detail show the expected names and numbers.
- E: opening a child that was removed on the server shows the "no longer on server" state instead of an error.
- E: layout check at phone width (no horizontal scroll).

### E3 · Time limit rules — M
**Refs:** FR-300..303, 305, 306, FR-900, UI-006.
**Work:** Rule table per category and a rule dialog (time in minutes, day checkboxes → bitmask in one place, optional time window HH:MM, session length, pause, per-day flag, expiry). Create, edit, delete with confirmation. Device integrity, no password.
**Result:**
- C: create, update (flat fields, no `categoryId`) and delete actions validate.
- I: create → rule appears with the same values after the pull, including a rule pulled from the server with field `e`.
- E: create a rule with days Mon–Fri and 90 minutes; the table shows "Mon–Fri · 1 h 30"; editing and deleting (with confirm) work; invalid input (end before start, time window > 1439) shows a field message and sends nothing (fake sees no request).
- I: the fake rejects the action → the UI reverts and shows the error (links to E4).

### E4 · Markers, conflicts, rollback — M
**Refs:** FR-205, 206, 208, 209, UI-007. **Gate:** Q3.
**Work:** Items added by the user show "waiting for server" until confirmed and disappear on failure; entities the server no longer reports are kept and flagged "no longer on server" with a clean-up action; conflict warning when the data being edited changed on the server meanwhile (mechanism per Q3); every action shows pending / confirmed / failed.
**Result:**
- E: with the fake held slow, a new rule shows the marker; on confirmation the marker goes; on rejection the item vanishes with an error.
- I/E: remove a child on the fake → the dashboard keeps it, flagged, and "clean up" removes it from the cache.
- I/E: change a rule on the fake while the edit dialog is open → saving shows the conflict warning; confirming saves (last writer wins).
- U: after a full resync the flags are consistent (no flagged entity that the server still reports).

### E5 · Blocked times — M
**Refs:** FR-304. **Gate:** Q4.
**Work:** Weekly schedule view/editor (slots per weekday) at the level decided in Q4, using the verified `times` encoding from B2.
**Result:**
- C/U: encoding round trip for random schedules.
- I: edit → cache equals the schedule after the pull; a schedule created in the fake is rendered correctly.
- E: block Mon–Fri 22:00–07:00 by clicking the grid; reload shows the same.

### E6 · Categories — M
**Refs:** FR-400, 401, 402. **Gate:** Q5.
**Work:** Create, rename, delete (confirm states the number of apps and rules removed), order and parent category, and the settings chosen in Q5.
**Result:**
- C/I: each action round trip.
- E: create a category, rename it, move it under another, reorder; delete shows the counts.
- I: deleting a category on the fake (`rmCategories`) removes it, with its rules and apps, from the cache.
- I: a cycle in the parent relation is refused before sending (U on the domain).

### E7 · Apps per category — M
**Refs:** FR-403, 404, 405.
**Work:** App list from the child's device (installed apps as synced), assign and remove apps; manual package names when the list is unreadable (encrypted clientLevel).
**Result:**
- I: assign apps → the pull shows them in the category and no longer in the previous one (move semantics).
- E: select 3 apps and assign; labels and package names are shown; an encrypted-list scenario in the fake shows the explanation and the manual field.
- C: `ADD_CATEGORY_APPS`/`REMOVE_CATEGORY_APPS` validate; duplicates are refused before sending.

### E8 · Extra time and temporary blocking — M
**Refs:** FR-500..504.
**Work:** Buttons +15/+30/+60, free minutes, today only (`day`), subtract/revert (down to zero), temporary block until a time, one-shot buttons ("block now for 1 hour").
**Result:**
- C/I: `INCREMENT_CATEGORY_EXTRATIME` / `SET_CATEGORY_EXTRA_TIME` with today's day number (computed in the child's time zone: U tests with several zones and around midnight); `UPDATE_CATEGORY_TEMPORARILY_BLOCKED` with `endTime`.
- E: +30 then −15 shows 15 extra minutes; subtracting more than available stops at zero; "block 1 hour" shows the end time; the block disappears at the end time (fake clock).

### E9 · Used time — M
**Refs:** FR-600, 601, FR-602 (not offered). **Gate:** Q10.
**Work:** First verify what days the server returns (server code and fake), then: today per category against the limit; history per day (7 and 30 days) as a list and a bar chart.
**Result:**
- U: aggregation (today, 7-day, 30-day) for fixtures including day boundaries and time zones.
- I: the pull of `usedTimes` fills the table; E: list and chart show the same numbers for the seeded data.
- If the server returns fewer than 30 days: the requirement is changed first (gate), not the test.

### E10 · Password actions and the "Dashboard" parent — M
**Refs:** FR-101, 900, 901, 902, TR-102. **Gate:** Q6, Q13.
**Work:** Password modal per action, only for server-required actions (change parent password, `SET_KEEP_SIGNED_IN` with HMAC); the password is never stored (whether it may appear in the unmasked log is question Q13); view of the "Dashboard" parent state (keep-signed-in, signed-out warning after `SET_DEVICE_USER`).
**Result:**
- C/I: the password HMAC action is accepted by the fake (which checks the HMAC with the verified method).
- E: wrong password → `INVALID_INPUT`-class message, nothing changes; correct → success; the modal is not shown for rules, categories or extra time.
- E/I: simulate `sign out` → banner and "link again".
- U: the password value does not appear in the database or in any stored session file (and, depending on Q13, not in the log).

### E11 · Test section — M
**Refs:** FR-800, 801. **Gate:** Q11, Q6.
**Work:** Separate section to create family members on a local test server: `ADD_USER` for children and parents (DH container), shown immediately with the marker (E4); available according to the test-server setting.
**Result:**
- I: add a child → `ADD_USER` is the first action pushed; a non-confirmed push returns 502 and shows an error; add a parent → the fake decrypts the container.
- E: with the test-server setting off the section is not available (hidden or disabled per Q11); on, users can be added and appear.

### E12 · Audit log — S
**Refs:** FR-1100, 1101. **Gate:** Q12.
**Work:** Every change through the dashboard is stored (action type, child, result, time) and shown where Q12 decides; entries older than 30 days are removed automatically.
**Result:**
- I: each feature's action creates one entry with the right result (confirmed / not confirmed).
- U: the purge removes entries older than 30 days and keeps newer ones (fake clock, boundary at exactly 30 days).
- E: the list shows the entries of a scripted session.

### E13 · *Optional:* disable limits until a time (FR-505) — S
**Refs:** FR-505 (Should). **Gate:** decision whether wanted.
**Result (if built):** C/I/E like E8 with `SET_USER_DISABLE_LIMITS_UNTIL`.

---

## 9. Phase F – Home Assistant (design §10.6)

### F1 · Runs under an ingress path prefix — S
**Refs:** TR-302.
**Work:** All URLs in templates, JS, SSE and API calls are relative; the app honours the proxy headers.
**Result:** E: the whole E-suite runs a second time through a test reverse proxy that serves the app under `/api/hassio_ingress/<token>/`; no request goes to the root path (the proxy logs any request outside the prefix and the test fails on it).

### F2 · aarch64 add-on with options — M
**Refs:** TR-302, TR-301, `design.md` §8.
**Work:** `config.yaml`: aarch64, ingress, options (server URL default from the server add-on's internal hostname, log level, test-server mode, listen address `0.0.0.0` set by the add-on), data in `/data`. s6 service starts the new dashboard.
**Result:**
- U: the options → configuration mapping is tested with sample `options.json`.
- U: a schema check of `config.yaml` (HA add-on schema validator).
- CI: the image builds for aarch64 and a smoke test (container start, `GET /api/health`) passes.
- M: on your HA the add-on starts from the sidebar and shows the overview.

### F3 · GitHub Actions to `ghcr.io` — S
**Refs:** `design.md` §8.
**Work:** Workflow that builds the image on a version change and pushes it; version from one source. The Windows version is not built by GitHub.
**Result:** a run on a test tag builds and pushes the image; the version in the image, `config.yaml` and the app are identical (a test compares them).

---

## 10. Phase G – Finish

### G1 · Cut-over **[deviation, gate K0]**
**Refs:** TR-312.
**Work:** Make the new package the entry point (`py -3 app.py` and the s6 service); delete the old `dashboardV2/` application and its tests, plus the archived duplicate docs.
**Result:** full suite green; `py -3 app.py` starts the new dashboard (M); a test imports every remaining module; no reference to the removed package remains (import-graph test).

### G2 · Acceptance — M
**Refs:** all Must requirements, NFR-001..004, TR-503, TR-504.
**Work:** Requirement coverage report (every Must has a passing test; every Should/Could is marked done or consciously open); full E-suite on desktop and phone viewports; optional scripted run against your local test server (opt-in); documents synced (`requirements.md`, `design.md`, `ServerAPI.md`, Project docs).
**Result:**
- `traceability.md` has **no Must without a passing test** (a test fails otherwise).
- The suite is green serially and in parallel; the run time is recorded.
- M: a 20-minute walkthrough on the laptop: link, create a rule, grant extra time, view usage, take the server down (banner, read-only), bring it back.

---

## 11. Requirement coverage (Must/Should)

| Requirement | Step | | Requirement | Step |
|-------------|------|-|-------------|------|
| FR-100..104 | E1 | | FR-700..702 | E2 |
| FR-200, 203, 204 | B4, B5 | | FR-800, 801 | E11 |
| FR-201, 202 | B3 | | FR-900 | E3, B4 |
| FR-205, 206, 208, 209 | E4 | | FR-901, 902 | E10 |
| FR-207 | B6 | | FR-1000..1003 | A7 |
| FR-300..303, 305, 306 | E3 | | FR-1100, 1101 | E12 |
| FR-304 | E5 | | UI-001 | E1, E2, E11 |
| FR-400..402 | E6 | | UI-002..006 | D1 |
| FR-403..405 | E7 | | UI-007 | E4 |
| FR-500..504 | E8 | | NFR-001, 002 | B5 |
| FR-505 (S) | E13 | | NFR-003 | A7 |
| FR-600, 601 | E9 | | NFR-004 | D1, A4 |
| TR-100, 101, 102 | B2 | | TR-300, 301, 305, 306 | A3 |
| TR-103 | B3 | | TR-307 | A4 |
| TR-104, 106 (S) | A6 | | TR-308 | B7 |
| TR-105 (S) | B6 | | TR-309 | B5 |
| TR-200, 201, 202, 310 | B1 | | TR-304 (S) | B5 |
| TR-302 | C1, F1, F2 | | TR-311 | A7, D1 |
| TR-303 | A6, A7 | | TR-312 | C1, C2, G1 |
| TR-400, 401 | A3 | | TR-402 (S) | E1 |
| TR-500 | A2 | | TR-501 | A5, B2 |
| TR-502 | A7, D1, E-steps | | TR-503, 504 | G2 |
| SEC-001 | A3 | | SEC-002 | A6 |
| SEC-003 | B1, E1 | | SEC-004 | A3 |
| TR-203 | R1 (remove) | | | |

Not built on purpose (Won't): FR-602, FR-703, UI-008, TR-204.

## 12. Risks the plan accounts for

1. **The fake server is only as right as our reading of the protocol.** Mitigation: conformance scenarios from `ServerAPI.md`, verified HMAC vectors, and the optional run against your local test server in A5 and G2. No live test has been done against a real server yet.
2. **Silent server failures** (`shouldDoFullSync` on HTTP 200) can hide bugs. Every action test therefore asserts the state after the pull, not only the HTTP status.
3. **Sequence numbers.** A reset or a reused number makes the server skip actions silently; B1 and B4 test this explicitly.
4. **Unmasked logs and no CSRF protection** are accepted for localhost (design §5). Revisit before F2, when `0.0.0.0` is set in the add-on.
5. **Time zones and day boundaries** affect extra time and usage (E8, E9); tests use several zones and midnight.
