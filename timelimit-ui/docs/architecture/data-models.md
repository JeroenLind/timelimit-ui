# Data Models

## Table of Contents

1. [Overview](#overview)
2. [Database Schema](#database-schema)
3. [Table Definitions](#table-definitions)
   - [server_checks](#server_checks)
   - [families](#families)
   - [devices](#devices)
   - [auth_tokens](#auth_tokens)
   - [users](#users)
   - [sync_state](#sync_state)
   - [categories](#categories)
   - [connected_devices](#connected_devices)
   - [time_limit_rules](#time_limit_rules)
4. [Password Hashing](#password-hashing)
5. [Days Bitmask](#days-bitmask)
6. [Foreign Key Relationships](#foreign-key-relationships)

---

## Overview

Dashboard V2 uses SQLite with 9 tables for local data storage. All tables use `device_auth_token` as the primary key or foreign key, matching the official Android app's approach.

### Table Overview

| Table | Purpose | Primary Key |
|-------|---------|-------------|
| `server_checks` | Timechecker results | `id` (AUTOINCREMENT) |
| `families` | Family account information | `device_auth_token` |
| `devices` | Device registration data | `id` |
| `auth_tokens` | Authentication tokens | `id` (AUTOINCREMENT) |
| `users` | User data from TimeLimit sync | `id` |
| `sync_state` | Sync version tracking | `device_auth_token` |
| `categories` | TimeLimit categories | `id` |
| `connected_devices` | Real-time connected device tracking | `(device_auth_token, device_id)` |
| `time_limit_rules` | Local time limit rules | `id` |

---

## Table Definitions

### server_checks

Stores historical server check results from the APScheduler timechecker.

```sql
CREATE TABLE server_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    success INTEGER NOT NULL,
    error_code TEXT,
    user_message TEXT,
    technical_detail TEXT,
    server_time INTEGER,
    attempts INTEGER DEFAULT 0,
    server_url TEXT NOT NULL
)
```

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Auto-incrementing primary key |
| `timestamp` | INTEGER | Unix timestamp in milliseconds |
| `success` | INTEGER | 1 for success, 0 for failure |
| `error_code` | TEXT | Error code if failed |
| `user_message` | TEXT | User-friendly error message |
| `technical_detail` | TEXT | Technical details for debugging |
| `server_time` | INTEGER | Server time in milliseconds |
| `attempts` | INTEGER | Number of connection attempts |
| `server_url` | TEXT | The server URL that was checked |

---

### families

Stores family account information, keyed by `device_auth_token`.

```sql
CREATE TABLE families (
    device_auth_token TEXT PRIMARY KEY,
    mail TEXT NOT NULL,
    created_at TEXT NOT NULL,
    parent_password_hash TEXT,
    parent_password_second_hash TEXT,
    parent_password_second_salt TEXT,
    parent_password_encrypted INTEGER DEFAULT 0,
    parent_user_id TEXT
)
```

| Column | Type | Description |
|--------|------|-------------|
| `device_auth_token` | TEXT | Primary key, unique device token |
| `mail` | TEXT | Parent email address |
| `created_at` | TEXT | ISO 8601 timestamp of family creation |
| `parent_password_hash` | TEXT | Bcrypt hash of parent password |
| `parent_password_second_hash` | TEXT | Second bcrypt hash for device removal |
| `parent_password_second_salt` | TEXT | Salt for second hash regeneration |
| `parent_password_encrypted` | INTEGER | 1 if secondHash is DH-encrypted |
| `parent_user_id` | TEXT | User ID of the parent account |

---

### devices

Stores device registration data for all devices in the family.

```sql
CREATE TABLE devices (
    id TEXT PRIMARY KEY,
    device_auth_token TEXT NOT NULL,
    name TEXT,
    model TEXT,
    created_at TEXT NOT NULL,
    current_user_id TEXT,
    current_protection_level INTEGER DEFAULT 0,
    highest_protection_level INTEGER DEFAULT 0,
    current_app_version TEXT,
    highest_app_version TEXT,
    public_key TEXT,
    platform_type TEXT,
    platform_level INTEGER DEFAULT 0,
    FOREIGN KEY (device_auth_token) REFERENCES families(device_auth_token)
)
```

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | Unique device identifier |
| `device_auth_token` | TEXT | Foreign key to families |
| `name` | TEXT | Device display name |
| `model` | TEXT | Device model |
| `created_at` | TEXT | ISO 8601 timestamp |
| `current_user_id` | TEXT | Current user's ID |
| `current_protection_level` | INTEGER | Current protection level (0-3) |
| `highest_protection_level` | INTEGER | Highest protection level achieved |
| `current_app_version` | TEXT | Current app version |
| `highest_app_version` | TEXT | Highest app version seen |
| `public_key` | TEXT | Public key for encryption |
| `platform_type` | TEXT | Platform type (android, etc.) |
| `platform_level` | INTEGER | Platform level |

---

### auth_tokens

Stores authentication tokens for session management.

```sql
CREATE TABLE auth_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_type TEXT NOT NULL,
    token_value TEXT NOT NULL UNIQUE,
    device_id TEXT,
    mail TEXT,
    code TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    FOREIGN KEY (device_id) REFERENCES devices(id)
)
```

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Auto-incrementing primary key |
| `token_type` | TEXT | Type: `mail_login_token`, `mail_auth_token`, `device_auth_token` |
| `token_value` | TEXT | The actual token string |
| `device_id` | TEXT | Associated device ID |
| `mail` | TEXT | Associated email |
| `code` | TEXT | Verification code |
| `created_at` | TEXT | ISO 8601 timestamp |
| `expires_at` | TEXT | Expiration timestamp |

---

### users

Stores user data synchronized from the TimeLimit server.

```sql
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    device_auth_token TEXT NOT NULL,
    name TEXT,
    password TEXT,
    second_password_salt TEXT,
    type TEXT,
    time_zone TEXT,
    disable_limits_until INTEGER,
    mail TEXT,
    current_device TEXT,
    category_for_not_assigned_apps TEXT,
    relax_primary_device INTEGER DEFAULT 0,
    flags INTEGER DEFAULT 0,
    limit_login_category TEXT,
    pre_block_duration INTEGER DEFAULT 0,
    last_updated INTEGER,
    FOREIGN KEY (device_auth_token) REFERENCES families(device_auth_token)
)
```

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | Unique user ID |
| `device_auth_token` | TEXT | Foreign key to families |
| `name` | TEXT | User display name |
| `password` | TEXT | User password hash |
| `second_password_salt` | TEXT | Salt for second password |
| `type` | TEXT | `parent` or `child` |
| `time_zone` | TEXT | User's time zone |
| `disable_limits_until` | INTEGER | Unix timestamp to disable limits |
| `mail` | TEXT | User email |
| `current_device` | TEXT | Current device name |
| `category_for_not_assigned_apps` | TEXT | Default category |
| `relax_primary_device` | INTEGER | Relax primary device flag |
| `flags` | INTEGER | User flags |
| `limit_login_category` | TEXT | Category for limit login |
| `pre_block_duration` | INTEGER | Pre-block duration in minutes |
| `last_updated` | INTEGER | Last update timestamp |

---

### sync_state

Tracks sync version numbers and sequence numbers for CRDT synchronization.

```sql
CREATE TABLE sync_state (
    device_auth_token TEXT PRIMARY KEY,
    device_list_version TEXT,
    user_list_version TEXT,
    last_sync_timestamp INTEGER,
    last_sync_success INTEGER,
    next_sequence_number INTEGER DEFAULT 0,
    FOREIGN KEY (device_auth_token) REFERENCES families(device_auth_token)
)
```

| Column | Type | Description |
|--------|------|-------------|
| `device_auth_token` | TEXT | Primary key |
| `device_list_version` | TEXT | Version of device list |
| `user_list_version` | TEXT | Version of user list |
| `last_sync_timestamp` | INTEGER | Last sync timestamp |
| `last_sync_success` | INTEGER | 1 if last sync succeeded |
| `next_sequence_number` | INTEGER | Next sequence number for sync |

---

### categories

Stores TimeLimit category data.

```sql
CREATE TABLE categories (
    id TEXT PRIMARY KEY,
    device_auth_token TEXT NOT NULL,
    child_id TEXT,
    title TEXT,
    blocked_times TEXT,
    extra_time INTEGER,
    extra_time_day INTEGER,
    temp_blocked INTEGER DEFAULT 0,
    temp_block_time INTEGER,
    version TEXT,
    parent_category_id TEXT,
    block_all_notifications INTEGER DEFAULT 0,
    time_warnings INTEGER DEFAULT 0,
    sort_order INTEGER DEFAULT 0,
    flags INTEGER DEFAULT 0,
    last_updated INTEGER,
    FOREIGN KEY (device_auth_token) REFERENCES families(device_auth_token)
)
```

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | Unique category ID |
| `device_auth_token` | TEXT | Foreign key to families |
| `child_id` | TEXT | Child user ID |
| `title` | TEXT | Category title |
| `blocked_times` | TEXT | Blocked time periods |
| `extra_time` | INTEGER | Extra time in minutes |
| `extra_time_day` | INTEGER | Extra time for the day |
| `temp_blocked` | INTEGER | Temporary blocked flag |
| `temp_block_time` | INTEGER | Temporary block time |
| `version` | TEXT | Category version |
| `parent_category_id` | TEXT | Parent category ID |
| `block_all_notifications` | INTEGER | Block all notifications flag |
| `time_warnings` | INTEGER | Time warnings flag |
| `sort_order` | INTEGER | Sort order |
| `flags` | INTEGER | Category flags |
| `last_updated` | INTEGER | Last update timestamp |

---

### connected_devices

Tracks devices currently connected to the server.

```sql
CREATE TABLE connected_devices (
    device_auth_token TEXT NOT NULL,
    device_id TEXT NOT NULL,
    last_seen INTEGER,
    name TEXT,
    PRIMARY KEY (device_auth_token, device_id),
    FOREIGN KEY (device_auth_token) REFERENCES families(device_auth_token)
)
```

| Column | Type | Description |
|--------|------|-------------|
| `device_auth_token` | TEXT | Foreign key to families |
| `device_id` | TEXT | Device ID |
| `last_seen` | INTEGER | Last seen timestamp |
| `name` | TEXT | Device name |

---

### time_limit_rules

Stores local time limit rules for users.

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

## Password Hashing

Dashboard V2 uses bcrypt for password hashing with the `$2a$` prefix.

### Hash Format

```
$2a$10$<22-character-salt><31-character-hash>
```

### Password Hash Fields

| Field | Purpose |
|-------|---------|
| `parent_password_hash` | First hash, used for general authentication |
| `parent_password_second_hash` | Second hash, used for device removal operations |
| `parent_password_second_salt` | Salt for regenerating the second hash |

### Hash Regeneration

When a parent sets their password:
1. Generate first hash: `bcrypt.hash(password)`
2. Generate second hash: `bcrypt.hash(password, salt=existing_salt)`
3. Store both hashes and the salt

This allows the same second hash to be regenerated from the same password and salt, enabling device removal operations.

---

## Days Bitmask

Days are represented as a bitmask (0-127) in the `time_limit_rules` table:

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

## Foreign Key Relationships

```
families (device_auth_token)
    │
    ├── devices (device_auth_token)
    ├── users (device_auth_token)
    ├── sync_state (device_auth_token)
    ├── categories (device_auth_token)
    └── connected_devices (device_auth_token)
        └── time_limit_rules (device_auth_token)
            ├── users.id (user_id)
            └── categories.id (category_id)
```

### Relationship Diagram

```mermaid
erDiagram
    families ||--o{ devices : "device_auth_token"
    families ||--o{ users : "device_auth_token"
    families ||--o{ sync_state : "device_auth_token"
    families ||--o{ categories : "device_auth_token"
    families ||--o{ connected_devices : "device_auth_token"
    users ||--o{ time_limit_rules : "user_id"
    categories ||--o{ time_limit_rules : "category_id"
    devices ||--o{ auth_tokens : "device_id"