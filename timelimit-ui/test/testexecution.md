# Test Execution Guide

This document provides instructions for running the unit tests for the TimeLimit UI debug mode functionality.

## Prerequisites

- Node.js installed (v12 or higher recommended)
- A web browser for browser-based testing
- The TimeLimit UI running locally (optional for browser tests)

## Running JavaScript Unit Tests

### Option 1: Node.js Environment (Recommended)

```bash
# Navigate to the project root
cd c:/git/timelimit-ui

# Run the debug mode tests directly with Node.js
node timelimit-ui/test/test_debug_mode.js
```

**Expected Output:**
```
Running debug mode tests...

✅ Test 1 PASSED: isDebugMode returns true when localStorage is null
✅ Test 2 PASSED: isDebugMode returns true when localStorage is "1"
✅ Test 3 PASSED: isDebugMode returns false when localStorage is "0"
✅ Test 4 PASSED: applyDebugMode sets display to "block" when enabled is true
✅ Test 5 PASSED: applyDebugMode sets display to "none" when enabled is false
✅ Test 6 PASSED: setDebugMode saves "1" to localStorage and shows debug window
✅ Test 7 PASSED: setDebugMode saves "0" to localStorage and hides debug window

========================================
Tests completed: 7
Passed: 7
Failed: 0
========================================
```

### Option 2: Browser Console

1. Start the TimeLimit UI server:
   ```bash
   cd c:/git/timelimit-ui
   python -m http.server 8099
   ```
   Or use the existing test environment:
   ```bash
   python test/start_test_environment.py
   ```

2. Open your browser and navigate to: `http://localhost:8099`

3. Open Developer Tools:
   - Press `F12` or `Ctrl+Shift+I` (Windows/Linux) or `Cmd+Option+I` (Mac)
   - Click on the "Console" tab

4. Copy and paste the test functions from `test_debug_mode.js` into the console, then run:
   ```javascript
   runTests();
   ```

### Option 3: Using a Test Runner (Jest)

If you have Jest installed or want to use it:

```bash
# Install Jest (if not already installed)
npm install --save-dev jest

# Run the tests
npx jest timelimit-ui/test/test_debug_mode.js
```

### Option 4: Using a Test Runner (Mocha)

```bash
# Install Mocha (if not already installed)
npm install --save-dev mocha

# Run the tests
npx mocha timelimit-ui/test/test_debug_mode.js
```

## Test Descriptions

| Test # | Function | Description |
|--------|----------|-------------|
| 1 | `isDebugMode()` | Returns `true` when localStorage is null (default behavior) |
| 2 | `isDebugMode()` | Returns `true` when localStorage is '1' |
| 3 | `isDebugMode()` | Returns `false` when localStorage is '0' |
| 4 | `applyDebugMode(true)` | Sets display to 'block' with !important |
| 5 | `applyDebugMode(false)` | Sets display to 'none' |
| 6 | `setDebugMode(true)` | Saves '1' to localStorage and shows debug window |
| 7 | `setDebugMode(false)` | Saves '0' to localStorage and hides debug window |

## Test Files

| File | Description |
|------|-------------|
| `test_debug_mode.js` | Unit tests for debug mode functionality |
| `testexecution.md` | This file - test execution guide |

## Troubleshooting

### Tests fail with "Cannot find module" error
- Ensure you're running from the correct directory
- Check that Node.js is installed and in your PATH

### Tests fail with "document is not defined" error
- This is expected when running in Node.js without a DOM environment
- The tests include a mock DOM environment, but if issues persist, try the browser console method

### Debug window not showing/hiding correctly
- Clear your browser cache and local storage
- Try a hard refresh (Ctrl+F5 or Cmd+Shift+R)
- Check that the debug mode checkbox is working correctly

## Additional Testing

For testing the "Check Server Time" button functionality:

1. Start the debug-server:
   ```bash
   cd c:/git/timelimit-ui/debug-server
   python run.py
   ```

2. Start the TimeLimit UI:
   ```bash
   cd c:/git/timelimit-ui
   python test/start_test_environment.py
   ```

3. Open `http://localhost:8099` in your browser

4. Enable debug mode by checking the "Debug" checkbox in the bottom bar

5. Click the ⏱️ "Check" button to verify server time functionality

## Contact

For issues or questions, please refer to the main project documentation or contact the development team.