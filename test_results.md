# Test Results: Create Family Flow Endpoints

## Test Environment
- **Debug Server**: Running at http://localhost:8081 (FastAPI)
- **Dashboard V2**: Running at http://localhost:8099 (Flask)
- **Test Date**: 2026-08-16

## Test Data Files Read
1. `create_family_data.json` - Contains mailAuthToken, parentPassword, locale, deviceName, deviceModel
2. `sign_in_data.json` - Contains mailLoginToken and receivedCode (3-word passphrase)
3. `test_data.json` - Contains test email address

## Debug-Server Endpoint Tests

### 1. POST /auth/send-mail-login-code-v2
**Test Command:**
```bash
curl -s -X POST http://localhost:8081/auth/send-mail-login-code-v2 \
  -H "Content-Type: application/json" \
  --data @test_send_mail.json
```

**Test Data:**
```json
{"mail": "test@example.com", "locale": "en"}
```

**Result:** ✅ PASS
**Response:**
```json
{
  "status": "ok",
  "mailLoginToken": "j2RTE4-LBY6hyRiY7xFQUHpEUAc9FrEwCzLASOdtHAM",
  "mailServerBlacklisted": false,
  "mailAddressNotWhitelisted": false,
  "blockedForIntegrityReasons": false,
  "mailServerBlacklistedTemporarily": false
}
```

### 2. POST /auth/sign-in-by-mail-code
**Test Command:**
```bash
curl -s -X POST http://localhost:8081/auth/sign-in-by-mail-code \
  -H "Content-Type: application/json" \
  --data @test_sign_in_v2.json
```

**Test Data:**
```json
{"mailLoginToken": "j2RTE4-LBY6hyRiY7xFQUHpEUAc9FrEwCzLASOdtHAM", "receivedCode": "Haus Regen Tisch"}
```

**Result:** ✅ PASS
**Response:**
```json
{
  "status": "ok",
  "mailAuthToken": "3q5pQ1EsFtU3DikIzpjkkJUuQiZ1tbfvL5XtysJbUiw"
}
```

### 3. POST /parent/create-family
**Test Command:**
```bash
curl -s -X POST http://localhost:8081/parent/create-family \
  -H "Content-Type: application/json" \
  --data @test_create_family_v3.json
```

**Test Data:**
```json
{
  "mailAuthToken": "3q5pQ1EsFtU3DikIzpjkkJUuQiZ1tbfvL5XtysJbUiw",
  "parentPassword": {
    "hash": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.VTtYA/7.J6LlZy",
    "secondHash": "$2b$12$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi",
    "secondSalt": "$2b$12$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi",
    "encrypted": false
  },
  "parentDevice": {
    "model": "Test Model"
  },
  "deviceName": "Test Device",
  "timeZone": "Europe/Amsterdam",
  "parentName": "Test Parent",
  "locale": "en"
}
```

**Result:** ✅ PASS (First time)
**Response:**
```json
{
  "status": "ok",
  "deviceAuthToken": "SiG_bPXyKPgx0TVNTmv2bFiajYSAtf0HaMOWwHuINnI",
  "ownDeviceId": "device_9B4lm-rJdXiGOtHurTHm_Q",
  "data": {
    "devices": {"version": "1", "data": []},
    "users": {"version": "1", "data": []},
    "apps": [],
    "rmCategories": [],
    "categoryBase": [],
    "categoryApp": [],
    "usedTimes": [],
    "rules": [],
    "tasks": [],
    "krq": [],
    "kr": [],
    "pings": [],
    "dh": {"v": "1", "k": ""},
    "u2f": {"v": "1", "d": []},
    "fullVersion": 0,
    "message": "",
    "apiLevel": 1
  }
}
```

## Edge Case Tests

### 4. Missing mailAuthToken
**Test Data:**
```json
{
  "parentPassword": {
    "hash": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.VTtYA/7.J6LlZy",
    "secondHash": "$2b$12$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi",
    "secondSalt": "$2b$12$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi",
    "encrypted": false
  },
  "parentDevice": {
    "model": "Test Model"
  },
  "deviceName": "Test Device",
  "timeZone": "Europe/Amsterdam",
  "parentName": "Test Parent"
}
```

**Result:** ✅ PASS
**Response:** HTTP 422 Unprocessable Content
```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "mailAuthToken"],
      "msg": "Field required"
    }
  ]
}
```

### 5. Missing parentPassword
**Test Data:**
```json
{
  "mailAuthToken": "invalid_token_12345"
}
```

**Result:** ✅ PASS
**Response:** HTTP 422 Unprocessable Content
```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "parentPassword"],
      "msg": "Field required"
    }
  ]
}
```

### 6. Invalid mailAuthToken
**Test Data:**
```json
{
  "mailAuthToken": "invalid_token_12345",
  "parentPassword": {
    "hash": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.VTtYA/7.J6LlZy",
    "secondHash": "$2b$12$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi",
    "secondSalt": "$2b$12$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi",
    "encrypted": false
  },
  "parentDevice": {
    "model": "Test Model"
  },
  "deviceName": "Test Device",
  "timeZone": "Europe/Amsterdam",
  "parentName": "Test Parent"
}
```

**Result:** ✅ PASS
**Response:** HTTP 401 Unauthorized
```json
{
  "detail": "Invalid mail auth token"
}
```

### 7. Family Already Exists
**Test Data:** Same as test 3

**Result:** ✅ PASS
**Response:** HTTP 400 Bad Request
```json
{
  "detail": "Family already exists for this email"
}
```

## Dashboard V2 Endpoint Tests

### POST /api/families
**Status:** ✅ PASS

The dashboardV2 correctly:
1. Accepts `parentDevice: { model: "string" }` format (matching official API)
2. Converts `deviceModel` from form data to `parentDevice: { model: deviceModel }`
3. Passes all required fields: `mailAuthToken`, `parentPassword`, `parentDevice`, `deviceName`, `timeZone`, `parentName`, `locale`

## Summary

| Test Case | Endpoint | Result |
|-----------|----------|--------|
| Send mail login code | POST /auth/send-mail-login-code-v2 | ✅ PASS |
| Sign in by mail code | POST /auth/sign-in-by-mail-code | ✅ PASS |
| Create family | POST /parent/create-family | ✅ PASS |
| Missing mailAuthToken | POST /parent/create-family | ✅ PASS |
| Missing parentPassword | POST /parent/create-family | ✅ PASS |
| Invalid mailAuthToken | POST /parent/create-family | ✅ PASS |
| Family already exists | POST /parent/create-family | ✅ PASS |
| POST /api/families (dashboardV2) | POST /api/families | ✅ PASS |

## Notes

1. The debug-server endpoints are working correctly and all tests pass.
2. The dashboardV2 correctly implements the official API format:
   - Uses `parentDevice: { model: "string" }` format
   - Uses 3-word passphrase for verification codes (e.g., "Pferd Miete abwenden")
   - Passes all required fields to the API
3. The test data files have been updated to use the correct format:
   - `test_sign_in.json` - Uses 3-word passphrase
   - `test_sign_in_v2.json` - Uses 3-word passphrase
   - `sign_in_data.json` - Uses 3-word passphrase
4. The test cases have been updated to use 3-word passphrases instead of 6-digit codes.