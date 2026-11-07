# Old tests: what happens to each file

Status: proposal agreed 2026-11-07 (legacy suite runs apart until the cut-over, G1). The classification comes from the module names, imports and the first lines of each file; it is **checked file by file in the step named in the last column**, and the table is updated then.

Counts are the number of `test_` functions found by text search in `rootfs/usr/bin/dashboardV2/tests/`; they differ slightly from pytest's own count (baseline 2026-11-04: 1325 collected, 29 failed).

| Class | Meaning |
|-------|---------|
| **K** keep | The module is reused; its tests move to the new test tree and stay green. |
| **R** rewrite | The idea stays, the module is replaced; the tests are rewritten for the new module (the old ones are read for edge cases). |
| **S** specification | Old internals disappear; the scenarios are read as a checklist for the new tests, the file is deleted with the code. |
| **X** drop | Tests of code or pages that disappear, or tests that only read source text. Deleted with the code (C2/G1). |


## K · keep

Moved in step A2 to `rootfs/usr/bin/dashboard/tests/kept/` (the modules they test stay in their old place until B2/B4; `kept/conftest.py` sets the environment). The legacy conftest marks everything left in `dashboardV2/tests/` with `legacy`.

| File | Tests | Step / note |
|---|---|---|
| `test_action_builder.py` | 21 | B2 |
| `test_crypto_utils.py` | 17 | B2 |
| `test_action_pusher.py` | 14 | B4 (imports `database`; adapt to the repository) |
| `test_key_manager.py` | 9 | B2 |

## R · rewrite

| File | Tests | Step | What to carry over |
|---|---|---|---|
| `test_auth_client.py` | 73 | A6 | HTTP error handling and timeouts |
| `test_analyze_logs.py` | 49 | C2 | script `scripts/analyze_logs`: keep or drop is decided in C2 |
| `test_request_logging.py` | 44 | A3, A4 | request id and request logging |
| `test_config.py` | 41 | A3 | precedence, paths, HA detection |
| `test_log_rotation.py` | 37 | A3 | rotation |
| `test_sanitization.py` | 33 | A3 | masking of secrets → `Secret`/`mask()` |
| `test_logging.py` | 32 | A3 | logging set-up |
| `test_audit_log.py` | 31 | E12 | audit log (reads source text for 28 checks; rewrite as behaviour tests) |
| `test_log_level.py` | 26 | A3 | log level |
| `test_auth_client_logging.py` | 23 | A6 | what the client logs |
| `test_scheduler_logging.py` | 22 | B6 | timers/poller logs |
| `test_persistence_logging.py` | 21 | B1 | what the link storage logs |
| `test_family_logging.py` | 18 | E1 | linking logs |
| `test_database_logging.py` | 15 | B1 | what the repository logs |
| `test_port_check.py` | 7 | A3 | port-in-use check at start |

## S · specification only

| File | Tests | Read in step |
|---|---|---|
| `test_database.py` | 158 | B1 |
| `test_dashboard_api.py` | 123 | E-steps (routes) |
| `test_persistence.py` | 58 | B1, E1 |
| `test_sync_manager.py` | 45 | B3–B5 |
| `test_scheduler.py` | 24 | B6 |
| `test_create_family_integration.py` | 23 | E1, E10 |
| `test_timechecker.py` | 21 | A7 (server-down handling) |
| `test_category_apps_api.py` | 15 | E7 |
| `test_time_limit_rules_e2e.py` | 5 | E3 |

## X · drop

| File | Tests | Reason |
|---|---|---|
| `test_visual_responsive.py` | 97 | reads source text (94 checks); replaced by Playwright (TR-502) |
| `test_landing.py` | 47 | old landing page |
| `test_login_as_parent.py` | 41 | old form page (replaced by settings screen) |
| `test_recover_parent_password.py` | 34 | old form page |
| `test_create_family.py` | 31 | old form page |
| `test_sign_out.py` | 20 | old UI |
| `test_hamburger_menu_interaction.py` | 20 | reads source text; replaced by Playwright |
| `test_set_parent_password.py` | 12 | old form page |
| `test_startup.py` | 11 | old app start |
| `test_database_isolation.py` | 11 | replaced by the per-test fixture (A2) |
| `test_missing_sign_in_links.py` | 7 | old UI text checks |
| `test_session_restoration_logging.py` | 7 | old session handling |
| `test_sign_out_sidebar.py` | 5 | old UI |
| `test_javascript_syntax.py` | 2 | old single JS file |

## Totals

K 61 · R 472 · S 472 · X 345 · together 1350 tests in this folder. Outside this folder: `test/` (check_server, web_server, script: 54 tests, all tied to the legacy UI layer, class X, removed in C2).

## Rules

- A class changes only here, with a short reason.
- A file is deleted in the same step that deletes the code it tests (C2 or G1), never earlier.
- Before deleting a class S or R file, its scenarios are checked off against the new tests (a short list in the step's pull request/commit message).
