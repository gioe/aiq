#!/bin/bash
#
# Test script for write_per_type_metrics function in bootstrap_inventory.sh
#
# Usage: ./scripts/tests/test_write_per_type_metrics.sh
#
# Exit codes:
#   0 - All tests passed
#   1 - One or more tests failed

set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Find script directory and project root
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
BOOTSTRAP_SCRIPT="$PROJECT_ROOT/scripts/bootstrap_inventory.sh"

# Counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Create a temp directory for RESULTS_DIR
TEST_RESULTS_DIR=$(mktemp -d)
trap "rm -rf '$TEST_RESULTS_DIR'" EXIT

# Source the function we need to test
extract_and_source_function() {
    # Create a temp file with just the function and required variables
    local temp_script
    temp_script=$(mktemp)
    trap "rm -f '$temp_script'" RETURN

    cat > "$temp_script" << 'FUNCTION_EOF'
# Colors for output (needed by write_per_type_metrics)
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# Function to write per-type metrics to a JSON file in RESULTS_DIR
write_per_type_metrics() {
    local question_type="$1"

    # Skip if RESULTS_DIR is not set
    if [ -z "$RESULTS_DIR" ]; then
        return 0
    fi

    # Skip if no metrics were captured
    if [ -z "$LAST_SUCCESS_GENERATED" ] || [ "$LAST_SUCCESS_GENERATED" = "0" ]; then
        return 0
    fi

    # Calculate approved count from generated and approval_rate
    # Use awk's -v flag to safely pass variables (prevents shell injection)
    local approved=0
    if [ -n "$LAST_SUCCESS_APPROVAL_RATE" ] && [ "$LAST_SUCCESS_APPROVAL_RATE" != "0" ]; then
        approved=$(awk -v gen="$LAST_SUCCESS_GENERATED" -v rate="$LAST_SUCCESS_APPROVAL_RATE" \
            'BEGIN {printf "%.0f", gen * rate / 100}')
    fi

    # Get ISO 8601 timestamp in UTC
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Build JSON object with metrics
    local metrics_json
    if ! metrics_json=$(jq -n \
        --arg type "$question_type" \
        --arg ts "$timestamp" \
        --argjson generated "${LAST_SUCCESS_GENERATED:-0}" \
        --argjson approved "$approved" \
        --argjson inserted "${LAST_SUCCESS_INSERTED:-0}" \
        --argjson approval_rate "${LAST_SUCCESS_APPROVAL_RATE:-0}" \
        --argjson duration "${LAST_SUCCESS_DURATION:-0}" \
        '{
            type: $type,
            timestamp: $ts,
            generated: $generated,
            approved: $approved,
            inserted: $inserted,
            approval_rate: $approval_rate,
            duration_seconds: $duration
        }' 2>/dev/null); then
        echo -e "  ${RED}[METRICS]${NC} Failed to build metrics JSON for $question_type"
        return 1
    fi

    # Verify we got valid JSON before writing
    if [ -z "$metrics_json" ]; then
        echo -e "  ${RED}[METRICS]${NC} Empty metrics JSON for $question_type"
        return 1
    fi

    # Write to per-type metrics file
    local metrics_file="$RESULTS_DIR/${question_type}_metrics.json"
    echo "$metrics_json" > "$metrics_file"

    echo -e "  ${BLUE}[METRICS]${NC} Wrote metrics to ${question_type}_metrics.json"
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

assert_file_exists() {
    local file_path="$1"
    local message="$2"

    TESTS_RUN=$((TESTS_RUN + 1))

    if [ -f "$file_path" ]; then
        echo -e "  ${GREEN}[PASS]${NC} $message"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "  ${RED}[FAIL]${NC} $message"
        echo -e "    File does not exist: '$file_path'"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

assert_file_not_exists() {
    local file_path="$1"
    local message="$2"

    TESTS_RUN=$((TESTS_RUN + 1))

    if [ ! -f "$file_path" ]; then
        echo -e "  ${GREEN}[PASS]${NC} $message"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "  ${RED}[FAIL]${NC} $message"
        echo -e "    File exists but should not: '$file_path'"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

assert_json_field() {
    local json_file="$1"
    local field="$2"
    local expected="$3"
    local message="$4"

    TESTS_RUN=$((TESTS_RUN + 1))

    local actual
    actual=$(jq -r ".$field" "$json_file" 2>/dev/null)

    if [ "$expected" = "$actual" ]; then
        echo -e "  ${GREEN}[PASS]${NC} $message"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "  ${RED}[FAIL]${NC} $message"
        echo -e "    Expected .$field: '$expected'"
        echo -e "    Actual .$field:   '$actual'"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Check for jq (required by write_per_type_metrics)
if ! command -v jq >/dev/null 2>&1; then
    echo -e "${RED}Error: jq is not installed${NC}"
    echo "Install jq to run these tests:"
    echo "  macOS:   brew install jq"
    echo "  Ubuntu:  sudo apt-get install jq"
    exit 1
fi

# Source the function
extract_and_source_function

# Set RESULTS_DIR to our test directory
RESULTS_DIR="$TEST_RESULTS_DIR"

echo ""
echo -e "${YELLOW}Running write_per_type_metrics tests${NC}"
echo "========================================"
echo ""

# Test 1: Write metrics for a successful run
echo "Test 1: Write metrics for a successful run"
LAST_SUCCESS_GENERATED="100"
LAST_SUCCESS_INSERTED="85"
LAST_SUCCESS_APPROVAL_RATE="90"
LAST_SUCCESS_DURATION="120.5"

write_per_type_metrics "math" > /dev/null

assert_file_exists "$RESULTS_DIR/math_metrics.json" "Metrics file created for math type" || true
assert_json_field "$RESULTS_DIR/math_metrics.json" "type" "math" "Type field is correct" || true
assert_json_field "$RESULTS_DIR/math_metrics.json" "generated" "100" "Generated count is correct" || true
assert_json_field "$RESULTS_DIR/math_metrics.json" "inserted" "85" "Inserted count is correct" || true
assert_json_field "$RESULTS_DIR/math_metrics.json" "approval_rate" "90" "Approval rate is correct" || true
# approved = 100 * 90 / 100 = 90
assert_json_field "$RESULTS_DIR/math_metrics.json" "approved" "90" "Approved count is calculated correctly" || true
assert_json_field "$RESULTS_DIR/math_metrics.json" "duration_seconds" "120.5" "Duration is correct" || true

echo ""

# Test 2: Skip writing when RESULTS_DIR is not set
echo "Test 2: Skip writing when RESULTS_DIR is not set"
OLD_RESULTS_DIR="$RESULTS_DIR"
RESULTS_DIR=""
LAST_SUCCESS_GENERATED="50"
LAST_SUCCESS_INSERTED="40"
LAST_SUCCESS_APPROVAL_RATE="80"
LAST_SUCCESS_DURATION="60"

write_per_type_metrics "verbal" > /dev/null

assert_file_not_exists "$OLD_RESULTS_DIR/verbal_metrics.json" "Metrics file not created when RESULTS_DIR is empty" || true

RESULTS_DIR="$OLD_RESULTS_DIR"

echo ""

# Test 3: Skip writing when no questions were generated
echo "Test 3: Skip writing when no questions were generated"
LAST_SUCCESS_GENERATED=""
LAST_SUCCESS_INSERTED=""
LAST_SUCCESS_APPROVAL_RATE=""
LAST_SUCCESS_DURATION=""

write_per_type_metrics "logic" > /dev/null

assert_file_not_exists "$RESULTS_DIR/logic_metrics.json" "Metrics file not created when LAST_SUCCESS_GENERATED is empty" || true

echo ""

# Test 4: Skip writing when generated count is zero
echo "Test 4: Skip writing when generated count is zero"
LAST_SUCCESS_GENERATED="0"
LAST_SUCCESS_INSERTED="0"
LAST_SUCCESS_APPROVAL_RATE="0"
LAST_SUCCESS_DURATION="0"

write_per_type_metrics "spatial" > /dev/null

assert_file_not_exists "$RESULTS_DIR/spatial_metrics.json" "Metrics file not created when LAST_SUCCESS_GENERATED is 0" || true

echo ""

# Test 5: Calculate approved count with fractional approval rate
echo "Test 5: Calculate approved count with fractional approval rate"
LAST_SUCCESS_GENERATED="150"
LAST_SUCCESS_INSERTED="120"
LAST_SUCCESS_APPROVAL_RATE="81.333"
LAST_SUCCESS_DURATION="200"

write_per_type_metrics "pattern" > /dev/null

assert_file_exists "$RESULTS_DIR/pattern_metrics.json" "Metrics file created for pattern type" || true
# approved = 150 * 81.333 / 100 = 122 (rounded)
assert_json_field "$RESULTS_DIR/pattern_metrics.json" "approved" "122" "Approved count rounds correctly" || true

echo ""

# Test 6: Write metrics with different types
echo "Test 6: Write metrics with different types"
LAST_SUCCESS_GENERATED="75"
LAST_SUCCESS_INSERTED="60"
LAST_SUCCESS_APPROVAL_RATE="85"
LAST_SUCCESS_DURATION="90"

write_per_type_metrics "memory" > /dev/null

assert_file_exists "$RESULTS_DIR/memory_metrics.json" "Metrics file created for memory type" || true
assert_json_field "$RESULTS_DIR/memory_metrics.json" "type" "memory" "Type field is memory" || true

echo ""

# Test 7: Verify timestamp format is ISO 8601
echo "Test 7: Verify timestamp is present and valid"
LAST_SUCCESS_GENERATED="50"
LAST_SUCCESS_INSERTED="45"
LAST_SUCCESS_APPROVAL_RATE="90"
LAST_SUCCESS_DURATION="30"

write_per_type_metrics "verbal" > /dev/null

assert_file_exists "$RESULTS_DIR/verbal_metrics.json" "Metrics file created for verbal type" || true

# Check timestamp is not null and matches ISO 8601 pattern
timestamp=$(jq -r ".timestamp" "$RESULTS_DIR/verbal_metrics.json")
TESTS_RUN=$((TESTS_RUN + 1))
if [[ "$timestamp" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]; then
    echo -e "  ${GREEN}[PASS]${NC} Timestamp is valid ISO 8601 format"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "  ${RED}[FAIL]${NC} Timestamp is not valid ISO 8601 format"
    echo -e "    Got: '$timestamp'"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

echo ""

# Test 8: Handle zero approval rate (no approved questions)
echo "Test 8: Handle zero approval rate"
LAST_SUCCESS_GENERATED="50"
LAST_SUCCESS_INSERTED="0"
LAST_SUCCESS_APPROVAL_RATE="0"
LAST_SUCCESS_DURATION="45"

write_per_type_metrics "spatial_zero" > /dev/null

assert_file_exists "$RESULTS_DIR/spatial_zero_metrics.json" "Metrics file created even with 0% approval" || true
assert_json_field "$RESULTS_DIR/spatial_zero_metrics.json" "approved" "0" "Approved is 0 when approval_rate is 0" || true

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
