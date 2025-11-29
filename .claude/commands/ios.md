---
description: Build and run the iOS app in Simulator
---

Build the iOS project and launch it in the iOS Simulator.

Steps:
1. Find the first available iPhone simulator
2. Build the app for that simulator
3. Boot the simulator if not already running
4. Install and launch the app
5. Open Xcode for code editing

Use this bash script (executed via temp file to avoid shell parsing issues):
```bash
cat > /tmp/run_ios.sh << 'SCRIPT'
cd /Users/mattgioe/aiq/ios
SIMULATOR=$(xcrun simctl list devices available | grep 'iPhone' | head -1 | sed 's/.*\([A-F0-9-]\{36\}\).*/\1/')
echo "Using simulator ID: $SIMULATOR"
xcodebuild -scheme AIQ -destination "id=$SIMULATOR" build
xcrun simctl boot "$SIMULATOR" 2>/dev/null || true
xcrun simctl install "$SIMULATOR" ~/Library/Developer/Xcode/DerivedData/AIQ-*/Build/Products/Release-iphonesimulator/AIQ.app
open -a Simulator
xcrun simctl launch "$SIMULATOR" com.iqtracker.app
open AIQ.xcodeproj
SCRIPT
chmod +x /tmp/run_ios.sh && /tmp/run_ios.sh
```

If any step fails, provide helpful error messages:
- If no simulator found: "No iPhone simulator available. Please install one via Xcode."
- If build fails: "Build failed. Opening Xcode to view errors..."
- If launch fails: "Build succeeded but couldn't launch app. Opening Xcode and Simulator..."

After running the command, tell the user:
- ✅ If fully successful: "Build successful! App is launching in Simulator and Xcode is open..."
- ⚠️ If partial success: Describe what worked and what didn't
- 📱 Remind them the app should appear in the Simulator shortly
