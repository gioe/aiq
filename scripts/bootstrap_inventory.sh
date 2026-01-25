#!/bin/bash
#
# bootstrap_inventory.sh
#
# Generates initial question inventory across all question types.
# This script systematically populates the question database to ensure sufficient
# coverage for production use.
#
# The question generation pipeline automatically distributes questions across
# difficulty levels (easy, medium, hard) equally for each type.
#
# Strata: 6 types x 3 difficulties = 18 strata
# Default target: 50 questions per stratum = 900 total questions
#
# Usage:
#   ./scripts/bootstrap_inventory.sh [OPTIONS]
#
# Options:
#   --count N           Total questions per type (distributed across difficulties)
#                       Default: 150 (50 per difficulty level)
#   --types TYPE,...    Comma-separated list of types to generate (default: all)
#   --dry-run           Generate without database insertion
#   --no-async          Disable async generation (slower but more stable)
#   --max-retries N     Maximum retries per type (default: 3)
#   --help              Show this help message
#
# Environment Variables:
#   QUESTIONS_PER_TYPE   Override default questions per type (150)
#
# Exit codes:
#   0 - All types completed successfully
#   1 - Some types failed after retries
#   2 - Configuration or setup error

set -eo pipefail

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration defaults
# 150 per type = 50 per difficulty (easy/medium/hard), matching target of 50 per stratum
DEFAULT_QUESTIONS_PER_TYPE=150
DEFAULT_MAX_RETRIES=3

# All question types (must match QuestionType enum in app/models.py)
ALL_TYPES="pattern logic spatial math verbal memory"

# Parse arguments
QUESTIONS_PER_TYPE="${QUESTIONS_PER_TYPE:-$DEFAULT_QUESTIONS_PER_TYPE}"
MAX_RETRIES=$DEFAULT_MAX_RETRIES
DRY_RUN=""
USE_ASYNC="--async --async-judge"
TYPES_FILTER=""

print_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Generate initial question inventory across all question types.

The pipeline automatically distributes questions across difficulty levels
(easy, medium, hard) equally for each type.

Options:
  --count N           Total questions per type (distributed across 3 difficulties)
                      Default: $DEFAULT_QUESTIONS_PER_TYPE (50 per difficulty)
  --types TYPE,...    Comma-separated list of types to generate (default: all)
                      Valid types: $ALL_TYPES
  --dry-run           Generate without database insertion
  --no-async          Disable async generation (slower but more stable)
  --max-retries N     Maximum retries per type (default: $DEFAULT_MAX_RETRIES)
  --help              Show this help message

Examples:
  # Generate full inventory: 150 questions per type = 900 total target
  # (50 per stratum across 6 types x 3 difficulties = 18 strata)
  ./scripts/bootstrap_inventory.sh

  # Generate only math questions (150 questions across 3 difficulties)
  ./scripts/bootstrap_inventory.sh --types math

  # Generate pattern and logic questions
  ./scripts/bootstrap_inventory.sh --types pattern,logic

  # Generate more questions per type (300 = 100 per difficulty)
  ./scripts/bootstrap_inventory.sh --count 300

  # Dry run to test without database writes
  ./scripts/bootstrap_inventory.sh --dry-run --count 15 --types math

  # Stable mode for troubleshooting (no async)
  ./scripts/bootstrap_inventory.sh --no-async --count 30 --types verbal

Environment Variables:
  QUESTIONS_PER_TYPE   Override default questions per type ($DEFAULT_QUESTIONS_PER_TYPE)
EOF
}

while [ $# -gt 0 ]; do
    case $1 in
        --count)
            QUESTIONS_PER_TYPE="$2"
            shift 2
            ;;
        --types)
            TYPES_FILTER="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN="--dry-run"
            shift
            ;;
        --no-async)
            USE_ASYNC=""
            shift
            ;;
        --max-retries)
            MAX_RETRIES="$2"
            shift 2
            ;;
        --help)
            print_usage
            exit 0
            ;;
        *)
            echo -e "${RED}Error: Unknown option: $1${NC}"
            print_usage
            exit 2
            ;;
    esac
done

# Validate --count parameter bounds
if ! [[ "$QUESTIONS_PER_TYPE" =~ ^[0-9]+$ ]]; then
    echo -e "${RED}Error: --count must be a positive integer${NC}"
    exit 2
fi

if [ "$QUESTIONS_PER_TYPE" -lt 1 ] || [ "$QUESTIONS_PER_TYPE" -gt 10000 ]; then
    echo -e "${RED}Error: --count must be between 1 and 10000 (got: $QUESTIONS_PER_TYPE)${NC}"
    exit 2
fi

# Warn if count is too low to distribute across difficulties
if [ "$QUESTIONS_PER_TYPE" -lt 3 ]; then
    echo -e "${YELLOW}Warning: --count $QUESTIONS_PER_TYPE is less than 3. Some difficulty levels will receive 0 questions.${NC}"
    echo -e "${YELLOW}         Questions are distributed across 3 difficulties (easy/medium/hard).${NC}"
    echo ""
fi

# Use filter or defaults, convert comma-separated to space-separated
if [ -n "$TYPES_FILTER" ]; then
    TYPES=$(echo "$TYPES_FILTER" | tr ',' ' ')
else
    TYPES="$ALL_TYPES"
fi

# Validate types
for type in $TYPES; do
    valid=false
    for valid_type in $ALL_TYPES; do
        if [ "$type" = "$valid_type" ]; then
            valid=true
            break
        fi
    done
    if [ "$valid" = "false" ]; then
        echo -e "${RED}Error: Invalid question type: $type${NC}"
        echo "Valid types: $ALL_TYPES"
        exit 2
    fi
done

# Find project root (where this script is in scripts/)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
QUESTION_SERVICE_DIR="$PROJECT_ROOT/question-service"

# Verify question-service directory exists
if [ ! -d "$QUESTION_SERVICE_DIR" ]; then
    echo -e "${RED}Error: question-service directory not found at $QUESTION_SERVICE_DIR${NC}"
    exit 2
fi

# Check for Python and venv
if [ -f "$QUESTION_SERVICE_DIR/venv/bin/python" ]; then
    PYTHON_CMD="$QUESTION_SERVICE_DIR/venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
    echo -e "${YELLOW}Warning: Virtual environment not found. Using system python3.${NC}"
    echo "For best results, create venv: cd $QUESTION_SERVICE_DIR && python -m venv venv && pip install -r requirements.txt"
else
    echo -e "${RED}Error: No Python 3 found${NC}"
    exit 2
fi

# Pre-flight API key check
# The question service requires at least one LLM provider API key
if [ -z "${OPENAI_API_KEY:-}" ] && [ -z "${ANTHROPIC_API_KEY:-}" ] && [ -z "${GOOGLE_API_KEY:-}" ] && [ -z "${XAI_API_KEY:-}" ]; then
    echo -e "${RED}Error: No LLM API key found${NC}"
    echo ""
    echo "The question service requires at least one of the following environment variables:"
    echo "  - OPENAI_API_KEY"
    echo "  - ANTHROPIC_API_KEY"
    echo "  - GOOGLE_API_KEY"
    echo "  - XAI_API_KEY"
    echo ""
    echo "Set one of these before running this script."
    exit 2
fi

# Calculate totals
TOTAL_TYPES=0
for _ in $TYPES; do
    TOTAL_TYPES=$((TOTAL_TYPES + 1))
done
QUESTIONS_PER_DIFFICULTY=$((QUESTIONS_PER_TYPE / 3))
TOTAL_TARGET=$((TOTAL_TYPES * QUESTIONS_PER_TYPE))
TOTAL_STRATA=$((TOTAL_TYPES * 3))

# Format async mode display
if [ -n "$USE_ASYNC" ]; then
    ASYNC_DISPLAY="enabled"
else
    ASYNC_DISPLAY="disabled"
fi

# Format dry run display
if [ -n "$DRY_RUN" ]; then
    DRY_RUN_DISPLAY="yes"
else
    DRY_RUN_DISPLAY="no"
fi

# Print banner
echo ""
echo -e "${CYAN}================================================================${NC}"
echo -e "${CYAN}       AIQ Question Inventory Bootstrap Script${NC}"
echo -e "${CYAN}================================================================${NC}"
echo ""
echo -e "${BLUE}Configuration:${NC}"
echo "  Questions per type: $QUESTIONS_PER_TYPE"
echo "  Questions per difficulty: ~$QUESTIONS_PER_DIFFICULTY"
echo "  Types: $TYPES"
echo "  Difficulties: easy, medium, hard (auto-distributed)"
echo "  Total types: $TOTAL_TYPES"
echo "  Total strata: $TOTAL_STRATA"
echo "  Target total questions: $TOTAL_TARGET"
echo "  Max retries per type: $MAX_RETRIES"
echo "  Async mode: $ASYNC_DISPLAY"
echo "  Dry run: $DRY_RUN_DISPLAY"
echo ""
echo -e "${CYAN}================================================================${NC}"
echo ""

# Track results using files (bash 3.2 compatible)
RESULTS_DIR=$(mktemp -d)
trap "rm -rf $RESULTS_DIR" EXIT

SUCCESSFUL_TYPES=0
FAILED_TYPES=0
START_TIME=$(date +%s)

# Create logs directory if needed
LOG_DIR="$QUESTION_SERVICE_DIR/logs"
mkdir -p "$LOG_DIR"
BOOTSTRAP_LOG="$LOG_DIR/bootstrap_$(date +%Y%m%d_%H%M%S).log"

echo -e "${BLUE}Logging to: $BOOTSTRAP_LOG${NC}"
echo ""

# Function to generate questions for a single type
generate_type() {
    local type=$1
    local attempt=0
    local success=false
    local exit_code=0

    while [ $attempt -lt $MAX_RETRIES ] && [ "$success" = "false" ]; do
        attempt=$((attempt + 1))

        if [ $attempt -gt 1 ]; then
            echo -e "  ${YELLOW}Retry $attempt/$MAX_RETRIES${NC}"
            sleep 5  # Brief pause before retry
        fi

        # Build command arguments
        # Note: --triggered-by only accepts scheduler, manual, or webhook
        local cmd_args="--types $type --count $QUESTIONS_PER_TYPE --triggered-by manual"
        if [ -n "$USE_ASYNC" ]; then
            cmd_args="$cmd_args $USE_ASYNC"
        fi
        if [ -n "$DRY_RUN" ]; then
            cmd_args="$cmd_args $DRY_RUN"
        fi

        # Log the command
        echo "Running: $PYTHON_CMD run_generation.py $cmd_args" >> "$BOOTSTRAP_LOG"
        echo "Started: $(date -Iseconds 2>/dev/null || date '+%Y-%m-%dT%H:%M:%S')" >> "$BOOTSTRAP_LOG"

        # Run generation
        cd "$QUESTION_SERVICE_DIR"

        if $PYTHON_CMD run_generation.py $cmd_args >> "$BOOTSTRAP_LOG" 2>&1; then
            success=true
            exit_code=0
            echo "Completed successfully: $(date -Iseconds 2>/dev/null || date '+%Y-%m-%dT%H:%M:%S')" >> "$BOOTSTRAP_LOG"
        else
            exit_code=$?
            echo "Failed with exit code $exit_code: $(date -Iseconds 2>/dev/null || date '+%Y-%m-%dT%H:%M:%S')" >> "$BOOTSTRAP_LOG"
            echo -e "  ${RED}Attempt $attempt failed (exit code: $exit_code)${NC}"
        fi

        echo "" >> "$BOOTSTRAP_LOG"
    done

    if [ "$success" = "true" ]; then
        return 0
    else
        return $exit_code
    fi
}

# Main generation loop
CURRENT_TYPE=0

for type in $TYPES; do
    CURRENT_TYPE=$((CURRENT_TYPE + 1))

    echo -n "[$CURRENT_TYPE/$TOTAL_TYPES] Generating $type ($QUESTIONS_PER_TYPE questions)... "

    type_start=$(date +%s)

    if generate_type "$type"; then
        type_end=$(date +%s)
        duration=$((type_end - type_start))
        echo -e "${GREEN}done${NC} (${duration}s)"
        echo "success" > "$RESULTS_DIR/$type"
        SUCCESSFUL_TYPES=$((SUCCESSFUL_TYPES + 1))
    else
        type_end=$(date +%s)
        duration=$((type_end - type_start))
        echo -e "${RED}FAILED${NC} (${duration}s)"
        echo "failed" > "$RESULTS_DIR/$type"
        FAILED_TYPES=$((FAILED_TYPES + 1))
    fi
done

# Calculate final stats
END_TIME=$(date +%s)
TOTAL_DURATION=$((END_TIME - START_TIME))
TOTAL_MINUTES=$((TOTAL_DURATION / 60))
TOTAL_SECONDS=$((TOTAL_DURATION % 60))

# Print summary
echo ""
echo -e "${CYAN}================================================================${NC}"
echo -e "${CYAN}                     BOOTSTRAP SUMMARY${NC}"
echo -e "${CYAN}================================================================${NC}"
echo ""
echo -e "${BLUE}Results:${NC}"
echo "  Successful types: $SUCCESSFUL_TYPES / $TOTAL_TYPES"
echo "  Failed types: $FAILED_TYPES"
echo "  Total duration: ${TOTAL_MINUTES}m ${TOTAL_SECONDS}s"
echo ""

# Detailed results
echo -e "${BLUE}Type Details:${NC}"
for type in $TYPES; do
    result_file="$RESULTS_DIR/$type"
    if [ -f "$result_file" ]; then
        result=$(cat "$result_file")
    else
        result="unknown"
    fi

    case $result in
        "success")
            echo -e "  ${GREEN}[OK]${NC} $type"
            ;;
        "failed")
            echo -e "  ${RED}[FAILED]${NC} $type"
            ;;
        *)
            echo -e "  ${YELLOW}[???]${NC} $type"
            ;;
    esac
done

echo ""
echo -e "${BLUE}Log file:${NC} $BOOTSTRAP_LOG"
echo ""

# Notes about actual vs target
echo -e "${BLUE}Note:${NC}"
echo "  Actual inserted questions may be lower than target due to:"
echo "  - Judge evaluation (min score threshold: 0.7)"
echo "  - Deduplication against existing questions"
echo "  Check the log file or /v1/admin/inventory-health for actual counts."
echo ""

# Exit with appropriate code
if [ $FAILED_TYPES -gt 0 ]; then
    echo -e "${RED}Bootstrap completed with failures.${NC}"
    echo "Check the log file for details: $BOOTSTRAP_LOG"
    exit 1
else
    echo -e "${GREEN}Bootstrap completed successfully!${NC}"
    exit 0
fi
