#!/bin/bash

# RTL Testing Script for AIQ iOS App
# This script makes it easy to test the app in RTL mode

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🔄 AIQ RTL Testing Helper"
echo "========================="
echo ""

# Check if we're in the right directory
if [ ! -f "$PROJECT_DIR/AIQ.xcodeproj/project.pbxproj" ]; then
    echo "❌ Error: AIQ.xcodeproj not found"
    echo "Please run this script from the ios/scripts directory"
    exit 1
fi

echo "ℹ️  This script will help you test the app in RTL (Right-to-Left) mode."
echo ""
echo "Options:"
echo "  1. Enable RTL launch arguments in scheme (manual)"
echo "  2. Build and run with RTL enabled (requires manual scheme edit)"
echo "  3. Show RTL testing guide"
echo "  4. Open project in Xcode"
echo ""

read -p "Select an option (1-4): " option

case $option in
    1)
        echo ""
        echo "📝 To enable RTL testing:"
        echo ""
        echo "1. Open the project in Xcode"
        echo "2. Go to Product > Scheme > Edit Scheme (⌘<)"
        echo "3. Select 'Run' in the left sidebar"
        echo "4. Go to the 'Arguments' tab"
        echo "5. Under 'Arguments Passed On Launch', check these boxes:"
        echo "   ☐ -AppleLanguages (ar)"
        echo "   ☐ -AppleLocale ar_SA"
        echo "   ☐ -AppleTextDirection YES"
        echo "6. Close the scheme editor"
        echo "7. Run the app (⌘R)"
        echo ""
        echo "✅ The app will now run in RTL mode!"
        ;;

    2)
        echo ""
        echo "🏗️  Building project for RTL testing..."
        echo ""

        # Build the project
        cd "$PROJECT_DIR"
        xcodebuild -scheme AIQ -sdk iphonesimulator build

        echo ""
        echo "✅ Build successful!"
        echo ""
        echo "⚠️  Note: You still need to manually enable RTL launch arguments"
        echo "   in the scheme (see option 1) before running."
        echo ""
        echo "To run the app:"
        echo "  1. Open the project in Xcode"
        echo "  2. Ensure RTL arguments are enabled in the scheme"
        echo "  3. Press ⌘R to run"
        ;;

    3)
        echo ""
        echo "📖 Opening RTL Testing Guide..."
        echo ""

        if [ -f "$PROJECT_DIR/docs/RTL_TESTING_GUIDE.md" ]; then
            if command -v open &> /dev/null; then
                open "$PROJECT_DIR/docs/RTL_TESTING_GUIDE.md"
                echo "✅ Guide opened!"
            else
                echo "Guide location: $PROJECT_DIR/docs/RTL_TESTING_GUIDE.md"
            fi
        else
            echo "❌ RTL Testing Guide not found"
        fi
        ;;

    4)
        echo ""
        echo "🚀 Opening project in Xcode..."

        if command -v open &> /dev/null; then
            open "$PROJECT_DIR/AIQ.xcodeproj"
            echo "✅ Xcode opened!"
        else
            echo "❌ Unable to open Xcode automatically"
            echo "Please open: $PROJECT_DIR/AIQ.xcodeproj"
        fi
        ;;

    *)
        echo ""
        echo "❌ Invalid option"
        exit 1
        ;;
esac

echo ""
echo "📚 For more information, see: docs/RTL_TESTING_GUIDE.md"
echo ""
