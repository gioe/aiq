#!/bin/bash
# Certificate Expiration Monitoring Script for AIQ iOS App
#
# This script checks the SSL certificate expiration status for the AIQ backend
# and compares it against the pinned certificates in TrustKit.plist.
#
# Usage:
#   ./check_certificate_expiration.sh           # Check status
#   ./check_certificate_expiration.sh --json    # Output as JSON
#   ./check_certificate_expiration.sh --quiet   # Only output warnings/errors
#
# Exit codes:
#   0 - All certificates valid, more than 30 days until expiration
#   1 - Warning: Certificate expires within 30 days
#   2 - Error: Certificate expired or connection failed

set -euo pipefail

# Configuration
DOMAIN="aiq-backend-production.up.railway.app"
WARNING_DAYS=30
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TRUSTKIT_PLIST="${SCRIPT_DIR}/../AIQ/TrustKit.plist"

# Parse arguments
OUTPUT_FORMAT="text"
QUIET=false
for arg in "$@"; do
    case $arg in
        --json)
            OUTPUT_FORMAT="json"
            ;;
        --quiet)
            QUIET=true
            ;;
        --help)
            echo "Usage: $0 [--json] [--quiet] [--help]"
            echo ""
            echo "Options:"
            echo "  --json    Output results as JSON"
            echo "  --quiet   Only output warnings and errors"
            echo "  --help    Show this help message"
            exit 0
            ;;
    esac
done

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Function to output based on format
output_text() {
    if [ "$QUIET" = false ]; then
        echo -e "$1"
    fi
}

# Function to calculate days until date
days_until() {
    local target_date="$1"
    local today=$(date +%s)
    local target=$(date -j -f "%b %d %T %Y %Z" "$target_date" +%s 2>/dev/null || date -d "$target_date" +%s 2>/dev/null)
    echo $(( (target - today) / 86400 ))
}

# Function to extract date in a portable way
parse_cert_date() {
    local date_str="$1"
    # Handle format: "Mar  6 23:59:59 2026 GMT"
    echo "$date_str"
}

output_text "=============================================="
output_text "AIQ Certificate Expiration Monitor"
output_text "=============================================="
output_text ""
output_text "Checking: ${DOMAIN}"
output_text "Date: $(date '+%Y-%m-%d %H:%M:%S')"
output_text ""

# Get certificate information
CERT_INFO=$(echo | openssl s_client -servername "$DOMAIN" -connect "${DOMAIN}:443" 2>/dev/null)
if [ $? -ne 0 ] || [ -z "$CERT_INFO" ]; then
    echo -e "${RED}ERROR: Failed to connect to ${DOMAIN}${NC}"
    exit 2
fi

# Extract certificate details
CERT_DATES=$(echo "$CERT_INFO" | openssl x509 -noout -dates 2>/dev/null)
CERT_SUBJECT=$(echo "$CERT_INFO" | openssl x509 -noout -subject 2>/dev/null | sed 's/subject=//')
CERT_ISSUER=$(echo "$CERT_INFO" | openssl x509 -noout -issuer 2>/dev/null | sed 's/issuer=//')

# Parse dates
NOT_BEFORE=$(echo "$CERT_DATES" | grep notBefore | cut -d= -f2)
NOT_AFTER=$(echo "$CERT_DATES" | grep notAfter | cut -d= -f2)

# Calculate days until expiration
DAYS_REMAINING=$(days_until "$NOT_AFTER")

# Get current certificate hash
CURRENT_HASH=$(echo "$CERT_INFO" | openssl x509 -pubkey -noout 2>/dev/null | \
    openssl pkey -pubin -outform der 2>/dev/null | \
    openssl dgst -sha256 -binary 2>/dev/null | \
    base64)

output_text "Backend Certificate Details:"
output_text "-------------------------------------------"
output_text "Subject: $CERT_SUBJECT"
output_text "Issuer: $CERT_ISSUER"
output_text "Valid From: $NOT_BEFORE"
output_text "Valid Until: $NOT_AFTER"
output_text "Days Remaining: $DAYS_REMAINING"
output_text "Current Hash: $CURRENT_HASH"
output_text ""

# Check TrustKit.plist configuration
if [ -f "$TRUSTKIT_PLIST" ]; then
    output_text "TrustKit.plist Configuration:"
    output_text "-------------------------------------------"

    # Extract pinned hashes from plist using plutil for reliable parsing
    # Fall back to grep if plutil output parsing fails
    PINNED_HASHES=""
    if command -v plutil &> /dev/null; then
        # Use plutil to convert plist to XML and extract strings from TSKPublicKeyHashes
        PINNED_HASHES=$(plutil -extract TSKPinnedDomains.aiq-backend-production\\.up\\.railway\\.app.TSKPublicKeyHashes xml1 -o - "$TRUSTKIT_PLIST" 2>/dev/null | \
            grep '<string>' | \
            sed 's/.*<string>//g; s/<\/string>.*//g' || true)
    fi

    # Fallback: grep-based extraction if plutil fails
    if [ -z "$PINNED_HASHES" ]; then
        PINNED_HASHES=$(awk '/<key>TSKPublicKeyHashes<\/key>/,/<\/array>/' "$TRUSTKIT_PLIST" | \
            grep '<string>' | \
            sed 's/.*<string>//g; s/<\/string>.*//g' || true)
    fi

    if [ -n "$PINNED_HASHES" ]; then
        output_text "Pinned Hashes:"
        HASH_MATCH=false
        while IFS= read -r hash; do
            if [ "$hash" = "$CURRENT_HASH" ]; then
                output_text "  ${GREEN}[MATCH]${NC} $hash"
                HASH_MATCH=true
            else
                output_text "  [PINNED] $hash"
            fi
        done <<< "$PINNED_HASHES"

        if [ "$HASH_MATCH" = false ]; then
            echo -e "${RED}WARNING: Current certificate hash NOT found in TrustKit.plist!${NC}"
            echo -e "${RED}This will cause connection failures in RELEASE builds!${NC}"
        fi
    else
        output_text "  Could not extract hashes from TrustKit.plist"
    fi
else
    output_text "${YELLOW}WARNING: TrustKit.plist not found at: ${TRUSTKIT_PLIST}${NC}"
fi

output_text ""

# Determine status and exit code
EXIT_CODE=0
STATUS="OK"

if [ "$DAYS_REMAINING" -lt 0 ]; then
    echo -e "${RED}=============================================="
    echo -e "CRITICAL: CERTIFICATE HAS EXPIRED!"
    echo -e "==============================================${NC}"
    echo ""
    echo "The Railway backend certificate expired $((DAYS_REMAINING * -1)) days ago."
    echo "All RELEASE builds will fail to connect to the backend."
    echo ""
    echo "IMMEDIATE ACTION REQUIRED:"
    echo "1. Check if Railway has issued a new certificate"
    echo "2. Generate new certificate hash"
    echo "3. Update TrustKit.plist"
    echo "4. Push emergency app update"
    EXIT_CODE=2
    STATUS="EXPIRED"
elif [ "$DAYS_REMAINING" -le "$WARNING_DAYS" ]; then
    echo -e "${YELLOW}=============================================="
    echo -e "WARNING: Certificate expires in $DAYS_REMAINING days"
    echo -e "==============================================${NC}"
    echo ""
    echo "The Railway backend certificate will expire on: $NOT_AFTER"
    echo ""
    echo "ACTION REQUIRED:"
    echo "1. Follow the Certificate Rotation Runbook"
    echo "2. Generate new certificate hash (may need to wait for Railway renewal)"
    echo "3. Update TrustKit.plist"
    echo "4. Submit app update before $NOT_AFTER"
    EXIT_CODE=1
    STATUS="WARNING"
else
    output_text "${GREEN}=============================================="
    output_text "Certificate Status: OK"
    output_text "==============================================${NC}"
    output_text ""
    output_text "Certificate expires in $DAYS_REMAINING days."
    output_text "Next check recommended: $(date -v+7d '+%Y-%m-%d' 2>/dev/null || date -d '+7 days' '+%Y-%m-%d' 2>/dev/null || echo 'in 7 days')"
fi

# JSON output if requested
if [ "$OUTPUT_FORMAT" = "json" ]; then
    cat << EOF
{
  "domain": "$DOMAIN",
  "check_time": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
  "certificate": {
    "subject": "$CERT_SUBJECT",
    "issuer": "$CERT_ISSUER",
    "not_before": "$NOT_BEFORE",
    "not_after": "$NOT_AFTER",
    "days_remaining": $DAYS_REMAINING,
    "current_hash": "$CURRENT_HASH"
  },
  "status": "$STATUS",
  "warning_threshold_days": $WARNING_DAYS
}
EOF
fi

exit $EXIT_CODE
