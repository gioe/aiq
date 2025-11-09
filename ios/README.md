# IQ Tracker iOS App

Native iOS application for tracking IQ scores over time.

## Setup

**For complete setup instructions**, see [DEVELOPMENT.md](../DEVELOPMENT.md) in the repository root.

Quick start:
```bash
cd ios
open IQTracker.xcodeproj
# Select your development team in Xcode, then ⌘+R to build and run
```

## Architecture

**For detailed architecture documentation**, see [ARCHITECTURE.md](ARCHITECTURE.md).

The app follows MVVM architecture with:
- **Models**: Data structures (User, Question, TestResult, etc.)
- **ViewModels**: Business logic inheriting from BaseViewModel
- **Views**: SwiftUI views organized by feature
- **Services**: API client, authentication, storage

## Development Commands

```bash
# Build
xcodebuild -scheme IQTracker -destination 'platform=iOS Simulator,name=iPhone 15' build

# Run tests
xcodebuild test -scheme IQTracker -destination 'platform=iOS Simulator,name=iPhone 15'

# Run single test
xcodebuild test -scheme IQTracker -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:IQTrackerTests/TestClass/testMethod
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
swiftformat --config .swiftformat --lint IQTracker/
```

## Project Structure

```
IQTracker/
├── Models/              # Data models
├── ViewModels/          # MVVM ViewModels (inherit from BaseViewModel)
├── Views/               # SwiftUI views by feature
│   ├── Auth/           # Authentication screens
│   ├── Test/           # Test-taking UI
│   ├── Dashboard/      # Home view
│   ├── History/        # Test history and charts
│   ├── Settings/       # Settings
│   └── Common/         # Reusable components
├── Services/            # Business logic layer
│   ├── API/            # Network client
│   ├── Auth/           # AuthManager
│   └── Storage/        # Keychain and local storage
└── Utilities/           # Extensions and helpers
```
