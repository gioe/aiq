#!/bin/bash
# Sync OpenAPI spec from docs/api/ to iOS project for Swift OpenAPI Generator
# This script is run as a pre-build phase in Xcode

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

SOURCE="$PROJECT_ROOT/docs/api/openapi.json"
DEST_LEGACY="$PROJECT_ROOT/ios/AIQ/openapi.json"
DEST_PACKAGE="$PROJECT_ROOT/ios/Packages/AIQAPIClient/Sources/AIQAPIClient/openapi.json"

if [ ! -f "$SOURCE" ]; then
    echo "warning: OpenAPI spec not found at $SOURCE"
    echo "note: Run 'cd backend && python export_openapi.py' to generate it"
    echo "note: Skipping OpenAPI code generation for this build"
    exit 0  # Exit successfully to not break fresh checkouts
fi

# Sync to package location (primary location for code generation)
if [ ! -f "$DEST_PACKAGE" ] || [ "$SOURCE" -nt "$DEST_PACKAGE" ]; then
    cp "$SOURCE" "$DEST_PACKAGE"
    echo "Synced OpenAPI spec to $DEST_PACKAGE"
else
    echo "OpenAPI spec in package is up to date"
fi

# Also sync to legacy location (kept for backward compatibility, can be removed later)
if [ ! -f "$DEST_LEGACY" ] || [ "$SOURCE" -nt "$DEST_LEGACY" ]; then
    cp "$SOURCE" "$DEST_LEGACY"
    echo "Synced OpenAPI spec to $DEST_LEGACY (legacy)"
else
    echo "OpenAPI spec in legacy location is up to date"
fi
