# Solution Plan: Fix Test Environment RootFS Path Issue

## Problem Analysis
The test environment does not properly simulate the Docker container's root filesystem structure. In the Docker container, the application runs with `/` as the root filesystem, where:
- `/data/options.json` maps to `timelimit-ui/data/options.json`
- `/usr/bin/dashboard.html` maps to `timelimit-ui/rootfs/usr/bin/dashboard.html`
- `/data/logs/` maps to `timelimit-ui/data/logs/`

However, in the test environment, the web server is started from the `timelimit-ui/rootfs` directory, making the absolute paths incorrect.

## Solution Overview
Modify the web server to use an environment variable (`TLUI_ROOTFS_PATH`) as the base path for all absolute paths, making it configurable for different environments.

## Changes Required

### 1. Modify start_test_environment.py
Add environment variable setup to point to the rootfs directory:
```python
# Set base path for rootfs simulation
os.environ['TLUI_ROOTFS_PATH'] = r'C:\git\timelimit-ui\timelimit-ui\rootfs'
```

### 2. Modify web_server.py
Update all absolute path constants to be relative to the TLUI_ROOTFS_PATH environment variable:
- CONFIG_PATH = "/data/options.json" → os.path.join(os.environ.get('TLUI_ROOTFS_PATH', ''), "data/options.json")
- HTML_PATH = "/usr/bin/dashboard.html" → os.path.join(os.environ.get('TLUI_ROOTFS_PATH', ''), "usr/bin/dashboard.html")
- STORAGE_PATH = "/data/timelimit_ui_storage.json" → os.path.join(os.environ.get('TLUI_ROOTFS_PATH', ''), "data/timelimit_ui_storage.json")
- STORAGE_TMP_PATH = "/data/timelimit_ui_storage.json.tmp" → os.path.join(os.environ.get('TLUI_ROOTFS_PATH', ''), "data/timelimit_ui_storage.json.tmp")
- LOG_DIR = "/data/logs" → os.path.join(os.environ.get('TLUI_ROOTFS_PATH', ''), "data/logs")
- LOG_FILE = "/data/logs/timelimit-ui.log" → os.path.join(os.environ.get('TLUI_ROOTFS_PATH', ''), "data/logs/timelimit-ui.log")

Add fallback logic to use original paths if TLUI_ROOTFS_PATH is not set (for Docker compatibility).

## Implementation Steps
1. Modify start_test_environment.py to set TLUI_ROOTFS_PATH environment variable
2. Modify web_server.py to use TLUI_ROOTFS_PATH for path resolution
3. Test the solution by running the test environment and verifying the web server can find resources

## Expected Outcome
The test environment will properly simulate the Docker container's filesystem structure, allowing the web server to find its resources correctly when running from the timelimit-ui/rootfs directory.