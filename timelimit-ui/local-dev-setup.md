# TimeLimit UI Local Development Setup for Windows

## Overview
This guide provides instructions for setting up the TimeLimit UI application locally on Windows for faster testing and development, eliminating the need to build and install on Home Assistant each time.

## Prerequisites

### System Requirements
- Windows 10/11 (64-bit)
- Python 3.8 or higher
- Node.js (for JavaScript components)
- Git
- Docker (optional, for testing containerized setup)

### Dependencies
- Python packages: `requests`, `bcrypt`, `http.server`
- Node.js packages: `tweetnacl` (for crypto operations)

## Setup Steps

### 1. Python Backend Setup

#### Install Python Dependencies
```powershell
# Create virtual environment
python -m venv timelimit-ui-env

# Activate virtual environment
.timelimit-ui-env\Scripts\activate

# Install required packages
pip install requests bcrypt
```

#### Run the Web Server
```powershell
# Navigate to the rootfs/usr/bin directory
cd timelimit-ui\rootfs\usr\bin

# Run the web server (port 8099)
python web_server.py
```

### 2. JavaScript Frontend Setup

#### Install Node.js
Download and install Node.js from [nodejs.org](https://nodejs.org/).

#### Run the Dashboard
```powershell
# Navigate to the rootfs/usr/bin directory
cd timelimit-ui\rootfs\usr\bin

# Open dashboard.html in a web browser
# The server will serve the HTML and JavaScript files
```

### 3. Configuration Setup

#### Create Local Configuration
Create a `config.yaml` file in the `timelimit-ui` directory:

```yaml
name: "Timelimit UI"
description: "WebUI app voor beheer van TimeLimit regels en synchronisatie"
version: "1.0.0"
slug: "timelimit-ui"
arch:
  - amd64
init: false
image: "ghcr.io/jeroenlind/timelimit-ui-amd64"
ingress: true
ingress_port: 8099
panel_icon: "mdi:clock-check"
panel_title: "Timelimit"
panel_admin: false
options:
  server_url: "http://localhost:8080"  # Change to your TimeLimit server
  logging_mode: "verbose"  # Enable verbose logging for debugging
schema:
  server_url: str
  logging_mode: list(standard|verbose)
```

#### Create Options File
Create `/data/options.json` for the web server:

```json
{
  "server_url": "http://localhost:8080",
  "logging_mode": "verbose"
}
```

### 4. Enhanced Logging Configuration

#### Enable Verbose Logging
Set `logging_mode` to "verbose" in the configuration to enable detailed logging for debugging.

#### Log File Setup
Create a log directory and configure the web server to write logs:

```powershell
# Create log directory
mkdir logs

# Modify web_server.py to write logs to file
# Add this to the log function in web_server.py:
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/timelimit-ui.log'),
        logging.StreamHandler()
    ]
)
```

### 5. Direct Server Connection Testing

#### Test Server Connectivity
Create a test script to verify server connectivity:

```python
# test_server_connection.py
import requests
import json
import time

def test_server_connection(server_url="http://localhost:8080"):
    """Test connection to TimeLimit server"""
    print(f"Testing connection to {server_url}")
    
    # Test basic connectivity
    try:
        response = requests.get(f"{server_url}/health", timeout=5)
        print(f"Server status: {response.status_code}")
        return True
    except Exception as e:
        print(f"Connection failed: {e}")
        return False

def test_ui_endpoints():
    """Test UI endpoints"""
    ui_url = "http://localhost:8099"
    
    # Test UI server
    try:
        response = requests.get(ui_url, timeout=5)
        print(f"UI server status: {response.status_code}")
        return True
    except Exception as e:
        print(f"UI server connection failed: {e}")
        return False

if __name__ == "__main__":
    print("=== TimeLimit UI Local Development Test ===")
    
    # Test server connection
    server_ok = test_server_connection()
    
    # Test UI server
    ui_ok = test_ui_endpoints()
    
    if server_ok and ui_ok:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed")
```

### 6. Development Scripts

#### Create Development Script
Create a `dev.bat` file for easy development:

```batch
@echo off
REM TimeLimit UI Development Script

cd /d "%~dp0"

REM Start Python web server in background
start "TimeLimit Web Server" cmd /c "cd rootfs\usr\bin & python web_server.py"

REM Wait for server to start
sleep 3

REM Open dashboard in default browser
start "TimeLimit UI" http://localhost:8099

REM Keep script running
pause
```

#### Create Test Script
Create a `test.bat` file for running tests:

```batch
@echo off
REM TimeLimit UI Test Script

cd /d "%~dp0"

REM Run server connection test
python test_server_connection.py

REM Keep window open
pause
```

### 7. File Structure for Local Development

```
timelimit-ui/
├── config.yaml                    # Local configuration
├── dev.bat                        # Development script
├── test.bat                       # Test script
├── test_server_connection.py      # Server connection test
├── logs/                          # Log files (created during runtime)
├── rootfs/
│   └── usr/bin/                   # Application binaries
│       ├── web_server.py          # Web server
│       ├── api_client.py          # API client
│       ├── crypto_utils.py        # Crypto utilities
│       ├── dashboard.html         # HTML dashboard
│       ├── ui.js                  # UI logic
│       ├── sync.js                # Sync logic
│       ├── state.js               # State management
│       ├── tree.js                # Tree rendering
│       └── wizard.js              # Onboarding
└── data/                          # Persistent data
    ├── options.json               # Web server configuration
    └── timelimit_ui_storage.json  # UI state storage
```

### 8. Troubleshooting

#### Common Issues

1. **Port Conflicts**
   - Check if port 8099 is already in use
   - Use `netstat -ano | findstr :8099` to check
   - Change port in config.yaml if needed

2. **Python Dependencies**
   - Ensure all required packages are installed
   - Use `pip install -r requirements.txt` if available

3. **JavaScript Issues**
   - Ensure Node.js is installed
   - Check browser console for JavaScript errors

4. **Configuration Issues**
   - Verify config.yaml syntax
   - Check file permissions

#### Debug Commands
```powershell
# Check running processes
netstat -ano | findstr :8099

# Check Python processes
wmic process where name="python.exe" get CommandLine

# Check log files
Get-Content logs\timelimit-ui.log -Wait
```

## Benefits of Local Development

1. **Faster Testing**: No need to build and install on Home Assistant
2. **Easier Debugging**: Enhanced logging and direct access to logs
3. **Quick Iteration**: Changes are immediately reflected
4. **Better Development Experience**: Local development environment familiar to developers
5. **Log File Access**: Easy access to log files for troubleshooting

## Next Steps

1. Set up the local development environment
2. Test server connectivity
3. Run the web server and dashboard
4. Create test cases for specific functionality
5. Implement logging enhancements
6. Document any issues or improvements

## Conclusion

This local development setup provides a faster and more efficient way to test and develop the TimeLimit UI application. By running the application directly on Windows, developers can quickly iterate, debug, and test changes without the overhead of building and installing on Home Assistant.
