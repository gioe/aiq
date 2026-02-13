#!/bin/bash
#
# validate-universal-links.sh
#
# Validates the apple-app-site-association (AASA) file deployment for Universal Links.
# Checks that the file is properly deployed, accessible, and correctly configured.
#
# Usage:
#   ./ios/scripts/validate-universal-links.sh [--team-id TEAM_ID] [--bundle-id BUNDLE_ID] [--domain DOMAIN]
#
# Environment Variables:
#   APNS_TEAM_ID  - Apple Developer Team ID (10 characters)
#   BUNDLE_ID     - App bundle identifier (defaults to com.aiq.app)
#   DOMAIN        - Domain to check (defaults to aiq.app)
#
# Exit codes:
#   0 - All validations passed
#   1 - Validation failed or error occurred

set -eo pipefail

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
DEFAULT_BUNDLE_ID="com.aiq.app"
DEFAULT_DOMAIN="aiq.app"
DEV_DOMAIN="dev.aiq.app"

# Parse arguments
TEAM_ID="${APNS_TEAM_ID:-}"
BUNDLE_ID="${BUNDLE_ID:-$DEFAULT_BUNDLE_ID}"
DOMAIN="${DOMAIN:-$DEFAULT_DOMAIN}"

while [[ $# -gt 0 ]]; do
    case $1 in
        --team-id)
            TEAM_ID="$2"
            shift 2
            ;;
        --bundle-id)
            BUNDLE_ID="$2"
            shift 2
            ;;
        --domain)
            DOMAIN="$2"
            shift 2
            ;;
        --dev)
            DOMAIN="$DEV_DOMAIN"
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--team-id TEAM_ID] [--bundle-id BUNDLE_ID] [--domain DOMAIN] [--dev]"
            echo ""
            echo "Validates the apple-app-site-association file for Universal Links."
            echo ""
            echo "Options:"
            echo "  --team-id     Apple Developer Team ID (10 characters)"
            echo "  --bundle-id   App bundle identifier (default: $DEFAULT_BUNDLE_ID)"
            echo "  --domain      Domain to check (default: $DEFAULT_DOMAIN)"
            echo "  --dev         Use development domain ($DEV_DOMAIN)"
            echo "  --help, -h    Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  APNS_TEAM_ID  - Apple Developer Team ID (alternative to --team-id)"
            echo "  BUNDLE_ID     - App bundle identifier (alternative to --bundle-id)"
            echo "  DOMAIN        - Domain to check (alternative to --domain)"
            echo ""
            echo "Examples:"
            echo "  $0 --team-id ABCD123456                    # Validate production domain"
            echo "  $0 --team-id ABCD123456 --dev              # Validate dev domain"
            echo "  $0 --team-id ABCD123456 --domain staging.aiq.app  # Validate custom domain"
            exit 0
            ;;
        *)
            echo -e "${RED}[ERROR]${NC} Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Validate Team ID is provided
if [[ -z "$TEAM_ID" ]]; then
    echo -e "${RED}[ERROR]${NC} Team ID is required."
    echo "Provide via --team-id argument or APNS_TEAM_ID environment variable."
    echo "Use --help for usage information"
    exit 1
fi

# Validate Team ID format (should be 10 alphanumeric characters)
if ! [[ "$TEAM_ID" =~ ^[A-Z0-9]{10}$ ]]; then
    echo -e "${YELLOW}[WARNING]${NC} Team ID '$TEAM_ID' may be invalid."
    echo "Expected format: 10 alphanumeric characters (e.g., ABCD123456)"
fi

# Validate domain format (alphanumeric with dots and hyphens, no path or protocol)
if ! [[ "$DOMAIN" =~ ^[a-zA-Z0-9][a-zA-Z0-9.-]*[a-zA-Z0-9]$ ]]; then
    echo -e "${RED}[ERROR]${NC} Invalid domain format: '$DOMAIN'"
    echo "Expected format: domain name only (e.g., aiq.app, www.example.com)"
    echo "Do not include protocol (https://) or path"
    exit 1
fi

# Construct expected appID
EXPECTED_APP_ID="${TEAM_ID}.${BUNDLE_ID}"
AASA_URL="https://${DOMAIN}/.well-known/apple-app-site-association"

echo -e "${BLUE}=== Universal Links Validation ===${NC}"
echo ""
echo "Configuration:"
echo "  Domain:     $DOMAIN"
echo "  Team ID:    $TEAM_ID"
echo "  Bundle ID:  $BUNDLE_ID"
echo "  App ID:     $EXPECTED_APP_ID"
echo "  AASA URL:   $AASA_URL"
echo ""

# Track validation results
PASS_COUNT=0
FAIL_COUNT=0
TOTAL_CHECKS=0

check_pass() {
    echo -e "  ${GREEN}✓${NC} $1"
    PASS_COUNT=$((PASS_COUNT + 1))
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
}

check_fail() {
    echo -e "  ${RED}✗${NC} $1"
    FAIL_COUNT=$((FAIL_COUNT + 1))
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
}

check_warn() {
    echo -e "  ${YELLOW}!${NC} $1"
}

# Step 1: Fetch the AASA file
echo -e "${BLUE}[1/5]${NC} Fetching AASA file..."
HTTP_RESPONSE=$(curl -s -w "\n%{http_code}" --connect-timeout 10 "$AASA_URL" 2>&1) || {
    check_fail "Failed to connect to $DOMAIN"
    echo ""
    echo -e "${RED}[RESULT]${NC} Validation FAILED"
    echo "Could not connect to the server. Check that the domain is accessible."
    exit 1
}

HTTP_BODY=$(echo "$HTTP_RESPONSE" | sed '$d')
HTTP_CODE=$(echo "$HTTP_RESPONSE" | tail -n1)

if [[ "$HTTP_CODE" == "200" ]]; then
    check_pass "AASA file accessible (HTTP 200)"
else
    check_fail "AASA file not accessible (HTTP $HTTP_CODE)"
    echo ""
    echo "Response body:"
    echo "$HTTP_BODY" | head -5
    echo ""
    echo -e "${RED}[RESULT]${NC} Validation FAILED"
    echo "The AASA file must be accessible at $AASA_URL"
    exit 1
fi

# Step 2: Validate JSON structure
echo ""
echo -e "${BLUE}[2/5]${NC} Validating JSON structure..."

# Check if it's valid JSON
JSON_VALID=false
if echo "$HTTP_BODY" | jq empty >/dev/null 2>&1; then
    JSON_VALID=true
fi

if [[ "$JSON_VALID" == "true" ]]; then
    check_pass "Valid JSON format"
else
    check_fail "Invalid JSON format"
    echo ""
    echo "Response is not valid JSON:"
    echo "$HTTP_BODY" | head -10
    echo ""
    echo -e "${RED}[RESULT]${NC} Validation FAILED"
    exit 1
fi

# Check for applinks key
if echo "$HTTP_BODY" | jq -e '.applinks' > /dev/null 2>&1; then
    check_pass "'applinks' key present"
else
    check_fail "'applinks' key missing"
    echo ""
    echo "AASA file must contain an 'applinks' key for Universal Links"
    echo ""
    echo -e "${RED}[RESULT]${NC} Validation FAILED"
    exit 1
fi

# Check for details or substitutionVariables (iOS 14+ format)
if echo "$HTTP_BODY" | jq -e '.applinks.details' > /dev/null 2>&1; then
    check_pass "'applinks.details' key present"
    DETAILS_PATH=".applinks.details"
elif echo "$HTTP_BODY" | jq -e '.applinks.apps' > /dev/null 2>&1; then
    check_warn "Using legacy 'applinks.apps' format (consider updating to iOS 14+ format)"
    DETAILS_PATH=".applinks"
else
    check_fail "Missing 'applinks.details' or 'applinks.apps' key"
    echo ""
    echo -e "${RED}[RESULT]${NC} Validation FAILED"
    exit 1
fi

# Step 3: Validate appID
echo ""
echo -e "${BLUE}[3/5]${NC} Validating App ID..."

# Extract all appIDs from the AASA file
APP_IDS=$(echo "$HTTP_BODY" | jq -r '
    if .applinks.details then
        .applinks.details[].appIDs[]? // .applinks.details[].appID?
    else
        .applinks.apps[]?
    end
' 2>/dev/null | sort -u | grep -v '^null$' || true)

if [[ -z "$APP_IDS" ]]; then
    # Try alternate structure
    APP_IDS=$(echo "$HTTP_BODY" | jq -r '.applinks.details[]?.appID // empty' 2>/dev/null | sort -u || true)
fi

if [[ -z "$APP_IDS" ]]; then
    check_fail "No App IDs found in AASA file"
    echo ""
    echo "AASA structure:"
    echo "$HTTP_BODY" | jq '.' 2>/dev/null | head -20
    echo ""
    echo -e "${RED}[RESULT]${NC} Validation FAILED"
    exit 1
fi

echo "  Found App IDs:"
echo "$APP_IDS" | while read -r id; do
    if [[ -n "$id" ]]; then
        echo "    - $id"
    fi
done

# Check if expected appID is present
if echo "$APP_IDS" | grep -q "^${EXPECTED_APP_ID}$"; then
    check_pass "Expected App ID '${EXPECTED_APP_ID}' found"
else
    check_fail "Expected App ID '${EXPECTED_APP_ID}' NOT found"
    echo ""
    echo "Make sure the AASA file contains your app's Team ID and Bundle ID"
fi

# Step 4: Validate paths/components
echo ""
echo -e "${BLUE}[4/5]${NC} Validating URL patterns..."

# Extract paths or components
PATHS=$(echo "$HTTP_BODY" | jq -r '
    if .applinks.details then
        .applinks.details[].paths[]? // .applinks.details[].components[].path? // "N/A"
    else
        "N/A"
    end
' 2>/dev/null | sort -u | head -10 || echo "N/A")

COMPONENTS=$(echo "$HTTP_BODY" | jq -r '
    .applinks.details[].components[]? |
    if . then
        if .["#"] then "#" + .["#"]
        elif .path then .path
        elif .["/"] then .["/"]
        else "complex pattern"
        end
    else empty end
' 2>/dev/null | sort -u | head -10 || true)

if [[ -n "$COMPONENTS" && "$COMPONENTS" != "N/A" ]]; then
    check_pass "URL components defined"
    echo "  Components found:"
    echo "$COMPONENTS" | while read -r comp; do
        if [[ -n "$comp" ]]; then
            echo "    - $comp"
        fi
    done
elif [[ -n "$PATHS" && "$PATHS" != "N/A" ]]; then
    check_pass "URL paths defined"
    echo "  Paths found:"
    echo "$PATHS" | while read -r path; do
        if [[ -n "$path" ]]; then
            echo "    - $path"
        fi
    done
else
    check_warn "No URL paths or components found (app may handle all URLs)"
fi

# Step 5: Check Content-Type header
echo ""
echo -e "${BLUE}[5/5]${NC} Checking HTTP headers..."

CONTENT_TYPE=$(curl -s -I --connect-timeout 10 "$AASA_URL" 2>/dev/null | grep -i "content-type:" | tr -d '\r' || true)

if echo "$CONTENT_TYPE" | grep -qi "application/json"; then
    check_pass "Content-Type is application/json"
elif echo "$CONTENT_TYPE" | grep -qi "application/pkcs7-mime"; then
    check_pass "Content-Type is application/pkcs7-mime (signed)"
elif [[ -z "$CONTENT_TYPE" ]]; then
    check_warn "Content-Type header not found (recommended: application/json)"
else
    check_warn "Unexpected Content-Type: $CONTENT_TYPE"
    echo "  Recommended: application/json or application/pkcs7-mime"
fi

# Summary
echo ""
echo -e "${BLUE}=== Validation Summary ===${NC}"
echo ""
echo "  Passed: $PASS_COUNT/$TOTAL_CHECKS"
echo "  Failed: $FAIL_COUNT/$TOTAL_CHECKS"
echo ""

if [[ $FAIL_COUNT -eq 0 ]]; then
    echo -e "${GREEN}[RESULT]${NC} All validations PASSED"
    echo ""
    echo "Universal Links should work correctly for $DOMAIN"
    exit 0
else
    echo -e "${RED}[RESULT]${NC} Validation FAILED ($FAIL_COUNT issues found)"
    echo ""
    echo "Please fix the issues above and run this script again."
    exit 1
fi
