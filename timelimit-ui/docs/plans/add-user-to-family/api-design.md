# Add User to Family - API Design

## Overview

The "Add User to Family" feature allows parents to add new users (children) to their family directly from the dashboard.

## API Endpoint

### POST /api/dashboard/users/add

Creates a new user and device in the family.

**Authentication Required**: Yes (device_auth_token in session)

**Request Body**:
```json
{
    "name": "Child Name",
    "deviceName": "Child's Device Name",
    "deviceModel": "Device Model"
}
```

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | Child's display name |
| `deviceName` | string | No | Name for the child's device |
| `deviceModel` | string | No | Model of the child's device |

**Response (Success)**:
```json
{
    "status": "ok",
    "userId": "user_123456",
    "deviceAuthToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "ownDeviceId": "device_123456"
}
```

**Response (Error)**:
```json
{
    "status": "error",
    "error": "Error message",
    "error_code": "error_code"
}
```

## Implementation Flow

```
1. Validate request
   ├── Check authentication
   ├── Validate user name
   └── Check parent password hash

2. Get parent user ID
   └── Query database by device_auth_token

3. Create add device token
   └── POST /api/parent/create-add-device-token

4. Add device
   └── POST /api/child/add-device

5. Sync to get user
   └── POST /api/sync/pull

6. Save users to database
   └── INSERT INTO users

7. Log audit events
   └── log_add_user_request
   └── log_add_user_response
```

## Error Handling

| Error | Condition | Response |
|-------|-----------|----------|
| `unauthorized` | Not authenticated | 401 |
| `validation` | Missing user name | 400 |
| `validation` | Missing parent password hash | 400 |
| `server_error` | Parent user ID not found | 500 |
| `server_error` | Token creation failed | 500 |
| `server_error` | Device addition failed | 500 |
| `server_error` | Sync failed | 500 |

## Audit Logging

### Request Log

```json
{
    "event_type": "add_user_request",
    "device_auth_token": "token",
    "parent_user_id": "user_id",
    "user_name": "Child Name",
    "device_name": "Device Name",
    "device_model": "Device Model",
    "request_id": "uuid",
    "server_url": "https://timeleap.org"
}
```

### Response Log

```json
{
    "event_type": "add_user_response",
    "device_auth_token": "token",
    "parent_user_id": "user_id",
    "user_id": "user_id",
    "child_device_auth_token": "token",
    "own_device_id": "device_id",
    "request_id": "uuid",
    "success": true,
    "status_code": 200
}
```

## Security Considerations

1. **Parent Password Required**: The parent must have set their password hash for device removal operations.

2. **Device Auth Token**: Used as the primary authentication mechanism, matching the Android app's approach.

3. **Audit Logging**: All add user operations are logged for security auditing.

4. **Input Validation**: User name is required and validated.

## Frontend Integration

### JavaScript API

```javascript
const response = await fetch('/api/dashboard/users/add', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        name: userName,
        deviceName: deviceName,
        deviceModel: deviceModel
    })
});

const data = await response.json();

if (data.status === 'ok') {
    // Success
    console.log('User added:', data.userId);
} else {
    // Error
    console.error('Failed to add user:', data.error);
}
```

### UI Flow

1. User clicks "Add User" button
2. Modal opens with form
3. User enters user name (required)
4. User enters device name (optional)
5. User enters device model (optional)
6. User clicks "Add"
7. Loading state shown
8. Success/error message displayed
9. Users table refreshed