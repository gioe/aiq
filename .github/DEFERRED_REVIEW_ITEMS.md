## Deferred from PR #496 Review

### 1. Implement atomic save with rollback in AuthService.saveAuthData()
- **Original comment**: "The tests correctly document a critical security and UX issue in AuthService.saveAuthData()... If any save() call fails, storage is left in an inconsistent state."
- **Reason deferred**: Out of scope for test-only PR; requires production code changes and careful implementation of transaction semantics
- **Jira ticket**: BTS-228

### 2. Add tests for apiClient state after partial storage save failures
- **Original comment**: "Consider testing apiClient state: Current tests verify storage state but not apiClient.setAuthToken() calls"
- **Reason deferred**: Enhancement to test coverage, not blocking for the initial PR
- **Jira ticket**: BTS-229
