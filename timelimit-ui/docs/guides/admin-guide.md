# Admin Guide

## Table of Contents

1. [Administration Overview](#administration-overview)
2. [User Management](#user-management)
3. [Device Management](#device-management)
4. [Category Management](#category-management)
5. [Time Limit Rules](#time-limit-rules)
6. [Server Configuration](#server-configuration)
7. [Data Management](#data-management)
8. [Backup and Restore](#backup-and-restore)
9. [Password Management](#password-management)
10. [Audit Logging](#audit-logging)
11. [Troubleshooting](#troubleshooting)
12. [Security Best Practices](#security-best-practices)
13. [API Access](#api-access)
14. [Configuration](#configuration)
15. [Support](#support)

---

## Administration Overview

Dashboard V2 provides administrative capabilities for managing families, devices, and users. This guide covers all administrative functions available through the dashboard interface.

### Key Administrative Functions

- **User Management**: View and manage family users
- **Device Management**: Register, view, and remove devices
- **Time Limit Rules**: Configure time-based restrictions
- **Server Configuration**: Select and monitor server connections
- **Data Management**: Backup, restore, and clear local data
- **Security**: Password management and audit logging

---

## User Management

### Viewing Users

Users are displayed in the **Users** section of the dashboard:

| Column | Description |
|--------|-------------|
| Name | User's display name |
| Type | Parent or Child |
| Mail | User's email (if set) |
| Current Device | Device currently logged in |
| Time Zone | User's time zone |
| Limits Disabled | Whether limits are disabled |

### User Types

| Type | Description |
|------|-------------|
| `parent` | Parent account with full administrative privileges |
| `child` | Child account with time limits applied |

### User Actions

- **View**: See user details in the table
- **Sync**: Users are automatically synced from the server
- **Modify**: Changes must be made through the TimeLimit server API

---

## Device Management

### Viewing Devices

Devices are displayed in the **Devices** section:

| Column | Description |
|--------|-------------|
| Name | Device display name |
| Model | Device model |
| Current User | User currently using the device |
| Protection Level | Device protection level (0-3) |
| App Version | Current app version |
| Platform | Platform type and version |
| Signing Key | Encryption key status |

### Protection Levels

| Level | Description |
|-------|-------------|
| 0 | None |
| 1 | Simple Device Admin |
| 2 | Password Device Admin |
| 3 | Device Owner |

### Device Removal

To remove a device:

1. Ensure parent password is set
2. Go to Devices section
3. Click trash can icon on the device row
4. Enter password when prompted
5. Confirm removal

**Note**: You cannot remove the dashboard's own device.

### Adding Devices

Devices are added automatically when:
- A new family is created
- A user is added to the family
- A device syncs with the server

---

## Category Management

### Viewing Categories

Categories are managed through the TimeLimit server. The dashboard syncs category data automatically.

### Default Categories

- **Games** - Entertainment apps
- **Work/School** - Productivity apps
- **Social** - Social media apps
- **Utilities** - System and utility apps

### Category Actions

- **View**: See category details in the dashboard
- **Sync**: Categories are automatically synced from the server
- **Modify**: Changes must be made through the TimeLimit server API

---

## Time Limit Rules

### Rule Management

Time limit rules are displayed in the **Time Limit Rules** section:

| Column | Description |
|--------|-------------|
| User | User the rule applies to |
| Category | Category the rule applies to |
| Days | Days the rule is active |
| Time | Active time range |
| Duration | Time limit duration |
| Actions | Edit/Delete buttons |

### Creating Rules

1. Click **Add Rule**
2. Select user and category
3. Set days (checkboxes)
4. Set time range
5. Set duration in minutes
6. Click **Save**

### Editing Rules

1. Click the pencil icon (✏️) on the rule row
2. Modify the rule settings
3. Click **Save**

### Deleting Rules

1. Click the trash can icon (🗑️) on the rule row
2. Confirm deletion in the dialog

### Rule Days Bitmask

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

**Examples**:
- `127` = Every day
- `62` = Weekdays only (Tue-Fri)
- `96` = Weekend only (Sat+Sun)

---

## Server Configuration

### Server Selection

Dashboard V2 supports multiple server endpoints:

| Key | Server | URL |
|-----|--------|-----|
| `local` | Local development | http://192.168.68.30:8080 |
| `official` | Official TimeLimit server | https://api.timelimit.io |
| `debug` | Debug server | http://localhost:8080 |

To change server:
1. Click server dropdown in dashboard
2. Select desired server
3. Selection persists across restarts

### Server Checks

The dashboard performs periodic server checks:

- **Interval**: Configurable via scheduler
- **Purpose**: Verify server connectivity
- **Results**: Stored in `server_checks` table

View server check history in the dashboard or query the database.

---

## Data Management

### Database Location

Default location: `/data/timelimit_ui_storage.json`

### Database Tables

| Table | Purpose |
|-------|---------|
| `server_checks` | Server check history |
| `families` | Family account data |
| `devices` | Device registrations |
| `auth_tokens` | Authentication tokens |
| `users` | User data |
| `sync_state` | Sync version tracking |
| `categories` | TimeLimit categories |
| `connected_devices` | Real-time device tracking |
| `time_limit_rules` | Local time limit rules |

### Clearing Data

#### Clear Session

1. Click **Clear Session**
2. Session is cleared and you're logged out

#### Clear All Data

**Warning**: This deletes all local data.

1. Click **Clear All Data**
2. Confirm in dialog
3. All tables are cleared

#### Clear Server Checks

1. Click **Clear Server Checks**
2. Server check history is deleted

---

## Backup and Restore

### Creating a Backup

1. Click **Create Backup**
2. Backup file is created at `/data/auth_backup.json`
3. Contains device auth tokens and device IDs

### Restoring from Backup

1. Click **Restore Backup**
2. Data is restored from backup file
3. Dashboard reloads with restored session

### Clearing Backup

1. Click **Clear Backup**
2. Backup file is deleted

---

## Password Management

### Setting Parent Password

Required for device removal operations.

1. Go to **Set Parent Password** page
2. Enter password (min 8 characters)
3. Click **Save**

### Password Recovery

If you've lost access to your password:

1. Go to **Recover Parent Password**
2. Enter email
3. Verify code from email
4. Set new password

---

## Audit Logging

Dashboard V2 maintains audit logs for security events.

### Log Events

| Event | Description |
|-------|-------------|
| `add_user_request` | User addition initiated |
| `add_user_response` | User addition result |
| `login_as_parent_*` | Login as parent events |
| `family_creation` | Family creation events |

### Log Location

Logs are written to:
- Console: stdout
- File: `/data/logs/dashboard.log`

### Log Format

Structured JSON format:
```json
{
    "timestamp": "2024-01-15T10:30:00Z",
    "level": "INFO",
    "event": "event_type",
    "device_auth_token": "token",
    "request_id": "uuid",
    "server_url": "https://timeleap.org"
}
```

---

## Troubleshooting

### Common Issues

#### Device Removal Fails

**Symptoms**: "Parent password hash not set" error

**Solution**: Set parent password via `/set-parent-password`

#### Sync Fails

**Symptoms**: "Sync failed" message

**Solution**: 
1. Check server connection
2. Verify device auth token
3. Check network connectivity

#### Users Not Loading

**Symptoms**: Empty users table

**Solution**:
1. Trigger manual sync
2. Check server status
3. Verify authentication

#### Categories Not Loading

**Symptoms**: Empty categories table

**Solution**:
1. Trigger manual sync
2. Check server status

### Log Analysis

View logs:
```bash
tail -f /data/logs/dashboard.log
```

Search for errors:
```bash
grep -i error /data/logs/dashboard.log
```

### Database Inspection

Access database:
```bash
sqlite3 /data/timelimit_ui_storage.json
```

Query tables:
```sql
.tables
SELECT * FROM users;
SELECT * FROM devices;
```

---

## Security Best Practices

1. **Set a strong parent password** for device removal
2. **Use HTTPS** for server connections
3. **Regular backups** of auth tokens
4. **Monitor audit logs** for suspicious activity
5. **Keep software updated** for security patches

---

## API Access

### Internal API

Dashboard V2 provides internal API endpoints for management operations. See [API Reference](../api/api-reference.md) for details.

### External API

The dashboard proxies requests to the TimeLimit server API. All server API calls are logged.

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_HOST` | `0.0.0.0` | Server host |
| `FLASK_PORT` | `8099` | Server port |
| `FLASK_DEBUG` | `false` | Debug mode |
| `LOG_LEVEL` | `info` | Logging level |
| `DATABASE_PATH` | `/data/timelimit_ui_storage.json` | Database path |

### Configuration File

Configuration can be set via environment variables or configuration file.

---

## Support

For support:
1. Check the logs for error messages
2. Review this documentation
3. Contact TimeLimit support
4. Check GitHub issues