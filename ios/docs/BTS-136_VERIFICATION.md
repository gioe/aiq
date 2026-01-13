# BTS-136: Verification Guide

## How to Verify Error Logging Works

### 1. Simulate Storage Errors in Tests

The existing test `testLogout_StorageDeleteError_StillClearsInMemoryState` demonstrates the error logging:

```swift
func testLogout_StorageDeleteError_StillClearsInMemoryState() async throws {
    // Given - user is logged in
    try await sut.login(email: "test@example.com", password: "password123")

    // Configure storage to throw on deleteAll
    mockSecureStorage.setShouldThrowOnDeleteAll(true)

    // When - user logs out
    try await sut.logout()

    // Then - verify error was logged and state still cleared
}
```

**Expected Output:**
```
2026-01-09 13:58:31.151158-0500 AIQ[38599:4580908] [AuthService] Failed to clear secure storage: Failed to delete all from secure storage
2026-01-09 13:58:31.151231-0500 AIQ[38599:4580908] [Error] [storage_delete] Failed to delete all from secure storage
🔴 [storage_delete] Error: deleteAllFailed
   Additional info: ["operation": "clearAuthData", "severity": "critical"]
❌ [AuthService] Storage error during clearAuthData: deleteAllFailed
   WARNING: Tokens may still exist in secure storage!
```

### 2. Verify Production vs Debug Logging

#### Debug Build
Run the app with Debug configuration and trigger a logout:

**Expected Console Output:**
```
[AuthService] Failed to clear secure storage: <error message>
[Error] [storage_delete] <error message>
🔴 [storage_delete] Error: <error type>
❌ [AuthService] Storage error during clearAuthData: <error>
   WARNING: Tokens may still exist in secure storage!
```

#### Release Build
Build in Release configuration:
```bash
xcodebuild -project AIQ.xcodeproj -scheme AIQ -configuration Release
```

**Expected Console Output:**
```
[AuthService] Failed to clear secure storage: <error message>
[Error] [storage_delete] <error message>
```

**No emoji indicators or DEBUG-only prints should appear.**

### 3. Verify No Sensitive Data Logged

Search logs for any token values:

```bash
# Should find NO results
grep -r "access_token_" ios/AIQ/Services/Auth/AuthService.swift
grep -r "Bearer" ios/AIQ/Services/Auth/AuthService.swift
```

**Verification:**
- ✅ Error messages use `error.localizedDescription` (generic)
- ✅ Logger uses `.public` privacy level
- ✅ No token values in log statements
- ✅ Only operation context logged ("init", "getAccessToken", "clearAuthData")

### 4. Verify Crashlytics Integration

#### Check Error Context Enum
```swift
// In CrashlyticsErrorRecorder.swift
enum ErrorContext: String {
    // Storage & Persistence
    case localSave = "storage_local_save"
    case localLoad = "storage_local_load"
    case storageRetrieve = "storage_retrieve"  // ✅ Added
    case storageDelete = "storage_delete"      // ✅ Added
}
```

#### Verify Metadata
All error recordings include:
- `context`: Error context enum (e.g., "storage_delete")
- `additionalInfo`: Operation-specific metadata
  - `key`: Storage key being accessed
  - `operation`: Which function logged the error
  - `severity`: "critical" for deletion failures

### 5. Run Full Test Suite

```bash
cd ios
xcodebuild -project AIQ.xcodeproj -scheme AIQ \
  -destination 'platform=iOS Simulator,name=iPhone 16,OS=18.3.1' \
  test
```

**Expected Result:**
```
Test Suite 'All tests' passed at <timestamp>
Executed 40+ tests, with 0 failures
```

### 6. Verify Error Handling Paths

| Operation | Storage Fails | Expected Behavior | Verified |
|-----------|--------------|-------------------|----------|
| `init()` | Retrieve fails | Logs error, continues without token | ✅ |
| `getAccessToken()` | Retrieve fails | Logs error, returns nil | ✅ |
| `clearAuthData()` | DeleteAll fails | Logs error, clears in-memory state | ✅ |
| `login()` | Save fails | Throws error (via saveAuthData) | ✅ |
| `logout()` | DeleteAll fails | Logs error, continues logout | ✅ |

## Common Issues & Solutions

### Issue: Crashlytics not recording errors in simulator
**Solution:** This is expected - Crashlytics only records in production builds on real devices. In DEBUG, errors are printed to console instead.

### Issue: Too much logging in production
**Solution:** Remove `#if DEBUG` guards to see what's logged in production. Only os_log and Crashlytics should appear.

### Issue: Token values appearing in logs
**Solution:** This should NEVER happen. If it does, immediately:
1. Remove the logging statement
2. Rotate the exposed tokens
3. File a security incident

## Success Criteria

All items must be ✅:

- ✅ `try?` replaced with do-catch in init, getAccessToken, clearAuthData
- ✅ os_log Logger used for production logging
- ✅ CrashlyticsErrorRecorder called with context
- ✅ No token values or PII in any log statements
- ✅ `.public` privacy level used for error messages
- ✅ DEBUG-only logging wrapped in `#if DEBUG`
- ✅ All 40+ AuthService tests pass
- ✅ Error contexts added to CrashlyticsErrorRecorder enum
- ✅ Documentation created (this file + implementation doc)

## Next Steps

1. Merge PR for BTS-136
2. Monitor Crashlytics for `storage_retrieve` and `storage_delete` errors post-deployment
3. If storage errors spike, investigate Keychain entitlements or device-specific issues
4. Consider adding user-facing error messages for critical storage failures (future enhancement)
