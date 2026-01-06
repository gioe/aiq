# Memory Leak Detection Guide - Xcode Instruments

This guide provides step-by-step instructions for running memory leak detection on the AIQ iOS app using Xcode Instruments.

## Prerequisites

- Xcode 15+ installed
- iOS Simulator or physical iOS device
- AIQ app built in Debug configuration

## Quick Start - CLI-Based Detection

For quick leak detection, use the `leaks` command-line tool:

```bash
# 1. Boot and install the app
xcrun simctl boot "iPhone 16 Pro"
xcrun simctl install "iPhone 16 Pro" ~/Library/Developer/Xcode/DerivedData/AIQ-*/Build/Products/Debug-iphonesimulator/AIQ.app

# 2. Launch the app and get PID
xcrun simctl launch "iPhone 16 Pro" com.aiq.app
# Output: com.aiq.app: <PID>

# 3. Run leak detection
leaks <PID>

# 4. Save memory graph for analysis
leaks <PID> --outputGraph=memory-graph
```

## Xcode Instruments - Full Analysis

### 1. Launch Instruments

1. Open Xcode
2. Go to **Product > Profile** (or press `Cmd + I`)
3. Select the **Leaks** template
4. Click **Choose**

### 2. Configure Target

1. Select target device (Simulator or physical device)
2. Ensure AIQ app is selected
3. Click the red **Record** button to start profiling

### 3. Test Flows to Execute

Perform each of the following user flows while Instruments is recording:

#### Flow 1: Login/Logout
1. Launch app (if not already open)
2. Navigate to login screen
3. Enter credentials and log in
4. Wait for home screen to load
5. Navigate to Settings/Profile
6. Log out
7. **Expected**: No leaked objects after logout

#### Flow 2: Test Taking Flow
1. Log in to the app
2. Start a new test
3. Answer several questions
4. Complete or abandon the test
5. Return to dashboard
6. **Expected**: No leaked objects after test completion

#### Flow 3: Navigation Through All Tabs
1. Log in to the app
2. Navigate to Dashboard tab
3. Navigate to History tab
4. Navigate to Profile/Settings tab
5. Navigate back to Dashboard
6. Repeat 2-3 times
7. **Expected**: No leaked objects from navigation

#### Flow 4: Background/Foreground Transitions
1. With app in foreground, press Home button (or swipe up)
2. Wait 5-10 seconds
3. Return to the app
4. Repeat 3-5 times
5. **Expected**: No leaked objects from state transitions

### 4. Analyzing Results

#### Leaks Timeline
- The Leaks timeline shows detected leaks over time
- Red markers indicate when leaks were detected
- Click on a leak to see details

#### Leak Details
For each detected leak, note:
- **Object Type**: The class/type of the leaked object
- **Size**: Memory size of the leak
- **Stack Trace**: Where the allocation occurred
- **Responsible Frame**: The likely source of the leak

#### Memory Graph
1. Click the **Pause** button to stop recording
2. Use the memory graph to see object relationships
3. Look for retain cycles (circular references)

### 5. Common Leak Patterns to Watch For

| Pattern | Description | Fix |
|---------|-------------|-----|
| Closure Retain Cycle | Strong self reference in closures | Use `[weak self]` |
| Delegate Retain Cycle | Strong delegate references | Use `weak var delegate` |
| Timer Retain Cycle | Timer holding strong reference | Invalidate timer, use `[weak self]` |
| NotificationCenter | Observer not removed | Remove observer in deinit |
| Combine/Publisher | Subscription not cancelled | Store in cancellables, use `.store(in:)` |

### 6. Memory Graph Debugging

Alternative to Instruments for quick memory graph analysis:

1. Run the app in Xcode debugger
2. Pause execution
3. Click **Debug Memory Graph** button (icon with circles)
4. Examine object relationships
5. Look for unexpected strong references

## Acceptance Criteria Checklist

- [ ] Instruments Leaks tool run on app
- [ ] Login/Logout flow tested - no leaks
- [ ] Test taking flow tested - no leaks
- [ ] Navigation through all tabs tested - no leaks
- [ ] Background/foreground transitions tested - no leaks
- [ ] Memory graph verified clean
- [ ] Test report created

## Troubleshooting

### "Process is not debuggable"
This is normal for simulator processes. The `leaks` tool will still detect leaks but cannot show full allocation stacks.

### Leaks from System Frameworks
Some leaks may originate from Apple's frameworks (Firebase, UIKit, etc.). Document these but note they are outside our control.

### False Positives
Autoreleased objects may appear as temporary leaks. Wait for autorelease pool drain before final assessment.

## Related Documentation

- [BTS-54: Fix StateObject misuse](https://gioematt.atlassian.net/browse/BTS-54)
- [BTS-56: Fix retain cycle in DashboardViewModel](https://gioematt.atlassian.net/browse/BTS-56)
- [BTS-57: Audit Timer closures for retain cycles](https://gioematt.atlassian.net/browse/BTS-57)
