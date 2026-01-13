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
