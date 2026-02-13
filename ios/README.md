# AIQ iOS App

Native iOS application for tracking IQ scores over time.

## Project Structure

```
ios/
├── AIQ/                  # Main app source (Views, ViewModels, Services, Models)
├── AIQTests/             # Unit tests
├── AIQUITests/           # UI tests and screenshot generation
├── AIQ.xcodeproj/        # Xcode project file
├── Packages/             # Local Swift packages (AIQAPIClient)
├── scripts/              # iOS tooling (OpenAPI sync, screenshots, validation)
├── docs/                 # iOS-specific documentation
├── app-store/            # App Store metadata and screenshots
├── TestNotifications/    # APNs test payloads
├── .claude/              # Claude Code config for iOS
└── project.yml           # XcodeGen project definition
```

## Setup

```bash
cd ios

# Sync OpenAPI spec for API client code generation (required before first build)
./scripts/sync_openapi_spec.sh

open AIQ.xcodeproj
```

In Xcode:
1. Select your development team in project settings (Signing & Capabilities)
2. Choose a simulator or connected device
3. On first build, approve the OpenAPIGenerator plugin when prompted (click "Trust & Enable")
4. Build and run (⌘+R)

### OpenAPI Client Generation

The iOS app uses Apple's [swift-openapi-generator](https://github.com/apple/swift-openapi-generator) to generate type-safe Swift code from the backend's OpenAPI specification. The generated code is located in the `Packages/AIQAPIClient` local Swift Package.

**The OpenAPI spec (`docs/api/openapi.json`) is the single source of truth** for the API contract between iOS and backend. This ensures:
- Type-safe API calls with build-time verification
- No manual `CodingKeys` mappings (snake_case → camelCase handled by generator)
- Contract drift caught at build time, not runtime

**Important**: The OpenAPI spec file (`openapi.json`) is not committed to the repository. You must run the sync script before building:

```bash
# Sync OpenAPI spec from docs/api/openapi.json to the local package
./scripts/sync_openapi_spec.sh
```

The spec is exported by the backend CI and stored in `docs/api/openapi.json`. If this file doesn't exist, you need to either:
1. Pull latest from main (includes the exported spec)
2. Run the backend locally and export the spec manually:
   ```bash
   cd backend && python export_openapi.py
   ```

**Working with API Changes:**
1. Backend changes Pydantic schemas → CI exports updated OpenAPI spec
2. Pull latest to get the new spec
3. Run `./scripts/sync_openapi_spec.sh` to update the local package
4. Build the project - compilation errors indicate breaking changes
5. Update call sites to match the new contract

For more details, see [docs/SWIFT_OPENAPI_INTEGRATION.md](docs/SWIFT_OPENAPI_INTEGRATION.md).

### Extending Generated Models

The OpenAPI generator creates type-safe Swift structs but doesn't include UI-specific computed properties. Extensions add formatting, display text, and accessibility helpers to generated models.

**Extension Location:** `Packages/AIQAPIClient/Sources/AIQAPIClient/Extensions/`

**Pattern:** Each extension file follows `<TypeName>+UI.swift` naming:

```
Extensions/
├── TestResultResponse+UI.swift      # Score formatting, accessibility
├── ConfidenceIntervalSchema+UI.swift # Range formatting, percentages
├── UserResponse+UI.swift            # Full name, initials
└── QuestionResponse+UI.swift        # Type display, difficulty colors
```

**Why extensions are in the package (not the main app):**
- Generated types and extensions are `public` for access from the main app
- Extensions must be in the same module as the types they extend
- All generated code and extensions are centralized in the API client package

**Adding a new extension:**

1. Check what properties exist in the generated type (run a build first to generate `Types.swift`)
2. Create `<TypeName>+UI.swift` in the Extensions directory
3. Add computed properties for formatting, display, colors, or accessibility
4. Mark properties as `public` for use outside the package

**Example extension pattern:**

```swift
// UserResponse+UI.swift
import Foundation

extension Components.Schemas.UserResponse {
    /// Full name combining first and last name
    public var fullName: String {
        "\(firstName) \(lastName)"
    }
}
```

**IDE Note:** SourceKit may show "Cannot find type 'Components' in scope" errors. This is expected—the generated types only exist after the build plugin runs. The project will compile successfully.

**Date formatting:** Don't add date formatting to package extensions. The main app's `Date+Extensions.swift` provides cached, locale-aware formatters. Package extensions expose raw `Date` properties; format them in the UI layer.

**Current Limitation:** The Swift OpenAPI Generator does not yet generate optional properties that use `anyOf: [type, null]` patterns. Only required properties appear in generated structs. Track [apple/swift-openapi-generator](https://github.com/apple/swift-openapi-generator) for updates.

## Features

- **MVVM Architecture**: Clean separation of concerns with BaseViewModel foundation
- **Design System**: Unified color palette, typography, and component styles
- **Accessibility**: Full VoiceOver support, Dynamic Type, semantic colors
- **RTL Support**: Full Right-to-Left layout support for Arabic and Hebrew
- **Analytics**: Built-in analytics service for user behavior tracking
- **Push Notifications**: APNs integration for test reminders
- **Offline Support**: Local answer storage during tests

## Architecture

**For detailed architecture documentation**, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

The app follows MVVM architecture with:
- **Models**: Data structures (User, Question, TestResult, etc.)
- **ViewModels**: Business logic inheriting from BaseViewModel
- **Views**: SwiftUI views organized by feature
- **Services**: API client, authentication, storage, analytics

## Security

### Certificate Pinning

The app uses TrustKit for SSL certificate pinning to prevent man-in-the-middle (MITM) attacks.

**Build Configuration Behavior:**

| Build Type | Certificate Pinning | API URL | Use Case |
|------------|-------------------|---------|----------|
| DEBUG | Disabled | `http://localhost:8000` | Local development, MITM debugging |
| RELEASE | Enabled & Enforced | `https://aiq-backend-production.up.railway.app` | Production, security testing |

**Key Security Features:**
- TrustKit only initialized in RELEASE builds
- Fail-secure validation (app crashes on invalid config in RELEASE)
- Minimum 2 certificate pins required (primary + backup)
- All API calls blocked if certificates don't match configured pins

**Documentation:**
- Configuration: `ios/AIQ/TrustKit.plist`
- Testing Guide: [docs/CERTIFICATE_PINNING_TESTING.md](docs/CERTIFICATE_PINNING_TESTING.md)
- Implementation: [docs/CODING_STANDARDS.md - Security Section](docs/CODING_STANDARDS.md#security)

**Testing Certificate Pinning Locally:**
1. Edit Scheme → Run → Build Configuration → Release
2. Build and run (⌘+R)
3. Verify console shows: "TrustKit initialized with certificate pinning"
4. Test API calls against production backend
5. Return to DEBUG configuration for normal development

## Push Notifications (APNs)

The app uses Apple Push Notification service (APNs) for test reminders.

For server-side APNs configuration and token management, see [Backend Documentation](../backend/README.md).

### APNs Environment Configuration

**Entitlements file:** `AIQ/AIQ.entitlements`

The `aps-environment` entitlement controls which APNs environment the app connects to:

| Environment | Use Case | Where to Configure |
|-------------|----------|-------------------|
| `production` | App Store, TestFlight builds | Default in `AIQ.entitlements` |
| `development` | Local development with push notifications | Change manually for testing |

**Current setting:** `production` (required for App Store builds)

### Switching Environments for Local Development

If you need to test push notifications locally against the APNs sandbox:

1. Open `AIQ/AIQ.entitlements`
2. Change `aps-environment` from `production` to `development`
3. Build and run on a physical device (push notifications don't work on simulator)
4. **Important:** Revert to `production` before committing

```xml
<!-- For local push notification testing -->
<key>aps-environment</key>
<string>development</string>

<!-- For App Store / TestFlight (default) -->
<key>aps-environment</key>
<string>production</string>
```

**Note:** The backend must send notifications to the correct APNs environment. Production builds require the production APNs endpoint; development builds require the sandbox endpoint. See backend documentation for server-side APNs configuration.

## Universal Links

The app supports Universal Links for seamless deep linking from web URLs to app screens.

### How It Works

Universal Links allow URLs like `https://aiq.app/test/results/123` to open directly in the app instead of Safari. This requires coordination between:
1. **iOS app** - Declares which domains it handles via Associated Domains entitlement
2. **Apple Developer Portal** - Enables Associated Domains capability for the app
3. **Web server** - Hosts an `apple-app-site-association` (AASA) file proving domain ownership

### Supported URL Patterns

| URL Pattern | Action |
|------------|--------|
| `https://aiq.app/test/results/{id}` | View specific test results |
| `https://aiq.app/test/resume/{sessionId}` | Resume a test session |
| `https://aiq.app/settings` | Open settings |

Custom URL scheme equivalents (`aiq://...`) are also supported.

### iOS App Configuration

**Entitlements file:** `AIQ/AIQ.entitlements`

The Associated Domains entitlement declares which domains the app handles:
```xml
<key>com.apple.developer.associated-domains</key>
<array>
    <string>applinks:aiq.app</string>
    <string>applinks:dev.aiq.app</string>
</array>
```

| Domain | Purpose |
|--------|---------|
| `aiq.app` | Production domain |
| `dev.aiq.app` | Development/staging domain for testing Universal Links |

**Code implementation:**
- `DeepLinkHandler.swift` - Parses URLs into structured navigation commands
- `AppDelegate.swift` - Receives universal links via `application(_:continue:restorationHandler:)`

### Apple Developer Portal Configuration

To enable Universal Links for a new app or team:

1. Sign in to [Apple Developer Portal](https://developer.apple.com/account)
2. Go to **Certificates, Identifiers & Profiles** → **Identifiers**
3. Select the App ID (`com.aiq.app`)
4. Under **Capabilities**, enable **Associated Domains**
5. Click **Save**

When building with Xcode:
- Xcode automatically syncs the capability with your provisioning profile
- Ensure your signing team has the Associated Domains capability enabled

### Server-Side Configuration (AASA File)

The server must host an `apple-app-site-association` file that tells iOS which apps can handle URLs for the domain.

**Required location:** `https://aiq.app/.well-known/apple-app-site-association`

**File format (iOS 14+ recommended):**
```json
{
  "applinks": {
    "details": [
      {
        "appIDs": ["TEAMID.com.aiq.app"],
        "components": [
          { "/": "/test/results/*" },
          { "/": "/test/resume/*" },
          { "/": "/settings" }
        ]
      }
    ]
  }
}
```

**Note:** Replace `TEAMID` with your actual 10-character Apple Developer Team ID (e.g., `ABCD123456`).

**Server requirements:**
- File must be served over HTTPS with a valid certificate
- Content-Type should be `application/json` (or `application/pkcs7-mime` for signed AASA files)
- File must be accessible without redirects (except HTTPS upgrade)
- No authentication required to access the file

**Development domain (`dev.aiq.app`):**

For Universal Links to work in staging environments, the dev domain needs its own AASA file:
- **Required location:** `https://dev.aiq.app/.well-known/apple-app-site-association`
- **Content:** Same format as production, with the same Team ID and Bundle ID

**Validate deployment:**
```bash
# Validate production domain (requires APNS_TEAM_ID env var)
./ios/scripts/validate-universal-links.sh

# Validate development domain
./ios/scripts/validate-universal-links.sh --team-id ABCD123456 --dev

# Or with explicit domain
./ios/scripts/validate-universal-links.sh --team-id ABCD123456 --domain aiq.app
```

### Troubleshooting

**Links open in Safari instead of the app:**
1. Verify the AASA file is accessible: `curl https://aiq.app/.well-known/apple-app-site-association`
2. Check the Team ID + Bundle ID combination matches exactly
3. Delete and reinstall the app (iOS caches AASA on first install)
4. Check device console for "swcd" (Site Association Daemon) errors

**AASA file validation fails:**
- Ensure the file is valid JSON (no trailing commas)
- Verify Content-Type header is `application/json`
- Check that Team ID is exactly 10 alphanumeric characters
- Run the validation script for detailed diagnostics

**Universal Links work on simulator but not device:**
- Simulator may have different caching behavior
- Ensure the app is signed with a profile that has Associated Domains enabled
- Check that the domain in entitlements matches the AASA file exactly

**Deep links work but navigation fails:**
- Check `DeepLinkHandler` is parsing the URL correctly
- Verify the app router is connected (`appRouter` in `AppDelegate`)
- Check console logs for parsing errors

**Testing Universal Links:**
1. Install the app on a device (not simulator for most accurate testing)
2. Send yourself a link via Messages or Notes
3. Tap the link - it should open the app directly
4. Long-press the link to see "Open in AIQ" option

## Development Commands

```bash
# Build
xcodebuild -scheme AIQ -destination 'platform=iOS Simulator,name=iPhone 15' build

# Run tests
xcodebuild test -scheme AIQ -destination 'platform=iOS Simulator,name=iPhone 15'

# Run single test
xcodebuild test -scheme AIQ -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:AIQTests/TestClass/testMethod
```

## Code Quality Tools

The project uses SwiftLint and SwiftFormat (pre-commit hooks configured).

Install tools:
```bash
brew install swiftlint swiftformat
```

Run manually:
```bash
swiftlint lint --config .swiftlint.yml
swiftformat --config .swiftformat --lint AIQ/
```

## Project Structure

```
ios/
├── AIQ/                 # Main app target
│   ├── Models/              # Data models
│   ├── ViewModels/          # MVVM ViewModels (inherit from BaseViewModel)
│   ├── Views/               # SwiftUI views by feature
│   │   ├── Auth/           # Authentication screens
│   │   ├── Test/           # Test-taking UI
│   │   ├── Dashboard/      # Home view
│   │   ├── History/        # Test history and charts
│   │   ├── Settings/       # Settings and notifications
│   │   └── Common/         # Reusable components
│   ├── Services/            # Business logic layer
│   │   ├── Analytics/      # User behavior tracking
│   │   ├── API/            # Network client with retry and token refresh
│   │   ├── Auth/           # AuthManager, token management, and push notifications
│   │   └── Storage/        # Keychain and local storage
│   └── Utilities/           # Extensions, helpers, and design system
│       ├── Design/         # Design system (ColorPalette, Typography, DesignSystem)
│       ├── Extensions/     # Swift extensions (Date, String, View)
│       └── Helpers/        # Helper utilities (AppConfig, Validators)
├── Packages/            # Local Swift Packages
│   └── AIQAPIClient/       # OpenAPI-generated type-safe API client
│       └── Extensions/     # UI computed properties for generated types
├── docs/                # Documentation
│   ├── CODING_STANDARDS.md       # Development standards and guidelines
│   ├── ARCHITECTURE.md           # Architecture documentation
│   └── SWIFT_OPENAPI_INTEGRATION.md  # OpenAPI generator setup
└── scripts/             # Utility scripts
    ├── add_files_to_xcode.rb    # Add files to Xcode project
    ├── sync_openapi_spec.sh     # Sync OpenAPI spec for code generation
    └── test_rtl.sh              # RTL testing helper
```
