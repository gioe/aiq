# BTS-39: Reduce Motion Implementation Plan

## Overview

Implement Reduce Motion accessibility support across all 68 animations in the AIQ iOS app to ensure users with motion sensitivity can use the app without experiencing disorientation, vertigo, or nausea.

## Strategic Context

### Problem Statement

The AIQ iOS app currently has **zero Reduce Motion support** across 68 animations in 17 files. Users who enable Reduce Motion in iOS Settings (25-35% of the population with varying degrees of motion sensitivity) experience all animations without any ability to disable them. This creates:

- **Physical harm**: Continuous rotation animations cause vertigo and motion sickness
- **Usability barriers**: Users cannot complete tests due to disorienting transitions
- **Legal risk**: ADA compliance concerns for accessibility
- **App Store risk**: May be flagged during accessibility review

**Affected Users:**
- Users with vestibular disorders (vertigo, Ménière's disease)
- Users prone to motion sickness
- Users with migraine triggers
- Elderly users with balance sensitivities
- Users with visual processing disorders

### Success Criteria

- [ ] All CRITICAL animations (3) respect Reduce Motion and do not cause vertigo
- [ ] All HIGH priority animations (24) are simplified or disabled for Reduce Motion users
- [ ] All MEDIUM animations (31) provide fade-only alternatives
- [ ] App functionality is preserved when Reduce Motion is enabled
- [ ] Manual testing confirms no disorienting animations remain
- [ ] SwiftUI Previews added for Reduce Motion testing
- [ ] Coding standards updated with Reduce Motion requirements

**Measurable Outcomes:**
- 68/68 animations respect `accessibilityReduceMotion` environment variable
- Zero motion sickness triggers for users with Reduce Motion enabled
- App Store submission includes Reduce Motion compliance documentation

### Why Now?

1. **App Store Submission Blocker**: Pre-release requirement for accessibility compliance
2. **Audit Complete**: Comprehensive audit (BTS-38) identified all 68 animations and severity levels
3. **User Harm**: Current state causes physical discomfort for 25-35% of potential users
4. **Clear Roadmap**: Severity-based prioritization provides clear implementation path
5. **Technical Simplicity**: SwiftUI provides built-in `accessibilityReduceMotion` support - no custom infrastructure needed

## Technical Approach

### High-Level Architecture

**Implementation Pattern: Environment Variable Checks**

SwiftUI provides the `@Environment(\.accessibilityReduceMotion)` environment variable that automatically reflects the user's iOS Settings preference. We will:

1. Add `@Environment(\.accessibilityReduceMotion) var reduceMotion` to all 17 files with animations
2. Conditionally modify animations based on `reduceMotion` boolean
3. Use 4 implementation patterns based on animation type (see patterns below)

**No new infrastructure required** - this is a pure refactoring effort using existing SwiftUI APIs.

### Key Decisions & Tradeoffs

#### Decision 1: Environment Variable vs Custom Service

**Chosen**: Direct `@Environment(\.accessibilityReduceMotion)` usage in each view
**Alternative**: Create `AnimationService` to centralize Reduce Motion logic
**Rationale**:
- Environment variable is the SwiftUI-native pattern
- Zero coupling between files
- Easy to test with `.environment()` modifier in previews
- No added abstraction complexity
- Follows Apple's design guidelines exactly

**Tradeoff**: Some code duplication across 17 files, but explicit and testable.

#### Decision 2: Severity-Based Sequencing vs Screen Flow

**Chosen**: Implement in severity order (Critical → High → Medium → Low)
**Alternative**: Implement by user flow (Auth → Test → Results)
**Rationale**:
- Harm reduction drives priority (Critical animations cause vertigo)
- Each phase completion delivers measurable user benefit
- Enables phased release if time-constrained
- Aligns with App Store review priorities (loading states, onboarding)

**Tradeoff**: Some screens will be partially fixed before others, but Critical issues are eliminated first.

#### Decision 3: Animation Replacement Strategy

**Critical Animations**: Complete removal (infinite loops, continuous rotation)
**High Animations**: Simplified to crossfade or instant (spring physics, multi-axis movement)
**Medium Animations**: Opacity-only transitions (remove offset/scale)
**Low Animations**: Optional - can keep simple fades or remove for consistency

**Rationale**: Matches disorientation severity to replacement strategy based on Apple's Motion guidelines.

### Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| **Breaking animations for non-Reduce Motion users** | HIGH | LOW | Use ternary conditionals that preserve original animations when `reduceMotion == false` |
| **Functionality loss when animations removed** | MEDIUM | LOW | All animations are decorative - no functional loss, just visual polish |
| **Incomplete testing across all severity tiers** | MEDIUM | MEDIUM | Create SwiftUI Previews with `.environment(\.accessibilityReduceMotion, true)` for each modified view |
| **Regression after implementation** | MEDIUM | MEDIUM | Update CODING_STANDARDS.md with mandatory Reduce Motion checks for all new animations |
| **Time overrun on Medium/Low priorities** | LOW | MEDIUM | Phased release plan allows shipping Critical+High first if needed |

### Implementation Patterns

#### Pattern 1: Disable Continuous Animations (Critical)

**Use Case**: Infinite loops, continuous rotation, breathing effects
**Example**: LoadingOverlay.swift continuous 360° rotation

```swift
@Environment(\.accessibilityReduceMotion) var reduceMotion

var body: some View {
    Image(systemName: "brain.head.profile")
        .rotationEffect(.degrees(rotationAngle))
        .onAppear {
            if !reduceMotion {
                // Only animate if Reduce Motion is OFF
                withAnimation(
                    Animation.linear(duration: 2.0)
                        .repeatForever(autoreverses: false)
                ) {
                    rotationAngle = 360
                }
            }
            // If Reduce Motion is ON, rotationAngle stays at 0 - static icon
        }
}
```

**Key Points**:
- Check `reduceMotion` in `.onAppear` before starting animation
- When enabled, skip animation block entirely - state stays static
- Icon remains visible but stationary

---

#### Pattern 2: Replace Spring/Physics Animations with Instant (High)

**Use Case**: Spring animations, bounce effects, navigation transitions
**Example**: TestTakingView.swift question navigation

```swift
@Environment(\.accessibilityReduceMotion) var reduceMotion

Button("Next Question") {
    withAnimation(reduceMotion ? nil : .spring(response: 0.3)) {
        viewModel.goToNext()
    }
}
```

**Key Points**:
- Pass `nil` to `withAnimation()` for instant state change
- Functionality preserved - question changes, just without spring bounce
- Ternary keeps code concise

---

#### Pattern 3: Simplify Multi-Effect Transitions to Opacity (Medium)

**Use Case**: Combined slide + scale + opacity entrance animations
**Example**: WelcomeView.swift feature highlights

```swift
@Environment(\.accessibilityReduceMotion) var reduceMotion

VStack {
    Text("Feature")
        .opacity(isAnimating ? 1.0 : 0.0)
        .offset(y: reduceMotion ? 0 : (isAnimating ? 0 : 20))  // Remove slide
        .scaleEffect(reduceMotion ? 1.0 : (isAnimating ? 1.0 : 0.95))  // Remove scale
        .animation(
            reduceMotion ? .linear(duration: 0.2) : DesignSystem.Animation.smooth.delay(0.4),
            value: isAnimating
        )
}
.onAppear {
    if reduceMotion {
        isAnimating = true  // Instant appearance
    } else {
        withAnimation(DesignSystem.Animation.bouncy) {
            isAnimating = true
        }
    }
}
```

**Key Points**:
- Keep opacity transition (simple fade is acceptable)
- Remove offset and scale effects (motion triggers)
- Use short linear fade instead of bouncy/smooth easing
- Instant appearance for Reduce Motion in `.onAppear`

---

#### Pattern 4: Replace Asymmetric Transitions with Crossfade (High)

**Use Case**: Directional slides (left/right, top/bottom) during navigation
**Example**: TestTakingView.swift question card transitions

```swift
@Environment(\.accessibilityReduceMotion) var reduceMotion

content
    .transition(
        reduceMotion ? .opacity : .asymmetric(
            insertion: .move(edge: .trailing).combined(with: .opacity),
            removal: .move(edge: .leading).combined(with: .opacity)
        )
    )
```

**Key Points**:
- Simple `.opacity` crossfade for Reduce Motion
- Preserves directional slide for non-Reduce Motion users
- No functional change - questions still navigate correctly

---

## Implementation Plan

### Phase 1: CRITICAL Fixes (Must Do Before Release)

**Goal**: Eliminate all motion sickness triggers (infinite loops, continuous rotation)
**Duration**: 4 hours
**Success Criteria**: Users with Reduce Motion enabled experience ZERO vertigo-inducing animations

| Task ID | Task | Dependencies | Estimate | Priority | Files |
|---------|------|--------------|----------|----------|-------|
| 1.1 | Fix LoadingOverlay continuous rotation | None | 1h | 🚨 HIGHEST | LoadingOverlay.swift |
| 1.2 | Fix WelcomeView brain icon breathing | None | 30m | 🔴 CRITICAL | WelcomeView.swift |
| 1.3 | Fix PrivacyConsentView hand icon breathing | None | 30m | 🔴 CRITICAL | PrivacyConsentView.swift |
| 1.4 | Manual testing - Critical animations | 1.1, 1.2, 1.3 | 1h | 🔴 CRITICAL | N/A |
| 1.5 | Add SwiftUI Previews for Reduce Motion | 1.1, 1.2, 1.3 | 1h | 🔴 CRITICAL | LoadingOverlay, WelcomeView, PrivacyConsentView |

**Detailed Task Breakdown:**

**Task 1.1: LoadingOverlay.swift - Disable Continuous Rotation**
- Add `@Environment(\.accessibilityReduceMotion) var reduceMotion`
- Wrap rotation animation in `if !reduceMotion` check (line 61-66)
- Wrap entrance animations in conditional (line 56-58)
- Remove pulsing scale when Reduce Motion enabled (line 27)
- Test: Verify static brain icon appears when Reduce Motion ON

**Task 1.2: WelcomeView.swift - Disable Brain Breathing**
- Add `@Environment(\.accessibilityReduceMotion) var reduceMotion`
- Wrap `.repeatForever()` animation in conditional (line 37-39)
- Test: Brain icon should be static at scale 1.0 when Reduce Motion ON

**Task 1.3: PrivacyConsentView.swift - Disable Hand Breathing**
- Add `@Environment(\.accessibilityReduceMotion) var reduceMotion`
- Disable infinite pulse animation (similar pattern to WelcomeView)
- Test: Hand icon should be static when Reduce Motion ON

**Task 1.4: Manual Testing Protocol**
1. Enable Reduce Motion: Settings > Accessibility > Motion > Reduce Motion (ON)
2. Test LoadingOverlay: Trigger sign-in loading state - verify NO rotation
3. Test WelcomeView: Launch app - verify brain icon is static
4. Test PrivacyConsentView: First launch - verify hand icon is static
5. Disable Reduce Motion and verify all animations still work normally

**Task 1.5: Add SwiftUI Previews**
```swift
#Preview("Reduce Motion Enabled") {
    LoadingOverlay(message: "Loading...")
        .environment(\.accessibilityReduceMotion, true)
}

#Preview("Reduce Motion Disabled") {
    LoadingOverlay(message: "Loading...")
        .environment(\.accessibilityReduceMotion, false)
}
```

---

### Phase 2: HIGH Priority Fixes (Should Do Before Release)

**Goal**: Simplify all spring physics and multi-axis movements that cause significant disorientation
**Duration**: 6 hours
**Success Criteria**: Test-taking flow is smooth and non-disorienting for Reduce Motion users

| Task ID | Task | Dependencies | Estimate | Priority | Files |
|---------|------|--------------|----------|----------|-------|
| 2.1 | Fix TestTakingView navigation springs | Phase 1 | 2h | 🟠 HIGH | TestTakingView.swift |
| 2.2 | Fix TestTakingView question transitions | Phase 1 | 1h | 🟠 HIGH | TestTakingView.swift |
| 2.3 | Fix TestTakingView completion animation | Phase 1 | 30m | 🟠 HIGH | TestTakingView.swift |
| 2.4 | Fix staggered entrance animations | Phase 1 | 2h | 🟠 HIGH | WelcomeView, RegistrationView, PrivacyConsentView, TestResultsView |
| 2.5 | Manual testing - Test-taking flow | 2.1, 2.2, 2.3 | 30m | 🟠 HIGH | N/A |

**Detailed Task Breakdown:**

**Task 2.1: TestTakingView Navigation Springs**
Files: `/Users/mattgioe/aiq/ios/AIQ/Views/Test/TestTakingView.swift`

Locations:
- Line 263-266: Question grid navigation spring
- Line 317-320: Previous button spring
- Line 336-339: Next button spring

Pattern:
```swift
withAnimation(reduceMotion ? nil : .spring(response: 0.3)) {
    viewModel.goToQuestion(at: index)
}
```

**Task 2.2: TestTakingView Question Transitions**
Location: Line 282-288 - Asymmetric slide transitions

Replace with:
```swift
.transition(
    reduceMotion ? .opacity : .asymmetric(
        insertion: .move(edge: .trailing).combined(with: .opacity),
        removal: .move(edge: .leading).combined(with: .opacity)
    )
)
```

**Task 2.3: TestTakingView Completion Animation**
Location: Line 383-385 - 180° rotation + scale + opacity

Replace with:
```swift
Image(systemName: "checkmark.circle.fill")
    .scaleEffect(reduceMotion ? 1.0 : (showCompletionAnimation ? 1.0 : 0.5))
    .opacity(showCompletionAnimation ? 1.0 : 0.0)
    .rotationEffect(.degrees(reduceMotion ? 0 : (showCompletionAnimation ? 0 : -180)))
```

**Task 2.4: Fix Staggered Entrance Animations**
Files: WelcomeView, RegistrationView, PrivacyConsentView, TestResultsView

Pattern - remove offset and scale, keep opacity only:
```swift
.opacity(isAnimating ? 1.0 : 0.0)
.offset(y: reduceMotion ? 0 : (isAnimating ? 0 : 20))
.scaleEffect(reduceMotion ? 1.0 : (isAnimating ? 1.0 : 0.95))
.animation(
    reduceMotion ? .linear(duration: 0.2) : DesignSystem.Animation.smooth.delay(0.4),
    value: isAnimating
)
```

In `.onAppear`:
```swift
if reduceMotion {
    isAnimating = true  // Instant
} else {
    withAnimation(DesignSystem.Animation.bouncy) {
        isAnimating = true
    }
}
```

**Task 2.5: Manual Testing - Test Taking Flow**
1. Enable Reduce Motion
2. Start a test and navigate through 5+ questions
3. Verify: No horizontal sliding, instant question changes
4. Complete test and verify completion screen has no rotation
5. Verify all navigation buttons work (Previous, Next, Grid)

---

### Phase 3: MEDIUM Priority Fixes (Recommended)

**Goal**: Simplify all slide transitions and combined effects to opacity-only
**Duration**: 4 hours
**Success Criteria**: All screen transitions are simple crossfades when Reduce Motion enabled

| Task ID | Task | Dependencies | Estimate | Priority | Files |
|---------|------|--------------|----------|----------|-------|
| 3.1 | Fix test progress and feedback animations | Phase 2 | 1.5h | 🟡 MEDIUM | TestProgressView, TimeWarningBanner, AnswerInputView |
| 3.2 | Fix results screen animations | Phase 2 | 1h | 🟡 MEDIUM | TestResultsView, DomainScoresView, TestDetailView |
| 3.3 | Fix dashboard and common components | Phase 2 | 1h | 🟡 MEDIUM | DashboardView, InProgressTestCard, NetworkStatusBanner, RootView |
| 3.4 | Manual testing - All screens | 3.1, 3.2, 3.3 | 30m | 🟡 MEDIUM | N/A |

**Detailed Task Breakdown:**

**Task 3.1: Test Progress and Feedback Animations**

Files:
- TestProgressView.swift (5 animations) - Progress bar spring animations
- TimeWarningBanner.swift (2 animations) - Slide-in spring from top
- AnswerInputView.swift (1 animation) - Selection spring

Pattern - Replace springs with linear or nil:
```swift
withAnimation(reduceMotion ? nil : .spring(response: 0.3)) {
    // State change
}
```

Transitions - Replace `.move(edge:)` with `.opacity`:
```swift
.transition(reduceMotion ? .opacity : .move(edge: .top).combined(with: .opacity))
```

**Task 3.2: Results Screen Animations**

Files:
- TestResultsView.swift (5 animations) - Staggered entrance
- DomainScoresView.swift (2 animations) - Score bars entrance
- TestDetailView.swift (4 animations) - Detail card entrance

Apply Pattern 3 (simplify to opacity-only) from Technical Approach section.

**Task 3.3: Dashboard and Common Components**

Files:
- DashboardView.swift (2 animations) - View transitions
- InProgressTestCard.swift (1 animation) - Card entrance
- NetworkStatusBanner.swift (1 animation) - Banner slide-in
- RootView.swift (4 animations) - Root-level transitions

Apply appropriate patterns based on animation type (transitions use Pattern 4, entrances use Pattern 3).

**Task 3.4: Manual Testing - All Screens**
1. Enable Reduce Motion
2. Navigate through: Auth → Dashboard → Start Test → Complete Test → Results → History → Settings
3. Verify all transitions are simple fades
4. Verify all functionality works (buttons, navigation, data display)
5. Compare with Reduce Motion disabled to ensure original animations preserved

---

### Phase 4: LOW Priority Fixes (Optional)

**Goal**: Address simple opacity fades and subtle animations for consistency
**Duration**: 2 hours
**Success Criteria**: 100% animation coverage, all 68 animations respect Reduce Motion

| Task ID | Task | Dependencies | Estimate | Priority | Files |
|---------|------|--------------|----------|----------|-------|
| 4.1 | Fix low-severity animations | Phase 3 | 1h | 🟢 LOW | QuestionNavigationGrid, TestTimerView, InProgressTestCard |
| 4.2 | Final QA pass - All 68 animations | 4.1 | 1h | 🟢 LOW | N/A |

**Detailed Task Breakdown:**

**Task 4.1: Low-Severity Animations**

Files:
- QuestionNavigationGrid.swift (1 animation) - Simple fade on selection
- TestTimerView.swift (1 animation) - Color transition
- InProgressTestCard.swift (1 animation if not covered in 3.3) - Fade entrance

Decision per animation:
- **Keep**: If it's a simple opacity fade (<0.2s duration), can optionally keep
- **Simplify**: Remove any lingering offset/scale effects
- **Disable**: For complete consistency, disable all animations when Reduce Motion ON

**Task 4.2: Final QA Pass**

Checklist:
- [ ] All 17 files have `@Environment(\.accessibilityReduceMotion)` declared
- [ ] All 68 animations identified in audit are addressed
- [ ] Manual testing with Reduce Motion ON: No disorienting animations
- [ ] Manual testing with Reduce Motion OFF: All animations work as before
- [ ] SwiftUI Previews added for critical views
- [ ] No functionality broken (buttons, navigation, data all work)

---

### Phase 5: Documentation and Standards (Required)

**Goal**: Prevent regression and establish Reduce Motion as a coding standard
**Duration**: 2 hours
**Success Criteria**: Future animations automatically respect Reduce Motion

| Task ID | Task | Dependencies | Estimate | Priority | Files |
|---------|------|--------------|----------|----------|-------|
| 5.1 | Update CODING_STANDARDS.md | Phase 2 | 1h | 🔴 REQUIRED | ios/docs/CODING_STANDARDS.md |
| 5.2 | Update REDUCE_MOTION_AUDIT.md with implementation notes | Phase 4 | 30m | 🟡 MEDIUM | ios/docs/REDUCE_MOTION_AUDIT.md |
| 5.3 | Create REDUCE_MOTION_IMPLEMENTATION.md summary | Phase 4 | 30m | 🟡 MEDIUM | ios/docs/REDUCE_MOTION_IMPLEMENTATION.md |

**Detailed Task Breakdown:**

**Task 5.1: Update CODING_STANDARDS.md**

Add new section to Accessibility chapter (after Dynamic Type):

```markdown
### Reduce Motion

All animations MUST respect the `accessibilityReduceMotion` environment variable to support users with motion sensitivity.

**Required for ALL animations:**

```swift
@Environment(\.accessibilityReduceMotion) var reduceMotion

// Pattern 1: Disable continuous animations (infinite loops, rotation)
.onAppear {
    if !reduceMotion {
        withAnimation(.linear(duration: 2.0).repeatForever()) {
            rotationAngle = 360
        }
    }
}

// Pattern 2: Replace spring/physics with instant
withAnimation(reduceMotion ? nil : .spring(response: 0.3)) {
    viewModel.updateState()
}

// Pattern 3: Simplify to opacity-only
.opacity(isAnimating ? 1.0 : 0.0)
.offset(y: reduceMotion ? 0 : (isAnimating ? 0 : 20))

// Pattern 4: Replace directional transitions with crossfade
.transition(reduceMotion ? .opacity : .move(edge: .trailing))
```

**Animation Classification:**
- **CRITICAL** (infinite loops, continuous rotation): Disable completely
- **HIGH** (spring physics, multi-axis movement): Replace with instant or crossfade
- **MEDIUM** (combined effects, slides): Simplify to opacity-only
- **LOW** (simple fades): Optional - can keep or disable for consistency

**Testing:**
- Add SwiftUI Previews with `.environment(\.accessibilityReduceMotion, true)`
- Manually test with Settings > Accessibility > Motion > Reduce Motion enabled
- Verify functionality preserved when animations disabled
```

**Task 5.2: Update REDUCE_MOTION_AUDIT.md**

Add "Implementation Summary" section documenting:
- Date implementation completed
- Final animation count addressed (68/68)
- Patterns used for each severity tier
- Testing results

**Task 5.3: Create REDUCE_MOTION_IMPLEMENTATION.md**

Summary document with:
- Before/after comparison for each file
- Code snippets showing key changes
- Testing methodology used
- Lessons learned for future accessibility work

---

## Open Questions

### Pre-Implementation Questions

1. **Should we create a `DesignSystem.Animation.reduceMotion()` helper?**
   - Pro: Reduces boilerplate in views
   - Con: Adds abstraction, less explicit
   - **Recommendation**: Start with explicit checks, refactor if pattern emerges post-implementation

2. **Should LOW priority animations be kept or removed for consistency?**
   - Simple opacity fades are generally acceptable even for Reduce Motion users
   - **Recommendation**: Phase 4 decision - evaluate during implementation based on user testing feedback

3. **Should we add UI automation tests for Reduce Motion?**
   - Would catch regressions automatically
   - Requires Xcode UI Test setup
   - **Recommendation**: Future enhancement - manual testing sufficient for MVP

### Post-Implementation Questions

4. **Should we add a developer mode toggle for testing Reduce Motion without changing device settings?**
   - Would speed up testing during development
   - **Recommendation**: Future enhancement if team velocity is impacted by manual testing

5. **Should we update App Store screenshots to show Reduce Motion support?**
   - Demonstrates accessibility commitment
   - May attract users with motion sensitivity
   - **Recommendation**: Marketing decision - consult App Store guidelines

---

## Appendix A: Testing Protocol

### Manual Testing Checklist

**Setup:**
1. Open Simulator: iPhone 16 Pro, iOS 18.3.1
2. Enable Reduce Motion: Settings > Accessibility > Motion > Reduce Motion (ON)
3. Rebuild app in Debug configuration
4. Launch AIQ app

**Test Scenarios:**

#### Phase 1 Testing (Critical Animations)
- [ ] **LoadingOverlay**: Trigger sign-in → Verify NO rotation, static brain icon
- [ ] **WelcomeView**: Launch app → Verify brain icon is static (no breathing)
- [ ] **PrivacyConsentView**: First launch → Verify hand icon is static

#### Phase 2 Testing (High Priority)
- [ ] **Test Navigation**: Navigate through 10 questions → Verify instant transitions, no sliding
- [ ] **Test Completion**: Complete test → Verify no rotation on checkmark
- [ ] **Entrance Animations**: Visit WelcomeView, RegistrationView, PrivacyConsentView → Verify instant appearance

#### Phase 3 Testing (Medium Priority)
- [ ] **Progress Indicators**: Watch progress bar during test → Verify smooth updates, no bounce
- [ ] **Banners**: Trigger time warning → Verify instant appearance (no slide from top)
- [ ] **Results Screens**: View test results → Verify instant display, no staggered entrance

#### Phase 4 Testing (Low Priority)
- [ ] **All Screens**: Navigate entire app → Verify no lingering animations
- [ ] **Edge Cases**: Rapid navigation, background/foreground → No animation artifacts

**Regression Testing (Reduce Motion OFF):**
- [ ] Disable Reduce Motion in Settings
- [ ] Relaunch app
- [ ] Verify all original animations still work (rotation, springs, slides, fades)

---

## Appendix B: SwiftUI Preview Template

Add these previews to each modified view for easy testing:

```swift
#if DEBUG
#Preview("Default Animations") {
    YourView()
        .environment(\.accessibilityReduceMotion, false)
}

#Preview("Reduce Motion Enabled") {
    YourView()
        .environment(\.accessibilityReduceMotion, true)
}
#endif
```

---

## Appendix C: File-by-File Severity Reference

| File | Animations | Highest Severity | Phase |
|------|-----------|------------------|-------|
| LoadingOverlay.swift | 5 | 🔴 CRITICAL | Phase 1 |
| WelcomeView.swift | 7 | 🔴 CRITICAL | Phase 1 + 2 |
| PrivacyConsentView.swift | 6 | 🔴 CRITICAL | Phase 1 + 2 |
| RegistrationView.swift | 7 | 🟠 HIGH | Phase 2 |
| TestTakingView.swift | 8 | 🟠 HIGH | Phase 2 |
| TestResultsView.swift | 5 | 🟡 MEDIUM | Phase 3 |
| DomainScoresView.swift | 2 | 🟡 MEDIUM | Phase 3 |
| TestDetailView.swift | 4 | 🟡 MEDIUM | Phase 3 |
| TestProgressView.swift | 5 | 🟡 MEDIUM | Phase 3 |
| TimeWarningBanner.swift | 2 | 🟡 MEDIUM | Phase 3 |
| AnswerInputView.swift | 1 | 🟡 MEDIUM | Phase 3 |
| DashboardView.swift | 2 | 🟡 MEDIUM | Phase 3 |
| InProgressTestCard.swift | 1 | 🟢 LOW | Phase 4 |
| NetworkStatusBanner.swift | 1 | 🟡 MEDIUM | Phase 3 |
| RootView.swift | 4 | 🟡 MEDIUM | Phase 3 |
| QuestionNavigationGrid.swift | 1 | 🟢 LOW | Phase 4 |
| TestTimerView.swift | 1 | 🟢 LOW | Phase 4 |

---

## Timeline and Effort Estimates

### Minimum Viable (CRITICAL Only)
**Duration**: 4 hours
**Deliverable**: Eliminate motion sickness triggers
**Risk**: App still has disorienting animations in test-taking flow

### Recommended (CRITICAL + HIGH)
**Duration**: 10 hours
**Deliverable**: App is fully usable for Reduce Motion users
**Risk**: Some polish animations remain (results screens, dashboards)

### Complete (All Phases)
**Duration**: 16 hours
**Deliverable**: 100% Reduce Motion support, updated documentation
**Risk**: None - full accessibility compliance

### Phased Release Schedule

**Week 1**: Phase 1 (Critical) - 4 hours
**Week 2**: Phase 2 (High) - 6 hours
**Week 3**: Phase 3 (Medium) + Phase 5 (Documentation) - 6 hours
**Week 4**: Phase 4 (Low) + Final QA - 3 hours

**Total**: 19 hours over 4 weeks (includes testing and documentation)

---

## Success Metrics

### Implementation Metrics
- [ ] 68/68 animations respect `accessibilityReduceMotion`
- [ ] 17/17 files have environment variable declared
- [ ] 0 Critical animations remain when Reduce Motion enabled
- [ ] 0 High priority animations remain when Reduce Motion enabled
- [ ] SwiftUI Previews added for 3+ critical views

### Quality Metrics
- [ ] Manual testing completed for all phases
- [ ] Zero functional regressions (all features work with Reduce Motion ON/OFF)
- [ ] CODING_STANDARDS.md updated with Reduce Motion requirements
- [ ] Implementation documentation complete

### User Impact Metrics (Post-Release)
- Reduced support tickets related to motion discomfort
- Positive accessibility reviews on App Store
- No App Store rejection due to accessibility concerns

---

## Related Documentation

- **Audit Report**: [ios/docs/REDUCE_MOTION_AUDIT.md](/Users/mattgioe/aiq/ios/docs/REDUCE_MOTION_AUDIT.md)
- **Audit Plan**: [docs/plans/BTS-38-reduce-motion-audit-plan.md](/Users/mattgioe/aiq/docs/plans/BTS-38-reduce-motion-audit-plan.md)
- **iOS Coding Standards**: [ios/docs/CODING_STANDARDS.md](/Users/mattgioe/aiq/ios/docs/CODING_STANDARDS.md)
- **iOS Architecture**: [ios/docs/ARCHITECTURE.md](/Users/mattgioe/aiq/ios/docs/ARCHITECTURE.md)
- **Apple Reduce Motion Guidelines**: https://developer.apple.com/documentation/swiftui/environmentvalues/accessibilityreducemotion

---

**End of Plan**
