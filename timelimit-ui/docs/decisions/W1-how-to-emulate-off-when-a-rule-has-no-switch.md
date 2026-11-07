# W1 · How to emulate "off" when a rule has no switch

- Status: accepted (answered by the owner, 2026-11-06/07)
- Plan steps: B2, E3a

## Context
How to emulate "off" when a rule has no switch?

## Choice
Remove today's bit from the rule's days mask (`UPDATE_TIMELIMIT_RULE`) and put it back later; the rest of the rule stays.

## Consequences
See the listed plan steps in `docs/plan/implementation-plan.md` and the matching requirements in `docs/requirements/requirements.md`.
