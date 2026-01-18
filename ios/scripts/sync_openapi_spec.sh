#!/bin/bash
# Sync OpenAPI spec from docs/api/ to iOS project for Swift OpenAPI Generator
# This script is run as a pre-build phase in Xcode

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

SOURCE="$PROJECT_ROOT/docs/api/openapi.json"
DEST="$PROJECT_ROOT/ios/AIQ/openapi.json"

if [ ! -f "$SOURCE" ]; then
    echo "error: OpenAPI spec not found at $SOURCE"
    echo "note: Run 'cd backend && poetry run python -m app.main --export-openapi' to generate it"
    exit 1
fi

# Only copy if source is newer or dest doesn't exist
if [ ! -f "$DEST" ] || [ "$SOURCE" -nt "$DEST" ]; then
    cp "$SOURCE" "$DEST"
    echo "Synced OpenAPI spec to $DEST"
else
    echo "OpenAPI spec is up to date"
fi
