# CI/CD Setup Guide

This document explains the CI/CD pipeline configuration for the AIQ iOS application.

## Overview

The iOS CI/CD pipeline is configured in `.github/workflows/ios-ci.yml` and runs automatically on:
- Pull requests that modify iOS code or the workflow file
- Pushes to the `main` branch

## Pipeline Jobs

### 1. `lint-and-build`

Validates code quality and builds the project.

**Steps:**
1. Checkout code
2. Install SwiftLint and SwiftFormat
3. Run SwiftLint (strict mode)
4. Run SwiftFormat (lint mode)
5. List available simulators
6. Build iOS project
7. Run unit tests (AIQTests target)
8. Upload unit test results on failure

**Duration:** ~5-10 minutes

### 2. `ui-tests`

Runs comprehensive UI tests for the application.

**Dependencies:**
- Requires `lint-and-build` job to pass first
- Uses GitHub Secrets for test credentials

**Steps:**
1. Checkout code
2. List available simulators
3. Create and boot iPhone 16 Pro simulator
4. Run UI tests with credentials from secrets
5. Upload UI test results (both success and failure)

**Duration:** ~15-25 minutes (timeout: 30 minutes)

**Test Coverage:**
- Authentication flow (login/logout)
- Registration flow
- Test-taking flow (complete test flow)
- Test abandonment handling
- Deep link navigation
- Error handling and recovery

## Required GitHub Secrets

The UI tests require two repository secrets to be configured:

### Setting Up Secrets

1. Go to your GitHub repository
2. Navigate to: Settings > Secrets and variables > Actions
3. Click "New repository secret"
4. Add the following secrets:

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `AIQ_TEST_EMAIL` | Email address for test account | `test@example.com` |
| `AIQ_TEST_PASSWORD` | Password for test account | `SecurePassword123!` |

### Test Account Requirements

The test account must:
- Exist in the backend database
- Have valid credentials
- Be accessible from GitHub Actions runners
- Not be used for production data

**Security Note:** These credentials are stored securely by GitHub and are never exposed in logs or PR comments.

## Test Result Artifacts

### Unit Test Results

**Artifact Name:** `ios-unit-test-results`
**Uploaded:** Only on failure
**Retention:** 7 days
**Contents:** xcresult bundle from unit tests

### UI Test Results - Failure

**Artifact Name:** `ui-test-results-failure`
**Uploaded:** Only on test failure
**Retention:** 7 days
**Contents:** xcresult bundle with test logs, screenshots, and performance data

### UI Test Results - Success

**Artifact Name:** `ui-test-results-success`
**Uploaded:** Only on test success
**Retention:** 3 days
**Contents:** xcresult bundle for verification

### Viewing Test Results

1. Go to the failed/successful workflow run in GitHub Actions
2. Scroll to the bottom to the "Artifacts" section
3. Download the appropriate xcresult bundle
4. Open in Xcode:
   ```bash
   open path/to/TestResults.xcresult
   ```

The xcresult bundle contains:
- Detailed test logs
- Screenshots of failures
- Performance metrics
- Code coverage data (if enabled)

## Simulator Configuration

The UI tests use:
- **Device:** iPhone 16 Pro
- **OS:** Latest available iOS version
- **Created dynamically:** New simulator instance for each run
- **Boot verification:** Uses `xcrun simctl bootstatus -b` to ensure ready state

## How Tests Block PRs

1. UI test job runs after build succeeds
2. If any UI test fails, the job fails
3. Failed job appears as a failed check on the PR
4. PR cannot be merged until all checks pass (if branch protection is enabled)

## Troubleshooting

### UI Tests Failing with Authentication Errors

**Cause:** Missing or incorrect GitHub Secrets

**Solution:**
1. Verify secrets are set: Settings > Secrets and variables > Actions
2. Check secret names match exactly: `AIQ_TEST_EMAIL` and `AIQ_TEST_PASSWORD`
3. Verify test account exists in backend
4. Ensure backend is accessible from GitHub Actions runners

### Simulator Boot Timeout

**Cause:** Simulator taking too long to boot

**Solution:**
1. Check GitHub Actions status page for macOS runner issues
2. Re-run the job (temporary infrastructure issue)
3. If persistent, consider increasing timeout in workflow

### Tests Passing Locally but Failing in CI

**Cause:** Environment differences or timing issues

**Solution:**
1. Download xcresult bundle from CI
2. Check for timing issues (network latency, slower CI runners)
3. Review test helper wait timeouts
4. Consider adding explicit waits for UI elements

### Test Artifacts Not Uploading

**Cause:** Path mismatch or test results not generated

**Solution:**
1. Check that `-resultBundlePath` is correct in xcodebuild command
2. Verify tests are actually running (check logs)
3. Ensure `ios/TestResults/` directory is created

## Running UI Tests Locally

To run the same tests locally with credentials:

```bash
cd ios

# Set environment variables
export AIQ_TEST_EMAIL="your-test-email@example.com"
export AIQ_TEST_PASSWORD="your-test-password"

# Run UI tests
xcodebuild test \
  -project AIQ.xcodeproj \
  -scheme AIQ \
  -sdk iphonesimulator \
  -destination 'platform=iOS Simulator,name=iPhone 16 Pro,OS=latest' \
  -only-testing:AIQUITests
```

Or run directly in Xcode:
1. Open AIQ.xcodeproj
2. Product > Scheme > Edit Scheme
3. Select "Test" action
4. Go to Arguments tab
5. Add environment variables:
   - `AIQ_TEST_EMAIL` = your test email
   - `AIQ_TEST_PASSWORD` = your test password
6. Run tests: Cmd+U

## Performance Considerations

### Job Timeouts

- `lint-and-build`: Default (6 hours, unlikely to hit)
- `ui-tests`: 30 minutes

If tests consistently approach timeout:
1. Review test efficiency
2. Consider test parallelization
3. Optimize setup/teardown
4. Remove unnecessary waits

### Artifact Storage

Artifacts consume GitHub storage:
- Free tier: 500 MB storage, 2 GB transfer/month
- Pro tier: 1 GB storage, 10 GB transfer/month

Current retention periods are optimized:
- Failures: 7 days (debugging priority)
- Successes: 3 days (verification only)

## Future Enhancements

Potential improvements to consider:

1. **Test Sharding:** Split UI tests across multiple jobs for faster execution
2. **Flaky Test Retry:** Automatically retry failed tests once
3. **Test Result Comments:** Post test summary as PR comment
4. **Notifications:** Slack/Discord notifications for failures
5. **Code Coverage:** Enable and track code coverage metrics
6. **Test Analytics:** Track test execution time and flakiness over time
7. **Matrix Testing:** Test on multiple iOS versions/devices
8. **Screenshot Comparison:** Visual regression testing

## Related Documentation

- [iOS Coding Standards](/Users/mattgioe/aiq/ios/docs/CODING_STANDARDS.md)
- [UI Test Helpers](/Users/mattgioe/aiq/ios/AIQUITests/Helpers/README.md)
- [Pull Request Template](/.github/PULL_REQUEST_TEMPLATE.md)

## Support

For issues with the CI/CD pipeline:
1. Check this documentation first
2. Review recent workflow runs for patterns
3. Download and inspect xcresult bundles
4. Check GitHub Actions status page
5. Review test logs for specific error messages
