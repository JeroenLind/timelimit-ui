# KeyFamilyData.md - Family Creation Audit Log

> **⚠️ ACCESS RESTRICTION NOTICE**
> 
> This file contains sensitive data including:
> - Password hashes (bcrypt)
> - Email addresses
> - Device authentication tokens
> - Parent names
> 
> **DO NOT SHARE** this file with unauthorized personnel.
> **DO NOT COMMIT** this file to version control.
> **DO NOT EXPOSE** this file via web server or API.
> 
> Access is restricted to authorized administrators only.
> Handle in accordance with data protection regulations.

---

## Table of Contents
- [Family Creation Entries](#family-creation-entries)

---

## Family Creation Entries

### Entry 1: Family Creation Request (2026-09-05T10:41:55.456616Z)

**Request ID:** `61f575fd`

#### User Information
- **Parent Name:** Jeroen2
- **Email:** pietje3@test.nl
- **Password:** 12345678
- **Time Zone:** Europe/Amsterdam
- **Locale:** en

#### Password Data (bcrypt hashes)
- **Primary Password Hash:** `$2a$12$mXJZGbKUlLVlAhIleE96H.hbKUliS0Iae52DrH45JA9lD6iD4.wg.`
- **Second Password Hash:** `$2a$12$GH3WX.UWo.gdKkWy0j/K9udedcl/fv9CkSbTRghbIY66Eeo.jY1.K`
- **Second Password Salt:** `$2a$12$GH3WX.UWo.gdKkWy0j/K9u`

#### Authentication Tokens
- **Mail Login Token:** `jekkWbBY1gEdrSK2AOMpAsv2ArjNjq7Y`
- **Mail Auth Token:** `t6552Rgvoq4jDFt8LRngjWWdyyyadjYs`
- **Device Auth Token:** `Yu0qaxaBYqby2L1zPqQBeGqhfuR0A14n`

#### Device Information
- **Device Name:** LaptopZXC
- **Device Model:** WindowsZXC
- **Own Device ID:** EIrFOT
- **Current User ID:** QFJ3Tl

#### Server Information
- **Server URL:** http://192.168.68.30:8080
- **Server Key:** local

#### Cryptographic Keys
- **DH Key (Diffie-Hellman):** `MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAELSbe+NVxCAjmFUFVc/UshV4KypydgNLueCuplyhQRxj1SJvevLuBDQDiXgTEhMpSiasXa2LHa7H3XyHJtf8vGQ==`
- **DH Version:** 6DRR
- **U2F Version:** YsIx

#### API Endpoints Used
- `POST /auth/send-mail-login-code-v2` - Send mail login code
- `POST /auth/sign-in-by-mail-code` - Sign in by mail code
- `POST /parent/create-family` - Create family
- `POST /sync/pull-status` - Pull status
- `POST /sync/pull` - Sync pull

#### Verification Code
- **Received Code:** Perle dick Zither

---

### Entry 2: Family Creation Response (2026-09-05T10:41:57.077015Z)

**Status:** Success (HTTP 200)

#### Response Data
- **Device Auth Token:** `Yu0qaxaBYqby2L1zPqQBeGqhfuR0A14n`
- **Own Device ID:** EIrFOT
- **API Level:** 8
- **Full Version:** 1789814515592

#### Device Details (from response)
- **Device ID:** EIrFOT
- **Name:** LaptopZXC
- **Model:** WindowsZXC
- **Added At:** 1788604915795 (Unix timestamp)
- **Network Time:** disabled
- **Protection Levels:** none (both c and h)
- **Usage Stats:** not granted
- **Notification Access:** not granted
- **App Version:** 0
- **User Kept Signed In:** true

#### User Details (from response)
- **User ID:** QFJ3Tl
- **Name:** Jeroen2
- **Type:** parent
- **Password Hash:** `$2a$12$mXJZGbKUlLVlAhIleE96H.hbKUliS0Iae52DrH45JA9lD6iD4.wg.`
- **Second Password Salt:** `$2a$12$GH3WX.UWo.gdKkWy0j/K9u`
- **Mail:** pietje3@test.nl
- **Time Zone:** Europe/Amsterdam
- **Mail Notification Flags:** 3

#### Sync Information
- **Client Level:** 7
- **Devices Version:** RWe0
- **Users Version:** Wq0F

---

### Entry 3: Sync Operations (2026-09-05T10:41:57.101314Z - 10:41:58.674172Z)

#### Sync Pull Request
- **Request ID:** 61f575fd
- **Device Auth Token:** Yu0qaxaBYqby2L1zPqQBeGqhfuR0A14n
- **Status:** Success (HTTP 200)

#### Sync Completion
- **Request ID:** 61f575fd
- **Event:** Sync completed successfully after family creation
- **Timestamp:** 2026-09-05T10:41:57.858642Z

---

## Troubleshooting Notes

This section is reserved for manual troubleshooting notes and observations.

### Common Issues

1. **Family ID Not Found**
   - Verify the device_auth_token matches the server response
   - Check that the family was created successfully on the server
   - Ensure the token hasn't expired

2. **Password Hash Mismatch**
   - Verify bcrypt rounds match (default: 12)
   - Ensure hash format is correct ($2a$ prefix)
   - Check that the same password was used for both hashes

3. **Email Verification Issues**
   - Verify the mail_login_token is still valid
   - Check that the verification code was entered correctly
   - Ensure the email address is correct

### Manual Notes

_Add your troubleshooting notes here:_