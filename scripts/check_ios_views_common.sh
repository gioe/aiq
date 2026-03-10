#!/bin/bash
# Check for stale Views/Common references in iOS documentation.
# Views/Common was renamed to Views/Components — all docs must use the new name.

FILES=(
    "ios/CLAUDE.md"
    "ios/docs/ARCHITECTURE.md"
    "ios/docs/CODING_STANDARDS.md"
)

FOUND=0
for f in "${FILES[@]}"; do
    if [ -f "$f" ] && grep -q "Views/Common" "$f"; then
        echo "ERROR: stale 'Views/Common' reference in $f (should be Views/Components)"
        grep -n "Views/Common" "$f"
        FOUND=1
    fi
done

if [ "$FOUND" -eq 1 ]; then
    exit 1
fi
