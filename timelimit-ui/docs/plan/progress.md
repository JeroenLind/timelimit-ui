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
| A5 Fake TimeLimit server | in progress | wip commits |
| A6 .. G2 | not started | |

## Current step
**A5** Fake TimeLimit server (test double), in `rootfs/usr/bin/dashboard/tests/fakeserver/`. Source of truth: the
server checkout `/home/claude/ref/MichaelSp_timelimit-server` (read-only, commit fe90617, apiLevel 9) and `docs/ServerAPI.md`.
Decisions inside the plan: the strict request schemas are extracted from the server's `src/api/validator.ts`
(`tools/extract_server_schemas.py`, output `fakeserver/server_schemas.json`); the semantic checks of actions
(6-character ids, bitmask length, ranges) are re-implemented from `src/action/*.ts`; only the actions the dashboard
sends are simulated, any other schema-valid action is recorded in `fake.unsimulated` and fails silently (a test
fails on a non-empty list) so gaps are loud; dev dependencies jsonschema, python-socketio, simple-websocket,
websocket-client.
- [x] schema extractor + `server_schemas.json` (22 validators, 106 definitions)
- [ ] `fakeserver/schemas.py` (validators, response schema built from the definitions)
- [ ] state + REST: /time, /auth/*, /parent/*, /child/add-device (mail login, create-family, sign-in-into-family, add-device token, remove-device, recover-parent-password)
- [ ] sync: pull-status (versions, clientLevel gates), push-actions (limit 50, silent failures, sequence rules, integrity device/password/childDevice, broadcast)
- [ ] simulated actions (see list in `fakeserver/actions.py`)
- [ ] Socket.IO `devicelogin` / `should sync`; fault injection (down, slow, reject next action)
- [ ] conformance suite incl. the two HMAC vectors; startup < 1 s on an ephemeral port
- [ ] closing commit `A5: ...`, progress, project docs, memory
- [ ] M (optional, yours): run the conformance scenarios against your local test server

**Still open from A3 (yours):** open `http://127.0.0.1:8100/api/health` (not `/`; `/` correctly answers 404 for now) and run `py -3 tools/baseline.py --record`.

## Notes
- A4 result: `domain/errors.py` (codes + `DashboardError`), `routes/errors.py` (status table, envelope, request id, handlers); a test fails when a route in `routes/` builds an error response by hand. Non-API paths keep Flask's normal pages. Unknown `/api/` paths and wrong methods/bodies answer with the envelope (405/413/415 map to `INVALID_INPUT` 400).
- A3 result: 190 tests green (serial and parallel); decisions taken inside the design are listed in the A3 commit and in `docs/architecture/design.md` §8 (data folder next to `app.py`, `DASHBOARD_<NAME>` variables, `config.json`, stdlib logging).
- Werkzeug exits the process itself when the port is taken; `build_server` probes first so `main` can report it.
- A2 result: new suite 106 tests green serially and with `-n auto`; the 77 kept tests live in `dashboard/tests/kept`; the legacy suite (1248 tests) runs apart with `py -3 tools/baseline.py` or `pytest rootfs/usr/bin/dashboardV2/tests -m legacy`.
- `test_action_builder.py` used to skip silently when the protocol reference was missing; it now fails.
- Windows baseline recorded 2026-11-08: 1244 passed, 4 failed (same 4 as Linux).
- Tag `pre-rebuild` is local only (pushing tags fails from the cloud).
