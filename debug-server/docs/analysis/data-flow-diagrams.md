# Data Flow Diagrams

## Overview

This document contains Mermaid diagrams illustrating the key data flows in the TimeLimit system: authentication flow, sync protocol flow, and the key request/response protocol for encrypted app lists.

## 1. Authentication Flow

**Source**: `context.md` §333, `context_android_app.md` §3.7, §8.4

The authentication flow follows a multi-step process: email verification → code validation → family creation → device registration → initial data pull.

```mermaid
flowchart TD
    A[User enters email] --> B[POST /auth/send-mail-login-code-v2]
    B --> C[Server sends verification code to email]
    C --> D[User enters code]
    D --> E[POST /auth/sign-in-by-mail-code]
    E --> F[Server returns mailAuthToken]
    F --> G[POST /parent/get-status-by-mail-address]
    G --> H[Check family status]
    H --> I{Family exists?}
    I -->|No| J[POST /parent/create-family]
    J --> K[Server creates family with parentPassword]
    K --> L[Server returns deviceAuthToken + ownDeviceId]
    I -->|Yes| M[POST /parent/sign-in-into-family]
    M --> N[Server returns deviceAuthToken + ownDeviceId]
    L --> O[POST /sync/pull-status]
    N --> O
    O --> P[Server returns ServerDataStatus]
    P --> Q[Client applies initial data]
    Q --> R[WebSocket connect + devicelogin]
    R --> S[Sync loop begins]
```

### Child Device Registration Flow

```mermaid
flowchart TD
    A[Parent creates add-device token] --> B[POST /parent/create-add-device-token]
    B --> C[Server returns token + deviceId]
    C --> D[Parent displays token to user]
    D --> E[Child device uses token to register]
    E --> F[POST /child/add-device]
    F --> G[Server returns deviceAuthToken + ownDeviceId]
    G --> H[POST /sync/pull-status]
    H --> I[Server returns ServerDataStatus]
    I --> J[Client applies initial data]
    J --> K[WebSocket connect + devicelogin]
    K --> L[Sync loop begins]
```

## 2. Sync Protocol Flow

**Source**: `context_android_app.md` §3.5, §8.9

The sync protocol uses an action-based CRDT approach. Actions are uploaded in batches of 25, then the client pulls the latest server status.

```mermaid
flowchart TD
    A[Sync requested] --> B[Wait for conditions]
    B --> C[Network connected + app enabled]
    C --> D[Rate limit check]
    D --> E[Rate limit OK?]
    E -->|No| F[Wait 30s]
    F --> D
    E -->|Yes| G[doSyncRound]
    G --> H[Phase 1: pushActions]
    H --> I[Get pending actions]
    I --> J[Batch actions 25 per batch]
    J --> K[Mark actions as scheduled]
    K --> L[POST /sync/push-actions]
    L --> M[Server returns shouldDoFullSync]
    M --> N{shouldDoFullSync?}
    N -->|Yes| O[Wipe version numbers]
    O --> P[Full sync on next pull]
    N -->|No| Q[Delete confirmed actions]
    Q --> R[More batches?]
    R -->|Yes| J
    R -->|No| S[Phase 2: pullStatus]
    S --> T[Build ClientDataStatus]
    T --> U[POST /sync/pull-status]
    U --> V[Server returns ServerDataStatus]
    V --> W[Phase 3: Apply server data]
    W --> X[Update local database]
    X --> Y[Phase 4: Handle crypto]
    Y --> Z[Key requests, key responses, encrypted app lists]
    Z --> AA[Phase 5: Handle pings]
    AA --> AB[Primary device borrowing via ping/pong]
    AB --> AC[Sync complete]
    AC --> AD[Update lastSync]
    AD --> AE[Wait for next sync request]
    AE --> A
```

### Push-Actions Request/Response

```mermaid
sequenceDiagram
    participant C as Client
    participant S as Server

    C->>S: POST /sync/push-actions
    Note over C,S: deviceAuthToken + actions array
    Note over C,S: Each action: encodedAction, sequenceNumber, integrity, type, userId
    Note over C,S: Batch size: 25 actions max

    S-->>C: shouldDoFullSync: bool
    Note over C,S: If true, client wipes version numbers
```

### Pull-Status Request/Response

```mermaid
sequenceDiagram
    participant C as Client
    participant S as Server

    C->>S: POST /sync/pull-status
    Note over C,S: deviceAuthToken + status: ClientDataStatus
    Note over C,S: ClientDataStatus: clientLevel, devices, users, apps, devicesDetail, categories, kri, kr, dh, u2f

    S-->>C: ServerDataStatus
    Note over C,S: devices, devices2, apps, rmCategories, categoryBase, categoryApp, usedTimes, rules, tasks, users, krq, kr, pings, dh, u2f, fullVersion, message, apiLevel
```

## 3. Key Request/Response Protocol

**Source**: `context_android_app.md` §3.6, §8.10

This is a multi-device key exchange protocol for sharing decryption keys for encrypted app lists. Device B (key requester) needs a decryption key that Device A (key holder) possesses.

```mermaid
sequenceDiagram
    participant A as Device A (key holder)
    participant S as Server
    participant B as Device B (key requester)

    B->>S: SendKeyRequestAction
    Note over B,S: tempKey, signature
    Note over B,S: Signed data: KeyRequestSignedData + deviceSequenceNumber + deviceId + categoryId + type + tempKey

    S->>A: Forward key request
    Note over S,A: Via sync/pull-status (krq field)

    A->>S: ReplyToKeyRequestAction
    Note over A,S: tempKey, encryptedKey, signature
    Note over A,S: Device A verifies B's signature with B's public key
    Note over A,S: Device A computes shared secret: Curve25519.sharedSecret(request.tempKey, ownPrivateKey)
    Note over A,S: Device A encrypts generation key: AES/ECB/NoPadding with first 16 bytes of shared secret
    Note over A,S: Device A signs response: KeyResponseSignedData + senderDevicePublicKey + tempKey + encryptedKey + request.serialize()

    S->>B: Forward key response
    Note over S,B: Via sync/pull-status (kr field)

    B->>S: FinishKeyRequestAction
    Note over B,S: Marks request as done
    Note over B,S: Device B verifies A's signature with A's public key
    Note over B,S: Device B computes shared secret: Curve25519.sharedSecret(response.tempKey, ownPrivateKey)
    Note over B,S: Device B decrypts key: AES/ECB/NoPadding with first 16 bytes of shared secret
    Note over B,S: Device B validates key against encrypted data
    Note over B,S: If valid: stores key, marks request as finished
    Note over B,S: If invalid: records CryptContainerKeyResult.InvalidKey
```

## 4. Crypto System Overview

**Source**: `context.md` §338–344, `context_android_app.md` §3.6

```mermaid
classDiagram
    class BcryptHasher {
        +hash_password(password)
        +verify_password(password, hash)
        +hash_password_with_salt(password, salt)
    }
    class HmacSigner {
        +calculate_hmac_sha256(second_hash, seq, device_id, action)
        +calculate_hmac_sha512(key_base64, message)
        +calculate_sha512_hex(message)
    }
    class AesGcmCrypt {
        +encrypt_data(plaintext, key)
        +decrypt_data(ciphertext, key)
        +CryptContainer class
    }
    class Curve25519 {
        +generate_keypair()
        +sign(private_key, message)
        +verify(public_key, message, signature)
        +shared_secret(private_key, public_key)
    }
    class DhHandshake {
        +dh_handshake(server_dh_key)
        +dh_encrypt(crypt_data, auth_data, server_dh_key)
    }
    class JwtManager {
        +generate_token(user_id, device_id, expires_delta)
        +validate_token(token)
        +decode_token(token)
    }

    BcryptHasher --> HmacSigner : used together
    AesGcmCrypt --> Curve25519 : uses shared secret
    DhHandshake --> AesGcmCrypt : encrypts parent passwords
    JwtManager --> BcryptHasher : validates user credentials
```

## 5. WebSocket Connection Flow

**Source**: `context_android_app.md` §3.4

```mermaid
sequenceDiagram
    participant App as Android App
    participant WS as WebSocket Server
    participant S as Sync Server

    App->>WS: Connect (Socket.IO, WebSocket transport)
    Note over App,WS: deviceAuthToken in connection

    WS->>App: connect event
    App->>WS: Emit devicelogin with auth token
    WS->>App: Ack (connection established)

    WS->>App: should sync event
    Note over WS,App: {isImportant: Boolean}
    App->>S: Trigger sync (push-actions + pull-status)

    WS->>App: connected devices event
    Note over WS,App: [deviceId, ...]
    App->>App: Update connected device list

    WS->>App: sign out event
    App->>App: Unset current device as primary device

    App->>WS: disconnect
    App->>WS: Reconnect when conditions met
```

## 6. Error Handling Flow

**Source**: `context_android_app.md` §3.2, §8.14

```mermaid
flowchart TD
    A[HTTP Request] --> B[Server processes request]
    B --> C{Error occurred?}
    C -->|No| D[Return 200 OK]
    C -->|Yes| E[Return error code]
    E --> F{Code 400?}
    F -->|Yes| G[BadRequestHttpError]
    F -->|No| H{Code 401?}
    H -->|Yes| I[UnauthorizedHttpError]
    I --> J[Check isDeviceRemoved]
    J --> K{Device removed?}
    K -->|Yes| L[Dangerous remote reset]
    K -->|No| M[Rethrow error]
    H -->|No| N{Code 403?}
    N -->|Yes| O[ForbiddenHttpError]
    N -->|No| P{Code 404?}
    P -->|Yes| Q[NotFoundHttpError]
    P -->|No| R{Code 409?}
    R -->|Yes| S[ConflictHttpError]
    R -->|No| T{Code 410?}
    T -->|Yes| U[GoneHttpError]
    T -->|No| V{Code 429?}
    V -->|Yes| W[TooManyRequestsHttpError]
    V -->|No| X[Other error]
    W --> Y[Wait and retry]
    X --> Z[Retry with exponential backoff]
```
