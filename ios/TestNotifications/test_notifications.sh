#!/bin/bash

# Notification Testing Script for IQ Tracker iOS App
# This script helps test push notifications in the iOS simulator

set -e

BUNDLE_ID="com.aiq.app"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🔔 IQ Tracker Notification Testing Script"
echo "=========================================="
echo ""

# Function to get booted simulator device ID
get_booted_simulator() {
    xcrun simctl list devices | grep "Booted" | grep -E -o -i "([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
}

# Function to send notification
send_notification() {
    local notification_file=$1
    local device_id=$2

    echo "📱 Sending notification from: $(basename "$notification_file")"
    xcrun simctl push "$device_id" "$BUNDLE_ID" "$notification_file"

    if [ $? -eq 0 ]; then
        echo "✅ Notification sent successfully"
    else
        echo "❌ Failed to send notification"
        return 1
    fi
}

# Main script
main() {
    # Check if simulator is running
    DEVICE_ID=$(get_booted_simulator)

    if [ -z "$DEVICE_ID" ]; then
        echo "❌ No booted simulator found!"
        echo "Please start an iOS simulator first."
        exit 1
    fi

    echo "✅ Found booted simulator: $DEVICE_ID"
    echo ""

    # Check if app is installed
    echo "Checking if IQ Tracker app is installed..."
    if ! xcrun simctl get_app_container "$DEVICE_ID" "$BUNDLE_ID" > /dev/null 2>&1; then
        echo "⚠️  IQ Tracker app may not be installed on this simulator"
        echo "Please build and run the app first."
        echo ""
    fi

    # Menu
    echo "Select notification to send:"
    echo "  1) Test Reminder (full format)"
    echo "  2) Test Reminder (simple format)"
    echo "  3) Test Reminder (no sound)"
    echo "  4) Send all test notifications"
    echo "  5) Exit"
    echo ""
    read -p "Enter choice [1-5]: " choice

    case $choice in
        1)
            send_notification "$SCRIPT_DIR/test_reminder.apns" "$DEVICE_ID"
            ;;
        2)
            send_notification "$SCRIPT_DIR/test_reminder_simple.apns" "$DEVICE_ID"
            ;;
        3)
            send_notification "$SCRIPT_DIR/test_reminder_no_sound.apns" "$DEVICE_ID"
            ;;
        4)
            echo "Sending all test notifications..."
            echo ""
            send_notification "$SCRIPT_DIR/test_reminder.apns" "$DEVICE_ID"
            sleep 2
            send_notification "$SCRIPT_DIR/test_reminder_simple.apns" "$DEVICE_ID"
            sleep 2
            send_notification "$SCRIPT_DIR/test_reminder_no_sound.apns" "$DEVICE_ID"
            ;;
        5)
            echo "Exiting..."
            exit 0
            ;;
        *)
            echo "Invalid choice"
            exit 1
            ;;
    esac

    echo ""
    echo "Testing Tips:"
    echo "  - Test with app in foreground (should show banner)"
    echo "  - Test with app in background (should show notification)"
    echo "  - Test tapping notification (should navigate to app)"
    echo "  - Check badge count updates"
    echo "  - Verify notification data is parsed correctly"
}

main
