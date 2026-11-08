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
| A3 Configuration, data folder, secret key, logging, clock, `Secret` | done except the Windows check (M) | closing commit below |
| A4 One error envelope | done | closing commit below |
| A5 Fake TimeLimit server | next | |
| A6 .. G2 | not started | |

## Current step
**A5** (not started). **Still open from A3 (yours):** the Windows check (`py -3 app.py` in `rootfs/usr/bin/dashboard`, health URL on 8100) and `py -3 tools/baseline.py --record`. Read plan step A5 and `docs/protocol/` first; write the checklist here when starting.

## Notes
- A4 result: `domain/errors.py` (codes + `DashboardError`), `routes/errors.py` (status table, envelope, request id, handlers); a test fails when a route in `routes/` builds an error response by hand. Non-API paths keep Flask's normal pages. Unknown `/api/` paths and wrong methods/bodies answer with the envelope (405/413/415 map to `INVALID_INPUT` 400).
- A3 result: 190 tests green (serial and parallel); decisions taken inside the design are listed in the A3 commit and in `docs/architecture/design.md` §8 (data folder next to `app.py`, `DASHBOARD_<NAME>` variables, `config.json`, stdlib logging).
- Werkzeug exits the process itself when the port is taken; `build_server` probes first so `main` can report it.
- A2 result: new suite 106 tests green serially and with `-n auto`; the 77 kept tests live in `dashboard/tests/kept`; the legacy suite (1248 tests) runs apart with `py -3 tools/baseline.py` or `pytest rootfs/usr/bin/dashboardV2/tests -m legacy`.
- `test_action_builder.py` used to skip silently when the protocol reference was missing; it now fails.
- Windows failure list of the old suite is still to be recorded (`py -3 tools/baseline.py --record`).
- Tag `pre-rebuild` is local only (pushing tags fails from the cloud).
