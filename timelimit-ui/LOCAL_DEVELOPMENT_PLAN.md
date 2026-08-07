# TimeLimit UI Local Development Plan

## Overview
This document outlines the plan for setting up the TimeLimit UI application locally on Windows for faster development and testing, eliminating the need to build and install on Home Assistant each time.

## Current State Analysis

### Project Structure
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

### Current Configuration
- `config.yaml` - Application configuration for Home Assistant integration
- Default server URL: `http://192.168.68.30:8080`
- Ingress port: 8099

## Development Goals

1. **Faster Testing**: Eliminate the need to build and install on Home Assistant
2. **Enhanced Debugging**: Better logging and debugging capabilities
3. **Direct Server Testing**: Test server connections directly from Windows
4. **Local Development Environment**: Familiar development setup for developers
5. **Log File Access**: Easy access to log files for troubleshooting

## Implementation Plan

### Phase 1: Local Development Setup

#### 1.1 Python Environment Setup
- Create virtual environment for Python dependencies
- Install required packages: `requests`, `bcrypt`, `http.server`
- Set up Python path for local development

#### 1.2 JavaScript Environment Setup
- Install Node.js for JavaScript components
- Set up local web server for static assets

#### 1.3 Directory Structure
```
timelimit-ui/
├── local-dev-setup.md              # Local development guide
├── LOCAL_DEVELOPMENT_PLAN.md       # This development plan
├── test_server_connection.py       # Server connection test script
├── dev.bat                         # Development script
├── test.bat                        # Test script
├── requirements.txt                # Python dependencies
├── package.json                    # Node.js dependencies
├── data/                           # Local data storage
│   ├── options.json                # Web server configuration
│   └── timelimit_ui_storage.json  # UI state storage
└── logs/                           # Log files
```

### Phase 2: Enhanced Logging Configuration

#### 2.1 Logging Infrastructure
- Implement structured logging with file output
- Add log rotation for large log files
- Include timestamps, log levels, and structured messages
- Support both standard and verbose logging modes

#### 2.2 Log File Management
- Create log directory: `/data/logs`
- Configure log file: `/data/logs/timelimit-ui.log`
- Implement log rotation to prevent disk space issues
- Add log filtering based on logging mode

### Phase 3: Direct Server Connection Testing

#### 3.1 Server Connection Tests
- Test connectivity to TimeLimit server
- Test UI server endpoints
- Test API endpoints (GET and POST)
- Test error handling and recovery

#### 3.2 Test Script
Create comprehensive test script that:
- Tests server connectivity
- Tests UI server functionality
- Tests API endpoints
- Validates log file creation
- Reports test results

### Phase 4: Configuration Updates

#### 4.1 Local Configuration
Update `config.yaml` for local development:
- Change server URL to local development server
- Enable verbose logging for debugging
- Adjust ingress settings for local testing

#### 4.2 Options File
Create `/data/options.json` with local configuration:
```json
{
  "server_url": "http://localhost:8080",
  "logging_mode": "verbose"
}
```

### Phase 5: Development Scripts

#### 5.1 Development Script (`dev.bat`)
- Start Python web server in background
- Wait for server to start
- Open dashboard in default browser
- Keep script running for development

#### 5.2 Test Script (`test.bat`)
- Run server connection tests
- Validate log file creation
- Report test results
- Keep window open for review

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

### Security Considerations
- SSL context management for secure connections
- Cryptographic operations for data integrity
- Token-based authentication
- Session management

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

## Benefits of Local Development

1. **Faster Iteration**: No need to build and install on Home Assistant
2. **Better Debugging**: Enhanced logging and direct access to logs
3. **Easier Testing**: Direct server connection testing
4. **Developer Friendly**: Familiar development environment
5. **Quick Feedback**: Immediate feedback on changes

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

## Success Criteria

1. **Functionality**: All UI features work correctly
2. **Performance**: Response times meet requirements
3. **Reliability**: No crashes or data loss
4. **Security**: All security measures are in place
5. **Usability**: Easy to set up and use
6. **Documentation**: Comprehensive documentation available

## Conclusion

This local development setup provides a faster and more efficient way to test and develop the TimeLimit UI application. By running the application directly on Windows, developers can quickly iterate, debug, and test changes without the overhead of building and installing on Home Assistant.

The enhanced logging, direct server testing, and comprehensive test suite will ensure high-quality development and reliable operation. The documentation and development scripts will make it easy for developers to get started and maintain the codebase.

This plan will enable faster development cycles, better debugging capabilities, and a more efficient development experience for the TimeLimit UI project.