# AIQ iOS App

Native iOS application for tracking IQ scores over time.

## Setup

```bash
cd ios
open AIQ.xcodeproj
```

In Xcode:
1. Select your development team in project settings (Signing & Capabilities)
2. Choose a simulator or connected device
3. Build and run (⌘+R)

## Features

- **MVVM Architecture**: Clean separation of concerns with BaseViewModel foundation
- **Design System**: Unified color palette, typography, and component styles
- **Accessibility**: Full VoiceOver support, Dynamic Type, semantic colors
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
AIQ/
├── Models/              # Data models
├── ViewModels/          # MVVM ViewModels (inherit from BaseViewModel)
├── Views/               # SwiftUI views by feature
│   ├── Auth/           # Authentication screens
│   ├── Test/           # Test-taking UI
│   ├── Dashboard/      # Home view
│   ├── History/        # Test history and charts
│   ├── Settings/       # Settings and notifications
│   └── Common/         # Reusable components
├── Services/            # Business logic layer
│   ├── Analytics/      # User behavior tracking
│   ├── API/            # Network client with retry and token refresh
│   ├── Auth/           # AuthManager, token management, and push notifications
│   └── Storage/        # Keychain and local storage
└── Utilities/           # Extensions, helpers, and design system
    ├── Design/         # Design system (ColorPalette, Typography, DesignSystem)
    ├── Extensions/     # Swift extensions (Date, String, View)
    └── Helpers/        # Helper utilities (AppConfig, Validators)
```
