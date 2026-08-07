# Logging Architecture and Analysis Procedures

This document describes the logging infrastructure for the TimeLimit debug server, including configuration, log formats, and analysis procedures.

## Overview

The TimeLimit debug server uses structured logging with the following components:

- **structlog** for structured JSON logging
- **RotatingFileHandler** for log file rotation
- **Console output** for real-time monitoring
- **Request/Response logging middleware** for HTTP request tracking

## Log Configuration

### Configuration Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `LOG_FILE_PATH` | `logs/debug-server.log` | Path to the log file |
| `LOG_MAX_BYTES` | `10485760` (10MB) | Maximum size of each log file |
| `LOG_BACKUP_COUNT` | `5` | Number of backup log files to keep |
| `LOG_FORMAT` | `json` | Output format (`json` or `console`) |

### Configuration Example

```yaml
# .env file
LOG_LEVEL=INFO
LOG_FILE_PATH=logs/debug-server.log
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=5
LOG_FORMAT=json
```

## Log Format

### JSON Format (default)

```json
{
  "timestamp": "2024-01-15T10:30:00.000000Z",
  "level": "INFO",
  "event": "Request started",
  "request_id": "abc123-def456-ghi789",
  "method": "POST",
  "path": "/api/v1/auth/login",
  "client_ip": "192.168.1.100",
  "duration_ms": 45,
  "status_code": 200
}
```

### Console Format

```
2024-01-15T10:30:00Z [INFO] Request started - method=POST path=/api/v1/auth/login
```

## Log Levels

| Level | Description |
|-------|-------------|
| `DEBUG` | Detailed debugging information |
| `INFO` | General operational information |
| `WARNING` | Warning conditions (potential issues) |
| `ERROR` | Error events that might still allow the request to complete |
| `CRITICAL` | Critical errors that cause request failure |

## Sensitive Data Sanitization

The logging system automatically sanitizes sensitive data:

- Passwords (`password`, `password_hash`, `second_hash`, `second_salt`)
- Tokens (`token`, `access_token`, `refresh_token`, `device_auth_token`, `mail_auth_token`, `mail_login_token`)
- Secret keys (`secret_key`, `jwt_secret`, `api_key`)
- Private keys (`private_key`)
- Signatures (`signature`)
- Encrypted data (`encrypted`)

Sensitive values are replaced with `***REDACTED***`.

## Request/Response Logging Middleware

The `RequestResponseLoggingMiddleware` logs:

### Request Information
- Request ID (UUID)
- HTTP method
- Request path
- Query string
- Client IP address
- Headers (sanitized)
- Request body size

### Response Information
- Status code
- Response size
- Request duration (milliseconds)

### Example Log Entry

```json
{
  "timestamp": "2024-01-15T10:30:00.123456Z",
  "level": "INFO",
  "event": "Request started",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "method": "POST",
  "path": "/api/v1/sync/pull-status",
  "query": "",
  "client_ip": "192.168.1.100",
  "headers": {
    "content-type": "application/json",
    "authorization": "***REDACTED***"
  },
  "body_size": 1024
}
```

## Log Analysis

### Using the analyze_logs.py Script

The `scripts/analyze_logs.py` script provides log analysis capabilities:

```bash
# Basic analysis
python scripts/analyze_logs.py

# Specify log file
python scripts/analyze_logs.py --log-file /path/to/logfile.log

# JSON output
python scripts/analyze_logs.py --output json
```

### Analysis Categories

1. **Errors**: All log entries with ERROR level or error patterns
2. **Security Events**: Authentication, token, password, and authorization events
3. **Communication Issues**: Timeout, connection refused, and network errors
4. **Warnings**: Warning-level log entries

### Example Output

```
============================================================
LOG ANALYSIS REPORT
============================================================

SUMMARY:
  Total Errors: 5
  Total Security Events: 12
  Total Communication Issues: 3
  Total Warnings: 8
  Total Info Events: 150

ERRORS:
  - Authentication failed: Invalid credentials
  - Database connection error: Connection refused

SECURITY EVENTS:
  - Token validation failed: Expired token
  - Login attempt: user@example.com

COMMUNICATION ISSUES:
  - Request timeout: /api/v1/sync/pull-status
  - Connection refused: Database server

============================================================
```

## Log Rotation

Logs are rotated automatically when they reach the configured maximum size:

- **Max file size**: 10 MB (configurable via `LOG_MAX_BYTES`)
- **Backup count**: 5 files (configurable via `LOG_BACKUP_COUNT`)
- **Rotation policy**: Oldest files are deleted when backup count is exceeded

### Example Rotation

```
logs/
├── debug-server.log         # Current log file
├── debug-server.log.1     # Most recent backup
├── debug-server.log.2
├── debug-server.log.3
├── debug-server.log.4
└── debug-server.log.5     # Oldest backup (will be deleted on next rotation)
```

## Monitoring and Alerting

### Health Check Endpoint

The `GET /health` endpoint provides server status:

```json
{
  "status": "ok",
  "version": "1.0.0",
  "uptime": 3600
}
```

### Metrics Endpoint

The `GET /metrics` endpoint provides Prometheus-style metrics:

```json
{
  "status": "ok",
  "totalRequests": 1000,
  "totalErrors": 5,
  "activeSessions": 10
}
```

## Best Practices

### Log Analysis Workflow

1. **Regular monitoring**: Check logs daily for errors and warnings
2. **Security review**: Review security events weekly
3. **Performance analysis**: Analyze request durations for performance issues
4. **Error investigation**: Investigate all ERROR level logs

### Troubleshooting

1. **High error rate**: Check for authentication failures or database issues
2. **Slow responses**: Look for long request durations in INFO logs
3. **Connection issues**: Check for timeout and connection refused errors
4. **Security concerns**: Review security events for suspicious activity

## Log File Locations

| Environment | Log File Path |
|-------------|---------------|
| Development | `logs/debug-server.log` |
| Production | `/var/log/timelimit/debug-server.log` |
| Docker | `/app/logs/debug-server.log` |

## Troubleshooting

### Log File Not Created

1. Check if the `logs/` directory exists
2. Verify write permissions
3. Check `LOG_FILE_PATH` configuration

### Logs Not Rotating

1. Verify `LOG_MAX_BYTES` is set correctly
2. Check file permissions
3. Restart the server to apply changes

### Missing Log Entries

1. Check `LOG_LEVEL` is set appropriately
2. Verify structlog is configured correctly
3. Check for exceptions in the application

## Related Files

- `app/utils/logger.py` - Structlog configuration
- `app/middleware/logging.py` - Request/response logging middleware
- `app/core/logging.py` - Legacy logging setup
- `scripts/analyze_logs.py` - Log analysis script
- `docs/logging.md` - This documentation