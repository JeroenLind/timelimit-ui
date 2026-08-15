# TimeLimit UI Logging Instructions

This document provides instructions for accessing and interpreting debug logs for the TimeLimit UI application, particularly for troubleshooting the "Check" button functionality.

## Table of Contents

1. [Log File Locations](#log-file-locations)
2. [Enabling Verbose Logging](#enabling-verbose-logging)
3. [Check Button Debug Flow](#check-button-debug-flow)
4. [Testing the Check Endpoint](#testing-the-check-endpoint)
5. [Common Issues and Solutions](#common-issues-and-solutions)
6. [Log Message Reference](#log-message-reference)

---

## Log File Locations

### Application Log File
```
c:/git/timelimit-ui/timelimit-ui/data/logs/timelimit-ui.log
```

### Server Output (Terminal)
When running via `start_test_environment.py`, server output is displayed in the terminal.

### Browser Console
Open browser DevTools (F12) → Console tab for frontend JavaScript logs.

---

## Enabling Verbose Logging

Edit `timelimit-ui/data/options.json` to enable verbose logging:

```json
{
  "server_url": "http://localhost:8080",
  "logging_mode": "verbose"
}
```

**Note:** After changing this setting, restart the web server for changes to take effect.

---

## Check Button Debug Flow

### Expected Log Messages

When you click the "Check" button, look for these log entries:

#### Backend Logs (timelimit-ui.log)

**Successful Check:**
```
[DEBUG] Route /api/time herkend
[DEBUG] SELECTED_SERVER geïnitialiseerd op: http://localhost:8080
[DEBUG] Making request to: http://localhost:8080/time
[DEBUG] Response status: 200, body size: 32 bytes
[SUCCESS] Server time check passed after 1 attempt(s)
```

**Timeout Error:**
```
[DEBUG] Route /api/time herkend
[DEBUG] SELECTED_SERVER geïnitialiseerd op: http://localhost:8080
[DEBUG] Making request to: http://localhost:8080/time
[WARNING] Timeout on attempt 1: Connection timed out
[DEBUG] Waiting 1.0s before retry...
[WARNING] Timeout on attempt 2: Connection timed out
[DEBUG] Waiting 2.0s before retry...
[WARNING] Timeout on attempt 3: Connection timed out
[ERROR] Server check failed after 3 attempt(s): timeout
```

**Unreachable Server:**
```
[DEBUG] Route /api/time herkend
[DEBUG] SELECTED_SERVER geïnitialiseerd op: http://localhost:8080
[DEBUG] Making request to: http://localhost:8080/time
[ERROR] Connection refused on attempt 1: Connection refused
[ERROR] Server check failed after 1 attempt(s): unreachable
```

#### Frontend Logs (Browser Console)

**Successful Check:**
```
⏱️ Checking server time...
✅ Server time: 14:30:00
```

**Error:**
```
⏱️ Checking server time...
❌ Server check failed (timeout): Connection timeout after 10s
   Attempts: 3, User message: Server did not respond within the timeout period...
```

---

## Testing the Check Endpoint

### Using curl

```bash
curl -X POST http://localhost:8099/api/time -H "Content-Type: application/json" -d '{}'
```

### Expected Responses

**Success:**
 ```json
 {
   "status": "ok",
   "ms": 1704067200000
 }
 ```

**Error:**
```json
{
  "status": "error",
  "error_code": "timeout",
  "user_message": "Server did not respond within the timeout period...",
  "technical_detail": "Connection timeout after 10s: ...",
  "attempts": 3
}
```

### Using Python requests

```python
import requests

response = requests.post('http://localhost:8099/api/time', json={})
print(response.json())
```

---

## Common Issues and Solutions

### Issue: Check button does nothing

**Possible Causes:**
1. Server not running on port 8099
2. `check_server.py` module not found
3. JavaScript error in browser console

**Solutions:**
1. Verify server is running: `curl http://localhost:8099/`
2. Check if `check_server.py` exists: `ls timelimit-ui/rootfs/usr/bin/check_server.py`
3. Open browser DevTools (F12) → Console tab for JavaScript errors

### Issue: "❌ Error" displayed in UI

**Possible Causes:**
1. TimeLimit server not running
2. Network connectivity issues
3. Server URL misconfiguration

**Solutions:**
1. Check log file for error details
2. Verify TimeLimit server is running on configured URL
3. Check network connectivity to the server

### Issue: Import errors

**Possible Causes:**
1. `check_server.py` module not in Python path
2. Missing dependencies

**Solutions:**
1. The web_server.py has a fallback mechanism if `check_server` module is not available
2. Check logs for: `[WARNING] check_server module not available`
3. Ensure `check_server.py` is in `timelimit-ui/rootfs/usr/bin/`

### Issue: Timeout errors

**Possible Causes:**
1. TimeLimit server is slow to respond
2. Network latency
3. Server is overloaded

**Solutions:**
1. Increase timeout in `check_server.py`:
   ```python
   checker = ServerChecker(server_url=..., timeout=30.0, ...)
   ```
2. Check server resources

---

## Log Message Reference

### Backend Log Messages

| Prefix | Meaning | Example |
|--------|---------|---------|
| `[DEBUG]` | Debug information (filtered in standard mode) | `[DEBUG] Route /api/time herkend` |
| `[SUCCESS]` | Successful operation | `[SUCCESS] Server time check passed after 1 attempt(s)` |
| `[WARNING]` | Warning condition | `[WARNING] Timeout on attempt 1: Connection timed out` |
| `[ERROR]` | Error condition | `[ERROR] Server check failed after 3 attempt(s): timeout` |
| `[EVENT]` | Event broadcast | `[EVENT] Broadcast event=push data=done` |

### Frontend Log Messages

| Prefix | Meaning | Example |
|--------|---------|---------|
| `⏱️` | Check operation started | `⏱️ Checking server time...` |
| `✅` | Success | `✅ Server time: 14:30:00` |
| `❌` | Error | `❌ Server check failed: timeout` |

---

## Quick Troubleshooting Checklist

1. ✅ Verify web server is running on port 8099
2. ✅ Check `timelimit-ui/data/options.json` for correct `server_url`
3. ✅ Enable verbose logging: `"logging_mode": "verbose"`
4. ✅ Restart web server after configuration changes
5. ✅ Check log file: `timelimit-ui/data/logs/timelimit-ui.log`
6. ✅ Open browser DevTools (F12) → Console tab
7. ✅ Test endpoint directly: `curl -X POST http://localhost:8099/api/time`
8. ✅ Verify TimeLimit server is running on configured URL