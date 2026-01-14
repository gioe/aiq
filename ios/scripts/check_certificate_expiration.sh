#!/bin/bash
# Certificate Expiration Monitoring Script for AIQ iOS App
#
# This script checks the SSL certificate expiration status for the AIQ backend
# and compares it against the pinned certificates in TrustKit.plist.
#
# Usage:
#   ./check_certificate_expiration.sh                          # Check status
#   ./check_certificate_expiration.sh --json                   # Output as JSON
#   ./check_certificate_expiration.sh --quiet                  # Only output warnings/errors
#   ./check_certificate_expiration.sh --domain example.com     # Check specific domain
#
# Exit codes:
#   0 - All certificates valid, hash matches, more than 30 days until expiration
#   1 - Warning: Certificate expires within 30 days
#   2 - Error: Certificate expired or connection failed
#   3 - Error: Certificate hash mismatch (production will fail!)
#   4 - Error: TrustKit.plist not found or invalid

set -euo pipefail

# Configuration defaults
DOMAIN="aiq-backend-production.up.railway.app"
WARNING_DAYS=30
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TRUSTKIT_PLIST="${SCRIPT_DIR}/../AIQ/TrustKit.plist"

# Parse arguments
OUTPUT_FORMAT="text"
QUIET=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --json)
            OUTPUT_FORMAT="json"
            shift
            ;;
        --quiet)
            QUIET=true
            shift
            ;;
        --domain)
            DOMAIN="$2"
            shift 2
            ;;
        --plist)
            TRUSTKIT_PLIST="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --json              Output results as JSON"
            echo "  --quiet             Only output warnings and errors"
            echo "  --domain DOMAIN     Check specific domain (default: aiq-backend-production.up.railway.app)"
            echo "  --plist PATH        Path to TrustKit.plist (default: ../AIQ/TrustKit.plist)"
            echo "  --help              Show this help message"
            echo ""
            echo "Exit codes:"
            echo "  0 - OK: Certificate valid, hash matches"
            echo "  1 - Warning: Certificate expires within $WARNING_DAYS days"
            echo "  2 - Error: Certificate expired or connection failed"
            echo "  3 - Error: Certificate hash mismatch"
            echo "  4 - Error: TrustKit.plist not found or invalid"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
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

# Function to output errors (always shown)
output_error() {
    echo -e "${RED}$1${NC}" >&2
}

# Cross-platform date calculation (works on macOS and Linux)
days_until() {
    local target_date="$1"
    local today_epoch target_epoch

    today_epoch=$(date +%s)

    # Try macOS format first, then GNU date
    if date -j -f "%b %d %T %Y %Z" "$target_date" +%s >/dev/null 2>&1; then
        target_epoch=$(date -j -f "%b %d %T %Y %Z" "$target_date" +%s)
    elif date -d "$target_date" +%s >/dev/null 2>&1; then
        target_epoch=$(date -d "$target_date" +%s)
    else
        # Last resort: parse manually for common OpenSSL format "Mon DD HH:MM:SS YYYY GMT"
        # Convert to ISO format and try again
        local month day time year
        read -r month day time year _ <<< "$target_date"
        local month_num
        case $month in
            Jan) month_num=01 ;; Feb) month_num=02 ;; Mar) month_num=03 ;;
            Apr) month_num=04 ;; May) month_num=05 ;; Jun) month_num=06 ;;
            Jul) month_num=07 ;; Aug) month_num=08 ;; Sep) month_num=09 ;;
            Oct) month_num=10 ;; Nov) month_num=11 ;; Dec) month_num=12 ;;
            *) output_error "ERROR: Cannot parse date: $target_date"; exit 2 ;;
        esac
        # Try with ISO format
        local iso_date="${year}-${month_num}-$(printf '%02d' "$day")T${time}Z"
        if date -d "$iso_date" +%s >/dev/null 2>&1; then
            target_epoch=$(date -d "$iso_date" +%s)
        else
            output_error "ERROR: Cannot parse date on this platform: $target_date"
            exit 2
        fi
    fi

    echo $(( (target_epoch - today_epoch) / 86400 ))
}

# Cross-platform date addition for "next check" recommendation
next_check_date() {
    if date -v+7d '+%Y-%m-%d' 2>/dev/null; then
        return
    elif date -d '+7 days' '+%Y-%m-%d' 2>/dev/null; then
        return
    else
        echo "in 7 days"
    fi
}

# Validate TrustKit.plist exists and is readable
if [ ! -f "$TRUSTKIT_PLIST" ]; then
    output_error "ERROR: TrustKit.plist not found at: $TRUSTKIT_PLIST"
    if [ "$OUTPUT_FORMAT" = "json" ]; then
        echo '{"error": "TrustKit.plist not found", "status": "CONFIG_ERROR"}'
    fi
    exit 4
fi

if [ ! -r "$TRUSTKIT_PLIST" ]; then
    output_error "ERROR: TrustKit.plist not readable at: $TRUSTKIT_PLIST"
    if [ "$OUTPUT_FORMAT" = "json" ]; then
        echo '{"error": "TrustKit.plist not readable", "status": "CONFIG_ERROR"}'
    fi
    exit 4
fi

output_text "=============================================="
output_text "AIQ Certificate Expiration Monitor"
output_text "=============================================="
output_text ""
output_text "Checking: ${DOMAIN}"
output_text "Date: $(date '+%Y-%m-%d %H:%M:%S')"
output_text ""

# Get certificate information - capture both stdout and stderr
SSL_ERROR_LOG=$(mktemp)
CERT_INFO=$(echo | openssl s_client -servername "$DOMAIN" -connect "${DOMAIN}:443" 2>"$SSL_ERROR_LOG") || true

# Check for connection errors
if [ -z "$CERT_INFO" ]; then
    output_error "ERROR: Failed to connect to ${DOMAIN}"
    if [ -s "$SSL_ERROR_LOG" ]; then
        output_error "SSL Error details:"
        cat "$SSL_ERROR_LOG" >&2
    fi
    rm -f "$SSL_ERROR_LOG"
    if [ "$OUTPUT_FORMAT" = "json" ]; then
        echo '{"error": "Connection failed", "domain": "'"$DOMAIN"'", "status": "CONNECTION_ERROR"}'
    fi
    exit 2
fi

# Check for SSL-specific errors that might indicate security issues
if grep -qi "certificate verify failed\|self.signed\|unable to verify\|handshake failure" "$SSL_ERROR_LOG" 2>/dev/null; then
    output_error "WARNING: SSL verification issues detected:"
    grep -i "certificate\|verify\|handshake" "$SSL_ERROR_LOG" >&2 || true
fi
rm -f "$SSL_ERROR_LOG"

# Extract certificate details
CERT_DATES=$(echo "$CERT_INFO" | openssl x509 -noout -dates 2>/dev/null) || {
    output_error "ERROR: Failed to parse certificate from ${DOMAIN}"
    exit 2
}
CERT_SUBJECT=$(echo "$CERT_INFO" | openssl x509 -noout -subject 2>/dev/null | sed 's/subject=//' || echo "Unknown")
CERT_ISSUER=$(echo "$CERT_INFO" | openssl x509 -noout -issuer 2>/dev/null | sed 's/issuer=//' || echo "Unknown")

# Parse dates
NOT_BEFORE=$(echo "$CERT_DATES" | grep notBefore | cut -d= -f2)
NOT_AFTER=$(echo "$CERT_DATES" | grep notAfter | cut -d= -f2)

if [ -z "$NOT_AFTER" ]; then
    output_error "ERROR: Could not extract certificate expiration date"
    exit 2
fi

# Calculate days until expiration
DAYS_REMAINING=$(days_until "$NOT_AFTER")

# Get current certificate hash
CURRENT_HASH=$(echo "$CERT_INFO" | openssl x509 -pubkey -noout 2>/dev/null | \
    openssl pkey -pubin -outform der 2>/dev/null | \
    openssl dgst -sha256 -binary 2>/dev/null | \
    base64) || {
    output_error "ERROR: Failed to compute certificate hash"
    exit 2
}

output_text "Backend Certificate Details:"
output_text "-------------------------------------------"
output_text "Subject: $CERT_SUBJECT"
output_text "Issuer: $CERT_ISSUER"
output_text "Valid From: $NOT_BEFORE"
output_text "Valid Until: $NOT_AFTER"
output_text "Days Remaining: $DAYS_REMAINING"
output_text "Current Hash: $CURRENT_HASH"
output_text ""

# Check TrustKit.plist configuration and hash matching
output_text "TrustKit.plist Configuration:"
output_text "-------------------------------------------"

# Extract pinned hashes from plist using plutil for reliable parsing
# Fall back to awk if plutil output parsing fails
PINNED_HASHES=""
if command -v plutil &> /dev/null; then
    # Use plutil to convert plist to XML and extract strings from TSKPublicKeyHashes
    PINNED_HASHES=$(plutil -extract TSKPinnedDomains.aiq-backend-production\\.up\\.railway\\.app.TSKPublicKeyHashes xml1 -o - "$TRUSTKIT_PLIST" 2>/dev/null | \
        grep '<string>' | \
        sed 's/.*<string>//g; s/<\/string>.*//g' || true)
fi

# Fallback: awk-based extraction if plutil fails (works on Linux)
if [ -z "$PINNED_HASHES" ]; then
    PINNED_HASHES=$(awk '/<key>TSKPublicKeyHashes<\/key>/,/<\/array>/' "$TRUSTKIT_PLIST" | \
        grep '<string>' | \
        sed 's/.*<string>//g; s/<\/string>.*//g' || true)
fi

# Validate hash extraction succeeded
if [ -z "$PINNED_HASHES" ]; then
    output_error "ERROR: Could not extract pinned hashes from TrustKit.plist"
    output_error "This may indicate a malformed plist file."
    if [ "$OUTPUT_FORMAT" = "json" ]; then
        echo '{"error": "Failed to extract hashes from TrustKit.plist", "status": "CONFIG_ERROR"}'
    fi
    exit 4
fi

# Check for hash match
HASH_MATCH=false
output_text "Pinned Hashes:"
while IFS= read -r hash; do
    if [ -z "$hash" ]; then
        continue
    fi
    if [ "$hash" = "$CURRENT_HASH" ]; then
        output_text "  ${GREEN}[MATCH]${NC} $hash"
        HASH_MATCH=true
    else
        output_text "  [PINNED] $hash"
    fi
done <<< "$PINNED_HASHES"

output_text ""

# Determine status and exit code
EXIT_CODE=0
STATUS="OK"

# CRITICAL: Hash mismatch is a fatal error (exit code 3)
if [ "$HASH_MATCH" = false ]; then
    echo -e "${RED}=============================================="
    echo -e "CRITICAL: CERTIFICATE HASH MISMATCH!"
    echo -e "==============================================${NC}"
    echo ""
    echo "The current server certificate hash does NOT match any pinned hash in TrustKit.plist!"
    echo ""
    echo "Current hash: $CURRENT_HASH"
    echo ""
    echo "This means:"
    echo "  - ALL RELEASE builds will fail to connect to the backend"
    echo "  - Production users cannot use the app"
    echo ""
    echo "IMMEDIATE ACTION REQUIRED:"
    echo "1. Verify this is the expected certificate (not MITM attack)"
    echo "2. Add the new hash to TrustKit.plist"
    echo "3. Submit emergency app update"
    EXIT_CODE=3
    STATUS="HASH_MISMATCH"
elif [ "$DAYS_REMAINING" -lt 0 ]; then
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
    output_text "Hash validation: PASSED"
    output_text "Next check recommended: $(next_check_date)"
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
  "hash_match": $HASH_MATCH,
  "status": "$STATUS",
  "warning_threshold_days": $WARNING_DAYS
}
EOF
fi

exit $EXIT_CODE
