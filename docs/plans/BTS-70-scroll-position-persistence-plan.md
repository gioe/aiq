# BTS-70: Persist Scroll Positions in Long Lists

## Overview
Implement scroll position persistence for SwiftUI list views in the AIQ iOS app, allowing users to return to their previous scroll position when navigating back to list views. This feature enhances the user experience by maintaining context during navigation, particularly beneficial for the paginated HistoryView and long-form educational Help pages.

## Strategic Context

### Problem Statement
Users currently lose their scroll position when navigating away from and back to list views. This creates friction in common workflows:
- **HistoryView**: Users viewing their test history must scroll back down after viewing test details, especially problematic with paginated results
- **Help Pages**: Users reading long educational content (IQ Score Help, Score Range Help, etc.) lose their place when navigating away

This degrades the user experience and creates unnecessary cognitive overhead in what should be a seamless browsing experience.

### Success Criteria
1. **Scroll position saved**: When users navigate away from HistoryView or Help pages, their scroll position is persisted
2. **Scroll position restored**: When users return to these views, their previous scroll position is restored (if technically feasible)
3. **Graceful degradation**: If SwiftUI limitations prevent full restoration, the implementation degrades gracefully without crashes or errors
4. **Performance**: No noticeable performance impact or lag when scrolling or navigating
5. **Thread safety**: All storage operations are thread-safe and don't cause race conditions
6. **Type safety**: Implementation follows existing AppStateStorage patterns for type-safe persistence

### Why Now?
1. **Infrastructure exists**: AppStateStorage service and @AppStorage patterns are already established (BTS-68, BTS-69)
2. **User feedback priority**: Scroll position loss is a common UX complaint, particularly for HistoryView
3. **iOS version availability**: iOS 17+ introduced native ScrollPosition API, making this feasible
4. **Low risk, high value**: Implementation follows established patterns with clear user benefit
5. **Complements recent work**: Builds on tab and filter persistence work already completed

## Technical Approach

### High-Level Architecture

The implementation leverages SwiftUI's ScrollPosition API (iOS 17+) combined with the existing AppStateStorage service:

```
User scrolls HistoryView
    ↓
ScrollPosition(id:) captures visible item ID
    ↓
onChange modifier detects scroll changes
    ↓
AppStateStorage persists position (String ID or offset)
    ↓
User navigates away and returns
    ↓
onAppear reads persisted position
    ↓
ScrollPosition restores to saved ID/offset
```

**Key Components:**
- **ScrollPosition API**: iOS 17+ native API for tracking and controlling scroll position
- **AppStateStorage**: Existing thread-safe UserDefaults wrapper for persistence
- **@AppStorage**: SwiftUI property wrapper for reactive storage binding
- **Identifiable items**: Test results and help sections with stable IDs

### iOS Version Compatibility

**Current deployment target**: iOS 16.0

**ScrollPosition API availability**:
- `ScrollPosition` struct: iOS 17.0+
- `scrollPosition(id:)` modifier: iOS 18.0+
- `scrollPosition(_:)` modifier: iOS 17.0+ (uses ScrollPosition binding)

**Decision**: Since the app targets iOS 16.0, we need version checking:
```swift
if #available(iOS 17.0, *) {
    // Use ScrollPosition API
} else {
    // Graceful degradation (no persistence)
}
```

### Key Decisions & Tradeoffs

**Decision 1: Use ScrollPosition API (iOS 17+) vs. ScrollViewReader**
- **Choice**: ScrollPosition API with iOS 17+ availability check
- **Rationale**:
  - ScrollViewReader requires manual scrollTo() calls on appear, which can cause jarring animations
  - ScrollPosition provides declarative, state-driven approach that's more SwiftUI-native
  - Better performance and animation characteristics
  - Official Apple recommendation for modern SwiftUI
- **Tradeoff**: iOS 16 users won't get persistence (acceptable degradation)

**Decision 2: Store item IDs vs. scroll offsets**
- **Choice**: Store stable item IDs (String) for HistoryView, offsets for Help pages
- **Rationale**:
  - HistoryView has stable, unique IDs (test result UUIDs)
  - Help pages don't have natural IDs, use CGPoint offsets
  - ID-based approach is more resilient to content changes
- **Tradeoff**: Help pages may have less precise restoration if content height changes

**Decision 3: Persist on every scroll vs. on view disappear**
- **Choice**: Persist on scroll with debouncing
- **Rationale**:
  - View disappear may not fire in all scenarios (app backgrounding, crashes)
  - Debouncing prevents excessive storage writes
  - More reliable state capture
- **Tradeoff**: Slightly more storage writes, mitigated by debouncing

**Decision 4: Global position vs. per-filter position**
- **Choice**: Single global position for HistoryView (ignores filter state)
- **Rationale**:
  - Simpler implementation and mental model
  - Users typically don't switch filters frequently
  - Filter changes reset scroll to top (expected behavior)
- **Tradeoff**: Position lost when changing filters (acceptable)

### Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| iOS 16 users lose feature | High | Low | Document as iOS 17+ feature, graceful degradation |
| Invalid stored IDs after data changes | Medium | Medium | Validate IDs on restoration, fall back to top |
| Performance impact from frequent storage | Low | Low | Implement debouncing (0.5s delay) |
| Race conditions in storage access | Low | High | Use existing AppStateStorage thread-safe queue |
| ScrollPosition API bugs in iOS 17 | Low | Medium | Extensive testing, fallback to no persistence |
| Pagination conflicts with position | Medium | Medium | Validate stored ID exists in current page |

## Implementation Plan

### Phase 1: Infrastructure & Storage Keys
**Goal**: Establish storage infrastructure and prepare for scroll position persistence
**Duration**: 1 hour

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 1.1 | Define storage key constants in AppStateStorage | None | 15 min | Add `com.aiq.historyScrollPosition`, `com.aiq.helpScrollPositions` |
| 1.2 | Add unit tests for new storage keys | 1.1 | 30 min | Test set/get/remove for String and CGPoint types |
| 1.3 | Document storage key usage in code comments | 1.1 | 15 min | Add inline documentation for future maintainers |

### Phase 2: HistoryView Implementation (iOS 17+)
**Goal**: Implement scroll position persistence for HistoryView with iOS 17+ support
**Duration**: 3 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 2.1 | Add @State var scrollPosition to HistoryView | Phase 1 | 15 min | Type: String? (test result ID) |
| 2.2 | Wrap ScrollView with availability check | 2.1 | 30 min | `if #available(iOS 17.0, *)` wrapper |
| 2.3 | Add scrollPosition binding to ScrollView | 2.2 | 30 min | Use `.scrollPosition(id: $scrollPosition)` |
| 2.4 | Add .id() to ForEach test result items | 2.3 | 15 min | Ensure items are identifiable |
| 2.5 | Implement onChange(of: scrollPosition) with debouncing | 2.4 | 45 min | Save to AppStorage after 0.5s delay |
| 2.6 | Load saved position on view appear | 2.5 | 30 min | Read from AppStorage, validate ID exists |
| 2.7 | Clear position on filter/sort changes | 2.6 | 15 min | Reset to nil when filters change |
| 2.8 | Add iOS 16 fallback (no persistence) | 2.2 | 15 min | Else clause with original ScrollView |

### Phase 3: HistoryView Testing
**Goal**: Comprehensive testing of HistoryView scroll persistence
**Duration**: 2 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 3.1 | Create HistoryViewScrollPersistenceTests test class | Phase 2 | 15 min | Follow existing test patterns |
| 3.2 | Test position saved when scrolling to item | 3.1 | 30 min | Mock scroll, verify storage write |
| 3.3 | Test position restored on view appear | 3.1 | 30 min | Set storage value, verify scroll restoration |
| 3.4 | Test invalid ID handling (graceful fallback) | 3.1 | 20 min | Store non-existent ID, verify no crash |
| 3.5 | Test position cleared on filter change | 3.1 | 20 min | Change filter, verify position reset |
| 3.6 | Test iOS 16 graceful degradation | 3.1 | 20 min | Ensure no crashes on iOS 16 simulator |
| 3.7 | Manual testing on iOS 17+ device | Phase 2 | 45 min | Real device testing with pagination |

### Phase 4: Help Pages Implementation (iOS 17+)
**Goal**: Implement scroll position persistence for all Help pages
**Duration**: 2.5 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 4.1 | Create reusable ScrollableHelpView component | Phase 3 | 45 min | Wraps ScrollView with position tracking |
| 4.2 | Add @AppStorage for position (keyed by page ID) | 4.1 | 20 min | Store CGPoint or anchor-based position |
| 4.3 | Refactor ScoreRangeHelpView to use component | 4.2 | 15 min | Replace ScrollView with ScrollableHelpView |
| 4.4 | Refactor IQScoreHelpView to use component | 4.2 | 15 min | Replace ScrollView with ScrollableHelpView |
| 4.5 | Refactor TestFrequencyHelpView to use component | 4.2 | 15 min | Replace ScrollView with ScrollableHelpView |
| 4.6 | Refactor QuestionTypesHelpView to use component | 4.2 | 15 min | Replace ScrollView with ScrollableHelpView |
| 4.7 | Refactor DataPrivacyHelpView to use component | 4.2 | 15 min | Replace ScrollView with ScrollableHelpView |
| 4.8 | Add iOS 16 fallback to component | 4.1 | 30 min | Conditional compilation for availability |

### Phase 5: Help Pages Testing
**Goal**: Test scroll persistence across all Help pages
**Duration**: 2 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 5.1 | Create HelpViewScrollPersistenceTests | Phase 4 | 15 min | Test class setup |
| 5.2 | Test ScrollableHelpView position saving | 5.1 | 30 min | Verify storage writes on scroll |
| 5.3 | Test ScrollableHelpView position restoration | 5.1 | 30 min | Verify scroll restoration on appear |
| 5.4 | Test position isolation between pages | 5.1 | 20 min | Ensure each page has independent storage |
| 5.5 | Test iOS 16 graceful degradation | 5.1 | 15 min | Ensure no crashes on iOS 16 |
| 5.6 | Manual testing of all 5 Help pages | Phase 4 | 50 min | Navigate through all pages, test persistence |

### Phase 6: Documentation & Code Review Prep
**Goal**: Document implementation and prepare for review
**Duration**: 1 hour

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 6.1 | Add inline code documentation | Phase 5 | 20 min | Document availability requirements, behavior |
| 6.2 | Update CODING_STANDARDS.md with scroll persistence pattern | 6.1 | 20 min | Add to SwiftUI Best Practices section |
| 6.3 | Create implementation summary document | 6.1 | 20 min | Document for Jira ticket and PR description |

### Phase 7: Integration Testing & Polish
**Goal**: End-to-end testing and final polish
**Duration**: 1.5 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 7.1 | Test complete user flow: History → Detail → Back | Phase 6 | 20 min | Verify position preserved |
| 7.2 | Test with pagination: Scroll, load more, navigate | Phase 6 | 20 min | Ensure works with dynamic content |
| 7.3 | Test Help navigation flow across multiple pages | Phase 6 | 20 min | Verify independent persistence |
| 7.4 | Performance testing: Check for scroll lag | Phase 6 | 15 min | Profile scrolling performance |
| 7.5 | Accessibility testing with VoiceOver | Phase 6 | 20 min | Ensure no accessibility regressions |
| 7.6 | Test on multiple iOS versions (16, 17, 18) | Phase 6 | 30 min | Verify graceful degradation and feature availability |

## Total Estimated Duration
**11.5 hours** (approximately 1.5-2 days of focused development)

## Open Questions

1. **Minimum iOS version policy**: Should we consider bumping the minimum deployment target to iOS 17 in the future to simplify this implementation? (Not a blocker for this ticket)

2. **Scroll position expiration**: Should stored scroll positions expire after a certain time period (e.g., 7 days)? Current plan: persist indefinitely until user clears app data.

3. **Pagination interaction**: If a user's saved scroll position is on page 3 of HistoryView, should we auto-load pages 1-3 on restoration? Current plan: Only restore if ID is in currently loaded results, otherwise scroll to top.

4. **Analytics tracking**: Should we track scroll position restoration success rate for iOS 17+ users? Current plan: No analytics for this feature initially.

## Appendix

### Storage Key Naming Convention
Following existing patterns in the codebase:
- `com.aiq.historyScrollPosition` (String - test result ID)
- `com.aiq.helpScrollPositions` (Dictionary<String, CGPoint> - keyed by page identifier)

### Alternative Approaches Considered

**Approach 1: ScrollViewReader with manual scrollTo()**
- Pros: Works on iOS 14+
- Cons: Requires manual scrollTo() calls, jarring animations, less SwiftUI-native
- Rejected: Poor UX due to animation issues

**Approach 2: Custom UIViewRepresentable with UIScrollView**
- Pros: Full control, works on all iOS versions
- Cons: Breaks SwiftUI paradigm, requires UIKit bridging, high maintenance
- Rejected: Over-engineered for this use case

**Approach 3: Raise minimum iOS version to 17**
- Pros: Simplifies implementation, no availability checks
- Cons: Excludes iOS 16 users (potentially significant user base)
- Rejected: Too disruptive for this single feature

### References
- [ScrollPosition API Documentation](https://developer.apple.com/documentation/swiftui/scrollposition)
- [WWDC 2023: What's new in SwiftUI](https://developer.apple.com/videos/play/wwdc2023/10148/)
- [Existing AppStateStorage implementation](/Users/mattgioe/aiq/ios/AIQ/Services/Storage/AppStateStorage.swift)
- [BTS-68: Tab Persistence](/Users/mattgioe/aiq/docs/analysis/BTS-68-tab-persistence-analysis.md)
- [BTS-69: Filter Persistence](/Users/mattgioe/aiq/ios/docs/BTS-69-FILTER-PERSISTENCE-IMPLEMENTATION.md)

### Success Metrics (Post-Launch)
If analytics are added in the future, track:
- Scroll restoration success rate (iOS 17+ only)
- Percentage of users scrolling beyond first screen in HistoryView
- Navigation patterns: Detail view return rate
- User session duration in Help pages (proxy for engagement)
