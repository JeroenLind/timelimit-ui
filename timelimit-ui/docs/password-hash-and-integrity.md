# Password hashes and integrity checks

This document describes how the dashboard currently derives password hashes and integrity values for sync actions. Use this as the reference point if future changes break compatibility.

## Scope and current behavior

- We always talk to an up-to-date server (apiLevel >= 6).
- Parent action integrity uses HMAC-SHA256 in a binary format and is prefixed with "password:".
- If required data is missing, the dashboard falls back to "device" integrity.

## Data flow overview

1. User supplies the parent password via the "Wachtwoord Hashes Bijwerken" dialog.
2. The backend generates or regenerates the bcrypt hash values.
3. The dashboard stores the relevant hashes in localStorage.
4. For each parent action, the dashboard calculates integrity using server-side HMAC-SHA256.

## Password hash handling

### Generation / regeneration

Source: rootfs/usr/bin/web_server.py and rootfs/usr/bin/crypto_utils.py

- When the user enters the password, the UI calls:
  - /regenerate-hash if a server secondPasswordSalt is available.
  - /generate-hashes if no salt is available (new family flow).
- /regenerate-hash uses bcrypt.hashpw(password, second_salt).
- /generate-hashes generates two bcrypt hashes with cost factor 12:
  - hash (first hash)
  - secondHash (second hash)
  - secondSalt (salt used for secondHash)

### Local storage

Source: rootfs/usr/bin/state.js

The dashboard stores the following object in localStorage under the key:

- timelimit_parentPasswordHash
  - hash
  - secondHash
  - secondSalt

Notes:

- secondHash is the bcrypt hash string (example: $2a$12$...).
- secondSalt is converted to standard base64 when the value is a bcrypt salt.

## Integrity calculation (apiLevel >= 6)

Source: rootfs/usr/bin/sync.js and rootfs/usr/bin/crypto_utils.py

### Inputs

For each parent action:

- sequenceNumber (integer)
- deviceId (string)
- encodedAction (JSON string)
- secondHash (bcrypt hash string)

### Algorithm

Integrity is computed as:

- HMAC-SHA256
- Key: secondHash (UTF-8 bytes)
- Message: a binary format described below
- Output: base64-encoded HMAC digest
- Final integrity string: "password:" + base64_digest

### Binary message format

The message is the concatenation of:

1. sequenceNumber as 8-byte big-endian unsigned integer
2. deviceId length as 4-byte big-endian unsigned integer
3. deviceId bytes (UTF-8)
4. encodedAction length as 4-byte big-endian unsigned integer
5. encodedAction bytes (UTF-8)

### Example values (illustrative)

Inputs:

- sequenceNumber: 42
- deviceId: "demo-device"
- encodedAction: "{\"type\":\"PARENT_ACTION\",\"action\":\"LOCK\"}"
- secondHash: "$2a$12$exampleexampleexampleexampleexampleexampleexample"

Derived details:

- deviceId length: 11
- encodedAction length: 45
- integrity format: "password:<base64-hmac>"

Example integrity string shape:

- password:QWJjZEVmZ0hJSktMTU5PUA==

Note: The integrity string above is a placeholder to illustrate format only, not a real digest.

### Where it is calculated

The UI requests server-side calculation:

- POST /calculate-hmac-sha256
- Returns { "integrity": "password:<base64>" }

If the response fails or required data is missing, the UI falls back to:

- integrity = "device"

## Sequence numbers

Source: rootfs/usr/bin/sync.js

- Stored in localStorage under timelimit_nextSyncSequenceNumber.
- Each prepared action consumes the next sequence number.

## Server apiLevel

Source: rootfs/usr/bin/sync.js

- Stored in localStorage under timelimit_serverApiLevel.
- For current environments, apiLevel is expected to be >= 6.

## Reference locations (implementation)

- rootfs/usr/bin/crypto_utils.py
  - generate_family_hashes
  - regenerate_second_hash
  - calculate_hmac_sha256_binary
- rootfs/usr/bin/web_server.py
  - /generate-hashes
  - /regenerate-hash
  - /calculate-hmac-sha256
- rootfs/usr/bin/state.js
  - storeparentPasswordHashForSync
  - loadParentPasswordHashFromStorage
- rootfs/usr/bin/sync.js
  - calculateIntegrity
  - sequence number helpers

## Troubleshooting

- Integrity is "device": ensure parent password hashes are stored in localStorage and secondHash is present.
- Integrity mismatch on server: confirm sequenceNumber increments and matches the server state.
- Server rejects integrity: verify the server apiLevel is >= 6 and /calculate-hmac-sha256 is reachable.
- Unexpected hash regeneration: verify secondPasswordSalt is used for /regenerate-hash.
- Empty or corrupted hash values: re-run "Wachtwoord Hashes Bijwerken" and check localStorage.

## Rollback checklist

If future changes cause signing failures:

1. Compare new logic to the binary format described above.
2. Verify the key is the bcrypt secondHash string (not the salt).
3. Verify the "password:" prefix and base64 digest.
4. Confirm sequenceNumber and deviceId inputs match the current flow.
5. Restore the current behavior if any deviation is found.
