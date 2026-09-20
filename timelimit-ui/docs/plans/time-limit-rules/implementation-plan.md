# Time Limit Rules Implementation Plan

## Table of Contents

1. [Overview](#overview)
2. [Feature Description](#feature-description)
3. [API Endpoints](#api-endpoints)
4. [Database Schema](#database-schema)
5. [Days Bitmask](#days-bitmask)
6. [Time Format](#time-format)
7. [Rule Validation](#rule-validation)
8. [Sync Protocol](#sync-protocol)
9. [Frontend Implementation](#frontend-implementation)
10. [Testing](#testing)
11. [Implementation Status](#implementation-status)
12. [Future Enhancements](#future-enhancements)

---

## Overview

This document describes the implementation plan for time limit rules functionality in Dashboard V2. Time limit rules allow parents to set time restrictions for their children's device usage through the web dashboard.

### Key Features

- Create, read, update, and delete time limit rules
- Configure rules for specific users and categories
- Set days of the week and time ranges
- Sync rules to the TimeLimit server via CRDT protocol

---

## Feature Description

Time limit rules allow parents to set time restrictions for their children's device usage. Rules can specify:

- **User**: Which user the rule applies to
- **Category**: Which category the rule applies to
- **Days**: Days of the week the rule is active (bitmask 0-127)
- **Time Range**: Start and end time (HH:MM format)
- **Duration**: Time limit in minutes

### Rule Types

| Type | Description |
|------|-------------|
| 0 | TIME_LIMIT - Standard time limit rule |
| 1 | TIME_LIMIT_EXCEPTIONS - Exception to existing rules |

---

## API Endpoints

### GET /api/dashboard/time-limit-rules

Retrieve all time limit rules for the authenticated device.

**Response**:
```json
{
    "status": "ok",
    "count": 1,
    "rules": [
        {
            "id": "rule_abc123",
            "user_id": "user_456",
            "category_id": "cat_789",
            "rule": {
                "type": 0,
                "startTime": "18:00",
                "endTime": "21:00",
                "days": 127,
                "limitMinutes": 120
            }
        }
    ]
}
```

### POST /api/dashboard/time-limit-rules

Create a new time limit rule.

**Request**:
```json
{
    "userId": "user_456",
    "categoryId": "cat_789",
    "rule": {
        "type": 0,
        "startTime": "18:00",
        "endTime": "21:00",
        "days": 127,
        "limitMinutes": 120
    }
}
```

**Response**:
```json
{
    "status": "ok",
    "ruleId": "rule_abc123"
}
```

### PUT /api/dashboard/time-limit-rules/{ruleId}

Update an existing time limit rule.

**Request**:
```json
{
    "rule": {
        "startTime": "17:00",
        "endTime": "20:00",
        "limitMinutes": 90
    }
}
```

### DELETE /api/dashboard/time-limit-rules/{ruleId}

Delete a time limit rule.

**Response**:
```json
{
    "status": "ok"
}
```

---

## Database Schema

### time_limit_rules Table

```sql
CREATE TABLE time_limit_rules (
    id TEXT PRIMARY KEY,
    device_auth_token TEXT NOT NULL,
    user_id TEXT NOT NULL,
    category_id TEXT NOT NULL,
    rule_type INTEGER DEFAULT 0,
    start_time TEXT,
    end_time TEXT,
    days INTEGER DEFAULT 127,
    limit_minutes INTEGER DEFAULT 0,
    version TEXT,
    created_at TEXT NOT NULL,
    last_updated INTEGER,
    FOREIGN KEY (device_auth_token) REFERENCES families(device_auth_token),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (category_id) REFERENCES categories(id)
)
```

### Table Columns

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | Unique rule ID |
| `device_auth_token` | TEXT | Foreign key to families |
| `user_id` | TEXT | Foreign key to users |
| `category_id` | TEXT | Foreign key to categories |
| `rule_type` | INTEGER | Type of rule (0=TIME_LIMIT, 1=TIME_LIMIT_EXCEPTIONS) |
| `start_time` | TEXT | Start time (HH:MM) |
| `end_time` | TEXT | End time (HH:MM) |
| `days` | INTEGER | Days bitmask (0-127) |
| `limit_minutes` | INTEGER | Time limit in minutes |
| `version` | TEXT | Rule version |
| `created_at` | TEXT | Creation timestamp |
| `last_updated` | INTEGER | Last update timestamp |

---

## Days Bitmask

Days are represented as a bitmask (0-127):

| Bit | Day | Value |
|-----|-----|-------|
| 0 | Monday | 1 |
| 1 | Tuesday | 2 |
| 2 | Wednesday | 4 |
| 3 | Thursday | 8 |
| 4 | Friday | 16 |
| 5 | Saturday | 32 |
| 6 | Sunday | 64 |

### Examples

- `127` = Every day (1+2+4+8+16+32+64)
- `1` = Monday only
- `3` = Monday and Tuesday
- `62` = Tuesday through Saturday (2+4+8+16+32)
- `96` = Weekend only (32+64)

---

## Time Format

Times are in 24-hour format (HH:MM):

- Valid: `00:00` to `23:59`
- Validation: Must match regex `^([01][0-9]|2[0-3]):[0-5][0-9]$`

---

## Rule Validation

### Server-Side Validation

1. **User ID**: Must be present and valid
2. **Category ID**: Must be present and valid
3. **Start Time**: Must be valid HH:MM format
4. **End Time**: Must be valid HH:MM format
5. **Days**: Must be integer between 0 and 127
6. **Limit Minutes**: Must be non-negative integer

### Client-Side Validation

JavaScript validation in `dashboardV2.js`:

```javascript
// Time format validation
const time_pattern = /^([01][0-9]|2[0-3]):[0-5][0-9]$/;

// Days validation
if (!isinstance(days, int) || days < 0 || days > 127) {
    return error('Invalid days value. Must be an integer between 0 and 127');
}

// Limit minutes validation
if (!isinstance(limit_minutes, int) || limit_minutes < 0) {
    return error('Invalid limitMinutes. Must be a non-negative integer');
}
```

---

## Sync Protocol

Time limit rules are synced to the server using the CRDT protocol:

1. Generate unique rule ID
2. Save rule to local database
3. Get parent password second hash
4. Get next sequence number
5. Push to server via `add_time_limit_rule` API
6. Increment sequence number on success

### Sync Action Structure

```json
{
    "type": "AddTimeLimitRuleAction",
    "categoryId": "<category_id>",
    "userId": "<user_id>",
    "rule": {
        "type": 0,
        "startTime": "HH:MM",
        "endTime": "HH:MM",
        "days": 127,
        "limitMinutes": 120
    }
}
```

---

## Frontend Implementation

### JavaScript API Service

```javascript
const timeLimitRulesApi = {
    getRules: async function() {
        const response = await fetch('/api/dashboard/time-limit-rules');
        return response.json();
    },
    
    addRule: async function(ruleData) {
        const response = await fetch('/api/dashboard/time-limit-rules', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(ruleData)
        });
        return response.json();
    },
    
    updateRule: async function(ruleId, ruleData) {
        const response = await fetch(`/api/dashboard/time-limit-rules/${ruleId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(ruleData)
        });
        return response.json();
    },
    
    deleteRule: async function(ruleId) {
        const response = await fetch(`/api/dashboard/time-limit-rules/${ruleId}`, {
            method: 'DELETE'
        });
        return response.json();
    }
};
```

### UI Components

1. **Rules Table**: Displays all rules with columns for User, Category, Days, Time, Duration, Actions
2. **Rule Form Modal**: Form for adding/editing rules
3. **Day Selection**: Checkboxes for each day of the week
4. **Time Pickers**: Input fields for start and end times
5. **Duration Input**: Number input for limit minutes

### Days Display

```javascript
function formatDays(days) {
    const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    const selectedDays = [];
    
    for (let i = 0; i < 7; i++) {
        if (days & (1 << i)) {
            selectedDays.push(dayNames[i]);
        }
    }
    
    return selectedDays.length === 7 ? 'Every day' : selectedDays.join(', ');
}
```

---

## Testing

### Unit Tests

- Rule creation with valid data
- Rule creation with invalid time format
- Rule creation with invalid days bitmask
- Rule update
- Rule deletion
- Days formatting

### Integration Tests

- Full rule creation flow
- Rule sync with server
- Rule update and sync

---

## Implementation Status

| Task | Status | Notes |
|------|--------|-------|
| API Endpoints | ✅ Complete | All CRUD operations implemented |
| Database Schema | ✅ Complete | Table created and migrated |
| Frontend UI | ✅ Complete | Table, modal, and form implemented |
| Validation | ✅ Complete | Server and client-side validation |
| Sync Protocol | ✅ Complete | CRDT sync with sequence numbers |
| Tests | ✅ Complete | 1028 tests passing |

---

## Future Enhancements

1. **Rule Templates**: Pre-defined rule templates for common scenarios
2. **Rule Scheduling**: Schedule rules to be active at specific times
3. **Rule Categories**: Group rules by purpose (homework, games, etc.)
4. **Notifications**: Notify when time limit is reached
5. **Reports**: Generate usage reports