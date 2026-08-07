# Data Model Specifications

## Overview

This document specifies the data models used by the TimeLimit backend API. These models are exchanged between the TimeLimit Android app, the UI bridge server, and the backend server (`api.timelimit.io`). All models are derived from `context.md` and `context_android_app.md`.

## 1. ServerDataStatus

**Source**: `context_android_app.md` §3.5, §8.7

The server's response to `POST /sync/pull-status`. Contains the complete family state that the client needs to synchronize.

### Structure

| Field | Type | Description |
|-------|------|-------------|
| `devices` | `{version: str, data: [ServerDeviceData]}` | Full device list with version |
| `devices2` | `[ServerExtendedDeviceData]` | Extended device data (app lists, details) |
| `apps` | `[ServerInstalledAppsData]` | Installed apps per device |
| `rmCategories` | `[str]` | List of removed category IDs |
| `categoryBase` | `[ServerUpdatedCategoryBaseData]` | Category base data (time limits, etc.) |
| `categoryApp` | `[ServerUpdatedCategoryAssignedApps]` | Category app assignments |
| `usedTimes` | `[ServerUpdatedCategoryUsedTimes]` | Used time items per category |
| `rules` | `[ServerUpdatedTimeLimitRules]` | Time limit rules per category |
| `tasks` | `[ServerUpdatedCategoryTasks]` | Child tasks per category |
| `users` | `{version: str, data: [ServerUserData]}` | Full user list with version |
| `krq` | `[KeyRequest]` | Pending key requests from other devices |
| `kr` | `[KeyResponse]` | Key responses |
| `pings` | `[Ping]` | Ping/pong messages for primary device borrowing |
| `dh` | `{v: str, k: str}` | DH key for password encryption (version + base64 key) |
| `u2f` | `{v: str, d: [U2FData]}` | U2F data (version + key handles/public keys) |
| `fullVersion` | `int` | Premium expiration timestamp (0 = not premium) |
| `message` | `str` | Server message |
| `apiLevel` | `int` | Server API level (current max: 8) |

### Example JSON

```json
{
    "devices": {
        "version": "abc123",
        "data": [
            {
                "deviceId": "device-001",
                "name": "Parent Phone",
                "model": "Pixel 8",
                "addedAt": 1700000000000,
                "currentUserId": "user-001",
                "currentProtectionLevel": "full",
                "highestProtectionLevel": "full",
                "currentAppVersion": 226,
                "highestAppVersion": 226,
                "publicKey": "base64key...",
                "platformType": "android",
                "platformLevel": 36
            }
        ]
    },
    "devices2": [
        {
            "deviceId": "device-001",
            "appsBase": {"version": "v1", "data": "base64encrypted..."},
            "appsDiff": {"version": "v1", "data": "base64encrypted..."}
        }
    ],
    "apps": [
        {
            "deviceId": "device-001",
            "version": "v1",
            "apps": ["com.example.app1", "com.example.app2"]
        }
    ],
    "rmCategories": ["cat-removed-001"],
    "categoryBase": [
        {
            "categoryId": "cat-001",
            "childId": "user-002",
            "title": "Games",
            "blockedTimes": "0",
            "extraTime": 0,
            "extraTimeDay": 0,
            "tempBlocked": false,
            "tempBlockTime": 0,
            "version": "v1",
            "parentCategoryId": null,
            "blockAllNotifications": false,
            "timeWarnings": 0,
            "sort": 0,
            "networks": [],
            "flags": 0,
            "blockNotificationDelay": 0,
            "atw": [0, 0, 0, 0, 0, 0, 0]
        }
    ],
    "categoryApp": [
        {
            "categoryId": "cat-001",
            "apps": ["com.example.game1", "com.example.game2"],
            "version": "v1"
        }
    ],
    "usedTimes": [
        {
            "categoryId": "cat-001",
            "usedTime": 3600000,
            "date": "2024-01-15"
        }
    ],
    "rules": [
        {
            "categoryId": "cat-001",
            "day": 1,
            "startTime": 3600000,
            "endTime": 64800000,
            "maxTime": 7200000
        }
    ],
    "tasks": [
        {
            "categoryId": "cat-001",
            "taskId": "task-001",
            "title": "Finish homework",
            "description": "Complete math exercises",
            "completed": false
        }
    ],
    "users": {
        "version": "def456",
        "data": [
            {
                "id": "user-001",
                "name": "Parent",
                "password": "$2b$12$...",
                "secondPasswordSalt": "$2b$12$...",
                "type": "parent",
                "timeZone": "Europe/Amsterdam",
                "disableLimitsUntil": 0,
                "mail": "parent@example.com",
                "currentDevice": "device-001",
                "categoryForNotAssignedApps": null,
                "relaxPrimaryDevice": true,
                "flags": 0,
                "limitLoginCategory": null,
                "preBlockDuration": 0
            }
        ]
    },
    "krq": [],
    "kr": [],
    "pings": [],
    "dh": {"v": "v1", "k": "base64key..."},
    "u2f": {"v": "v1", "d": []},
    "fullVersion": 0,
    "message": "",
    "apiLevel": 8
}
```

## 2. ClientDataStatus

**Source**: `context_android_app.md` §3.5, §8.9

The client's sync state sent to the server in `POST /sync/pull-status`. Contains version numbers for each entity type, allowing the server to return only changed data.

### Structure

| Field | Type | Description |
|-------|------|-------------|
| `clientLevel` | `int` | Client protocol version (current: 7) |
| `devices` | `str` | Device list version |
| `users` | `str` | User list version |
| `apps` | `{deviceId: str}` | Per-device installed apps version |
| `devicesDetail` | `{deviceId: {baseVersion: str, diffVersion: str}}` | Per-device app base/diff versions (API level ≥ 4) |
| `categories` | `{categoryId: {baseVersion: str, assignedAppsVersion: str, timeLimitRulesVersion: str, usedTimeItemsVersion: str, taskListVersion: str}}` | Per-category version numbers |
| `kri` | `int` | Last processed key request server sequence |
| `kr` | `int` | Last processed key response server sequence |
| `dh` | `str` | DH key version |
| `u2f` | `str` | U2F data version |

### Example JSON

```json
{
    "clientLevel": 7,
    "devices": "abc123",
    "users": "def456",
    "apps": {
        "device-001": "v1"
    },
    "devicesDetail": {
        "device-001": {
            "baseVersion": "v1",
            "diffVersion": "v1"
        }
    },
    "categories": {
        "cat-001": {
            "baseVersion": "v1",
            "assignedAppsVersion": "v1",
            "timeLimitRulesVersion": "v1",
            "usedTimeItemsVersion": "v1",
            "taskListVersion": "v1"
        }
    },
    "kri": 0,
    "kr": 0,
    "dh": "v1",
    "u2f": "v1"
}
```

## 3. ServerUserData

**Source**: `context_android_app.md` §3.7, §8.7

User data within `ServerDataStatus.users.data[]`.

### Structure

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | UUID (client-generated) |
| `name` | `str` | Display name |
| `password` | `str` | bcrypt hash (empty if not set) |
| `secondPasswordSalt` | `str` | Salt for second password hash |
| `type` | `str` | `"parent"` or `"child"` |
| `timeZone` | `str` | IANA timezone ID |
| `disableLimitsUntil` | `int` | Timestamp (0 = limits enabled) |
| `mail` | `str` | Email address (for parent accounts) |
| `currentDevice` | `str` | ID of current/primary device |
| `categoryForNotAssignedApps` | `str` | Category for apps not assigned to any category |
| `relaxPrimaryDevice` | `bool` | If true, limits relaxed when connected and premium |
| `flags` | `long` | Bitmask (RESTRICT_VIEWING_TO_PARENTS, ALLOW_SELF_LIMIT_ADD) |
| `limitLoginCategory` | `str` | Category ID for login limits (or null) |
| `preBlockDuration` | `long` | Pre-block duration in milliseconds |

### Example JSON

```json
{
    "id": "user-001",
    "name": "Parent",
    "password": "$2b$12$abcdefghijklmnopqrstuvwxyz0123456789",
    "secondPasswordSalt": "$2b$12$abcdefghijklmnopqrstuvwxyz0123456789",
    "type": "parent",
    "timeZone": "Europe/Amsterdam",
    "disableLimitsUntil": 0,
    "mail": "parent@example.com",
    "currentDevice": "device-001",
    "categoryForNotAssignedApps": null,
    "relaxPrimaryDevice": true,
    "flags": 0,
    "limitLoginCategory": null,
    "preBlockDuration": 0
}
```

## 4. ServerDeviceData

**Source**: `context_android_app.md` §3.7, §8.7

Device data within `ServerDataStatus.devices.data[]`.

### Structure

| Field | Type | Description |
|-------|------|-------------|
| `deviceId` | `str` | Unique device identifier |
| `name` | `str` | Human-readable device name |
| `model` | `str` | Device model |
| `addedAt` | `int` | Timestamp when device was added |
| `currentUserId` | `str` | ID of current user on this device |
| `currentProtectionLevel` | `str` | Current protection level |
| `highestProtectionLevel` | `str` | Highest achieved protection level |
| `currentAppVersion` | `int` | Current app version code |
| `highestAppVersion` | `int` | Highest app version code |
| `publicKey` | `str` | Curve25519 public key (base64, or null) |
| `platformType` | `str` | Platform type (e.g., "android", or null) |
| `platformLevel` | `int` | Platform API level (or null) |

### Example JSON

```json
{
    "deviceId": "device-001",
    "name": "Parent Phone",
    "model": "Pixel 8",
    "addedAt": 1700000000000,
    "currentUserId": "user-001",
    "currentProtectionLevel": "full",
    "highestProtectionLevel": "full",
    "currentAppVersion": 226,
    "highestAppVersion": 226,
    "publicKey": "base64curve25519key...",
    "platformType": "android",
    "platformLevel": 36
}
```

## 5. ServerUpdatedCategoryBaseData

**Source**: `context_android_app.md` §3.7, §8.7

Category base data within `ServerDataStatus.categoryBase[]`.

### Structure

| Field | Type | Description |
|-------|------|-------------|
| `categoryId` | `str` | Unique category identifier |
| `childId` | `str` | User ID this category belongs to |
| `title` | `str` | Category title |
| `blockedTimes` | `str` | Bitmask string for blocked times |
| `extraTime` | `int` | Extra time in milliseconds |
| `extraTimeDay` | `int` | Extra time day |
| `tempBlocked` | `bool` | If category is temporarily blocked |
| `tempBlockTime` | `int` | Temporary block expiration timestamp |
| `version` | `str` | Base data version |
| `parentCategoryId` | `str` | Parent category ID (or null) |
| `blockAllNotifications` | `bool` | If true, block all notifications |
| `timeWarnings` | `int` | Time warning settings |
| `sort` | `int` | Sort order |
| `networks` | `[str]` | Network restrictions |
| `flags` | `long` | Category flags bitmask |
| `blockNotificationDelay` | `long` | Notification block delay |
| `atw` | `[int]` | Allowed time windows (7-element array) |

### Example JSON

```json
{
    "categoryId": "cat-001",
    "childId": "user-002",
    "title": "Games",
    "blockedTimes": "0",
    "extraTime": 0,
    "extraTimeDay": 0,
    "tempBlocked": false,
    "tempBlockTime": 0,
    "version": "v1",
    "parentCategoryId": null,
    "blockAllNotifications": false,
    "timeWarnings": 0,
    "sort": 0,
    "networks": [],
    "flags": 0,
    "blockNotificationDelay": 0,
    "atw": [0, 0, 0, 0, 0, 0, 0]
}
```

## 6. ActionUploadItem

**Source**: `context_android_app.md` §3.5, §8.11

An action uploaded to the server via `POST /sync/push-actions`.

### Structure

| Field | Type | Description |
|-------|------|-------------|
| `encodedAction` | `str` | JSON string of the action |
| `sequenceNumber` | `long` | Unique sequence number (prevents duplicates) |
| `integrity` | `str` | Integrity hash (HMAC-SHA256: `"password:" + base64(hmac)`) |
| `type` | `str` | Action type string (e.g., `"AddCategoryAppAction"`) |
| `userId` | `str` | User ID associated with the action |

### Example JSON

```json
{
    "encodedAction": "{\"type\":\"AddCategoryAppAction\",\"categoryId\":\"cat-001\",\"app\":\"com.example.game\",\"userId\":\"user-002\"}",
    "sequenceNumber": 42,
    "integrity": "password:base64hmac...",
    "type": "AddCategoryAppAction",
    "userId": "user-002"
}
```

### Action Hierarchy

Actions are organized in a sealed class hierarchy:

```
Action (sealed)
├── AppLogicAction (sealed) — client-generated actions
│   ├── AddUsedTimeActionVersion2
│   ├── SendKeyRequestAction
│   ├── ReplyToKeyRequestAction
│   ├── FinishKeyRequestAction
│   ├── PingAction
│   ├── UploadDevicePublicKeyAction
│   ├── AddAppAction
│   ├── RemoveAppAction
│   ├── AddCategoryAction
│   ├── UpdateCategoryAction
│   ├── RemoveCategoryAction
│   ├── AddCategoryAppAction
│   ├── RemoveCategoryAppAction
│   ├── AddUsedTimeAction
│   ├── AddTimeLimitRuleAction
│   ├── RemoveTimeLimitRuleAction
│   ├── AddChildTaskAction
│   ├── RemoveChildTaskAction
│   ├── AddTemporarilyAllowedAppAction
│   ├── RemoveTemporarilyAllowedAppAction
│   ├── UpdateUserAction
│   ├── RemoveUserAction
│   ├── UpdateDeviceAction
│   ├── AddDeviceAction
│   ├── RemoveDeviceAction
│   ├── UpdatePrimaryDeviceAction
│   ├── SetUserCurrentDeviceAction
│   ├── UpdateCategoryUsedTimeAction
│   └── ... (many more)
├── ParentAction (sealed) — parent-initiated actions
└── ChildAction (sealed) — child-initiated actions
```

## 7. ParentPassword

**Source**: `context_android_app.md` §3.6, §8.10

Parent password structure sent in `POST /parent/create-family`.

### Structure

| Field | Type | Description |
|-------|------|-------------|
| `hash` | `str` | bcrypt hash of password |
| `secondHash` | `str` | bcrypt hash with second salt, or DH-encrypted |
| `secondSalt` | `str` | Salt for second hash |
| `encrypted` | `bool` | If true, secondHash is DH-encrypted |

### Example JSON

```json
{
    "hash": "$2b$12$abcdefghijklmnopqrstuvwxyz0123456789",
    "secondHash": "$2b$12$abcdefghijklmnopqrstuvwxyz0123456789",
    "secondSalt": "$2b$12$abcdefghijklmnopqrstuvwxyz0123456789",
    "encrypted": false
}
```

### Encryption Flow

When DH key is available:
1. `secondHash` is encrypted via DH handshake (ECDH secp256r1)
2. AAD for encryption: `"ParentPassword:<hash>:<secondSalt>"`
3. Output format: `base64(iv + encryptedData) + "." + base64(ownPublicKey) + "." + keyVersion`

## 8. ServerInstalledAppsData

**Source**: `context_android_app.md` §8.7

Installed apps per device within `ServerDataStatus.apps[]`.

### Structure

| Field | Type | Description |
|-------|------|-------------|
| `deviceId` | `str` | Device identifier |
| `version` | `str` | Installed apps version |
| `apps` | `[str]` | List of installed app package names |

## 9. ServerUpdatedCategoryAssignedApps

**Source**: `context_android_app.md` §8.7

Category app assignments within `ServerDataStatus.categoryApp[]`.

### Structure

| Field | Type | Description |
|-------|------|-------------|
| `categoryId` | `str` | Category identifier |
| `apps` | `[str]` | List of app package names assigned to this category |
| `version` | `str` | Assigned apps version |

## 10. ServerUpdatedCategoryUsedTimes

**Source**: `context_android_app.md` §8.7

Used time items within `ServerDataStatus.usedTimes[]`.

### Structure

| Field | Type | Description |
|-------|------|-------------|
| `categoryId` | `str` | Category identifier |
| `usedTime` | `int` | Used time in milliseconds |
| `date` | `str` | Date string (e.g., "2024-01-15") |

## 11. ServerUpdatedTimeLimitRules

**Source**: `context_android_app.md` §8.7

Time limit rules within `ServerDataStatus.rules[]`.

### Structure

| Field | Type | Description |
|-------|------|-------------|
| `categoryId` | `str` | Category identifier |
| `day` | `int` | Day of week (0-6, 0=Sunday) |
| `startTime` | `int` | Start time in milliseconds |
| `endTime` | `int` | End time in milliseconds |
| `maxTime` | `int` | Maximum allowed time in milliseconds |

## 12. ServerUpdatedCategoryTasks

**Source**: `context_android_app.md` §8.7

Child tasks within `ServerDataStatus.tasks[]`.

### Structure

| Field | Type | Description |
|-------|------|-------------|
| `categoryId` | `str` | Category identifier |
| `taskId` | `str` | Task identifier |
| `title` | `str` | Task title |
| `description` | `str` | Task description |
| `completed` | `bool` | If task is completed |

## 13. ServerExtendedDeviceData

**Source**: `context_android_app.md` §8.7

Extended device data within `ServerDataStatus.devices2[]`.

### Structure

| Field | Type | Description |
|-------|------|-------------|
| `deviceId` | `str` | Device identifier |
| `appsBase` | `ServerCryptContainer` | Encrypted app list (base) |
| `appsDiff` | `ServerCryptContainer` | Encrypted app list (diff) |

## 14. ServerCryptContainer

**Source**: `context_android_app.md` §8.7

Encrypted data container for app lists.

### Structure

| Field | Type | Description |
|-------|------|-------------|
| `version` | `str` | Crypt container version |
| `data` | `str` | Base64 encoded encrypted data |

## 15. ServerDhKey

**Source**: `context_android_app.md` §8.7

DH key for password encryption within `ServerDataStatus.dh`.

### Structure

| Field | Type | Description |
|-------|------|-------------|
| `v` | `str` | Key version string |
| `k` | `str` | Base64 encoded EC public key (secp256r1) |

## 16. ServerU2fData

**Source**: `context_android_app.md` §8.7

U2F data within `ServerDataStatus.u2f`.

### Structure

| Field | Type | Description |
|-------|------|-------------|
| `v` | `str` | U2F data version |
| `d` | `[U2FEntry]` | List of U2F key handles and public keys |

## 17. Ping

**Source**: `context_android_app.md` §8.7

Ping/pong messages for primary device borrowing within `ServerDataStatus.pings[]`.

### Structure

| Field | Type | Description |
|-------|------|-------------|
| `deviceId` | `str` | Device that sent the ping |
| `token` | `str` | Ping token |
| `timestamp` | `int` | Ping timestamp |

## 18. KeyRequest

**Source**: `context_android_app.md` §3.6

Pending key requests within `ServerDataStatus.krq[]`.

### Structure

| Field | Type | Description |
|-------|------|-------------|
| `deviceId` | `str` | Requesting device ID |
| `tempKey` | `str` | Temporary Curve25519 key |
| `signature` | `str` | Signature of the request |
| `categoryId` | `str` | Category ID for the key request |
| `type` | `str` | Key request type |
| `sequenceNumber` | `long` | Server sequence number |

## 19. KeyResponse

**Source**: `context_android_app.md` §3.6

Key responses within `ServerDataStatus.kr[]`.

### Structure

| Field | Type | Description |
|-------|------|-------------|
| `deviceId` | `str` | Responding device ID |
| `tempKey` | `str` | Temporary Curve25519 key |
| `encryptedKey` | `str` | Encrypted generation key |
| `signature` | `str` | Signature of the response |
| `sequenceNumber` | `long` | Server sequence number |

## 20. ActionUploadResponse

**Source**: `context_android_app.md` §8.11

Response to `POST /sync/push-actions`.

### Structure

| Field | Type | Description |
|-------|------|-------------|
| `shouldDoFullSync` | `bool` | If true, client should wipe version numbers and do a full sync |

### Example JSON

```json
{
    "shouldDoFullSync": false
}
```

## 21. Auth Response Models

**Source**: `context_android_app.md` §8.4–8.6

### SendMailLoginCode Response

| Field | Type | Description |
|-------|------|-------------|
| `mailLoginToken` | `str` | Token for the next step |
| `mailServerBlacklisted` | `bool` | If true, mail server is blacklisted |
| `mailAddressNotWhitelisted` | `bool` | If true, email not whitelisted |
| `blockedForIntegrityReasons` | `bool` | If true, blocked for integrity |
| `mailServerBlacklistedTemporarily` | `bool` | If true, temporarily blacklisted |

### SignInByMailCode Response

| Field | Type | Description |
|-------|------|-------------|
| `mailAuthToken` | `str` | Authentication token for mail-based operations |

### GetStatusByMailAddress Response

| Field | Type | Description |
|-------|------|-------------|
| `mail` | `str` | Email address |
| `status` | `str` | `"with family"` or `"without family"` |
| `canCreateFamily` | `bool` | If user can create a family |
| `alwaysPro` | `bool` | If user always has premium |

### CreateFamily / SignInIntoFamily Response

| Field | Type | Description |
|-------|------|-------------|
| `deviceAuthToken` | `str` | Device authentication token |
| `ownDeviceId` | `str` | This device's ID |
| `data` | `ServerDataStatus` | Initial server data (or null) |

### CreateAddDeviceToken Response

| Field | Type | Description |
|-------|------|-------------|
| `token` | `str` | Add-device token string |
| `deviceId` | `str` | Parent device ID |

### AddDevice Response

| Field | Type | Description |
|-------|------|-------------|
| `deviceAuthToken` | `str` | New device auth token |
| `ownDeviceId` | `str` | New device's ID |
| `data` | `ServerDataStatus` | Initial server data (or null) |

### Purchase Response

| Field | Type | Description |
|-------|------|-------------|
| `canDoPurchase` | `bool` | If purchase is allowed |
| `status` | `str` | `"ok"` |
| `fullVersionUntil` | `int` | Premium expiration timestamp |

### Identity Token Response

| Field | Type | Description |
|-------|------|-------------|
| `identityToken` | `str` | Identity token for purchases |

### RecoverParentPassword Response

| Field | Type | Description |
|-------|------|-------------|
| `status` | `str` | `"ok"` |

### RemoveDevice Response

| Field | Type | Description |
|-------|------|-------------|
| `status` | `str` | `"ok"` |

### LinkMailAddress Response

| Field | Type | Description |
|-------|------|-------------|
| `status` | `str` | `"ok"` |

### UpdatePrimaryDevice Response

| Field | Type | Description |
|-------|------|-------------|
| `status` | `str` | `"ok"` |

### LogoutAtPrimaryDevice Response

| Field | Type | Description |
|-------|------|-------------|
| `status` | `str` | `"ok"` |

### ReportRemoved Response

| Field | Type | Description |
|-------|------|-------------|
| `status` | `str` | `"ok"` |

### IsDeviceRemoved Response

| Field | Type | Description |
|-------|------|-------------|
| `isDeviceRemoved` | `bool` | If device was removed |

### DeleteAccount Response

| Field | Type | Description |
|-------|------|-------------|
| `status` | `str` | `"ok"` |
