#!/bin/bash
#
# Test script for parse_success_run_line function in bootstrap_inventory.sh
#
# Usage: ./scripts/tests/test_parse_success_run.sh
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
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
BOOTSTRAP_SCRIPT="$PROJECT_ROOT/scripts/bootstrap_inventory.sh"

# Counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Source only the function we need to test (extract it from the bootstrap script)
# We extract the function to avoid running the entire bootstrap script
extract_and_source_function() {
    # Create a temp file with just the function and required variables
    local temp_script
    temp_script=$(mktemp)
    trap "rm -f '$temp_script'" RETURN

    cat > "$temp_script" << 'FUNCTION_EOF'
# Colors for output (needed by parse_success_run_line)
GREEN='\033[0;32m'
NC='\033[0m'

# Global variables set by parse_success_run_line
LAST_SUCCESS_GENERATED=""
LAST_SUCCESS_INSERTED=""
LAST_SUCCESS_APPROVAL_RATE=""

# Function to parse and display SUCCESS_RUN information
parse_success_run_line() {
    local line="$1"
    local json_data

    # Extract JSON from "SUCCESS_RUN: {...}" format
    json_data="${line#SUCCESS_RUN: }"

    # Parse key metrics using jq
    local generated inserted approval_rate duration providers
    generated=$(echo "$json_data" | jq -r '.questions_generated // empty' 2>/dev/null)
    inserted=$(echo "$json_data" | jq -r '.questions_inserted // empty' 2>/dev/null)
    approval_rate=$(echo "$json_data" | jq -r '.approval_rate // empty' 2>/dev/null)
    duration=$(echo "$json_data" | jq -r '.duration_seconds // empty' 2>/dev/null)
    providers=$(echo "$json_data" | jq -r '.providers_used // [] | join(", ")' 2>/dev/null)

    # Set global variables for downstream use (e.g., log_event calls)
    LAST_SUCCESS_GENERATED="${generated:-0}"
    LAST_SUCCESS_INSERTED="${inserted:-0}"
    LAST_SUCCESS_APPROVAL_RATE="${approval_rate:-0}"

    # Display the success run information
    if [ -n "$generated" ] && [ -n "$inserted" ]; then
        echo -e "  ${GREEN}[SUCCESS_RUN]${NC} Generated: ${generated}, Inserted: ${inserted}"
        if [ -n "$approval_rate" ]; then
            echo -e "  ${GREEN}[SUCCESS_RUN]${NC} Approval rate: ${approval_rate}%"
        fi
        if [ -n "$duration" ]; then
            if [ "$(echo "$duration > 60" | bc -l 2>/dev/null || echo 0)" = "1" ]; then
                local minutes seconds
                minutes=$(echo "$duration / 60" | bc 2>/dev/null || echo "")
                seconds=$(printf "%.0f" "$(echo "$duration % 60" | bc 2>/dev/null)" 2>/dev/null || printf "%.0f" "$duration")
                if [ -n "$minutes" ]; then
                    echo -e "  ${GREEN}[SUCCESS_RUN]${NC} Duration: ${minutes}m ${seconds}s"
                else
                    echo -e "  ${GREEN}[SUCCESS_RUN]${NC} Duration: ${duration}s"
                fi
            else
                echo -e "  ${GREEN}[SUCCESS_RUN]${NC} Duration: ${duration}s"
            fi
        fi
        if [ -n "$providers" ]; then
            echo -e "  ${GREEN}[SUCCESS_RUN]${NC} Providers: ${providers}"
        fi
    fi
}
FUNCTION_EOF

    source "$temp_script"
}

# Test helper functions
assert_equals() {
    local expected="$1"
    local actual="$2"
    local message="$3"

    TESTS_RUN=$((TESTS_RUN + 1))

    if [ "$expected" = "$actual" ]; then
        echo -e "  ${GREEN}✓${NC} $message"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "  ${RED}✗${NC} $message"
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
        echo -e "  ${GREEN}✓${NC} $message"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "  ${RED}✗${NC} $message"
        echo -e "    Expected to contain: '$needle'"
        echo -e "    Actual: '$haystack'"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Check for jq (required by parse_success_run_line)
if ! command -v jq >/dev/null 2>&1; then
    echo -e "${RED}Error: jq is not installed${NC}"
    echo "Install jq to run these tests:"
    echo "  macOS:   brew install jq"
    echo "  Ubuntu:  sudo apt-get install jq"
    exit 1
fi

# Source the function
extract_and_source_function

echo ""
echo -e "${YELLOW}Running parse_success_run_line tests${NC}"
echo "========================================"
echo ""

# Test 1: Parse complete SUCCESS_RUN JSON
echo "Test: Parse complete SUCCESS_RUN JSON with all fields"
LAST_SUCCESS_GENERATED=""
LAST_SUCCESS_INSERTED=""
LAST_SUCCESS_APPROVAL_RATE=""

line='SUCCESS_RUN: {"timestamp":"2026-01-25T20:45:33.123456+00:00","questions_generated":50,"questions_inserted":42,"duration_seconds":124.5,"approval_rate":84.0,"providers_used":["openai","anthropic"]}'

# Run function to set globals (no subshell)
parse_success_run_line "$line" > /dev/null

assert_equals "50" "$LAST_SUCCESS_GENERATED" "questions_generated extracted correctly" || true
assert_equals "42" "$LAST_SUCCESS_INSERTED" "questions_inserted extracted correctly" || true
assert_equals "84.0" "$LAST_SUCCESS_APPROVAL_RATE" "approval_rate extracted correctly" || true

# Re-run to capture output
output=$(parse_success_run_line "$line")

assert_contains "Generated: 50" "$output" "Output shows generated count" || true
assert_contains "Inserted: 42" "$output" "Output shows inserted count" || true
assert_contains "Approval rate: 84.0%" "$output" "Output shows approval rate" || true
assert_contains "openai, anthropic" "$output" "Output shows providers" || true

echo ""

# Test 2: Parse SUCCESS_RUN with missing optional fields
echo "Test: Parse SUCCESS_RUN with missing optional fields"
LAST_SUCCESS_GENERATED=""
LAST_SUCCESS_INSERTED=""
LAST_SUCCESS_APPROVAL_RATE=""

line='SUCCESS_RUN: {"questions_generated":100,"questions_inserted":80}'

# Run function to set globals (no subshell)
parse_success_run_line "$line" > /dev/null

assert_equals "100" "$LAST_SUCCESS_GENERATED" "questions_generated extracted with missing fields" || true
assert_equals "80" "$LAST_SUCCESS_INSERTED" "questions_inserted extracted with missing fields" || true
assert_equals "0" "$LAST_SUCCESS_APPROVAL_RATE" "approval_rate defaults to 0 when missing" || true

# Re-run to capture output
output=$(parse_success_run_line "$line")

assert_contains "Generated: 100" "$output" "Output shows generated count" || true
assert_contains "Inserted: 80" "$output" "Output shows inserted count" || true

echo ""

# Test 3: Parse SUCCESS_RUN with zero values
echo "Test: Parse SUCCESS_RUN with zero values"
LAST_SUCCESS_GENERATED=""
LAST_SUCCESS_INSERTED=""
LAST_SUCCESS_APPROVAL_RATE=""

line='SUCCESS_RUN: {"questions_generated":0,"questions_inserted":0,"approval_rate":0.0}'

# Run function to set globals (no subshell)
parse_success_run_line "$line" > /dev/null

assert_equals "0" "$LAST_SUCCESS_GENERATED" "questions_generated can be 0" || true
assert_equals "0" "$LAST_SUCCESS_INSERTED" "questions_inserted can be 0" || true
assert_equals "0.0" "$LAST_SUCCESS_APPROVAL_RATE" "approval_rate can be 0" || true

echo ""

# Test 4: Parse SUCCESS_RUN with single provider
echo "Test: Parse SUCCESS_RUN with single provider"
LAST_SUCCESS_GENERATED=""
LAST_SUCCESS_INSERTED=""
LAST_SUCCESS_APPROVAL_RATE=""

line='SUCCESS_RUN: {"questions_generated":25,"questions_inserted":20,"providers_used":["anthropic"]}'
output=$(parse_success_run_line "$line")

assert_contains "anthropic" "$output" "Output shows single provider" || true

echo ""

# Test 5: Parse SUCCESS_RUN with empty providers array
echo "Test: Parse SUCCESS_RUN with empty providers array"
LAST_SUCCESS_GENERATED=""
LAST_SUCCESS_INSERTED=""
LAST_SUCCESS_APPROVAL_RATE=""

line='SUCCESS_RUN: {"questions_generated":10,"questions_inserted":8,"providers_used":[]}'

# Run function to set globals (no subshell)
parse_success_run_line "$line" > /dev/null

assert_equals "10" "$LAST_SUCCESS_GENERATED" "questions_generated extracted with empty providers" || true

echo ""

# Test 6: Parse SUCCESS_RUN with duration under 60 seconds
echo "Test: Parse SUCCESS_RUN with duration under 60 seconds"
LAST_SUCCESS_GENERATED=""
LAST_SUCCESS_INSERTED=""
LAST_SUCCESS_APPROVAL_RATE=""

line='SUCCESS_RUN: {"questions_generated":15,"questions_inserted":12,"duration_seconds":45.5}'
output=$(parse_success_run_line "$line")

assert_contains "Duration: 45.5s" "$output" "Duration shows seconds for < 60s" || true

echo ""

# Test 7: Parse SUCCESS_RUN with duration over 60 seconds
echo "Test: Parse SUCCESS_RUN with duration over 60 seconds"
LAST_SUCCESS_GENERATED=""
LAST_SUCCESS_INSERTED=""
LAST_SUCCESS_APPROVAL_RATE=""

line='SUCCESS_RUN: {"questions_generated":150,"questions_inserted":120,"duration_seconds":185}'
output=$(parse_success_run_line "$line")

assert_contains "Duration: 3m" "$output" "Duration shows minutes for > 60s" || true

echo ""

# Test 7b: Parse SUCCESS_RUN with fractional duration over 60 seconds
echo "Test: Parse SUCCESS_RUN with fractional duration over 60 seconds"
LAST_SUCCESS_GENERATED=""
LAST_SUCCESS_INSERTED=""
LAST_SUCCESS_APPROVAL_RATE=""

line='SUCCESS_RUN: {"questions_generated":50,"questions_inserted":42,"duration_seconds":124.5}'
output=$(parse_success_run_line "$line")

# Should format as "2m 4s" or "2m 5s" (rounded), not "2m 4.5s"
assert_contains "Duration: 2m" "$output" "Duration shows minutes for fractional > 60s" || true
# Ensure no decimal in seconds portion
TESTS_RUN=$((TESTS_RUN + 1))
if echo "$output" | grep -q "Duration: 2m [0-9]*\.[0-9]*s"; then
    echo -e "  ${RED}✗${NC} Seconds should be rounded, not fractional"
    TESTS_FAILED=$((TESTS_FAILED + 1))
else
    echo -e "  ${GREEN}✓${NC} Seconds are rounded (no decimal)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
fi

echo ""

# Test 8: Handle malformed JSON gracefully
echo "Test: Handle malformed JSON gracefully (no crash)"
LAST_SUCCESS_GENERATED=""
LAST_SUCCESS_INSERTED=""
LAST_SUCCESS_APPROVAL_RATE=""

line='SUCCESS_RUN: {invalid json here}'

# Run function to set globals (no subshell), suppress jq errors
parse_success_run_line "$line" > /dev/null 2>&1 || true

# Should default to 0 when parsing fails
assert_equals "0" "$LAST_SUCCESS_GENERATED" "Defaults to 0 for malformed JSON" || true

echo ""

# Test 9: Parse SUCCESS_RUN with floating point approval rate
echo "Test: Parse SUCCESS_RUN with floating point approval rate"
LAST_SUCCESS_GENERATED=""
LAST_SUCCESS_INSERTED=""
LAST_SUCCESS_APPROVAL_RATE=""

line='SUCCESS_RUN: {"questions_generated":33,"questions_inserted":27,"approval_rate":81.81818181818183}'
output=$(parse_success_run_line "$line")

assert_contains "81.81818181818183%" "$output" "Output preserves floating point precision" || true

echo ""

# Print summary
echo "========================================"
echo ""
if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}All $TESTS_RUN tests passed!${NC}"
    exit 0
else
    echo -e "${RED}$TESTS_FAILED of $TESTS_RUN tests failed${NC}"
    exit 1
fi
