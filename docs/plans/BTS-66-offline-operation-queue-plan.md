# BTS-66: Offline Operation Queue Implementation Plan

## Overview
Implement an offline operation queue to improve the user experience when network connectivity is unavailable. The queue will persist profile updates and settings changes, automatically retry failed operations with exponential backoff, and sync when connectivity returns.

## Strategic Context

### Problem Statement
Users currently experience failures when attempting to update their profile or settings while offline. These operations fail immediately without any queuing mechanism, requiring users to manually retry once connectivity is restored. This creates a poor user experience and can lead to data loss if users forget to retry their changes.

### Success Criteria
- Operations are successfully queued when offline and executed when network returns
- Failed operations retry automatically with exponential backoff
- Users are notified of sync status (queuing, syncing, success, permanent failure)
- No data loss occurs during offline periods
- Queue state persists across app restarts
- Conflicts are handled gracefully (last-write-wins for profile updates)
- Test coverage exceeds 80% for the queue implementation

### Why Now?
- The app already has offline support for test-taking (LocalAnswerStorage)
- Profile and settings updates are common user operations
- Network reliability varies significantly across users
- Recent work on AppStateStorage (BTS-67) establishes patterns for disk persistence
- This capability is foundational for future offline features

## Technical Approach

### High-Level Architecture

The offline operation queue will follow the established patterns in the codebase:

```
┌─────────────────────────────────────────────────────────┐
│                     ViewModels                           │
│          (SettingsViewModel, ProfileViewModel)          │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ Enqueue Operations
                     ▼
┌─────────────────────────────────────────────────────────┐
│              OfflineOperationQueue                       │
│  ┌─────────────────────────────────────────────────┐   │
│  │  - Enqueue mutations when offline                │   │
│  │  - Persist queue to disk (UserDefaults)         │   │
│  │  - Monitor NetworkMonitor state changes          │   │
│  │  - Process queue when online                     │   │
│  │  - Exponential backoff retry logic               │   │
│  │  - Max retry limit enforcement                   │   │
│  └─────────────────────────────────────────────────┘   │
└────────────┬────────────────────────────────────────────┘
             │
             │ Observes Connectivity
             ▼
┌─────────────────────────────────────────────────────────┐
│                   NetworkMonitor                         │
│                   (existing service)                     │
└─────────────────────────────────────────────────────────┘
```

### Key Components

#### 1. OfflineOperationQueue (New)
A service that manages queued operations:
- **Protocol-based design** for testability
- **Actor isolation** for thread-safe queue access
- **UserDefaults persistence** following LocalAnswerStorage pattern
- **NetworkMonitor observation** for connectivity state
- **Exponential backoff** using RetryPolicy pattern
- **@Published state** for UI updates

#### 2. QueuedOperation (New Model)
Represents a queued mutation:
```swift
struct QueuedOperation: Codable, Identifiable {
    let id: UUID
    let type: OperationType
    let payload: Data  // JSON-encoded operation data
    let createdAt: Date
    var attemptCount: Int
    var lastAttemptAt: Date?
    var error: String?  // Last error message (for user feedback)

    enum OperationType: String, Codable {
        case updateProfile
        case updateNotificationSettings
        // Future: other mutations
    }
}
```

#### 3. Integration Points
- **ViewModels**: Enqueue operations when API calls fail with network errors
- **NetworkMonitor**: Observe connectivity to trigger sync
- **APIClient**: Execute queued operations using existing retry mechanisms

### Key Decisions & Tradeoffs

#### Decision 1: Actor vs. Serial Queue
**Choice**: Use Swift `actor` for queue isolation
**Rationale**:
- Modern Swift concurrency approach
- Compiler-enforced thread safety
- Consistent with codebase direction (DataCache is an actor)
- Simpler than manually managing DispatchQueue

**Tradeoff**: Requires async/await at call sites

#### Decision 2: UserDefaults vs. File System
**Choice**: UserDefaults for queue persistence
**Rationale**:
- Consistent with LocalAnswerStorage pattern
- Automatic iCloud sync if enabled
- Simpler implementation
- Queue size will be small (< 50 operations typically)

**Tradeoff**:
- Not ideal for very large queues (not expected in this use case)
- 1MB practical limit (sufficient for ~100 operations)

#### Decision 3: Optimistic vs. Pessimistic Queueing
**Choice**: Pessimistic (queue only on network error)
**Rationale**:
- Simpler implementation
- Avoids conflict resolution complexity
- Network errors are already handled by RetryPolicy
- User sees immediate feedback on success

**Tradeoff**: No offline queuing before attempting network call

#### Decision 4: Conflict Resolution Strategy
**Choice**: Last-write-wins (overwrite server state)
**Rationale**:
- Profile/settings updates are typically single-device operations
- No collaborative editing scenarios
- Simpler than merge strategies
- Consistent with user expectations

**Tradeoff**: Could lose server-side changes if multiple devices (acceptable for MVP)

#### Decision 5: Retry Policy
**Choice**: Exponential backoff with max 5 retries
**Rationale**:
- Consistent with existing RetryPolicy pattern
- 1s, 2s, 4s, 8s, 16s (total ~31s over time)
- Balances responsiveness with network load
- Max 5 attempts before permanent failure

**Tradeoff**: Operations could wait up to 31s before permanent failure

#### Decision 6: UI Notification Strategy
**Choice**: Published properties + toast/banner notifications
**Rationale**:
- @Published properties for reactive UI updates
- Non-intrusive notifications during sync
- Error alerts for permanent failures only
- Consistent with existing error handling patterns

**Tradeoff**: Users might miss transient sync notifications

### Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Queue grows unbounded | Memory/storage issues | Implement max queue size (100 operations), drop oldest |
| Corruption of persisted queue | Queue becomes unreadable | Graceful fallback: clear queue, log to Crashlytics |
| Network flapping causes rapid retries | Battery drain, poor UX | Debounce network state changes (1s delay) |
| Operation succeeds but queue persists | Duplicate operations | Track operation state, remove on success |
| User changes value multiple times offline | Stale operations in queue | Coalesce duplicate operations before sync |
| App terminated during sync | Incomplete operations | Persist state after each operation completion |

## Implementation Plan

### Phase 1: Core Queue Infrastructure
**Goal**: Implement the operation queue with persistence and basic retry logic
**Duration**: 3-4 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 1.1 | Create QueuedOperation model with Codable conformance | None | 30 min | Follow SavedTestProgress pattern |
| 1.2 | Create OfflineOperationQueueProtocol | None | 15 min | For testability |
| 1.3 | Implement OfflineOperationQueue actor with storage | 1.1, 1.2 | 1.5 hours | UserDefaults persistence, serial queue |
| 1.4 | Add operation enqueue with deduplication logic | 1.3 | 45 min | Coalesce duplicate operations |
| 1.5 | Implement disk persistence (save/load/clear) | 1.3 | 45 min | Handle encoding errors gracefully |
| 1.6 | Add queue size limit enforcement | 1.5 | 30 min | Max 100 operations, FIFO eviction |

### Phase 2: Network Monitoring & Sync
**Goal**: Integrate with NetworkMonitor to trigger sync when connectivity returns
**Duration**: 2-3 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 2.1 | Add NetworkMonitor observation to queue | 1.5 | 45 min | Observe isConnected publisher |
| 2.2 | Implement sync trigger with debouncing | 2.1 | 45 min | 1s debounce to avoid flapping |
| 2.3 | Add queue processing loop with concurrency control | 2.2 | 1 hour | Process one operation at a time |
| 2.4 | Implement operation execution via APIClient | 2.3 | 45 min | Route by operation type |

### Phase 3: Retry Logic with Exponential Backoff
**Goal**: Add robust retry mechanism with exponential backoff
**Duration**: 2-3 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 3.1 | Create retry policy for queue operations | Phase 2 | 30 min | Based on existing RetryPolicy |
| 3.2 | Implement exponential backoff calculator | 3.1 | 30 min | 1s, 2s, 4s, 8s, 16s |
| 3.3 | Add retry attempt tracking per operation | 3.2 | 45 min | Update attemptCount, lastAttemptAt |
| 3.4 | Implement max retry limit (5 attempts) | 3.3 | 30 min | Mark as permanently failed |
| 3.5 | Add error capture for user feedback | 3.4 | 30 min | Store last error message |
| 3.6 | Implement operation removal on permanent failure | 3.5 | 30 min | Move to failed operations list |

### Phase 4: State Publishing & UI Integration
**Goal**: Expose queue state for UI updates and user notifications
**Duration**: 2-3 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 4.1 | Add @Published properties for queue state | Phase 3 | 45 min | operationCount, isSyncing, failures |
| 4.2 | Create QueueStatus enum for UI | 4.1 | 15 min | idle, syncing, failed |
| 4.3 | Add notification for sync start/complete | 4.2 | 30 min | @Published syncStatus |
| 4.4 | Add notification for permanent failures | 4.3 | 30 min | @Published failedOperations |
| 4.5 | Document integration patterns for ViewModels | 4.4 | 45 min | Code examples in doc comments |

### Phase 5: Comprehensive Testing
**Goal**: Achieve >80% test coverage with robust unit tests
**Duration**: 4-5 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 5.1 | Create MockOfflineOperationQueue | Phase 4 | 30 min | For ViewModel testing |
| 5.2 | Test: Enqueue operation when offline | 5.1 | 30 min | Verify operation added to queue |
| 5.3 | Test: Queue persists to disk | 5.1 | 45 min | Verify save/load round-trip |
| 5.4 | Test: Queue loads from disk on init | 5.3 | 30 min | Verify persistence across restarts |
| 5.5 | Test: Corrupt data clears queue gracefully | 5.3 | 30 min | Verify error handling |
| 5.6 | Test: Sync triggers when network returns | 2.4 | 45 min | Mock NetworkMonitor state change |
| 5.7 | Test: Operations execute in order | 2.4 | 30 min | Verify FIFO processing |
| 5.8 | Test: Successful operation removed from queue | 2.4 | 30 min | Verify cleanup |
| 5.9 | Test: Failed operation retries with backoff | 3.6 | 1 hour | Mock clock, verify delays |
| 5.10 | Test: Max retry limit enforced | 3.6 | 30 min | Verify permanent failure after 5 |
| 5.11 | Test: Duplicate operations coalesced | 1.4 | 45 min | Verify deduplication logic |
| 5.12 | Test: Queue size limit enforced | 1.6 | 30 min | Verify FIFO eviction |
| 5.13 | Test: Published state updates correctly | 4.4 | 45 min | Verify UI state changes |

### Phase 6: Documentation & Integration Examples
**Goal**: Document the queue and provide integration examples
**Duration**: 1-2 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 6.1 | Add comprehensive doc comments to protocol | Phase 5 | 30 min | Include usage examples |
| 6.2 | Add doc comments to all public methods | Phase 5 | 30 min | Explain parameters, behavior |
| 6.3 | Create integration example in SettingsViewModel | Phase 5 | 45 min | Show enqueue pattern |
| 6.4 | Document conflict resolution strategy | Phase 5 | 15 min | Explain last-write-wins |

## Open Questions

1. **Should we batch operations for efficiency?**
   - Current plan: Process one at a time for simplicity
   - Future enhancement: Batch profile updates if queue has multiple

2. **Should we expose retry attempt count to users?**
   - Current plan: Show binary state (syncing/failed)
   - Alternative: Show "Retry 3 of 5" for transparency

3. **Should we support operation cancellation?**
   - Current plan: No manual cancellation (operations are user-initiated)
   - Alternative: Add "Cancel Pending Changes" button

4. **Should we sync immediately on app launch if queue is non-empty?**
   - Current plan: Yes, sync on init if network available
   - Risk: Could delay app launch if many operations queued

5. **How should we handle 401 (unauthorized) errors during sync?**
   - Current plan: Treat as permanent failure (user logged out)
   - Alternative: Clear queue and notify user to re-authenticate

## Appendix

### Related Code Patterns

#### LocalAnswerStorage Pattern
The queue will follow the LocalAnswerStorage pattern for persistence:
- UserDefaults storage with JSONEncoder/JSONDecoder
- Serial queue for thread-safe access
- Graceful handling of decode errors (clear corrupt data)
- Validation on load (clear expired data)

#### RetryPolicy Pattern
The queue will use exponential backoff similar to RetryPolicy:
- `delayCalculator: { attempt in pow(2.0, Double(attempt - 1)) }`
- Max 5 attempts (vs. 3 for network requests)
- Retryable errors: network errors, 5xx, 408, 429

#### NetworkMonitor Integration
The queue will observe NetworkMonitor.shared:
```swift
NetworkMonitor.shared.$isConnected
    .sink { [weak self] isConnected in
        if isConnected {
            Task { await self?.processPendingOperations() }
        }
    }
    .store(in: &cancellables)
```

#### BaseViewModel Error Handling
ViewModels will enqueue operations in catch blocks:
```swift
do {
    try await apiClient.request(endpoint: .updateProfile, ...)
} catch let error as APIError {
    if error.isRetryable {
        await offlineQueue.enqueue(operation: .updateProfile(data))
    }
    handleError(error, context: .updateProfile)
}
```

### Recommended Subagent Assignment

This implementation should be delegated to the **ios-engineer** subagent because:

1. **Pure iOS Implementation**: No backend changes required
2. **Established Patterns**: Follows existing codebase patterns (LocalAnswerStorage, RetryPolicy, NetworkMonitor)
3. **Testing Expertise**: Requires comprehensive unit test coverage (>80%)
4. **Architectural Understanding**: Needs deep knowledge of MVVM, actors, and Swift concurrency
5. **Integration Complexity**: Must integrate with multiple existing services (APIClient, NetworkMonitor, ViewModels)

The ios-engineer subagent should:
- Implement all phases sequentially (1 → 6)
- Run tests after each phase to ensure incremental quality
- Use the build-ios-project and run-ios-test skills
- Use the xcode-file-manager skill to add new files to the Xcode project
- Follow the CODING_STANDARDS.md guidelines strictly
- Update CODING_STANDARDS.md if any new patterns are established

### Success Metrics

- [ ] All acceptance criteria met
- [ ] Test coverage >80% for OfflineOperationQueue
- [ ] All tests pass (run via /run-ios-test skill)
- [ ] Project builds successfully (run via /build-ios-project skill)
- [ ] No SwiftLint violations
- [ ] Integration example provided in SettingsViewModel or ProfileViewModel
- [ ] Documentation complete (doc comments + integration guide)
- [ ] Queue persists across app restarts (verified via test)
- [ ] Network state changes trigger sync (verified via test)
- [ ] Exponential backoff works correctly (verified via test)
