#!/bin/bash
# Cron wrapper script for IQ Tracker question generation
#
# This script should be called from crontab to run scheduled question generation.
# It handles environment setup, logging, and optional error notifications.
#
# Usage:
#   Add to crontab:
#   0 2 * * 0 /path/to/iq-tracker/question-service/scripts/run_cron.sh >> /path/to/logs/cron.log 2>&1

# Exit on error
set -e

# Determine script directory (works even if called via symlink)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="$(dirname "$SCRIPT_DIR")"

echo "================================================================"
echo "IQ Tracker Question Generation - Cron Run"
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
if [ -z "$DATABASE_URL" ]; then
    echo "ERROR: DATABASE_URL not set"
    exit 3
fi

# Check that at least one API key is set
if [ -z "$OPENAI_API_KEY" ] && [ -z "$ANTHROPIC_API_KEY" ] && [ -z "$GOOGLE_API_KEY" ]; then
    echo "ERROR: No LLM API keys configured"
    echo "Set at least one of: OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY"
    exit 3
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Run generation script
echo ""
echo "Running question generation..."
echo "----------------------------------------------------------------"

python run_generation.py --no-console

# Capture exit code
EXIT_CODE=$?

echo "----------------------------------------------------------------"
echo "Generation completed with exit code: $EXIT_CODE"
echo "Finished: $(date)"
echo "================================================================"

# Optional: Send email notification on failure
# Uncomment and configure if you want email alerts
#
# if [ $EXIT_CODE -ne 0 ]; then
#     HOSTNAME=$(hostname)
#     LOG_FILE="$SERVICE_DIR/logs/question_service.log"
#
#     echo "Question generation failed with exit code $EXIT_CODE on $HOSTNAME" | \
#         mail -s "IQ Tracker Alert: Generation Failed" \
#         -a "From: iq-tracker@$HOSTNAME" \
#         admin@example.com
#
#     echo "Failure notification sent to admin@example.com"
# fi

exit $EXIT_CODE
