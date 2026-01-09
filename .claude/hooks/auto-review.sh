#!/bin/bash
# Auto-review hook: Triggers code review when Claude modifies files
# This runs on the Stop event and checks for uncommitted changes

# Read hook input from stdin
INPUT=$(cat)
CWD=$(echo "$INPUT" | jq -r '.cwd // "."')

cd "$CWD" 2>/dev/null || {
    # Can't change to directory, allow stop
    echo '{}'
    exit 0
}

# Check for modified files (staged and unstaged)
MODIFIED_FILES=$(git diff --name-only HEAD 2>/dev/null || true)

if [ -z "$MODIFIED_FILES" ]; then
    # No modifications, allow stop
    echo '{}'
    exit 0
fi

# Categorize modified files
PYTHON_FILES=$(echo "$MODIFIED_FILES" | grep -E '\.py$' || true)
SWIFT_FILES=$(echo "$MODIFIED_FILES" | grep -E '\.swift$' || true)

# Build review message
REVIEW_MSG=""

if [ -n "$PYTHON_FILES" ]; then
    PYTHON_COUNT=$(echo "$PYTHON_FILES" | wc -l | tr -d ' ')
    REVIEW_MSG="$PYTHON_COUNT Python file(s) modified. Run the project-code-reviewer agent."
fi

if [ -n "$SWIFT_FILES" ]; then
    SWIFT_COUNT=$(echo "$SWIFT_FILES" | wc -l | tr -d ' ')
    if [ -n "$REVIEW_MSG" ]; then
        REVIEW_MSG="$REVIEW_MSG Also, $SWIFT_COUNT Swift file(s) modified - run ios-code-reviewer agent."
    else
        REVIEW_MSG="$SWIFT_COUNT Swift file(s) modified. Run the ios-code-reviewer agent."
    fi
fi

if [ -n "$REVIEW_MSG" ]; then
    # Output JSON with the review message and continue flag
    # This tells Claude to continue and provides context about what to do
    cat <<EOF
{"continue": true, "reason": "[Auto-Review] $REVIEW_MSG"}
EOF
else
    # Modified files exist but none are Python or Swift, allow stop
    echo '{}'
fi
