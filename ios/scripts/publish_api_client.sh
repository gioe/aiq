#!/bin/bash
# Publish updated OpenAPI spec to a local ios-libs checkout and prompt to release
#
# Usage: ./publish_api_client.sh <path-to-ios-libs-checkout>
#
# Example:
#   ./ios/scripts/publish_api_client.sh ~/code/ios-libs

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

IOS_LIBS_PATH="${1:-}"

if [ -z "$IOS_LIBS_PATH" ]; then
    echo "error: Missing required argument: path to local ios-libs checkout"
    echo ""
    echo "Usage: $0 <path-to-ios-libs-checkout>"
    echo ""
    echo "Example:"
    echo "  $0 ~/code/ios-libs"
    exit 1
fi

if [ ! -d "$IOS_LIBS_PATH" ]; then
    echo "error: ios-libs directory not found: $IOS_LIBS_PATH"
    exit 1
fi

SOURCE="$PROJECT_ROOT/docs/api/openapi.json"
DEST="$IOS_LIBS_PATH/Sources/APIClient/openapi.json"

if [ ! -f "$SOURCE" ]; then
    echo "error: OpenAPI spec not found at $SOURCE"
    echo "Run 'cd backend && python export_openapi.py' to generate it first."
    exit 1
fi

DEST_DIR="$(dirname "$DEST")"
if [ ! -d "$DEST_DIR" ]; then
    echo "error: Destination directory not found: $DEST_DIR"
    echo "Verify that '$IOS_LIBS_PATH' is a valid ios-libs checkout."
    exit 1
fi

cp "$SOURCE" "$DEST"
echo "Copied openapi.json → $DEST"

# Prompt to commit and tag a new version in ios-libs
echo ""
echo "Next steps in ios-libs ($IOS_LIBS_PATH):"
echo "  1. Review the diff:  cd '$IOS_LIBS_PATH' && git diff"
echo "  2. Stage the change: git add Sources/APIClient/openapi.json"
echo "  3. Commit:           git commit -m 'chore: update openapi spec'"
echo "  4. Tag a new version (semver): git tag <vX.Y.Z>"
echo "  5. Push:             git push && git push --tags"
echo ""
read -r -p "Open a shell in '$IOS_LIBS_PATH' to do this now? [y/N] " answer
if [[ "$answer" =~ ^[Yy]$ ]]; then
    cd "$IOS_LIBS_PATH"
    echo "(Type 'exit' to return)"
    "${SHELL:-/bin/bash}"
fi
