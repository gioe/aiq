# BTS-38: Reduce Motion Support Audit & Testing Plan

**Ticket:** BTS-38
**Priority:** CRITICAL
**Created:** January 1, 2026
**Owner:** ios-engineer agent

---

## Overview

This plan outlines the comprehensive audit and testing approach for evaluating Reduce Motion accessibility support in the AIQ iOS app. This is a testing and documentation task, NOT an implementation task. The goal is to identify which animations respect (or fail to respect) the Reduce Motion setting and provide recommendations for each.

---

## Strategic Context

### Problem Statement

Users with motion sensitivity, vestibular disorders, or those prone to motion sickness need the ability to disable or simplify animations. iOS provides the "Reduce Motion" accessibility setting specifically for this purpose. Apps that fail to respect this setting can cause:

- Vertigo and dizziness
- Nausea and physical discomfort
- Difficulty focusing on content
- Cognitive overload

### Success Criteria

1. All 15 files containing animations have been tested with Reduce Motion enabled
2. Disorienting or problematic animations are identified and documented
3. A comprehensive test report is created documenting all animations
4. Specific recommendations are provided for each animation
5. Report follows the format established by previous accessibility audits (VOICEOVER_AUDIT.md, DYNAMIC_TYPE_AUDIT.md)

### Why Now?

- This is part of the iOS Codebase Gaps initiative (BTS-26 to BTS-45)
- Reduce Motion support is an App Store accessibility requirement
- Motion sensitivity affects approximately 25-35% of the population to varying degrees
- This audit must be completed before implementation work (future ticket)

---

## Technical Approach

### High-Level Architecture

The audit will examine animations across three layers:
1. **View Layer Animations**: SwiftUI `.animation()` and `withAnimation()` calls
2. **Transition Animations**: `.transition()` modifiers
3. **Custom Animations**: Rotation, scaling, opacity, offset animations

### Key Decisions & Tradeoffs

**Decision 1: Manual Testing vs. Automated**
- **Choice**: Manual testing with simulator
- **Rationale**: Animation perception (especially "disorienting" animations) requires human judgment
- **Tradeoff**: More time-consuming but more accurate

**Decision 2: Audit First, Implement Later**
- **Choice**: Separate audit ticket from implementation
- **Rationale**: Understanding scope before committing to timeline
- **Tradeoff**: Two-phase approach takes longer but reduces risk

**Decision 3: Use Simulator vs. Physical Device**
- **Choice**: Simulator for consistency and screenshot capture
- **Rationale**: Easier to document, consistent environment
- **Tradeoff**: Some animations may behave differently on device

### Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Missing animations in code search | Use multiple search patterns (`.animation`, `withAnimation`, `.transition`) |
| Subjective determination of "disorienting" | Use established criteria (duration, intensity, type) |
| Animation behavior differs in production | Test both Debug and Release builds |
| Environmental state affects animations | Test in fresh simulator with known state |

---

## Implementation Plan

### Phase 1: Environment Setup & Code Discovery
**Goal**: Prepare testing environment and catalog all animations
**Duration**: 30 minutes

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 1.1 | Boot simulator with known device (iPhone 16 Pro) | None | 5 min | Use consistent device for all tests |
| 1.2 | Enable Reduce Motion in Settings > Accessibility > Motion | 1.1 | 5 min | Document setting state with screenshot |
| 1.3 | Grep codebase for `.animation(` and `withAnimation` | None | 5 min | Catalog all animation usage locations |
| 1.4 | Grep codebase for `.transition(` | None | 5 min | Catalog all transition usage locations |
| 1.5 | Create animation inventory spreadsheet | 1.3, 1.4 | 15 min | Track: file, line, type, description, tested, result |

### Phase 2: Animation Analysis & Categorization
**Goal**: Understand each animation's purpose and characteristics
**Duration**: 1 hour

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 2.1 | Analyze LoadingOverlay.swift animations | 1.5 | 5 min | Rotation + scaling + opacity |
| 2.2 | Analyze TimeWarningBanner.swift animations | 1.5 | 5 min | Spring animation + slide-in |
| 2.3 | Analyze TestTakingView.swift animations | 1.5 | 10 min | Multiple transitions and springs |
| 2.4 | Analyze QuestionNavigationGrid.swift animations | 1.5 | 5 min | Grid animation |
| 2.5 | Analyze WelcomeView.swift animations | 1.5 | 5 min | Entrance animations |
| 2.6 | Analyze RegistrationView.swift animations | 1.5 | 5 min | Form animations |
| 2.7 | Analyze DomainScoresView.swift animations | 1.5 | 5 min | Score reveal animations |
| 2.8 | Analyze TestTimerView.swift animations | 1.5 | 5 min | Timer animations |
| 2.9 | Analyze TestProgressView.swift animations | 1.5 | 5 min | Progress bar animations |
| 2.10 | Analyze PrivacyConsentView.swift animations | 1.5 | 5 min | Consent screen animations |
| 2.11 | Analyze AnswerInputView.swift animations | 1.5 | 5 min | Input animations |
| 2.12 | Analyze RootView.swift animations | 1.5 | 5 min | Navigation animations |
| 2.13 | Analyze TestResultsView.swift animations | 1.5 | 5 min | Results reveal animations |
| 2.14 | Analyze DashboardView.swift animations | 1.5 | 5 min | Dashboard transitions |
| 2.15 | Analyze TestDetailView.swift animations | 1.5 | 5 min | Detail view animations |

### Phase 3: Manual Testing - Reduce Motion Enabled
**Goal**: Test each animation with Reduce Motion enabled
**Duration**: 2 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 3.1 | Build app in Debug configuration | Phase 2 | 5 min | Ensure fresh build |
| 3.2 | Test LoadingOverlay with Reduce Motion ON | 3.1 | 10 min | Note: continuous rotation, scaling |
| 3.3 | Test TimeWarningBanner with Reduce Motion ON | 3.1 | 5 min | Note: spring slide-in |
| 3.4 | Test test-taking navigation with Reduce Motion ON | 3.1 | 15 min | Question transitions, grid |
| 3.5 | Test authentication flow with Reduce Motion ON | 3.1 | 10 min | Welcome and registration |
| 3.6 | Test test results reveal with Reduce Motion ON | 3.1 | 10 min | Note: rotation, scaling, opacity |
| 3.7 | Test dashboard transitions with Reduce Motion ON | 3.1 | 10 min | Card animations |
| 3.8 | Test privacy consent flow with Reduce Motion ON | 3.1 | 5 min | Consent animations |
| 3.9 | Test all view transitions with Reduce Motion ON | 3.1 | 20 min | Navigation stack animations |
| 3.10 | Capture screenshots of problematic animations | 3.2-3.9 | 10 min | Document visual issues |
| 3.11 | Record animation inventory results | 3.2-3.9 | 10 min | Update spreadsheet with findings |

### Phase 4: Manual Testing - Reduce Motion Disabled (Baseline)
**Goal**: Capture baseline behavior for comparison
**Duration**: 1 hour

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 4.1 | Disable Reduce Motion in Settings | Phase 3 | 2 min | Restore default setting |
| 4.2 | Test LoadingOverlay with Reduce Motion OFF | 4.1 | 5 min | Baseline comparison |
| 4.3 | Test TimeWarningBanner with Reduce Motion OFF | 4.1 | 3 min | Baseline comparison |
| 4.4 | Test test-taking navigation with Reduce Motion OFF | 4.1 | 10 min | Baseline comparison |
| 4.5 | Test authentication flow with Reduce Motion OFF | 4.1 | 5 min | Baseline comparison |
| 4.6 | Test test results reveal with Reduce Motion OFF | 4.1 | 5 min | Baseline comparison |
| 4.7 | Test dashboard transitions with Reduce Motion OFF | 4.1 | 5 min | Baseline comparison |
| 4.8 | Test privacy consent flow with Reduce Motion OFF | 4.1 | 3 min | Baseline comparison |
| 4.9 | Test all view transitions with Reduce Motion OFF | 4.1 | 10 min | Baseline comparison |
| 4.10 | Capture screenshots for before/after comparison | 4.2-4.9 | 10 min | Document visual differences |

### Phase 5: Analysis & Classification
**Goal**: Classify animations by severity and type
**Duration**: 1 hour

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 5.1 | Classify animations by type (entrance, transition, continuous, feedback) | Phase 3, 4 | 15 min | Use standard categories |
| 5.2 | Rate each animation's disorientation potential (None/Low/Medium/High/Critical) | Phase 3, 4 | 20 min | Use established criteria |
| 5.3 | Identify animations that MUST be removed when Reduce Motion is enabled | 5.2 | 10 min | Critical/High severity |
| 5.4 | Identify animations that can be simplified (not removed) | 5.2 | 10 min | Medium severity |
| 5.5 | Identify animations that are acceptable as-is | 5.2 | 5 min | None/Low severity |

### Phase 6: Report Writing
**Goal**: Create comprehensive test report
**Duration**: 2 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 6.1 | Create report document at `/Users/mattgioe/aiq/ios/docs/REDUCE_MOTION_AUDIT.md` | Phase 5 | 10 min | Use audit template |
| 6.2 | Write Executive Summary section | 5.2, 5.3 | 15 min | High-level findings |
| 6.3 | Write Testing Methodology section | Phase 1-4 | 15 min | Document approach |
| 6.4 | Write Animation Inventory section | 5.1 | 20 min | Catalog all animations |
| 6.5 | Write Detailed Findings by Screen section | Phase 3, 4 | 30 min | Per-screen analysis |
| 6.6 | Write Severity Classification section | 5.2-5.5 | 15 min | Severity matrix |
| 6.7 | Write Recommendations section | 5.3-5.5 | 20 min | Specific guidance per animation |
| 6.8 | Write Implementation Guidance section | 5.3-5.5 | 10 min | Code patterns for fixes |
| 6.9 | Write Appendix with testing commands and code samples | None | 10 min | Reference material |

---

## Open Questions

1. **Should we test on physical device in addition to simulator?**
   - Initial answer: No, simulator is sufficient for audit
   - Revisit if findings are unclear

2. **Should we include performance metrics (FPS, frame drops)?**
   - Initial answer: No, this is a user experience audit, not performance
   - Focus on perceptual impact

3. **Should we test in Release build as well as Debug?**
   - Initial answer: Yes, at minimum test LoadingOverlay and TestResultsView in Release
   - Some animations may behave differently

4. **How do we handle animations that serve functional purposes (e.g., loading states)?**
   - Recommendation: Replace with static indicators, not remove entirely
   - Document this pattern in report

---

## Animation Classification Criteria

### Animation Types

1. **Entrance Animations**: Elements appearing on screen (fade, slide, scale)
2. **Transition Animations**: Moving between screens or states
3. **Continuous Animations**: Indefinite animations (spinners, rotations)
4. **Feedback Animations**: Response to user interaction (button press, selection)
5. **Decorative Animations**: Purely aesthetic (parallax, floating)

### Disorientation Severity Ratings

| Severity | Criteria | Examples | Action |
|----------|----------|----------|--------|
| **CRITICAL** | Continuous motion, rotation >180°, or rapid scaling | Loading spinner rotation, parallax scrolling | MUST remove when Reduce Motion enabled |
| **HIGH** | Multiple simultaneous animations, spring physics, or large movements | Results screen celebration animation | SHOULD simplify significantly |
| **MEDIUM** | Single-axis movement, opacity fades with movement, or moderate springs | Slide-in banners, card transitions | SHOULD reduce duration and easing |
| **LOW** | Simple opacity fades, small-scale changes, or subtle movements | Button press feedback, selection state | CAN leave as-is or reduce slightly |
| **NONE** | No perceived motion or disorientation | Static appearance, instant transitions | Leave as-is |

### Reduce Motion Implementation Patterns

**Pattern 1: Environment Variable Check**
```swift
@Environment(\.accessibilityReduceMotion) var reduceMotion

if reduceMotion {
    // No animation or simple crossfade
} else {
    withAnimation(.spring()) {
        // Full animation
    }
}
```

**Pattern 2: Conditional Animation**
```swift
.animation(
    reduceMotion ? nil : .spring(response: 0.3),
    value: someState
)
```

**Pattern 3: Replace with Crossfade**
```swift
.transition(
    reduceMotion ? .opacity : .asymmetric(
        insertion: .move(edge: .trailing).combined(with: .opacity),
        removal: .move(edge: .leading).combined(with: .opacity)
    )
)
```

---

## Deliverables

1. **Reduce Motion Audit Report** (`/Users/mattgioe/aiq/ios/docs/REDUCE_MOTION_AUDIT.md`)
   - Executive summary with pass/fail assessment
   - Complete animation inventory (all 15 files)
   - Detailed findings by screen
   - Severity classifications
   - Specific recommendations for each animation
   - Implementation guidance with code patterns
   - Screenshots documenting problematic animations

2. **Animation Inventory Spreadsheet** (embedded in report as table)
   - File path
   - Line number
   - Animation type
   - Description
   - Severity rating
   - Recommendation
   - Estimated effort to fix

3. **Updated Task in Jira** (BTS-38)
   - Link to audit report
   - Summary of findings
   - Recommendation for follow-up implementation ticket

---

## Estimated Timeline

| Phase | Duration | Cumulative |
|-------|----------|------------|
| Phase 1: Setup | 30 min | 30 min |
| Phase 2: Analysis | 1 hour | 1.5 hours |
| Phase 3: Testing (Reduce Motion ON) | 2 hours | 3.5 hours |
| Phase 4: Testing (Reduce Motion OFF) | 1 hour | 4.5 hours |
| Phase 5: Classification | 1 hour | 5.5 hours |
| Phase 6: Report Writing | 2 hours | 7.5 hours |

**Total Estimated Effort**: 7.5 hours

**Recommended Execution**: 2 sessions
- Session 1 (4 hours): Phases 1-4 (setup, analysis, testing)
- Session 2 (3.5 hours): Phases 5-6 (classification, report)

---

## Success Metrics

- [ ] All 15 files with animations documented
- [ ] Each animation classified by severity (CRITICAL/HIGH/MEDIUM/LOW/NONE)
- [ ] Specific recommendation provided for each animation
- [ ] Report follows established audit format
- [ ] Screenshots captured for problematic animations
- [ ] Implementation guidance includes code patterns
- [ ] Jira ticket updated with findings and next steps

---

## Next Steps (After Audit)

1. Review audit report with stakeholders
2. Prioritize fixes based on severity ratings
3. Create implementation ticket (e.g., BTS-39: Implement Reduce Motion Support)
4. Estimate implementation effort based on audit findings
5. Schedule implementation work in sprint

---

## Appendix A: Files with Animations (from code search)

**Files containing `.animation()` or `withAnimation`** (15 files):
1. `/Users/mattgioe/aiq/ios/AIQ/Views/Test/TimeWarningBanner.swift`
2. `/Users/mattgioe/aiq/ios/AIQ/Views/Test/TestTakingView.swift`
3. `/Users/mattgioe/aiq/ios/AIQ/Views/Test/QuestionNavigationGrid.swift`
4. `/Users/mattgioe/aiq/ios/AIQ/Views/Auth/WelcomeView.swift`
5. `/Users/mattgioe/aiq/ios/AIQ/Views/Auth/RegistrationView.swift`
6. `/Users/mattgioe/aiq/ios/AIQ/Views/Test/DomainScoresView.swift`
7. `/Users/mattgioe/aiq/ios/AIQ/Views/Test/TestTimerView.swift`
8. `/Users/mattgioe/aiq/ios/AIQ/Views/Test/TestProgressView.swift`
9. `/Users/mattgioe/aiq/ios/AIQ/Views/Onboarding/PrivacyConsentView.swift`
10. `/Users/mattgioe/aiq/ios/AIQ/Views/Common/LoadingOverlay.swift`
11. `/Users/mattgioe/aiq/ios/AIQ/Views/Test/AnswerInputView.swift`
12. `/Users/mattgioe/aiq/ios/AIQ/Views/Common/RootView.swift`
13. `/Users/mattgioe/aiq/ios/AIQ/Views/Test/TestResultsView.swift`
14. `/Users/mattgioe/aiq/ios/AIQ/Views/Dashboard/DashboardView.swift`
15. `/Users/mattgioe/aiq/ios/AIQ/Views/History/TestDetailView.swift`

**Files containing `.transition()`** (5 files):
1. `/Users/mattgioe/aiq/ios/AIQ/Views/Test/TestTakingView.swift`
2. `/Users/mattgioe/aiq/ios/AIQ/Views/Dashboard/InProgressTestCard.swift`
3. `/Users/mattgioe/aiq/ios/AIQ/Views/Common/NetworkStatusBanner.swift`
4. `/Users/mattgioe/aiq/ios/AIQ/Views/Common/RootView.swift`
5. `/Users/mattgioe/aiq/ios/AIQ/Views/Dashboard/DashboardView.swift`

---

## Appendix B: Testing Commands

### Enable/Disable Reduce Motion via Simulator

**Enable Reduce Motion:**
```bash
# Method 1: Via Settings app
# Settings > Accessibility > Motion > Reduce Motion (toggle ON)

# Method 2: Via simctl (doesn't work reliably for Reduce Motion)
# Must use Settings app for this preference
```

**Verify Reduce Motion State in SwiftUI Preview:**
```swift
#Preview("Reduce Motion Enabled") {
    TestResultsView(result: mockResult)
        .environment(\.accessibilityReduceMotion, true)
}

#Preview("Reduce Motion Disabled") {
    TestResultsView(result: mockResult)
        .environment(\.accessibilityReduceMotion, false)
}
```

### Build for Simulator

```bash
xcodebuild -project /Users/mattgioe/aiq/ios/AIQ.xcodeproj \
  -scheme AIQ \
  -destination 'platform=iOS Simulator,name=iPhone 16 Pro' \
  -configuration Debug build
```

### Capture Screenshots

```bash
# From Simulator menu: File > New Screen Recording
# Or use Command+S to save screenshot
```

---

## Appendix C: Related Documentation

- **VoiceOver Audit**: `/Users/mattgioe/aiq/ios/docs/VOICEOVER_AUDIT.md`
- **Dynamic Type Audit**: `/Users/mattgioe/aiq/ios/docs/DYNAMIC_TYPE_AUDIT.md`
- **Touch Target Audit**: `/Users/mattgioe/aiq/docs/audits/BTS-34-touch-target-audit.md`
- **iOS Coding Standards**: `/Users/mattgioe/aiq/ios/docs/CODING_STANDARDS.md`
- **iOS Architecture**: `/Users/mattgioe/aiq/ios/docs/ARCHITECTURE.md`

---

**End of Plan**
