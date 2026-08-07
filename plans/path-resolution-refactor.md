# Path Resolution Refactor Plan

## Problem Analysis

### Current Issue
When the webserver serves `dashboard.html`, it reports 404 errors for CSS and JS files:
- `/style.css?v=96` - 404
- `/state.js?v=104` - 404
- `/ui.js?v=121` - 404
- `/sync.js?v=100` - 404
- `/wizard.js?v=87` - 404
- `/tree.js?v=100` - 404

### Root Cause
The `web_server.py` uses `os.path.dirname(__file__)` to determine paths, but:
1. The `SimpleHTTPRequestHandler` with `self.directory` attribute doesn't work correctly in all Python versions
2. Query strings (`?v=96`) in static file URLs are not being handled properly
3. The `find_project_root()` function creates confusion by searching for `context.md`
4. Two separate files (`web_server.py` and `frontend.py`) have different path strategies

### Current Path Strategies

| File | Container Paths | Test Paths |
|------|---------------|------------|
| `web_server.py` | Uses `find_project_root()` + relative paths | Uses `find_project_root()` + relative paths |
| `frontend.py` | Hardcoded absolute paths (`/data/...`, `/usr/bin/...`) | Not used in test |

## Solution Concept

### Core Principle
All file paths should be resolved **relative to the script's location** (`__file__`), not the current working directory. This ensures the code works regardless of where it's started from.

### Path Resolution Strategy
```
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'data')
STATIC_DIR = SCRIPT_DIR  # All static files (HTML, CSS, JS) are in the same directory
```

### Key Changes

1. **Remove `find_project_root()` function** - Not needed for path resolution
2. **Use `os.path.abspath(__file__)` consistently** - Always resolve from script location
3. **Handle query strings in static file requests** - Strip query params before serving
4. **Unify `web_server.py` and `frontend.py`** - Single source of truth for paths

## Implementation Plan

### Step 1: Refactor web_server.py
- Remove `find_project_root()` function
- Define all paths relative to script directory
- Add query string stripping for static file requests
- Ensure `SimpleHTTPRequestHandler` serves from correct directory

### Step 2: Update start_test_environment.py
- Remove `TLUI_ROOTFS_PATH` environment variable (no longer needed)
- Ensure test data directory structure matches expected paths
- Update log path to be relative to script location

### Step 3: Update s6-overlay run script
- Ensure container starts server from correct directory
- Verify paths work in container environment

### Step 4: Test the changes
- Start webserver in test environment
- Verify all static files are served correctly
- Check log file for errors

## File Changes Summary

### Files to Modify
1. `timelimit-ui/rootfs/usr/bin/web_server.py` - Main webserver
2. `timelimit-ui/test/start_test_environment.py` - Test environment script
3. `timelimit-ui/rootfs/etc/s6-overlay/s6-rc.d/web-server/run` - Container startup

### Files to Keep Unchanged
- `timelimit-ui/rootfs/usr/bin/dashboard.html` - Static file references are correct
- `timelimit-ui/rootfs/usr/bin/*.js` - JavaScript files
- `timelimit-ui/rootfs/usr/bin/style.css` - CSS file

## Expected Outcome

After the changes:
- Webserver works from any working directory
- All static files (CSS, JS) are served correctly
- No more 404 errors for static assets
- Code is platform-independent and uses only relative paths