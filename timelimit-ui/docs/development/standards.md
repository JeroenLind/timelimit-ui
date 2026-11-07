# Development standards

Requirements TR-510..TR-519, design section 9.1, plan step A0. These rules apply to the new package
`rootfs/usr/bin/dashboard/` and to `tools/`. The legacy code (`dashboardV2/` and the old UI layer) is not
linted or reformatted; it is deleted at the cut-over.

## One command

```
py -3 -m pip install -r requirements-dev.txt
py -3 tools/check.py          # ruff check, ruff format --check, mypy, pytest (definition of done)
py -3 tools/check.py --fast   # what the pre-commit hook runs: no browser (ui) or legacy tests
py -3 -m pre_commit install   # once, from the repository root
```

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

## Decisions (TR-519)
`docs/decisions/`: one record per decision, written from `TEMPLATE.md`; IDs follow the plan.
