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
| A3 Configuration, data folder, secret key, logging, clock, `Secret` | next | |
| A4 .. G2 | not started | |

## Current step
**A3** Configuration, data folder, secret key, logging, `Clock`, `Secret`. Decisions taken while implementing
(inside the design, listed so they can be challenged): data folder default = `data/` next to `app.py` (the
`dashboard/` folder), override with `DASHBOARD_DATA_DIR` (the add-on sets `/data` in F2); env names are
`DASHBOARD_<SETTING>`; optional `config.json` in the data folder; stdlib `logging` with a JSON formatter (no
new dependency); `Secret` and `Clock`/`FakeClock` live in `domain/`, `SystemClock` in `services/`; entry
points `py -3 app.py` (inside `dashboard/`) and `py -3 -m dashboard`; one route `GET /api/health`.
- [ ] domain: `Secret`, `mask()`, `Clock`, `FakeClock` (+ tests)
- [ ] `services/clock.py` `SystemClock`
- [ ] `config.py`: settings, precedence env > file > default, validation (+ precedence table test)
- [ ] secret key created once, kept, env override (+ test)
- [ ] `logs.py`: JSON lines, level, rotation, masking (+ tests)
- [ ] factory, `routes/health.py`, `main.py`, `app.py`, `__main__.py`; bind test (127.0.0.1, other interface refused)
- [ ] `.gitignore` `data/`; docs (design §8 note, standards), progress, project docs, memory; closing commit `A3: ...`
- [ ] M (you): `py -3 app.py` on Windows creates `data/` and starts on 8100

## Notes
- A2 result: new suite 106 tests green serially and with `-n auto`; the 77 kept tests live in `dashboard/tests/kept`; the legacy suite (1248 tests) runs apart with `py -3 tools/baseline.py` or `pytest rootfs/usr/bin/dashboardV2/tests -m legacy`.
- `test_action_builder.py` used to skip silently when the protocol reference was missing; it now fails.
- Windows failure list of the old suite is still to be recorded (`py -3 tools/baseline.py --record`).
- Tag `pre-rebuild` is local only (pushing tags fails from the cloud).
