---
name: run-ios-test
description: Run iOS unit tests for the AIQ project. Supports running all tests, a specific test file, or a specific test method. Use this skill whenever you need to verify iOS code changes or run the test suite.
allowed-tools: Bash
---

# Run iOS Test Skill

This skill runs iOS unit tests for the AIQ project using `xcodebuild`.

## Prerequisites

Install `xcpretty` for clean, readable test output:

```bash
gem install xcpretty
# On macOS system Ruby you may need: sudo gem install xcpretty
# Alternatively, use a user-managed Ruby (rbenv/rvm) to install without sudo.
```

**Detecting xcpretty availability:** At invocation time (before running tests), the agent should check whether xcpretty is installed:

```bash
which xcpretty
```

If it exits 0, xcpretty is available — use the xcpretty variant below. Otherwise use the fallback variant (raw `xcodebuild` output, streamed in full without truncation).

## Usage

When this skill is invoked, determine what tests to run based on the user's request or the context.

### Run All Tests

If no specific test is requested, run the full test suite:

```bash
# With xcpretty (recommended) — pipefail ensures test failures propagate correctly
set -o pipefail && cd "$(git rev-parse --show-toplevel)/ios" && xcodebuild test -project AIQ.xcodeproj -scheme AIQ -destination 'platform=iOS Simulator,name=iPhone 16,OS=18.3.1' 2>&1 | xcpretty

# Without xcpretty (fallback — streams full output, no truncation)
cd "$(git rev-parse --show-toplevel)/ios" && xcodebuild test -project AIQ.xcodeproj -scheme AIQ -destination 'platform=iOS Simulator,name=iPhone 16,OS=18.3.1' 2>&1
```

### Run a Specific Test File

To run tests from a specific test class, use the `-only-testing` flag.
Use `AIQTests` for unit tests and `AIQUITests` for UI/integration tests:

```bash
# With xcpretty (recommended) — pipefail ensures test failures propagate correctly
set -o pipefail && cd "$(git rev-parse --show-toplevel)/ios" && xcodebuild test -project AIQ.xcodeproj -scheme AIQ -destination 'platform=iOS Simulator,name=iPhone 16,OS=18.3.1' -only-testing:AIQTests/TestClassName 2>&1 | xcpretty

# Without xcpretty (fallback)
cd "$(git rev-parse --show-toplevel)/ios" && xcodebuild test -project AIQ.xcodeproj -scheme AIQ -destination 'platform=iOS Simulator,name=iPhone 16,OS=18.3.1' -only-testing:AIQTests/TestClassName 2>&1
```

**Examples:**
```bash
# Run AuthManagerTests (unit test — AIQTests target)
-only-testing:AIQTests/AuthManagerTests

# Run APIClientTests (unit test — AIQTests target)
-only-testing:AIQTests/APIClientTests

# Run NotificationServiceTests (unit test — AIQTests target)
-only-testing:AIQTests/NotificationServiceTests

# Run UITests (note: AIQUITests target, not AIQTests)
-only-testing:AIQUITests/LoginUITests
-only-testing:AIQUITests/TestTakingAbandonmentFlowTests
```

### Run a Specific Test Method

To run a single test method within a class:

```bash
# With xcpretty (recommended) — pipefail ensures test failures propagate correctly
set -o pipefail && cd "$(git rev-parse --show-toplevel)/ios" && xcodebuild test -project AIQ.xcodeproj -scheme AIQ -destination 'platform=iOS Simulator,name=iPhone 16,OS=18.3.1' -only-testing:AIQTests/TestClassName/testMethodName 2>&1 | xcpretty

# Without xcpretty (fallback)
cd "$(git rev-parse --show-toplevel)/ios" && xcodebuild test -project AIQ.xcodeproj -scheme AIQ -destination 'platform=iOS Simulator,name=iPhone 16,OS=18.3.1' -only-testing:AIQTests/TestClassName/testMethodName 2>&1
```

**Example:**
```bash
-only-testing:AIQTests/AuthManagerTests/testLoginSuccess
```

### Run Multiple Test Files

Chain multiple `-only-testing` flags to run several test classes:

```bash
# With xcpretty (recommended) — pipefail ensures test failures propagate correctly
set -o pipefail && cd "$(git rev-parse --show-toplevel)/ios" && xcodebuild test -project AIQ.xcodeproj -scheme AIQ -destination 'platform=iOS Simulator,name=iPhone 16,OS=18.3.1' -only-testing:AIQTests/AuthManagerTests -only-testing:AIQTests/APIClientTests 2>&1 | xcpretty

# Without xcpretty (fallback)
cd "$(git rev-parse --show-toplevel)/ios" && xcodebuild test -project AIQ.xcodeproj -scheme AIQ -destination 'platform=iOS Simulator,name=iPhone 16,OS=18.3.1' -only-testing:AIQTests/AuthManagerTests -only-testing:AIQTests/APIClientTests 2>&1
```

## Common Test Classes

| Test Class | Tests For |
|------------|-----------|
| `AuthManagerTests` | Authentication logic |
| `APIClientTests` | API client functionality |
| `NotificationServiceTests` | Push notification handling |
| `AnalyticsServiceTests` | Analytics tracking |
| `KeychainServiceTests` | Keychain operations |
| `DashboardViewModelTests` | Dashboard view model |

## Arguments

When invoked with arguments, parse them to determine the test scope:

- **No arguments**: Run all tests
- **Class name** (e.g., `AuthManagerTests`): Run that test class — but first check if it's an SPM class (see below)
- **Class/method** (e.g., `AuthManagerTests/testLogin`): Run that specific test — same SPM check applies
- **Package path** (e.g., `ios/Packages/APIClient`): Run that SPM package's tests via `swift test` (not `xcodebuild`)

### SPM class name detection

When given a class name (not a path), grep for the test file to determine if it belongs to an SPM package:

```bash
find "$(git rev-parse --show-toplevel)/ios/Packages" -name "<ClassName>.swift" 2>/dev/null | head -1
```

- **If a match is found under `ios/Packages/`**: the class lives in an SPM package. Check the package's `platforms` in its `Package.swift` before choosing a runner (see **iOS-only SPM packages** below). If the package supports macOS, use `swift test --filter`:
  ```bash
  cd <package-root> && swift test --filter <ClassName> 2>&1
  ```
  Example for `AuthenticationMiddlewareTests`:
  ```bash
  cd ios/Packages/APIClient && swift test --filter AuthenticationMiddlewareTests 2>&1
  ```
- **If no match is found under `ios/Packages/`**: the class is in the main `AIQTests` target — use `xcodebuild -only-testing` as usual.

## SPM Package Tests

If the argument is a path to a Swift Package (contains a `Package.swift`), check whether the package is iOS-only before choosing a runner:

```bash
grep -A3 'platforms' <package-path>/Package.swift
```

### iOS-only SPM packages

**`swift test` does not work for packages that only declare `.iOS` platforms.** It compiles for macOS by default and fails with availability errors on every SwiftUI type. This applies to `ios/Packages/SharedKit` (`.iOS(.v16)`).

For iOS-only SPM packages embedded in the Xcode project, tests must be run via `xcodebuild` through the main project — **but only if the test target has been added to `AIQ.xcscheme`'s `<Testables>` section**. If it hasn't, the test target can only be run from Xcode's GUI (Command+U). Check whether the target is in the scheme before proceeding:

```bash
grep -l "<target-name>" "$(git rev-parse --show-toplevel)/ios/AIQ.xcodeproj/xcshareddata/xcschemes/AIQ.xcscheme"
```

- **In scheme**: run via `xcodebuild -only-testing:<TargetName>/<ClassName>`
- **Not in scheme**: inform the user that the test target is not yet wired into the CLI scheme and must be run from Xcode. To add it, a full `PBXNativeTarget` wrapper (Sources + Frameworks build phases) must be added to `project.pbxproj` — editing the xcscheme alone is insufficient. See the **SharedKitTests and the Xcode native target** note in `ios/CLAUDE.md` for the required approach.

### macOS-compatible SPM packages

If the package declares `.macOS` in its platforms list, use `swift test` instead of `xcodebuild`:

```bash
cd <package-path> && swift test 2>&1
```

Example:
```bash
cd ios/Packages/APIClient && swift test 2>&1
```

## Interpreting Results

- **Test Succeeded**: All tests passed
- **Test Failed**: Check the output for failing test names and assertion failures
- **Build Failed**: Compilation errors prevent tests from running; fix build errors first

## Troubleshooting

### Pre-existing Failure Check (for git stash verification)
The full iOS test suite takes 10+ minutes. When verifying that test failures are pre-existing
(via `git stash && <test_command>; git stash pop`), run only the failing test class(es) instead
of the full suite:
```bash
set -o pipefail && cd "$(git rev-parse --show-toplevel)/ios" && xcodebuild test -project AIQ.xcodeproj -scheme AIQ \
  -destination 'platform=iOS Simulator,name=iPhone 16,OS=18.3.1' \
  -only-testing:AIQTests/<FailingTestClass> 2>&1 | xcpretty
```
This keeps the stash check under ~2 minutes and avoids timeouts.

### Simulator Not Found
If the destination simulator isn't available, list available simulators:
```bash
xcrun simctl list devices available
```

Then adjust the `-destination` parameter accordingly.

### Tests Timeout
For long-running tests, consider adding `-test-timeouts-enabled NO` or increasing the default timeout.
