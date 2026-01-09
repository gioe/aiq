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
