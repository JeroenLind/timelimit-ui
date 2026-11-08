# Progress and resume notes

Single place that says where the build stands, so work can continue after any interruption (usage
limits, a lost session). Update it in the same commit as the work. Plan: `implementation-plan.md`.

## Resume protocol (first thing in every session)
1. `git status` and `git log --oneline -10`; `git fetch` and compare with `origin/claudeEnhancedVersion`.
2. Read the **Current step** block below and the status table.
3. Files on disk that are not committed belong to the current step: **read and verify them, never
   assume they are right and never redo them blindly**; run `py -3 tools/check.py`.
4. Continue at the first unchecked item of the current step.

## Working rules against interruption
- Commit and push after every finished sub-result (a green test, a finished file), not only at the end
  of a step. Checkpoint commits start with `wip(<step>):` and may skip the hook (`--no-verify`) when the
  suite is not green yet; the **closing commit of a step** starts with `<step>:` and passes the hook.
- Never leave a step half-written in the working tree at the end of a work block; if a stop is near,
  commit a checkpoint and update the block below.
- Long runs (for example the 3-minute old suite) write their output to a file so the result survives.
- Update this file and the project docs (`project_write`) at the end of every step.

## Status
| Step | Status | Commit |
|------|--------|--------|
| A0 Development standards | done | 26c47d3 |
| A1 Baseline and working method | done | 1aa7330, 3b3463e |
| A2 Isolated tests, legacy suite apart | done | bef8a74 (wip), closing commit below |
| A3 Configuration, data folder, secret key, logging, clock, `Secret` | done (Windows check passed 2026-11-08: /api/health ok) | closing commit below |
| A4 One error envelope | done | closing commit below |
| A5 Fake TimeLimit server | done | closing commit `A5: ...` |
| A6 Server client | done | closing commit `A6: ...` |
| A7 Frontend skeleton, server-down handling | done | closing commit `A7: ...` |
| B1 .. G2 | not started | |

## Current step
**B1** Repository and cache schema (SQLite, versions, per-server profile). Read the B1 section of the plan first.
- [ ] B1 implementation, closing commit `B1: ...`, progress, project docs, memory
- [ ] Windows check of A7 (open the page, stop/start the server): asked of the user, result pending.

## Notes
- A7 result: server-side `services/connection.py` (probe with the health timeout, never raises; `require_online()` gives READ_ONLY_OFFLINE for the later change routes), `routes/server.py` (`GET /api/server/status` -> up/down/not_configured + code), `routes/pages.py` (overview page, placeholder list from `services/overview.py` until the cache exists in B1). Frontend: `templates/base.html`, `overview.html`, `static/js/{api,state,i18n,connection,overview,main}.js`, `static/css/{theme,layout}.css`, `static/i18n/{en,nl}.json`. Behaviour: check on load, poll every `health_interval` (new setting, default 5 s) while up, back-off `backoff_initial` -> `backoff_max` while down, retry button, controls with `data-change-control` disabled while down, `body[data-server]`, banner `data-code`. `server_url` setting (env `DASHBOARD_SERVER_URL` or `config.json`) is temporary until the settings screen (design 8.1). 10 browser tests (`-m ui`, Playwright) + 7 backend tests; total 305 green.
- A6 result: `client/server.py`: one `_request` function (always a timeout, gzip body, one retry without compression on 411, error mapping: timeout -> SERVER_TIMEOUT, no connection -> SERVER_UNREACHABLE, 401 SESSION_INVALID, 403 INVALID_PASSWORD, 404/410 NOT_FOUND, 409 CONFLICT, 429/5xx SERVER_UNREACHABLE, other 4xx INTERNAL_ERROR; `ServerHttpError` keeps the status so callers can tell a wrong mail code 403 from an exhausted one 410). `clientLevel` 7 is added by the client on every call that accepts it (the server schemas reject it elsewhere). Plain http only for localhost, loopback, private/link-local addresses, `.local`/`.lan` names and dot-less host names; no DNS lookups. Tests: `tests/test_client.py` (41), including a scan that only `client/server.py` imports an HTTP library.
- A5 result: `tests/fakeserver/` (schemas.py, state.py, integrity.py, actions.py, app.py, `FakeTimeLimitServer`), 30 conformance tests (`tests/test_fakeserver.py`, 2 s). Findings from the server source, now pinned by tests: `ClientDataStatus` requires `apps` (object), `categories`, `devices`, `users`, otherwise 400; extra time and temporary-block actions fail silently without the family's premium version; a failed action consumes its sequence number and a reused number is ignored without a full-sync request; more than 50 actions per push = 400; pull answers contain `tasks` only for `clientLevel` >= 3; the rule `e` (expiresAt) is sent by one server variant only (`FakeTimeLimitServer(rule_expiry=True)`). Not simulated (listed loudly via `fake.unsimulated`): child actions, key requests, pings, `devices2`. Never run `ruff format .` (it reformats the legacy files); format named paths.
- A4 result: `domain/errors.py` (codes + `DashboardError`), `routes/errors.py` (status table, envelope, request id, handlers); a test fails when a route in `routes/` builds an error response by hand. Non-API paths keep Flask's normal pages. Unknown `/api/` paths and wrong methods/bodies answer with the envelope (405/413/415 map to `INVALID_INPUT` 400).
- A3 result: 190 tests green (serial and parallel); decisions taken inside the design are listed in the A3 commit and in `docs/architecture/design.md` §8 (data folder next to `app.py`, `DASHBOARD_<NAME>` variables, `config.json`, stdlib logging).
- Werkzeug exits the process itself when the port is taken; `build_server` probes first so `main` can report it.
- A2 result: new suite 106 tests green serially and with `-n auto`; the 77 kept tests live in `dashboard/tests/kept`; the legacy suite (1248 tests) runs apart with `py -3 tools/baseline.py` or `pytest rootfs/usr/bin/dashboardV2/tests -m legacy`.
- `test_action_builder.py` used to skip silently when the protocol reference was missing; it now fails.
- Windows baseline recorded 2026-11-08: 1244 passed, 4 failed (same 4 as Linux).
- Tag `pre-rebuild` is local only (pushing tags fails from the cloud).
