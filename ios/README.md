# AIQ iOS App

Native iOS application for tracking IQ scores over time.

## Setup

**For complete setup instructions**, see [DEVELOPMENT.md](../DEVELOPMENT.md) in the repository root.

Quick start:
```bash
cd ios
open AIQ.xcodeproj
# Select your development team in Xcode, then ⌘+R to build and run
```

## Features

- **MVVM Architecture**: Clean separation of concerns with BaseViewModel foundation
- **Design System**: Unified color palette, typography, and component styles
- **Accessibility**: Full VoiceOver support, Dynamic Type, semantic colors
- **Analytics**: Built-in analytics service for user behavior tracking
- **Push Notifications**: APNs integration for test reminders
- **Offline Support**: Local answer storage during tests

## Architecture

**For detailed architecture documentation**, see [ARCHITECTURE.md](ARCHITECTURE.md).

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
│   ├── API/            # Network client with retry and token refresh
│   ├── Auth/           # AuthManager and token management
│   └── Storage/        # Keychain and local storage
└── Utilities/           # Extensions, helpers, and design system
    ├── Design/         # Design system (ColorPalette, Typography, DesignSystem)
    ├── Extensions/     # Swift extensions (Date, String, View)
    └── Helpers/        # Helper utilities (AppConfig, Validators)
```
