# FeedbackViewModel Unit Tests Implementation Plan

## Overview
Comprehensive unit test suite for FeedbackViewModel covering validation logic, form submission behavior, and edge cases. Related to BTS-45 (Feedback feature).

## Strategic Context

### Problem Statement
The FeedbackViewModel is functional but lacks test coverage. Without tests, we risk regression bugs when making changes to validation logic or API integration. This is particularly important for a user-facing feature where validation errors directly impact user experience.

### Success Criteria
- 100% code coverage for FeedbackViewModel
- All validation edge cases tested
- All submission scenarios covered (success, failure, network errors)
- Tests follow existing patterns from RegistrationViewModelTests and LoginViewModelTests
- Tests are maintainable and clearly document expected behavior

### Why Now?
The feedback feature was just implemented in PR #484. Adding tests now while the implementation is fresh ensures we catch any issues early and establish a test baseline before future modifications.

## Technical Approach

### High-Level Architecture
Following the established testing pattern:
1. Use MockAPIClient (actor-based) for network dependency injection
2. Inherit test structure from existing ViewModel tests
3. Use @MainActor for test class since ViewModel is @MainActor
4. Group tests by functionality: Initialization, Validation, Actions, Loading State, Error Handling, Integration

### Key Decisions & Tradeoffs
1. **MockAPIClient over Real Networking**: Provides deterministic, fast tests without external dependencies
2. **Comprehensive Validation Testing**: Test boundary conditions for all fields to prevent regression
3. **Async/Await Testing**: Use Swift Concurrency for testing async submitFeedback() method
4. **Test Organization**: Follow existing pattern (6 categories) for consistency with other ViewModel tests

### Risks & Mitigations
- **Risk**: MockAPIClient actor isolation complexity
  - **Mitigation**: Follow established patterns from other test files
- **Risk**: Testing async DispatchQueue.main.asyncAfter in resetForm()
  - **Mitigation**: Use expectations with appropriate timeouts

## Implementation Plan

### Phase 1: Test File Setup and Initialization Tests
**Goal**: Create test file with basic structure and initialization tests
**Duration**: 30 minutes

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 1.1 | Create FeedbackViewModelTests.swift in AIQTests/ViewModels/ | None | 10 min | Follow existing test file structure |
| 1.2 | Add MockAPIClient setup in setUp() method | 1.1 | 10 min | Create sut with mock dependency |
| 1.3 | Write testInitialState() | 1.2 | 10 min | Verify all properties have correct initial values |

### Phase 2: Validation Tests - Name Field
**Goal**: Test all name validation scenarios
**Duration**: 45 minutes

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 2.1 | testNameValidation_EmptyName() | 1.3 | 10 min | Verify empty name returns .invalid with "Name is required" |
| 2.2 | testNameValidation_SingleCharacter() | 2.1 | 10 min | Test boundary: 1 character should be invalid |
| 2.3 | testNameValidation_TwoCharacters() | 2.2 | 10 min | Test boundary: 2 characters should be valid |
| 2.4 | testNameValidation_WhitespaceOnly() | 2.3 | 10 min | Test " " or "  " should be invalid |
| 2.5 | testNameValidation_ValidName() | 2.4 | 5 min | Test normal valid input |

### Phase 3: Validation Tests - Email Field
**Goal**: Test all email validation scenarios
**Duration**: 45 minutes

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 3.1 | testEmailValidation_EmptyEmail() | 2.5 | 10 min | Verify empty email returns .invalid |
| 3.2 | testEmailValidation_NoAtSign() | 3.1 | 10 min | Test "invalidemail.com" |
| 3.3 | testEmailValidation_NoDomain() | 3.2 | 10 min | Test "user@" |
| 3.4 | testEmailValidation_NoTLD() | 3.3 | 10 min | Test "user@domain" |
| 3.5 | testEmailValidation_ValidEmail() | 3.4 | 5 min | Test "test@example.com" |

### Phase 4: Validation Tests - Category Field
**Goal**: Test category validation scenarios
**Duration**: 30 minutes

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 4.1 | testCategoryValidation_NoSelection() | 3.5 | 15 min | Verify nil category returns .invalid |
| 4.2 | testCategoryValidation_AllCategories() | 4.1 | 15 min | Test each FeedbackCategory case is valid |

### Phase 5: Validation Tests - Description Field
**Goal**: Test description validation scenarios
**Duration**: 45 minutes

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 5.1 | testDescriptionValidation_EmptyDescription() | 4.2 | 10 min | Verify empty description returns .invalid |
| 5.2 | testDescriptionValidation_NineCharacters() | 5.1 | 10 min | Test boundary: 9 characters should be invalid |
| 5.3 | testDescriptionValidation_TenCharacters() | 5.2 | 10 min | Test boundary: 10 characters should be valid |
| 5.4 | testDescriptionValidation_WhitespaceOnly() | 5.3 | 10 min | Test "     " should be invalid |
| 5.5 | testDescriptionValidation_ValidDescription() | 5.4 | 5 min | Test normal valid input |

### Phase 6: Form Validation Tests
**Goal**: Test complete form validation combinations
**Duration**: 45 minutes

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 6.1 | testFormValidation_AllFieldsEmpty() | 5.5 | 10 min | Verify isFormValid returns false |
| 6.2 | testFormValidation_OnlyNameValid() | 6.1 | 10 min | Test partial completion returns false |
| 6.3 | testFormValidation_MissingCategory() | 6.2 | 10 min | All fields except category |
| 6.4 | testFormValidation_InvalidEmail() | 6.3 | 10 min | One invalid field makes form invalid |
| 6.5 | testFormValidation_AllFieldsValid() | 6.4 | 5 min | Verify complete valid form returns true |

### Phase 7: Submit Feedback - Success Cases
**Goal**: Test successful submission scenarios
**Duration**: 60 minutes

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 7.1 | testSubmitFeedback_Success() | 6.5 | 20 min | Mock success response, verify API called correctly |
| 7.2 | testSubmitFeedback_ShowsSuccessMessage() | 7.1 | 15 min | Verify showSuccessMessage = true after success |
| 7.3 | testSubmitFeedback_ResetsFormAfterDelay() | 7.2 | 20 min | Use expectation to test 2-second delay + reset |
| 7.4 | testSubmitFeedback_VerifyRequestBody() | 7.3 | 5 min | Assert API called with correct Feedback model |

### Phase 8: Submit Feedback - Failure Cases
**Goal**: Test error handling scenarios
**Duration**: 60 minutes

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 8.1 | testSubmitFeedback_BackendSuccessFalse() | 7.4 | 15 min | Mock response.success = false, verify error set |
| 8.2 | testSubmitFeedback_NetworkError() | 8.1 | 15 min | Mock APIError, verify handleError called |
| 8.3 | testSubmitFeedback_InvalidFormDoesNotSubmit() | 8.2 | 15 min | Call with empty form, verify API never called |
| 8.4 | testSubmitFeedback_RequiresAuthFalse() | 8.3 | 15 min | Verify requiresAuth parameter is false |

### Phase 9: Loading State Tests
**Goal**: Test loading state management during submission
**Duration**: 30 minutes

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 9.1 | testSubmitFeedback_LoadingStateDuringSubmit() | 8.4 | 15 min | Verify isLoading true during, false after |
| 9.2 | testSubmitFeedback_LoadingStateClearedOnError() | 9.1 | 15 min | Verify isLoading false after error |

### Phase 10: Reset Form Tests
**Goal**: Test form reset functionality
**Duration**: 30 minutes

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 10.1 | testResetForm_ClearsAllFields() | 9.2 | 15 min | Set all fields, call resetForm(), verify cleared |
| 10.2 | testResetForm_ClearsErrorAndSuccessMessage() | 10.1 | 15 min | Verify error and showSuccessMessage cleared |

### Phase 11: Edge Cases and Integration
**Goal**: Test edge cases and complete flows
**Duration**: 45 minutes

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 11.1 | testSubmitFeedback_TrimsWhitespace() | 10.2 | 15 min | Verify leading/trailing whitespace trimmed |
| 11.2 | testSubmitFeedback_WithSpecialCharacters() | 11.1 | 15 min | Test description with emojis, unicode |
| 11.3 | testCompleteSubmissionFlow() | 11.2 | 15 min | Integration test: fill form → submit → verify reset |

### Phase 12: Add Test File to Xcode Project
**Goal**: Ensure test file is properly integrated
**Duration**: 15 minutes

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 12.1 | Run xcode-file-manager skill to add test file | 11.3 | 5 min | Add to AIQTests target |
| 12.2 | Build and run tests | 12.1 | 5 min | Verify all tests pass |
| 12.3 | Verify test coverage | 12.2 | 5 min | Check coverage report |

## Test Categories Summary

### 1. Initialization Tests (1 test)
- testInitialState

### 2. Validation Tests (17 tests)
- Name validation (5 tests)
- Email validation (5 tests)
- Category validation (2 tests)
- Description validation (5 tests)

### 3. Form Validation Tests (5 tests)
- Various combination tests for isFormValid

### 4. Submit Feedback Action Tests (8 tests)
- Success scenarios (4 tests)
- Failure scenarios (4 tests)

### 5. Loading State Tests (2 tests)
- Loading during submission
- Loading cleared on error

### 6. Reset Form Tests (2 tests)
- Clear fields
- Clear error/success state

### 7. Edge Cases and Integration (3 tests)
- Whitespace trimming
- Special characters
- Complete flow

**Total: 38 tests**

## Expected Test Coverage
- **Line Coverage**: 100% of FeedbackViewModel
- **Branch Coverage**: All validation paths and error handling branches
- **Functionality Coverage**: All public methods and computed properties

## Appendix

### Key Testing Resources
- **Existing Test Examples**:
  - `/Users/mattgioe/aiq/ios/AIQTests/ViewModels/RegistrationViewModelTests.swift`
  - `/Users/mattgioe/aiq/ios/AIQTests/ViewModels/LoginViewModelTests.swift`
- **Mock Dependencies**: `/Users/mattgioe/aiq/ios/AIQTests/Mocks/MockAPIClient.swift`
- **Validation Logic**: `/Users/mattgioe/aiq/ios/AIQ/Utilities/Helpers/Validators.swift`
- **Models**: `/Users/mattgioe/aiq/ios/AIQ/Models/Feedback.swift`

### Testing Conventions
1. Use descriptive test names: `test<Method>_<Scenario>_<ExpectedOutcome>`
2. Use Given-When-Then structure in comments (optional but helpful)
3. Use XCTAssert with descriptive failure messages
4. Group related tests with `// MARK: -` comments
5. Use `async`/`await` for testing async methods
6. Use `expectation` for testing delayed operations

### API Endpoint Details
- **Endpoint**: `.submitFeedback` → `/v1/feedback/submit`
- **Method**: POST
- **Auth Required**: false
- **Request Body**: `Feedback` model (name, email, category, description)
- **Response**: `FeedbackSubmitResponse` (success, submissionId, message)

### Validation Requirements Reference
```swift
// From Constants.swift
Constants.Validation.minNameLength = 2
Constants.Validation.minPasswordLength = 8 (not used in Feedback)

// Feedback-specific
Feedback description minimum: 10 characters
Email: Must match regex pattern
Category: Must be non-nil
```
