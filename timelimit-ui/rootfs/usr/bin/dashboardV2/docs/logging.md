# DashboardV2 Logging

This document describes the logging infrastructure for the DashboardV2 Flask application, including the logging concept, log file locations, and how to use logs to analyze problems.

## Overview

DashboardV2 uses structured JSON logging to provide comprehensive visibility into application behavior. The logging system captures all HTTP requests, API calls, database operations, scheduler events, and authentication flows.

## Logging Concept

### Structured JSON Format

All log entries use structured JSON format for machine-parseability and easy analysis:

```json
{
  "timestamp": "2026-08-13T16:30:00.123456Z",
  "level": "INFO",
  "logger": "dashboardV2.app",
  "event": "Request completed",
  "request_id": "a1b2c3d4",
  "component": "app",
  "method": "POST",
  "path": "/api/auth/sign-in-by-mail-code",
  "status_code": 200,
  "duration_ms": 45,
  "response_size": 256
}
```

### Standard Fields

| Field | Description |
|-------|-------------|
| `timestamp` | ISO 8601 UTC timestamp with microsecond precision |
| `level` | Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `logger` | Logger name (module path) |
| `event` | Human-readable event description |
| `request_id` | UUID-based correlation ID for request tracing |
| `component` | Logical component name |

### Log Levels

| Level | Usage |
|-------|-------|
| `DEBUG` | Detailed diagnostics, request payloads, retry attempts |
| `INFO` | Operational events, successful operations, health checks |
| `WARNING` | Potential issues, retries, degraded performance |
| `ERROR` | Operation failures, API errors, database errors |
| `CRITICAL` | Application failures, scheduler failures |

### Request ID Correlation

Every HTTP request generates a unique 8-character request ID that is propagated through all components:

1. Generated at the start of each request
2. Stored in Flask's `g` object
3. Included in all log entries for that request
4. Propagated to the debug-server via `X-Request-ID` header

This enables end-to-end request tracing across the entire system.

## Log File Locations

### Development (Windows)

```
dashboardV2/
├── logs/
│   ├── dashboardV2-2026-08-13_16-30-00.log
│   ├── dashboardV2-2026-08-13_14-15-00.log
│   └── ...
└── dashboardV2.log
```

### Home Assistant Ingress

```
/data/logs/
├── dashboardV2-2026-08-13_16-30-00.log
└── ...
```

### Docker

```
/app/logs/
├── dashboardV2-2026-08-13_16-30-00.log
└── ...
```

## Log Rotation and Retention

### Size-Based Rotation

- Maximum file size: 10MB (configurable via `LOG_MAX_BYTES`)
- Backup count: 5 files (configurable via `LOG_BACKUP_COUNT`)
- Uses Python's `RotatingFileHandler`

### Startup-Based Rotation

- New timestamped file created on each application startup
- Format: `dashboardV2-YYYY-MM-DD_HH-MM-SS.log`
- Retention: 10 files (configurable via `MAX_LOG_FILES`)

## Using Logs to Analyze Problems

### Step 1: Identify the Time Window

Determine when the issue occurred. Check:
- User reports
- Error notifications
- Dashboard behavior

### Step 2: Locate Relevant Log Files

Find the log file(s) covering the time window:

```bash
# List log files with timestamps
ls -la logs/

# Find logs for a specific date range
ls logs/dashboardV2-2026-08-13_*.log
```

### Step 3: Use the Log Analysis Script

The `scripts/analyze_logs.py` script provides quick analysis:

```bash
# Basic analysis
python scripts/analyze_logs.py -f logs/dashboardV2.log

# Analyze all logs in a directory
python scripts/analyze_logs.py -d logs/

# Filter by log level
python scripts/analyze_logs.py -f logs/dashboardV2.log --level ERROR

# Filter by request ID for tracing
python scripts/analyze_logs.py -f logs/dashboardV2.log -r a1b2c3d4

# Output as JSON
python scripts/analyze_logs.py -f logs/dashboardV2.log -o json
```

### Step 4: Analyze by Category

The analysis script categorizes logs into:

1. **Errors** - All ERROR and CRITICAL level entries
2. **Security Events** - Authentication, token, password events
3. **Communication Issues** - Timeouts, connection errors
4. **Warnings** - Warning-level entries
5. **Info Events** - Operational events

### Step 5: Trace a Specific Request

Use the request ID to trace a request through all components:

```bash
# Find all entries for a specific request
grep '"request_id": "a1b2c3d4"' logs/dashboardV2.log

# Or use the analysis script
python scripts/analyze_logs.py -f logs/dashboardV2.log -r a1b2c3d4
```

### Step 6: Identify Root Cause

Look for patterns in the logs:

1. **API Errors** - Check `error_code` field for `timeout`, `unreachable`, `invalid_response`
2. **Authentication Failures** - Look for WARNING/ERROR entries with `component=auth_client`
3. **Database Issues** - Check for ERROR entries with `component=database`
4. **Scheduler Failures** - Look for ERROR entries with `component=scheduler`
5. **Server Connectivity** - Check for timeout or connection refused errors

## Common Problem Patterns

### API Request Failures

```bash
# Find all API errors
grep '"event": "API call failed"' logs/dashboardV2.log

# Find timeout errors
grep '"error_code": "timeout"' logs/dashboardV2.log

# Find connection errors
grep '"error_code": "unreachable"' logs/dashboardV2.log
```

### Authentication Issues

```bash
# Find all auth-related events
grep -E '"component": "auth_client"' logs/dashboardV2.log

# Find failed sign-in attempts
grep '"event": "Sign-in failed"' logs/dashboardV2.log
```

### Server Check Failures

```bash
# Find scheduler errors
grep '"component": "scheduler"' logs/dashboardV2.log | grep ERROR

# Find server check failures
grep '"event": "Server check completed"' logs/dashboardV2.log | grep '"success": false'
```

### Performance Issues

```bash
# Find slow requests (duration > 1000ms)
grep '"duration_ms":' logs/dashboardV2.log | awk -F: '$NF > 1000 {print}'
```

## Log File Analysis Examples

### Example 1: Authentication Failure

```json
{
  "timestamp": "2026-08-13T16:30:00.123456Z",
  "level": "WARNING",
  "logger": "dashboardV2.auth_client",
  "event": "Sign-in failed",
  "request_id": "a1b2c3d4",
  "component": "auth_client",
  "error_code": "invalid_response",
  "error_message": "Invalid credentials",
  "server_url": "https://api.timelimit.io"
}
```

**Analysis**: The sign-in failed due to invalid credentials. Check if the user entered the correct email and verification code.

### Example 2: Server Timeout

```json
{
  "timestamp": "2026-08-13T16:30:00.123456Z",
  "level": "WARNING",
  "logger": "dashboardV2.auth_client",
  "event": "Request timeout",
  "request_id": "a1b2c3d4",
  "component": "auth_client",
  "error_code": "timeout",
  "error_message": "Request timed out",
  "technical_detail": "Connection timeout after 10 seconds",
  "server_url": "https://api.timelimit.io"
}
```

**Analysis**: The debug-server is not responding within the timeout period. Check:
1. Server connectivity
2. Server load
3. Network issues

### Example 3: Database Error

```json
{
  "timestamp": "2026-08-13T16:30:00.123456Z",
  "level": "ERROR",
  "logger": "dashboardV2.database",
  "event": "Database operation failed",
  "request_id": "a1b2c3d4",
  "component": "database",
  "error": "UNIQUE constraint failed",
  "error_code": "database_error",
  "table": "auth_tokens",
  "operation": "INSERT"
}
```

**Analysis**: A database constraint violation occurred. This could indicate:
1. Duplicate token insertion
2. Race condition in token generation
3. Database corruption

## Audit Log Events

The audit log provides detailed tracking of sensitive operations for security analysis, compliance audits, and forensic investigations. Audit logs are written to a separate file (`logs/audit.log`) and preserve complete request payloads and headers without sanitization.

### Add User to Family Events

The "Add User to Family" feature logs two types of events: request and response.

#### log_add_user_request()

Logs when a parent requests to add a new user (child) to their family.

**Function Signature**:
```python
def log_add_user_request(
    device_auth_token: str,
    parent_user_id: str,
    user_name: str,
    device_name: Optional[str] = None,
    device_model: Optional[str] = None,
    request_id: Optional[str] = None,
    server_url: Optional[str] = None,
    audit_log_path: Optional[str] = None
) -> None:
```

**Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `device_auth_token` | str | The parent's device authentication token |
| `parent_user_id` | str | The parent user's unique identifier |
| `user_name` | str | The child's display name |
| `device_name` | Optional[str] | The child's device name |
| `device_model` | Optional[str] | The child's device model |
| `request_id` | Optional[str] | UUID-based correlation ID for request tracing |
| `server_url` | Optional[str] | The server URL being contacted |
| `audit_log_path` | Optional[str] | Path to the audit log file |

**Log Format Example**:
```json
{
  "timestamp": "2026-08-13T16:30:00.123456Z",
  "timestamp_unix_ms": 1755114600123,
  "event": "add_user_request",
  "device_auth_token": "parent_device_token_abc123",
  "parent_user_id": "user_456",
  "user_name": "Child User",
  "device_name": "iPhone 15",
  "device_model": "iPhone15,2",
  "request_id": "a1b2c3d4",
  "server_url": "https://api.timelimit.io"
}
```

#### log_add_user_response()

Logs the server response after an add user request, including success status and any error details.

**Function Signature**:
```python
def log_add_user_response(
    device_auth_token: str,
    parent_user_id: str,
    user_id: Optional[str],
    child_device_auth_token: Optional[str],
    own_device_id: Optional[str],
    request_id: Optional[str] = None,
    success: bool = True,
    status_code: Optional[int] = None,
    response_data: Optional[Dict[str, Any]] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    audit_log_path: Optional[str] = None
) -> None:
```

**Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `device_auth_token` | str | The parent's device authentication token |
| `parent_user_id` | str | The parent user's unique identifier |
| `user_id` | Optional[str] | The new child user's ID (if successful) |
| `child_device_auth_token` | Optional[str] | The new child device's auth token (if successful) |
| `own_device_id` | Optional[str] | The new child device's ID (if successful) |
| `request_id` | Optional[str] | UUID-based correlation ID for request tracing |
| `success` | bool | Whether the operation succeeded |
| `status_code` | Optional[int] | HTTP status code of the response |
| `response_data` | Optional[Dict[str, Any]] | The complete response data from the server |
| `error_code` | Optional[str] | Error code if the request failed |
| `error_message` | Optional[str] | Error message if the request failed |
| `audit_log_path` | Optional[str] | Path to the audit log file |

**Log Format Example (Success)**:
```json
{
  "timestamp": "2026-08-13T16:30:00.123456Z",
  "timestamp_unix_ms": 1755114600123,
  "event": "add_user_response",
  "device_auth_token": "parent_device_token_abc123",
  "parent_user_id": "user_456",
  "user_id": "child_user_789",
  "child_device_auth_token": "child_device_token_xyz789",
  "own_device_id": "device_789",
  "request_id": "a1b2c3d4",
  "success": true,
  "status_code": 200,
  "response_data": {
    "ok": true,
    "message": "User added successfully",
    "userId": "child_user_789",
    "deviceAuthToken": "child_device_token_xyz789",
    "deviceId": "device_789"
  }
}
```

**Log Format Example (Failure)**:
```json
{
  "timestamp": "2026-08-13T16:30:00.123456Z",
  "timestamp_unix_ms": 1755114600123,
  "event": "add_user_response",
  "device_auth_token": "parent_device_token_abc123",
  "parent_user_id": "user_456",
  "user_id": null,
  "child_device_auth_token": null,
  "own_device_id": null,
  "request_id": "a1b2c3d4",
  "success": false,
  "status_code": 400,
  "error_code": "user_exists",
  "error_message": "User already exists in this family"
}
```

### Log Fields

The following fields are logged for Add User to Family events:

| Field | Description | Required |
|-------|-------------|----------|
| `timestamp` | ISO 8601 UTC timestamp with microsecond precision | Yes |
| `timestamp_unix_ms` | Unix timestamp in milliseconds | Yes |
| `event` | Event type (`add_user_request` or `add_user_response`) | Yes |
| `device_auth_token` | The parent's device authentication token | Yes |
| `parent_user_id` | The parent user's unique identifier | Yes |
| `user_name` | The child's display name (request only) | Request only |
| `device_name` | The child's device name (request only) | Optional |
| `device_model` | The child's device model (request only) | Optional |
| `user_id` | The new child user's ID (response only) | Response only |
| `child_device_auth_token` | The new child device's auth token (response only) | Response only |
| `own_device_id` | The new child device's ID (response only) | Response only |
| `request_id` | UUID-based correlation ID for request tracing | Optional |
| `server_url` | The server URL being contacted | Optional |
| `success` | Whether the operation succeeded | Response only |
| `status_code` | HTTP status code of the response | Response only |
| `response_data` | The complete response data from the server | Response only |
| `error_code` | Error code if the request failed | Failure only |
| `error_message` | Error message if the request failed | Failure only |

### Log Format

Audit log entries follow the same structured JSON format as regular logs, with the following characteristics:

1. **One JSON object per line** - Each log entry is a single line of JSON
2. **No sanitization** - Sensitive data (tokens, hashes) are logged as-is for forensic analysis
3. **Timestamp precision** - Microsecond precision timestamps for accurate event ordering
4. **Request correlation** - Request IDs enable tracing requests through the entire system

### Analyzing Audit Logs

Use the following commands to analyze audit logs:

```bash
# Find all add user requests
grep '"event": "add_user_request"' logs/audit.log

# Find all add user responses
grep '"event": "add_user_response"' logs/audit.log

# Trace a specific request
grep '"request_id": "a1b2c3d4"' logs/audit.log

# Find failed add user operations
grep '"event": "add_user_response"' logs/audit.log | grep '"success": false'

# Find add user operations for a specific parent
grep '"parent_user_id": "user_456"' logs/audit.log
```

## Environment Variables

Configure logging behavior via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `LOG_FILE_PATH` | `logs/dashboardV2.log` | Base path for log files |
| `LOG_MAX_BYTES` | `10485760` | Maximum file size (10MB) |
| `LOG_BACKUP_COUNT` | `5` | Number of backup files |
| `LOG_FORMAT` | `json` | Output format (json or console) |
| `MAX_LOG_FILES` | `10` | Maximum timestamped files |

## Security Considerations

### Sensitive Data Redaction

The logging system automatically redacts sensitive data:

- Passwords (`password`, `password_hash`, `second_hash`, `second_salt`)
- Tokens (`token`, `access_token`, `refresh_token`, `device_auth_token`, `mail_auth_token`, `mail_login_token`)
- Secret keys (`secret_key`, `jwt_secret`, `api_key`, `private_key`)
- Session data (`session`, `cookie`)

Redacted values appear as `***REDACTED***` in logs.

### Audit Log Security

Audit logs contain sensitive data and should be protected:

- Audit log files are created with restrictive permissions (0600)
- Access should be restricted to authorized administrators only
- Audit logs should not be committed to version control
- Handle audit logs in accordance with data protection regulations

## Troubleshooting

### Log File Not Created

1. Check if the `logs/` directory exists
2. Verify write permissions on the log directory
3. Check `LOG_FILE_PATH` configuration

### Logs Not Rotating

1. Verify `LOG_MAX_BYTES` is set correctly
2. Check file permissions on log files
3. Restart the application to trigger rotation

### Missing Log Entries

1. Check `LOG_LEVEL` is set appropriately
2. Verify structlog is configured correctly
3. Check for exceptions in the application

### Performance Impact

Logging adds minimal overhead (<1ms per request in production). If experiencing performance issues:

1. Check if `LOG_LEVEL` is set to DEBUG in production
2. Verify async logging is enabled (`MESSAGE_LOGGING_ASYNC=True`)
3. Check log file sizes and rotation settings

## Related Files

- `dashboardV2/utils/logging.py` - Structlog configuration
- `dashboardV2/utils/log_rotation.py` - Log file rotation
- `dashboardV2/utils/sanitization.py` - Sensitive data sanitization
- `dashboardV2/middleware/request_logging.py` - Request/response logging middleware
- `dashboardV2/scripts/analyze_logs.py` - Log analysis script
- `dashboardV2/utils/audit_log.py` - Audit logging functions
- `dashboardV2/utils/family_logging.py` - Family creation logging