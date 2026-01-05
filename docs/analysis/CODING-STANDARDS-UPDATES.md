# Recommended Updates to iOS Coding Standards

Based on analysis of PR #466 review findings, these additions will help prevent similar issues in future development.

## Priority 1: Must Add (High Value)

### 1. Configuration Management Section

**Add after line 1684 (after Security section)**

```markdown
---

## Configuration Management

### External URLs

Centralize external URLs in `AppConfig.swift` to ensure consistency, easy updates, and compile-time validation.

**DO:**
- Add external URLs to AppConfig with clear documentation
- Use force unwrapping only when URLs are validated in tests
- Document the purpose and expected availability of each URL

**DON'T:**
- Hardcode external URLs directly in views
- Use force unwrapping without test coverage
- Create multiple URL constants for the same resource

**Example:**

```swift
// In AppConfig.swift
enum AppConfig {
    // MARK: - External URLs

    /// Privacy policy URL
    /// Returns the URL to the AIQ privacy policy page
    static var privacyPolicyURL: URL {
        // This URL is validated at compile time in tests
        // swiftlint:disable:next force_unwrapping
        URL(string: "https://aiq.app/privacy-policy")!
    }

    /// Terms of service URL
    static var termsOfServiceURL: URL {
        // swiftlint:disable:next force_unwrapping
        URL(string: "https://aiq.app/terms")!
    }
}

// In view
Link("Privacy Policy", destination: AppConfig.privacyPolicyURL)
```

**Test validation:**

All URLs in AppConfig should be validated in tests to prevent crashes:

```swift
func testPrivacyPolicyURL_IsValid() {
    // Ensures AppConfig.privacyPolicyURL doesn't crash
    let url = AppConfig.privacyPolicyURL
    XCTAssertEqual(url.scheme, "https")
    XCTAssertNotNil(url.host)
}
```

**When to use AppConfig:**
- External marketing pages (privacy policy, terms, support)
- API endpoints (already established pattern)
- Deep link URLs and custom schemes
- Any URL that might change between environments

**When NOT to use AppConfig:**
- Dynamic URLs constructed from user input or API responses
- Temporary URLs for development/testing only
```

### 2. Global State Modifications in SwiftUI

**Add to SwiftUI Best Practices section after line 376 (after ViewModifiers subsection)**

```markdown

### Global Appearance Modifications

When using `UIAppearance` API to customize UIKit components embedded in SwiftUI, always document the global scope and implications.

**IMPORTANT:** UIAppearance modifications affect ALL instances of a component throughout the app, not just the current view. SwiftUI does not provide scoped appearance APIs for UIKit components.

**DO:**
- Add comprehensive doc comments explaining global scope
- Document when and where the modification takes effect
- Warn about side effects on other views using the same component
- Consider implementing a custom SwiftUI component instead if different styling is needed in different contexts

**DON'T:**
- Modify global appearance without documentation
- Assume appearance changes are scoped to a single view
- Forget that UIAppearance affects system-provided components
- Use UIAppearance when a custom component would be clearer and more maintainable

**Example:**

```swift
/// Configure UIPageControl appearance for onboarding
///
/// - Note: This modifies the **global** UIPageControl appearance, affecting all TabView page indicators
///   throughout the app. SwiftUI does not currently provide a scoped API for customizing
///   page indicators within a single TabView.
///
///   **Side effects:**
///   - All TabView page indicators will use these colors
///   - System default colors will be overridden app-wide
///
///   **If different styling is needed elsewhere:** Consider implementing a custom page indicator
///   component using SwiftUI instead of relying on UIAppearance.
private func configurePageControl() {
    let appearance = UIPageControl.appearance()
    appearance.currentPageIndicatorTintColor = UIColor(ColorPalette.primary)
    appearance.pageIndicatorTintColor = UIColor(ColorPalette.textTertiary)
}
```

**When to use UIAppearance:**
- SwiftUI doesn't provide the needed customization API
- The styling should intentionally apply app-wide
- You've verified no other views need different styling
- Creating a custom component would be significantly more complex

**When to avoid UIAppearance:**
- Different views need different styling for the same component type
- The modification might conflict with system defaults in unexpected contexts
- A custom SwiftUI component could achieve the same result with better encapsulation
- You need the flexibility to change styling in specific contexts

**Common UIAppearance use cases in SwiftUI:**
- `UIPageControl` - TabView page indicators
- `UINavigationBar` - Navigation bar appearance (though prefer SwiftUI modifiers when possible)
- `UITableView` - List separators and backgrounds
- `UISwitch`, `UISlider` - Control tints
```

---

## Priority 2: Should Add (Medium Value)

### 3. Animation Delays and Staggering

**Add to Animations subsection under Design System (after line 750)**

```markdown

### Animation Delays and Staggering

For staggered animations (sequential entrance effects), use judgment about when to create constants:

**One-off stagger pattern (acceptable for view-specific choreography):**

When animation delays are specific to a single view's entrance choreography and unlikely to be reused:

```swift
VStack {
    headerView
        .opacity(isAnimating ? 1.0 : 0.0)
        .animation(DesignSystem.Animation.smooth.delay(0.2), value: isAnimating)

    contentView
        .opacity(isAnimating ? 1.0 : 0.0)
        .animation(DesignSystem.Animation.smooth.delay(0.4), value: isAnimating)
}
```

**Reused stagger pattern (create constants when used 3+ times):**

When the same stagger timing is reused across multiple views or components:

```swift
// In DesignSystem.swift
enum AnimationDelays {
    /// Short stagger delay for sequential animations (200ms)
    static let staggerShort: TimeInterval = 0.2

    /// Medium stagger delay for sequential animations (400ms)
    static let staggerMedium: TimeInterval = 0.4

    /// Long stagger delay for sequential animations (600ms)
    static let staggerLong: TimeInterval = 0.6
}

// Usage
.animation(
    DesignSystem.Animation.smooth.delay(DesignSystem.AnimationDelays.staggerShort),
    value: isAnimating
)
```

**Rationale:**

Animation delays are often specific to a particular view's choreography. Creating constants for every delay value adds overhead without clear benefit unless the pattern is genuinely reused.

**Guidelines:**
- Use inline delays for onboarding flows, tutorials, and one-off animations
- Create constants when the same stagger pattern appears in 3+ places
- Document the purpose of delay constants (e.g., "stagger for card entrance")
- Keep delays relative to animation duration (0.2s for 0.4s animation = 50% stagger)
```

---

## Priority 3: Nice to Have (Low Priority)

### 4. Haptic Feedback Patterns

**Add as new subsection under SwiftUI Best Practices or Performance section**

```markdown

### Haptic Feedback

Use haptic feedback to enhance user interactions. Haptics should feel responsive, not laggy or excessive.

**Pattern 1: Inline instantiation (preferred for most cases)**

For button taps and one-off actions, instantiate haptic generators inline:

```swift
Button("Submit") {
    let generator = UIImpactFeedbackGenerator(style: .medium)
    generator.impactOccurred()
    handleSubmit()
}
```

**Pattern 2: Prepared generator (optional optimization)**

For high-frequency interactions or when measurable latency exists, prepare generators in advance:

```swift
@MainActor
class InteractiveViewModel: BaseViewModel {
    private let buttonTapGenerator = UIImpactFeedbackGenerator(style: .medium)

    override init() {
        super.init()
        buttonTapGenerator.prepare()
    }

    func handleButtonTap() {
        buttonTapGenerator.impactOccurred()
        // Handle action
    }
}
```

**When to prepare haptics:**
- High-frequency interactions (slider scrubbing, game controls, rapid tapping)
- Performance-critical views where latency is measurable
- When profiling shows haptic latency impacting user experience

**When inline instantiation is fine:**
- Standard button taps and one-off actions
- Onboarding flows and infrequent interactions
- When code simplicity outweighs micro-optimization benefits
- Most view code (default to this pattern)

**Haptic style guide:**

| Style | Use Case | Example |
|-------|----------|---------|
| `.light` | Subtle selections, toggles | Switching tabs, selecting items |
| `.medium` | Standard button taps | Primary/secondary buttons, continues |
| `.heavy` | Important/destructive actions | Delete, submit final answer |
| `.success` | Successful completion | Test submitted, data saved |
| `.warning` | Caution or destructive confirmation | "Are you sure?" dialogs |
| `.error` | Failed action or validation | Invalid input, network error |

**Best practices:**
- Use haptics to reinforce visual feedback, not replace it
- Respect accessibility settings (haptics automatically disabled if user has turned them off)
- Don't overuse - too many haptics feel chaotic
- Match haptic intensity to action importance
- Trigger haptics at the moment of action, not after delay

**Example - Complete button interaction:**

```swift
Button("Submit Test") {
    let generator = UINotificationFeedbackGenerator()
    generator.notificationOccurred(.success)

    Task {
        await viewModel.submitTest()
    }
}
.accessibilityHint("Double tap to submit your test answers")
```
```

---

## SwiftLint Configuration Changes

### Optional: Enable `missing_docs` for High-Value Scopes

**Current state:** `missing_docs` rule is disabled globally

**Recommendation:** Keep disabled globally, but consider selectively enabling for critical public APIs

**Why not enable globally:**
- High noise for self-explanatory properties (`isLoading`, `hasTests`)
- Encourages low-quality boilerplate comments
- Most view code has obvious property purposes

**Where to consider enabling:**
- Public protocol definitions (APIClientProtocol, AuthServiceProtocol)
- Service layer classes (APIClient, AuthService, AnalyticsService)
- Complex ViewModels with non-obvious state management

**Implementation (if desired):**

```yaml
# .swiftlint.yml

# Keep disabled globally
missing_docs:
  severity: none

# Enable for specific paths
included_paths_for_missing_docs:
  - ios/AIQ/Services/
  - ios/AIQ/Protocols/

# Exclude obvious cases
excluded_names_from_missing_docs:
  - isLoading
  - isError
  - hasData
```

**Recommendation:** Start with PR review enforcement, only add linting if documentation debt grows.

---

## Summary

### Must Add (Priority 1)
1. Configuration Management section - External URL centralization pattern
2. Global Appearance Modifications - Document UIAppearance side effects

### Should Add (Priority 2)
3. Animation Delays guidance - When to inline vs. create constants

### Nice to Have (Priority 3)
4. Haptic Feedback patterns - Inline vs. prepared generators

### Changes NOT Recommended
- Enabling `missing_docs` SwiftLint rule globally (too noisy)
- Creating custom lint rules for animation delays (too many false positives)
- Requiring haptic generator preparation (micro-optimization, not worth complexity)

### Implementation Plan

1. Add Priority 1 items to CODING_STANDARDS.md immediately
2. Monitor next 2-3 PRs to validate Priority 2 guidance is needed
3. Add Priority 3 items opportunistically when editing that section of docs
4. Review effectiveness after 1 month and adjust

### Validation

After adding these standards:
- Review 2-3 future onboarding-style PRs to see if issues recur
- Check if developers reference these sections during development
- Adjust wording if sections are confusing or create friction
