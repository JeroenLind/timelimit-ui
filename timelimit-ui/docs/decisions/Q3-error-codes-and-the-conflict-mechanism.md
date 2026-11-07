# Q3 · Error codes and the conflict mechanism

- Status: accepted (answered by the owner, 2026-11-06/07)
- Plan steps: A4, E4

## Context
Error codes and the conflict mechanism

## Choice
Accepted list (design §6, TR-307): `INVALID_INPUT` 400, `SESSION_INVALID` 401, `INVALID_PASSWORD` 403, `NOT_FOUND` 404, `NOT_LINKED` 409, `CONFLICT` 409, `READ_ONLY_OFFLINE` 503, `SERVER_UNREACHABLE` 502, `SERVER_TIMEOUT` 504, `ACTION_NOT_CONFIRMED` 502, `INTERNAL_ERROR` 500. `CONFLICT`: the browser sends the version it started editing with; a mismatch with the cache gives 409.

## Consequences
See the listed plan steps in `docs/plan/implementation-plan.md` and the matching requirements in `docs/requirements/requirements.md`.
