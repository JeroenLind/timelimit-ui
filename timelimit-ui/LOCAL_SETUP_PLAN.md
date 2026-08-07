# TimeLimit UI Local Setup Plan

## Overview
This document provides a comprehensive plan for setting up the TimeLimit UI application locally on Windows for faster development and testing, while maintaining connection to the real TimeLimit server.

## Current State
The TimeLimit UI project consists of:

**Backend (Python):**
- `web_server.py` - Main HTTP server acting as bridge between UI and backend server
- `api_client.py` - HTTP client for TimeLimit API calls
- `crypto_utils.py` - Cryptographic helpers for security and integrity

**Frontend (JavaScript):**
- `ui.js` - Main UI logic entry point
- `sync.js` - Synchronization engine
- `state.js` - Application state management
- `tree.js` - Hierarchical view rendering
- `wizard.js` - Onboarding workflow management

**Static Assets:**
- `dashboard.html` - Main dashboard interface
- `style.css` - Styling

## Development Goals

1. **Faster Testing**: Eliminate the need to build and install on Home Assistant
2. **Enhanced Debugging**: Better logging and debugging capabilities
3. **Direct Server Testing**: Test server connections directly from Windows
4. **Local Development Environment**: Familiar development setup for developers
5. **Log File Access**: Easy access to log files for troubleshooting

## Implementation Plan

### Phase 1: Environment Setup

#### 1.1 System Requirements
- Windows 10/11 (64-bit)
- Python 3.8 or higher
- Node.js (for JavaScript components)
- Git
- Docker (optional, for testing containerized setup)

#### 1.2 Python Environment Setup
```powershell
# Create virtual environment
python -m venv timelimit-ui-env

# Activate virtual environment
.timelimit-ui-env\Scripts\activate

# Install required packages
pip install requests bcrypt
```

#### 1.3 JavaScript Environment Setup
Download and install Node.js from [nodejs.org](https://nodejs.org/).

### Phase 2: Configuration Setup

#### 2.1 Update Configuration
Update `config.yaml` for local development:
- **Keep original server URL** for testing against real server
- Enable verbose logging for debugging
- Adjust ingress settings for local testing

#### 2.2 Create Options File
Create `/data/options.json` with local configuration:
```json
{
  "server_url": "http://192.168.68.30:8080",
  "logging_mode": "verbose"
}
```

### Phase 3: Enhanced Logging Setup

#### 3.1 Configure Logging Infrastructure
- Implement structured logging with file output
- Add log rotation for large log files
- Include timestamps, log levels, and structured messages
- Support both standard and verbose logging modes

#### 3.2 Log File Management
- Create log directory: `/data/logs/`
- Configure log file: `/data/logs/timelimit-ui.log`
- Implement log rotation to prevent disk space issues
- Add log filtering based on logging mode

### Phase 4: Development Scripts

#### 4.1 Development Script (`dev.bat`)
Create a batch file for easy development:
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

#### 4.2 Test Script (`test.bat`)
Create a batch file for running tests:
```batch
@echo off
REM TimeLimit UI Test Script

cd /d "%~dp0"

REM Run server connection test
python test_server_connection.py

REM Keep window open
pause
```

### Phase 5: Testing and Validation

#### 5.1 Server Connection Tests
- Test connectivity to TimeLimit server
- Test UI server endpoints
- Test API endpoints (GET and POST)
- Test error handling and recovery

#### 5.2 Test Script
Create comprehensive test script that:
- Tests server connectivity
- Tests UI server functionality
- Tests API endpoints
- Validates log file creation
- Reports test results

### Phase 6: Documentation

#### 6.1 Development Guide
Create `local-dev-setup.md` with:
- Prerequisites and system requirements
- Step-by-step setup instructions
- Configuration details
- Troubleshooting guide
- Best practices

#### 6.2 API Documentation
Document all API endpoints:
- UI ↔ Backend endpoints
- Server ↔ TimeLimit endpoints
- Authentication flows
- Error handling

## Technical Specifications

### Server Configuration
- **Port**: 8099 (TimeLimit UI)
- **Host**: localhost (for local development)
- **Logging**: Standard/verbose modes
- **Storage**: JSON files in `/data/` directory

### API Endpoints
#### UI ↔ Backend (web_server.py)
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/set-server` | POST | Update server selection |
| `/ha-storage` | POST/GET | HA storage shadow copy |
| `/ha-events-longpoll` | GET | Long-polling for events |
| `/sync` | POST | Pull status data |
| `/sync/push-actions` | POST | Push changes to server |
| `/generate-hashes` | POST | Generate password hashes |
| `/calculate-hmac-sha256` | POST | Calculate HMAC-SHA256 |

## Deployment Steps

### 1. Initial Setup
1. Clone the repository
2. Create virtual environment
3. Install dependencies
4. Create local configuration
5. Run development script

### 2. Development Workflow
1. Make changes to code
2. Test changes with test script
3. Verify log files
4. Check server connectivity
5. Update documentation as needed

### 3. Testing Workflow
1. Run unit tests
2. Run integration tests
3. Run end-to-end tests
4. Review test results
5. Fix any issues

## Testing Strategy

### 1. Unit Tests
- Test individual functions in Python modules
- Test JavaScript functions
- Test cryptographic operations

### 2. Integration Tests
- Test server connectivity
- Test API endpoints
- Test UI functionality

### 3. End-to-End Tests
- Test complete user workflows
- Test authentication flows
- Test synchronization processes

## Success Criteria

1. **Functionality**: All UI features work correctly
2. **Performance**: Response times meet requirements
3. **Reliability**: No crashes or data loss
4. **Security**: All security measures are in place
5. **Usability**: Easy to set up and use
6. **Documentation**: Comprehensive documentation available

## Timeline

### Week 1: Setup and Configuration
- Create development environment
- Set up logging infrastructure
- Configure local development

### Week 2: Testing and Validation
- Create test scripts
- Run initial tests
- Validate functionality

### Week 3: Documentation and Refinement
- Create comprehensive documentation
- Refine development scripts
- Optimize performance

### Week 4: Final Testing and Deployment
- Run complete test suite
- Deploy to development environment
- Provide training and support

## Risk Mitigation

### 1. Port Conflicts
- Check for port 8099 usage before starting
- Use different ports if needed
- Document port configuration

### 2. Configuration Issues
- Validate configuration files
- Use default values when unsure
- Document configuration options

### 3. Dependency Issues
- Use virtual environment
- Document dependency versions
- Provide installation instructions

## Conclusion

This local development setup provides a faster and more efficient way to test and develop the TimeLimit UI application. By running the application directly on Windows, developers can quickly iterate, debug, and test changes without the overhead of building and installing on Home Assistant.

The enhanced logging, direct server testing, and comprehensive test suite will ensure high-quality development and reliable operation. The documentation and development scripts will make it easy for developers to get started and maintain the codebase.

This plan will enable faster development cycles, better debugging capabilities, and a more efficient development experience for the TimeLimit UI project.