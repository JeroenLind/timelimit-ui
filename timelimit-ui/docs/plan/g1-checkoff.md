# G1 check-off: old test files against the new tests

Rule from `old-tests-disposition.md`: before an R or S file is deleted, its scenarios are checked off
against the new tests. Done 2026-11-19 by topic (the old files test internals that no longer exist; what
matters is that the behaviour they described is covered). The old suite (1201 tests) is deleted with the
code in the same commit; the git history keeps it (tag `pre-rebuild` is local only, use the commit before
the G1 commit).

## K · keep (moved in A2)
| Old file | Covered now by |
|---|---|
| `test_action_builder.py` | `test_domain_actions.py` (156 contract tests against the server schemas) |
| `test_crypto_utils.py` | `test_domain_integrity.py` (HMAC vectors, change-password scheme, container) |
| `test_key_manager.py` | `test_domain_integrity.py`, `test_link.py` (device keys and the DH container) |
| `test_action_pusher.py` | `test_push.py`, `test_worker.py` |

## R · rewritten
| Old file | Covered now by |
|---|---|
| `test_auth_client.py`, `test_auth_client_logging.py` | `test_client.py` |
| `test_request_logging.py` | `test_errors.py` (request ids), `test_logs.py` |
| `test_config.py`, `test_port_check.py` | `test_config.py`, `test_start.py` |
| `test_log_rotation.py`, `test_logging.py`, `test_log_level.py`, `test_sanitization.py` | `test_logs.py`, `test_secret_clock.py`, `test_architecture.py` (no secrets in log calls) |
| `test_audit_log.py` | `test_audit.py`, `test_ui_audit.py` |
| `test_scheduler_logging.py` | `test_live.py`, `test_worker.py` |
| `test_persistence_logging.py`, `test_database_logging.py` | `test_repository.py` (no secret in any file of the data folder) |
| `test_family_logging.py` | `test_link.py`, `test_parents.py` |
| `test_analyze_logs.py` | **dropped on purpose:** the script `scripts/analyze_logs` goes with `dashboardV2`; the debug export (E1) and the audit log (E12) replace it |

## S · specification only
| Old file | Covered now by |
|---|---|
| `test_database.py`, `test_persistence.py` | `test_repository.py` |
| `test_dashboard_api.py` | `test_children.py`, `test_rules.py`, `test_categories.py`, `test_blocked_times.py`, `test_apps.py`, `test_usage.py`, `test_extra_time.py`, `test_parents.py`, `test_link.py` and the `test_ui_*` files |
| `test_sync_manager.py` | `test_pull.py`, `test_push.py`, `test_worker.py` |
| `test_scheduler.py` | `test_live.py`, `test_rule_today.py` |
| `test_create_family_integration.py` | `test_link.py`, `test_testsection.py` |
| `test_timechecker.py` | `test_connection.py`, `test_ui_offline.py` |
| `test_category_apps_api.py` | `test_apps.py`, `test_ui_apps.py` |
| `test_time_limit_rules_e2e.py` | `test_rules.py`, `test_rule_today.py`, `test_ui_rules.py` |

## X · dropped
Unchanged from the disposition (old form pages, source-text checks, old app start).
