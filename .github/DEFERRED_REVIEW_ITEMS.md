## Deferred from PR #525 Review

### 1. Consolidate SettingsViewModel error handling properties
- **Original comment**: "The ViewModel maintains a separate deleteAccountError property in addition to the inherited error property from BaseViewModel. This creates two error channels which could be confusing."
- **Reason deferred**: Refactoring suggestion that doesn't affect functionality; current implementation works correctly
- **Jira ticket**: BTS-254

### 2. Add error handling to logout() method
- **Original comment**: "The logout() method doesn't handle errors. Check if AuthManager.logout() implementation can fail."
- **Reason deferred**: Requires investigation of AuthManager; current method is non-throwing
- **Jira ticket**: BTS-255

### 3. Add Crashlytics integration tests
- **Original comment**: "The tests verify functional behavior but don't verify that errors are properly logged to Crashlytics."
- **Reason deferred**: Test enhancement that provides additional confidence but doesn't affect production functionality
- **Jira ticket**: BTS-256

### 4. Document dual error handling architecture
- **Original comment**: "Add a comment explaining why deleteAccount uses a separate error property instead of BaseViewModel's standard error handling."
- **Reason deferred**: Documentation improvement that doesn't affect functionality
- **Jira ticket**: BTS-257

### 5. Add concurrent operation protection
- **Original comment**: "If logout() or deleteAccount() is called twice concurrently, the loading state could be incorrect."
- **Reason deferred**: Very low impact edge case; UI already prevents double-taps
- **Jira ticket**: BTS-258

---

## Deferred from PR #504 Review

### 1. Extract UserDefaults deviceTokenKey to shared constant
- **Original comment**: "The deviceTokenKey is duplicated from NotificationManager.swift:36. If the key changes in the implementation, tests break."
- **Reason deferred**: Minor duplication issue; does not affect test correctness
- **Jira ticket**: BTS-230

### 2. Add concurrency test for isRegisteringToken flag
- **Original comment**: "NotificationManager has an isRegisteringToken flag to prevent concurrent registrations, but there's no test verifying this works correctly."
- **Reason deferred**: Nice-to-have test enhancement; existing tests provide adequate coverage
- **Jira ticket**: BTS-231

### 3. Improve test naming consistency
- **Original comment**: "Some test names use 'PropagatesCorrectly' while others use more descriptive names."
- **Reason deferred**: Style preference; does not affect test functionality
- **Jira ticket**: BTS-232

### 4. Document mock reset pattern
- **Original comment**: "Some tests reset mocks mid-test. The pattern should be consistently documented."
- **Reason deferred**: Documentation enhancement; partially addressed in this PR
- **Jira ticket**: BTS-233

---

## Deferred from PR #496 Review

### 1. Implement atomic save with rollback in AuthService.saveAuthData()
- **Original comment**: "The tests correctly document a critical security and UX issue in AuthService.saveAuthData()... If any save() call fails, storage is left in an inconsistent state."
- **Reason deferred**: Out of scope for test-only PR; requires production code changes and careful implementation of transaction semantics
- **Jira ticket**: BTS-228

### 2. Add tests for apiClient state after partial storage save failures
- **Original comment**: "Consider testing apiClient state: Current tests verify storage state but not apiClient.setAuthToken() calls"
- **Reason deferred**: Enhancement to test coverage, not blocking for the initial PR
- **Jira ticket**: BTS-229
