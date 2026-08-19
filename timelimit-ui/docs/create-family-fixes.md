# Create Family Flow Fixes

This document details the fixes applied to resolve issues with the create family flow.

## Fix 1: Add Missing `clientLevel` Field

**Root Cause:** The create family step 3 was failing with a 400 Bad Request error because the `clientLevel` field was missing from the API request.

**Android App Reference:** `HttpServerApi.kt` lines 306-308

**Fix:** Added `'clientLevel': 7` to both `create_family()` and `create_family_rest()` methods in `auth_client.py`.

## Fix 2: Remove `encrypted` Field from `parentPassword`

**Root Cause:** The `parentPassword` object included an `encrypted` field that is not allowed by the server's validation schema (`PlaintextParentPassword`).

**Server Schema:** `C:\git\timelimit-server\src\api\schema.ts`

**Fix:** Removed `password_data['encrypted'] = False` from `app.py` line 1020.

## Fix 3: Remove `locale` Field from Create Family Request

**Root Cause:** The `locale` field was being sent in the request body but is not allowed by the server's validation schema (`CreateFamilyByMailTokenRequest`).

**Server Schema:** `C:\git\timelimit-server\src/api/schema.ts`

**Fix:** Removed the `locale` field from the request data in `auth_client.py` for both `create_family()` and `create_family_rest()` methods.

## Fix 4: Bcrypt Hash Prefix Mismatch

**Root Cause:** bcrypt 5.0+ requires the prefix parameter to be `b'2a'` or `b'2b'` (without dollar signs), but the code was passing `b'$2a$'` (with dollar signs).

**Server Validation Regex:** `/^(\$2a\$[123][0-9]\$[./A-Za-z0-9]{53})?$/`

**Fix:** Updated `crypto_utils.py` to use `prefix=b'2a'` (without dollar signs) for bcrypt 5.0+ compatibility.

## Fix 5: Password Validation

Added server-side and client-side password validation:
- Server-side: Minimum 8 character password check in `app.py`
- Client-side: `minlength="8"` and `pattern=".{8,}"` attributes in `create_family.html`

## Time Zone Field Change

The time zone field in Step 3 of the create family form was changed from a free-text input to a dropdown selection box with valid IANA time zones.

## Files Modified

| File | Changes |
|------|---------|
| `auth_client.py` | Added `clientLevel: 7`, removed `locale` and `encrypted` fields |
| `app.py` | Removed `encrypted` field, added password validation |
| `crypto_utils.py` | Fixed bcrypt prefix for 5.0+ compatibility |
| `create_family.html` | Changed time zone to dropdown, added password validation |
| Various test data files | Updated to match server schema |

## Verification

All fixes have been verified and tested. See `test_families_flow.py` for integration tests.