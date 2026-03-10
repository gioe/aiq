# iOS App Architecture

## Overview

The AIQ iOS app follows **MVVM (Model-View-ViewModel)** architecture with a clear separation of concerns.

## Architecture Components

### 1. Models

Models represent the data structures used throughout the app. They are typically:
- `Codable` for JSON serialization/deserialization
- `Identifiable` for SwiftUI list rendering
- Immutable (`struct`) when possible
- Match the backend API structure with snake_case to camelCase conversion

**Example:**
```swift
struct User: Codable, Identifiable, Equatable {
    let id: Int
    let email: String
    let firstName: String
    // ...
}
```

### 2. ViewModels

ViewModels contain the business logic and state for views. They:
- Conform to `ObservableObject`
- Use `@Published` properties to drive UI updates
- Coordinate with services (API, Auth, Storage)
- Handle errors and loading states
- Should NOT import SwiftUI (except for ObservableObject)

**Base Classes:**
- `ViewModelProtocol`: Protocol defining common ViewModel interface
- `BaseViewModel`: Base class providing common functionality (loading, errors)

**Example:**
```swift
class LoginViewModel: BaseViewModel {
    @Published var email: String = ""
    @Published var password: String = ""

    func login() async {
        setLoading(true)
        // Business logic...
    }
}
```

### 3. Views

Views are SwiftUI views that:
- Display UI based on ViewModel state
- Handle user interactions
- Forward user actions to ViewModels
- Are organized by feature module under `Features/<Module>/Views/`

**Common Components:**
Reusable UI components are in `Views/Components/`:
- `LoadingView`, `LoadingOverlay`: Loading indicators
- `ErrorView`, `ErrorBanner`: Error display with retry
- `EmptyStateView`: Empty state placeholders
- `PrimaryButton`: Styled action buttons
- `CustomTextField`: Styled text inputs
- `NetworkStatusBanner`: Network connectivity indicator
- `MainTabView`, `RootView`, `ContentView`: App navigation structure

**Example:**
```swift
struct LoginView: View {
    @StateObject private var viewModel = LoginViewModel(authManager: AuthManager.shared)

    var body: some View {
        // UI implementation...
    }
}
```

### 4. Services

Services encapsulate external dependencies and business logic:

**API Service (`APIClient`):**
- Handles all network communication
- Manages authentication tokens
- Provides type-safe endpoint definitions
- Handles errors and response parsing

**Auth Service:**
- Manages user authentication
- Stores/retrieves auth tokens securely
- Provides current user state

**Storage Service:**
- Secure storage (Keychain) for sensitive data
- User preferences and settings

### 5. Utilities

**Extensions:**
- `View+Extensions`: SwiftUI view helpers
- `Date+Extensions`: Date formatting utilities
- `String+Extensions`: String validation and manipulation
- `Int+Extensions`: Integer formatting utilities

**Helpers:**
- `AppConfig`: App configuration and environment settings
- `Validators`: Input validation logic

## Data Flow

1. **User Interaction** → View receives user action
2. **View** → Calls method on ViewModel
3. **ViewModel** → Coordinates with Services (API, Auth, etc.)
4. **Services** → Perform operations (network calls, storage, etc.)
5. **Services** → Return results to ViewModel
6. **ViewModel** → Updates `@Published` properties
7. **View** → Automatically re-renders based on changes

## Key Patterns

### Dependency Injection

Services should be injected into ViewModels via protocols:

```swift
class LoginViewModel: BaseViewModel {
    private let authManager: any AuthManagerProtocol

    init(authManager: any AuthManagerProtocol) {
        self.authManager = authManager
        super.init()
    }
}
```

### Error Handling

Errors are handled at the ViewModel level:

```swift
do {
    try await someAsyncOperation()
} catch {
    handleError(error)  // From BaseViewModel
}
```

Views display errors using `ErrorView`:

```swift
if let error = viewModel.error {
    ErrorView(error: error) {
        viewModel.retry()
    }
}
```

### Loading States

Loading states are managed by ViewModels:

```swift
@Published var isLoading: Bool = false

func loadData() async {
    setLoading(true)
    defer { setLoading(false) }
    // ... async work
}
```

Views display loading states using `LoadingView`:

```swift
if viewModel.isLoading {
    LoadingView()
} else {
    // ... content
}
```

### Validation

Input validation uses the `Validators` utility:

```swift
let emailValidation = Validators.validateEmail(email)
if !emailValidation.isValid {
    errorMessage = emailValidation.errorMessage
}
```

## Testing Strategy

- **Unit Tests**: Test ViewModels with mocked services
- **UI Tests**: Test critical user flows (optional for MVP)
- **Integration Tests**: Test Service implementations

## Conventions

### Naming
- Views: `LoginView`, `DashboardView`
- ViewModels: `LoginViewModel`, `DashboardViewModel`
- Services: `AuthService`, `APIClient`
- Models: `User`, `TestResult`

### File Organization

The project uses a **feature-module** layout. Views and ViewModels are co-located inside each feature rather than separated into global `Views/` and `ViewModels/` top-level directories.

```
AIQ/
├── Features/                    # Feature modules — views + view models co-located
│   ├── Auth/
│   │   ├── Views/
│   │   │   ├── WelcomeView.swift
│   │   │   └── RegistrationView.swift
│   │   └── ViewModels/
│   │       ├── LoginViewModel.swift
│   │       └── RegistrationViewModel.swift
│   ├── Dashboard/
│   │   ├── Views/
│   │   │   ├── DashboardView.swift
│   │   │   ├── DashboardActionButton.swift
│   │   │   ├── DashboardWelcomeHeader.swift
│   │   │   ├── InProgressTestCard.swift
│   │   │   └── OnboardingSkippedInfoCard.swift
│   │   └── ViewModels/
│   │       └── DashboardViewModel.swift
│   ├── History/
│   │   ├── Views/
│   │   │   ├── HistoryView.swift
│   │   │   ├── TestDetailView.swift
│   │   │   ├── TestDetailView+Helpers.swift
│   │   │   ├── TestHistoryListItem.swift
│   │   │   ├── IQTrendChart.swift
│   │   │   ├── ChartDomainCalculator.swift
│   │   │   └── InsightsCardView.swift
│   │   └── ViewModels/
│   │       └── HistoryViewModel.swift
│   ├── Onboarding/
│   │   ├── Views/
│   │   │   ├── OnboardingContainerView.swift
│   │   │   ├── PrivacyConsentView.swift
│   │   │   └── Pages/
│   │   │       ├── OnboardingPage1View.swift
│   │   │       ├── OnboardingPage2View.swift
│   │   │       ├── OnboardingPage3View.swift
│   │   │       └── OnboardingPage4View.swift
│   │   └── ViewModels/
│   │       └── OnboardingViewModel.swift
│   ├── Settings/
│   │   ├── Views/
│   │   │   ├── SettingsView.swift
│   │   │   ├── FeedbackView.swift
│   │   │   ├── HelpView.swift
│   │   │   └── NotificationSettingsView.swift
│   │   └── ViewModels/
│   │       ├── SettingsViewModel.swift
│   │       ├── FeedbackViewModel.swift
│   │       └── NotificationSettingsViewModel.swift
│   └── Test/
│       ├── Views/
│       │   ├── AdaptiveTestView.swift
│       │   ├── AdaptiveProgressHeader.swift
│       │   ├── AnswerInputView.swift
│       │   ├── DomainScoresView.swift
│       │   ├── MemoryQuestionView.swift
│       │   ├── PercentileCard.swift
│       │   ├── QuestionCardView.swift
│       │   ├── QuestionContentView.swift
│       │   ├── QuestionNavigationGrid.swift
│       │   ├── TestCompletionView.swift
│       │   ├── TestProgressHeader.swift
│       │   ├── TestProgressView.swift
│       │   ├── TestResultsView.swift
│       │   ├── TestTakingView.swift
│       │   ├── TestTimerModifier.swift
│       │   ├── TestTimerView.swift
│       │   └── TimeWarningBanner.swift
│       └── ViewModels/
│           ├── TestTakingViewModel.swift
│           ├── AdaptiveTestCoordinator.swift
│           ├── QuestionTimeTracker.swift
│           ├── TestNavigationState.swift
│           └── TestTimerManager.swift
├── ViewModels/                  # Shared/cross-cutting ViewModels (app-wide concerns)
│   ├── BaseViewModel.swift          # Base class all ViewModels inherit from
│   ├── ViewModelProtocol.swift      # Common ViewModel protocol
│   ├── AuthStateObserver.swift      # Observes auth state changes across the app
│   ├── NetworkMonitorObserver.swift # Observes network connectivity app-wide
│   └── ToastManagerObserver.swift   # Manages toast notifications app-wide
├── Views/
│   └── Components/              # Shared reusable UI components (cross-feature)
│       ├── RootView.swift           # App root / auth gate
│       ├── ContentView.swift        # Main tab container
│       ├── MainTabView.swift        # Tab bar layout
│       ├── LoadingView.swift
│       ├── LoadingOverlay.swift
│       ├── ErrorView.swift
│       ├── ErrorBanner.swift
│       ├── EmptyStateView.swift
│       ├── PrimaryButton.swift
│       ├── CustomTextField.swift
│       ├── NetworkStatusBanner.swift
│       ├── BiometricLockView.swift
│       ├── ToastView.swift
│       └── ... (other shared components)
├── Models/                      # Codable data structures matching backend API
│   └── Extensions/              # Model helper extensions
├── Services/                    # Business logic and external dependencies
│   ├── API/                     # Network client, token refresh
│   ├── Auth/                    # Authentication, token storage
│   ├── Analytics/               # Analytics tracking
│   ├── Navigation/              # Routing and deep linking
│   ├── Storage/                 # Keychain / UserDefaults
│   └── Background/              # Background task scheduling
└── Utilities/                   # Pure helpers with no feature coupling
    ├── Design/                  # ColorPalette, Typography, DesignSystem
    ├── Extensions/              # Swift / SwiftUI extensions
    ├── Helpers/                 # AppConfig, Validators, etc.
    └── DI/                      # Dependency injection setup
```

**Rule:** New feature views go in `Features/<Module>/Views/`, new feature view models go in `Features/<Module>/ViewModels/`. Components reused across two or more features belong in `Views/Components/`. Cross-cutting ViewModels (not tied to any single feature) go in `ViewModels/`.

- One class/struct per file
- File name matches the type name

### Code Style
- Use SwiftLint and SwiftFormat (configured in project root)
- Follow Swift API Design Guidelines
- Use meaningful variable names
- Add documentation comments for public APIs

## Future Enhancements

- Router/Coordinator pattern for navigation
- Redux-style state management for complex state
- More comprehensive caching strategy

## References

- [Apple's SwiftUI Documentation](https://developer.apple.com/documentation/swiftui/)
- [Swift API Design Guidelines](https://swift.org/documentation/api-design-guidelines/)
