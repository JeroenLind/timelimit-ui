# Development standards

Requirements TR-510..TR-519, design section 9.1, plan step A0. These rules apply to the new package
`rootfs/usr/bin/dashboard/` and to `tools/`. The legacy code (`dashboardV2/` and the old UI layer) was deleted at
the cut-over (plan step G1, 2026-11-19); the git history keeps it.

## One command

```
py -3 -m pip install -r requirements-dev.txt
py -3 tools/check.py          # ruff check, ruff format --check, mypy, pytest (definition of done)
py -3 tools/check.py --fast   # what the pre-commit hook runs: no browser (ui) or legacy tests
py -3 -m pre_commit install   # once, from the repository root
```

## Keeping the suite fast

The full check took 10 minutes before 2026-11-18 and takes about 3 on two cores. What made the difference:
- **Measure first:** `pytest --durations=30 --durations-min=0.5`. Look at *setup* and *teardown* as well as *call*: 3 s of every test was spent closing the socket listener (the websocket close handshake waited for the server), found only because teardown showed up in the list.
- **One Chromium per test process** (`browser` fixture in `conftest.py`); every test still gets its own context, closed after the test.
- **Parallel** with `pytest-xdist` (`-n auto`, already used by `tools/check.py`).
- **While developing:** `pytest --lf` (last failed), `pytest -k name`, `tools/check.py --fast` (no browser tests). The full check is the definition of done, not the inner loop.
- **No fixed sleeps** in tests; wait for a condition (Playwright `expect`). A click that starts a navigation is followed by a wait for the next page.
- Optional: `pytest-testmon` runs only tests affected by the changed files; not part of the check because it needs a stored database.

## Style and types (TR-510, TR-515)
- `ruff` with its default rules and `ruff format`; configuration only in `pyproject.toml`.
- Type hints on public functions of `domain/`, `services/` and `client/`. `mypy` is strict on `domain/` and
  `client/`; other packages are added to the strict list when they are clean.

## Line endings (TR-511)
LF everywhere (`.gitattributes`, `.editorconfig`). Shell scripts and s6 services must never contain CRLF.

## Code rules (checked by the architecture test in step B7)
- **Time (TR-512):** the domain never calls `now()`; it receives a `Clock` that returns time-zone-aware times.
- **Secrets (TR-513):** tokens, hashes and typed passwords are wrapped in `Secret`; only an explicit
  `reveal()` shows the value, and only at debug level (decision Q13).
- **Timeouts (TR-514):** every HTTP call passes a timeout, and only the server client makes HTTP calls.

## Dependencies (TR-516)
`requirements.txt` has loose ranges. `py -3 tools/make_constraints.py` writes `constraints.txt` with pinned
versions; the HA image installs with `-c constraints.txt`. Regenerate after changing `requirements.txt`.

## Commits (TR-518)
Short, descriptive message, one commit per plan step, ending with the agreed trailers
(`Co-Authored-By: ...` and `Claude-Session: ...`).
In between, checkpoint commits `wip(<step>): ...` are allowed (and may use `--no-verify`) so no work is lost when a
session is interrupted; the closing commit of a step passes the hook. See `docs/plan/progress.md` for the resume protocol.

## Decisions (TR-519)
`docs/decisions/`: one record per decision, written from `TEMPLATE.md`; IDs follow the plan.
