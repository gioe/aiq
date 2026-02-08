#!/bin/bash
# Pre-commit lint hook for Claude Code
# Intercepts `git commit` commands, runs pre-commit checks on staged files,
# and denies the commit with structured feedback if checks fail.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Only intercept git commit commands (not git commit --amend with no changes, etc.)
if ! echo "$COMMAND" | grep -qE '^\s*git\s+commit\b'; then
    exit 0
fi

# Skip if the command already includes --no-verify (user explicitly opted out)
if echo "$COMMAND" | grep -qE '\-\-no-verify'; then
    exit 0
fi

CWD=$(echo "$INPUT" | jq -r '.cwd // "."')
cd "$CWD" 2>/dev/null || exit 0

# Check if there are staged files to validate
STAGED=$(git diff --cached --name-only 2>/dev/null)
if [ -z "$STAGED" ]; then
    exit 0
fi

# Find pre-commit binary (may be in a virtualenv)
if command -v pre-commit &>/dev/null; then
    PRE_COMMIT=pre-commit
elif [ -x "$CWD/backend/venv/bin/pre-commit" ]; then
    PRE_COMMIT="$CWD/backend/venv/bin/pre-commit"
elif [ -x "$CWD/question-service/venv/bin/pre-commit" ]; then
    PRE_COMMIT="$CWD/question-service/venv/bin/pre-commit"
else
    # pre-commit not installed — skip check rather than block all commits
    exit 0
fi

# Run pre-commit on staged files only
OUTPUT=$($PRE_COMMIT run --files $STAGED 2>&1)
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    # Truncate output if very long (keep first 80 lines)
    TRUNCATED=$(echo "$OUTPUT" | head -80)
    if [ $(echo "$OUTPUT" | wc -l) -gt 80 ]; then
        TRUNCATED="$TRUNCATED
... (output truncated)"
    fi

    # Escape for JSON
    ESCAPED=$(echo "$TRUNCATED" | jq -Rs .)

    cat <<ENDJSON
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Pre-commit checks failed. Fix these issues before committing:\n\n${TRUNCATED}"
  }
}
ENDJSON
    exit 0
fi

# All checks passed — allow the commit
exit 0
