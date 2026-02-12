#!/bin/bash
# Add .claude/bin to PATH for Claude Code sessions
if [ -n "$CLAUDE_ENV_FILE" ]; then
  echo "export PATH=\"$CLAUDE_PROJECT_DIR/.claude/bin:\$PATH\"" >> "$CLAUDE_ENV_FILE"
fi
exit 0
