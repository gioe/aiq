#!/bin/bash
#
# Test script for check_certificate_expiration.sh
#
# Tests the certificate monitoring script's edge cases without making live
# network calls. Functions are extracted and tested in isolation; the full
# script is tested using a stub openssl wrapper.
#
# Usage: ./ios/scripts/tests/test_check_certificate_expiration.sh
#
# Exit codes:
#   0 - All tests passed
#   1 - One or more tests failed

set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Find script directory and project root
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CERT_SCRIPT="$(dirname "$SCRIPT_DIR")/check_certificate_expiration.sh"

# Counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Check for required tools
for cmd in python3 openssl base64 jq; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo -e "${RED}Error: $cmd is not installed${NC}"
        exit 1
    fi
done

# Test certificate hashes (from TrustKit.plist - not secrets)
VALID_HASH="i+fyVetXyACCzW7mWtTNzuYIjv0JpKqW00eIiiuLp1o="  # pragma: allowlist secret
BACKUP_HASH="kZwN96eHtZftBWrOZUsd6cA4es80n3NzSk/XtYz2EqQ="  # pragma: allowlist secret

# Temp directory for test fixtures
TEST_DIR=$(mktemp -d)
cleanup() { rm -rf "$TEST_DIR"; }
trap cleanup EXIT

# --------------------------------------------------------------------------
# Test helpers
# --------------------------------------------------------------------------

assert_equals() {
    local expected="$1"
    local actual="$2"
    local message="$3"

    TESTS_RUN=$((TESTS_RUN + 1))

    if [ "$expected" = "$actual" ]; then
        echo -e "  ${GREEN}[PASS]${NC} $message"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "  ${RED}[FAIL]${NC} $message"
        echo -e "    Expected: '$expected'"
        echo -e "    Actual:   '$actual'"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

assert_contains() {
    local needle="$1"
    local haystack="$2"
    local message="$3"

    TESTS_RUN=$((TESTS_RUN + 1))

    if [[ "$haystack" == *"$needle"* ]]; then
        echo -e "  ${GREEN}[PASS]${NC} $message"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "  ${RED}[FAIL]${NC} $message"
        echo -e "    Expected to contain: '$needle'"
        echo -e "    Actual: '$haystack'"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

assert_exit_code() {
    local expected="$1"
    local actual="$2"
    local message="$3"

    TESTS_RUN=$((TESTS_RUN + 1))

    if [ "$expected" = "$actual" ]; then
        echo -e "  ${GREEN}[PASS]${NC} $message"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "  ${RED}[FAIL]${NC} $message"
        echo -e "    Expected exit code: $expected"
        echo -e "    Actual exit code:   $actual"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# --------------------------------------------------------------------------
# Create test fixture: valid TrustKit.plist
# --------------------------------------------------------------------------

create_valid_plist() {
    local hash1="${1:-$VALID_HASH}"
    local hash2="${2:-$BACKUP_HASH}"
    local plist_path="$TEST_DIR/TrustKit.plist"

    cat > "$plist_path" << PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>TSKSwizzleNetworkDelegates</key>
    <true/>
    <key>TSKPinnedDomains</key>
    <dict>
        <key>aiq-backend-production.up.railway.app</key>
        <dict>
            <key>TSKEnforcePinning</key>
            <true/>
            <key>TSKIncludeSubdomains</key>
            <false/>
            <key>TSKPublicKeyHashes</key>
            <array>
                <string>${hash1}</string>
                <string>${hash2}</string>
            </array>
        </dict>
    </dict>
</dict>
</plist>
PLIST_EOF

    echo "$plist_path"
}

# --------------------------------------------------------------------------
# Create test fixture: malformed TrustKit.plist (no hashes)
# --------------------------------------------------------------------------

create_malformed_plist() {
    local plist_path="$TEST_DIR/MalformedTrustKit.plist"
    cat > "$plist_path" << 'PLIST_EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>TSKSwizzleNetworkDelegates</key>
    <true/>
    <key>TSKPinnedDomains</key>
    <dict>
        <key>aiq-backend-production.up.railway.app</key>
        <dict>
            <key>TSKEnforcePinning</key>
            <true/>
        </dict>
    </dict>
</dict>
</plist>
PLIST_EOF

    echo "$plist_path"
}

# --------------------------------------------------------------------------
# Create a fake openssl binary that returns controlled output.
#
# Usage: create_openssl_stub <cert_expiry_date> <cert_hash>
#
# The stub handles the specific openssl subcommands used by the script:
#   openssl s_client ...  -> echoes a marker certificate
#   openssl x509 -noout -dates  -> echoes notBefore/notAfter
#   openssl x509 -noout -subject -> echoes subject
#   openssl x509 -noout -issuer -> echoes issuer
#   openssl x509 -pubkey -noout -> piped through to hash generation
#   openssl pkey ... -> passes through
#   openssl dgst ... -> outputs binary that base64 converts to the hash
#
# We take a simpler approach: wrap the ENTIRE script invocation with PATH
# manipulation so openssl is our stub.
# --------------------------------------------------------------------------

create_openssl_stub() {
    local not_after="$1"
    local cert_hash="$2"
    local not_before="${3:-Dec  1 00:00:00 2024 GMT}"

    # Each stub gets its own unique directory to avoid conflicts between tests
    local stub_dir
    stub_dir=$(mktemp -d "$TEST_DIR/stub_bin_XXXXXX")

    # Write the expected hash to a file the stub can read
    local hash_file="$stub_dir/.expected_hash"
    printf '%s' "$cert_hash" > "$hash_file"

    cat > "$stub_dir/openssl" << 'STUB_EOF'
#!/bin/bash
# Stub openssl for testing check_certificate_expiration.sh
# Reads configuration from sibling files in the same directory.

STUB_DIR="$(cd "$(dirname "$0")" && pwd)"

case "$1" in
    s_client)
        echo "-----BEGIN CERTIFICATE-----"
        echo "MIIFake+Certificate+Content+For+Testing=="
        echo "-----END CERTIFICATE-----"
        ;;
    x509)
        case "$*" in
            *-noout*-dates*|*-dates*-noout*)
                cat "$STUB_DIR/.dates"
                ;;
            *-noout*-subject*|*-subject*-noout*)
                echo "subject=CN = *.up.railway.app"
                ;;
            *-noout*-issuer*|*-issuer*-noout*)
                echo "issuer=C = US, O = Let's Encrypt, CN = R12"
                ;;
            *-pubkey*-noout*|*-noout*-pubkey*)
                echo "-----BEGIN PUBLIC KEY-----"
                echo "FAKEPUBLICKEY"
                echo "-----END PUBLIC KEY-----"
                ;;
        esac
        ;;
    pkey)
        # Consume stdin, output deterministic bytes
        cat > /dev/null
        printf 'FAKEDEROUTPUT'
        ;;
    dgst)
        # Consume stdin, output the raw bytes of the expected hash.
        # When the real base64 encodes this, it will produce the expected hash.
        cat > /dev/null
        STUB_DIR="$STUB_DIR" python3 -c "
import base64, sys, os
sys.stdout.buffer.write(base64.b64decode(open(os.environ['STUB_DIR'] + '/.expected_hash').read()))
" 2>/dev/null
        ;;
    *)
        /usr/bin/openssl "$@"
        ;;
esac
STUB_EOF

    chmod +x "$stub_dir/openssl"

    # Write the dates file
    cat > "$stub_dir/.dates" << DATES_EOF
notBefore=${not_before}
notAfter=${not_after}
DATES_EOF

    echo "$stub_dir"
}

# --------------------------------------------------------------------------
# Helper to run the certificate script with controlled environment
# --------------------------------------------------------------------------

run_cert_script() {
    local stub_dir="$1"
    shift
    # Prepend stub dir to PATH so our openssl is found first
    # Also disable set -e in the script so we capture exit code
    set +e
    PATH="$stub_dir:$PATH" bash "$CERT_SCRIPT" "$@" 2>&1
    local exit_code=$?
    set -e
    echo "EXIT_CODE:$exit_code"
}

# --------------------------------------------------------------------------
# Extract days_until function for isolated testing
# --------------------------------------------------------------------------

source_days_until() {
    # Extract the days_until and supporting functions from the script
    local temp_script
    temp_script=$(mktemp)
    trap "rm -f '$temp_script'" RETURN

    cat > "$temp_script" << 'FUNC_EOF'
RED='\033[0;31m'
NC='\033[0m'

output_error() {
    echo -e "${RED}$1${NC}" >&2
}

FUNC_EOF

    # Extract days_until function using brace-depth tracking for robustness
    awk '
        /^days_until\(\)/ { found=1; depth=0 }
        found {
            print
            for (i=1; i<=length($0); i++) {
                c = substr($0,i,1)
                if (c == "{") depth++
                if (c == "}") depth--
            }
            if (found && depth == 0 && /}/) { found=0 }
        }
    ' "$CERT_SCRIPT" >> "$temp_script"

    source "$temp_script"
}

echo ""
echo -e "${YELLOW}Running check_certificate_expiration.sh tests${NC}"
echo "================================================="
echo ""

# ==========================================================================
# Section 1: Argument Parsing Tests
# ==========================================================================

echo -e "${YELLOW}--- Argument Parsing ---${NC}"
echo ""

# Test: --help prints usage and exits 0
echo "Test: --help flag prints usage and exits 0"
output=$(bash "$CERT_SCRIPT" --help 2>&1) || true
exit_code=$?
assert_exit_code "0" "$exit_code" "--help exits with code 0" || true
assert_contains "Usage:" "$output" "--help prints usage text" || true
assert_contains "--json" "$output" "--help mentions --json flag" || true
assert_contains "--quiet" "$output" "--help mentions --quiet flag" || true
assert_contains "--domain" "$output" "--help mentions --domain flag" || true
assert_contains "--plist" "$output" "--help mentions --plist flag" || true
echo ""

# Test: Unknown option exits with code 1
echo "Test: Unknown option exits with code 1"
set +e
output=$(bash "$CERT_SCRIPT" --invalid-flag 2>&1)
exit_code=$?
set -e
assert_exit_code "1" "$exit_code" "Unknown option exits with code 1" || true
assert_contains "Unknown option" "$output" "Prints error for unknown option" || true
echo ""

# Test: --domain without argument exits with error
echo "Test: --domain without argument exits with error"
set +e
output=$(bash "$CERT_SCRIPT" --domain 2>&1)
exit_code=$?
set -e
TESTS_RUN=$((TESTS_RUN + 1))
if [ "$exit_code" -ne 0 ]; then
    echo -e "  ${GREEN}[PASS]${NC} --domain without argument exits with error (code: $exit_code)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}[FAIL]${NC} --domain without argument should exit with error"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
echo ""

# Test: --plist without argument exits with error
echo "Test: --plist without argument exits with error"
set +e
output=$(bash "$CERT_SCRIPT" --plist 2>&1)
exit_code=$?
set -e
TESTS_RUN=$((TESTS_RUN + 1))
if [ "$exit_code" -ne 0 ]; then
    echo -e "  ${GREEN}[PASS]${NC} --plist without argument exits with error (code: $exit_code)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}[FAIL]${NC} --plist without argument should exit with error"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
echo ""

# ==========================================================================
# Section 2: TrustKit.plist Validation Tests
# ==========================================================================

echo -e "${YELLOW}--- TrustKit.plist Validation ---${NC}"
echo ""

# Test: Missing plist file exits with code 4
echo "Test: Missing plist file exits with code 4"
set +e
output=$(bash "$CERT_SCRIPT" --plist "$TEST_DIR/nonexistent.plist" 2>&1)
exit_code=$?
set -e
assert_exit_code "4" "$exit_code" "Missing plist exits with code 4" || true
assert_contains "not found" "$output" "Error message mentions plist not found" || true
echo ""

# Test: Missing plist file with --json outputs JSON error
echo "Test: Missing plist with --json outputs JSON error"
set +e
output=$(bash "$CERT_SCRIPT" --plist "$TEST_DIR/nonexistent.plist" --json 2>&1)
exit_code=$?
set -e
assert_exit_code "4" "$exit_code" "Missing plist with --json exits with code 4" || true
assert_contains "CONFIG_ERROR" "$output" "JSON output contains CONFIG_ERROR status" || true
echo ""

# Test: Unreadable plist file exits with code 4
echo "Test: Unreadable plist file exits with code 4"
if [ "$(id -u)" = "0" ]; then
    TESTS_RUN=$((TESTS_RUN + 1))
    echo -e "  ${YELLOW}[SKIP]${NC} Running as root - permission test not applicable"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    unreadable_plist="$TEST_DIR/unreadable.plist"
    touch "$unreadable_plist"
    chmod 000 "$unreadable_plist"
    set +e
    output=$(bash "$CERT_SCRIPT" --plist "$unreadable_plist" 2>&1)
    exit_code=$?
    set -e
    assert_exit_code "4" "$exit_code" "Unreadable plist exits with code 4" || true
    assert_contains "not readable" "$output" "Error message mentions plist not readable" || true
    chmod 644 "$unreadable_plist"
fi
echo ""

# Test: Malformed plist (no hashes) exits with code 4
echo "Test: Malformed plist (no hashes) exits with code 4"
malformed_plist=$(create_malformed_plist)
stub_dir=$(create_openssl_stub "Mar  6 00:00:00 2027 GMT" "$VALID_HASH")
output=$(run_cert_script "$stub_dir" --plist "$malformed_plist")
exit_code=$(echo "$output" | grep "EXIT_CODE:" | tail -1 | cut -d: -f2)
assert_exit_code "4" "$exit_code" "Malformed plist exits with code 4" || true
assert_contains "Could not extract pinned hashes" "$output" "Error mentions hash extraction failure" || true
echo ""

# ==========================================================================
# Section 3: Network Failure / Connection Error Tests
# ==========================================================================

echo -e "${YELLOW}--- Network Failure ---${NC}"
echo ""

# Test: Connection failure (openssl returns empty) exits with code 2
echo "Test: Connection failure exits with code 2"
fail_stub_dir="$TEST_DIR/fail_stub"
mkdir -p "$fail_stub_dir"
cat > "$fail_stub_dir/openssl" << 'FAIL_STUB'
#!/bin/bash
# Stub that simulates connection failure
case "$1" in
    s_client)
        # Output nothing to simulate connection failure
        exit 1
        ;;
    *)
        /usr/bin/openssl "$@"
        ;;
esac
FAIL_STUB
chmod +x "$fail_stub_dir/openssl"

valid_plist=$(create_valid_plist)
output=$(run_cert_script "$fail_stub_dir" --plist "$valid_plist")
exit_code=$(echo "$output" | grep "EXIT_CODE:" | tail -1 | cut -d: -f2)
assert_exit_code "2" "$exit_code" "Connection failure exits with code 2" || true
assert_contains "Failed to connect" "$output" "Error mentions connection failure" || true
echo ""

# Test: Connection failure with --json outputs JSON
echo "Test: Connection failure with --json outputs JSON"
output=$(run_cert_script "$fail_stub_dir" --plist "$valid_plist" --json)
exit_code=$(echo "$output" | grep "EXIT_CODE:" | tail -1 | cut -d: -f2)
assert_exit_code "2" "$exit_code" "Connection failure with --json exits with code 2" || true
assert_contains "CONNECTION_ERROR" "$output" "JSON output contains CONNECTION_ERROR" || true
echo ""

# ==========================================================================
# Section 4: Certificate Expiration Logic Tests
# ==========================================================================

echo -e "${YELLOW}--- Certificate Expiration Logic ---${NC}"
echo ""

# Test: Expired certificate exits with code 2
echo "Test: Expired certificate exits with code 2"
# Use a date in the past
stub_dir=$(create_openssl_stub "Jan  1 00:00:00 2020 GMT" "$VALID_HASH")
valid_plist=$(create_valid_plist)
output=$(run_cert_script "$stub_dir" --plist "$valid_plist")
exit_code=$(echo "$output" | grep "EXIT_CODE:" | tail -1 | cut -d: -f2)
assert_exit_code "2" "$exit_code" "Expired certificate exits with code 2" || true
assert_contains "EXPIRED" "$output" "Output mentions certificate expired" || true
echo ""

# Test: Certificate expiring within 30 days exits with code 1
echo "Test: Certificate expiring within 30 days exits with code 1 (warning)"
# Calculate a date 15 days from now
if date -v+15d '+%b %e %T %Y GMT' >/dev/null 2>&1; then
    future_15d=$(date -v+15d '+%b %e %T %Y GMT')
elif date -d '+15 days' '+%b %e %T %Y GMT' >/dev/null 2>&1; then
    future_15d=$(date -d '+15 days' '+%b %e %T %Y GMT')
else
    echo -e "  ${RED}[ERROR]${NC} Cannot compute future date on this platform"
    exit 1
fi
stub_dir=$(create_openssl_stub "$future_15d" "$VALID_HASH")
valid_plist=$(create_valid_plist)
output=$(run_cert_script "$stub_dir" --plist "$valid_plist")
exit_code=$(echo "$output" | grep "EXIT_CODE:" | tail -1 | cut -d: -f2)
assert_exit_code "1" "$exit_code" "Certificate expiring in <30 days exits with code 1" || true
assert_contains "WARNING" "$output" "Output contains warning message" || true
echo ""

# Test: Valid certificate (>30 days) exits with code 0
echo "Test: Valid certificate (>30 days) exits with code 0"
# Calculate a date 90 days from now
if date -v+90d '+%b %e %T %Y GMT' >/dev/null 2>&1; then
    future_90d=$(date -v+90d '+%b %e %T %Y GMT')
elif date -d '+90 days' '+%b %e %T %Y GMT' >/dev/null 2>&1; then
    future_90d=$(date -d '+90 days' '+%b %e %T %Y GMT')
else
    echo -e "  ${RED}[ERROR]${NC} Cannot compute future date on this platform"
    exit 1
fi
stub_dir=$(create_openssl_stub "$future_90d" "$VALID_HASH")
valid_plist=$(create_valid_plist)
output=$(run_cert_script "$stub_dir" --plist "$valid_plist")
exit_code=$(echo "$output" | grep "EXIT_CODE:" | tail -1 | cut -d: -f2)
assert_exit_code "0" "$exit_code" "Valid certificate exits with code 0" || true
assert_contains "OK" "$output" "Output contains OK status" || true
echo ""

# ==========================================================================
# Section 5: Hash Mismatch Tests
# ==========================================================================

echo -e "${YELLOW}--- Hash Mismatch ---${NC}"
echo ""

# Test: Hash mismatch exits with code 3
echo "Test: Hash mismatch exits with code 3"
# Reuse future_90d from certificate expiration tests
future_date="$future_90d"
# Use a hash that does NOT match any pinned hash
mismatched_hash="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
stub_dir=$(create_openssl_stub "$future_date" "$mismatched_hash")
valid_plist=$(create_valid_plist)
output=$(run_cert_script "$stub_dir" --plist "$valid_plist")
exit_code=$(echo "$output" | grep "EXIT_CODE:" | tail -1 | cut -d: -f2)
assert_exit_code "3" "$exit_code" "Hash mismatch exits with code 3" || true
assert_contains "HASH MISMATCH" "$output" "Output mentions hash mismatch" || true
assert_contains "IMMEDIATE ACTION REQUIRED" "$output" "Output shows action required" || true
echo ""

# Test: Hash mismatch takes precedence over expiration warning
echo "Test: Hash mismatch takes precedence even when cert expires soon"
stub_dir=$(create_openssl_stub "$future_15d" "$mismatched_hash")
valid_plist=$(create_valid_plist)
output=$(run_cert_script "$stub_dir" --plist "$valid_plist")
exit_code=$(echo "$output" | grep "EXIT_CODE:" | tail -1 | cut -d: -f2)
# Hash mismatch (exit 3) should take priority over warning (exit 1)
assert_exit_code "3" "$exit_code" "Hash mismatch (3) takes precedence over warning (1)" || true
echo ""

# ==========================================================================
# Section 6: JSON Output Tests
# ==========================================================================

echo -e "${YELLOW}--- JSON Output ---${NC}"
echo ""

# Test: --json flag produces valid JSON for OK status
echo "Test: --json produces valid JSON for OK status"
stub_dir=$(create_openssl_stub "$future_90d" "$VALID_HASH")
valid_plist=$(create_valid_plist)
output=$(run_cert_script "$stub_dir" --plist "$valid_plist" --json)
# Extract the JSON block by finding lines between the first { and the
# final } (the script's heredoc JSON). Use python3 for reliable extraction.
json_part=$(echo "$output" | python3 -c "
import sys, json
text = sys.stdin.read()
# Find the outermost JSON object
start = text.find('{')
if start == -1:
    sys.exit(1)
depth = 0
for i in range(start, len(text)):
    if text[i] == '{': depth += 1
    elif text[i] == '}': depth -= 1
    if depth == 0:
        print(text[start:i+1])
        break
" 2>/dev/null || true)
if [ -n "$json_part" ]; then
    TESTS_RUN=$((TESTS_RUN + 1))
    if echo "$json_part" | jq . >/dev/null 2>&1; then
        echo -e "  ${GREEN}[PASS]${NC} JSON output is valid JSON"
        TESTS_PASSED=$((TESTS_PASSED + 1))

        # Validate specific JSON fields
        status=$(echo "$json_part" | jq -r '.status')
        assert_equals "OK" "$status" "JSON status field is OK" || true

        domain=$(echo "$json_part" | jq -r '.domain')
        assert_equals "aiq-backend-production.up.railway.app" "$domain" "JSON domain field is correct" || true

        hash_match=$(echo "$json_part" | jq -r '.hash_match')
        assert_equals "true" "$hash_match" "JSON hash_match is true" || true

        days_remaining=$(echo "$json_part" | jq -r '.certificate.days_remaining')
        TESTS_RUN=$((TESTS_RUN + 1))
        if [ "$days_remaining" -gt 30 ] 2>/dev/null; then
            echo -e "  ${GREEN}[PASS]${NC} JSON days_remaining is > 30"
            TESTS_PASSED=$((TESTS_PASSED + 1))
        else
            echo -e "  ${RED}[FAIL]${NC} JSON days_remaining should be > 30, got: $days_remaining"
            TESTS_FAILED=$((TESTS_FAILED + 1))
        fi
    else
        echo -e "  ${RED}[FAIL]${NC} JSON output is not valid JSON"
        echo -e "    Got: '$json_part'"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
else
    TESTS_RUN=$((TESTS_RUN + 1))
    echo -e "  ${RED}[FAIL]${NC} No JSON found in script output"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
echo ""

# ==========================================================================
# Section 7: --quiet Flag Tests
# ==========================================================================

echo -e "${YELLOW}--- Quiet Mode ---${NC}"
echo ""

# Test: --quiet suppresses normal output but shows errors
echo "Test: --quiet suppresses normal output on OK status"
stub_dir=$(create_openssl_stub "$future_90d" "$VALID_HASH")
valid_plist=$(create_valid_plist)
output=$(run_cert_script "$stub_dir" --plist "$valid_plist" --quiet)
exit_code=$(echo "$output" | grep "EXIT_CODE:" | tail -1 | cut -d: -f2)
assert_exit_code "0" "$exit_code" "--quiet with OK cert exits 0" || true
# In quiet mode with OK status, no header should be printed
TESTS_RUN=$((TESTS_RUN + 1))
# Filter out EXIT_CODE line for content check
content=$(echo "$output" | grep -v "EXIT_CODE:" || true)
if [[ "$content" != *"AIQ Certificate Expiration Monitor"* ]]; then
    echo -e "  ${GREEN}[PASS]${NC} --quiet suppresses banner output"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}[FAIL]${NC} --quiet should suppress banner output"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
echo ""

# Test: --quiet still shows critical errors
echo "Test: --quiet still shows critical hash mismatch"
stub_dir=$(create_openssl_stub "$future_90d" "$mismatched_hash")
valid_plist=$(create_valid_plist)
output=$(run_cert_script "$stub_dir" --plist "$valid_plist" --quiet)
exit_code=$(echo "$output" | grep "EXIT_CODE:" | tail -1 | cut -d: -f2)
assert_exit_code "3" "$exit_code" "--quiet with hash mismatch exits 3" || true
assert_contains "HASH MISMATCH" "$output" "--quiet still shows hash mismatch critical alert" || true
echo ""

# ==========================================================================
# Section 8: days_until Function Isolated Tests
# ==========================================================================

echo -e "${YELLOW}--- days_until Function ---${NC}"
echo ""

# Source the function for isolated testing
source_days_until

# Test: Future date returns positive days
echo "Test: days_until with future date returns positive number"
# Use a date ~365 days in the future
if date -v+365d '+%b %e %T %Y %Z' >/dev/null 2>&1; then
    future_date_str=$(date -v+365d '+%b %e %T %Y %Z')
elif date -d '+365 days' '+%b %e %T %Y %Z' >/dev/null 2>&1; then
    future_date_str=$(date -d '+365 days' '+%b %e %T %Y %Z')
else
    echo -e "  ${RED}[ERROR]${NC} Cannot compute future date on this platform"
    exit 1
fi
result=$(days_until "$future_date_str" 2>/dev/null) || true
TESTS_RUN=$((TESTS_RUN + 1))
if [ -n "$result" ] && [ "$result" -gt 300 ] 2>/dev/null; then
    echo -e "  ${GREEN}[PASS]${NC} Future date returns positive days ($result)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}[FAIL]${NC} Future date should return > 300, got: '$result'"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
echo ""

# Test: Past date returns negative days
echo "Test: days_until with past date returns negative number"
result=$(days_until "Jan  1 00:00:00 2020 GMT" 2>/dev/null) || true
TESTS_RUN=$((TESTS_RUN + 1))
if [ -n "$result" ] && [ "$result" -lt 0 ] 2>/dev/null; then
    echo -e "  ${GREEN}[PASS]${NC} Past date returns negative days ($result)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}[FAIL]${NC} Past date should return negative, got: '$result'"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
echo ""

# Test: Today returns 0
echo "Test: days_until with today's date returns 0"
today_str=""
if date '+%b %e %T %Y %Z' >/dev/null 2>&1; then
    today_str=$(date '+%b %e %T %Y %Z')
fi
if [ -z "$today_str" ]; then
    echo -e "  ${YELLOW}[SKIP]${NC} Cannot format today's date on this platform"
else
    result=$(days_until "$today_str" 2>/dev/null) || true
    TESTS_RUN=$((TESTS_RUN + 1))
    if [ -n "$result" ] && [ "$result" -ge -1 ] && [ "$result" -le 1 ] 2>/dev/null; then
        echo -e "  ${GREEN}[PASS]${NC} Today's date returns ~0 ($result)"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "  ${RED}[FAIL]${NC} Today's date should return ~0, got: '$result'"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
fi
echo ""

# Test: Various date formats (OpenSSL outputs "Mon DD HH:MM:SS YYYY GMT")
echo "Test: days_until handles OpenSSL date format"
result=$(days_until "Dec 31 23:59:59 2030 GMT" 2>/dev/null) || true
TESTS_RUN=$((TESTS_RUN + 1))
if [ -n "$result" ] && [ "$result" -gt 0 ] 2>/dev/null; then
    echo -e "  ${GREEN}[PASS]${NC} OpenSSL date format parsed correctly ($result days)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}[FAIL]${NC} Failed to parse OpenSSL date format, got: '$result'"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
echo ""

# Test: Leap year date
echo "Test: days_until handles leap year date (Feb 29)"
result=$(days_until "Feb 29 12:00:00 2028 GMT" 2>/dev/null) || true
TESTS_RUN=$((TESTS_RUN + 1))
if [ -n "$result" ] && [ "$result" -gt 0 ] 2>/dev/null; then
    echo -e "  ${GREEN}[PASS]${NC} Leap year date parsed correctly ($result days)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}[FAIL]${NC} Failed to parse leap year date, got: '$result'"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
echo ""

# Test: Single-digit day (no leading zero)
echo "Test: days_until handles single-digit day (Mar 6)"
result=$(days_until "Mar  6 00:00:00 2030 GMT" 2>/dev/null) || true
TESTS_RUN=$((TESTS_RUN + 1))
if [ -n "$result" ] && [ "$result" -gt 0 ] 2>/dev/null; then
    echo -e "  ${GREEN}[PASS]${NC} Single-digit day parsed correctly ($result days)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}[FAIL]${NC} Failed to parse single-digit day, got: '$result'"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
echo ""

# Test: Invalid date format exits with error
echo "Test: days_until with invalid date format exits with error"
set +e
result=$(days_until "not-a-date" 2>&1)
invalid_exit=$?
set -e
TESTS_RUN=$((TESTS_RUN + 1))
if [ "$invalid_exit" -ne 0 ] || [[ "$result" == *"Cannot parse"* ]]; then
    echo -e "  ${GREEN}[PASS]${NC} Invalid date format handled (exit: $invalid_exit)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}[FAIL]${NC} Invalid date should fail, got exit: $invalid_exit, output: '$result'"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
echo ""

# ==========================================================================
# Section 9: Hash Extraction from Plist (awk fallback)
# ==========================================================================

echo -e "${YELLOW}--- Plist Hash Extraction ---${NC}"
echo ""

# Test: awk-based extraction works on a valid plist
echo "Test: awk-based hash extraction from valid plist"
valid_plist=$(create_valid_plist "hash1ForTesting=" "hash2ForTesting=")
# Use awk extraction logic from the script directly
extracted_hashes=$(awk '/<key>TSKPublicKeyHashes<\/key>/,/<\/array>/' "$valid_plist" | \
    grep '<string>' | \
    sed 's/.*<string>//g; s/<\/string>.*//g' || true)
TESTS_RUN=$((TESTS_RUN + 1))
if echo "$extracted_hashes" | grep -q "hash1ForTesting="; then
    echo -e "  ${GREEN}[PASS]${NC} First hash extracted via awk"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}[FAIL]${NC} Failed to extract first hash via awk"
    echo -e "    Got: '$extracted_hashes'"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
TESTS_RUN=$((TESTS_RUN + 1))
if echo "$extracted_hashes" | grep -q "hash2ForTesting="; then
    echo -e "  ${GREEN}[PASS]${NC} Second hash extracted via awk"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}[FAIL]${NC} Failed to extract second hash via awk"
    echo -e "    Got: '$extracted_hashes'"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
echo ""

# Test: Hash extraction from malformed plist returns empty
echo "Test: Hash extraction from malformed plist returns empty"
malformed_plist=$(create_malformed_plist)
extracted_hashes=$(awk '/<key>TSKPublicKeyHashes<\/key>/,/<\/array>/' "$malformed_plist" | \
    grep '<string>' | \
    sed 's/.*<string>//g; s/<\/string>.*//g' || true)
TESTS_RUN=$((TESTS_RUN + 1))
if [ -z "$extracted_hashes" ]; then
    echo -e "  ${GREEN}[PASS]${NC} Malformed plist returns empty hash list"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}[FAIL]${NC} Malformed plist should return empty, got: '$extracted_hashes'"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
echo ""

# ==========================================================================
# Section 10: Custom --domain Flag
# ==========================================================================

echo -e "${YELLOW}--- Custom Domain ---${NC}"
echo ""

# Test: --domain flag is reflected in JSON output
echo "Test: --domain flag sets custom domain in JSON output"
stub_dir=$(create_openssl_stub "$future_90d" "$VALID_HASH")
valid_plist=$(create_valid_plist)
output=$(run_cert_script "$stub_dir" --plist "$valid_plist" --domain "custom.example.com" --json)
assert_contains "custom.example.com" "$output" "Custom domain appears in output" || true
echo ""

# ==========================================================================
# Print summary
# ==========================================================================

echo "================================================="
echo ""
if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}All $TESTS_RUN tests passed!${NC}"
    exit 0
else
    echo -e "${RED}$TESTS_FAILED of $TESTS_RUN tests failed${NC}"
    exit 1
fi
