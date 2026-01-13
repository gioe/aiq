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
