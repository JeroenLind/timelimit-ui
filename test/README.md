# TimeLimit UI Unit Tests

This directory contains unit tests for the TimeLimit UI application.

## Test Files

| File | Description |
|------|-------------|
| `test_check_server.py` | Comprehensive unit tests for the server connection checking functionality |
| `conftest.py` | Pytest fixtures for test setup |
| `pytest.ini` | Pytest configuration |

## Running the Tests

### Prerequisites

Ensure you have Python 3.9+ and pytest installed:

```bash
pip install pytest
```

### Run All Tests

```bash
cd c:/git/timelimit-ui
python -m pytest test/ -v
```

### Run Specific Test File

```bash
cd c:/git/timelimit-ui
python -m pytest test/test_check_server.py -v
```

### Run Specific Test Class

```bash
cd c:/git/timelimit-ui
python -m pytest test/test_check_server.py::TestServerCheckerSuccess -v
```

### Run Specific Test Function

```bash
cd c:/git/timelimit-ui
python -m pytest test/test_check_server.py::TestServerCheckerSuccess::test_successful_connection -v
```

### Run with Coverage

```bash
cd c:/git/timelimit-ui
pip install pytest-cov
python -m pytest test/test_check_server.py -v --cov=timelimit-ui/rootfs/usr/bin/check_server --cov-report=html
```

### Run with Verbose Output

```bash
cd c:/git/timelimit-ui
python -m pytest test/test_check_server.py -v -s
```

## Test Categories

The tests are organized into the following categories:

- **TestServerCheckResult** - Tests for the `ServerCheckResult` dataclass
- **TestServerCheckerSuccess** - Tests for successful server connections
- **TestServerCheckerTimeout** - Tests for network timeout scenarios
- **TestServerCheckerUnreachable** - Tests for unreachable server scenarios
- **TestServerCheckerInvalidResponse** - Tests for invalid server responses
- **TestServerCheckerServerError** - Tests for server error scenarios
- **TestServerCheckerRetryLogic** - Tests for retry logic and exponential backoff
- **TestServerCheckerConfiguration** - Tests for configuration options
- **TestCheckServerConnection** - Tests for the convenience function
- **TestUserMessages** - Tests for user message mapping
- **TestErrorCodeValidation** - Tests for error code validation
- **TestIntegration** - Integration tests for the complete check flow

## Test Output

Successful test run:
```
============================= 30 passed in 6.16s ==============================
```

## Debugging Tests

To debug a failing test, you can add the `-s` flag to see print statements:

```bash
python -m pytest test/test_check_server.py -v -s
```

Or use the `--pdb` flag to enter the debugger on failure:

```bash
python -m pytest test/test_check_server.py -v --pdb