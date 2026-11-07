# Q13 · Are passwords and the second hash logged

- Status: accepted (answered by the owner, 2026-11-06/07)
- Plan steps: E10, A3

## Context
Are passwords and the second hash logged?

## Choice
Secrets are masked at info level and higher; only at debug level everything is unmasked, also in the debug export. Replaces the earlier "logs not masked"; design §5 and TR-402 updated.

## Consequences
See the listed plan steps in `docs/plan/implementation-plan.md` and the matching requirements in `docs/requirements/requirements.md`.
