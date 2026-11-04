# TimeLimit Android — Architecture & Design Overview
This document contains the architecture and desing of the original android app


> **Project**: TimeLimit (GPL v3) — Android app for setting time limits on device usage
> **Language**: Kotlin (JVM 21) | **Min SDK**: 26 | **Target SDK**: 36 | **Compile SDK**: 36
> **Version**: 7.4.0 (code 226) | **Database**: Room v50

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    UI Layer                              │
│  Activities, Fragments, Compose, Widgets, Dialogs        │
├─────────────────────────────────────────────────────────┤
│                  Logic Layer                             │
│  AppLogic (central coordinator) + ~30 logic classes      │
├─────────────────────────────────────────────────────────┤
│                  Data Layer                              │
│  Room Database (22 entities, DAOs, LiveData)             │
├─────────────────────────────────────────────────────────┤
│                  Sync Layer                              │
│  HTTP API (OkHttp) + WebSocket (Socket.IO) + Action Sync │
├─────────────────────────────────────────────────────────┤
│                  Crypto Layer                            │
│  Curve25519, AES-GCM, ECDH, bcrypt                     │
├─────────────────────────────────────────────────────────┤
│           Platform Integration (Android)                 │
│  DeviceAdmin, Accessibility, NotificationListener, etc.  │
└─────────────────────────────────────────────────────────┘
```

### Central Coordinator: `AppLogic`

`AppLogic` ([app/src/main/java/io/timelimit/android/logic/AppLogic.kt:33](app/src/main/java/io/timelimit/android/logic/AppLogic.kt)) is the central dependency injection hub. It holds references to:

- `platformIntegration` — Android platform integration
- `timeApi` — time source abstraction
- `database` — Room database
- `serverLogic` — server URL and auth token management
- `syncUtil` — sync orchestration
- `websocket` — WebSocket connection management
- `serverApiLevelLogic` — server API level tracking
- `appSetupLogic` — device setup/reset
- `currentDeviceLogic` — primary device / borrow logic
- `fullVersion` — premium feature gating
- `syncAppsLogic` — installed app sync
- `suspendAppsLogic`, `annoyLogic`, `backgroundTaskLogic`, etc.

Initialized via `AndroidAppLogic` ([app/src/main/java/io/timelimit/android/logic/AndroidAppLogic.kt:33](app/src/main/java/io/timelimit/android/logic/AndroidAppLogic.kt)), which is a singleton that creates the `AppLogic` on the main thread and restores database backups asynchronously.

---

## 2. Build System & Flavors

### Gradle Configuration

- **Plugins**: Android Application, Kotlin Android, Kotlin Parcelize, Navigation SafeArgs, Kotlin KAPT, Square Wire (protobuf), Compose
- **Dependencies**: OkHttp 5.3.2, Socket.IO 2.1.2, Room 2.8.4, WorkManager 2.11.1, Paging 3.3.6, jBCrypt 0.4, Curve25519 (WhisperSystems) 0.5.0, ZXing 3.5.4, Apache Commons Text 1.15.0

### Product Flavors (3 dimensions)

| Dimension | Flavors | Description |
|-----------|---------|-------------|
| `server` | `developmentServer`, `productionServer`, `noServer` | Server connection mode |
| `api` | `googleApi`, `noGoogleApi` | Google Play Services vs AOSP |
| `channel` | `storeVersion`, `directVersion` | Play Store vs direct download |

**Variant filtering**: storeVersion+noGoogleApi, directVersion+googleApi, and noServer+googleApi are excluded.

### Build Config Fields

| Field | Value |
|-------|-------|
| `serverUrl` | `https://api.timelimit.io` (production) / `http://10.0.2.2:8080` (dev) |
| `serverDomain` | `api.timelimit.io` |
| `backupServerDomain` | `api.timelimitapp.de` |
| `updateServer` | `https://update.timelimit.io/update.json` |
| `updateServerDomain` | `update.timelimit.io` |
| `updateServerBuildsCertificate` | SHA256 cert pin for update server |
| `googlePlayKey` | RSA public key for Google Play billing verification |
| `backdoorPublicKey` | RSA public key for backdoor authentication |
| `minimumRecommendServerVersion` | 5 |
| `hasServer` | `true` (production/dev) / `false` (noServer) |

---

## 3. Connection & User Handling (Primary Focus)

### 3.1 Server Configuration

Server configuration is managed by `ServerLogic` ([app/src/main/java/io/timelimit/android/logic/ServerLogic.kt:23](app/src/main/java/io/timelimit/android/logic/ServerLogic.kt)):

- **Server URL**: Resolved from `BuildConfig.serverUrl` or a custom URL stored in `ConfigurationItem.CustomServerUrl`
- **Device Auth Token**: Stored in `ConfigurationItem.DeviceAuthToken` — the primary authentication credential
- **Server API Level**: Stored in `ConfigurationItemType.ServerApiLevel` — tracks server capabilities (current max: 8, `EXPIRE_RULES = 8`)
- **ServerConfig**: Data class combining `customServerUrl`, `deviceAuthToken`, `isAppEnabled`, and a lazily-created `ServerApi` instance

The `ServerApiLevelLogic` ([app/src/main/java/io/timelimit/android/logic/ServerApiLevelLogic.kt:25](app/src/main/java/io/timelimit/android/logic/ServerApiLevelLogic.kt)) tracks the server API level as a LiveData, switching between `Online(serverLevel)` and `Offline` states.

### 3.2 HTTP API

The `ServerApi` interface ([app/src/main/java/io/timelimit/android/sync/network/api/Api.kt:20](app/src/main/java/io/timelimit/android/sync/network/api/Api.kt)) defines 21 methods. The `HttpServerApi` ([app/src/main/java/io/timelimit/android/sync/network/api/HttpServerApi.kt:53](app/src/main/java/io/timelimit/android/sync/network/api/HttpServerApi.kt)) implements them using OkHttp.

#### HTTP Client Configuration

`HttpClient.kt` ([app/src/main/java/io/timelimit/android/sync/network/api/HttpClient.kt:25](app/src/main/java/io/timelimit/android/sync/network/api/HttpClient.kt)) creates a singleton `OkHttpClient` with:

- **Certificate Pinning**: Via `SslConfig.certificatePinner` (flavor-dependent)
- **Custom Trust Manager**: Via `SslConfig.certificates` (flavor-dependent)
- **Custom DNS**: Via `Dns.instance` (flavor-dependent)
- **Logging**: HTTP headers logged in debug mode

#### Request Format

- **Content-Type**: `application/json; charset=utf-8`
- **Encoding**: Gzip compression (`Content-Encoding: gzip`)
- **Body**: JSON via `android.util.JsonWriter`
- **Content-Length**: Auto-negotiated (first request without, retry with if 411)

#### API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/time` | Get server time in milliseconds |
| POST | `/auth/send-mail-login-code-v2` | Send email login code (with device verification) |
| POST | `/auth/sign-in-by-mail-code` | Sign in with email + code → returns mailAuthToken |
| POST | `/parent/get-status-by-mail-address` | Get family/mail status |
| POST | `/parent/create-family` | Create family (parent setup) |
| POST | `/parent/sign-in-into-family` | Sign in to existing family |
| POST | `/parent/recover-parent-password` | Recover parent password |
| POST | `/child/add-device` | Register child device |
| POST | `/sync/push-actions` | Push pending actions to server |
| POST | `/sync/pull-status` | Pull server status (devices, users, categories, crypto) |
| POST | `/parent/create-add-device-token` | Create token for adding a device |
| POST | `/purchase/can-do-purchase` | Check purchase eligibility |
| POST | `/purchase/finish-purchase-by-google-play` | Finish Google Play purchase |
| POST | `/parent/link-mail-address` | Link email to parent account |
| POST | `/child/update-primary-device` | Update primary device selection |
| POST | `/child/logout-at-primary-device` | Sign out at primary device |
| POST | `/sync/report-removed` | Report device as removed |
| POST | `/parent/remove-device` | Remove a device |
| POST | `/sync/is-device-removed` | Check if device was removed |
| POST | `/parent/create-identity-token` | Create identity token (for purchases) |
| POST | `/parent/delete-account` | Delete account |

#### Device Verification (Android 7.0+)

`withDeviceVerification()` in `HttpServerApi` ([app/src/main/java/io/timelimit/android/sync/network/api/HttpServerApi.kt:713](app/src/main/java/io/timelimit/android/sync/network/api/HttpServerApi.kt)) generates a temporary EC key pair in Android Keystore with attestation, creates an `X509ClientKeyManager`, and uses it for the TLS connection. This provides device attestation for the `sendMailLoginCode` endpoint.

#### Error Handling

`HttpErrors.kt` ([app/src/main/java/io/timelimit/android/sync/network/api/HttpErrors.kt:21](app/src/main/java/io/timelimit/android/sync/network/api/HttpErrors.kt)) maps HTTP status codes to typed exceptions:

| Code | Exception |
|------|-----------|
| 400 | `BadRequestHttpError` |
| 401 | `UnauthorizedHttpError` |
| 403 | `ForbiddenHttpError` |
| 404 | `NotFoundHttpError` |
| 409 | `ConflictHttpError` |
| 410 | `GoneHttpError` |
| 429 | `TooManyRequestsHttpError` |

### 3.3 SSL/TLS & DNS Configuration (by Flavor)

#### Production Server (`SslConfig.kt`)

- **Certificate Pinning**: Pins ISRG Root X1, X2, YE, YR (Let's Encrypt) for `api.timelimit.io`, `update.timelimit.io`, and `api.timelimitapp.de`
- **Trust Manager**: Custom `HandshakeCertificates` with ISRG roots + platform-trusted certificates
- **DNS**: Custom DNS resolver that queries both `api.timelimit.io` and `api.timelimitapp.de` for the server domain, combining results for redundancy

#### Development Server

- **Certificate Pinning**: None (empty `CertificatePinner`)
- **Trust Manager**: Platform-trusted certificates only
- **DNS**: System DNS

#### No Server

- **Certificate Pinning**: None
- **Trust Manager**: Platform-trusted certificates only
- **DNS**: System DNS
- All API calls throw `IOException` (via `DummyServerApi`)

### 3.4 WebSocket (Socket.IO)

`WebsocketClient.kt` ([app/src/main/java/io/timelimit/android/sync/websocket/WebsocketClient.kt:43](app/src/main/java/io/timelimit/android/sync/websocket/WebsocketClient.kt)) uses the Socket.IO client library with WebSocket transport only.

#### Connection Flow

```
1. AppLogic creates WebsocketClientLogic
2. WebsocketClientLogic monitors:
   - App enabled
   - Network status (online)
   - Screen on (or KEEP_CONNECTED_WHEN_SCREEN_OFF flag)
   - User type (child always connects; parent only when app in foreground)
3. When conditions met → get deviceAuthToken from database
4. Create SocketIoWebsocketClient with serverUrl + deviceAuthToken
5. Socket.IO connects → emit "devicelogin" with auth token
6. Server responds with ack → onConnectionEstablished()
```

#### Socket.IO Events

| Event | Direction | Payload | Handler |
|-------|-----------|---------|---------|
| `connect` | Server → Client | — | Emit `devicelogin` with auth token |
| `devicelogin` | Client → Server | auth token (ack) | `onConnectionEstablished()` |
| `disconnect` | Server → Client | — | `onConnectionLost()` |
| `should sync` | Server → Client | `{isImportant: Boolean}` | `onSyncRequestedByServer(important)` |
| `connected devices` | Server → Client | `[deviceId, ...]` | `onGotConnectedDeviceList(ids)` |
| `sign out` | Server → Client | — | `onGotSignOutRequest()` |

#### WebsocketClientLogic

`WebsocketClientLogic.kt` ([app/src/main/java/io/timelimit/android/logic/WebsocketClientLogic.kt:35](app/src/main/java/io/timelimit/android/logic/WebsocketClientLogic.kt)) manages the WebSocket lifecycle:

- Monitors connection conditions via LiveData chain
- Reconnects when auth token changes
- Shuts down old connections when creating new ones
- On `onConnectionEstablished`: sets `isConnected = true`, clears connected devices, requests important sync
- On `onSyncRequestedByServer`: triggers sync (important or unimportant)
- On `onGotSignOutRequest`: unsets current device as primary device
- Uses instance identity check (`currentWebsocketClient !== newWebsocketClient`) to prevent stale callbacks

### 3.5 Sync Protocol (Action-Based CRDT)

The sync system is the core of the connection logic. It uses an action-based approach where all changes are serialized as JSON actions.

#### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    SyncUtil                              │
│  - Sync loop (infinite coroutine)                        │
│  - Token bucket rate limiting                            │
│  - Three sync priorities (important/unimportant/very)  │
├─────────────────────────────────────────────────────────┤
│              UploadActionsUtil                           │
│  - Batches actions (25 per batch)                       │
│  - Marks actions as "scheduled" before upload             │
│  - Handles full sync on conflict                          │
├─────────────────────────────────────────────────────────┤
│              ApplyServerDataStatus                       │
│  - Applies server data to local database                  │
│  - Dispatches parent actions locally                      │
│  - Handles crypto key requests/responses                  │
├─────────────────────────────────────────────────────────┤
│              CryptoSyncLogic                             │
│  - KeyRequestProcessor: responds to key requests          │
│  - KeyResponseProcessor: processes key responses        │
│  - DecryptProcessor: decrypts app lists                 │
└─────────────────────────────────────────────────────────┘
```

#### Sync Flow

```
1. Sync requested (important/unimportant/veryUnimportant)
2. Wait for conditions: network connected + app enabled + sync requested
3. Rate limit check (token bucket: 30s interval, max 30 tokens)
4. doSync():
   a. Get ServerConfig (auth token, server URL)
   b. If no auth token → throw SyncingDisabledException
   c. doSyncRoundRetryOnNewActions():
      i.  pushActions(): UploadActionsUtil.uploadActions()
         - Get max sequence number
         - Loop: mark unscheduled actions as scheduled (batch of 25)
         - Upload scheduled actions via pushChanges()
         - Delete confirmed actions
         - If server says shouldDoFullSync → wipe version numbers
      ii. pullStatus():
         - Get current ClientDataStatus (version numbers)
         - Call pullChanges() with auth token + status
         - ApplyServerDataStatus.applyServerDataStatusSync()
         - CryptoSyncLogic.postPullHook()
         - Handle pings (pong responses)
         - If new actions created → request next sync
   d. On UnauthorizedHttpError:
      - Check if device removed → dangerousRemoteReset()
      - Otherwise rethrow
5. On success: update lastSync, deschedule background worker
6. On failure: wait 10-15s, retry
```

#### Sync Priorities

| Priority | Trigger | Conditions |
|----------|---------|------------|
| Important | User action, websocket connect, server push | Always syncs |
| Unimportant | Server push (non-important) | App must be in foreground |
| Very Unimportant | Periodic/background | Last sync > 10 minutes ago |

#### ClientDataStatus

`ClientDataStatus.kt` ([app/src/main/java/io/timelimit/android/sync/network/ClientDataStatus.kt:21](app/src/main/java/io/timelimit/android/sync/network/ClientDataStatus.kt)) tracks the client's sync state:

- `deviceListVersion` — version of device list
- `installedAppsVersionsByDeviceId` — per-device app list versions
- `deviceDetailData` — per-device app base/diff versions (API level ≥ 4)
- `categories` — per-category version numbers (base, assignedApps, timeLimitRules, usedTimeItems, taskList)
- `userListVersion` — version of user list
- `lastKeyRequestServerSequence` — last processed key request sequence
- `lastKeyResponseServerSequence` — last processed key response sequence
- `dhKeyVersion` — DH key version
- `u2fVersion` — U2F data version
- `CLIENT_LEVEL_VALUE = 7` — client protocol version

#### ServerDataStatus

`ServerDataStatus.kt` ([app/src/main/java/io/timelimit/android/sync/network/ServerDataStatus.kt:34](app/src/main/java/io/timelimit/android/sync/network/ServerDataStatus.kt)) is the server's response containing:

- `newDeviceList` — full device list with version
- `updatedExtendedDeviceData` — device detail data
- `newInstalledApps` — installed apps per device
- `removedCategories` — list of removed category IDs
- `newCategoryBaseData` — category base data (time limits, etc.)
- `newCategoryAssignedApps` — category app assignments
- `newCategoryUsedTimes` — used time items
- `newCategoryTimeLimitRules` — time limit rules
- `newCategoryTasks` — child tasks
- `newUserList` — full user list with version
- `pendingKeyRequests` — crypto key requests from other devices
- `keyResponses` — crypto key responses
- `pings` — ping/pong messages for primary device borrowing
- `dh` — DH key for password encryption
- `u2f` — U2F data
- `fullVersionUntil` — premium expiration timestamp
- `message` — server message
- `apiLevel` — server API level

#### Action System

`Actions.kt` ([app/src/main/java/io/timelimit/android/sync/actions/Actions.kt:89](app/src/main/java/io/timelimit/android/sync/actions/Actions.kt)) defines the action hierarchy:

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
│   ├── ... (many more)
├── ParentAction (sealed) — parent-initiated actions
└── ChildAction (sealed) — child-initiated actions
```

**Key Design Principles** (from Actions.kt comments):

- Actions are deterministic: same actions in same order → same state
- Client generates IDs randomly; server prefixes with family ID
- Conflict handling: client uploads first, failed actions trigger version wipe
- Version numbers: random strings, stored per entity type
- Laggy connection handling: actions marked "once sent" before sending, sequence numbers prevent duplicates
- Server doesn't process duplicate sequence numbers but still sends status

#### Action Upload

`ActionUpload.kt` ([app/src/main/java/io/timelimit/android/sync/network/ActionUpload.kt:23](app/src/main/java/io/timelimit/android/sync/network/ActionUpload.kt)):

- `ActionUploadRequest`: `{deviceAuthToken, actions: [ActionUploadItem]}`
- `ActionUploadItem`: `{encodedAction, sequenceNumber, integrity, type, userId}`
- `ActionUploadResponse`: `{shouldDoFullSync: Boolean}`

#### Background Sync

`SyncInBackgroundWorker.kt` ([app/src/main/java/io/timelimit/android/work/SyncInBackgroundWorker.kt:32](app/src/main/java/io/timelimit/android/work/SyncInBackgroundWorker.kt)) uses WorkManager with:

- Unique work name: `SyncInBackgroundWork`
- Initial delay: 10 seconds
- Constraint: network connected
- Runs `DefaultAppLogic.with(context).syncUtil.doSync()`
- On `SyncingDisabledException`: failure
- On other exceptions: retry

### 3.6 Crypto System

#### Overview

The crypto system provides end-to-end encryption for sensitive data synced between devices, particularly app lists and parent passwords.

#### Curve25519 (`Curve25519.kt`)

- Uses WhisperSystems Curve25519 library
- Key pair: 32-byte public + 32-byte private (serialized as 64 bytes)
- Operations: `generateKeyPair()`, `getPublicKey()`, `getPrivateKey()`, `sign()`, `validateSignature()`, `sharedSecret()`
- Signature size: 64 bytes

#### AES-GCM CryptContainer (`CryptContainer.kt`)

- Key size: 16 bytes (AES-128)
- Auth tag: 128 bits
- Format versions: `FORMAT_LEGACY (0)`, `FORMAT_APP_LIST_V2 (1)`, `FORMAT_APP_DIFF_V2 (2)`
- Header: generation (8 bytes) + counter (8 bytes) + IV (4 bytes) = 20 bytes
- IV construction: `iv (4 bytes) + counter (8 bytes)` = 12 bytes
- AAD: generation + format version
- Counter prevents replay attacks; generation allows key rotation

#### Device Signing Key (`DeviceSigningKey.kt`)

- Curve25519 key pair stored in `ConfigurationItem.SigningKey`
- Only used when server API level ≥ 4
- Public key uploaded to server via `UploadDevicePublicKeyAction`
- Used for signing key requests and responses

#### Key Request/Response Protocol

This is a multi-device key exchange protocol for sharing decryption keys:

```
Device A (key holder)          Server          Device B (key requester)
     │                          │                       │
     │ 1. SendKeyRequestAction  │                       │
     │    (tempKey, signature)  │                       │
     │─────────────────────────→│                       │
     │                          │ 2. Forward to A       │
     │                          │───────────────────────→│
     │                          │                       │
     │ 3. ReplyToKeyRequestAction                       │
     │    (tempKey, encryptedKey, signature)            │
     │←─────────────────────────│                       │
     │                          │ 4. Forward to B       │
     │                          │←───────────────────────│
     │                          │                       │
     │ 5. FinishKeyRequestAction                        │
     │    (marks request as done)                       │
     │──────────────────────────────────────────────────→│
```

**Key Request** (`KeyRequestSignedData.kt`):
- Signed data: `"KeyRequestSignedData" + deviceSequenceNumber + deviceId + categoryId + type + tempKey`
- Device A verifies signature with Device B's public key
- Device A computes shared secret: `Curve25519.sharedSecret(request.tempKey, ownPrivateKey)`
- Device A encrypts the generation key: `AES/ECB/NoPadding` with first 16 bytes of shared secret
- Device A signs response: `"KeyResponseSignedData" + senderDevicePublicKey + tempKey + encryptedKey + request.serialize()`

**Key Response** (`KeyResponseProcessor.kt`):
- Device B verifies signature with Device A's public key
- Device B computes shared secret: `Curve25519.sharedSecret(response.tempKey, ownPrivateKey)`
- Device B decrypts key: `AES/ECB/NoPadding` with first 16 bytes of shared secret
- Device B validates key against encrypted data
- If valid: stores key, marks request as finished
- If invalid: records `CryptContainerKeyResult.InvalidKey`

#### DH Key Exchange (`DH.kt`)

- ECDH with secp256r1 curve
- Used for encrypting parent passwords during family creation
- `DHHandshake.fromServerKey()`: generates own keypair, computes shared secret
- `encrypt()`: AES-GCM with 16-byte key (first 16 bytes of the 32-byte shared secret; verified in the server source, see docs/ServerAPI.md section 8), 12-byte IV, AAD for auth
- Output format: `base64(iv + encryptedData) + "." + base64(ownPublicKey) + "." + keyVersion`

#### Password Hashing (`PasswordHashing.kt`)

- Uses jBCrypt (bcrypt)
- `hashSync()`: generates salt + hash
- `hashSyncWithSalt()`: hash with specific salt
- `validateSync()`: bcrypt verification with exception handling

#### Parent Password (`ParentPassword.kt`)

- Contains: `parentPasswordHash` (bcrypt), `parentPasswordSecondHash` (bcrypt with separate salt), `parentPasswordSecondSalt`, `encrypted` flag
- When DH key available: second hash is encrypted via DH handshake
- AAD for encryption: `"ParentPassword:$hash:$secondSalt"`

#### App List Encryption (`DecryptProcessor.kt`)

- Encrypted app lists synced between devices (TYPE_APP_LIST_BASE, TYPE_APP_LIST_DIFF)
- Uses `CryptContainer` with format versions
- `DecryptProcessor.handleEncryptedApps()`: decrypts app lists for other devices
- Validates base/diff consistency (generation and counter matching)
- Updates local app database with decrypted app lists

### 3.7 User Handling

#### User Model

`User.kt` ([app/src/main/java/io/timelimit/android/data/model/User.kt:31](app/src/main/java/io/timelimit/android/data/model/User.kt)):

- `id`: UUID (client-generated)
- `name`: Display name
- `password`: bcrypt hash (empty if not set)
- `secondPasswordSalt`: Salt for second password hash
- `type`: `Parent` or `Child`
- `timeZone`: IANA timezone ID
- `disableLimitsUntil`: Timestamp (0 = limits enabled)
- `mail`: Email address (for parent accounts)
- `currentDevice`: ID of current/primary device
- `categoryForNotAssignedApps`: Category for apps not assigned to any category
- `relaxPrimaryDevice`: If true, limits relaxed when connected and premium
- `mailNotificationFlags`: Bitmask for mail notifications
- `flags`: Bitmask (RESTRICT_VIEWING_TO_PARENTS, ALLOW_SELF_LIMIT_ADD)

#### Authentication Flow

```
1. Parent creates family:
   a. Send email → receive code
   b. Sign in with code → get mailAuthToken
   c. Create family with parentPassword (bcrypt + DH encryption)
   d. Server returns deviceAuthToken + ownDeviceId
   e. Pull initial data from server

2. Child device registration:
   a. Parent creates add-device token
   b. Child uses token to register
   c. Server returns deviceAuthToken + ownDeviceId
   d. Pull initial data from server

3. Password recovery:
   a. Send email → receive code
   b. Sign in with code → get mailAuthToken
   c. Recover password with new password
```

#### Mail-Based Authentication

- `sendMailLoginCode()`: Sends code to email, with device verification (attestation)
- `signInByMailCode()`: Exchanges code for mailAuthToken
- `getStatusByMailAddress()`: Checks if email is linked to a family
- `createFamilyByMailToken()`: Creates new family
- `signInToFamilyByMailToken()`: Joins existing family
- `recoverPasswordByMailToken()`: Resets parent password
- `linkParentMailAddress()`: Links email to parent account

#### U2F (Universal 2nd Factor)

- USB and NFC support
- `U2fManager`: Singleton managing USB and NFC U2F managers
- `UserU2FKey`: Stores U2F key handles and public keys per user
- Server sends U2F data (key handles, public keys) via `ServerU2fData`
- Used for parent authentication (second factor)

#### Primary Device & Borrowing

`CurrentDeviceLogic.kt` ([app/src/main/java/io/timelimit/android/logic/CurrentDeviceLogic.kt:41](app/src/main/java/io/timelimit/android/logic/CurrentDeviceLogic.kt)):

- **Primary Device**: The device where the user is currently active (user.currentDevice == device.id)
- **Relaxed Current Device**: When connected, premium, and `relaxPrimaryDevice` is true
- **Borrowed Current Device**: When the primary device is temporarily borrowed via ping/pong
- **Local Mode**: When no server is configured (offline mode)

**Borrow Flow**:
```
1. Child device requests borrow from parent device
2. Sends PingAction with token via sync
3. Parent device receives PingAction → sends PingAction back
4. Server forwards ping to parent device
5. Parent device responds with PongAction
6. Child device receives PongAction → becomes borrowed current device
7. Borrow expires after 5 minutes, refreshed every 2-4 minutes
```

#### Full Version / Premium

`FullVersionLogic.kt` ([app/src/main/java/io/timelimit/android/logic/FullVersionLogic.kt:24](app/src/main/java/io/timelimit/android/logic/FullVersionLogic.kt)):

- `hasFullVersion`: `fullVersionUntil != 0` (from server)
- `isLocalMode`: No device auth token (offline)
- `shouldProvideFullVersionFunctions`: `hasFullVersion OR isLocalMode`
- Full version enables: relaxed primary device, system-level blocking, etc.

---

## 4. Data Layer

### Room Database

`RoomDatabase.kt` ([app/src/main/java/io/timelimit/android/data/RoomDatabase.kt:70](app/src/main/java/io/timelimit/android/data/RoomDatabase.kt)):

- **Version**: 50 (with auto-migrations 46→47→48→49→50)
- **Journal Mode**: TRUNCATE (with PERSIST pragma on open)
- **Query Executor**: `Threads.database`
- **Entities** (22):

| Entity | Table | Purpose |
|--------|-------|---------|
| `User` | user | Parent/child users |
| `Device` | device | Registered devices |
| `App` | app | Installed apps per device |
| `CategoryApp` | category_app | App-to-category assignments |
| `Category` | category | Time limit categories |
| `UsedTimeItem` | used_time | Used time tracking |
| `TimeLimitRule` | time_limit_rule | Time limit rules |
| `ConfigurationItem` | config | App configuration |
| `TemporarilyAllowedApp` | temporarily_allowed_app | Temporarily allowed apps |
| `PendingSyncAction` | pending_sync_action | Queued sync actions |
| `AppActivity` | app_activity | App activities |
| `Notification` | notification | Notification records |
| `AllowedContact` | allowed_contact | Allowed contacts |
| `UserKey` | user_key | User encryption keys |
| `SessionDuration` | session_duration | Session duration limits |
| `UserLimitLoginCategory` | user_limit_login_category | Limit login categories |
| `CategoryNetworkId` | category_network_id | Network-specific categories |
| `ChildTask` | child_task | Child tasks |
| `CategoryTimeWarning` | category_time_warning | Time warnings |
| `CryptContainerMetadata` | crypt_container_metadata | Encrypted data metadata |
| `CryptContainerData` | crypt_container_data | Encrypted data |
| `CryptContainerPendingKeyRequest` | crypt_container_key_request | Pending key requests |
| `CryptContainerKeyResult` | crypt_container_key_result | Key request results |
| `DevicePublicKey` | device_key | Device public keys |
| `UserU2FKey` | user_u2f_key | U2F keys |
| `WidgetCategory` | widget_category | Widget categories |
| `WidgetConfig` | widget_config | Widget configs |

### Configuration Items

`ConfigurationItem.kt` ([app/src/main/java/io/timelimit/android/data/model/ConfigurationItem.kt:25](app/src/main/java/io/timelimit/android/data/model/ConfigurationItem.kt)):

Key-value storage with 34 configuration types:

| Type | Key | Purpose |
|------|-----|---------|
| `OwnDeviceId` | 1 | This device's ID |
| `UserListVersion` | 2 | User list sync version |
| `DeviceListVersion` | 3 | Device list sync version |
| `NextSyncSequenceNumber` | 4 | Next action sequence number |
| `DeviceAuthToken` | 5 | Server authentication token |
| `FullVersionUntil` | 6 | Premium expiration timestamp |
| `ServerMessage` | 12 | Message from server |
| `CustomServerUrl` | 13 | Custom server URL |
| `ServerApiLevel` | 24 | Server API level |
| `SigningKey` | 27 | Curve25519 signing key |
| `SignSequenceNumber` | 28 | Signing sequence number |
| `LastServerKeyRequestSequence` | 29 | Last key request sequence |
| `LastKeyResponseSequence` | 30 | Last key response sequence |
| `DhKey` | 31 | DH key for password encryption |
| `DhKeyVersion` | 32 | DH key version |
| `U2fListVersion` | 33 | U2F data version |

### Experimental Flags

```
SYSTEM_LEVEL_BLOCKING = 2
IGNORE_SYSTEM_CONNECTION_STATUS = 8
CUSTOM_HOME_SCREEN = 16
CUSTOM_HOMESCREEN_DELAY = 32
NETWORKTIME_AT_SYSTEMLEVEL = 64
HIGH_MAIN_LOOP_DELAY = 128
KEEP_CONNECTED_WHEN_SCREEN_OFF = 512
MULTI_APP_DETECTION = 1024
REQUIRE_SYNC_FOR_PARENT_LOGIN = 2048
HIDE_MANIPULATION_WARNING = 8192
ENABLE_SOFT_BLOCKING = 16384
SYNC_RELATED_NOTIFICATIONS = 32768
STRICT_OVERLAY_CHECKING = 0x40000
```

### Consent Flags

```
APP_LIST_SYNC = 1
BLOCK_USER_SWITCH_BY_DEFAULT = 2
```

---

## 5. Platform Integration

### Android Services

| Component | Purpose |
|-----------|---------|
| `AdminReceiver` | Device admin receiver |
| `BackgroundService` | Foreground service for blocking |
| `BackgroundActionService` | Background action processing |
| `NotificationListener` | Notification access service |
| `AccessibilityService` | Accessibility service for blocking |
| `BootReceiver` | Boot completed handler |
| `UpdateReceiver` | Package replaced handler |
| `TimesWidgetProvider` | App widget provider |

### Permissions

- `RECEIVE_BOOT_COMPLETED`, `VIBRATE`, `SYSTEM_ALERT_WINDOW`, `INTERNET`
- `ACCESS_NETWORK_STATE`, `WAKE_LOCK`, `FOREGROUND_SERVICE`
- `FOREGROUND_SERVICE_SYSTEM_EXEMPTED`, `CALL_PHONE`, `QUERY_ALL_PACKAGES`
- `ACCESS_WIFI_STATE`, `ACCESS_FINE_LOCATION`, `POST_NOTIFICATIONS`, `NFC`
- `PACKAGE_USAGE_STATS` (system-level), `GET_TASKS` (deprecated)

### Manipulation Detection

The app detects device manipulation attempts:
- Disabling device admin
- Rebooting
- `manipulationFlags` bitmask tracking various manipulation types
- `hadManipulation` flag for tracking if manipulation occurred

---

## 6. Update System

### Update Check

`CheckUpdateWorker.kt` checks for updates from `https://update.timelimit.io/update.json`:

- Certificate pinning with `updateServerBuildsCertificate`
- Compares app version with minimum recommended server version
- Shows update notification if newer version available

### Update Flow

- `UpdateActivity` handles the update process
- Downloads APK from update server
- Verifies certificate fingerprint
- Installs via system installer

---

## 7. Key File References

### Connection & Sync

| File | Lines | Description |
|------|-------|-------------|
| [`Api.kt`](app/src/main/java/io/timelimit/android/sync/network/api/Api.kt) | 20-60 | ServerApi interface |
| [`HttpServerApi.kt`](app/src/main/java/io/timelimit/android/sync/network/api/HttpServerApi.kt) | 53-767 | HTTP API implementation |
| [`HttpClient.kt`](app/src/main/java/io/timelimit/android/sync/network/api/HttpClient.kt) | 25-38 | OkHttp client configuration |
| [`HttpErrors.kt`](app/src/main/java/io/timelimit/android/sync/network/api/HttpErrors.kt) | 21-45 | HTTP error mapping |
| [`DummyServerApi.kt`](app/src/main/java/io/timelimit/android/sync/network/api/DummyServerApi.kt) | 21-116 | Offline mode API |
| [`WebsocketClient.kt`](app/src/main/java/io/timelimit/android/sync/websocket/WebsocketClient.kt) | 43-117 | Socket.IO client |
| [`WebsocketClientLogic.kt`](app/src/main/java/io/timelimit/android/logic/WebsocketClientLogic.kt) | 35-223 | WebSocket lifecycle |
| [`SyncUtil.kt`](app/src/main/java/io/timelimit/android/sync/SyncUtil.kt) | 44-313 | Sync orchestration |
| [`UploadActionsUtil.kt`](app/src/main/java/io/timelimit/android/sync/actions/apply/UploadActionsUtil.kt) | 25-127 | Action upload |
| [`ApplyServerDataStatus.kt`](app/src/main/java/io/timelimit/android/sync/ApplyServerDataStatus.kt) | 34-658 | Server data application |
| [`Actions.kt`](app/src/main/java/io/timelimit/android/sync/actions/Actions.kt) | 89-2220 | Action definitions |
| [`ClientDataStatus.kt`](app/src/main/java/io/timelimit/android/sync/network/ClientDataStatus.kt) | 21-187 | Client sync status |
| [`ServerDataStatus.kt`](app/src/main/java/io/timelimit/android/sync/network/ServerDataStatus.kt) | 34-1431 | Server sync response |
| [`ServerLogic.kt`](app/src/main/java/io/timelimit/android/logic/ServerLogic.kt) | 23-63 | Server config management |
| [`ServerApiLevelLogic.kt`](app/src/main/java/io/timelimit/android/logic/ServerApiLevelLogic.kt) | 25-65 | API level tracking |

### Crypto

| File | Lines | Description |
|------|-------|-------------|
| [`Curve25519.kt`](app/src/main/java/io/timelimit/android/crypto/Curve25519.kt) | 24-69 | Curve25519 operations |
| [`CryptContainer.kt`](app/src/main/java/io/timelimit/android/crypto/CryptContainer.kt) | 26-150 | AES-GCM container |
| [`DH.kt`](app/src/main/java/io/timelimit/android/crypto/DH.kt) | 30-82 | ECDH key exchange |
| [`PasswordHashing.kt`](app/src/main/java/io/timelimit/android/crypto/PasswordHashing.kt) | 20-32 | bcrypt hashing |
| [`DeviceSigningKey.kt`](app/src/main/java/io/timelimit/android/logic/crypto/DeviceSigningKey.kt) | 23-49 | Device signing key |
| [`KeyRequestProcessor.kt`](app/src/main/java/io/timelimit/android/logic/crypto/KeyRequestProcessor.kt) | 30-183 | Key request handling |
| [`KeyResponseProcessor.kt`](app/src/main/java/io/timelimit/android/logic/crypto/KeyResponseProcessor.kt) | 32-215 | Key response handling |
| [`CryptDataHandler.kt`](app/src/main/java/io/timelimit/android/logic/crypto/CryptDataHandler.kt) | 27-195 | Crypto data processing |
| [`DecryptProcessor.kt`](app/src/main/java/io/timelimit/android/logic/crypto/decrypt/DecryptProcessor.kt) | 34-192 | App list decryption |
| [`KeyRequestSignedData.kt`](app/src/main/java/io/timelimit/android/logic/crypto/KeyRequestSignedData.kt) | 20-83 | Key request signing |
| [`CryptoSyncLogic.kt`](app/src/main/java/io/timelimit/android/logic/crypto/CryptoSyncLogic.kt) | 25-55 | Crypto sync orchestration |
| [`ParentPassword.kt`](app/src/main/java/io/timelimit/android/sync/network/ParentPassword.kt) | 25-80 | Password encryption |

### SSL/DNS (Flavors)

| File | Flavor | Description |
|------|--------|-------------|
| [`SslConfig.kt`](app/src/productionServer/java/io/timelimit/flavor/SslConfig.kt) | production | Certificate pinning + ISRG roots |
| [`SslConfig.kt`](app/src/developmentServer/java/io/timelimit/flavor/SslConfig.kt) | development | No pinning, platform trust |
| [`CertificatePinning.kt`](app/src/noServer/java/io/timelimit/flavor/CertificatePinning.kt) | noServer | Empty pinner |
| [`Dns.kt`](app/src/productionServer/java/io/timelimit/flavor/Dns.kt) | production | Dual-domain DNS |
| [`Dns.kt`](app/src/developmentServer/java/io/timelimit/flavor/Dns.kt) | development | System DNS |
| [`Dns.kt`](app/src/noServer/java/io/timelimit/flavor/Dns.kt) | noServer | System DNS |

### Core Logic

| File | Lines | Description |
|------|-------|-------------|
| [`AppLogic.kt`](app/src/main/java/io/timelimit/android/logic/AppLogic.kt) | 33-109 | Central coordinator |
| [`AndroidAppLogic.kt`](app/src/main/java/io/timelimit/android/logic/AndroidAppLogic.kt) | 33-85 | AppLogic initialization |
| [`AppSetupLogic.kt`](app/src/main/java/io/timelimit/android/logic/AppSetupLogic.kt) | 40-288 | Device setup/reset |
| [`CurrentDeviceLogic.kt`](app/src/main/java/io/timelimit/android/logic/CurrentDeviceLogic.kt) | 41-343 | Primary device/borrowing |
| [`FullVersionLogic.kt`](app/src/main/java/io/timelimit/android/logic/FullVersionLogic.kt) | 24-31 | Premium feature gating |
| [`RoomDatabase.kt`](app/src/main/java/io/timelimit/android/data/RoomDatabase.kt) | 70-203 | Database configuration |
| [`User.kt`](app/src/main/java/io/timelimit/android/data/model/User.kt) | 31-200 | User model |
| [`Device.kt`](app/src/main/java/io/timelimit/android/data/model/Device.kt) | 32-419 | Device model |
| [`ConfigurationItem.kt`](app/src/main/java/io/timelimit/android/data/model/ConfigurationItem.kt) | 25-307 | Config storage |

---

## 8. Device Registration Flow (for Non-Android Python Client)

This section details the complete flow of adding a new device to an existing family, with pseudo code
sufficient to implement a Python client that registers as a non-Android device and manages allowed
applications on other devices and users.

### 8.1 Overview

The flow has two phases:

1. **Parent phase**: An already-registered parent device creates an "add device token" via the HTTP API.
2. **Child phase**: The new (non-Android) device uses that token to register, receives a `deviceAuthToken`,
   and then participates in the sync protocol.

After registration, the new device behaves like any other device: it connects via WebSocket (Socket.IO)
for real-time sync, and uses the HTTP sync endpoints (`push-actions`, `pull-status`) to exchange actions
and state with the server.

```
Parent Device              TimeLimit Server           New Python Device
     |                           |                          |
     | 1. POST /parent/create-add-device-token            |
     |    {deviceAuthToken, parentId, parentPasswordSecondHash}
     |------------------------->|                          |
     |    {token, deviceId}     |                          |
     |<------------------------|                          |
     |    (displays token to user)                        |
     |                                                    |
     |                                                    | 2. POST /child/add-device
     |                                                    |    {registerToken, childDevice:{model}, deviceName, clientLevel}
     |                                                    |------------------------->|
     |                                                    |    {deviceAuthToken, ownDeviceId, data: ServerDataStatus}
     |                                                    |<------------------------|
     |                                                    | 3. Store deviceAuthToken + ownDeviceId
     |                                                    | 4. Apply ServerDataStatus to local state
     |                                                    | 5. WebSocket connect + sync loop
```

### 8.2 Server Configuration

- **Server URL**: `https://api.timelimit.io` (production) or `http://10.0.2.2:8080` (development)
- **Server Domain**: `api.timelimit.io`
- **Backup Domain**: `api.timelimitapp.de`
- **Certificate Pinning**: Production pins ISRG Root X1, X2, YE, YR (Let's Encrypt). Development has no pinning.
- **Client Level**: `7` (checked 2026-11-04: Android app 7.5.0 in the `mpashka` fork sends `8`, the older `flov91` fork sends `6`; the server only gates features by level, see docs/ServerAPI.md section 5.2; so `7` was not the current level, sent as `clientLevel` in registration and sync requests)

### 8.3 HTTP Request Format

All HTTP requests follow the same format:

```
POST /<endpoint>
Content-Type: application/json; charset=utf-8
Content-Encoding: gzip
Content-Length: <auto-negotiated>

<gzipped JSON body>
```

Pseudo code for HTTP request construction:

```python
def make_http_request(endpoint, body_dict, server_url, use_device_verification=False):
    """
    Construct and send an HTTP POST request to the TimeLimit server.

    Key details:
    - Body is JSON, then gzip-compressed
    - Content-Type: application/json; charset=utf-8
    - Content-Encoding: gzip
    - Content-Length is auto-negotiated: first request without it,
      if server returns 411 (Length Required), retry with Content-Length
    - Device verification (Android 7.0+) uses a temporary EC key pair
      from Android Keystore with attestation, used as a TLS client cert.
      For Python, this step can be skipped (the server retries without it).
    """
    json_body = json.dumps(body_dict)
    gzipped_body = gzip.compress(json_body.encode('utf-8'))

    headers = {
        'Content-Type': 'application/json; charset=utf-8',
        'Content-Encoding': 'gzip',
    }

    url = f"{server_url}/{endpoint}"

    # First attempt: no Content-Length
    response = http_post(url, data=gzipped_body, headers=headers)

    if response.status_code == 411:
        # Server requires Content-Length
        headers['Content-Length'] = str(len(gzipped_body))
        response = http_post(url, data=gzipped_body, headers=headers)

    return response
```

### 8.4 Parent Authentication Flow (Email-Based)

Before creating an add-device token, the parent must be authenticated. The parent device already has a
`deviceAuthToken` from its own registration. If the parent needs to re-authenticate via email:

```python
def parent_authenticate_via_email(server_url, mail_address, locale="en"):
    """
    Step 1: Send email login code
    POST /auth/send-mail-login-code-v2

    Request body:
    {
        "mail": "<email address>",
        "locale": "<locale string>",
        "deviceAuthToken": "<optional, existing token>"
    }

    Response body:
    {
        "mailLoginToken": "<token string>",
        "mailServerBlacklisted": false,        # if true, throw exception
        "mailAddressNotWhitelisted": false,    # if true, throw exception
        "blockedForIntegrityReasons": false,   # if true, throw exception
        "mailServerBlacklistedTemporarily": false  # if true, throw exception
    }

    The server sends a verification code to the email address.
    """
    response = make_http_request(
        endpoint="auth/send-mail-login-code-v2",
        body_dict={
            "mail": mail_address,
            "locale": locale,
            # "deviceAuthToken": existing_token  # optional
        },
        server_url=server_url
    )
    data = json.loads(response.body)
    return data["mailLoginToken"]


def parent_sign_in_with_code(server_url, mail_login_token, code):
    """
    Step 2: Sign in with email code
    POST /auth/sign-in-by-mail-code

    Request body:
    {
        "mailLoginToken": "<token from step 1>",
        "receivedCode": "<code entered by user>"
    }

    Response body:
    {
        "mailAuthToken": "<token string>"
    }
    """
    response = make_http_request(
        endpoint="auth/sign-in-by-mail-code",
        body_dict={
            "mailLoginToken": mail_login_token,
            "receivedCode": code
        },
        server_url=server_url
    )
    data = json.loads(response.body)
    return data["mailAuthToken"]


def parent_get_status_by_mail(server_url, mail_auth_token):
    """
    Step 3: Check family status
    POST /parent/get-status-by-mail-address

    Request body:
    {
        "mailAuthToken": "<token from step 2>"
    }

    Response body:
    {
        "mail": "<email address>",
        "status": "with family" | "without family",
        "canCreateFamily": true/false,
        "alwaysPro": true/false
    }
    """
    response = make_http_request(
        endpoint="parent/get-status-by-mail-address",
        body_dict={
            "mailAuthToken": mail_auth_token
        },
        server_url=server_url
    )
    data = json.loads(response.body)
    return data
```

### 8.5 Parent Creates Add Device Token

The parent device (which already has a `deviceAuthToken`) creates a token that the new device will use
to register. The parent must provide:

- `deviceAuthToken`: The parent device's auth token (from its own registration)
- `parentUserId`: The user ID of the parent user
- `parentPasswordSecondHash`: The second password hash of the parent user

```python
def parent_create_add_device_token(server_url, device_auth_token, parent_user_id, parent_password_second_hash):
    """
    POST /parent/create-add-device-token

    Request body:
    {
        "deviceAuthToken": "<parent device auth token>",
        "parentId": "<parent user ID>",
        "parentPasswordSecondHash": "<second password hash>"
    }

    Response body:
    {
        "token": "<add-device token string>",
        "deviceId": "<parent device ID>"
    }

    The token is displayed to the user (e.g., as a QR code or text) and
    must be provided to the new device within 5 minutes.
    """
    response = make_http_request(
        endpoint="parent/create-add-device-token",
        body_dict={
            "deviceAuthToken": device_auth_token,
            "parentId": parent_user_id,
            "parentPasswordSecondHash": parent_password_second_hash
        },
        server_url=server_url
    )
    data = json.loads(response.body)
    return {
        "token": data["token"],
        "deviceId": data["deviceId"]
    }
```

**How to obtain `parentUserId` and `parentPasswordSecondHash`**:

After the parent device has registered and synced, it pulls `ServerDataStatus` from the server. The
user list (`ServerDataStatus.users.data`) contains `ServerUserData` entries. The parent user's entry
has:

- `id`: The user ID (used as `parentId`)
- `secondPasswordSalt`: The salt for the second password hash
- `password`: The first bcrypt password hash

The `parentPasswordSecondHash` is computed as:

```python
def compute_parent_password_second_hash(password, second_password_salt):
    """
    Compute the second password hash using bcrypt with a specific salt.

    This is the same as PasswordHashing.hashSyncWithSalt(password, secondPasswordSalt).
    Uses jBCrypt (bcrypt) with the provided salt.

    Args:
        password: The parent password (plaintext)
        second_password_salt: The salt string from ServerUserData.secondPasswordSalt

    Returns:
        The bcrypt hash string
    """
    # bcrypt hash with specific salt
    # In Python: bcrypt.hashpw(password.encode(), second_password_salt.encode())
    return bcrypt_hash_with_salt(password, second_password_salt)
```

**Note**: If the parent device was set up via `createFamilyByMailToken`, the `parentPasswordSecondHash`
may be encrypted using DH (ECDH secp256r1). In that case, the parent device stores the encrypted hash
and sends it directly. For a Python client, if you are the parent device, you would need to decrypt it
first using the DH shared secret, or if you are registering as a new device, the parent provides the
token and you do not need the password hash.

### 8.6 Child Device Registration

The new (non-Android) device uses the add-device token to register:

```python
def child_register_device(server_url, register_token, device_model_name, device_name):
    """
    POST /child/add-device

    Request body:
    {
        "registerToken": "<token from parent>",
        "childDevice": {
            "model": "<device model name>"
        },
        "deviceName": "<human-readable device name>",
        "clientLevel": 7
    }

    Note: The server may return HTTP 400 (BadRequest) if it does not recognize
    clientLevel=7. In that case, retry without the clientLevel field.

    Response body:
    {
        "deviceAuthToken": "<new device auth token>",
        "ownDeviceId": "<new device ID>",
        "data": <ServerDataStatus or null>
    }

    If "data" is null, the client must immediately call pullChanges with an
    empty ClientDataStatus to get the initial state.
    """
    body = {
        "registerToken": register_token,
        "childDevice": {
            "model": device_model_name
        },
        "deviceName": device_name,
        "clientLevel": 7
    }

    response = make_http_request(
        endpoint="child/add-device",
        body_dict=body,
        server_url=server_url
    )

    if response.status_code == 400:
        # Retry without clientLevel
        body.pop("clientLevel")
        response = make_http_request(
            endpoint="child/add-device",
            body_dict=body,
            server_url=server_url
        )

    data = json.loads(response.body)

    device_auth_token = data["deviceAuthToken"]
    own_device_id = data["ownDeviceId"]

    if data.get("data") is not None:
        server_data = parse_server_data_status(data["data"])
    else:
        # Pull initial data with empty status
        server_data = pull_changes(server_url, device_auth_token, client_data_status_empty())

    return {
        "deviceAuthToken": device_auth_token,
        "ownDeviceId": own_device_id,
        "serverData": server_data
    }
```

### 8.7 Post-Registration: Applying ServerDataStatus

After registration, the client receives a `ServerDataStatus` object. This contains the complete family
state: devices, users, categories, assigned apps, time limits, crypto keys, etc.

```python
def apply_server_data_status(server_data, local_state):
    """
    Apply the ServerDataStatus to local state.

    ServerDataStatus JSON structure:
    {
        "devices": {"version": "...", "data": [...]},           # ServerDeviceList
        "devices2": [...],                                        # List<ServerExtendedDeviceData>
        "apps": [...],                                            # List<ServerInstalledAppsData>
        "rmCategories": ["<categoryId>", ...],                   # removed categories
        "categoryBase": [...],                                   # List<ServerUpdatedCategoryBaseData>
        "categoryApp": [...],                                    # List<ServerUpdatedCategoryAssignedApps>
        "usedTimes": [...],                                      # List<ServerUpdatedCategoryUsedTimes>
        "rules": [...],                                          # List<ServerUpdatedTimeLimitRules>
        "tasks": [...],                                          # List<ServerUpdatedCategoryTasks>
        "users": {"version": "...", "data": [...]},              # ServerUserList
        "krq": [...],                                            # pending key requests
        "kr": [...],                                             # key responses
        "pings": [...],                                          # ping/pong for primary device borrowing
        "dh": {"v": "...", "k": "<base64>"},                    # DH key for password encryption
        "u2f": {"v": "...", "d": [...]},                        # U2F data
        "fullVersion": <timestamp>,                              # premium expiration
        "message": "<server message>",
        "apiLevel": <int>                                        # server API level
    }

    Key sub-structures:

    ServerDeviceData (in devices.data[]):
    {
        "deviceId": "...",
        "name": "...",
        "model": "...",
        "addedAt": <timestamp>,
        "currentUserId": "...",
        "currentProtectionLevel": "...",
        "highestProtectionLevel": "...",
        "currentAppVersion": <int>,
        "highestAppVersion": <int>,
        "publicKey": "<base64 or null>",
        "platformType": "<string or null>",
        "platformLevel": <int or null>,
        ... (many more fields)
    }

    ServerUserData (in users.data[]):
    {
        "id": "...",
        "name": "...",
        "password": "<bcrypt hash>",
        "secondPasswordSalt": "...",
        "type": "parent" | "child",
        "timeZone": "...",
        "disableLimitsUntil": <timestamp>,
        "mail": "...",
        "currentDevice": "...",
        "categoryForNotAssignedApps": "...",
        "relaxPrimaryDevice": <bool>,
        "flags": <long bitmask>,
        "limitLoginCategory": "<categoryId or null>",
        "preBlockDuration": <long>
    }

    ServerUpdatedCategoryBaseData (in categoryBase[]):
    {
        "categoryId": "...",
        "childId": "<user ID this category belongs to>",
        "title": "...",
        "blockedTimes": "<bitmask string>",
        "extraTime": <millis>,
        "extraTimeDay": <int>,
        "tempBlocked": <bool>,
        "tempBlockTime": <timestamp>,
        "version": "<base data version>",
        "parentCategoryId": "...",
        "blockAllNotifications": <bool>,
        "timeWarnings": <int>,
        "sort": <int>,
        "networks": [...],
        "flags": <long>,
        "blockNotificationDelay": <long>,
        "atw": [<int>, ...]
    }

    ServerUpdatedCategoryAssignedApps (in categoryApp[]):
    {
        "categoryId": "...",
        "apps": ["<package_name>", ...],
        "version": "<assigned apps version>"
    }

    ServerCryptContainer (in devices2[].appsBase / appsDiff):
    {
        "version": "<crypt container version>",
        "data": "<base64 encrypted app list data>"
    }
    Note: App lists are encrypted. See Section 9.10 for decryption.
    """
    # Store device list version
    local_state.device_list_version = server_data["devices"]["version"]

    # Store user list version
    local_state.user_list_version = server_data["users"]["version"]

    # Store devices
    for device in server_data["devices"]["data"]:
        local_state.devices[device["deviceId"]] = device

    # Store users
    for user in server_data["users"]["data"]:
        local_state.users[user["id"]] = user

    # Store categories (base data)
    for cat in server_data.get("categoryBase", []):
        local_state.categories[cat["categoryId"]] = cat

    # Store assigned apps per category
    for cat_apps in server_data.get("categoryApp", []):
        local_state.category_assigned_apps[cat_apps["categoryId"]] = cat_apps["apps"]

    # Store installed apps versions
    for app_data in server_data.get("apps", []):
        local_state.installed_apps_versions[app_data["deviceId"]] = app_data["version"]

    # Store DH key (for parent password encryption)
    if server_data.get("dh"):
        local_state.dh_key = server_data["dh"]

    # Store full version
    local_state.full_version_until = server_data.get("fullVersion", 0)

    # Store server API level
    local_state.server_api_level = server_data.get("apiLevel", 0)

    # Handle crypto key requests and responses (see Section 9.10)
    # Handle pings (primary device borrowing)
    # Handle removed categories
```

### 8.8 WebSocket Connection (Socket.IO)

After registration, the device connects via WebSocket for real-time sync notifications:

```python
def websocket_connect(server_url, device_auth_token):
    """
    Connect to the server via Socket.IO (WebSocket transport only).

    Flow:
    1. Create Socket.IO client with WebSocket transport
    2. Connect to server_url with deviceAuthToken
    3. On "connect" event: emit "devicelogin" with auth token
    4. Server responds with ack -> connection established
    5. Listen for events:
       - "should sync": {"isImportant": <bool>} -> trigger sync
       - "connected devices": [<deviceId>, ...] -> update connected device list
       - "sign out": -> unset current device as primary device
       - "disconnect": -> connection lost, reconnect when conditions met
    """
    import socketio

    sio = socketio.Client()

    @sio.event
    def connect():
        # Emit devicelogin with auth token
        sio.emit("devicelogin", device_auth_token)

    @sio.event
    def disconnect():
        # Connection lost
        pass

    @sio.on("should sync")
    def on_should_sync(data):
        # data = {"isImportant": <bool>}
        is_important = data.get("isImportant", False)
        if is_important:
            trigger_sync(important=True)
        else:
            trigger_sync(important=False)

    @sio.on("connected devices")
    def on_connected_devices(data):
        # data = [<deviceId>, ...]
        update_connected_device_list(data)

    @sio.on("sign out")
    def on_sign_out():
        # Unset current device as primary device
        unset_primary_device()

    sio.connect(server_url, transports=["websocket"])
    return sio
```

### 8.9 Sync Protocol (Action-Based CRDT)

The sync protocol is the core of the connection logic. It uses an action-based approach where all
changes are serialized as JSON actions.

```python
def sync_loop(device_auth_token, server_url, local_state):
    """
    Main sync loop. Runs periodically or when triggered by WebSocket events.

    Flow:
    1. Wait for conditions: network connected + app enabled + sync requested
    2. Rate limit check (token bucket: 30s interval, max 30 tokens)
    3. doSyncRound():
       a. pushActions(): Upload pending actions
       b. pullStatus(): Pull server state
       c. Apply server data
       d. Handle crypto key requests/responses
    4. On UnauthorizedHttpError (401):
       - Check if device removed -> dangerous remote reset
       - Otherwise rethrow
    5. On success: update lastSync
    6. On failure: wait 10-15s, retry
    """
    while True:
        if not local_state.sync_requested:
            wait_for_sync_request()

        # Rate limiting
        if not rate_limit_check():
            sleep(30)
            continue

        try:
            do_sync_round(device_auth_token, server_url, local_state)
            local_state.last_sync = current_time()
        except UnauthorizedHttpError:
            if is_device_removed(device_auth_token, server_url):
                dangerous_remote_reset()
            else:
                raise
        except Exception:
            sleep(random(10, 15))


def push_actions(device_auth_token, server_url, pending_actions):
    """
    Upload pending actions to the server.
    POST /sync/push-actions

    Request body:
    {
        "deviceAuthToken": "<token>",
        "actions": [
            {
                "encodedAction": "<JSON string of the action>",
                "sequenceNumber": <long>,
                "integrity": "<integrity string>",
                "type": "<action type string>",
                "userId": "<user ID>"
            },
            ...
        ]
    }

    Actions are uploaded in batches of 25. Before uploading, actions are marked
    as "scheduled" to prevent duplicates. If the server responds with
    shouldDoFullSync=true, the client wipes all version numbers and does a full sync.

    Response body:
    {
        "shouldDoFullSync": <bool>
    }
    """
    # Batch actions (25 per batch)
    for batch in chunk(pending_actions, 25):
        # Mark actions as scheduled
        for action in batch:
            action.scheduled = True

        body = {
            "deviceAuthToken": device_auth_token,
            "actions": [
                {
                    "encodedAction": action.encoded_action,
                    "sequenceNumber": action.sequence_number,
                    "integrity": action.integrity,
                    "type": action.type,
                    "userId": action.user_id
                }
                for action in batch
            ]
        }

        response = make_http_request(
            endpoint="sync/push-actions",
            body_dict=body,
            server_url=server_url
        )
        data = json.loads(response.body)

        if data["shouldDoFullSync"]:
            # Wipe version numbers and do full sync
            wipe_version_numbers(local_state)
            return

        # Delete confirmed actions
        for action in batch:
            delete_action(action)


def pull_changes(device_auth_token, server_url, local_state):
    """
    Pull server state from the server.
    POST /sync/pull-status

    Request body:
    {
        "deviceAuthToken": "<token>",
        "status": <ClientDataStatus>
    }

    ClientDataStatus structure:
    {
        "clientLevel": 7,
        "devices": "<device list version>",
        "users": "<user list version>",
        "apps": {"<deviceId>": "<installed apps version>", ...},
        "devicesDetail": {"<deviceId>": {"baseVersion": "...", "diffVersion": "..."}, ...},
        "categories": {"<categoryId>": {"baseVersion": "...", "assignedAppsVersion": "...", "timeLimitRulesVersion": "...", "usedTimeItemsVersion": "...", "taskListVersion": "..."}, ...},
        "kri": <last key request server sequence>,
        "kr": <last key response server sequence>,
        "dh": "<dh key version>",
        "u2f": "<u2f version>"
    }

    Response body: ServerDataStatus (see Section 9.7)
    """
    client_status = {
        "clientLevel": 7,
        "devices": local_state.device_list_version,
        "users": local_state.user_list_version,
        "apps": local_state.installed_apps_versions,
        "devicesDetail": local_state.device_detail_data,
        "categories": local_state.category_versions,
        "kri": local_state.last_key_request_sequence,
        "kr": local_state.last_key_response_sequence,
        "dh": local_state.dh_key_version,
        "u2f": local_state.u2f_version
    }

    body = {
        "deviceAuthToken": device_auth_token,
        "status": client_status
    }

    response = make_http_request(
        endpoint="sync/pull-status",
        body_dict=body,
        server_url=server_url
    )

    return parse_server_data_status(json.loads(response.body))


def do_sync_round(device_auth_token, server_url, local_state):
    """
    Execute one sync round: push actions, then pull status.
    """
    # Phase 1: Push actions
    pending_actions = get_pending_actions(local_state)
    if pending_actions:
        push_actions(device_auth_token, server_url, pending_actions)

    # Phase 2: Pull status
    server_data = pull_changes(device_auth_token, server_url, local_state)

    # Phase 3: Apply server data
    apply_server_data_status(server_data, local_state)

    # Phase 4: Handle crypto (key requests, key responses, encrypted app lists)
    handle_crypto_sync(device_auth_token, server_url, local_state, server_data)

    # Phase 5: Handle pings (primary device borrowing)
    handle_pings(device_auth_token, server_url, local_state, server_data)
```

### 8.10 Crypto System

The crypto system provides end-to-end encryption for sensitive data synced between devices, particularly
app lists and parent passwords.

#### Curve25519

- Key pair: 32-byte public + 32-byte private (serialized as 64 bytes)
- Operations: `generateKeyPair()`, `getPublicKey()`, `getPrivateKey()`, `sign()`, `validateSignature()`, `sharedSecret()`
- Signature size: 64 bytes
- Library: WhisperSystems Curve25519 (in Python: `nacl.signing` or `pycryptodome`)

#### AES-GCM CryptContainer

Encrypted app lists use a custom container format:

```python
def crypt_container_format():
    """
    CryptContainer format:

    Header (20 bytes):
    - generation (8 bytes): key rotation counter
    - counter (8 bytes): replay protection counter
    - IV (4 bytes): initialization vector

    AES-GCM:
    - Key: 16 bytes (first 16 bytes of the generation key)
    - IV: 12 bytes (4 bytes IV + 8 bytes counter)
    - AAD: generation + format version (2 bytes)
    - Auth tag: 128 bits

    Format versions:
    - FORMAT_LEGACY (0)
    - FORMAT_APP_LIST_V2 (1)
    - FORMAT_APP_DIFF_V2 (2)
    """
    pass
```

#### Device Signing Key

- Curve25519 key pair stored in `ConfigurationItem.SigningKey`
- Only used when server API level >= 4
- Public key uploaded to server via `UploadDevicePublicKeyAction`
- Used for signing key requests and responses

#### Key Request/Response Protocol

This is a multi-device key exchange protocol for sharing decryption keys (for encrypted app lists):

```python
def key_request_protocol():
    """
    Device A (key holder)          Server          Device B (key requester)
         |                          |                       |
         | 1. SendKeyRequestAction  |                       |
         |    (tempKey, signature)  |                       |
         |------------------------->|                       |
         |                          | 2. Forward to A       |
         |                          |---------------------->|
         |                          |                       |
         | 3. ReplyToKeyRequestAction                        |
         |    (tempKey, encryptedKey, signature)             |
         |<-------------------------|                       |
         |                          | 4. Forward to B       |
         |                          |<----------------------|
         |                          |                       |
         | 5. FinishKeyRequestAction                         |
         |    (marks request as done)                        |
         |------------------------------------------------->|

    Key Request (SendKeyRequestAction):
    - Signed data: "KeyRequestSignedData" + deviceSequenceNumber + deviceId + categoryId + type + tempKey
    - Device A verifies signature with Device B's public key
    - Device A computes shared secret: Curve25519.sharedSecret(request.tempKey, ownPrivateKey)
    - Device A encrypts the generation key: AES/ECB/NoPadding with first 16 bytes of shared secret
    - Device A signs response: "KeyResponseSignedData" + senderDevicePublicKey + tempKey + encryptedKey + request.serialize()

    Key Response (ReplyToKeyRequestAction):
    - Device B verifies signature with Device A's public key
    - Device B computes shared secret: Curve25519.sharedSecret(response.tempKey, ownPrivateKey)
    - Device B decrypts key: AES/ECB/NoPadding with first 16 bytes of shared secret
    - Device B validates key against encrypted data
    - If valid: stores key, marks request as finished
    - If invalid: records CryptContainerKeyResult.InvalidKey
    """
    pass
```

#### DH Key Exchange (ECDH secp256r1)

Used for encrypting parent passwords during family creation:

```python
def dh_handshake(server_dh_key):
    """
    ECDH with secp256r1 curve.

    ServerDhKey JSON format:
    {
        "v": "<key version string>",
        "k": "<base64 encoded EC public key>"
    }

    Steps:
    1. Parse server public key from base64 (X.509 encoded EC point)
    2. Generate own keypair (secp256r1)
    3. Compute shared secret via ECDH
    4. Encrypt data: AES-GCM with 16-byte key (first 16 bytes of shared secret),
       12-byte IV, AAD for authentication
    5. Output format: base64(iv + encryptedData) + "." + base64(ownPublicKey) + "." + keyVersion
    """
    pass


def dh_encrypt(crypt_data, auth_data, server_dh_key):
    """
    Encrypt data using DH shared secret.

    Args:
        crypt_data: data to encrypt (bytes)
        auth_data: additional authenticated data (bytes)
        server_dh_key: ServerDhKey from server response

    Returns:
        "base64(iv + encryptedData).base64(ownPublicKey).keyVersion"
    """
    pass
```

#### Password Hashing (bcrypt)

```python
def password_hashing():
    """
    Uses jBCrypt (bcrypt).

    - hashSync(password): generates salt + hash
    - hashSyncWithSalt(password, salt): hash with specific salt
    - validateSync(password, hash): bcrypt verification

    In Python: use the 'bcrypt' library
        bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        bcrypt.hashpw(password.encode(), salt.encode())
        bcrypt.checkpw(password.encode(), hash.encode())
    """
    pass
```

#### ParentPassword Structure

```python
def parent_password_structure():
    """
    ParentPassword JSON format (sent in createFamilyByMailToken):

    {
        "hash": "<bcrypt hash of password>",
        "secondHash": "<bcrypt hash with second salt, or DH-encrypted>",
        "secondSalt": "<salt for second hash>",
        "encrypted": true/false
    }

    When DH key is available:
    - secondHash is encrypted via DH handshake
    - AAD for encryption: "ParentPassword:<hash>:<secondSalt>"
    """
    pass
```

### 8.11 Action System

All changes to family state are serialized as JSON actions. Actions are uploaded via `push-actions`
and applied locally from `pull-status` responses.

```python
def action_system():
    """
    Action hierarchy:

    Action (sealed)
    +-- AppLogicAction (sealed) -- client-generated actions
    |   +-- AddUsedTimeActionVersion2
    |   +-- SendKeyRequestAction
    |   +-- ReplyToKeyRequestAction
    |   +-- FinishKeyRequestAction
    |   +-- PingAction
    |   +-- UploadDevicePublicKeyAction
    |   +-- AddAppAction
    |   +-- RemoveAppAction
    |   +-- AddCategoryAction
    |   +-- UpdateCategoryAction
    |   +-- RemoveCategoryAction
    |   +-- AddCategoryAppAction          -- for managing allowed apps
    |   +-- RemoveCategoryAppAction       -- for managing allowed apps
    |   +-- AddUsedTimeAction
    |   +-- AddTimeLimitRuleAction
    |   +-- RemoveTimeLimitRuleAction
    |   +-- AddChildTaskAction
    |   +-- RemoveChildTaskAction
    |   +-- AddTemporarilyAllowedAppAction
    |   +-- RemoveTemporarilyAllowedAppAction
    |   +-- UpdateUserAction
    |   +-- RemoveUserAction
    |   +-- UpdateDeviceAction
    |   +-- AddDeviceAction
    |   +-- RemoveDeviceAction
    |   +-- UpdatePrimaryDeviceAction
    |   +-- SetUserCurrentDeviceAction
    |   +-- UpdateCategoryUsedTimeAction
    |   +-- ... (many more)
    +-- ParentAction (sealed) -- parent-initiated actions
    +-- ChildAction (sealed) -- child-initiated actions

    Key Design Principles:
    - Actions are deterministic: same actions in same order -> same state
    - Client generates IDs randomly; server prefixes with family ID
    - Conflict handling: client uploads first, failed actions trigger version wipe
    - Version numbers: random strings, stored per entity type
    - Laggy connection handling: actions marked "once sent" before sending,
      sequence numbers prevent duplicates
    - Server doesn't process duplicate sequence numbers but still sends status

    ActionUploadItem JSON format:
    {
        "encodedAction": "<JSON string of the action>",
        "sequenceNumber": <long>,
        "integrity": "<integrity string>",
        "type": "<PendingSyncActionType string>",
        "userId": "<user ID>"
    }
    """
    pass
```

### 8.12 Managing Allowed Applications (Python Client Use Case)

The Python client's primary goal is to manage allowed applications on other devices and users.
This is done through the sync protocol by uploading actions:

```python
def add_app_to_category(device_auth_token, server_url, category_id, app_package_name, user_id):
    """
    Add an app to a category (i.e., allow an app for a user).

    This creates an AddCategoryAppAction and uploads it via push-actions.
    The server distributes it to all devices, which apply it locally.

    Action JSON (encodedAction field):
    {
        "type": "AddCategoryAppAction",
        "categoryId": "<category ID>",
        "app": "<package name>",
        "userId": "<user ID>"
    }
    """
    action = {
        "type": "AddCategoryAppAction",
        "categoryId": category_id,
        "app": app_package_name,
        "userId": user_id
    }
    upload_action(device_auth_token, server_url, action, user_id)


def remove_app_from_category(device_auth_token, server_url, category_id, app_package_name, user_id):
    """
    Remove an app from a category.

    Action JSON:
    {
        "type": "RemoveCategoryAppAction",
        "categoryId": "<category ID>",
        "app": "<package name>",
        "userId": "<user ID>"
    }
    """
    action = {
        "type": "RemoveCategoryAppAction",
        "categoryId": category_id,
        "app": app_package_name,
        "userId": user_id
    }
    upload_action(device_auth_token, server_url, action, user_id)


def upload_action(device_auth_token, server_url, action, user_id):
    """
    Upload a single action to the server.

    The action is wrapped in an ActionUploadItem with a sequence number
    and integrity hash, then uploaded via push-actions.
    """
    sequence_number = get_next_sequence_number()
    encoded_action = json.dumps(action)
    integrity = compute_integrity(encoded_action)

    body = {
        "deviceAuthToken": device_auth_token,
        "actions": [
            {
                "encodedAction": encoded_action,
                "sequenceNumber": sequence_number,
                "integrity": integrity,
                "type": action["type"],
                "userId": user_id
            }
        ]
    }

    response = make_http_request(
        endpoint="sync/push-actions",
        body_dict=body,
        server_url=server_url
    )

    data = json.loads(response.body)
    if data["shouldDoFullSync"]:
        # Need to do a full sync
        pass
```

### 8.13 Complete Registration Flow (Pseudo Code)

```python
def complete_device_registration(server_url, register_token, device_model, device_name):
    """
    Complete flow for a non-Android Python device to register with an existing family.

    Prerequisites:
    - The parent has already created an add-device token via the Android app
    - The Python device has received the token string

    Returns:
    - device_auth_token: used for all subsequent API calls
    - own_device_id: this device's ID
    - server_data: initial family state (ServerDataStatus)
    """
    # Step 1: Register the child device
    registration = child_register_device(
        server_url=server_url,
        register_token=register_token,
        device_model_name=device_model,
        device_name=device_name
    )

    device_auth_token = registration["deviceAuthToken"]
    own_device_id = registration["ownDeviceId"]
    server_data = registration["serverData"]

    # Step 2: Store credentials
    store_credentials(device_auth_token, own_device_id)

    # Step 3: Apply initial server data
    local_state = LocalState()
    apply_server_data_status(server_data, local_state)

    # Step 4: Connect WebSocket for real-time sync
    websocket = websocket_connect(server_url, device_auth_token)

    # Step 5: Start sync loop (can run in background)

    return {
        "deviceAuthToken": device_auth_token,
        "ownDeviceId": own_device_id,
        "serverData": server_data,
        "localState": local_state,
        "websocket": websocket
    }


def manage_applications_example(device_auth_token, server_url, local_state):
    """
    Example: Python client managing allowed applications.

    After registration, the Python client can:
    1. Pull current state to see existing categories and assigned apps
    2. Upload actions to add/remove apps from categories
    3. The server distributes changes to all devices in the family
    """
    # Pull current state
    server_data = pull_changes(device_auth_token, server_url, local_state)
    apply_server_data_status(server_data, local_state)

    # Find a category for a specific child user
    child_user_id = None
    for user in local_state.users.values():
        if user["type"] == "child":
            child_user_id = user["id"]
            break

    # Find the category for this child
    category_id = None
    for cat in local_state.categories.values():
        if cat["childId"] == child_user_id:
            category_id = cat["categoryId"]
            break

    if category_id:
        # Add an app to the category (allow it)
        add_app_to_category(
            device_auth_token=device_auth_token,
            server_url=server_url,
            category_id=category_id,
            app_package_name="com.example.game",
            user_id=child_user_id
        )

        # Remove an app from the category (block it)
        remove_app_from_category(
            device_auth_token=device_auth_token,
            server_url=server_url,
            category_id=category_id,
            app_package_name="com.example.social",
            user_id=child_user_id
        )

        # Trigger a sync to push the changes
        do_sync_round(device_auth_token, server_url, local_state)
```

### 8.14 Error Handling

```python
def error_handling():
    """
    HTTP error mapping (from HttpErrors.kt):

    | Code | Exception               |
    |------|-------------------------|
    | 400  | BadRequestHttpError     |
    | 401  | UnauthorizedHttpError   |
    | 403  | ForbiddenHttpError      |
    | 404  | NotFoundHttpError       |
    | 409  | ConflictHttpError       |
    | 410  | GoneHttpError           |
    | 429  | TooManyRequestsHttpError|

    Key error scenarios:
    - 401 Unauthorized: device auth token is invalid or device was removed
      -> Check isDeviceRemoved, if true do dangerous remote reset
    - 400 BadRequest: often means clientLevel is not supported
      -> Retry without clientLevel field
    - 429 TooManyRequests: rate limited, wait and retry
    - Network errors: retry with exponential backoff (10-15s initial)
    """
    pass


def is_device_removed(device_auth_token, server_url):
    """
    Check if the device was removed from the family.
    POST /sync/is-device-removed

    Request: {"deviceAuthToken": "<token>"}
    Response: {"isDeviceRemoved": <bool>}
    """
    response = make_http_request(
        endpoint="sync/is-device-removed",
        body_dict={"deviceAuthToken": device_auth_token},
        server_url=server_url
    )
    data = json.loads(response.body)
    return data["isDeviceRemoved"]


def report_device_removed(device_auth_token, server_url):
    """
    Report this device as removed.
    POST /sync/report-removed

    Request: {"deviceAuthToken": "<token>"}
    """
    make_http_request(
        endpoint="sync/report-removed",
        body_dict={"deviceAuthToken": device_auth_token},
        server_url=server_url
    )
```

### 8.15 Python Implementation Notes

```python
def python_implementation_notes():
    """
    Key considerations for implementing the Python client:

    1. HTTP Client:
       - Use 'requests' or 'httpx' library
       - Implement gzip compression for request bodies
       - Handle Content-Length auto-negotiation (411 retry)
       - Certificate pinning: use 'certifi' or custom SSL context
         for production (ISRG Root X1, X2, YE, YR)

    2. WebSocket:
       - Use 'python-socketio' library with WebSocket transport
       - Handle reconnection logic
       - Listen for "should sync", "connected devices", "sign out" events

    3. Crypto:
       - bcrypt: use 'bcrypt' library
       - Curve25519: use 'pynacl' (libsodium bindings)
       - ECDH secp256r1: use 'cryptography' library
       - AES-GCM: use 'cryptography' library

    4. State Management:
       - Store deviceAuthToken and ownDeviceId persistently
       - Track version numbers for sync (deviceListVersion, userListVersion, etc.)
       - Track lastKeyRequestServerSequence and lastKeyResponseServerSequence
       - Store DH key version and U2F version

    5. Sync Loop:
       - Run in background thread
       - Rate limiting: 30s interval, max 30 tokens
       - Sync priorities: important (always), unimportant (foreground only),
         veryUnimportant (last sync > 10 min ago)

    6. Action Integrity:
       - Each action has an integrity hash
       - Sequence numbers prevent duplicates
       - Actions are deterministic

    7. Encrypted App Lists:
       - App lists (TYPE_APP_LIST_BASE, TYPE_APP_LIST_DIFF) are encrypted
       - Use CryptContainer with AES-GCM
       - Key exchange via KeyRequest/Response protocol
       - The Python client may need to participate in key exchange
         if it needs to read encrypted app lists from other devices

    8. Device Info:
       - NewDeviceInfo only requires "model" field
       - Device name can be any string (e.g., "Python Client")

    9. Client Level:
       - Current value: 7
       - Sent in registration and sync requests
       - If server returns 400, retry without it

    10. Server URL:
        - Production: https://api.timelimit.io
        - Development: http://10.0.2.2:8080
        - Custom: stored in ConfigurationItem.CustomServerUrl
    """
    pass

---

## 9. Open Questions / Areas for Further Investigation

1. **Server-side implementation**: The server code is not in this repository. The API endpoints, sync protocol, and crypto protocol are inferred from the client implementation.
2. **Wire protobuf usage**: The `wire` plugin is configured but the proto file (`applist.proto`) appears to be used only for app list sync, not the main sync protocol.
3. **Billing integration**: Google Play Billing is only in the `googleApi` flavor. The `backdoorPublicKey` and `googlePlayKey` are used for verification.
4. **Database migrations**: 50 versions with auto-migrations for 46-50. Older migrations are in `DatabaseMigrations.ALL`.
5. **Accessibility service**: Used for system-level blocking but details are in the platform integration layer.
6. **NFC U2F**: `NFCU2FManager` is referenced but not in the file listing (may be in a different package).
