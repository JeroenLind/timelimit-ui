# Verification Plan: Create New Family Flow

## Overview
This document outlines the steps to verify the createNewFamily flow implementation in dashboardV2.

## Prerequisites
1. Docker container running dashboardV2
2. Debug server running on port 8080
3. Browser with hard refresh capability (Ctrl+F5 or Cmd+Shift+R)

## Verification Steps

### Step 1: Verify Version Number
1. Open browser and navigate to `http://localhost:8099/dashboardV2`
2. Check the page title - should show "TimeLimit Dashboard v2 - v1.0.0"
3. Check the Dashboard Content heading - should show "Dashboard Content v1.0.0"

### Step 2: Verify "Create New Family" Button
1. On the dashboard page, scroll to the bottom
2. Look for the "Session Information" section
3. Verify the "Create New Family" link is visible
4. The link should be styled as a button with class `refresh-btn`

### Step 3: Verify Create Family Flow
1. Click the "Create New Family" link
2. Verify you're taken to `/create-family`
3. Verify Step 1 form is displayed (email entry)
4. Enter a test email and submit
5. Verify you're redirected to Step 2 (code entry)
6. Enter "123456" as the verification code (debug server uses fixed code)
7. Verify you're redirected to Step 3 (password entry)
8. Enter matching passwords and submit
9. Verify you're redirected to `/dashboardV2`

### Step 4: Verify Cancel Functionality
1. Start the create family flow
2. Click the "Cancel" button
3. Verify you're redirected to `/dashboardV2`
4. Verify session data is cleared

### Step 5: Verify Tests Pass
1. Run: `py -3 -m pytest tests/test_create_family.py tests/test_crypto_utils.py tests/test_create_family_integration.py -v --timeout=30`
2. Verify all 58 tests pass

## Expected Results

| Check | Expected Result |
|-------|-----------------|
| Page title | "TimeLimit Dashboard v2 - v1.0.0" |
| Version badge | Visible in Dashboard Content heading |
| Create New Family link | Visible in Session Information section |
| Step 1 form | Email input field visible |
| Step 2 form | Verification code input field visible |
| Step 3 form | Password fields visible |
| Cancel button | Visible on all steps |
| All tests | 58 tests pass |

## Troubleshooting

### Button not visible
- Hard refresh browser (Ctrl+F5)
- Restart Docker container: `docker restart <container-name>`
- Check server logs for errors

### Flow not working
- Verify debug server is running on port 8080
- Check that the debug server accepts code "123456"
- Verify network connectivity between dashboardV2 and debug server

### Tests failing
- Run tests in dashboardV2 directory
- Verify all dependencies are installed
- Check for port conflicts