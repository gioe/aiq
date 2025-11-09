# iOS App Architecture

## Overview

The IQ Tracker iOS app follows **MVVM (Model-View-ViewModel)** architecture with a clear separation of concerns.

## Architecture Components

### 1. Models

Models represent the data structures used throughout the app. They are typically:
- `Codable` for JSON serialization/deserialization
- `Identifiable` for SwiftUI list rendering
- Immutable (`struct`) when possible
- Match the backend API structure with snake_case to camelCase conversion

**Example:**
```swift
struct User: Codable, Identifiable {
    let id: String
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
- Are organized by feature (Auth, Dashboard, Test, etc.)

**Common Components:**
Reusable UI components are in `Views/Common/`:
- `LoadingView`: Loading indicators
- `ErrorView`: Error display with retry
- `PrimaryButton`: Styled action buttons
- `CustomTextField`: Styled text inputs

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

Services should be injected into ViewModels:

```swift
class LoginViewModel: BaseViewModel {
    private let authService: AuthServiceProtocol

    init(authService: AuthServiceProtocol = AuthService.shared) {
        self.authService = authService
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
- One class/struct per file
- File name matches the type name
- Group related files in directories

### Code Style
- Use SwiftLint and SwiftFormat (configured in project root)
- Follow Swift API Design Guidelines
- Use meaningful variable names
- Add documentation comments for public APIs

## Future Enhancements

- Router/Coordinator pattern for navigation
- Redux-style state management for complex state
- More comprehensive caching strategy
- Offline support

## References

- [Apple's SwiftUI Documentation](https://developer.apple.com/documentation/swiftui/)
- [Swift API Design Guidelines](https://swift.org/documentation/api-design-guidelines/)
