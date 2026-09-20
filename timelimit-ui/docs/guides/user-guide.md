# User Guide

## Table of Contents

1. [Getting Started](#getting-started)
2. [Creating a Family](#creating-a-family)
3. [Logging In as Parent](#logging-in-as-parent)
4. [Dashboard Overview](#dashboard-overview)
5. [Time Limit Rules](#time-limit-rules)
6. [Adding a User to Family](#adding-a-user-to-family)
7. [Device Management](#device-management)
8. [Sync Operations](#sync-operations)
9. [Backup and Restore](#backup-and-restore)
10. [Session Management](#session-management)
11. [Server Selection](#server-selection)
12. [Troubleshooting](#troubleshooting)
13. [Keyboard Shortcuts](#keyboard-shortcuts)
14. [Accessibility](#accessibility)

---

## Getting Started

### Accessing the Dashboard

1. Open your web browser
2. Navigate to `http://localhost:8099` (or your configured host:port)
3. You'll see the landing page with two options:
   - **Create Family** - For new users
   - **Login as Parent** - For existing families

### Prerequisites

- A web browser (Chrome, Firefox, Edge, Safari)
- Internet connection (for initial setup)
- Valid email address
- 3-word verification code from email

---

## Creating a Family

### Step 1: Enter Email

1. Click **Create Family**
2. Enter your email address
3. Click **Send Verification Code**
4. Check your email for the verification code

### Step 2: Verify Code

1. Enter the 3-word verification code from your email
2. Click **Verify Code**
3. You'll be prompted to set your password

### Step 3: Set Password

1. Enter a password (minimum 8 characters)
2. Enter the password again to confirm
3. Enter your name and device information
4. Click **Create Family**

### Step 4: Dashboard Access

After successful family creation, you'll be redirected to the dashboard.

---

## Logging In as Parent

### Step 1: Enter Email

1. Click **Login as Parent**
2. Enter your email address
3. Click **Send Verification Code**

### Step 2: Verify Code

1. Enter the 3-word verification code
2. Click **Verify Code**

### Step 3: Enter Device Info

1. Enter your device name
2. Enter your device model
3. Click **Sign In**

### Step 4: Set Password (Optional)

If you want to enable device removal:
1. Enter your password
2. Click **Save Password**

---

## Dashboard Overview

The dashboard displays four main sections:

### 1. Session Overview

Shows your current authentication status:
- Server URL
- Device Auth Token
- Own Device ID
- Parent Password Hash status

### 2. Users

Lists all users in your family:
- User name
- User type (Parent/Child)
- Email
- Current device
- Time zone
- Limits disabled status

### 3. Devices

Lists all devices in your family:
- Device name
- Device model
- Current user
- Protection level
- App version
- Platform info
- Signing key status

### 4. Connected Devices

Shows devices currently connected to the server:
- Device name
- Last seen time

---

## Time Limit Rules

### Viewing Rules

1. Navigate to the **Time Limit Rules** section
2. View all configured rules in the table

### Adding a Rule

1. Click **Add Rule**
2. Select user and category
3. Set days (checkboxes for each day)
4. Set time range (start and end)
5. Set duration (minutes)
6. Click **Save**

### Editing a Rule

1. Click the pencil icon (✏️) on the rule row
2. Modify the rule settings
3. Click **Save**

### Deleting a Rule

1. Click the trash can icon (🗑️) on the rule row
2. Confirm deletion in the dialog

### Rule Types

| Type | Description |
|------|-------------|
| TIME_LIMIT | Standard time limit rule |
| TIME_LIMIT_EXCEPTIONS | Exception to existing rules |

### Days Bitmask

Days are represented as a bitmask:

| Day | Bit | Value |
|-----|-----|-------|
| Monday | 0 | 1 |
| Tuesday | 1 | 2 |
| Wednesday | 2 | 4 |
| Thursday | 3 | 8 |
| Friday | 4 | 16 |
| Saturday | 5 | 32 |
| Sunday | 6 | 64 |

**Examples:**
- `127` = Every day
- `62` = Weekdays only (Tue-Fri)
- `96` = Weekend only (Sat+Sun)

---

## Adding a User to Family

### Prerequisites

- Parent password must be set
- You must be logged in as parent

### Steps

1. Click **Add User** button
2. Enter the child's name
3. Optionally enter device name and model
4. Click **Add**
5. Share the device auth token with the child

### Device Setup for Child

On the child's device:
1. Open Dashboard V2
2. Click **Login as Parent**
3. Enter the device auth token when prompted
4. The child is now added to the family

---

## Device Management

### Removing a Device

**Prerequisites**: Parent password must be set.

1. Go to the **Devices** section
2. Find the device to remove
3. Click the trash can icon (🗑️)
4. Enter your password when prompted
5. Confirm removal

**Note**: You cannot remove your own device (the dashboard device).

### Setting Parent Password

1. Go to **Set Parent Password** page
2. Enter your password
3. Click **Save**

This enables device removal functionality.

### Protection Levels

| Level | Description |
|-------|-------------|
| 0 | None |
| 1 | Simple Device Admin |
| 2 | Password Device Admin |
| 3 | Device Owner |

---

## Sync Operations

### Manual Sync

1. Click the **Sync** button
2. Wait for sync to complete
3. Check for success message

### Automatic Sync

The dashboard automatically syncs:
- After family creation
- After login
- When manually triggered

### Sync Status

View sync status in the session overview:
- Last sync timestamp
- Sync success/failure status
- Pending changes count

---

## Backup and Restore

### Creating a Backup

1. Click **Create Backup**
2. Wait for success message
3. Backup file is created locally

### Restoring from Backup

1. Click **Restore Backup**
2. Wait for success message
3. Dashboard will reload with restored data

### Clearing Backup

1. Click **Clear Backup**
2. Confirm action
3. Backup file is deleted

---

## Session Management

### Clearing Session

1. Click **Clear Session**
2. Confirm action
3. You'll be logged out

### Clearing All Data

**Warning**: This will delete all local data.

1. Click **Clear All Data**
2. Confirm action in the dialog
3. All data is deleted and you're logged out

---

## Server Selection

### Changing Server

1. Click the server dropdown
2. Select a different server:
   - **Local** - Local development server
   - **Official** - Official TimeLimit server
   - **Debug** - Debug server

3. The server selection persists across restarts

### Server URLs

| Server | URL |
|--------|-----|
| Local | http://192.168.68.30:8080 |
| Official | https://api.timelimit.io |
| Debug | http://localhost:8080 |

---

## Troubleshooting

### Common Issues

#### "Not Authenticated"

- Solution: Log in or create a family

#### "Family Not Found"

- Solution: Verify your email and try logging in again

#### "Device Removal Failed"

- Solution: Set your parent password first

#### "Sync Failed"

- Solution: Check server connection and try again

#### "Password Too Short"

- Solution: Use a password with at least 8 characters

#### "Invalid Verification Code"

- Solution: Check your email for the correct 3-word code

#### "Server Connection Failed"

- Solution: Check your network connection and server URL

### Getting Help

1. Check the logs in `/data/logs/dashboard.log`
2. Review the audit log for recent actions
3. Contact support if issues persist

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Escape` | Close modal dialogs |
| `Ctrl/Cmd + R` | Refresh page |
| `Tab` | Navigate between form fields |

---

## Accessibility

The dashboard supports:
- Keyboard navigation
- Screen reader compatibility
- High contrast mode (via browser settings)

### Accessibility Features

- Semantic HTML5 elements
- Proper ARIA attributes
- Focus indicators for keyboard navigation
- Sufficient color contrast
- Resizable text support