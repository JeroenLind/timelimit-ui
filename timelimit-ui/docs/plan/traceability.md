# Traceability: requirement → step → test

Created in step A1 from `docs/plan/implementation-plan.md` §11. The *Test* column is filled in by each step when its tests exist (file or test name). A test (`tools/tests/test_traceability.py`) checks that every Must requirement of `requirements.md` has a row with a step.

| Requirement | Pri | Step | Test | Summary |
|---|---|---|---|---|
| FR-100 | M | E1 | – | On first start the dashboard shows a settings screen where the server is selected with a d |
| FR-101 | M | E1 | – | The dashboard device is signed in as a separate parent user "Dashboard" (never as a person |
| FR-103 | M | E1 | – | Only one family per installation. Switching family means resetting the installation. |
| FR-200 | M | B4, B5 | – | Sync starts automatically when the dashboard starts and after every change, without user a |
| FR-201 | M | B3 | – | Pull sends the versions the dashboard holds (devices, users, per-category data, rules, app |
| FR-202 | M | B3 | – | After shouldDoFullSync the dashboard forgets all versions, fully re-pulls, refreshes the U |
| FR-203 | M | B4, B5 | – | The server never reports a failed action (HTTP 200, shouldDoFullSync:true). The dashboard  |
| FR-204 | M | B4, B5 | – | Sequence numbers are persistent per device, start at 0, and are reserved before sending. M |
| FR-205 | M | E4 | – | A newly added item (e.g. a user in the test section) is shown immediately with the marker  |
| FR-206 | M | E4 | – | Users and other entities that the server no longer reports are kept and flagged "no longer |
| FR-207 | M | B6 | – | A change by another parent or by the app appears instantly through the server WebSocket (s |
| FR-208 | M | E4 | – | Conflicts: last writer wins. If the data being edited changed on the server in the meantim |
| FR-209 | M | E4 | – | If an action fails or is not confirmed, the UI change is reverted and a notice is shown (m |
| FR-300 | M | E3 | – | Per category, parents can create, view, edit and delete rules (CREATE/UPDATE/DELETE_TIMELI |
| FR-301 | M | E3 | – | Days use the bitmask Mon=1, Tue=2, Wed=4, Thu=8, Fri=16, Sat=32, Sun=64 (0–127; 127 = ever |
| FR-302 | M | E3 | – | Time is entered in minutes (0 = no time allowed), time windows as HH:MM 24 h (0–1439 minut |
| FR-303 | M | E3 | – | Creating a rule uses the nested rule object; updating uses flat fields without categoryId  |
| FR-304 | M | E5 | – | Weekly blocked-time schedule per category (as the server stores it: slots per weekday, UPD |
| FR-305 | M | E3 | – | Deleting a rule asks for confirmation. |
| FR-307 | M | E3a | – | Rule off for today. A parent can switch a time limit rule off for the current day only. Th |
| FR-400 | M | E6 | – | Create, rename and delete categories per child. Deleting asks for confirmation and states  |
| FR-401 | M | E6 | – | Set the order and the parent category of a category. |
| FR-402 | M | E6 | – | Category settings, four groups: (1) category flags (block, show time, etc.; bit meanings t |
| FR-403 | M | E7 | – | Assign and remove apps for a category (ADD_CATEGORY_APPS, REMOVE_CATEGORY_APPS). Adding mo |
| FR-404 | M | E7 | – | The selectable app list comes from the child's device (installed apps as synced by the dev |
| FR-500 | M | E8 | – | Grant extra time to a child per category with fixed buttons +15 / +30 / +60 minutes and fr |
| FR-501 | M | E8 | – | Extra time applies to today only. |
| FR-502 | M | E8 | – | Extra time can be reverted/subtracted (down to zero). |
| FR-503 | M | E8 | – | A category can be temporarily blocked until a chosen time. |
| FR-600 | M | E9 | – | Show today's used time per category and child, against the limit. |
| FR-601 | M | E9 | – | Show the history per day (7 and 30 days) per category as a list and a bar chart. The dashb |
| FR-700 | M | E2 | – | Overview of all children: status, today's used time, quick actions (extra time, block). |
| FR-701 | M | E2 | – | Child detail screen: categories, rules, apps, blocked times, used time. |
| FR-800 | M | E11 | – | A clearly separated "Test" section lets the parent create family members (ADD_USER) for a  |
| FR-801 | M | E11 | – | Adding a user pushes ADD_USER first; a 502 is shown when the server does not confirm. Pare |
| FR-900 | M | B4, E3 | – | Rules, categories, extra time and blocking use device integrity: no password prompt. |
| FR-901 | M | E10 | – | A password prompt (modal, per action, password never stored) appears only for server-requi |
| FR-1000 | M | A7 | – | Health check on page load with a configurable timeout (default 3 s). |
| FR-1001 | M | A7 | – | When the server is unreachable: offline banner, read-only view from the cache, all change  |
| FR-1002 | M | A7 | – | Reconnection polling with exponential backoff (default 10 s → 30 s max, configurable) and  |
| FR-1003 | M | A7 | – | When the server is back, controls are re-enabled and data is refreshed with a sync. |
| FR-1100 | M | E12 | – | Every change made through the dashboard (action type, child, result, time) is logged and s |
| FR-1101 | M | E12 | – | Entries older than 30 days are removed automatically. |
| NFR-001 | M | B5 | – | Sync target: a change is visible within 5 s on a local network. The target is configurable |
| NFR-002 | M | B5 | – | Reliability: sync failures are retried with back-off (TR-304) and never leave the UI froze |
| NFR-003 | M | A7 | – | Performance: the browser stays responsive when the server is down (no growing request queu |
| NFR-004 | M | A4, D1 | – | Usability: all texts are available in Dutch and English; errors are clear and say what to  |
| SEC-001 | M | A3 | – | The dashboard listens on localhost by default (127.0.0.1) and has no login. Remote access  |
| SEC-002 | M | A6 | – | The server connection uses HTTPS when the server is not on the local network. Plain HTTP i |
| SEC-003 | M | B1, E1 | – | The device auth token is stored only on the local disk (database and session file), never  |
| TR-100 | M | B2 | – | All server calls follow docs/ServerAPI.md. The server code wins over the document. |
| TR-101 | M | B2 | – | Wire action types are SCREAMING_SNAKE; ids inside a family are 6 characters [0-9a-zA-Z]; e |
| TR-102 | M | B2 | – | Password integrity: HMAC-SHA256 with key = second hash, message = uint64BE(seq) ‖ len+devi |
| TR-103 | M | B3 | – | ClientDataStatus contains all versions and per-category data (D10). |
| TR-104 | M | A6 | – | The dashboard sends clientLevel 7 and only uses features available at that level. |
| TR-200 | M | B1 | – | SQLite is the cache. One file in the data folder (data/ next to the app on Windows, /data  |
| TR-201 | M | B1 | – | Database access is thread-safe; writes that change several tables use one transaction. syn |
| TR-202 | M | B1 | – | No parent passwords are stored. Only the device auth token (and own ids) are stored locall |
| TR-300 | M | A3 | – | Python 3.10+; requirements.txt with loose version ranges. Starts with py -3 app.py on Wind |
| TR-301 | M | A3 | – | All settings (port, data directory, log level, timings) come from a config file/environmen |
| TR-303 | M | A6, A7 | – | Timeouts: all outgoing server requests and all browser fetch calls have a timeout (AbortCo |
| TR-305 | M | A3 | – | Default port 8100 (configurable) and default listen address 127.0.0.1; the HA add-on sets  |
| TR-306 | M | A3 | – | SECRET_KEY is generated randomly on first start and stored next to the database; an enviro |
| TR-307 | M | A4 | – | All API routes return one error envelope {status:"error", code, message, requestId} with t |
| TR-308 | M | B7 | – | Layers: routes (thin) → services → repository (only layer with SQL); one server-client mod |
| TR-309 | M | B5 | – | One sync worker thread with a queue; a user change is push then immediate pull, the reques |
| TR-310 | M | B1 | – | A cache reset (schema change) drops the cache and fully re-syncs, but keeps the link, sett |
| TR-311 | M | A7, D1 | – | Frontend: Jinja + vanilla JS in ES modules, no build step; CSS variables, no inline styles |
| TR-312 | M | C1, C2, G1 | – | The legacy UI layer (frontend.py, web_server.py, api_client.py, check_server.py) and the o |
| TR-400 | M | A3 | – | Configurable log level (debug/info/warn/error). |
| TR-401 | M | A3 | – | Log rotation with limited size and file count. |
| TR-500 | M | A2 | dashboard/tests/test_isolation.py | pytest unit tests, isolated (own temporary database and log folder per test), parallel wit |
| TR-501 | M | A5, B2 | dashboard/tests/kept/test_action_builder.py (partial; completed in B2) | Contract tests: every action the dashboard can produce is validated against the schemas ge |
| TR-502 | M | A7, D1, E-steps | – | Browser/UI tests (Playwright) for the main screens: overview, child detail, rule dialog, h |
| TR-504 | M | G2 | – | Documentation stays in sync: this document, docs/ServerAPI.md, and design notes are update |
| TR-510 | M | A0 | – | One tool for style and lint: ruff (lint and format), configured in pyproject.toml. ruff ch |
| TR-511 | M | A0 | – | Line endings: the repository uses LF (.gitattributes and .editorconfig); shell scripts and |
| TR-512 | M | A3, B7 | – | Time and time zones: the domain layer only uses time-zone-aware times and receives the cur |
| TR-513 | M | A3, B7 | – | Secrets in code: tokens, hashes and typed passwords pass through one Secret type / masking |
| TR-514 | M | A6, B7 | – | Timeouts on all I/O: every HTTP call has an explicit timeout; a test fails on any call wit |
| UI-001 | M | E1, E11, E2 | – | Screens: children overview, child detail, settings, test section. |
| UI-002 | M | D1 | – | Navigation: fixed sidebar on desktop, hamburger menu on small screens. The menu opens/clos |
| UI-003 | M | D1 | – | Layout works on desktop browsers, phones and tablets. |
| UI-004 | M | D1 | – | Dark theme (and light). |
| UI-005 | M | D1 | – | Languages: Dutch and English, selectable in settings. Default: the browser language when i |
| UI-006 | M | D1 | – | Destructive actions (delete rule, category, remove apps) require a confirmation dialog. |
| UI-007 | M | E4 | – | Every action shows its state: pending, confirmed, failed. |
