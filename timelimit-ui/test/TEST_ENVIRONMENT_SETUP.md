# TimeLimit UI Test Environment Setup

This document provides instructions for setting up and using the TimeLimit UI test environment.

## Overview

The TimeLimit UI test environment provides a complete local development setup that starts the webserver and all other components for testing purposes. It eliminates the need to build and install on Home Assistant each time.

## Files in This Directory

- `start_test_environment.py` - Main script to start the complete test environment
- `config.yaml` - Local configuration file for the TimeLimit UI
- `data/options.json` - Web server configuration
- `data/logs/timelimit-ui.log` - Log file for the application

## Quick Start

### Prerequisites

1. **Python 3.8 or higher**
2. **Node.js** (for JavaScript components)
3. **Git**
4. **Docker** (optional, for testing containerized setup)

### Installation

1. Clone the repository
2. Navigate to the timelimit-ui directory
3. Run the test environment script:

```bash
python test/start_test_environment.py
```

### What This Script Does

The `start_test_environment.py` script performs the following actions:

1. **Sets up the environment**:
   - Creates necessary directories (`data`, `data/logs`, `rootfs/usr/bin`)
   - Creates `options.json` configuration file
   - Creates log file

2. **Starts the web server**:
   - Launches the TimeLimit UI web server on port 8099
   - Waits for the server to start
   - Monitors server output for errors

3. **Starts frontend components**:
   - Checks for essential frontend files
   - Verifies all JavaScript and HTML files are present

4. **Runs health checks**:
   - Tests server connectivity
   - Validates server responses

5. **Runs test suite**:
   - Executes existing test scripts
   - Validates server connection tests

6. **Keeps the environment running**:
   - Displays startup information
   - Opens the dashboard in your browser
   - Waits for user interruption

## Configuration

### config.yaml

The `config.yaml` file contains the following configuration options:

- `name`: Application name
- `description`: Application description
- `version`: Application version
- `slug`: Application slug
- `arch`: Supported architectures
- `init`: Initialization flag
- `image`: Docker image name
- `ingress`: Ingress enabled flag
- `ingress_port`: Ingress port (8099)
- `panel_icon`: Panel icon
- `panel_title`: Panel title
- `panel_admin`: Admin panel flag
- `options`: Configuration options
  - `server_url`: TimeLimit server URL
  - `logging_mode`: Logging mode (standard or verbose)
- `schema`: Configuration schema

### options.json

The `data/options.json` file contains the web server configuration:

- `server_url`: TimeLimit server URL (default: `http://localhost:8080`)
- `logging_mode`: Logging mode (default: `verbose`)

## Usage

### Starting the Test Environment

Run the following command from the timelimit-ui directory:

```bash
python test/start_test_environment.py
```

### Stopping the Test Environment

Press Ctrl+C in the terminal where the script is running, or run:

```bash
pkill -f web_server.py
```

### Accessing the UI

Once the test environment is running, open your web browser and navigate to:

```
http://localhost:8099
```

### Viewing Logs

The application logs are stored in:

```
<workspace>/timelimit-ui/test/data/logs/timelimit-ui.log
```

You can view the logs in real-time using:

```bash
tail -f timelimit-ui/test/data/logs/timelimit-ui.log
```

## Testing

### Running Server Connection Tests

You can run the existing server connection tests manually:

```bash
python test/test_server_connection.py
```

### Running Local Setup Tests

You can run the local setup verification tests:

```bash
python test/test_local_setup.py
```

## Troubleshooting

### Common Issues

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

### Debug Commands

```powershell
# Check running processes
netstat -ano | findstr :8099

# Check Python processes
wmic process where name="python.exe" get CommandLine

# Check log files
Get-Content test\data\logs\timelimit-ui.log -Wait
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

This test environment provides a faster and more efficient way to test and develop the TimeLimit UI application. By running the application directly on Windows, developers can quickly iterate, debug, and test changes without the overhead of building and installing on Home Assistant.

The enhanced logging, direct server testing, and comprehensive test suite will ensure high-quality development and reliable operation. The documentation and development scripts will make it easy for developers to get started and maintain the codebase.