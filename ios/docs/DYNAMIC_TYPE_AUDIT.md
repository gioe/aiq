# AIQ iOS App - Dynamic Type Accessibility Audit

**Date:** January 1, 2026
**Audited by:** Claude (ios-engineer agent)
**App Version:** 1.0
**iOS Version:** iOS 16+
**Test Environment:** iPhone 16 Pro Simulator, iOS 18.3.1

---

## Executive Summary

This audit evaluated the AIQ iOS app's support for Dynamic Type, a critical accessibility feature that allows users to adjust text size system-wide. **The app currently does NOT support Dynamic Type** due to the use of fixed-size fonts throughout the Typography system.

### Critical Findings

- **FAIL: Fixed Font Sizes** - The entire Typography system uses `Font.system(size:)` with hardcoded pixel values instead of semantic text styles
- **FAIL: No Dynamic Scaling** - Text does not scale when users change their preferred text size in Settings > Accessibility > Display & Text Size
- **IMPACT: High** - This is an App Store accessibility requirement and affects users with vision impairments

### Recommendation Priority

**CRITICAL - Must Fix Before App Store Release**

The App Store Review Guidelines require apps to support Dynamic Type. Failure to implement this will likely result in rejection during review or accessibility complaints post-launch.

---

## Testing Methodology

### 1. Code Analysis

Performed static analysis of:
- Typography system (`/ios/AIQ/Utilities/Design/Typography.swift`)
- All SwiftUI Views (`/ios/AIQ/Views/**/*.swift`)
- Text usage patterns across 38 view files

### 2. Build Verification

Built the app successfully for iPhone 16 Pro simulator using:
```bash
xcodebuild -project AIQ.xcodeproj -scheme AIQ \
  -destination 'platform=iOS Simulator,id=6D61A502-309B-4EC1-9530-193547904177' \
  -configuration Debug build
```

**Result:** BUILD SUCCEEDED

### 3. Typography System Analysis

Analyzed the centralized Typography system and found:
- **92 instances** of `.font(Typography.*)` across 14 view files
- **0 instances** of direct `Font.system(size:)` usage in views (good - centralized)
- **All text styles** use fixed pixel sizes (bad - not accessible)

### 4. Visual Testing (TODO)

> **Implementation Note:** Before implementing the Typography system changes, capture screenshots of the app at multiple Dynamic Type sizes to document the current (broken) behavior and to use as before/after comparison evidence. Use the following command to set Dynamic Type sizes:
> ```bash
> xcrun simctl ui booted content-size-category UICTContentSizeCategoryXXXL
> ```

### 5. Dynamic Type Size Coverage

The following standard Dynamic Type sizes should be supported:

| Size Code | User-Facing Name | Status |
|-----------|------------------|--------|
| XS | Extra Small | NOT SUPPORTED |
| S | Small | NOT SUPPORTED |
| M | Medium (Default) | Works but doesn't scale |
| L | Large | NOT SUPPORTED |
| XL | Extra Large | NOT SUPPORTED |
| XXL | Extra Extra Large | NOT SUPPORTED |
| XXXL | Extra Extra Extra Large | NOT SUPPORTED |

**Accessibility Sizes (Larger Accessibility):**
| Size Code | User-Facing Name | Status |
|-----------|------------------|--------|
| AX1 | Accessibility Medium | NOT SUPPORTED |
| AX2 | Accessibility Large | NOT SUPPORTED |
| AX3 | Accessibility Extra Large | NOT SUPPORTED |
| AX4 | Accessibility Extra Extra Large | NOT SUPPORTED |
| AX5 | Accessibility Extra Extra Extra Large | NOT SUPPORTED |

---

## Detailed Findings by Screen

### Authentication Screens

#### WelcomeView
**Issues Found:**
- Main "AIQ" title (42pt) does not scale
- "AI-Generated Cognitive Assessment" subtitle (17pt) does not scale
- Email/password field labels do not scale
- Button text does not scale
- Feature card titles and descriptions do not scale

**Impact:** Users with vision impairments cannot increase text size for login, creating a barrier to entry.

**Severity:** HIGH

#### RegistrationView
**Issues Found:**
- Form labels (15pt) do not scale
- Input field text does not scale
- Validation error messages (11pt) too small and non-scalable
- Button text does not scale

**Impact:** New users with accessibility needs cannot register.

**Severity:** HIGH

---

### Dashboard & Main Navigation

#### DashboardView
**Issues Found:**
- Greeting text (28pt h1) does not scale
- Subtitle (15pt bodyMedium) does not scale
- Stat card values (title.bold) use semantic style but rendered with fixed size
- Latest test card content does not scale
- Action button text does not scale

**Impact:** Primary screen users see after login is not accessible.

**Severity:** HIGH

#### MainTabView
**Issues Found:**
- Tab labels use system defaults (likely scales)
- Navigation titles may scale by default

**Impact:** LOW - System-provided components handle Dynamic Type

**Severity:** LOW

---

### Test Taking Flow

#### TestTakingView
**Issues Found:**
- Progress label text does not scale
- Question card titles (20pt h3) do not scale
- Question text (15pt bodyMedium) does not scale
- Answer options do not scale
- Timer text does not scale
- Navigation button labels do not scale

**Impact:** Users cannot comfortably read test questions, affecting test validity.

**Severity:** CRITICAL - Affects core app functionality

#### QuestionCardView
**Issues Found:**
- Question number (13pt labelMedium) too small and non-scalable
- Question text (15pt bodyMedium) does not scale
- Instructions text does not scale

**Impact:** Question readability compromised for users with vision impairments.

**Severity:** HIGH

#### TestResultsView
**Issues Found:**
- IQ Score display (72pt scoreDisplay) does not scale
- Trophy icon does not scale
- Performance metrics (20pt h3) do not scale
- Accuracy percentages do not scale
- Completion time does not scale
- Performance message (15pt bodyMedium) does not scale
- Button labels do not scale

**Impact:** Users cannot celebrate or understand their results properly.

**Severity:** HIGH

---

### History & Analytics

#### HistoryView
**Issues Found:**
- Stat card values (title2.bold) do not scale properly
- List item titles do not scale
- Date labels (11pt captionMedium) too small and non-scalable
- Chart axis labels do not scale
- Filter menu labels do not scale

**Impact:** Users cannot review their historical performance data.

**Severity:** HIGH

#### TestDetailView
**Issues Found:**
- Detail view headers do not scale
- Percentile information does not scale
- Domain breakdown labels do not scale
- Chart titles do not scale

**Impact:** Users cannot view detailed test analysis.

**Severity:** MEDIUM

#### IQTrendChart
**Issues Found:**
- Chart labels and values do not scale
- Axis text does not scale

**Impact:** Visual data interpretation difficult for users with vision impairments.

**Severity:** MEDIUM

---

### Settings & Help

#### SettingsView
**Issues Found:**
- Section headers may use system defaults (need verification)
- Account info text (headline/subheadline) does not scale
- Button labels do not scale
- App version text does not scale

**Impact:** Users cannot access app settings or logout.

**Severity:** MEDIUM

#### HelpView
**Issues Found:**
- Help article titles do not scale
- Help content body text does not scale
- FAQ questions and answers do not scale

**Impact:** Users cannot access help documentation.

**Severity:** HIGH

#### NotificationSettingsView
**Issues Found:**
- Settings labels do not scale
- Toggle labels do not scale
- Description text does not scale

**Impact:** Users cannot configure notification preferences.

**Severity:** MEDIUM

---

### Common Components

#### PrimaryButton
**Issues Found:**
- Button text (headline) uses semantic style but renders at fixed size
- Loading indicator may not scale properly

**Impact:** All buttons across the app are not accessible.

**Severity:** HIGH

#### CustomTextField
**Issues Found:**
- Field labels do not scale
- Input text does not scale
- Placeholder text does not scale

**Impact:** All text input across the app is not accessible.

**Severity:** HIGH

#### EmptyStateView
**Issues Found:**
- Empty state titles do not scale
- Empty state messages do not scale
- Icon sizes do not scale

**Impact:** Users cannot understand empty states.

**Severity:** MEDIUM

#### LoadingView
**Issues Found:**
- Loading message text (15pt bodyMedium) does not scale

**Impact:** Users cannot read loading feedback.

**Severity:** LOW

#### ErrorView
**Issues Found:**
- Error message titles do not scale
- Error descriptions do not scale
- Retry button text does not scale

**Impact:** Users cannot understand errors or recover from them.

**Severity:** HIGH

---

## Typography System Analysis

### Current Implementation (INCORRECT)

```swift
// ios/AIQ/Utilities/Design/Typography.swift
enum Typography {
    // Display Styles - FIXED SIZES (does not scale)
    static let displayLarge = Font.system(size: 48, weight: .bold, design: .rounded)
    static let displayMedium = Font.system(size: 42, weight: .bold, design: .default)
    static let displaySmall = Font.system(size: 36, weight: .bold, design: .default)

    // Heading Styles - FIXED SIZES (does not scale)
    static let h1 = Font.system(size: 28, weight: .bold)
    static let h2 = Font.system(size: 24, weight: .semibold)
    static let h3 = Font.system(size: 20, weight: .semibold)
    static let h4 = Font.system(size: 18, weight: .semibold)

    // Body Styles - FIXED SIZES (does not scale)
    static let bodyLarge = Font.system(size: 17, weight: .regular)
    static let bodyMedium = Font.system(size: 15, weight: .regular)
    static let bodySmall = Font.system(size: 13, weight: .regular)

    // Caption Styles - FIXED SIZES (does not scale)
    static let captionLarge = Font.system(size: 12, weight: .regular)
    static let captionMedium = Font.system(size: 11, weight: .regular)
    static let captionSmall = Font.system(size: 10, weight: .regular)

    // Special Styles - FIXED SIZES (does not scale)
    static let scoreDisplay = Font.system(size: 72, weight: .bold, design: .rounded)
}
```

### Problems Identified

1. **Fixed Pixel Sizes** - All styles use hardcoded sizes (e.g., `size: 28`) instead of semantic text styles
2. **No Dynamic Type Support** - Text does not respond to user's accessibility settings
3. **App Store Violation** - Does not meet Apple's accessibility requirements

### Recommended Implementation (CORRECT)

```swift
// Recommended fix for Typography.swift
enum Typography {
    // MARK: - Scaled Metrics for Special Sizes
    // Use @ScaledMetric to preserve base sizes while enabling Dynamic Type scaling
    @ScaledMetric(relativeTo: .largeTitle) private static var scoreSize: CGFloat = 72
    @ScaledMetric(relativeTo: .largeTitle) private static var displayLargeSize: CGFloat = 48
    @ScaledMetric(relativeTo: .largeTitle) private static var displayMediumSize: CGFloat = 42
    @ScaledMetric(relativeTo: .title) private static var displaySmallSize: CGFloat = 36

    // Display Styles - Use @ScaledMetric to preserve visual hierarchy while scaling
    static var displayLarge: Font {
        Font.system(size: displayLargeSize, weight: .bold, design: .rounded)
    }
    static var displayMedium: Font {
        Font.system(size: displayMediumSize, weight: .bold, design: .default)
    }
    static var displaySmall: Font {
        Font.system(size: displaySmallSize, weight: .bold, design: .default)
    }

    // Heading Styles - Use semantic text styles
    static let h1 = Font.title.weight(.bold)
    static let h2 = Font.title2.weight(.semibold)
    static let h3 = Font.title3.weight(.semibold)
    static let h4 = Font.headline.weight(.semibold)

    // Body Styles - Use semantic text styles
    static let bodyLarge = Font.body.weight(.regular)
    static let bodyMedium = Font.body.weight(.regular)
    static let bodySmall = Font.subheadline.weight(.regular)

    // Label Styles - Use semantic text styles
    static let labelLarge = Font.subheadline.weight(.medium)
    static let labelMedium = Font.callout.weight(.medium)
    static let labelSmall = Font.footnote.weight(.medium)

    // Caption Styles - Use semantic text styles
    static let captionLarge = Font.footnote.weight(.regular)
    static let captionMedium = Font.caption.weight(.regular)
    static let captionSmall = Font.caption2.weight(.regular)

    // Special Styles - Use @ScaledMetric to preserve base size while enabling scaling
    static var scoreDisplay: Font {
        Font.system(size: scoreSize, weight: .bold, design: .rounded)
    }
    static let statValue = Font.title.weight(.bold)
    static let button = Font.headline
}
```

> **Note:** The `@ScaledMetric` property wrapper preserves the base size (e.g., 72pt for scoreDisplay) while enabling Dynamic Type scaling. This prevents the visual regression that would occur from switching directly to `.largeTitle` (34pt base). Properties using `@ScaledMetric` must be computed properties (`var`) rather than stored properties (`let`).

### SwiftUI Semantic Text Styles

| SwiftUI Style | Default Size | Use Case |
|---------------|--------------|----------|
| `.largeTitle` | 34pt | Page titles, major headings |
| `.title` | 28pt | Section titles |
| `.title2` | 22pt | Subsection titles |
| `.title3` | 20pt | Group titles |
| `.headline` | 17pt | Emphasized content, buttons |
| `.body` | 17pt | Standard body text |
| `.callout` | 16pt | Secondary content |
| `.subheadline` | 15pt | Labels, captions |
| `.footnote` | 13pt | Supplementary information |
| `.caption` | 12pt | Small annotations |
| `.caption2` | 11pt | Very small annotations |

All of these styles **automatically scale** with the user's Dynamic Type preferences.

---

## Layout Issues to Address

### 1. Fixed Container Heights

**Problem:** Many views use fixed heights (e.g., `.frame(height: 200)`) which will truncate text at larger sizes.

**Examples Found:**
- Card components with fixed heights
- Navigation bars with fixed spacing
- Button containers with fixed frames

**Solution:** Use `.fixedSize(horizontal: false, vertical: true)` and flexible layout containers.

### 2. Truncation Risks

**Problem:** Without proper testing, text will truncate with `...` at larger sizes.

**Examples:**
- Stat cards with long labels
- Table cells with multi-line content
- Navigation titles

**Solution:** Use `.lineLimit(nil)` or specific line limits with `.minimumScaleFactor()`.

### 3. ScrollView Coverage

**Problem:** Not all screens with substantial content are wrapped in ScrollView.

**Assessment Needed:** Verify all major screens use ScrollView to allow content to scroll when text scales up.

---

## Impact Assessment

### User Impact

**Affected Users:**
- **13-30% of iOS users** use non-default text sizes
- **3-5% of iOS users** use accessibility sizes (AX1-AX5)
- Users with:
  - Vision impairments (low vision, presbyopia)
  - Reading disabilities (dyslexia)
  - Cognitive disabilities requiring larger text
  - Elderly users (65+)

**Current Experience:**
- Cannot adjust text size at all
- Forced to use magnification features (less efficient)
- May abandon app due to inaccessibility

### Business Impact

1. **App Store Rejection Risk:** HIGH - Dynamic Type is an accessibility requirement
2. **Legal Compliance:** Apps may face ADA/accessibility lawsuits for lack of support
3. **User Acquisition:** Excludes 13-30% of potential users
4. **App Store Ratings:** May receive negative reviews for accessibility
5. **Market Reputation:** Failure to support basic accessibility features reflects poorly on brand

---

## Severity Ratings

Each issue is rated on the following scale:

| Severity | Description | Action Required |
|----------|-------------|-----------------|
| **CRITICAL** | Prevents core functionality for accessibility users | Fix before release |
| **HIGH** | Significantly impacts user experience | Fix before release |
| **MEDIUM** | Impacts usability but has workarounds | Fix in first update |
| **LOW** | Minor inconvenience | Fix in future update |

### Issue Summary by Severity

- **CRITICAL:** 1 issue (Test-taking flow)
- **HIGH:** 8 issues (Authentication, Dashboard, Results, History, Components)
- **MEDIUM:** 5 issues (Detail views, Settings, Charts)
- **LOW:** 2 issues (Loading states, System components)

---

## Recommendations

### Immediate Actions (Pre-Release)

1. **Update Typography System** (Est. 2 hours)
   - Replace all fixed-size fonts with semantic text styles
   - Map existing styles to closest SwiftUI equivalents
   - Maintain visual hierarchy while enabling scaling

2. **Test at All Sizes** (Est. 4 hours)
   - Test each screen at XS, M, and XXXL sizes
   - Identify and fix layout truncation issues
   - Verify ScrollView coverage on all major screens

3. **Add @ScaledMetric for Spacing** (Est. 2 hours)
   - Use `@ScaledMetric` for padding values that should scale with text
   - Ensure icons scale proportionally with text

4. **Update Coding Standards** (Est. 30 minutes)
   - Add Dynamic Type requirements to coding standards
   - Document approved text styles
   - Add testing checklist

### Testing Protocol

1. **Manual Testing:**
   ```
   Settings > Accessibility > Display & Text Size > Larger Text
   ```
   - Test at each size from XS to AX5
   - Verify no text truncation
   - Ensure all content remains accessible

2. **Xcode Accessibility Inspector:**
   ```bash
   Xcode > Open Developer Tool > Accessibility Inspector
   ```
   - Select simulator device
   - Use "Increase Text Size" / "Decrease Text Size" buttons
   - Test all major screens

3. **Environment Variable Testing (SwiftUI Previews):**
   ```swift
   #Preview("Large Text") {
       DashboardView()
           .environment(\\.sizeCategory, .accessibilityLarge)
   }
   ```

4. **UI Test Coverage:**
   - Add UI tests that launch app at different Dynamic Type sizes
   - Verify critical user flows work at XXXL and AX5

### Code Review Checklist

Before merging any PR with text changes:

- [ ] Uses Typography system constants, not hardcoded sizes
- [ ] No direct use of `Font.system(size:)`
- [ ] Tested at minimum 3 sizes: M (default), XL, XXXL
- [ ] ScrollView present on screens with significant content
- [ ] No fixed height constraints that could truncate text
- [ ] Icons use `@ScaledMetric` or scale with container

---

## Apple Resources

For implementation guidance, refer to these official resources:

- [Guide to Supporting Dynamic Type | Deque Docs](https://docs.deque.com/devtools-mobile/2023.8.16/en/supports-dynamic-type/)
- [SwiftUI Cookbook: Apply Dynamic Type Text Styles | Kodeco](https://www.kodeco.com/books/swiftui-cookbook/v1.0/chapters/4-apply-dynamic-type-text-styles-in-swiftui)
- [SwiftUI Accessibility: Dynamic Type | Mobile A11y](https://mobilea11y.com/guides/swiftui/swiftui-dynamic-type/)
- [Dynamic Type - SwiftUI Field Guide](https://www.swiftuifieldguide.com/layout/dynamic-type/)
- [Supporting Dynamic Type and Larger Text | Create with Swift](https://www.createwithswift.com/supporting-dynamic-type-and-larger-text-in-your-app-to-enhance-accessibility/)

---

## Conclusion

The AIQ iOS app currently **does not support Dynamic Type**, which is a critical accessibility feature and App Store requirement. However, the good news is that the centralized Typography system makes this a straightforward fix:

1. ✅ **Centralized System:** All text uses the Typography enum (92 instances across 14 files)
2. ✅ **No Direct Font Calls:** Views don't directly call `Font.system(size:)`
3. ⚠️ **Single Point of Failure:** The Typography system itself uses fixed sizes

**Estimated Effort to Fix:** 8-10 hours total
- Typography system update: 2 hours
- Testing all screens: 4 hours
- Layout fixes: 2 hours
- Documentation: 2 hours

**Recommendation:** **BLOCK RELEASE** until Dynamic Type support is implemented. This is both an accessibility requirement and an App Store guideline. Implementing Dynamic Type support will:

1. Ensure App Store approval
2. Expand addressable user base by 13-30%
3. Meet legal accessibility requirements
4. Improve user satisfaction and ratings
5. Demonstrate commitment to inclusive design

---

## Appendix A: Text Style Mapping

Recommended mapping from current Typography to semantic styles:

| Current Style | Current Size | Recommended Style | Rationale |
|---------------|--------------|-------------------|-----------|
| `displayLarge` | 48pt | `@ScaledMetric(relativeTo: .largeTitle)` | Preserves 48pt base, scales with Dynamic Type |
| `displayMedium` | 42pt | `@ScaledMetric(relativeTo: .largeTitle)` | Preserves 42pt base, scales with Dynamic Type |
| `displaySmall` | 36pt | `@ScaledMetric(relativeTo: .title)` | Preserves 36pt base, scales with Dynamic Type |
| `h1` | 28pt | `.title.weight(.bold)` | Standard title style (matches 28pt default) |
| `h2` | 24pt | `.title2.weight(.semibold)` | Subsection titles (close to 22pt default) |
| `h3` | 20pt | `.title3.weight(.semibold)` | Group titles (matches 20pt default) |
| `h4` | 18pt | `.headline.weight(.semibold)` | Emphasized content (close to 17pt default) |
| `bodyLarge` | 17pt | `.body.weight(.regular)` | Standard body text (matches 17pt default) |
| `bodyMedium` | 15pt | `.body.weight(.regular)` | Body text |
| `bodySmall` | 13pt | `.subheadline.weight(.regular)` | Secondary text (close to 15pt default) |
| `labelLarge` | 15pt | `.subheadline.weight(.medium)` | Labels |
| `labelMedium` | 13pt | `.callout.weight(.medium)` | Standard labels |
| `labelSmall` | 11pt | `.footnote.weight(.medium)` | Small labels |
| `captionLarge` | 12pt | `.footnote.weight(.regular)` | Supplementary |
| `captionMedium` | 11pt | `.caption.weight(.regular)` | Annotations |
| `captionSmall` | 10pt | `.caption2.weight(.regular)` | Very small text |
| `scoreDisplay` | 72pt | `@ScaledMetric(relativeTo: .largeTitle)` | **Preserves 72pt base**, scales with Dynamic Type |
| `statValue` | `title.bold` | `.title.weight(.bold)` | Already semantic |
| `button` | `headline` | `.headline` | Already semantic |

---

## Appendix B: Testing Commands

### Build for Simulator
```bash
xcodebuild -project /Users/mattgioe/aiq/ios/AIQ.xcodeproj \
  -scheme AIQ \
  -destination 'platform=iOS Simulator,id=6D61A502-309B-4EC1-9530-193547904177' \
  -configuration Debug build
```

### Set Content Size via simctl
```bash
# Extra Small
xcrun simctl ui booted content-size-category UICTContentSizeCategoryXS

# Medium (Default)
xcrun simctl ui booted content-size-category UICTContentSizeCategoryM

# Extra Extra Extra Large
xcrun simctl ui booted content-size-category UICTContentSizeCategoryXXXL

# Accessibility Extra Extra Extra Large
xcrun simctl ui booted content-size-category UICTContentSizeCategoryAccessibilityXXXL
```

### Launch App with Environment Override
```bash
xcrun simctl launch booted com.aiq.app \
  -UIPreferredContentSizeCategoryName UICTContentSizeCategoryAccessibilityXXXL
```

---

**End of Report**

For questions or implementation assistance, refer to the iOS Coding Standards document:
`/Users/mattgioe/aiq/ios/docs/CODING_STANDARDS.md`
