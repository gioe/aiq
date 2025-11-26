---
description: Build and open the iOS project in Xcode
---

Build the iOS project and open it in Xcode.

Steps:
1. Run xcodebuild to build the project for iPhone 15 simulator
2. Report the build status (success or failure)
3. Open the project in Xcode using the `open` command
4. If the build failed, mention that Xcode will show the errors

Use this exact command:
```bash
cd ios && xcodebuild -scheme AIQ -destination 'platform=iOS Simulator,name=iPhone 15' build && open AIQ.xcodeproj
```

If the build fails, still open Xcode so the user can see the errors:
```bash
cd ios && (xcodebuild -scheme AIQ -destination 'platform=iOS Simulator,name=iPhone 15' build || true) && open AIQ.xcodeproj
```

After running the command, tell the user:
- ✅ If build succeeded: "Build successful! Opening Xcode..."
- ⚠️ If build failed: "Build failed. Opening Xcode to view errors..."
- 📱 Remind them they can press ⌘+R in Xcode to build and run
