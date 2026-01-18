# AIQ iOS App

Native iOS application for tracking IQ scores over time.

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
├── docs/                # Documentation
│   ├── CODING_STANDARDS.md       # Development standards and guidelines
│   ├── ARCHITECTURE.md           # Architecture documentation
│   └── SWIFT_OPENAPI_INTEGRATION.md  # OpenAPI generator setup
└── scripts/             # Utility scripts
    ├── add_files_to_xcode.rb    # Add files to Xcode project
    ├── sync_openapi_spec.sh     # Sync OpenAPI spec for code generation
    └── test_rtl.sh              # RTL testing helper
```
