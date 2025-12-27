# RTL (Right-to-Left) Testing Guide

This guide explains how to test the AIQ iOS app with RTL (Right-to-Left) languages like Arabic and Hebrew.

## Quick Start

### Enable RTL Testing in Xcode

The project includes launch arguments to enable RTL mode for testing. To enable them:

1. Open the AIQ scheme in Xcode (Product > Scheme > Edit Scheme... or `⌘<`)
2. Select "Run" in the left sidebar
3. Go to the "Arguments" tab
4. Under "Arguments Passed On Launch", enable the following arguments by checking their boxes:
   - `-AppleLanguages (ar)` - Sets the app language to Arabic
   - `-AppleLocale ar_SA` - Sets the locale to Saudi Arabia
   - `-AppleTextDirection YES` - Forces RTL layout direction

5. Run the app (`⌘R`)

The app will now display in RTL mode, with all layouts mirrored.

### Testing with Simulators

You can also test RTL by changing the simulator's language:

1. Open the Settings app in the iOS Simulator
2. Go to General > Language & Region
3. Tap "Add Language..."
4. Select "Arabic" or "Hebrew"
5. When prompted, choose to make it the primary language
6. The device will switch to RTL mode

## What to Test

### 1. Navigation and Tab Bar

- **Expected**: Tab bar items should appear right-to-left
- **Expected**: Navigation back buttons should appear on the right side
- **Expected**: Swipe gestures should work in reverse (swipe right to go back becomes swipe left)

### 2. Lists and Scrolling

- **Expected**: List items should align to the right
- **Expected**: Chevron indicators (›) should appear on the left
- **Expected**: ScrollViews should start scrolled to the right edge

### 3. Text Alignment

- **Expected**: All text should align to the right by default
- **Expected**: Numbers may remain left-to-right (this is correct behavior)
- **Expected**: Multi-line text should flow right-to-left

### 4. Layout Elements

#### Dashboard View
- Stats cards should maintain their layout (centered elements are OK)
- "Latest Result" card content should align right
- Action buttons with icons should show icons on the right side

#### Test Taking View
- Question navigation grid should flow right-to-left
- Previous/Next buttons should swap positions
- Progress bar should fill from right to left
- Answer options should align right

#### History View
- List items should align right
- Dates and scores should maintain readable layout
- Charts should consider RTL direction (Y-axis labels on right)

#### Settings View
- List items with chevrons should show chevrons on the left
- Account information should align right

### 5. Icons and Images

- **Expected**: Directional SF Symbols (arrows, chevrons) automatically flip
- **Expected**: Non-directional symbols (clock, star, etc.) remain the same
- **Expected**: Custom images marked for RTL mirroring flip appropriately

## RTL Layout Best Practices

The codebase already follows these best practices:

### ✅ DO: Use Semantic Directions

```swift
// Good - These automatically flip for RTL
VStack(alignment: .leading) { }
HStack { }
.frame(maxWidth: .infinity, alignment: .leading)
.padding(.leading, 16)
```

### ❌ DON'T: Use Absolute Directions

```swift
// Bad - These don't flip for RTL
.frame(maxWidth: .infinity, alignment: .left)
.padding(.left, 16)
```

### ✅ DO: Use FlexibleSpace and Spacer

```swift
// Good - Automatically adjusts for RTL
HStack {
    Text("Title")
    Spacer()
    Image(systemName: "chevron.right")
}
```

### ✅ DO: Use SF Symbols for Directional Icons

```swift
// Good - Automatically flips for RTL
Image(systemName: "chevron.right")
Image(systemName: "arrow.right")
```

### ⚠️ CAREFUL: GeometryReader with Offsets

When using GeometryReader with manual offsets, consider RTL:

```swift
// May need adjustment for RTL
.offset(x: (geometry.size.width * progress) - 7)

// Better approach - let SwiftUI handle it
ZStack(alignment: .leading) {
    // Progress bar fills from leading edge (right in RTL)
}
```

## Known RTL Compatibility

### Fully Compatible Components

All view components in the app use semantic directions and are RTL-compatible:

- ✅ MainTabView - Tab bar automatically mirrors
- ✅ DashboardView - All layouts use .leading/.trailing
- ✅ TestTakingView - Navigation and content adapt to RTL
- ✅ HistoryView - List and detail views support RTL
- ✅ SettingsView - All list items support RTL
- ✅ Custom components (PrimaryButton, CustomTextField, etc.)

### Components Requiring Manual Testing

These components use GeometryReader or custom layouts and should be manually tested:

1. **TestProgressView** - Progress bar with manual offset calculation
2. **TestCardProgress** - Progress bar in dashboard cards
3. **IQTrendChart** - Chart layouts and axes
4. **QuestionNavigationGrid** - Grid layout with manual positioning

## Testing Checklist

Use this checklist when testing RTL support:

### Visual Layout
- [ ] All text aligns to the right
- [ ] Navigation bars show back button on the right
- [ ] Tab bar items are mirrored (rightmost is active)
- [ ] Lists scroll naturally
- [ ] Chevrons and arrows point in correct direction
- [ ] Progress bars fill from right to left
- [ ] Cards and containers have proper alignment

### Interaction
- [ ] Tap targets work correctly
- [ ] Swipe gestures work in RTL direction
- [ ] Text input shows cursor on the right
- [ ] Button icons are positioned correctly

### Content
- [ ] No text truncation or overlap
- [ ] Multi-line text wraps correctly
- [ ] Numbers remain readable (LTR is acceptable)
- [ ] Dates and times display correctly

### Navigation
- [ ] Deep links work correctly
- [ ] Navigation stack behaves properly
- [ ] Tab switching works
- [ ] Modal presentations appear correctly

## Reporting Issues

If you find RTL layout issues:

1. Take a screenshot showing the issue
2. Note the view/screen where it occurs
3. Describe expected vs. actual behavior
4. Include the device/simulator and iOS version
5. Create a task in the project tracker

## Additional Resources

- [Apple Human Interface Guidelines - Right to Left](https://developer.apple.com/design/human-interface-guidelines/right-to-left)
- [SwiftUI Layout Directions](https://developer.apple.com/documentation/swiftui/layoutdirection)
- [Testing Your App in Different Languages](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPInternational/TestingYourInternationalApp/TestingYourInternationalApp.html)
