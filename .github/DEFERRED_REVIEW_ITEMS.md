# Deferred Review Items

## Deferred from PR #534 Review (BTS-83 - Background Refresh Capability)

### 1. Refactor BackgroundRefreshManagerTests to test actual implementation
- **Original comment**: "Tests duplicate the production logic rather than testing the actual implementation"
- **Reason deferred**: Testing architecture improvement that doesn't affect production behavior
- **Jira ticket**: BTS-281

### 2. Add max(0, ...) guard to day calculation
- **Original comment**: "dateComponents(_:from:to:) can return negative values if clock changes or timezone shifts occur"
- **Reason deferred**: Edge case unlikely to cause issues; existing ?? 0 fallback provides reasonable behavior
- **Jira ticket**: BTS-282

### 3. Manual testing documentation
- **Original comment**: "Consider documenting how to test background refresh using Xcode's simulated background fetch"
- **Reason deferred**: Documentation improvement that doesn't affect functionality
- **Jira ticket**: BTS-283

## Deferred from PR #536 Review (BTS-104 - Standardize Network Timeouts)

### 1. Document RegistrationHelper 15s timeout rationale
- **Original comment**: "Add code comment explaining why RegistrationHelper uses 15s timeout vs standard 10s"
- **Reason deferred**: Code style/documentation improvement - doesn't affect functionality
- **Jira ticket**: BTS-284

### 2. Add test coverage for education level picker
- **Original comment**: "Add test case for education level picker (can be follow-up PR)"
- **Reason deferred**: Functionality works; test coverage can be added in a follow-up PR
- **Jira ticket**: BTS-285

### 3. Consider extracting timeout constants to config file
- **Original comment**: "Consider extracting timeout constants to dedicated config file if more timeout types are added"
- **Reason deferred**: Future scalability enhancement - current implementation is sufficient
- **Jira ticket**: BTS-286

## Deferred from PR #537 Review (BTS-103 - Add Error Recovery to LoginHelper.logout())

### 1. Optimize fallback timeout strategy
- **Original comment**: "Each fallback strategy waits full 5s timeout. In worst case, 15 seconds of wait time."
- **Reason deferred**: Performance optimization, not correctness issue. PR approved as "safe to merge as-is"
- **Jira ticket**: BTS-290

### 2. Make confirmation button timeout configurable
- **Original comment**: "Confirmation button uses hardcoded 2.0s timeout"
- **Reason deferred**: Low priority code style improvement - doesn't affect test functionality
- **Jira ticket**: BTS-290

### 3. Documentation improvements for timeout behavior
- **Original comment**: "Clarify cumulative timeout impact and dialog detection short-circuit behavior"
- **Reason deferred**: Documentation clarity - doesn't affect test execution
- **Jira ticket**: BTS-290

## Deferred from PR #538 Review (BTS-102 - Implement .notificationTapped Observer)

### 1. Add navigation behavior tests for notification tap handling
- **Original comment**: "Tests thoroughly validate payload extraction and deep link parsing, but don't test actual navigation behavior"
- **Reason deferred**: Unit tests focused on parsing logic are acceptable; integration tests are a nice-to-have
- **Jira ticket**: BTS-292

### 2. Rename test file to match component
- **Original comment**: "Test file named NotificationTappedHandlerTests but tests functionality in MainTabView"
- **Reason deferred**: Not blocking, just a discoverability consideration
- **Jira ticket**: BTS-293

### 3. Improve test documentation
- **Original comment**: "Doc comment doesn't specify what happens if deep_link is missing or what URL schemes are supported"
- **Reason deferred**: Nice-to-have documentation improvement
- **Jira ticket**: BTS-294
