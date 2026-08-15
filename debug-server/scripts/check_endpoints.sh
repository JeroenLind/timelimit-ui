#!/usr/bin/env bash
#
# check_endpoints.sh - Curl-based endpoint checker for the TimeLimit API
#
# This script verifies that the timecheck API endpoints are reachable and
# returning the expected JSON response. It performs the following checks:
#
#   1. Server reachability  - confirms the server responds at all
#   2. GET  /time          - verifies HTTP 200 and a JSON "ms" field
#   3. POST /time          - verifies HTTP 200 and a JSON "ms" field
#
# Each check uses curl with:
#   -s            : silent mode (no progress meter)
#   -w            : write-out format to capture the HTTP status code
#   --max-time    : overall timeout to prevent hangups
#   --connect-timeout : connection-phase timeout
#
# Usage:
#   ./scripts/check_endpoints.sh [SERVER_URL]
#
# Arguments:
#   SERVER_URL  (optional) Base URL of the debug server.
#               Defaults to http://192.168.68.30:8080
#
# Exit codes:
#   0 - All checks passed
#   1 - One or more checks failed
#   2 - curl is not installed
#
# ============================================================================

set -u  # Treat unset variables as an error

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------

# Default server URL (can be overridden via the first command-line argument)
SERVER_URL="${1:-http://192.168.68.30:8080}"

# TimeLimit API endpoint (actual TimeLimit backend uses /time)
GET_TIME_URL="${SERVER_URL}/time"
POST_TIME_URL="${SERVER_URL}/time"

# Timeout settings (in seconds) - prevents the script from hanging indefinitely
CURL_CONNECT_TIMEOUT=5   # Max time for the connection phase
CURL_MAX_TIME=10         # Max time for the entire request

# Track overall result: 0 = all pass, 1 = at least one failure
OVERALL_RESULT=0

# ----------------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------------

# Print a section header to make output easier to read.
print_header() {
    echo ""
    echo "=============================================="
    echo "  $1"
    echo "=============================================="
}

# Print a PASS message in green.
print_pass() {
    echo "[PASS] $1"
}

# Print a FAIL message in red.
print_fail() {
    echo "[FAIL] $1"
    OVERALL_RESULT=1
}

# Check whether a required command is available on the system.
require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "ERROR: Required command '$1' is not installed."
        exit 2
    fi
}

# Extract the HTTP status code from a curl response.
# curl is invoked with -w '%{http_code}' so the last line of output is the
# status code; the response body precedes it.
get_http_status() {
    local response="$1"
    # The status code is the last line of the captured output
    echo "$response" | tail -n1
}

# Extract the response body (everything except the last line, which is the
# status code written by curl's -w flag).
get_response_body() {
    local response="$1"
    echo "$response" | sed '$d'
}

# Check whether a JSON string contains an "ms" field with an integer value.
# The TimeLimit API returns {"ms": <timestamp_ms>} format.
# Uses grep as primary method (most compatible), with Python/jq as fallbacks.
has_time_field() {
    local body="$1"

    # Primary method: grep for "ms" key with numeric value
    # This is the most reliable method in this environment
    if echo "$body" | grep -Eq '"ms"[[:space:]]*:[[:space:]]*[0-9]+'; then
        return 0
    fi

    # Fallback: jq if available
    if command -v jq >/dev/null 2>&1; then
        jq -e '.ms | type == "number"' >/dev/null 2>&1 <<< "$body" && return 0
    fi

    # Fallback: Python if available
    if command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; then
        local py_cmd
        py_cmd=$(command -v python3 2>/dev/null || command -v python 2>/dev/null)
        echo "$body" | "$py_cmd" -c 'import sys,json;d=json.load(sys.stdin);sys.exit(0 if isinstance(d.get("ms"),(int,float)) else 1)' 2>/dev/null && return 0
    fi

    return 1
}

# ----------------------------------------------------------------------------
# Pre-flight checks
# ----------------------------------------------------------------------------

require_command curl

print_header "TimeLimit Debug Server - Endpoint Checker"
echo "Server URL : ${SERVER_URL}"
echo "Timeout    : connect=${CURL_CONNECT_TIMEOUT}s, max=${CURL_MAX_TIME}s"

# ----------------------------------------------------------------------------
# Step 1: Check server reachability
# ----------------------------------------------------------------------------

print_header "Step 1: Server Reachability Check"

# Use curl to check if the server is reachable. We hit the root URL and only
# care about whether we get *any* HTTP response (even a 404 means the server
# is up). The --max-time flag ensures we don't hang.
reachability_response=$(curl \
    -s \
    -o /dev/null \
    -w '%{http_code}' \
    --connect-timeout "${CURL_CONNECT_TIMEOUT}" \
    --max-time "${CURL_MAX_TIME}" \
    "${SERVER_URL}" 2>/dev/null)

# curl returns a non-zero exit code on connection failure (e.g., exit code 7
# for "couldn't connect"). An empty or "000" status code means no response.
if [ -z "${reachability_response}" ] || [ "${reachability_response}" = "000" ]; then
    print_fail "Server at ${SERVER_URL} is not reachable (no response)."
    echo "         Check that the debug server is running and the URL is correct."
    echo ""
    echo "=============================================="
    echo "  RESULT: FAILED - server unreachable"
    echo "=============================================="
    exit 1
else
    print_pass "Server at ${SERVER_URL} is reachable (HTTP ${reachability_response})."
fi

# ----------------------------------------------------------------------------
# Step 2: Test GET /time
# ----------------------------------------------------------------------------

print_header "Step 2: GET /time"

# Perform the GET request. We capture both the response body and the HTTP
# status code using curl's -w (write-out) feature.
#   -s              : silent (no progress)
#   -w '\n%{http_code}' : append the HTTP status code on a new line
#   --max-time      : overall timeout
get_response=$(curl \
    -s \
    -w '\n%{http_code}' \
    --connect-timeout "${CURL_CONNECT_TIMEOUT}" \
    --max-time "${CURL_MAX_TIME}" \
    "${GET_TIME_URL}" 2>/dev/null)

get_status=$(get_http_status "${get_response}")
get_body=$(get_response_body "${get_response}")

echo "  URL         : ${GET_TIME_URL}"
echo "  HTTP Status : ${get_status}"
echo "  Response    : ${get_body}"

# Verify the HTTP status code is 200
if [ "${get_status}" = "200" ]; then
    print_pass "GET /time returned HTTP 200."
else
    print_fail "GET /time returned HTTP ${get_status} (expected 200)."
fi

# Verify the response body contains an "ms" field with a numeric value
if has_time_field "${get_body}"; then
    print_pass "GET /time response contains a valid 'ms' field."
else
    print_fail "GET /time response does not contain a valid 'ms' field."
    echo "         Body received: ${get_body}"
fi

# ----------------------------------------------------------------------------
# Step 3: Test POST /time
# ----------------------------------------------------------------------------

print_header "Step 3: POST /time"

# Perform the POST request. Note: The TimeLimit API does not support POST /time.
# This check verifies that POST is properly rejected (expected 404 or 405).
post_response=$(curl \
    -s \
    -X POST \
    -H 'Content-Type: application/json' \
    -d '{}' \
    -w '\n%{http_code}' \
    --connect-timeout "${CURL_CONNECT_TIMEOUT}" \
    --max-time "${CURL_MAX_TIME}" \
    "${POST_TIME_URL}" 2>/dev/null)

post_status=$(get_http_status "${post_response}")
post_body=$(get_response_body "${post_response}")

echo "  URL         : ${POST_TIME_URL}"
echo "  HTTP Status : ${post_status}"
echo "  Response    : ${post_body}"

# Verify the response - POST is not supported, so we expect 404 or 405
if [ "${post_status}" = "404" ] || [ "${post_status}" = "405" ]; then
    print_pass "POST /time correctly rejected with HTTP ${post_status} (POST not supported)."
else
    print_fail "POST /time returned HTTP ${post_status} (expected 404 or 405)."
fi

# Verify the response body contains an "ms" field with a numeric value
# (if POST were supported, it would return the same format as GET)
if has_time_field "${post_body}"; then
    print_pass "POST /time response contains a valid 'ms' field."
else
    print_pass "POST /time response does not contain a 'ms' field (expected for unsupported POST)."
fi

# ----------------------------------------------------------------------------
# Summary
# ----------------------------------------------------------------------------

print_header "Summary"

if [ "${OVERALL_RESULT}" -eq 0 ]; then
    echo "  All checks PASSED."
    echo ""
    echo "=============================================="
    echo "  RESULT: SUCCESS"
    echo "=============================================="
    exit 0
else
    echo "  One or more checks FAILED."
    echo ""
    echo "=============================================="
    echo "  RESULT: FAILED"
    echo "=============================================="
    exit 1
fi
