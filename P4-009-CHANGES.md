# P4-009: Add Error Handling for Network Issues

## Summary
This task implements comprehensive error handling for network issues across the iOS app, including:
- Automatic token refresh on 401 errors
- User-friendly error messages with operation context
- Server error message parsing
- Retry functionality for recoverable errors
- Improved timeout and connectivity error handling

## Changes Made

### 1. Enhanced APIError Model (`ios/IQTracker/Models/APIError.swift`)

#### New Features:
- **NetworkOperation enum**: Provides context for errors (login, fetchQuestions, submitTest, etc.)
- **Enhanced APIError cases**: Now include optional server messages
  - `unauthorized(message: String?)`
  - `forbidden(message: String?)`
  - `notFound(message: String?)`
  - `serverError(statusCode: Int, message: String?)`
  - `timeout` - new case for timeout errors
  - `noInternetConnection` - new case for connectivity issues
  - `unknown(message: String?)` - enhanced with optional message

#### Improved Error Messages:
- URLError handling for specific network conditions
- User-friendly messages for common scenarios
- `isRetryable` property to determine if errors can be retried

#### New ContextualError Wrapper:
- Wraps APIError with operation context
- Provides contextual error messages like "Error while loading questions: No internet connection"
- Exposes `isRetryable` property for UI

### 2. Updated APIClient (`ios/IQTracker/Services/API/APIClient.swift`)

#### Response Interceptor Support:
- Added `responseInterceptors` array
- Integrated `TokenRefreshInterceptor` as a response interceptor
- Automatic retry of requests after successful token refresh

#### Server Error Message Parsing:
- `parseErrorMessage(from:)` method extracts server error details
- Parses `ErrorResponse.detail` field from API responses
- Includes server messages in thrown errors

#### Enhanced Error Handling:
- HTTP 408 now throws `APIError.timeout`
- All error cases now include server-provided messages when available
- Better separation of request and response interceptors

#### Token Refresh Integration:
- `setAuthService(_:)` method to configure token refresh
- Handles `TokenRefreshError.shouldRetryRequest` to automatically retry after token refresh

### 3. Enhanced TokenRefreshInterceptor (`ios/IQTracker/Services/Auth/TokenRefreshInterceptor.swift`)

#### ResponseInterceptor Conformance:
- Now conforms to `ResponseInterceptor` protocol
- `intercept(response:data:)` method handles 401 responses

#### Automatic Token Refresh:
- Detects 401 unauthorized responses
- Automatically attempts to refresh the token
- Signals request retry via `TokenRefreshError.shouldRetryRequest`
- Prevents duplicate refresh attempts with task coordination

#### Graceful Degradation:
- Logs out user if token refresh fails
- Wraps refresh failures in `TokenRefreshError.refreshFailed`

### 4. Updated RequestInterceptor (`ios/IQTracker/Services/API/RequestInterceptor.swift`)

#### Simplified ConnectivityInterceptor:
- Uses new `APIError.noInternetConnection` case
- Cleaner, more consistent error handling

### 5. Enhanced BaseViewModel (`ios/IQTracker/ViewModels/BaseViewModel.swift`)

#### Retry Support:
- `@Published var canRetry: Bool` - indicates if error is retryable
- `lastFailedOperation` - stores operation for retry
- `retry()` async method to retry failed operations

#### Improved Error Handling:
- `handleError(_:retryOperation:)` - accepts optional retry closure
- Automatically determines if error is retryable
- Clears retry state when error is cleared

### 6. Updated TestTakingViewModel (`ios/IQTracker/ViewModels/TestTakingViewModel.swift`)

#### Operation Context:
- Wraps errors with `ContextualError` for better messages
- `startTest()` uses `.fetchQuestions` operation context
- `submitTest()` uses `.submitTest` operation context

#### Retry Functionality:
- Both `startTest()` and `submitTest()` provide retry operations
- Users can retry failed network requests
- Maintains operation parameters for retry

#### Improved Validation Messages:
- "No active test session. Please start a new test."
- "Please answer all questions before submitting your test."

### 7. Updated AuthManager (`ios/IQTracker/Services/Auth/AuthManager.swift`)

#### Token Refresh Integration:
- Initializes APIClient with AuthService reference
- Calls `APIClient.shared.setAuthService(authService)` in init

#### Contextual Errors:
- `login()` wraps errors with `.login` operation context
- `register()` wraps errors with `.register` operation context

## Error Flow

### Normal Request Flow:
1. ViewModel calls APIClient
2. Request interceptors run (connectivity check, logging)
3. Request sent to server
4. Response interceptors run
5. Response parsed and returned

### Token Refresh Flow (401 Error):
1. Request returns 401 Unauthorized
2. TokenRefreshInterceptor detects 401
3. Interceptor calls AuthService.refreshToken()
4. New token saved and set on APIClient
5. Interceptor throws `TokenRefreshError.shouldRetryRequest`
6. APIClient catches this error and retries original request
7. Original request succeeds with new token

### Retry Flow (Network Error):
1. Network request fails
2. Error wrapped with operation context
3. ViewModel calls `handleError(_:retryOperation:)`
4. BaseViewModel determines error is retryable
5. Sets `canRetry = true`
6. UI shows retry button
7. User taps retry
8. BaseViewModel calls stored retry operation
9. Original operation executes again

## User-Facing Improvements

### Better Error Messages:
- "Error while loading questions: No internet connection. Please check your network settings and try again."
- "Error while submitting test: Server error: Invalid session ID"
- "Error while signing in: Your session has expired. Please log in again."

### Retry Capability:
- Network errors show retry button
- Server errors (5xx) show retry button
- Timeout errors show retry button
- Non-retryable errors (validation, 404, etc.) don't show retry

### Automatic Token Refresh:
- Seamless experience when token expires
- No manual re-login required for expired tokens
- Automatic logout only if refresh fails

## Testing Recommendations

### Network Conditions:
- Test with airplane mode (no connection)
- Test with slow/unstable connection (timeouts)
- Test with server returning 5xx errors

### Token Expiry:
- Test with expired access token (should auto-refresh)
- Test with expired refresh token (should logout)
- Test with invalid tokens (should logout)

### Retry Functionality:
- Verify retry button appears for network errors
- Verify retry executes the same operation
- Verify retry works for both fetchQuestions and submitTest

### Error Messages:
- Verify server error messages are displayed
- Verify operation context is included
- Verify timeout vs network error messages

## Breaking Changes

### BaseViewModel.handleError Signature:
- Old: `handleError(_ error: Error)`
- New: `handleError(_ error: Error, retryOperation: (() async -> Void)? = nil)`
- **Impact**: Existing calls still work (retryOperation is optional)

### APIError Cases:
- Several cases now include associated values (messages)
- **Impact**: Code that pattern matches on APIError needs updating
- Example: `.unauthorized` → `.unauthorized(message: String?)`

## Files Modified
1. `ios/IQTracker/Models/APIError.swift`
2. `ios/IQTracker/Services/API/APIClient.swift`
3. `ios/IQTracker/Services/Auth/TokenRefreshInterceptor.swift`
4. `ios/IQTracker/Services/API/RequestInterceptor.swift`
5. `ios/IQTracker/ViewModels/BaseViewModel.swift`
6. `ios/IQTracker/ViewModels/TestTakingViewModel.swift`
7. `ios/IQTracker/Services/Auth/AuthManager.swift`

## Next Steps
1. Build and test on iOS simulator
2. Test with mock server returning various error codes
3. Test network interruption scenarios
4. Update UI components to show retry button when `canRetry` is true
5. Add unit tests for error handling logic
6. Add integration tests for token refresh flow
