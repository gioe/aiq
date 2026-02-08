#!/usr/bin/env bash
# Verify OTEL/Grafana integration for the question-service.
# Run locally or on Railway to check that all required env vars are set
# and the metrics endpoint is reachable.
#
# Usage:
#   ./verify-otel-setup.sh                  # Check local env vars
#   ./verify-otel-setup.sh <trigger-url>    # Also test /metrics endpoint

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "${GREEN}✓${NC} $1"; }
fail() { echo -e "${RED}✗${NC} $1"; ERRORS=$((ERRORS + 1)); }
warn() { echo -e "${YELLOW}!${NC} $1"; }

ERRORS=0

echo "=== AIQ Question Service OTEL/Grafana Setup Verification ==="
echo ""

# --- Question-service env vars ---
echo "--- Question-Service Environment Variables ---"

if [ -n "${OTEL_EXPORTER_OTLP_ENDPOINT:-}" ]; then
  pass "OTEL_EXPORTER_OTLP_ENDPOINT is set: ${OTEL_EXPORTER_OTLP_ENDPOINT}"
else
  fail "OTEL_EXPORTER_OTLP_ENDPOINT is not set"
fi

if [ -n "${OTEL_EXPORTER_OTLP_HEADERS:-}" ]; then
  pass "OTEL_EXPORTER_OTLP_HEADERS is set (value hidden)"
else
  warn "OTEL_EXPORTER_OTLP_HEADERS is not set (OK if using Alloy-only approach)"
fi

if [ -n "${SENTRY_DSN:-}" ]; then
  pass "SENTRY_DSN is set (value hidden)"
else
  warn "SENTRY_DSN is not set (error tracking disabled)"
fi

if [ -n "${ENV:-}" ]; then
  pass "ENV is set: ${ENV}"
else
  warn "ENV is not set (defaults to 'development')"
fi

echo ""

# --- Alloy env vars (if running on the Alloy service) ---
echo "--- Alloy Service Environment Variables (optional if not on Alloy service) ---"

if [ -n "${GRAFANA_PROMETHEUS_HOST:-}" ]; then
  pass "GRAFANA_PROMETHEUS_HOST is set: ${GRAFANA_PROMETHEUS_HOST}"
else
  warn "GRAFANA_PROMETHEUS_HOST is not set"
fi

if [ -n "${GRAFANA_PROMETHEUS_USERNAME:-}" ]; then
  pass "GRAFANA_PROMETHEUS_USERNAME is set"
else
  warn "GRAFANA_PROMETHEUS_USERNAME is not set"
fi

if [ -n "${GRAFANA_PROMETHEUS_PASSWORD:-}" ]; then
  pass "GRAFANA_PROMETHEUS_PASSWORD is set (value hidden)"
else
  warn "GRAFANA_PROMETHEUS_PASSWORD is not set"
fi

echo ""

# --- Test /metrics endpoint ---
TRIGGER_URL="${1:-}"
if [ -n "$TRIGGER_URL" ]; then
  echo "--- Testing /metrics Endpoint ---"
  METRICS_URL="${TRIGGER_URL%/}/metrics"

  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$METRICS_URL" 2>/dev/null || echo "000")
  if [ "$HTTP_CODE" = "200" ]; then
    pass "/metrics endpoint returned 200"

    # Check for expected metric names
    METRICS_OUTPUT=$(curl -s --max-time 10 "$METRICS_URL" 2>/dev/null)
    if echo "$METRICS_OUTPUT" | grep -q "aiq_question_service_http_requests_total"; then
      pass "Found aiq_question_service_http_requests_total metric"
    else
      fail "Missing aiq_question_service_http_requests_total metric"
    fi

    if echo "$METRICS_OUTPUT" | grep -q "aiq_question_service_http_request_duration_seconds"; then
      pass "Found aiq_question_service_http_request_duration_seconds metric"
    else
      fail "Missing aiq_question_service_http_request_duration_seconds metric"
    fi
  elif [ "$HTTP_CODE" = "000" ]; then
    fail "Could not connect to $METRICS_URL (connection failed)"
  else
    fail "/metrics endpoint returned HTTP $HTTP_CODE"
  fi
else
  warn "No trigger URL provided, skipping /metrics endpoint test"
  echo "  Usage: $0 https://your-trigger-service-url"
fi

echo ""
echo "=== Summary ==="
if [ $ERRORS -gt 0 ]; then
  echo -e "${RED}$ERRORS error(s) found. Please fix the issues above.${NC}"
  exit 1
else
  echo -e "${GREEN}All checks passed!${NC}"
  exit 0
fi
