#!/bin/bash
#
# generate-app-store-screenshots.sh
#
# Generates App Store screenshots by running UI tests on required device simulators.
# Screenshots are captured during test execution and extracted to ios/app-store/screenshots/
#
# Required Device Sizes (per Apple's requirements):
# - iPhone 6.9" (iPhone 16 Pro Max) - 1320 x 2868
# - iPhone 6.7" (iPhone 15 Pro Max) - 1290 x 2796
# - iPhone 6.5" (iPhone XS Max) - 1242 x 2688
# - iPhone 5.5" (iPhone 8 Plus) - 1242 x 2208
# - iPad Pro 12.9" (6th gen) - 2048 x 2732
#
# Usage:
#   ./scripts/generate-app-store-screenshots.sh [--device <device_name>] [--quick]
#
# Options:
#   --device <name>  Only run on the specified device
#   --quick          Run only on iPhone 16 Pro Max (fastest for testing)
#   --help           Show this help message
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
IOS_DIR="$PROJECT_ROOT/ios"
SCREENSHOT_DIR="$IOS_DIR/app-store/screenshots"
XCRESULT_DIR="$PROJECT_ROOT/build/screenshots"

# Device configurations
declare -A DEVICES=(
    ["iPhone_6.9"]="iPhone 16 Pro Max"
    ["iPhone_6.7"]="iPhone 15 Pro Max"
    ["iPhone_6.5"]="iPhone XS Max"
    ["iPhone_5.5"]="iPhone 8 Plus"
    ["iPad_12.9"]="iPad Pro (12.9-inch) (6th generation)"
)

# Parse arguments
SELECTED_DEVICE=""
QUICK_MODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --device)
            SELECTED_DEVICE="$2"
            shift 2
            ;;
        --quick)
            QUICK_MODE=true
            shift
            ;;
        --help)
            head -30 "$0" | tail -25
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Create output directories
mkdir -p "$SCREENSHOT_DIR"
mkdir -p "$XCRESULT_DIR"

echo "========================================"
echo "App Store Screenshot Generator"
echo "========================================"
echo ""
echo "Project: $IOS_DIR"
echo "Output:  $SCREENSHOT_DIR"
echo ""

# Function to run tests on a specific device
run_tests_on_device() {
    local device_key="$1"
    local device_name="$2"
    local result_path="$XCRESULT_DIR/${device_key}.xcresult"

    echo "----------------------------------------"
    echo "Running on: $device_name"
    echo "----------------------------------------"

    # Remove previous result if exists
    rm -rf "$result_path"

    # Run the screenshot tests
    cd "$IOS_DIR"

    set +e
    xcodebuild test \
        -project AIQ.xcodeproj \
        -scheme AIQ \
        -destination "platform=iOS Simulator,name=$device_name" \
        -only-testing:AIQUITests/AppStoreScreenshotTests/testGenerateAllScreenshots \
        -resultBundlePath "$result_path" \
        -quiet \
        2>&1

    local exit_code=$?
    set -e

    if [ $exit_code -ne 0 ]; then
        echo "[Warning] Tests failed or had issues on $device_name (exit code: $exit_code)"
        echo "          Screenshots may still have been captured."
    fi

    # Extract screenshots from xcresult
    extract_screenshots "$device_key" "$result_path"

    return 0
}

# Function to extract screenshots from xcresult bundle
extract_screenshots() {
    local device_key="$1"
    local result_path="$2"
    local device_dir="$SCREENSHOT_DIR/$device_key"

    if [ ! -d "$result_path" ]; then
        echo "[Warning] No xcresult found at $result_path"
        return 1
    fi

    mkdir -p "$device_dir"

    echo "Extracting screenshots from $result_path..."

    # Get list of attachment IDs from the xcresult
    local attachments_json
    attachments_json=$(xcrun xcresulttool get --path "$result_path" --format json 2>/dev/null || echo "{}")

    # Extract attachments using xcresulttool
    # First, get the test plan run summaries ID
    local summaries_id
    summaries_id=$(echo "$attachments_json" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    actions = data.get('actions', {}).get('_values', [])
    for action in actions:
        result = action.get('actionResult', {})
        tests_ref = result.get('testsRef', {})
        ref_id = tests_ref.get('id', {}).get('_value', '')
        if ref_id:
            print(ref_id)
            break
except:
    pass
" 2>/dev/null || echo "")

    if [ -z "$summaries_id" ]; then
        echo "[Warning] Could not find test summaries ID"
        # Try alternative extraction method
        extract_screenshots_alternative "$device_key" "$result_path"
        return
    fi

    # Get detailed test results
    local test_results
    test_results=$(xcrun xcresulttool get --path "$result_path" --id "$summaries_id" --format json 2>/dev/null || echo "{}")

    # Extract attachment references
    echo "$test_results" | python3 -c "
import sys, json, subprocess, os

device_key = '$device_key'
result_path = '$result_path'
screenshot_dir = '$SCREENSHOT_DIR'
device_dir = os.path.join(screenshot_dir, device_key)

try:
    data = json.load(sys.stdin)

    def find_attachments(obj, path=''):
        if isinstance(obj, dict):
            # Check for attachments array
            if 'attachments' in obj:
                attachments = obj['attachments'].get('_values', [])
                for att in attachments:
                    name = att.get('name', {}).get('_value', 'unknown')
                    payload_ref = att.get('payloadRef', {}).get('id', {}).get('_value')
                    if payload_ref and name.endswith(('.png', '.PNG')) or '01_' in name or '02_' in name:
                        # Export the attachment
                        output_file = os.path.join(device_dir, f'{name}.png')
                        cmd = ['xcrun', 'xcresulttool', 'get', '--path', result_path, '--id', payload_ref, '--output', output_file]
                        try:
                            subprocess.run(cmd, check=True, capture_output=True)
                            print(f'Exported: {name}')
                        except:
                            pass

            # Recurse into nested objects
            for key, value in obj.items():
                find_attachments(value, f'{path}.{key}')
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                find_attachments(item, f'{path}[{i}]')

    find_attachments(data)
except Exception as e:
    print(f'Error: {e}', file=sys.stderr)
" 2>/dev/null

    echo "Screenshots saved to $device_dir"
}

# Alternative extraction method using xcparse if available
extract_screenshots_alternative() {
    local device_key="$1"
    local result_path="$2"
    local device_dir="$SCREENSHOT_DIR/$device_key"

    # Check if xcparse is available
    if command -v xcparse &> /dev/null; then
        echo "Using xcparse for extraction..."
        xcparse screenshots "$result_path" "$device_dir" 2>/dev/null || true
    else
        echo "[Info] Install xcparse for better screenshot extraction: brew install chargepoint/xcparse/xcparse"

        # Manual extraction using find and xcresulttool
        echo "Attempting manual extraction..."

        # Find all attachment files in the xcresult bundle
        find "$result_path" -name "*.png" -exec cp {} "$device_dir/" \; 2>/dev/null || true

        # Also try to export using xcresulttool export
        xcrun xcresulttool export --type screenshots --path "$result_path" --output "$device_dir" 2>/dev/null || true
    fi

    # Count extracted screenshots
    local count
    count=$(find "$device_dir" -name "*.png" 2>/dev/null | wc -l | tr -d ' ')
    echo "Extracted $count screenshots to $device_dir"
}

# Main execution
echo "Starting screenshot generation..."
echo ""

if [ "$QUICK_MODE" = true ]; then
    echo "Quick mode: Running only on iPhone 16 Pro Max"
    run_tests_on_device "iPhone_6.9" "iPhone 16 Pro Max"
elif [ -n "$SELECTED_DEVICE" ]; then
    # Find matching device
    found=false
    for key in "${!DEVICES[@]}"; do
        if [[ "${DEVICES[$key]}" == *"$SELECTED_DEVICE"* ]] || [[ "$key" == *"$SELECTED_DEVICE"* ]]; then
            run_tests_on_device "$key" "${DEVICES[$key]}"
            found=true
            break
        fi
    done

    if [ "$found" = false ]; then
        echo "Device not found: $SELECTED_DEVICE"
        echo "Available devices:"
        for key in "${!DEVICES[@]}"; do
            echo "  - $key: ${DEVICES[$key]}"
        done
        exit 1
    fi
else
    # Run on all devices
    for key in "${!DEVICES[@]}"; do
        run_tests_on_device "$key" "${DEVICES[$key]}"
    done
fi

echo ""
echo "========================================"
echo "Screenshot generation complete!"
echo "========================================"
echo ""
echo "Screenshots saved to: $SCREENSHOT_DIR"
echo ""

# List generated screenshots
echo "Generated screenshots:"
find "$SCREENSHOT_DIR" -name "*.png" -type f 2>/dev/null | sort | while read -r file; do
    echo "  - $file"
done

echo ""
echo "Next steps:"
echo "1. Review screenshots in $SCREENSHOT_DIR"
echo "2. Upload to App Store Connect"
echo ""
