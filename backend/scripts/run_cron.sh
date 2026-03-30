#!/bin/bash
# Cron wrapper script for AIQ Backend IRT Calibration
#
# Derived from libs/templates/run_cron.sh.template.
# See libs/templates/README.md for the 5-step setup workflow.
#
# In production this job is scheduled via Railway (backend/infra/railway-cron-calibration.json).
# Use this script for local scheduling or non-Railway environments.
#
# Usage:
#   Add to crontab:
#   0 4 * * 0 /path/to/aiq/backend/scripts/run_cron.sh >> /path/to/logs/cron.log 2>&1

# ── Configure these four values ──────────────────────────────────────────────
SERVICE_NAME="AIQ Backend IRT Calibration"
REQUIRED_ENV_VARS="DATABASE_URL"
SCRIPT_PATH="scripts/run_irt_calibration.py"
PYTHON_ARGS=""
# ─────────────────────────────────────────────────────────────────────────────

# Exit on error
set -e

# Determine script directory (works even if called via symlink)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="$(dirname "$SCRIPT_DIR")"

echo "================================================================"
echo "$SERVICE_NAME - Cron Run"
echo "Started: $(date)"
echo "Service directory: $SERVICE_DIR"
echo "================================================================"

# Change to service directory
cd "$SERVICE_DIR" || {
    echo "ERROR: Failed to change to service directory: $SERVICE_DIR"
    exit 1
}

# Activate virtual environment
if [ -f "venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    # shellcheck disable=SC1091
    source venv/bin/activate
else
    echo "ERROR: Virtual environment not found at $SERVICE_DIR/venv"
    exit 1
fi

# Load environment variables from .env file
if [ -f ".env" ]; then
    echo "Loading environment variables from .env..."
    # Export variables from .env (skip comments and empty lines)
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
else
    echo "WARNING: .env file not found, using existing environment variables"
fi

# Verify required environment variables
for VAR in $REQUIRED_ENV_VARS; do
    if [ -z "${!VAR}" ]; then
        echo "ERROR: Required environment variable $VAR is not set"
        exit 3
    fi
done

# Create logs directory if it doesn't exist
mkdir -p logs

# Run the configured script
echo ""
echo "Running $SERVICE_NAME..."
echo "----------------------------------------------------------------"

# shellcheck disable=SC2086
python "$SCRIPT_PATH" $PYTHON_ARGS

# Capture exit code
EXIT_CODE=$?

echo "----------------------------------------------------------------"
echo "$SERVICE_NAME completed with exit code: $EXIT_CODE"
echo "Finished: $(date)"
echo "================================================================"

# Optional: Send email notification on failure
# Uncomment and configure if you want email alerts
#
# if [ $EXIT_CODE -ne 0 ]; then
#     HOSTNAME=$(hostname)
#     LOG_FILE="$SERVICE_DIR/logs/backend.log"
#
#     echo "$SERVICE_NAME failed with exit code $EXIT_CODE on $HOSTNAME" | \
#         mail -s "Alert: $SERVICE_NAME Failed" \
#         -a "From: aiq@$HOSTNAME" \
#         admin@example.com
#
#     echo "Failure notification sent to admin@example.com"
# fi

exit $EXIT_CODE
