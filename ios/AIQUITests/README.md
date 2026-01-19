# AIQ UI Tests

UI tests for the AIQ iOS application covering authentication flows, test-taking, navigation, and error handling.

## Test Account Setup

Many UI tests require valid backend connectivity and test accounts. This document explains how to configure your environment for running these tests.

### Required Test Accounts

The following test accounts are needed for full UI test coverage:

| Account Type | Purpose | Required Credentials |
|-------------|---------|---------------------|
| **Primary Test User** | Login/logout flows, session persistence | Email + Password |
| **Registration Test** | New user registration flows | Unique email per test run |
| **Existing Email Test** | Duplicate email validation | Pre-registered email |

**Note:** The primary test user must be a valid account registered in the backend environment you're testing against.

### Environment Variables

The UI tests read credentials from environment variables to avoid hardcoding sensitive data in the codebase.

#### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `AIQ_TEST_EMAIL` | Primary test account email | `uitest@example.com` |
| `AIQ_TEST_PASSWORD` | Primary test account password | `SecurePassword123!` |

#### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AIQ_TEST_TIMEOUT` | Custom timeout for network operations | `10` (seconds) |

### Configuring Environment Variables

#### Option 1: Xcode Scheme (Recommended for local development)

1. Open `AIQ.xcodeproj` in Xcode
2. Select **Product** > **Scheme** > **Edit Scheme...**
3. Select **Test** in the left sidebar
4. Select the **Arguments** tab
5. Under **Environment Variables**, add:
   - `AIQ_TEST_EMAIL` = `your-test-email@example.com`
   - `AIQ_TEST_PASSWORD` = `your-test-password`
6. Click **Close**

**Important:** Do not commit scheme changes that include test credentials. Add `.xcscheme` files with credentials to `.gitignore` if needed.

#### Option 2: Shell Environment (CI/CD)

Export variables before running tests:

```bash
export AIQ_TEST_EMAIL="uitest@example.com"
export AIQ_TEST_PASSWORD="SecureTestPassword123!"

xcodebuild test \
  -scheme AIQ \
  -destination 'platform=iOS Simulator,name=iPhone 15' \
  -only-testing:AIQUITests
```

#### Option 3: xcodebuild Arguments

Pass environment variables directly to xcodebuild:

```bash
xcodebuild test \
  -scheme AIQ \
  -destination 'platform=iOS Simulator,name=iPhone 15' \
  -only-testing:AIQUITests \
  AIQ_TEST_EMAIL="uitest@example.com" \
  AIQ_TEST_PASSWORD="SecureTestPassword123!"
```

### Environment-Specific Configuration

#### Local Development

For local development against `http://localhost:8000`:

1. Start the backend locally: `cd backend && uvicorn main:app --reload`
2. Create a test account via the API or UI
3. Configure environment variables with the test account credentials
4. Run tests in DEBUG configuration

#### Staging/Production

For testing against remote environments:

1. Ensure the test account exists in the target environment
2. Use Release configuration for certificate pinning tests
3. Set environment variables with production-valid credentials

### Test Categories

Tests are organized by the level of backend dependency required:

#### No Backend Required
- `testLoginWithInvalidEmailFormat_ShowsValidationError` - Client-side validation
- Element presence tests
- Navigation tests without authentication

#### Backend Required (Skipped by Default)
- `testLoginWithValidCredentials_Success`
- `testLogoutFromSettings_Success`
- `testSessionPersistence_AfterAppRestart`
- All registration flow tests

Tests requiring backend connectivity use `throw XCTSkip()` by default. To enable them:

1. Configure valid test credentials
2. Ensure backend is reachable
3. Remove or comment out the `XCTSkip` statements

### Creating Test Accounts

#### Via Backend API

```bash
# Create a test user via the registration endpoint
curl -X POST https://your-backend-url/v1/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "uitest@example.com",
    "password": "SecureTestPassword123!",
    "first_name": "UI",
    "last_name": "Test"
  }'
```

#### Via iOS App

1. Run the app on a simulator
2. Tap "Create Account"
3. Fill in registration details
4. Note the credentials for test configuration

### Best Practices

1. **Use dedicated test accounts** - Don't use personal or production accounts
2. **Unique emails for registration tests** - Tests generate timestamp-based emails to avoid conflicts
3. **Environment isolation** - Keep test credentials separate per environment
4. **Secure storage** - Use CI/CD secrets management for automated pipelines
5. **Regular cleanup** - Periodically clean up test accounts from staging environments

### Troubleshooting

#### Tests Skip with "Requires backend connection"

The test is designed to skip when:
- No backend is available
- Test credentials are not configured
- Network connectivity issues

**Solution:** Configure environment variables and ensure backend connectivity.

#### "Invalid email or password" Error in Tests

1. Verify the test account exists in the target environment
2. Check that credentials match exactly (case-sensitive password)
3. Confirm the account is not locked or expired

#### Tests Hang on Network Operations

1. Check backend health: `curl https://your-backend-url/v1/health`
2. Verify simulator has network access
3. Check for certificate pinning issues (DEBUG vs RELEASE builds)

#### Element Not Found Errors

1. Review accessibility identifiers in `AccessibilityIdentifiers.swift`
2. Check if UI has changed since tests were written
3. Use Accessibility Inspector to verify element identifiers

### CI/CD Integration

For GitHub Actions or similar CI systems:

```yaml
- name: Run UI Tests
  env:
    AIQ_TEST_EMAIL: ${{ secrets.TEST_EMAIL }}
    AIQ_TEST_PASSWORD: ${{ secrets.TEST_PASSWORD }}
  run: |
    xcodebuild test \
      -scheme AIQ \
      -destination 'platform=iOS Simulator,name=iPhone 15' \
      -only-testing:AIQUITests
```

Store credentials as repository secrets, never in workflow files.

## Related Documentation

- [Helpers/README.md](Helpers/README.md) - UI test helper classes and utilities
- [ios/README.md](../README.md) - Main iOS project documentation
- [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) - App architecture overview
