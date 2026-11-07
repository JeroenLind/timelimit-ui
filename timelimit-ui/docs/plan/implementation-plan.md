# TimeLimit Dashboard – Implementation Plan

| Item | Value |
|------|-------|
| Version | 1.2 (draft for approval; 1.1 plus requirement FR-307 "rule off for today") |
| Implements | `docs/requirements/requirements.md` v3.0 and `docs/architecture/design.md` v3.0 |
| Protocol | `docs/ServerAPI.md`, `docs/protocol/actions-reference.md` |
| Rule | **This plan makes no design choices.** Where a step needed one, it was asked as a question (section 3); the answers are recorded there and in the design and requirements. New gaps found later go back to the design or requirements first. |

---

## 1. How to read this plan

**Strategy (decided, K0).** The new dashboard is built **next to the old one** in a new package `dashboard/`; what is already correct is reused, the switch-over comes at the end.
- Reused as-is (wire-correct and tested): `action_builder.py`, `action_pusher.py`, `crypto_utils.py`, the generated protocol docs and schemas.
- The old `dashboardV2/` application stays runnable and untouched until step G1; then it is deleted.

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

**Order.** Follows `design.md` §10 (foundation → sync → cleanup → features → frontend → HA). Two additions to that order were approved (K0, K1) and are marked **[deviation]**:
- D1 (frontend base: theme, i18n, navigation) comes **before** the feature steps, so every feature view is built correctly once instead of being reworked.
- G1 (delete the old `dashboardV2/`) is new because of the build-next-to-old strategy.

---

## 2. Overview

| Phase | Step | Result in one line | Size | Decided in §3 |
|-------|------|--------------------|------|------|
| A Foundation | A0 | Development standards: lint, line endings, check command, hooks, decision log | M | T1 |
| | A1 | Baseline and working method fixed | S | K0, Q2, R1 |
| | A2 | Isolated, green, parallel test suite; old tests classified (legacy suite apart) | M | T2 |
| | A3 | Configuration, data folder, secret key, logging, clock and `Secret` type | M | Q9, T1 |
| | A4 | One error envelope for all API routes | M | Q3 |
| | A5 | Fake TimeLimit server (test double) | L | |
| | A6 | Server client with timeouts, gzip, error mapping | M | |
| | A7 | Frontend skeleton with working server-down handling | M | |
| B Sync | B1 | Repository and cache schema keyed by server profile and family id | L | |
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
| | E3a | Rule off for today (FR-307) | M | W1–W6 |
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

## 3. Decisions taken (answers to the plan questions)

All questions of the first version of this plan were answered on 2026-11-06/07 and are now part of the requirements (v3.1) and the design (v3.1). This table is the record; the step texts below already use the answers.

| # | Steps | Question | Answer |
|---|-------|----------|--------|
| K0 | A1, G1 | Build next to the old code or rebuild in place? | **Next to the old code**, new package, cut-over in G1. |
| K1 | D1 | Frontend base before the features (deviation from design §10)? | **Yes**, D1 comes before the features; design §10 updated. |
| Q2 | A1 | Package name and layout | **`dashboard/`** (under `rootfs/usr/bin/`) with sub-folders `routes/`, `services/`, `repository/`, `domain/`, `sync/`, `client/`, `static/`, `templates/`. |
| Q3 | A4, E4 | Error codes and the conflict mechanism | **Accepted list** (design §6, TR-307): `INVALID_INPUT` 400, `SESSION_INVALID` 401, `INVALID_PASSWORD` 403, `NOT_FOUND` 404, `NOT_LINKED` 409, `CONFLICT` 409, `READ_ONLY_OFFLINE` 503, `SERVER_UNREACHABLE` 502, `SERVER_TIMEOUT` 504, `ACTION_NOT_CONFIRMED` 502, `INTERNAL_ERROR` 500. `CONFLICT`: the browser sends the version it started editing with; a mismatch with the cache gives 409. |
| Q4 | B2, E5 | Blocked times per child or per category? | **Per category** (as the server stores them); FR-304 changed. |
| Q5 | B2, E6 | Which category settings (FR-402)? | **All four groups:** flags (block, show time, …), notifications and time warnings, battery limit and network ids, category for unassigned apps and disable limits per category. Flag bits are taken from the server code in B2. |
| Q6 | E1, E10 | How does the parent "Dashboard" come to exist? | **(b)** The dashboard logs in once as an existing parent (password used once, not stored) and creates "Dashboard" itself with `ADD_USER` (DH password container). |
| Q6b | E1 | Import the old dashboard's link? | **No**, register again as a new device. |
| Q6c | E1 | First family on a fresh test server? | With the test-server switch on, the link screen can **create a new family**; its first parent becomes "Dashboard". |
| Q7 | E1 | Tested range for the version warning | **`apiLevel` 7 and 9**; any other value gives a warning (never blocks). |
| Q8 | D1 | Default language and theme | Language follows the browser (nl/en), otherwise **English**; theme follows the **system**. |
| Q9 | A3 | How is a server marked as a test server? | Switch **"This is a test server"** in the settings screen, default off. |
| Q10 | E9 | History when the server returns fewer than 30 days | The dashboard **builds its own daily totals** in the cache (history grows from first use). |
| Q10b | B1, E9 | Does that history survive a cache reset? | **No**, it is ordinary cache and is lost on a reset (TR-310 unchanged). |
| Q11 | E11 | Test section without the switch; `debug_database.html` | **Hidden** (menu item absent, routes 404); `debug_database.html` moves **into** the test section. |
| Q12 | E12 | Where is the audit log shown? | As a **tab "Changes" in child detail**. Entries without a child are still stored; where they are shown is decided when E12 is detailed. |
| Q13 | E10, A3 | Are passwords and the second hash logged? | Secrets are **masked at info level and higher**; **only at debug level** everything is unmasked, also in the debug export. Replaces the earlier "logs not masked"; design §5 and TR-402 updated. |
| R1 | A1 | TR-203 versus TR-310 | **TR-203 removed.** |
| S1 | E1 | Default server and selection | Dropdown in settings: **Official server** (`https://api.timelimit.io`) or **Alternative server**; nothing selected on first start. |
| S2 | E1 | Alternative server fields | Protocol (http/https, default **http**), address and port; stored persistently. |
| S3 | A3, B1, E1 | Switching servers | **Each server has its own profile** (link, cache, counter, pending restores); switching back restores it untouched. |
| T2 | A2, C2, G1 | Old tests until the cut-over | The old suite runs **apart** as the "legacy suite"; only the kept modules (class K) must be green. Definition of done applies to the new suite plus the kept tests; legacy failures do not block and disappear with their code. Classification per file: `old-tests-disposition.md`. |
| T1 | A0, A3, A6, B7, F2 | Development standards | **All ten** proposed standards are included (TR-510..TR-519): ruff, LF endings, injected clock, `Secret` type, timeouts everywhere, type hints with mypy, constraints file, pre-commit, commit convention, decision log. |
| R2 | B1, B3 | Tasks | **Not stored** in v1 (no UI). B3 checks what the server sends when the tasks version is omitted. |

**Rule off for today (new requirement FR-307, asked 2026-11-07):**

| # | Steps | Question | Answer |
|---|-------|----------|--------|
| W1 | B2, E3a | How to emulate "off" when a rule has no switch? | **Remove today's bit** from the rule's days mask (`UPDATE_TIMELIMIT_RULE`) and put it back later; the rest of the rule stays. |
| W2 | E3a | Which midnight and time zone? | The time zone of the **machine running the dashboard**. |
| W3 | E3a | Child's time zone differs from the dashboard's | **Warn** (naming both zones), keep the function available; weekday follows the dashboard. |
| W4 | B1, E3a | Dashboard not running at midnight | Pending restores are in the **database**; at the next start overdue ones run **immediately** with a notice. |
| W5 | E3a | Rule changed or deleted on the server meanwhile | **Do not touch it**, show a notice; the parent decides. |
| W6 | E3a | Edit or delete in the dashboard while off | **Restore first**, then apply the change; short notice. |

Derived from these answers, written into FR-307 and **confirmed by you on 2026-11-07**: (e) switching on again earlier the same day is allowed; (f) not offered for a rule that does not apply today, and if today's bit is the only one the mask becomes 0 until the restore; (g) the list shows "off for today" with the restore time and every switch-off and restore is audit-logged. Design consequences: the restore timer is a fourth trigger in the sync engine (diagram: "Timers"), and the pending restores are kept across a cache reset like the link.

**Still open (not blocking the start):** FR-505 (E13) is built only if you ask for it; audit-log entries without a child (E12).

---

## 4. Phase A – Foundation (design §10.1)

### A0 · Development standards — M
**Refs:** TR-510, 511, 515, 516 (tool part), 517, 518, 519. **Decided:** T1 (§3).
**Work:** `pyproject.toml` with `ruff` (lint and format) and `mypy` (strict on `domain/` and `client/`); `.editorconfig` and `.gitattributes` (LF); `tools/check.py` (ruff, ruff format check, mypy, pytest) as the one entry command; `.pre-commit-config.yaml` (ruff plus the fast unit tests without Playwright); `docs/development/standards.md` (commit convention with the trailers, one commit per step); `docs/decisions/` with a template and the decisions of §3 backfilled as short records; a script that generates the constraints file with `pip-tools`.
**Result (testable):**
- `py -3 tools/check.py` runs on the empty `dashboard/` package and exits 0; a deliberate style error, type error or failing test makes it exit non-zero (shown once).
- A test checks that no tracked text file in the repository contains CRLF (outside binary and explicitly excluded files).
- The pre-commit hook rejects a commit with a ruff error and accepts a clean one.
- The constraints script produces a file from `requirements.txt`; a test checks that every package in `requirements.txt` appears in it.
- A test checks that every decision row of §3 has a record in `docs/decisions/`.

### A1 · Baseline and working method — S
**Refs:** TR-504, `.roo/rules`. **Decided:** K0, Q2, R1 (§3).
**Work:** Tag the current commit (`pre-rebuild`). Record the baseline test run per platform in `docs/plan/baseline.json` (`tools/baseline.py`): 1325 tests collected; on Windows (2026-11-04) 29 failed in 369 s; in the Linux cloud container (2026-11-07) 4 failed (`test_path_separators`, two `ClearAll` tests, `test_test_database_is_in_tests_directory`) in 198 s. The Windows failure list is recorded on your first run of `py -3 tools/baseline.py --record`. Add a dev requirements file (pytest, pytest-xdist, playwright). Create the new package `dashboard/` with the sub-folders of Q2. Create `docs/plan/traceability.md` (requirement → step → test), filled as steps complete.
**Result (testable):**
- `py -3 -m pytest` on the **old** tree reproduces the recorded baseline numbers (a script prints "baseline OK").
- The new, empty package imports (`py -3 -c "import <package>"`) and an empty test folder for it passes in CI/local.
- `traceability.md` lists every Must requirement with its planned step (a test checks that every Must ID of `requirements.md` appears in it).

### A2 · Isolated, green, parallel tests — M
**Refs:** TR-500, `design.md` §9. **Decided:** T2 (§3).
**Work:** Fixture giving every test its own temporary database and log folder for the **new** test tree; remove the shared `test_isolation.db`. Split the old tests with `docs/plan/old-tests-disposition.md` (K keep, R rewrite, S specification, X drop): class K moves into the new test tree and must be green; the rest stays in a separate "legacy" folder/marker, run apart with `pytest -m legacy` and not repaired (T2). A legacy test that fails is only listed. A test that contradicts the new requirements is **not** rewritten silently: it is listed and we go back to the requirements.
**Result:**
- The new suite (including the kept K tests) is green **serially and with `-n auto`**, same pass count both times.
- `docs/plan/old-tests-disposition.md` lists every old test file exactly once (a test compares the list with the files on disk).
- The legacy suite runs apart with its own command and its failures are listed, not blocking.
- Running the suite leaves no file in the repository tree (a test asserts the tree is unchanged: no `*.db`, no `logs/`).
- Per-test timeout 30 s is active; a deliberately hanging test is killed in the demo.

### A3 · Configuration, data folder, secret key, logging — M
**Refs:** TR-300, 301, 305, 306, 400, 401, 512, 513, SEC-001, SEC-004. **Decided:** Q9, T1 (§3).
**Work:** Also here: a `Clock` interface (real and fake, time-zone aware; TR-512) and the `Secret` wrapper / `mask()` function through which tokens, hashes and typed passwords pass (TR-513). One configuration module: precedence *environment > config file > default*; data folder (`data/` next to the app, `/data` in HA); default `127.0.0.1:8100`; masking of secrets in logs at info level and higher, unmasked only at debug (Q13); secret key generated on first start and kept; log level and rotation; timing settings with their defaults (health timeout 3 s, back-off 10→30 s, sync target 5 s, browser timeout 10 s); the setting "This is a test server" (default off, Q9). `data/` goes into `.gitignore`.
**Result:**
- U: precedence table (env wins, then file, then default) for every setting; invalid values give a clear error at start.
- U/I: the secret key is created once and identical after a restart; changing the env var overrides it.
- I: starting the app binds `127.0.0.1:8100`; a connection from another interface is refused (bind test on an ephemeral port).
- I: log files rotate at the configured size and file count.
- U: the fake `Clock` returns a time-zone-aware time and a naive time is refused; `Secret` shows a mask in `repr()`, `str()` and log output at info level and reveals only through `reveal()`.
- M: `py -3 app.py` on Windows creates `data/` and starts on 8100.

### A4 · One error envelope for all API routes — M
**Refs:** TR-307, `design.md` §6. **Decided:** Q3 (§3).
**Work:** One error type and handler producing `{status:"error", code, message, requestId}` with the codes and HTTP status of design §6 (Q3); request id per request, also in the log line. Routes added later must use it.
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
**Refs:** TR-100, 103 (client part), 104, 106, 303, 514, SEC-002, FR-1000.
**Work:** The only module that does HTTP to the TimeLimit server. Configurable timeouts, `clientLevel` 7, gzip with the retry on HTTP 411, mapping of network/HTTP failures to the error classes (`SERVER_UNREACHABLE`, `SESSION_INVALID`, …), HTTPS rule (HTTP only for localhost/LAN).
**Result:**
- I: against the fake: timeout after the configured time (fake made slow), connection refused → `SERVER_UNREACHABLE`, 401 → `SESSION_INVALID`, 411 → retry with `Content-Length`.
- U: a non-local `http://` URL is rejected with a clear message; `localhost` and LAN addresses are accepted.
- Every request carries `clientLevel` 7 (asserted on the fake).
- U: every HTTP call goes through one function that always passes a timeout (the check that enforces it is in B7).

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
**Work:** Repository modules are the only place with SQL. Tables for: devices, users, categories, category apps, rules, blocked times per category, used time per day (including the dashboard's **own daily totals**, Q10; lost on a reset, Q10b), installed apps per device (**no tasks**, R2), version ids per part, audit log, settings, and the **link** (token, own device id, family id, sequence counter). Cache keyed by family id. `reset_cache()` drops the cache tables but keeps link, settings, the sequence counter and the pending restores of "rule off for today" (FR-307, W4). Token also kept in the session file with backup (kept behaviour). No `INSERT OR REPLACE` on sync state; multi-table writes in one transaction.
**Result:**
- U: round trip of every entity; transaction rollback leaves nothing half-written (fault injected mid-write).
- U: `reset_cache()` keeps the sequence counter, link, settings and pending restores (value before = value after).
- U: a schema version mismatch at start triggers the reset and the sequence counter survives.
- U: thread-safety test (concurrent writers) without errors.
- No password is ever written (a test inspects the database file for the test password).

### B2 · Domain: every v1 action — L
**Refs:** TR-100, 101, 102, 501, FR-300..303, 400..403, 500..504, 801, 901. **Decided:** Q4, Q5 (§3).
**Work:** Extend `action_builder.py` (pure, no I/O) to all actions needed in v1: rules (done), categories (`CREATE_CATEGORY`, `DELETE_CATEGORY`, `UPDATE_CATEGORY_TITLE`, `SET_PARENT_CATEGORY`, `UPDATE_CATEGORY_SORTING`, category settings: the four groups of FR-402, Q5), apps (done), blocked times (`UPDATE_CATEGORY_BLOCKED_TIMES`; verify the `times` string format in the server code and write it into `ServerAPI.md`), extra time (`INCREMENT_CATEGORY_EXTRATIME`, `SET_CATEGORY_EXTRA_TIME`), temporary block (`UPDATE_CATEGORY_TEMPORARILY_BLOCKED`), users (`ADD_USER` child done; parent with the DH container), password integrity (`SET_KEEP_SIGNED_IN`, change parent password). Bitmask and blocked-times encoding as pure functions.
**Result:**
- C: for **every** builder, generated valid and invalid inputs are checked against the server schemas (valid pass, invalid raise `ActionError` before a sequence number is used).
- U: property tests: bitmask and blocked-times encode/decode round trip; boundaries (0, 1439, 127).
- U: the verified HMAC vectors still pass; a parent `ADD_USER` container decrypts with the test key pair (ECDH P-256, AES-128-GCM).
- A coverage list in `traceability.md`: every v1 action has a builder and a contract test (a test fails when an action of the v1 list lacks one).

### B3 · Pull with version exchange — L
**Refs:** FR-201, 202, TR-103, D10.
**Work:** `ClientDataStatus` carries all stored versions (devices, users, apps per device, categories `{base, apps, rules, usedTime}`; tasks are not stored, R2 — this step checks what the server sends when the tasks version is omitted); apply every part of `ServerDataStatus` (`devices`, `users`, `categoryBase`, `categoryApp`, `rules` incl. field `e`, `usedTimes`, `apps`, `rmCategories`, `fullVersion`, `apiLevel`); `shouldDoFullSync` handling: forget versions, full re-pull, notice.
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
**Work:** One test that reads the import graph (static analysis, not text search for names) and enforces the layer table of `design.md` §2.1, plus three code-standard rules (TR-512, 513, 514): the domain never calls `now()`/`time.time()` directly, secrets are never formatted into log calls without the `Secret` type, and every HTTP call has a timeout. The layer rules: Routes do not import the repository or server client; only the repository imports `sqlite3`; only the server client imports the HTTP library; the domain imports nothing with I/O.
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
**Work:** Delete the class-X test files that belong to the removed code (`old-tests-disposition.md`), `frontend.py`, `web_server.py`, `api_client.py`, `check_server.py` (in `rootfs/usr/bin`), `add_time_limit_rules*.py`, `update_database.py`, `verify_bcrypt.py`, `test_hash_verify*.py`, the loose `test_*.py` in the repository root, and the tests that only test those files.
**Result:**
- Full suite green; no import of a removed module anywhere (a test imports every remaining module).
- The suite count drops by exactly the removed tests (listed in the commit message).

---

## 7. Phase D – Frontend base (before the features) **[deviation, approved K1]**

### D1 · Theme, i18n, navigation, dialogs — M
**Refs:** UI-002, 003, 004, 005, 006, TR-311. **Decided:** Q8 (§3).
**Work:** Shared CSS with variables (no inline styles); dark theme follows the system with a manual override; `nl.json` / `en.json` with fallback to English and a language switch (default: the browser language if nl or en, otherwise English; Q8); sidebar on desktop, hamburger on small screens (open/close by button, close button, overlay, Escape; `aria-expanded`/`aria-hidden`; focus returns to the button); one confirmation-dialog component; responsive layout for phone and tablet.
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
**Refs:** FR-100, 101 (part), 102, 103, 104, TR-402, FR-1002. **Decided:** Q6, Q6b, Q6c, Q7, Q9 (§3).
**Work:** Settings screen: server dropdown (official / alternative with protocol, address, port; S1, S2), per-server profiles (S3), link (log in once as an existing parent, create "Dashboard" with `ADD_USER`, register as a new device, Q6/Q6b; with the test-server switch on, create a new family, Q6c), connection state, device id (not the token), versions, last sync, timings, log level, language/theme, test-server setting, debug export (unmasked, with the warning). Version/`clientLevel` check on connect (warn only). The server can be switched in the UI; every server keeps its own link and cache. `SESSION_INVALID` shows "link again".
**Result:**
- E: first start without a link shows only the settings/link screen; entering the fake's URL and the credentials of an existing parent creates the parent "Dashboard" (`ADD_USER` is the first action, confirmed), registers a new device and the overview loads; the parent's password is not in the database or the logs at info level.
- E: on a fresh fake server with no family and the switch "This is a test server" off, the link screen offers no "create family"; with the switch on it creates a family whose first parent is "Dashboard".
- I: the link survives a restart and a cache reset.
- E: choosing "Alternative" asks for protocol (default http), address and port; the choice is still there after a restart.
- I: link two fake servers in turn; switching back and forth keeps each link, cache, counter and pending restores separate, and an action is only ever sent to the active server.
- E: a server with `apiLevel` 7 or 9 shows no warning; any other value shows a warning banner but stays usable (Q7).
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

### E3a · Rule off for today — M
**Refs:** FR-307, FR-1100, TR-512. **Decided:** W1–W6 (§3). Needs E3 and B5; the timer part needs B5/B6.
**Work:** In the rule list a button "off for today" (not offered when the rule does not apply today). Switching off pushes `UPDATE_TIMELIMIT_RULE` with today's bit removed and stores a pending restore (rule id, day bit, original days, the state that was set, due time). A timer (a trigger of the sync engine) restores at the dashboard's midnight; at start, overdue restores run at once with a notice. At restore the rule on the server is compared with the state that was set: different or missing → nothing is changed and a notice is shown. Editing or deleting such a rule restores it first. Warning when the child's time zone differs. State "off for today" with the restore time in the list; switch-off and restore are audit-logged.
**Result:**
- C/U: the days mask without today's bit for all 7 weekdays and for masks with one bit (result 0), validated against the schema; a rule that does not apply today is refused before sending.
- I (fake clock): switch off on a Wednesday → the fake shows the rule without bit Wednesday and all other fields unchanged; at midnight (clock advanced) the bit is back and the pending restore is gone; the audit log has both entries.
- I: stop the dashboard before midnight, start it the next afternoon → the restore runs immediately at start and a notice lists it.
- I: change the rule on the fake while it is off → at restore nothing is sent and a notice appears; delete it on the fake → same.
- I/E: edit and delete in the UI while off → the restore is pushed first, then the change; a notice says "off for today" ended.
- I: a cache reset between switch-off and midnight keeps the pending restore.
- I: the server (fake) never sees anything but `UPDATE_TIMELIMIT_RULE` actions for this feature (asserted on the action types).
- U: dashboard time zone ≠ child's time zone → the warning names both zones; the function still works.
- E: the button is disabled with a reason for a rule that does not apply today; "on again" the same day restores at once.

### E4 · Markers, conflicts, rollback — M
**Refs:** FR-205, 206, 208, 209, UI-007. **Decided:** Q3 (§3).
**Work:** Items added by the user show "waiting for server" until confirmed and disappear on failure; entities the server no longer reports are kept and flagged "no longer on server" with a clean-up action; conflict warning when the data being edited changed on the server meanwhile (mechanism per Q3); every action shows pending / confirmed / failed.
**Result:**
- E: with the fake held slow, a new rule shows the marker; on confirmation the marker goes; on rejection the item vanishes with an error.
- I/E: remove a child on the fake → the dashboard keeps it, flagged, and "clean up" removes it from the cache.
- I/E: change a rule on the fake while the edit dialog is open → saving shows the conflict warning; confirming saves (last writer wins).
- U: after a full resync the flags are consistent (no flagged entity that the server still reports).

### E5 · Blocked times — M
**Refs:** FR-304. **Decided:** Q4 (§3).
**Work:** Weekly schedule view/editor (slots per weekday) per category (Q4), using the verified `times` encoding from B2.
**Result:**
- C/U: encoding round trip for random schedules.
- I: edit → cache equals the schedule after the pull; a schedule created in the fake is rendered correctly.
- E: block Mon–Fri 22:00–07:00 by clicking the grid; reload shows the same.

### E6 · Categories — M
**Refs:** FR-400, 401, 402. **Decided:** Q5 (§3).
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
**Refs:** FR-600, 601, FR-602 (not offered). **Decided:** Q10 (§3).
**Work:** Today per category against the limit; the dashboard records its **own daily totals** from each pull so the history grows to 30 days (Q10; lost on a cache reset, Q10b); history per day (7 and 30 days) as a list and a bar chart.
**Result:**
- U: aggregation (today, 7-day, 30-day) for fixtures including day boundaries and time zones.
- I: the pull of `usedTimes` fills the table; E: list and chart show the same numbers for the seeded data.
- U/I: each pull adds or updates the day's total; after a scripted 40-day sequence of pulls the history shows exactly the last 30 days; after a cache reset the history starts again (Q10b).

### E10 · Password actions and the "Dashboard" parent — M
**Refs:** FR-101, 900, 901, 902, TR-102. **Decided:** Q6, Q13 (§3).
**Work:** Password modal per action, only for server-required actions (change parent password, `SET_KEEP_SIGNED_IN` with HMAC); the password is never stored; it is masked in the log at info level and higher and appears only at debug level (Q13); view of the "Dashboard" parent state (keep-signed-in, signed-out warning after `SET_DEVICE_USER`).
**Result:**
- C/I: the password HMAC action is accepted by the fake (which checks the HMAC with the verified method).
- E: wrong password → `INVALID_PASSWORD` (403) message, nothing changes; correct → success; the modal is not shown for rules, categories or extra time.
- E/I: simulate `sign out` → banner and "link again".
- U: the password value does not appear in the database or in any stored session file; with log level info it is not in the log (token, hashes and second hash neither); with level debug it is (Q13).

### E11 · Test section — M
**Refs:** FR-800, 801. **Decided:** Q11, Q6 (§3).
**Work:** Separate section to create family members on a local test server: `ADD_USER` for children and parents (DH container), shown immediately with the marker (E4); available only when the switch "This is a test server" is on (Q9); `debug_database.html` is part of the section (Q11).
**Result:**
- I: add a child → `ADD_USER` is the first action pushed; a non-confirmed push returns 502 and shows an error; add a parent → the fake decrypts the container.
- E: with the switch off the menu item is absent and the section's routes answer 404; with the switch on, users can be added and appear; `debug_database.html` is reachable only there.

### E12 · Audit log — S
**Refs:** FR-1100, 1101. **Decided:** Q12 (§3).
**Work:** Every change through the dashboard is stored (action type, child, result, time) and shown as the tab "Changes" in child detail (Q12); entries without a child are stored too (where they are shown is decided when this step is detailed); entries older than 30 days are removed automatically.
**Result:**
- I: each feature's action creates one entry with the right result (confirmed / not confirmed).
- U: the purge removes entries older than 30 days and keeps newer ones (fake clock, boundary at exactly 30 days).
- E: the tab "Changes" of a child shows the entries of a scripted session, newest first, with the right result per entry.

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
**Refs:** TR-302, TR-301, 516, `design.md` §8.
**Work:** The image build installs from the generated constraints file (A0). `config.yaml`: aarch64, ingress, options (log level, listen address `0.0.0.0` set by the add-on; the server is chosen in the settings screen, design §8.1), data in `/data`. s6 service starts the new dashboard.
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

### G1 · Cut-over **[deviation, approved K0]**
**Refs:** TR-312.
**Work:** Make the new package the entry point (`py -3 app.py` and the s6 service); delete the old `dashboardV2/` application and its tests (the legacy suite ends here), plus the archived duplicate docs. Each R and S file is checked off against the new tests before it goes (`old-tests-disposition.md`).
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
| FR-307 | E3a | | | |
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
| TR-510, 511, 517, 518, 519 | A0 | | TR-512, 513 | A3, B7 |
| TR-514 | A6, B7 | | TR-515 | A0 (config), all steps |
| TR-516 | A0, F2 | | | |
| TR-502 | A7, D1, E-steps | | TR-503, 504 | G2 |
| SEC-001 | A3 | | SEC-002 | A6 |
| SEC-003 | B1, E1 | | SEC-004 | A3 |

Not built on purpose (Won't): FR-602, FR-703, UI-008, TR-204.

## 12. Risks the plan accounts for

1. **The fake server is only as right as our reading of the protocol.** Mitigation: conformance scenarios from `ServerAPI.md`, verified HMAC vectors, and the optional run against your local test server in A5 and G2. No live test has been done against a real server yet.
2. **Silent server failures** (`shouldDoFullSync` on HTTP 200) can hide bugs. Every action test therefore asserts the state after the pull, not only the HTTP status.
3. **Sequence numbers.** A reset or a reused number makes the server skip actions silently; B1 and B4 test this explicitly.
4. **Unmasked logs and no CSRF protection** are accepted for localhost (design §5). Revisit before F2, when `0.0.0.0` is set in the add-on.
5. **Time zones and day boundaries** affect extra time and usage (E8, E9); tests use several zones and midnight.
