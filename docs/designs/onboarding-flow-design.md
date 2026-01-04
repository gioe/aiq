# AIQ iOS Onboarding Flow - Design Specification

## Summary
A 4-screen onboarding flow for first-time AIQ users that introduces the app's value proposition, explains how testing works, establishes the recommended 3-month testing cadence, and reassures users about data privacy. The design follows iOS Human Interface Guidelines, maintains WCAG AA accessibility compliance, and uses the existing AIQ design system.

---

## Platform Compliance

### iOS Human Interface Guidelines Adherence
- **Onboarding Pattern**: Sequential page-based navigation with page indicators
- **Navigation**: Swipe gesture support + explicit "Continue" buttons for accessibility
- **Dismissal**: "Skip" button available (except final screen which requires action)
- **Visual Design**: Uses SF Symbols for all icons, maintains iOS visual language
- **Gesture Support**: Full swipe gesture support with haptic feedback
- **Safe Areas**: All content respects safe area insets for notched devices

### Design System Integration
- **Typography**: Uses existing Typography enum (displayMedium, h2, bodyLarge, bodyMedium)
- **Colors**: Uses ColorPalette semantic colors with WCAG AA compliance
- **Spacing**: Uses DesignSystem.Spacing tokens consistently
- **Animations**: Uses DesignSystem.Animation for smooth transitions
- **Components**: Leverages existing PrimaryButton and design patterns

---

## Accessibility Audit

### WCAG 2.1 AA Compliance

#### Perceivable
- **Color Contrast**: All text meets 4.5:1 minimum (using textPrimary/textSecondary)
- **Icons**: Decorative icons marked with .accessibilityHidden(true), semantic meaning conveyed through text
- **Dynamic Type**: All text uses semantic font styles that scale with Dynamic Type
- **VoiceOver**: Full VoiceOver support with descriptive labels and hints

#### Operable
- **Touch Targets**: All buttons minimum 44x44pt (iOS standard)
- **Keyboard Navigation**: Not applicable for iOS touch interface
- **Gestures**: Swipe gestures supplemented with explicit button controls
- **Motion**: Respects `@Environment(\.accessibilityReduceMotion)` to disable animations when needed

#### Understandable
- **Clear Language**: Concise, jargon-free copy at 8th-grade reading level
- **Consistent Navigation**: Same pattern across all screens
- **Progress Indicators**: Page indicator shows position in flow
- **Error Prevention**: No forms or inputs to validate

#### Robust
- **Screen Reader**: Full VoiceOver compatibility with proper accessibility labels
- **Semantic Structure**: Proper heading hierarchy and element grouping

---

## Localization Readiness

### Text Expansion
- **Layouts**: Use VStack/HStack with flexible spacing to accommodate text expansion
- **Buttons**: Text wrapping enabled for languages like German (30% longer)
- **Fixed Widths**: Avoided; all containers use maxWidth with padding

### RTL Support
- **Layouts**: Use leading/trailing instead of left/right for automatic RTL support
- **Icons**: SF Symbols automatically flip for RTL where appropriate
- **Page Indicators**: Will reverse direction in RTL contexts

### Cultural Neutrality
- **Icons**: Brain, chart, calendar, lock are culturally universal
- **Imagery**: Abstract scientific visuals, no culture-specific content
- **Language**: Neutral, scientific tone suitable for global audience

### String Externalization
- All user-facing strings should be defined as localized string keys
- No hardcoded text in views
- Support for NSLocalizedString pattern

---

## UX Analysis

### Information Architecture
The 4-screen flow follows a logical progression:
1. **Value Proposition** - Hook users with the "why"
2. **How It Works** - Set expectations for the experience
3. **Testing Cadence** - Establish usage pattern for success
4. **Privacy** - Address common objection before first test

### Cognitive Load
- **One Concept Per Screen**: Each screen focuses on a single key message
- **Visual Hierarchy**: Large icon → headline → body → CTA
- **Progressive Disclosure**: Information revealed gradually, not overwhelming
- **Scannable Content**: Bullet points, short paragraphs, visual emphasis

### User Journey
**Entry Point**: First launch after registration
**Exit Point**: Dashboard with "Start First Test" prompt
**Skip Option**: Available to reduce friction, but encouraged to complete
**Re-access**: Settings → About → "View Onboarding Again"

### Edge Cases Considered
- **Reduce Motion**: Animations disabled for users with motion sensitivity
- **Large Text Sizes**: ScrollView ensures content accessible at all Dynamic Type sizes
- **Interruptions**: State preserved if app backgrounded during onboarding
- **Skip Flow**: Users who skip see condensed info card on dashboard

---

## Onboarding Screens Specification

### Screen 1: Value Proposition
**Purpose**: Hook users by explaining what AIQ does and why it matters

#### Content

**Icon**
- SF Symbol: `brain.head.profile`
- Size: 64pt (DesignSystem.IconSize.huge)
- Color: ColorPalette.scoreGradient (blue to purple)
- Animation: Subtle scale pulse (respects reduce motion)

**Headline**
- Text: "Track Your Cognitive Capacity"
- Style: Typography.displayMedium (42pt bold)
- Color: ColorPalette.textPrimary
- Alignment: Center

**Body Copy**
- Text: "Just like tracking your weight, heart rate, or steps, AIQ helps you monitor your cognitive performance over time. See how your mind performs and track changes with scientifically-based assessments."
- Style: Typography.bodyLarge (17pt regular)
- Color: ColorPalette.textSecondary
- Alignment: Center
- Max Lines: 4-5 lines

**Feature Highlights** (3 compact points)
- Brain icon (teal) + "Fresh AI-generated questions every test"
- Chart icon (purple) + "Track trends over months and years"
- Trophy icon (orange) + "Scientifically-grounded methodology"

Each highlight:
- Icon: 24pt SF Symbol, colored (statGreen, statPurple, statOrange)
- Text: Typography.bodyMedium (16pt)
- Layout: HStack with icon leading, text trailing

**CTA Button**
- Text: "Continue"
- Component: PrimaryButton
- Style: Full width with horizontal padding
- Accessibility: "Continue to learn how tests work"

**Skip Option**
- Text: "Skip"
- Style: Text button, Typography.bodyMedium
- Color: ColorPalette.textSecondary
- Position: Below CTA button
- Accessibility: "Skip onboarding and go to dashboard"

**Page Indicator**
- Position: 1 of 4
- Style: iOS standard UIPageControl
- Color: Active = ColorPalette.primary, Inactive = ColorPalette.textTertiary

#### Layout Structure
```swift
VStack(spacing: DesignSystem.Spacing.xxxl) {
    Spacer(minLength: DesignSystem.Spacing.xl)

    // Icon
    Image(systemName: "brain.head.profile")

    // Content Group
    VStack(spacing: DesignSystem.Spacing.lg) {
        // Headline
        Text("Track Your Cognitive Capacity")

        // Body
        Text("Just like tracking...")

        // Feature Highlights
        VStack(spacing: DesignSystem.Spacing.md) {
            FeatureHighlightRow(...)
            FeatureHighlightRow(...)
            FeatureHighlightRow(...)
        }
    }

    Spacer()

    // CTA + Skip
    VStack(spacing: DesignSystem.Spacing.sm) {
        PrimaryButton("Continue", ...)
        Button("Skip", ...)
    }

    // Page Indicator
    PageIndicator(currentPage: 0, totalPages: 4)
}
.padding(.horizontal, DesignSystem.Spacing.xxl)
```

#### Accessibility Implementation
- Icon: `.accessibilityHidden(true)` (decorative)
- Headline: `.accessibilityAddTraits(.isHeader)`
- Body: Default accessibility (reads entire text)
- Feature highlights: `.accessibilityElement(children: .combine)` per row
- CTA: Default button semantics
- Skip: `.accessibilityHint("Skip onboarding and go to dashboard")`
- Page indicator: `.accessibilityLabel("Page 1 of 4")`

---

### Screen 2: How Tests Work
**Purpose**: Set clear expectations for the testing experience

#### Content

**Icon**
- SF Symbol: `puzzlepiece.extension.fill`
- Size: 64pt (DesignSystem.IconSize.huge)
- Color: ColorPalette.statBlue
- Animation: Gentle rotation on appear (respects reduce motion)

**Headline**
- Text: "How AIQ Tests Work"
- Style: Typography.displayMedium (42pt bold)
- Color: ColorPalette.textPrimary
- Alignment: Center

**Body Copy**
- Text: "Each test contains a mix of questions across cognitive domains—pattern recognition, logic, spatial reasoning, math, and verbal skills. Tests are untimed but typically take 15-25 minutes."
- Style: Typography.bodyLarge (17pt regular)
- Color: ColorPalette.textSecondary
- Alignment: Center

**Test Process Steps** (3 numbered steps with icons)

1. **Answer Questions**
   - Icon: `questionmark.circle.fill` (blue)
   - Text: "Work through diverse cognitive challenges at your own pace"

2. **Review Your Score**
   - Icon: `chart.bar.fill` (green)
   - Text: "See your IQ score with confidence intervals and percentile rank"

3. **Track Progress**
   - Icon: `arrow.up.right.circle.fill` (purple)
   - Text: "Compare results over time to see trends and improvements"

Each step:
- Number badge: Circle with number, ColorPalette.primary background, white text
- Icon: 32pt SF Symbol, colored
- Heading: Typography.labelLarge (15pt medium)
- Description: Typography.bodySmall (15pt regular)
- Layout: HStack with number+icon, VStack for text

**Informational Note**
- Text: "Questions are freshly generated each night to prevent memorization"
- Style: Typography.captionMedium (12pt)
- Color: ColorPalette.textSecondary
- Background: ColorPalette.backgroundSecondary with rounded corners
- Icon: `info.circle` leading

**CTA Button**
- Text: "Continue"
- Component: PrimaryButton
- Accessibility: "Continue to learn about testing frequency"

**Skip Option**
- Text: "Skip"
- Style: Text button, Typography.bodyMedium
- Color: ColorPalette.textSecondary

**Page Indicator**
- Position: 2 of 4

#### Layout Structure
```swift
ScrollView {
    VStack(spacing: DesignSystem.Spacing.xxxl) {
        // Icon
        Image(systemName: "puzzlepiece.extension.fill")

        // Content Group
        VStack(spacing: DesignSystem.Spacing.xl) {
            // Headline
            Text("How AIQ Tests Work")

            // Body
            Text("Each test contains...")

            // Process Steps
            VStack(alignment: .leading, spacing: DesignSystem.Spacing.lg) {
                ProcessStepRow(number: 1, ...)
                ProcessStepRow(number: 2, ...)
                ProcessStepRow(number: 3, ...)
            }

            // Info Note
            InfoCard("Questions are freshly generated...")
        }

        // CTA + Skip
        VStack(spacing: DesignSystem.Spacing.sm) {
            PrimaryButton("Continue", ...)
            Button("Skip", ...)
        }

        // Page Indicator
        PageIndicator(currentPage: 1, totalPages: 4)
    }
    .padding(.horizontal, DesignSystem.Spacing.xxl)
    .padding(.vertical, DesignSystem.Spacing.xl)
}
```

#### Accessibility Implementation
- Icon: `.accessibilityHidden(true)` (decorative)
- Headline: `.accessibilityAddTraits(.isHeader)`
- Process steps: Each step is `.accessibilityElement(children: .combine)` with label "Step 1: Answer Questions. Work through..."
- Info note: Default accessibility with info icon hidden
- VoiceOver reads: "Information. Questions are freshly generated each night to prevent memorization"

---

### Screen 3: Recommended Testing Frequency
**Purpose**: Establish optimal usage pattern and prevent over-testing

#### Content

**Icon**
- SF Symbol: `calendar.badge.clock`
- Size: 64pt (DesignSystem.IconSize.huge)
- Color: ColorPalette.statPurple
- Animation: Fade-in with subtle bounce (respects reduce motion)

**Headline**
- Text: "Test Every 3 Months"
- Style: Typography.displayMedium (42pt bold)
- Color: ColorPalette.textPrimary
- Alignment: Center

**Body Copy**
- Text: "For meaningful insights, we recommend taking AIQ every 3 months. This cadence allows enough time to see genuine changes while maintaining consistent tracking."
- Style: Typography.bodyLarge (17pt regular)
- Color: ColorPalette.textSecondary
- Alignment: Center

**Rationale Cards** (2 cards explaining why)

**Card 1: Avoid Practice Effects**
- Icon: `repeat.circle.fill` (orange)
- Heading: "Minimize Practice Effects"
- Body: "Spacing tests prevents score inflation from memorization or familiarity"
- Background: ColorPalette.backgroundSecondary
- Padding: DesignSystem.Spacing.lg
- Corner Radius: DesignSystem.CornerRadius.md

**Card 2: Track Real Change**
- Icon: `brain.head.profile` (green)
- Heading: "Capture Real Changes"
- Body: "Cognitive capacity shifts over months, not days. Quarterly testing reveals true trends"
- Background: ColorPalette.backgroundSecondary

**Reminder Option**
- Text: "We'll send you a reminder when it's time for your next test"
- Icon: `bell.fill` leading
- Style: Typography.bodyMedium
- Color: ColorPalette.infoText
- Background: ColorPalette.info.opacity(0.1)
- Padding: DesignSystem.Spacing.md
- Corner Radius: DesignSystem.CornerRadius.sm

**CTA Button**
- Text: "Continue"
- Component: PrimaryButton
- Accessibility: "Continue to learn about privacy"

**Skip Option**
- Text: "Skip"
- Style: Text button

**Page Indicator**
- Position: 3 of 4

#### Layout Structure
```swift
ScrollView {
    VStack(spacing: DesignSystem.Spacing.xxxl) {
        // Icon
        Image(systemName: "calendar.badge.clock")

        // Content Group
        VStack(spacing: DesignSystem.Spacing.xl) {
            // Headline
            Text("Test Every 3 Months")

            // Body
            Text("For meaningful insights...")

            // Rationale Cards
            VStack(spacing: DesignSystem.Spacing.md) {
                RationaleCard(icon: "repeat.circle.fill", ...)
                RationaleCard(icon: "brain.head.profile", ...)
            }

            // Reminder Note
            HStack {
                Image(systemName: "bell.fill")
                Text("We'll send you a reminder...")
            }
            .padding()
            .background(...)
        }

        // CTA + Skip
        VStack(spacing: DesignSystem.Spacing.sm) {
            PrimaryButton("Continue", ...)
            Button("Skip", ...)
        }

        // Page Indicator
        PageIndicator(currentPage: 2, totalPages: 4)
    }
    .padding(.horizontal, DesignSystem.Spacing.xxl)
    .padding(.vertical, DesignSystem.Spacing.xl)
}
```

#### Accessibility Implementation
- Icon: `.accessibilityHidden(true)` (decorative)
- Headline: `.accessibilityAddTraits(.isHeader)`
- Rationale cards: Each card is `.accessibilityElement(children: .combine)`
- Reminder note: `.accessibilityLabel("Reminder: We'll send you a reminder when it's time for your next test")`
- Card icons: `.accessibilityHidden(true)` (decorative, meaning in text)

---

### Screen 4: Privacy and Data Security
**Purpose**: Build trust before first test by addressing privacy concerns

#### Content

**Icon**
- SF Symbol: `lock.shield.fill`
- Size: 64pt (DesignSystem.IconSize.huge)
- Color: ColorPalette.successText (green, conveys security)
- Animation: Scale-in with subtle glow effect (respects reduce motion)

**Headline**
- Text: "Your Data is Secure"
- Style: Typography.displayMedium (42pt bold)
- Color: ColorPalette.textPrimary
- Alignment: Center

**Body Copy**
- Text: "Your privacy matters. AIQ uses industry-standard encryption and follows best practices to protect your cognitive assessment data."
- Style: Typography.bodyLarge (17pt regular)
- Color: ColorPalette.textSecondary
- Alignment: Center

**Privacy Features** (4 checkmark items)

1. **End-to-End Encryption**
   - Icon: `checkmark.shield.fill` (green)
   - Text: "All test data encrypted in transit and at rest"

2. **No Data Sharing**
   - Icon: `checkmark.shield.fill` (green)
   - Text: "We never sell or share your data with third parties"

3. **Secure Storage**
   - Icon: `checkmark.shield.fill` (green)
   - Text: "Stored on secure, certified cloud infrastructure"

4. **You Own Your Data**
   - Icon: `checkmark.shield.fill` (green)
   - Text: "Request data export or deletion anytime in Settings"

Each item:
- Icon: 20pt checkmark.shield.fill, ColorPalette.successText
- Text: Typography.bodyMedium (16pt)
- Layout: HStack with icon leading, alignment: .top

**Privacy Policy Link**
- Text: "View Privacy Policy"
- Style: Button with `.plain` style
- Color: ColorPalette.infoText
- Icon: `arrow.up.right` trailing (external link indicator)
- Accessibility: "View Privacy Policy in Safari"

**CTA Button**
- Text: "Get Started"
- Component: PrimaryButton
- Accessibility: "Complete onboarding and go to dashboard"
- Note: This is the final screen, so no skip option

**Page Indicator**
- Position: 4 of 4

#### Layout Structure
```swift
ScrollView {
    VStack(spacing: DesignSystem.Spacing.xxxl) {
        // Icon
        Image(systemName: "lock.shield.fill")

        // Content Group
        VStack(spacing: DesignSystem.Spacing.xl) {
            // Headline
            Text("Your Data is Secure")

            // Body
            Text("Your privacy matters...")

            // Privacy Features
            VStack(alignment: .leading, spacing: DesignSystem.Spacing.md) {
                PrivacyFeatureRow(icon: "checkmark.shield.fill", ...)
                PrivacyFeatureRow(...)
                PrivacyFeatureRow(...)
                PrivacyFeatureRow(...)
            }

            // Privacy Policy Link
            Button(action: openPrivacyPolicy) {
                HStack {
                    Text("View Privacy Policy")
                    Image(systemName: "arrow.up.right")
                }
            }
        }

        // CTA (no skip on final screen)
        PrimaryButton("Get Started", action: completeOnboarding)

        // Page Indicator
        PageIndicator(currentPage: 3, totalPages: 4)
    }
    .padding(.horizontal, DesignSystem.Spacing.xxl)
    .padding(.vertical, DesignSystem.Spacing.xl)
}
```

#### Accessibility Implementation
- Icon: `.accessibilityHidden(true)` (decorative)
- Headline: `.accessibilityAddTraits(.isHeader)`
- Privacy features: Each row is `.accessibilityElement(children: .combine)` reading "Checkmark. End-to-End Encryption. All test data encrypted..."
- Privacy policy link: `.accessibilityHint("Opens privacy policy in Safari")`
- Get Started button: `.accessibilityHint("Complete onboarding and return to dashboard")`

---

## Implementation Notes

### Technical Considerations

#### SwiftUI Implementation

**OnboardingContainerView**
```swift
struct OnboardingContainerView: View {
    @StateObject private var viewModel = OnboardingViewModel()
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @Environment(\.dismiss) var dismiss

    var body: some View {
        TabView(selection: $viewModel.currentPage) {
            OnboardingPage1View(viewModel: viewModel).tag(0)
            OnboardingPage2View(viewModel: viewModel).tag(1)
            OnboardingPage3View(viewModel: viewModel).tag(2)
            OnboardingPage4View(viewModel: viewModel).tag(3)
        }
        .tabViewStyle(.page(indexDisplayMode: .always))
        .indexViewStyle(.page(backgroundDisplayMode: .always))
        .onAppear {
            setupPageControlAppearance()
        }
    }

    private func setupPageControlAppearance() {
        UIPageControl.appearance().currentPageIndicatorTintColor = UIColor(ColorPalette.primary)
        UIPageControl.appearance().pageIndicatorTintColor = UIColor(ColorPalette.textTertiary)
    }
}
```

**OnboardingViewModel**
```swift
class OnboardingViewModel: ObservableObject {
    @Published var currentPage: Int = 0
    @AppStorage("hasCompletedOnboarding") private var hasCompletedOnboarding = false

    func nextPage() {
        withAnimation {
            currentPage += 1
        }
    }

    func skipOnboarding() {
        completeOnboarding()
    }

    func completeOnboarding() {
        hasCompletedOnboarding = true
        // Trigger analytics event
        // Dismiss onboarding
    }
}
```

#### State Management
- Use `@AppStorage("hasCompletedOnboarding")` to persist completion
- Store in UserDefaults for simple boolean flag
- Check on app launch to determine whether to show onboarding

#### Navigation Flow
```
WelcomeView (after login/registration)
    → OnboardingContainerView (if !hasCompletedOnboarding)
        → DashboardView
```

#### Animations
```swift
// Respect reduce motion preference
if reduceMotion {
    // No animation
} else {
    withAnimation(DesignSystem.Animation.smooth) {
        // Animated transition
    }
}
```

#### Haptic Feedback
```swift
// On page change
let generator = UIImpactFeedbackGenerator(style: .light)
generator.impactOccurred()

// On button tap
let generator = UIImpactFeedbackGenerator(style: .medium)
generator.impactOccurred()
```

### Analytics Events

Track onboarding funnel:
```swift
// OnboardingStarted
analytics.track("onboarding_started")

// OnboardingPageViewed
analytics.track("onboarding_page_viewed", properties: [
    "page_number": pageNumber,
    "page_name": pageName
])

// OnboardingCompleted
analytics.track("onboarding_completed", properties: [
    "completion_method": "finished" // or "skipped"
])

// OnboardingSkipped
analytics.track("onboarding_skipped", properties: [
    "skipped_at_page": pageNumber
])
```

### Performance Considerations
- Lazy load each page to optimize memory
- Pre-render next page for smooth swipe transitions
- Use lightweight SF Symbols instead of custom graphics
- Minimize animation complexity on lower-end devices

### Testing Checklist
- [ ] Test with VoiceOver enabled (full flow)
- [ ] Test with all Dynamic Type sizes (especially largest)
- [ ] Test with Reduce Motion enabled
- [ ] Test with different language settings (RTL: Arabic, Hebrew)
- [ ] Test skip flow and completion flow
- [ ] Test app backgrounding during onboarding
- [ ] Test on various device sizes (SE, standard, Plus/Max, iPad)
- [ ] Verify analytics events fire correctly

---

## Recommendations

### Critical
1. **Implement VoiceOver Testing**: Conduct full accessibility audit with screen reader before release
2. **User Testing**: Test onboarding with 5-10 first-time users to validate clarity
3. **Analytics Instrumentation**: Track completion rates and identify drop-off points
4. **String Localization**: Prepare all strings for localization from day one

### Major
1. **Optional Video Tutorial**: Consider adding short video demo on Screen 2 (How Tests Work)
2. **Progressive Profiling**: Capture optional user context (age range, education) after onboarding
3. **Re-onboarding**: Allow users to replay onboarding from Settings → About
4. **A/B Testing**: Test different copy variations to optimize completion rates

### Minor
1. **Animated Illustrations**: Consider custom Lottie animations for each screen icon
2. **Personalization**: Add user's name to final screen if available from registration
3. **Gamification Teaser**: Show achievement badges or streak features on Screen 1
4. **Social Proof**: Add testimonials or user count to build credibility

### Enhancement
1. **Interactive Demo**: Allow users to try a sample question on Screen 2
2. **Notification Permission**: Prompt for notification permission on Screen 3 (testing cadence)
3. **Contextual Help**: Add "Learn More" links that expand with additional details
4. **Accessibility Shortcuts**: Add VoiceOver-specific navigation hints

---

## File Structure for Implementation

```
ios/AIQ/Views/Onboarding/
├── OnboardingContainerView.swift      # Main container with TabView
├── OnboardingViewModel.swift          # State management
├── Pages/
│   ├── OnboardingPage1View.swift     # Value Proposition
│   ├── OnboardingPage2View.swift     # How Tests Work
│   ├── OnboardingPage3View.swift     # Testing Frequency
│   └── OnboardingPage4View.swift     # Privacy & Security
└── Components/
    ├── FeatureHighlightRow.swift     # Reusable feature highlight
    ├── ProcessStepRow.swift          # Numbered step component
    ├── RationaleCard.swift           # Card with icon + explanation
    ├── PrivacyFeatureRow.swift       # Checkmark + privacy feature
    └── PageIndicator.swift           # Custom page indicator (if needed)
```

---

## Visual Design Reference

### Color Usage Summary
- **Primary actions**: ColorPalette.primary (blue)
- **Gradients**: ColorPalette.scoreGradient (blue to purple) for hero icons
- **Success/Security**: ColorPalette.successText (green) for privacy features
- **Informational**: ColorPalette.infoText (blue) for notes and links
- **Backgrounds**: ColorPalette.background, backgroundSecondary
- **Text**: ColorPalette.textPrimary (headings), textSecondary (body), textTertiary (captions)

### Typography Hierarchy
- **Display**: Typography.displayMedium (42pt) - Page headlines
- **Headings**: Typography.h2 (22pt) - Card titles
- **Body**: Typography.bodyLarge (17pt) - Main copy
- **Labels**: Typography.bodyMedium (16pt) - Feature descriptions
- **Captions**: Typography.captionMedium (12pt) - Fine print, notes

### Spacing Rhythm
- **Section gaps**: DesignSystem.Spacing.xxxl (32pt)
- **Content groups**: DesignSystem.Spacing.xl (20pt)
- **Related items**: DesignSystem.Spacing.lg (16pt)
- **List items**: DesignSystem.Spacing.md (12pt)
- **Tight spacing**: DesignSystem.Spacing.sm (8pt)

### Component Styles
- **Cards**: backgroundSecondary + CornerRadius.md (12pt) + Shadow.sm
- **Buttons**: PrimaryButton component (consistent with rest of app)
- **Icons**: SF Symbols at 64pt (hero), 32pt (steps), 24pt (features), 20pt (checkmarks)

---

## Conclusion

This onboarding flow balances **scientific credibility** with **approachability**, setting clear expectations while building trust. By following iOS design guidelines, maintaining WCAG AA accessibility, and using the existing AIQ design system, this specification can be directly implemented by the iOS engineering team.

The flow is:
- **Concise**: 4 screens, 2-3 minutes to complete
- **Skippable**: Reduces friction for eager users
- **Accessible**: Full VoiceOver support, Dynamic Type, reduce motion
- **Localization-ready**: Flexible layouts, externalized strings
- **Brand-consistent**: Uses existing design tokens and patterns

## Related Files
- `/ios/AIQ/Utilities/Design/ColorPalette.swift`
- `/ios/AIQ/Utilities/Design/Typography.swift`
- `/ios/AIQ/Utilities/Design/DesignSystem.swift`
- `/ios/AIQ/Views/Common/PrimaryButton.swift`
- `/ios/AIQ/Views/Auth/WelcomeView.swift`
