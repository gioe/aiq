# AIQ iOS Coding Standards

This document outlines the coding standards and best practices for the AIQ iOS application. These standards ensure consistency, maintainability, and quality across the codebase.

**This document is the single source of truth for iOS development decisions.** The ios-engineer agent is authorized to update this document when Apple best practices change, gaps are discovered, or corrections are needed.

## How to Read This Document

- **Required Standards** (main sections): Follow strictly. These reflect the current codebase patterns.
- **Recommended Enhancements** (end of document): Consider for new code. When implemented, promote to required standards.

---

## Table of Contents

- [Project Structure](#project-structure)
- [Architecture Patterns](#architecture-patterns)
- [UI-First Development Workflow](#ui-first-development-workflow)
- [Naming Conventions](#naming-conventions)
- [SwiftUI Best Practices](#swiftui-best-practices)
- [State Management](#state-management)
  - [Navigation Path Management](#navigation-path-management)
  - [Badge Management Patterns](#badge-management-patterns)
- [Error Handling](#error-handling)
  - [Operation-Specific Error Properties](#operation-specific-error-properties)
  - [Fatal Errors vs. Recoverable Errors](#fatal-errors-vs-recoverable-errors)
  - [Validation Philosophy](#validation-philosophy)
  - [Parsing and Validation Utilities](#parsing-and-validation-utilities)
  - [Localization for Error Messages](#localization-for-error-messages)
  - [Date and Time Edge Cases](#date-and-time-edge-cases)
- [Networking](#networking)
- [Design System](#design-system)
- [Documentation](#documentation)
  - [Documenting Lifecycle and Concurrency Constraints](#documenting-lifecycle-and-concurrency-constraints)
- [Testing](#testing)
  - [Test Isolation and Shared Resources](#test-isolation-and-shared-resources)
  - [Testing Factory Methods and Initialization](#testing-factory-methods-and-initialization)
  - [Test Helper Anti-Patterns](#test-helper-anti-patterns)
- [Code Formatting](#code-formatting)
- [Accessibility](#accessibility)
- [Concurrency](#concurrency)
  - [Main Actor Synchronization and Race Conditions](#main-actor-synchronization-and-race-conditions)
  - [Cross-Actor Property Access](#cross-actor-property-access)
  - [Background Task Execution Patterns](#background-task-execution-patterns)
- [Performance](#performance)
- [Security](#security)
- [Third-Party Dependencies](#third-party-dependencies)
  - [Criteria for Adding Dependencies](#criteria-for-adding-dependencies)
  - [Swift Package Manager vs CocoaPods](#swift-package-manager-vs-cocoapods)
  - [Version Pinning Strategy](#version-pinning-strategy)
  - [Dependency Update Process](#dependency-update-process)
  - [Security Audit Requirements](#security-audit-requirements)
  - [Evaluating Dependency Health](#evaluating-dependency-health)
  - [Documentation Requirements](#documentation-requirements)
- [CI/CD Pipeline](#cicd-pipeline)
- [Git and Version Control](#git-and-version-control)
- [Recommended Enhancements](#recommended-enhancements)

---

## Project Structure

### Current Organization

The project follows a **hybrid type-and-feature** structure. Top-level directories are organized by architectural layer (Models, ViewModels, Views, Services), with feature-based organization nested within Views:

```
AIQ/
├── Models/              # Data models and domain entities
├── ViewModels/          # MVVM ViewModels (all inherit from BaseViewModel)
├── Views/               # SwiftUI views organized by feature
│   ├── Auth/           # Authentication screens
│   ├── Test/           # Test-taking UI
│   ├── Dashboard/      # Home/Dashboard views
│   ├── History/        # Test history and charts
│   ├── Settings/       # Settings and preferences
│   └── Common/         # Reusable view components
├── Services/            # Business logic and external dependencies
│   ├── Analytics/      # Analytics tracking
│   ├── API/            # Network layer
│   ├── Auth/           # Authentication and notifications
│   ├── Navigation/     # Routing and deep linking
│   └── Storage/        # Data persistence
└── Utilities/           # Cross-cutting concerns
    ├── Design/         # Design system (colors, typography, spacing)
    ├── Extensions/     # Swift extensions
    └── Helpers/        # Utility functions and configurations
```

### Standards

**DO:**
- Keep Models, ViewModels, and Views in their respective top-level directories
- Organize Views by feature subdirectories (Auth/, Dashboard/, etc.)
- Place reusable view components in `Views/Common/`
- Keep the design system in `Utilities/Design/`
- Put cross-cutting extensions in `Utilities/Extensions/`
- Name ViewModels to match their corresponding View feature (e.g., `DashboardViewModel` for `Dashboard/`)

**DON'T:**
- Create additional top-level directories (e.g., `Controllers/`, `Managers/`)
- Mix business logic with view code
- Place feature-specific components in `Common/`
- Put ViewModels inside View feature folders (keep them in top-level `ViewModels/`)

---

## Architecture Patterns

### MVVM (Model-View-ViewModel)

The app strictly follows MVVM architecture with the following responsibilities:

#### Models
Data structures representing domain entities. Should be:
- Immutable when possible (prefer `struct` over `class`)
- `Codable` for API serialization
- `Equatable` and `Identifiable` when needed for SwiftUI

```swift
struct TestResult: Codable, Identifiable, Equatable {
    let id: Int
    let iqScore: Int
    let completedAt: Date
    // ... other properties

    enum CodingKeys: String, CodingKey {
        case id
        case iqScore = "iq_score"
        case completedAt = "completed_at"
    }
}
```

#### ViewModels
Business logic layer that:
- Inherits from `BaseViewModel`
- Marked with `@MainActor` for UI updates
- Contains all business logic and state
- Uses `@Published` properties for observable state
- Handles API calls and error management
- Never imports `SwiftUI` (UIKit is acceptable for utilities)

```swift
@MainActor
class DashboardViewModel: BaseViewModel {
    @Published var latestTestResult: TestResult?
    @Published var testCount: Int = 0

    private let apiClient: APIClientProtocol

    init(apiClient: APIClientProtocol = APIClient.shared) {
        self.apiClient = apiClient
        super.init()
    }

    func fetchDashboardData() async {
        setLoading(true)
        clearError()

        do {
            let response: PaginatedTestHistoryResponse = try await apiClient.request(
                endpoint: .testHistory(limit: nil, offset: nil),
                method: .get,
                requiresAuth: true
            )
            updateDashboardState(with: response.results)
        } catch {
            handleError(error, context: .fetchDashboard)
        }

        setLoading(false)
    }
}
```

#### Views
SwiftUI views that:
- Are purely declarative
- Observe ViewModels using `@StateObject` or `@ObservedObject`
- Contain NO business logic
- Use the Design System for styling
- Break down into smaller subviews for readability

```swift
struct DashboardView: View {
    @StateObject private var viewModel = DashboardViewModel()

    var body: some View {
        ZStack {
            if viewModel.isLoading {
                LoadingView(message: "Loading dashboard...")
            } else if let error = viewModel.error {
                ErrorView(error: error) {
                    Task { await viewModel.retry() }
                }
            } else {
                dashboardContent
            }
        }
        .task {
            await viewModel.fetchDashboardData()
        }
    }

    private var dashboardContent: some View {
        // View implementation
    }
}
```

### BaseViewModel Pattern

All ViewModels MUST inherit from `BaseViewModel` which provides:
- Loading state management (`isLoading`)
- Error handling with retry capability (`error`, `canRetry`)
- Crashlytics error recording
- Combine cancellables management

```swift
// In ViewModel
handleError(error, context: .fetchDashboard) {
    await self.fetchDashboardData()
}

// In View
if viewModel.canRetry {
    Button("Retry") {
        Task { await viewModel.retry() }
    }
}
```

#### Validation Error Helpers

`BaseViewModel` provides reusable helper methods for field validation error properties, eliminating boilerplate code. These helpers return `nil` if the field is empty (before user interaction) and the error message only if the field is non-empty and invalid.

**Basic Field Validation:**
```swift
var emailError: String? {
    validationError(for: email, using: Validators.validateEmail)
}

var passwordError: String? {
    validationError(for: password, using: Validators.validatePassword)
}
```

**For validators with extra parameters (use a closure):**
```swift
var firstNameError: String? {
    validationError(for: firstName, using: { Validators.validateName($0, fieldName: "First name") })
}
```

**For password confirmation (two-value comparison):**
```swift
var confirmPasswordError: String? {
    validationError(for: confirmPassword, matching: password, using: Validators.validatePasswordConfirmation)
}
```

This pattern reduces ~5 lines of boilerplate per field to a single line while maintaining consistent behavior across all ViewModels.

### Protocol-Oriented Design

Use protocols for:
- Dependency injection (e.g., `APIClientProtocol`, `AuthServiceProtocol`)
- Testability (allows mocking)
- Flexibility in implementation

```swift
protocol APIClientProtocol {
    func request<T: Decodable>(
        endpoint: APIEndpoint,
        method: HTTPMethod,
        body: Encodable?,
        requiresAuth: Bool
    ) async throws -> T
}

// In ViewModel
private let apiClient: APIClientProtocol

init(apiClient: APIClientProtocol = APIClient.shared) {
    self.apiClient = apiClient
}
```

---

## UI-First Development Workflow

When implementing full-stack features that span iOS and backend, follow a **UI-first development approach**. This workflow ensures better UX outcomes, clearer API contracts, and fewer integration issues.

### Why UI-First?

1. **Better UX outcomes**: Starting with UI forces consideration of user interactions and data display needs before backend implementation
2. **Clearer API contracts**: Mock data in iOS reveals exactly what fields and types the backend must provide
3. **Parallel development**: Once iOS establishes the contract via mock data, backend development can proceed in parallel
4. **Reduced rework**: Changes to data structures are cheaper to make during UI prototyping than after backend implementation

### UI-First Process

#### Step 1: Prototype the UI with Mock Data

Create the full user experience using hardcoded mock data. This step should include:

- Complete SwiftUI views with realistic layout and styling
- ViewModels with `@Published` properties matching expected data shapes
- User interactions (buttons, forms, navigation) wired up locally
- Loading states, error states, and empty states

```swift
// Example: Mock data during prototyping
// (FeatureItem and featureItems are placeholders - use your actual model/endpoint)
class FeatureViewModel: BaseViewModel {
    @Published var items: [FeatureItem] = [
        FeatureItem(id: 1, title: "Mock Item 1", value: 42),
        FeatureItem(id: 2, title: "Mock Item 2", value: 87)
    ]

    func fetchItems() async {
        // TODO: Replace with API call
        // Mock data already loaded
    }
}
```

#### Step 2: Document the API Contract

Based on the mock data, document what the backend must provide:

- **Request format**: HTTP method, endpoint path, request body structure
- **Response format**: Field names (snake_case for JSON), types, optionality
- **Error scenarios**: What errors can occur and how iOS will handle them

This documentation can live in the PR description or a brief spec file.

#### Step 3: Implement Backend API

With a clear contract from the iOS prototype:

- Implement the endpoint matching the documented contract
- Use Pydantic schemas that match the iOS model expectations
- Write tests that verify response structure matches the contract

#### Step 4: Wire Up the Real API

Replace mock data with actual API calls:

```swift
// After backend is ready
// (Replace placeholder endpoint/context with your actual values)
func fetchItems() async {
    setLoading(true)
    clearError()

    do {
        let response: [FeatureItem] = try await apiClient.request(
            endpoint: .featureItems,  // Add to APIEndpoint enum
            method: .get,
            requiresAuth: true
        )
        self.items = response
    } catch {
        handleError(error, context: .fetchFeatureItems)  // Add to ErrorContext enum
    }

    setLoading(false)
}
```

#### Step 5: Integration Testing

Test the complete flow end-to-end:

- Verify data displays correctly from real API
- Test error scenarios
- Confirm loading states work as designed

### Handling Already-Implemented APIs

When the backend API already exists:

1. **Read the API documentation or code** to understand the response format
2. **Create iOS models that match exactly** (field names, types, optionality)
3. **Test with real data early** to catch any mismatches
4. **Avoid assuming** - verify response structure with actual calls

### Common Anti-Patterns to Avoid

| Anti-Pattern | Problem | Better Approach |
|--------------|---------|-----------------|
| Backend-first development | UI needs discovered late, causing rework | Start with UI mock, document contract |
| Optional fields for required data | Runtime crashes when API returns nil | Match optionality to API reality |
| Mismatch in field naming | Decoding failures | Use CodingKeys for snake_case ↔ camelCase |
| Untested integration | Bugs found in production | Test against real API before merging |

---

## Naming Conventions

### Files

- **Swift files**: PascalCase matching the primary type (e.g., `DashboardViewModel.swift`)
- **Extensions**: `TypeName+Extension.swift` (e.g., `Int+Extensions.swift`)
- **Protocols**: Descriptive name with Protocol suffix (e.g., `AuthServiceProtocol.swift`)
- **Test files**: `ClassNameTests.swift` (e.g., `DashboardViewModelTests.swift`)

### Types

- **Classes/Structs/Enums**: PascalCase (e.g., `DashboardViewModel`, `TestResult`)
- **Protocols**: PascalCase with descriptive name, typically ending in `-able` or `-Protocol` (e.g., `APIClientProtocol`, `Codable`)
- **Enums**: PascalCase for type, camelCase for cases

```swift
enum QuestionType: String, Codable {
    case pattern
    case logic
    case spatial
}
```

### Properties and Methods

- **Properties**: camelCase (e.g., `latestTestResult`, `isLoading`)
- **Methods**: camelCase, verb-based (e.g., `fetchDashboardData()`, `handleError()`)
- **Boolean properties**: Use `is`, `has`, `should` prefix (e.g., `isLoading`, `hasActiveTest`, `shouldRetry`)
- **Private properties**: camelCase with no prefix (rely on access control)

### Constants

- **Static constants**: camelCase within an enum or static let
- **Design tokens**: Organized in enums (e.g., `DesignSystem.Spacing.lg`)

```swift
enum ColorPalette {
    static let primary = Color.accentColor
    static let background = Color(uiColor: .systemBackground)
}
```

### Acronyms

Keep acronyms lowercase except when starting a name:
- Good: `apiClient`, `iqScore`, `URLSession`
- Bad: `APIClient`, `IQScore`, `urlSession`

### Delegate Protocols

Name delegate protocols to describe the delegating type and the role:

```swift
// Good - describes the source and role
protocol DashboardViewModelDelegate: AnyObject {
    func dashboardViewModel(_ viewModel: DashboardViewModel, didUpdateScore score: Int)
    func dashboardViewModelDidFinishLoading(_ viewModel: DashboardViewModel)
}

protocol TestSessionDataSource: AnyObject {
    func numberOfQuestions(in session: TestSession) -> Int
    func testSession(_ session: TestSession, questionAt index: Int) -> Question
}

// Bad - vague or missing context
protocol DashboardDelegate { }  // Which dashboard?
protocol DataDelegate { }       // Too generic
```

**Delegate method naming conventions:**
- Include the delegating object as the first parameter
- Use past tense for notifications (`didUpdate`, `didFinish`)
- Use future tense for permission requests (`shouldAllow`, `willBegin`)

### Factory Methods

Use the `make` prefix for factory methods that create and return new instances:

```swift
// Good - clear factory pattern
struct ViewModelFactory {
    func makeDashboardViewModel() -> DashboardViewModel
    func makeTestSessionViewModel(for test: Test) -> TestSessionViewModel
}

extension UIView {
    static func makeLoadingIndicator() -> UIActivityIndicatorView
}

// Bad - unclear intent
func getDashboardViewModel() -> DashboardViewModel  // "get" implies retrieval, not creation
func createViewModel() -> DashboardViewModel        // less idiomatic in Swift
func dashboardViewModel() -> DashboardViewModel     // ambiguous
```

**When to use `make`:**
- Static factory methods returning new instances
- Builder pattern methods
- Dependency injection container methods

### Fluent API Methods

For chainable APIs, name methods to read naturally when chained:

```swift
// Good - reads like a sentence
let request = URLRequest(url: endpoint)
    .setting(\.httpMethod, to: "POST")
    .addingHeader("Content-Type", value: "application/json")
    .settingTimeout(30)

// Good - builder pattern
let alert = AlertBuilder()
    .withTitle("Error")
    .withMessage("Something went wrong")
    .withPrimaryAction("OK")
    .build()

// Bad - doesn't read naturally
let request = URLRequest(url: endpoint)
    .setHttpMethod("POST")      // imperative, not descriptive
    .headerAdd("Content-Type")  // awkward word order
```

**Guidelines for fluent APIs:**
- Use present participles (`adding`, `setting`, `with`) for methods that return modified copies
- Return `Self` to enable chaining
- Keep method names short but descriptive

### Mutating and Non-Mutating Method Pairs

Follow Swift standard library conventions for mutating/non-mutating pairs:

```swift
// Standard pattern: verb (mutating) / past participle (non-mutating)
extension Array {
    mutating func sort()      // Mutates in place
    func sorted() -> [Element] // Returns new sorted array

    mutating func reverse()
    func reversed() -> [Element]

    mutating func shuffle()
    func shuffled() -> [Element]
}

// Applied to custom types
extension TestResults {
    mutating func filter(by category: Category)
    func filtered(by category: Category) -> TestResults

    mutating func normalize()
    func normalized() -> TestResults
}
```

**Naming rules:**
- Mutating: Use imperative verb (`sort`, `reverse`, `append`)
- Non-mutating: Use past participle (`sorted`, `reversed`, `appended`) or noun form

### Closure and Callback Parameters

Name closure parameters to describe what they do, not their type:

```swift
// Good - describes the closure's purpose
func fetchData(completion: @escaping (Result<Data, Error>) -> Void)
func animate(duration: TimeInterval, animations: () -> Void, completion: ((Bool) -> Void)?)
func process(items: [Item], transform: (Item) -> ProcessedItem)

// Good - specific names for multiple closures
func performRequest(
    onSuccess: (Response) -> Void,
    onFailure: (Error) -> Void,
    onProgress: (Double) -> Void
)

// Bad - generic or type-focused names
func fetchData(handler: @escaping (Result<Data, Error>) -> Void)  // "handler" is vague
func fetchData(closure: @escaping (Result<Data, Error>) -> Void)  // describes type, not purpose
func fetchData(callback: @escaping (Result<Data, Error>) -> Void) // acceptable but less specific
```

**Common closure parameter names:**
- `completion` - for async operations that finish
- `transform` - for mapping operations
- `predicate` - for filtering conditions
- `configure` - for configuration closures
- `onSuccess`/`onFailure` - for split result handling

### Generic Type Parameters

Use descriptive names for generic type parameters beyond single letters:

```swift
// Good - single letter for simple, obvious generics
func swap<T>(_ a: inout T, _ b: inout T)
struct Box<T> { let value: T }

// Good - descriptive names for complex generics
struct Cache<Key: Hashable, Value> {
    func store(_ value: Value, forKey key: Key)
}

protocol DataStore<Model, Identifier> {
    func fetch(by id: Identifier) -> Model?
}

func transform<Input, Output>(_ input: Input, using transformer: (Input) -> Output) -> Output

// Standard conventions
// T, U, V - arbitrary types (use sparingly)
// Element - collection element type
// Key, Value - dictionary-like types
// Model - data model types
// Identifier/ID - unique identifier types
// Source, Destination - transformation types
// Request, Response - API types
```

**Guidelines:**
- Use `T` only when the type's role is obvious from context
- Use descriptive names when there are 2+ type parameters
- Follow standard library conventions (`Element`, `Key`, `Value`)

---

## SwiftUI Best Practices

### Property Wrappers

Use the correct property wrapper for each scenario:

| Wrapper | Use Case |
|---------|----------|
| `@State` | Local view state owned by the view |
| `@StateObject` | ViewModel or ObservableObject owned by the view |
| `@ObservedObject` | ViewModel or ObservableObject passed from parent |
| `@EnvironmentObject` | Shared dependency injected into environment |
| `@Binding` | Two-way binding to parent's state |
| `@Environment` | System environment values |
| `@AppStorage` | Simple values persisted to UserDefaults (must conform to RawRepresentable) |

```swift
struct DashboardView: View {
    @StateObject private var viewModel = DashboardViewModel()  // Owned by this view
    @Environment(\.appRouter) var router                       // Environment dependency

    var body: some View {
        // Implementation
    }
}

struct StatCard: View {
    @Binding var value: String  // Two-way binding to parent

    var body: some View {
        // Implementation
    }
}

struct MainTabView: View {
    @AppStorage("com.aiq.selectedTab") private var selectedTab: TabDestination = .dashboard  // Persisted to UserDefaults

    var body: some View {
        TabView(selection: $selectedTab) {
            // Implementation
        }
    }
}
```

#### Common Property Wrapper Anti-Patterns

**Never use `@StateObject` with singletons:**

```swift
// Wrong - StateObject implies ownership of a singleton's lifecycle
@StateObject private var authManager = AuthManager.shared

// Correct - ObservedObject observes an externally-managed singleton
@ObservedObject private var authManager = AuthManager.shared
```

**Why?** `@StateObject` tells SwiftUI the view owns the object's lifecycle (creating/destroying it with the view). Singletons like `.shared` manage their own lifecycle and should use `@ObservedObject` instead.

**Rule of thumb:**
- Creating a new instance → `@StateObject private var vm = MyViewModel()`
- Referencing a singleton → `@ObservedObject private var manager = Manager.shared`

#### @AppStorage Best Practices

`@AppStorage` provides automatic persistence to UserDefaults with built-in invalid value handling. Understanding how it works prevents unnecessary validation code.

**How @AppStorage Works:**

1. **On initialization**: Reads from UserDefaults using the specified key
2. **If stored value is valid**: Uses the stored value
3. **If stored value is invalid or missing**: Uses the default value provided
4. **On change**: Automatically writes to UserDefaults

**DO:**
- Use `@AppStorage` for simple value types that conform to `RawRepresentable` (Int, String, Bool, enums with raw values)
- Provide a default value that will be used if the stored value is invalid or missing
- Trust `@AppStorage` to handle invalid values automatically
- Use consistent key naming with reverse-DNS notation (e.g., `"com.aiq.selectedTab"`)

**DON'T:**
- Manually validate or "fix" stored values in `.onAppear` (duplicate effort - `@AppStorage` already handled it)
- Access the same UserDefaults key directly with `UserDefaults.standard` (creates two sources of truth)
- Duplicate storage key strings in validation logic (maintenance hazard)
- Try to "clean up" invalid values with `removeObject(forKey:)` (happens too late, `@AppStorage` already initialized)

**Example - Correct Usage:**

```swift
struct MainTabView: View {
    // @AppStorage automatically handles invalid values by using default
    @AppStorage("com.aiq.selectedTab") private var selectedTab: TabDestination = .dashboard

    var body: some View {
        TabView(selection: $selectedTab) {
            // Tab content...
        }
        .onAppear {
            // No validation needed - @AppStorage already handled it
            router.currentTab = selectedTab
        }
    }
}
```

**Anti-Pattern - Unnecessary Validation:**

```swift
// ❌ BAD - Duplicates key, mixed access, unnecessary complexity
struct MainTabView: View {
    @AppStorage("com.aiq.selectedTab") private var selectedTab: TabDestination = .dashboard

    var body: some View {
        TabView(selection: $selectedTab) {
            // Tab content...
        }
        .onAppear {
            // ALL OF THIS IS UNNECESSARY:
            let storedKey = "com.aiq.selectedTab"  // ❌ Duplicate key declaration
            let storedValue = UserDefaults.standard.integer(forKey: storedKey)  // ❌ Mixed access
            if TabDestination(rawValue: storedValue) == nil {
                UserDefaults.standard.removeObject(forKey: storedKey)  // ❌ @AppStorage already handled this
            }
            router.currentTab = selectedTab
        }
    }
}

// ✅ GOOD - Trust @AppStorage to handle edge cases
struct MainTabView: View {
    @AppStorage("com.aiq.selectedTab") private var selectedTab: TabDestination = .dashboard

    var body: some View {
        TabView(selection: $selectedTab) {
            // Tab content...
        }
        .onAppear {
            router.currentTab = selectedTab  // Simple and correct
        }
    }
}
```

**Why Manual Validation is Problematic:**

1. **Timing Issue**: Validation in `.onAppear` happens after `@AppStorage` has already initialized and handled invalid values
2. **Duplicate Effort**: `@AppStorage` already fell back to the default if value was invalid
3. **Two Sources of Truth**: Mixing `@AppStorage` with direct `UserDefaults` access creates confusion
4. **Maintenance Burden**: Duplicating key strings means changes must be made in multiple places
5. **No Benefit**: The validation doesn't affect the already-loaded value

**When Manual Access Might Be Justified:**

Manual UserDefaults access might be appropriate in rare cases:
- **Migration**: Converting from old storage format to new format (one-time operation)
- **Diagnostic Logging**: Logging when invalid values are encountered (for debugging, not to "fix" them)
- **Complex Transformation**: Data requires transformation before use that `@AppStorage` can't handle

**Example - Legitimate Diagnostic Logging:**

```swift
.onAppear {
    // Optional: Log if we encountered an invalid stored value (debugging only)
    // Note: This is purely diagnostic - @AppStorage already handled it
    if let storedInt = UserDefaults.standard.integer(forKey: "com.aiq.selectedTab") as Int?,
       storedInt != 0,  // 0 means "not set"
       TabDestination(rawValue: storedInt) == nil {
        logger.debug("Encountered invalid stored tab value: \(storedInt). Using default (.dashboard).")
        // Don't try to "fix" it - @AppStorage already used the default
    }

    router.currentTab = selectedTab
}
```

Even in this diagnostic case, the logging happens after `@AppStorage` initialization, so it's purely for observability.

### View Decomposition

Break large views into smaller, focused subviews:

```swift
struct DashboardView: View {
    var body: some View {
        ScrollView {
            VStack(spacing: DesignSystem.Spacing.xxl) {
                welcomeHeader
                statsGrid
                latestTestCard
                actionButton
            }
        }
    }

    // MARK: - Subviews

    private var welcomeHeader: some View {
        VStack(spacing: DesignSystem.Spacing.md) {
            // Header implementation
        }
    }

    private var statsGrid: some View {
        HStack(spacing: DesignSystem.Spacing.lg) {
            // Stats implementation
        }
    }
}
```

### Event Handler Refactoring

When multiple event handlers (`.onReceive`, `.onChange`, `.onAppear`) share the same logic, extract it into a private helper method:

```swift
// ❌ Bad: Duplicate navigation logic in two handlers
.onReceive(NotificationCenter.default.publisher(for: .deepLinkReceived)) { notification in
    guard let deepLink = notification.userInfo?["deepLink"] as? DeepLink else { return }
    Task {
        switch deepLink {
        case .settings:
            selectedTab = .settings
            // ... 15+ lines of navigation logic
        }
    }
}
.onReceive(NotificationCenter.default.publisher(for: .notificationTapped)) { notification in
    // ... payload extraction ...
    let deepLink = deepLinkHandler.parse(url)
    Task {
        switch deepLink {
        case .settings:
            selectedTab = .settings
            // ... same 15+ lines duplicated
        }
    }
}

// ✅ Good: Extract shared logic into a helper method
.onReceive(NotificationCenter.default.publisher(for: .deepLinkReceived)) { notification in
    guard let deepLink = notification.userInfo?["deepLink"] as? DeepLink else { return }
    handleDeepLinkNavigation(deepLink)
}
.onReceive(NotificationCenter.default.publisher(for: .notificationTapped)) { notification in
    // ... payload extraction ...
    let deepLink = deepLinkHandler.parse(url)
    handleDeepLinkNavigation(deepLink)
}

// MARK: - Private Helpers

private func handleDeepLinkNavigation(_ deepLink: DeepLink) {
    Task {
        switch deepLink {
        case .settings:
            selectedTab = .settings
            // ... navigation logic in one place
        }
    }
}
```

**Guidelines:**
- Extract logic when it exceeds ~10 lines or is used in multiple handlers
- Keep handler bodies focused on event-specific extraction/validation
- Use descriptive method names that indicate the action (e.g., `handleDeepLinkNavigation`, `processNotificationPayload`)
- Place helper methods in a `// MARK: - Private Helpers` section

### ViewModifiers

Extract reusable styling into ViewModifiers:

```swift
struct CardStyle: ViewModifier {
    func body(content: Content) -> some View {
        content
            .padding(DesignSystem.Spacing.lg)
            .background(ColorPalette.backgroundSecondary)
            .cornerRadius(DesignSystem.CornerRadius.lg)
            .shadow(
                color: Color.black.opacity(0.1),
                radius: DesignSystem.Shadow.lg.radius
            )
    }
}

extension View {
    func cardStyle() -> some View {
        modifier(CardStyle())
    }
}
```

### Previews

Always include SwiftUI previews for views and components:

```swift
#Preview {
    DashboardView()
}

#Preview("Multiple States") {
    VStack(spacing: 20) {
        PrimaryButton(title: "Normal", action: {})
        PrimaryButton(title: "Loading", action: {}, isLoading: true)
        PrimaryButton(title: "Disabled", action: {}, isDisabled: true)
    }
    .padding()
}
```

---

## State Management

### Published Properties

Mark all observable state with `@Published`:

```swift
@MainActor
class DashboardViewModel: BaseViewModel {
    @Published var latestTestResult: TestResult?
    @Published var testCount: Int = 0
    @Published var isRefreshing: Bool = false
}
```

### Computed Properties

Use computed properties for derived state:

```swift
var hasTests: Bool {
    testCount > 0
}

var latestTestDateFormatted: String? {
    guard let latest = latestTestResult else { return nil }
    let formatter = DateFormatter()
    formatter.dateStyle = .medium
    return formatter.string(from: latest.completedAt)
}
```

### State Updates

Always update UI state on the main actor:

```swift
@MainActor
func updateState() {
    isLoading = false
    latestTestResult = result
}
```

### Navigation Path Management

When working with `NavigationPath` in `AppRouter`, follow these patterns to avoid edge cases and ensure clean navigation state.

**DO:**
- Use `setPath(NavigationPath(), for: tab)` to clear/reset navigation for a tab
- This creates a clean navigation state and avoids edge cases

**DON'T:**
- Mutate path by removing items and then setting it
- Use `path.removeLast(count)` patterns that risk edge cases

**Example:**

```swift
// ✅ Good - Clean navigation reset
func popToRoot(in tab: TabDestination) {
    setPath(NavigationPath(), for: tab)
}

// ❌ Bad - Manual removal with edge case risks
func popToRoot(in tab: TabDestination) {
    var path = path(for: tab)
    path.removeLast(path.count)  // What if count is calculated incorrectly?
    setPath(path, for: tab)
}
```

**Why This Matters:**
- `NavigationPath` doesn't expose its count property publicly, making validation difficult
- Manual removal can crash if count exceeds path depth
- Creating a new `NavigationPath()` is more explicit and self-documenting
- The copy-modify-set pattern for `NavigationPath` uses Swift's copy-on-write semantics, so it's efficient, but the simpler pattern is still preferred for `popToRoot`

### Badge Management Patterns

App badges require centralized coordination when multiple sources (notifications, background refresh, unread counts) can update the badge. Without coordination, badge values overwrite each other unpredictably.

#### The Problem

```swift
// ❌ WRONG - Multiple sources overwriting each other
class BackgroundRefreshManager {
    func sendTestNotification() {
        content.badge = 1  // Overwrites any existing badge
    }
}

class MessageService {
    func updateUnreadCount(_ count: Int) {
        UIApplication.shared.applicationIconBadgeNumber = count  // Overwrites test notification badge
    }
}
```

#### Centralized Badge Management

Use a single manager to coordinate badge state:

```swift
// ✅ CORRECT - Centralized badge coordination
@MainActor
class BadgeManager: ObservableObject {
    static let shared = BadgeManager()

    @Published private(set) var totalBadgeCount: Int = 0

    private var unreadMessages: Int = 0
    private var pendingTests: Int = 0
    private var otherNotifications: Int = 0

    func updateUnreadMessages(_ count: Int) {
        unreadMessages = count
        recalculateBadge()
    }

    func updatePendingTests(_ count: Int) {
        pendingTests = count
        recalculateBadge()
    }

    func clearAll() {
        unreadMessages = 0
        pendingTests = 0
        otherNotifications = 0
        recalculateBadge()
    }

    private func recalculateBadge() {
        totalBadgeCount = unreadMessages + pendingTests + otherNotifications
        UIApplication.shared.applicationIconBadgeNumber = totalBadgeCount
    }
}
```

#### Notification Badge Pattern

When sending local notifications, **do not set the badge directly**. Let the app update badges when it becomes active:

```swift
// ✅ CORRECT - Don't set badge in notification content
func sendTestAvailableNotification() {
    let content = UNMutableNotificationContent()
    content.title = "New Test Available"
    content.body = "Your cognitive assessment is ready"
    content.sound = .default
    // Note: We don't set badge here. Badge is updated when app becomes active.
    content.userInfo = ["type": "test_reminder"]

    // Schedule notification...
}

// In SceneDelegate or AppDelegate:
func sceneDidBecomeActive(_ scene: UIScene) {
    // Centralized badge update when app becomes active
    Task {
        await BadgeManager.shared.refreshBadgeCount()
    }
}

// ❌ WRONG - Setting badge in notification
func sendTestAvailableNotification() {
    let content = UNMutableNotificationContent()
    content.badge = 1  // Overwrites other badge sources
}
```

#### When Badge Coordination Matters

| App Complexity | Recommended Approach |
|----------------|---------------------|
| Single badge source | Direct badge setting is OK |
| Multiple badge sources | Centralized BadgeManager required |
| Background notifications | Don't set badge in content, update on app active |

---

## Error Handling

### APIError Enum

Use the centralized `APIError` enum for all API-related errors:

```swift
enum APIError: Error, LocalizedError {
    case invalidURL
    case unauthorized(message: String?)
    case networkError(Error)
    case decodingError(Error)
    // ... other cases

    var errorDescription: String? {
        // User-friendly error messages
    }

    var isRetryable: Bool {
        // Determine if error can be retried
    }
}
```

### Error Handling in ViewModels

Use `BaseViewModel.handleError()` for consistent error handling:

```swift
do {
    let result = try await apiClient.request(...)
    // Handle success
} catch {
    handleError(error, context: .fetchDashboard) { [weak self] in
        await self?.fetchDashboardData()  // Retry closure
    }
}
```

### Memory Management in Error Handlers

**CRITICAL:** Always use `[weak self]` in retry closures passed to `handleError()` to avoid retain cycles.

The retry closure is stored in `BaseViewModel.lastFailedOperation`, which creates a retain cycle if `self` is captured strongly:

```swift
// ❌ WRONG - Creates retain cycle
handleError(error, context: .fetchDashboard) {
    await self.fetchDashboardData()  // Strong capture of self
}

// ✅ CORRECT - Breaks retain cycle
handleError(error, context: .fetchDashboard) { [weak self] in
    await self?.fetchDashboardData()  // Weak capture + optional chaining
}
```

**Why this matters:**
- `handleError()` stores the retry closure in `BaseViewModel.lastFailedOperation`
- Without `[weak self]`, creates: `ViewModel → lastFailedOperation → closure → ViewModel`
- This retain cycle prevents the ViewModel from being deallocated
- Use optional chaining (`self?`) so retry becomes a no-op if ViewModel is deallocated

### Error Display in Views

Use `ErrorView` for displaying errors with retry capability:

```swift
if let error = viewModel.error {
    ErrorView(error: error) {
        Task { await viewModel.retry() }
    }
}
```

### Operation-Specific Error Properties

ViewModels inherit `error` from BaseViewModel for general error display. However, some operations require **operation-specific error properties** for contextual UI alerts. This is a valid pattern when used appropriately.

#### When to Use BaseViewModel's `error` Property (Default)

Use the inherited `error` property and `handleError()` for most operations:

```swift
do {
    let result = try await apiClient.request(...)
    // Handle success
} catch {
    handleError(error, context: .fetchDashboard) { [weak self] in
        await self?.fetchDashboardData()  // Retry closure
    }
}

// In View - Uses standard error display:
if let error = viewModel.error {
    ErrorView(error: error) {
        Task { await viewModel.retry() }
    }
}
```

#### When to Use Operation-Specific Error Properties

Use a separate error property when:
- The operation needs a **specific alert title/message** distinct from general errors
- The UI requires **separate error state** for a particular action (e.g., confirmation dialogs)
- The operation's error should **not affect** BaseViewModel's retry state or general error display
- Multiple independent operations could fail and need distinct error handling

**Example - Delete Account with Specific Alert:**

```swift
// In ViewModel:
@Published var deleteAccountError: Error?

func deleteAccount() async {
    isDeletingAccount = true
    deleteAccountError = nil  // Clear previous delete error
    clearError()  // Clear general errors

    do {
        try await authManager.deleteAccount()
        isDeletingAccount = false
    } catch {
        deleteAccountError = error  // Operation-specific error
        isDeletingAccount = false
        // NOTE: Using operation-specific error because:
        // - Delete account needs a specific "Delete Account Failed" alert title
        // - This error shouldn't affect general error state or retry logic
        // - AuthManager already logs this error to Crashlytics
    }
}

func clearDeleteAccountError() {
    deleteAccountError = nil
}

// In View - Specific alert for delete operation:
.alert("Delete Account Failed", isPresented: Binding(
    get: { viewModel.deleteAccountError != nil },
    set: { if !$0 { viewModel.clearDeleteAccountError() } }
)) {
    Button("OK") {}
} message: {
    if let error = viewModel.deleteAccountError {
        Text(error.localizedDescription)
    }
}
```

#### Pattern Comparison

| Pattern | Use When | Example |
|---------|----------|---------|
| `handleError()` with retry | Operation is retryable, uses standard error UI | Dashboard fetch, API calls |
| Operation-specific error | Operation needs custom alert title/message | Delete account, logout confirmation |
| Service error binding | ViewModel observes service error state | LoginViewModel binding to AuthManager |

#### Documenting Error Handling Decisions

When using operation-specific error properties, **document why** in a comment:

```swift
// ✅ Good - Explains the architectural decision
} catch {
    deleteAccountError = error
    // NOTE: Using operation-specific error instead of handleError() because:
    // - Delete account needs a specific "Delete Account Failed" alert title
    // - This error shouldn't affect general error state or retry logic
    // - AuthManager already logs this error to Crashlytics
}

// ❌ Bad - States what but not why
} catch {
    deleteAccountError = error
    // We don't need to call handleError here since we're setting deleteAccountError
}
```

### Crashlytics Integration

All errors handled through `BaseViewModel.handleError()` are automatically recorded to Crashlytics with context:

```swift
handleError(error, context: .login)  // Provides context for debugging
```

### Fatal Errors vs. Recoverable Errors

Use `fatalError()` for programmer errors that should never occur in production. These are configuration or development mistakes, not runtime errors.

**DO use `fatalError()`:**
- Dependency injection failures (service not registered)
- Invalid enum cases that should be exhaustive
- Required resources missing from bundle
- Precondition violations in critical paths
- Factory methods when required dependencies are missing

**DON'T use `fatalError()`:**
- User input validation failures
- Network request failures
- File system errors
- Any error that could occur during normal operation

**Example - Factory Methods:**

```swift
// ✅ Good - fatalError for programmer error (missing DI registration)
func makeDashboardViewModel(container: ServiceContainer) -> DashboardViewModel {
    guard let apiClient = container.resolve(APIClientProtocol.self) else {
        fatalError("APIClientProtocol not registered in ServiceContainer")
    }
    return DashboardViewModel(apiClient: apiClient)
}

// ❌ Bad - fatalError for user/runtime error
func parseUserInput(_ input: String) -> Configuration {
    guard let data = input.data(using: .utf8) else {
        fatalError("Invalid input encoding")  // Wrong! This can happen at runtime
    }
    // ...
}

// ✅ Good - throw for user/runtime error
func parseUserInput(_ input: String) throws -> Configuration {
    guard let data = input.data(using: .utf8) else {
        throw ConfigurationError.invalidEncoding
    }
    // ...
}
```

**Why This Distinction Matters:**
- `fatalError()` crashes the app immediately - appropriate for "this should never happen" scenarios
- Throws/errors allow graceful recovery - appropriate for "this might happen" scenarios
- Using `fatalError()` for runtime errors gives users a poor experience
- Using throws for programmer errors allows bugs to propagate silently

### Validation Philosophy

#### Client vs. Server Validation Responsibilities

Understanding where validation belongs prevents unnecessary duplication and maintains clear architectural boundaries.

**Server Validation (Backend)**:
- Input sanitization (trim whitespace, normalize data)
- Business rule enforcement (ranges, formats, relationships)
- Data integrity constraints (uniqueness, foreign keys)
- Persistent state validation

**Client Validation (iOS)**:
- User input validation (before sending to server)
- UI/UX feedback (real-time form validation)
- Type safety (Swift model constraints)
- Crash prevention (guard against nil in critical paths)

#### When to Add Model Validation

Add validation to iOS models when:
1. **Preventing Critical Failures**: Empty strings that would crash UI rendering
2. **Type Constraints**: Values that violate fundamental assumptions (negative time)
3. **Test Reliability**: Ensuring test fixtures don't create invalid states

Do NOT add validation when:
1. **Backend Already Validates**: Trust server-side constraints (IDs, timestamps)
2. **No User Input Path**: Data only comes from backend API
3. **Defensive Programming**: Guarding against impossible conditions
4. **Duplicating Server Logic**: Whitespace trimming, format normalization

#### Helper Method Extraction

Extract validation into helper methods when:
- Validation logic exceeds ~10 lines
- Same validation used in 3+ places
- Complex business rules requiring documentation
- Validation involves multiple fields or dependencies

Keep validation inline when:
- Single guard statement (e.g., `guard !text.isEmpty`)
- Only used in init() and init(from decoder:)
- Validation is self-documenting

**Example - Keep Inline**:
```swift
guard !questionText.isEmpty else {
    throw QuestionValidationError.emptyQuestionText
}
```

**Example - Extract Helper**:
```swift
// If validation were complex:
private static func validateQuestionConstraints(
    text: String,
    options: [String]?,
    type: QuestionType
) throws {
    // 15+ lines of complex validation logic
}
```

#### Input Sanitization Patterns

**User Input (Registration, Forms)**: Always sanitize
```swift
// User provides birth year
let trimmed = birthYearText.trimmingCharacters(in: .whitespaces)
let birthYear = Int(trimmed)
```

**Backend Data (API Responses)**: Trust and validate for crashes only
```swift
// Question Model: Backend provides data
guard !questionText.isEmpty else {
    throw QuestionValidationError.emptyQuestionText
}
// No trimming - backend is source of truth
```

### Parsing and Validation Utilities

When creating utilities that parse external input (strings, files, network data), follow these safety guidelines to avoid silent failures.

#### Failable Initializers for Parsing

Use failable initializers (`init?`) that return `nil` for invalid input instead of returning default/fallback values:

```swift
// ✅ Good - Explicit failure
extension Color {
    /// Creates a color from a hex string
    /// - Returns: A Color if valid (3, 6, or 8 hex digits), nil otherwise
    init?(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0

        guard Scanner(string: hex).scanHexInt64(&int) else {
            return nil  // Explicit failure
        }

        guard [3, 6, 8].contains(hex.count) else {
            return nil  // Invalid format
        }

        // ... parsing logic
        self.init(.sRGB, red: r, green: g, blue: b, opacity: a)
    }
}

// Usage with fallback - caller decides the default
let color = Color(hex: userInput) ?? .black
```

```swift
// ❌ Bad - Silent failure
init(hex: String) {
    // ... parsing logic

    // Returns black for invalid input - hides bugs!
    (alpha, red, green, blue) = (255, 0, 0, 0)
}
```

#### Validation Before Processing

For functions that process input, validate early and throw or return errors:

```swift
func parseConfiguration(_ json: String) throws -> Configuration {
    guard !json.isEmpty else {
        throw ConfigurationError.emptyInput
    }

    guard let data = json.data(using: .utf8) else {
        throw ConfigurationError.invalidEncoding
    }

    // Continue with valid input
}
```

#### Why This Matters

Silent failures in parsing utilities create bugs that are:
- **Hard to debug**: No error is thrown, so failures go unnoticed
- **Non-obvious**: Developers may not realize input was invalid
- **Production-impacting**: Malformed data can cause UI issues or incorrect behavior

By making parsing functions failable or throwing errors, you make invalid states unrepresentable and force callers to handle error cases explicitly.

### Localization for Error Messages

When creating new error types that use `LocalizedError`, you MUST add the corresponding localization string to `Localizable.strings`. Missing localization keys will display as raw key strings to users.

#### Checklist for Adding New Errors

When adding a new error enum or case:

- [ ] Define the error enum/case with `LocalizedError` conformance
- [ ] Add the localization key to `AIQ/en.lproj/Localizable.strings`
- [ ] Place it in the appropriate `// MARK: - Service Errors` section
- [ ] Verify the key matches exactly (case-sensitive)

#### Pattern to Follow

```swift
// 1. Define error in Swift
enum NotificationError: Error, LocalizedError, Equatable {
    case emptyDeviceToken

    var errorDescription: String? {
        switch self {
        case .emptyDeviceToken:
            NSLocalizedString("error.notification.empty.device.token", comment: "")
        }
    }
}

// 2. Add to Localizable.strings (REQUIRED!)
// In AIQ/en.lproj/Localizable.strings:
// MARK: - Service Errors - Notification
"error.notification.empty.device.token" = "Device token cannot be empty";
```

#### Naming Convention for Error Keys

Follow this pattern for consistency:
```
error.<service>.<error_case_in_snake_case>
```

Examples:
- `error.auth.no.refresh.token`
- `error.keychain.save.failed`
- `error.notification.empty.device.token`
- `error.deeplink.unrecognized.scheme`

#### Common Mistakes

| Mistake | Problem | Fix |
|---------|---------|-----|
| Missing Localizable.strings entry | Raw key shown to users | Add the key before merging |
| Key mismatch (typo) | Key not found, raw string shown | Verify exact match |
| Wrong section in Localizable.strings | Hard to maintain | Use `// MARK: - Service Errors - <ServiceName>` |

#### Why This Matters

When a `NSLocalizedString` key doesn't exist in `Localizable.strings`:
- The raw key string (e.g., `"error.notification.empty.device.token"`) is displayed to users
- This creates a poor user experience
- The error appears technical and confusing
- It's easily missed during development because it doesn't crash

### Date and Time Edge Cases

Date calculations can produce unexpected results due to clock skew, timezone changes, and other edge cases. Defensive coding prevents subtle bugs.

#### Common Pitfalls

| Edge Case | Cause | Impact |
|-----------|-------|--------|
| **Negative day count** | Device clock set backwards | Test availability calculated incorrectly |
| **Nil components** | Invalid date ranges | Crash or unexpected default |
| **Timezone shifts** | User travels across zones | Day boundaries change |
| **DST transitions** | Daylight Saving Time | Hour added/removed |

#### Defensive Date Calculation Pattern

Always guard against unexpected values from `Calendar.dateComponents()`:

```swift
// ✅ CORRECT - Defensive calculation
func daysSince(date: Date) -> Int {
    let components = Calendar.current.dateComponents(
        [.day],
        from: date,
        to: Date()
    )

    let days = components.day ?? 0

    // Guard against clock skew (device clock set backwards)
    guard days >= 0 else {
        logger.warning("Date calculation returned negative days (clock skew?): \(days)")
        return 0  // Fail safe
    }

    return days
}

// ❌ WRONG - Assumes positive values
func daysSince(date: Date) -> Int {
    Calendar.current.dateComponents([.day], from: date, to: Date()).day ?? 0
    // Could return -5 if device clock is wrong
}
```

#### When to Use Defensive Checks

| Scenario | Apply Defensive Check? | Reason |
|----------|------------------------|--------|
| Date from server response | ✅ Yes | Clock sync issues |
| Date from user input | ✅ Yes | Invalid input possible |
| Date from system (e.g., `Date()`) | ⚠️ Optional | Usually trustworthy |
| Date stored locally | ✅ Yes | Device clock may have changed |

#### UTC vs. Local Time

Use UTC for server-synced dates to avoid timezone issues:

```swift
// ✅ CORRECT - Use UTC for server-synced dates
let utcFormatter = ISO8601DateFormatter()
utcFormatter.timeZone = TimeZone(identifier: "UTC")

// For display, convert to local timezone
let displayFormatter = DateFormatter()
displayFormatter.dateStyle = .medium
displayFormatter.timeZone = .current
let displayString = displayFormatter.string(from: serverDate)

// ❌ WRONG - Mixing local and UTC
let localFormatter = DateFormatter()
localFormatter.dateFormat = "yyyy-MM-dd"  // Ambiguous timezone
```

#### Fail-Safe Defaults

When date calculations fail, choose safe defaults:

```swift
// For "is X available after Y days" checks:
// - Default to NOT available (false) if uncertain
// - Better to show "not ready" than allow premature action

func isTestAvailable(lastTestDate: Date?) -> Bool {
    guard let lastDate = lastTestDate else {
        // No previous test - test IS available
        return true
    }

    let days = Calendar.current.dateComponents([.day], from: lastDate, to: Date()).day ?? 0

    // Defensive: negative days means clock issue, fail safe to "not available"
    guard days >= 0 else {
        logger.warning("Negative days since last test: \(days). Assuming not available.")
        return false
    }

    return days >= Constants.testCadenceDays
}
```

---

## Networking

### API Client

Use the centralized `APIClient` with protocol-based design:

```swift
// Define endpoint
enum APIEndpoint {
    case testHistory(limit: Int?, offset: Int?)

    var path: String {
        switch self {
        case let .testHistory(limit, offset):
            var path = "/v1/test/history"
            // Build query params
            return path
        }
    }
}

// Make request
let response: PaginatedTestHistoryResponse = try await apiClient.request(
    endpoint: .testHistory(limit: 50, offset: 0),
    method: .get,
    requiresAuth: true,
    cacheKey: DataCache.Key.testHistory,
    cacheDuration: 300
)
```

### Caching

Use `DataCache` for response caching:

```swift
// Cache configuration
try await apiClient.request(
    endpoint: .testHistory,
    cacheKey: DataCache.Key.testHistory,  // Cache key
    cacheDuration: 300                     // 5 minutes TTL
)

// Force refresh
try await apiClient.request(
    endpoint: .testHistory,
    cacheKey: DataCache.Key.testHistory,
    forceRefresh: true  // Bypass cache
)

// Manual cache invalidation
await DataCache.shared.remove(forKey: DataCache.Key.testHistory)
```

### Request/Response Models

- All request/response models must be `Codable`
- Use `CodingKeys` for snake_case to camelCase conversion
- Make models `Equatable` for testing

```swift
struct TestResult: Codable, Equatable {
    let iqScore: Int
    let completedAt: Date

    enum CodingKeys: String, CodingKey {
        case iqScore = "iq_score"
        case completedAt = "completed_at"
    }
}
```

### Token Management

Authentication tokens are handled automatically by `AuthService` and `APIClient`:
- Access tokens are automatically refreshed when expired
- Retry logic is built into the API client
- No manual token management needed in ViewModels

### API Schema Consistency

When implementing features that involve backend API responses, **always verify iOS models match the backend Pydantic schemas exactly**. Schema mismatches can cause silent decoding failures or mask bugs.

#### Verification Process

Before implementing an iOS model for a backend response:

1. **Read the backend schema**: Check `backend/app/schemas/` for the Pydantic model
2. **Verify field optionality**: If backend returns a field as required, iOS should NOT make it optional
3. **Verify field types**: Match Python types to Swift types exactly
4. **Check CodingKeys**: Ensure snake_case to camelCase mapping is correct

#### Type Mapping Reference

| Python (Pydantic) | Swift | Notes |
|-------------------|-------|-------|
| `str` | `String` | |
| `int` | `Int` | |
| `float` | `Double` | Not `Float` - use `Double` for API responses |
| `bool` | `Bool` | |
| `Optional[T]` | `T?` | Only if backend field is truly optional |
| `List[T]` | `[T]` | |
| `datetime` | `Date` | Requires date decoding strategy |
| `Enum` | `String` (with enum) | Match raw values exactly |

#### Common Mistakes

**Mistake 1: Making required fields optional**
```swift
// Backend schema (required field):
// class FeedbackResponse(BaseModel):
//     submission_id: int  # Required - always returned

// BAD: iOS makes it optional
struct FeedbackResponse: Decodable {
    let submissionId: Int?  // Wrong! Masks decoding failures
}

// GOOD: iOS matches backend
struct FeedbackResponse: Decodable {
    let submissionId: Int  // Correct - will fail loudly if missing
}
```

**Mistake 2: Wrong type precision**
```swift
// Backend returns float
// score: float = 85.5

// BAD: Using Float instead of Double
let score: Float  // Float has less precision

// GOOD: Use Double for API floats
let score: Double
```

**Mistake 3: Missing CodingKeys**
```swift
// Backend uses snake_case: "iq_score", "completed_at"

// BAD: No CodingKeys - decoding fails silently
struct TestResult: Decodable {
    let iqScore: Int  // Won't decode from "iq_score"
}

// GOOD: Explicit CodingKeys
struct TestResult: Decodable {
    let iqScore: Int

    enum CodingKeys: String, CodingKey {
        case iqScore = "iq_score"
    }
}
```

#### Schema Verification Checklist

Before creating/modifying an iOS model for a backend response:

- [ ] Read the backend Pydantic schema in `backend/app/schemas/`
- [ ] Verify every field's optionality matches (required vs Optional)
- [ ] Verify field types match using the type mapping table
- [ ] Add CodingKeys for all snake_case fields
- [ ] Test decoding with actual backend response (not mock data)

#### Why This Matters

Schema mismatches cause:
- **Silent failures**: Optional fields that should be required don't trigger errors
- **Runtime crashes**: When backend changes a field and iOS expects old schema
- **Data loss**: Missing fields due to decoding errors are silently nil
- **Debugging difficulty**: Issues manifest far from the actual problem

When implementing full-stack features, verify schemas as the **first step** before writing any iOS code.

---

## Design System

### Color Palette

ALWAYS use `ColorPalette` for colors - never hardcode colors:

```swift
// Good
.foregroundColor(ColorPalette.primary)
.background(ColorPalette.backgroundSecondary)

// Bad
.foregroundColor(.blue)
.background(Color(red: 0.95, green: 0.95, blue: 0.95))
```

Available color categories:
- **Primary colors**: `primary`, `secondary`
- **Semantic colors**: `success`, `warning`, `error`, `info`
- **Text colors**: `textPrimary`, `textSecondary`, `textTertiary`
- **Backgrounds**: `background`, `backgroundSecondary`, `backgroundTertiary`
- **Chart colors**: `chartColors` array
- **Performance levels**: `performanceExcellent`, `performanceGood`, etc.

### Typography

Use `Typography` enum for all text styling:

```swift
Text("Welcome")
    .font(Typography.h1)

Text("Subtitle")
    .font(Typography.bodyMedium)
    .foregroundColor(ColorPalette.textSecondary)
```

Available styles:
- **Display**: `displayLarge`, `displayMedium`, `displaySmall`
- **Headings**: `h1`, `h2`, `h3`, `h4`
- **Body**: `bodyLarge`, `bodyMedium`, `bodySmall`
- **Labels**: `labelLarge`, `labelMedium`, `labelSmall`
- **Captions**: `captionLarge`, `captionMedium`, `captionSmall`
- **Special**: `scoreDisplay`, `statValue`, `button`

### Spacing

Use `DesignSystem.Spacing` for consistent spacing:

```swift
VStack(spacing: DesignSystem.Spacing.lg) {
    // Content
}
.padding(DesignSystem.Spacing.xxl)
```

Available sizes: `xs` (4pt), `sm` (8pt), `md` (12pt), `lg` (16pt), `xl` (20pt), `xxl` (24pt), `xxxl` (32pt), `huge` (40pt), `section` (60pt)

### Corner Radius

Use `DesignSystem.CornerRadius`:

```swift
.cornerRadius(DesignSystem.CornerRadius.lg)
```

Available sizes: `sm` (8pt), `md` (12pt), `lg` (16pt), `xl` (20pt), `full` (9999)

### Shadows

Use `DesignSystem.Shadow` for consistent elevation:

```swift
.shadow(
    color: DesignSystem.Shadow.lg.color,
    radius: DesignSystem.Shadow.lg.radius,
    x: DesignSystem.Shadow.lg.x,
    y: DesignSystem.Shadow.lg.y
)
```

Available shadows: `sm`, `md`, `lg`

### Animations

Use `DesignSystem.Animation` for consistent motion:

```swift
.animation(DesignSystem.Animation.standard, value: someState)
```

Available animations: `quick`, `standard`, `smooth`, `bouncy`

---

## Documentation

### Code Comments

Use documentation comments (`///`) for:
- All public types, properties, and methods
- Complex algorithms or non-obvious logic
- Enum cases with specific meanings

```swift
/// ViewModel for managing dashboard data and state
@MainActor
class DashboardViewModel: BaseViewModel {
    /// Latest completed test result for the user
    @Published var latestTestResult: TestResult?

    /// Fetch dashboard data from API with caching
    /// - Parameter forceRefresh: If true, bypass cache and fetch from API
    func fetchDashboardData(forceRefresh: Bool = false) async {
        // Implementation
    }
}
```

### Inline Comments

Use inline comments (`//`) for:
- Explaining why code is written a certain way
- Clarifying complex expressions
- Marking TODOs or FIXMEs

```swift
// Check if error is retryable (network errors, timeouts, server errors)
if error.isRetryable {
    // Show retry UI
}

// TODO: Add pagination support for large result sets
```

### MARK Comments

Use `// MARK:` to organize code sections:

```swift
// MARK: - Published Properties

@Published var isLoading: Bool = false

// MARK: - Private Properties

private let apiClient: APIClientProtocol

// MARK: - Initialization

init(apiClient: APIClientProtocol) {
    // ...
}

// MARK: - Public Methods

func fetchData() async {
    // ...
}

// MARK: - Private Methods

private func handleResponse() {
    // ...
}
```

### Documenting Lifecycle and Concurrency Constraints

When implementing types with initialization-time vs. runtime behavior, document the constraints explicitly. This is especially important for singletons, service containers, and configuration objects.

**Required Documentation Patterns:**

**1. Startup-only APIs** - APIs that should only be called during app initialization:

```swift
/// Registers a service in the container.
///
/// - Warning: This method must only be called during app startup before the container
///            is accessed by application code. While thread-safe, runtime registration
///            after app launch may cause race conditions with concurrent resolution.
/// - Parameters:
///   - type: The protocol type to register
///   - factory: A closure that creates instances of the service
func register<T>(_ type: T.Type, factory: @escaping () -> T)
```

**2. Thread-safety guarantees** - Document what operations are thread-safe:

```swift
/// Thread-safe service container for dependency injection.
///
/// ## Thread Safety
/// - `register()` and `resolve()` are thread-safe (protected by NSLock)
/// - `register()` should only be called during app startup
/// - `resolve()` is safe to call from any thread after configuration
///
/// ## Usage
/// Configure all services at app launch:
/// ```swift
/// // In AppDelegate or App struct
/// let container = ServiceContainer()
/// ServiceConfiguration.configureServices(container: container)
/// ```
class ServiceContainer {
    // ...
}
```

**3. Testing-only APIs** - Methods not intended for production use:

```swift
/// Removes all registered services from the container.
///
/// - Warning: For testing only. Do not call in production code.
///            Calling this while the app is running will cause crashes
///            when ViewModels attempt to resolve dependencies.
func reset()
```

**When to Add Lifecycle Documentation:**
- Singletons with an initialization phase
- Service containers and registries
- Configuration objects that affect app behavior
- Any API where "when you call it" matters as much as "what it does"
- APIs with different thread-safety guarantees for different operations

**Why This Matters:**
- Prevents misuse of APIs in ways that cause race conditions
- Makes lifecycle constraints explicit for future maintainers
- Helps code reviewers identify concurrency issues
- Reduces debugging time when threading issues occur
- Creates self-documenting code that explains intent

---

## Testing

### Test File Organization

- Place unit tests in `AIQTests/`
- Place UI tests in `AIQUITests/`
- Mirror the main app structure
- Name test files with `Tests` suffix (e.g., `DashboardViewModelTests.swift`)

### Unit Testing ViewModels

Use the SUT (System Under Test) pattern:

```swift
@MainActor
final class DashboardViewModelTests: XCTestCase {
    var sut: DashboardViewModel!
    var mockAPIClient: MockAPIClient!

    override func setUp() async throws {
        try await super.setUp()
        mockAPIClient = MockAPIClient()
        sut = DashboardViewModel(apiClient: mockAPIClient)
    }

    override func tearDown() {
        sut = nil
        mockAPIClient = nil
        super.tearDown()
    }

    func testFetchDashboardData_Success() async {
        // Given
        let mockResult = TestResult(...)
        await mockAPIClient.setTestHistoryResponse([mockResult])

        // When
        await sut.fetchDashboardData()

        // Then
        XCTAssertEqual(sut.testCount, 1)
        XCTAssertNotNil(sut.latestTestResult)
        XCTAssertFalse(sut.isLoading)
    }
}
```

### Test Isolation and Shared Resources

**Principle:** Each test should be fully independent and not rely on side effects from other tests.

**For Shared Resources (Singletons, Containers):**

**DO:**
- Reset shared state in `setUp()` for each test
- Configure dependencies explicitly in each test class
- Make test dependencies obvious by initializing in `setUp()`
- Clean up resources in `tearDown()` without reconfiguring

**DON'T:**
- Reconfigure shared state in `tearDown()` "for other tests"
- Assume other tests have left state in a particular configuration
- Create implicit dependencies between test execution order

**Example - ServiceContainer Tests:**

```swift
// ✅ Good - Each test configures explicitly
final class ServiceConfigurationTests: XCTestCase {
    var container: ServiceContainer!

    override func setUp() async throws {
        try await super.setUp()
        container = ServiceContainer()
        ServiceConfiguration.configureServices(container: container)
    }

    override func tearDown() async throws {
        container.reset()  // Clean up, but don't reconfigure
        container = nil
        try await super.tearDown()
    }
}

// ❌ Bad - Defensive reconfiguration masks dependencies
override func tearDown() async throws {
    container.reset()
    ServiceConfiguration.configureServices(container: container)  // Don't do this
    try await super.tearDown()
}
```

**Why This Matters:**
- If Test B depends on the container being configured, Test B should configure it in `setUp()`
- Reconfiguring in `tearDown()` hides this dependency
- Test isolation issues become obvious when tests fail independently
- Debugging is easier when each test is self-contained

### Mocking

Create protocol-based mocks in `AIQTests/Mocks/`:

```swift
actor MockAPIClient: APIClientProtocol {
    var requestCalled = false
    var mockResponse: Any?
    var mockError: Error?

    func request<T: Decodable>(...) async throws -> T {
        requestCalled = true

        if let error = mockError {
            throw error
        }

        guard let response = mockResponse as? T else {
            throw NSError(...)
        }

        return response
    }
}
```

### Test Naming

Use descriptive test names following the pattern: `test<Method>_<Scenario>_<ExpectedBehavior>`

```swift
func testFetchDashboardData_Success()
func testFetchDashboardData_ErrorHandling()
func testFetchDashboardData_CacheBehavior()
```

### Async Testing

Use `async/await` in tests for async operations:

```swift
func testAsyncOperation() async {
    await sut.performAsyncOperation()
    XCTAssertTrue(sut.operationCompleted)
}
```

### Async Test Synchronization Patterns

**NEVER use `Task.sleep()` for synchronization in unit/integration tests.** Arbitrary delays cause flaky tests, slow CI runs, and can mask race conditions.

#### Anti-Pattern: Task.sleep()

```swift
// ❌ BAD - Arbitrary delay, flaky, slow
func testAuthStateChange_TriggersRegistration() async {
    mockAuthManager.isAuthenticated = true

    try? await Task.sleep(nanoseconds: 100_000_000) // 0.1 second - DON'T DO THIS

    XCTAssertTrue(sut.isDeviceTokenRegistered)
}
```

**Why this is problematic:**
- Tests may pass locally but fail on slower CI machines
- No guarantee operations complete within the delay
- `try?` silently swallows errors (see below)
- Artificial delays add up, making test suites slow
- Race conditions can still occur

#### Correct Pattern: Poll for Conditions

Use a helper function that polls for a condition with a timeout:

```swift
// ✅ GOOD - Proper async waiting pattern
private func waitForCondition(
    timeout: TimeInterval = 2.0,
    message: String = "Condition not met within timeout",
    _ condition: @escaping () async -> Bool
) async throws {
    let deadline = Date().addingTimeInterval(timeout)
    while !(await condition()) {
        if Date() > deadline {
            XCTFail(message)
            return
        }
        await Task.yield()  // Yield to allow other tasks to run
    }
}

// Usage
func testAuthStateChange_TriggersRegistration() async throws {
    mockAuthManager.isAuthenticated = true

    try await waitForCondition(message: "Should become registered") {
        sut.isDeviceTokenRegistered
    }

    XCTAssertTrue(sut.isDeviceTokenRegistered)
}
```

#### Domain-Specific Helpers

Create reusable helpers for common wait patterns:

```swift
/// Wait for device token registration state to change
private func waitForRegistrationState(_ expected: Bool, timeout: TimeInterval = 2.0) async throws {
    try await waitForCondition(
        timeout: timeout,
        message: "isDeviceTokenRegistered did not become \(expected) within timeout"
    ) {
        sut.isDeviceTokenRegistered == expected
    }
}

/// Wait for mock service to receive a call
private func waitForRegisterCall(timeout: TimeInterval = 2.0) async throws {
    try await waitForCondition(
        timeout: timeout,
        message: "registerDeviceToken was not called within timeout"
    ) {
        await mockNotificationService.registerDeviceTokenCalled
    }
}
```

#### Never Use `try?` with Async Operations

**NEVER use `try?` to silence errors in tests.** This hides failures and causes tests to pass when they shouldn't.

```swift
// ❌ BAD - Silently discards errors
try? await Task.sleep(nanoseconds: 100_000_000)  // If this throws, test continues as if delay happened

// ❌ BAD - Hides assertion failures from waitForCondition
try? await waitForCondition { sut.isReady }  // Timeout failures are silently ignored

// ✅ GOOD - Make test throw so errors propagate
func testAuthStateChange() async throws {  // Note: `throws`
    try await waitForCondition { sut.isReady }  // Failures will fail the test
}
```

**Why `try?` is dangerous in tests:**
- If `Task.sleep` is cancelled, the test continues without the intended delay
- If `waitForCondition` times out, `XCTFail` is called but may be swallowed
- Tests appear to pass when they should fail
- Debugging becomes difficult because errors are hidden

#### Acceptable Uses of Task.sleep

`Task.sleep` is acceptable ONLY when:
1. Testing time-based behavior (cache expiration, debounce)
2. Simulating network latency in mock services
3. Testing timer/delay-specific logic

```swift
// ✅ OK - Testing cache expiration requires actual time passage
func testCache_ExpiresAfterTTL() async throws {
    await cache.set("key", value: "data", ttl: 0.1)

    try await Task.sleep(nanoseconds: 150_000_000)  // Must wait for TTL

    let result = await cache.get("key")
    XCTAssertNil(result, "Cache should expire after TTL")
}

// ✅ OK - Mock simulating slow network
actor MockSlowService: ServiceProtocol {
    func fetch() async throws -> Data {
        try await Task.sleep(nanoseconds: 50_000_000)  // Simulate latency
        return mockData
    }
}
```

#### Quick Reference

| Scenario | Use This | NOT This |
|----------|----------|----------|
| Wait for state change | `waitForCondition { state == expected }` | `Task.sleep()` |
| Wait for mock called | `waitForCondition { mock.wasCalled }` | `Task.sleep()` |
| Wait for Published property | `waitForCondition { vm.isLoaded }` | `Task.sleep()` |
| Test cache expiration | `Task.sleep()` (unavoidable) | - |
| Test debounce/throttle | `Task.sleep()` (unavoidable) | - |

### Safe Test Data Encoding

When creating JSON data for decoding tests, use `XCTUnwrap()` instead of force unwrapping:

**DO:**
```swift
func testModelDecoding() throws {
    let json = """
    {"id": 1, "name": "Test"}
    """
    let data = try XCTUnwrap(json.data(using: .utf8))
    let model = try JSONDecoder().decode(Model.self, from: data)
    XCTAssertEqual(model.id, 1)
}
```

**DON'T:**
```swift
func testModelDecoding() throws {
    let json = """
    {"id": 1, "name": "Test"}
    """
    let data = json.data(using: .utf8)!  // Force unwrap can crash tests
    let model = try JSONDecoder().decode(Model.self, from: data)
}
```

**Rationale**: While `.data(using: .utf8)` rarely fails for hardcoded strings, using `XCTUnwrap()`:
- Provides clear failure messages if encoding fails
- Follows XCTest best practices
- Makes tests more maintainable
- Prevents silent test failures

### Assertion Best Practices

Include diagnostic information in assertion messages to aid debugging test failures:

```swift
// Good - Includes actual value on failure
XCTAssertTrue(error is MockSecureStorageError,
              "Should throw MockSecureStorageError, got \(type(of: error))")

XCTAssertEqual(sut.testCount, 1,
               "Should have 1 test after successful fetch, got \(sut.testCount)")

// Bad - Generic message without diagnostics
XCTAssertTrue(error is MockSecureStorageError, "Wrong error type")
XCTAssertEqual(sut.testCount, 1, "Wrong count")
```

**Why this matters**: When tests fail in CI or on different machines, diagnostic messages provide immediate context without requiring a developer to reproduce the failure locally.

### Test Coverage Completeness

When testing methods that modify multiple pieces of state, verify ALL state changes, not just the primary one.

**Pattern**: Methods that update storage, API client state, published properties, or caches should have tests that verify each component:

```swift
// Example: AuthService.login() modifies:
// 1. SecureStorage (access token, refresh token, userId)
// 2. APIClient state (setAuthToken called)
// 3. Published properties (currentUser, isAuthenticated)

func testLogin_PartialStorageFailure() async throws {
    // Given
    mockStorage.setShouldThrowOnSave(forKey: SecureStorageKey.refreshToken.rawValue, true)

    // When
    do {
        _ = try await sut.login(email: "test@example.com", password: "pass123")
        XCTFail("Should throw storage error")
    } catch {
        // Then - Verify ALL state components

        // 1. Storage state (primary)
        let savedAccessToken = try? mockStorage.retrieve(forKey: SecureStorageKey.accessToken.rawValue)
        XCTAssertEqual(savedAccessToken, "new_access_token", "Access token saved before failure")

        let savedRefreshToken = try? mockStorage.retrieve(forKey: SecureStorageKey.refreshToken.rawValue)
        XCTAssertNil(savedRefreshToken, "Refresh token should not be saved (threw error)")

        // 2. API client state (often missed!)
        let setAuthTokenCalled = await mockAPIClient.setAuthTokenCalled
        let lastAuthToken = await mockAPIClient.lastAuthToken
        XCTAssertTrue(setAuthTokenCalled, "API client should be updated before storage failure")
        XCTAssertEqual(lastAuthToken, "new_access_token", "API client should have new token")

        // 3. Published properties
        let isAuthenticated = await sut.isAuthenticated
        XCTAssertFalse(isAuthenticated, "Should not be authenticated after partial save")

        let currentUser = await sut.currentUser
        XCTAssertNil(currentUser, "Current user should be nil after error")
    }
}
```

**Common Gaps:**
- Testing storage but not API client state
- Testing success path but not failure path state consistency
- Testing published properties but not cache invalidation
- Testing primary state but not derived/computed state

**Why This Matters:**
- Partial state updates create subtle bugs that are hard to debug
- State mismatches between components (storage vs. API client) cause inconsistent behavior
- Tests should verify the system is in a consistent state after both success and error conditions

**Checklist for Test Coverage:**
When writing tests for methods that modify state:
- [ ] Identify ALL state mutations (storage, API client, published properties, caches, analytics)
- [ ] Test each state component in success scenarios
- [ ] Test each state component in failure scenarios (what's saved vs. what's not)
- [ ] Verify state consistency between components (e.g., API client token matches storage token)
- [ ] Test edge cases (first item fails vs. middle item fails vs. last item fails)

### Testing Factory Methods and Initialization

When factory methods or initializers use `fatalError()` for missing dependencies (see [Fatal Errors vs. Recoverable Errors](#fatal-errors-vs-recoverable-errors)), add a verification test to catch configuration errors at test time.

**Required Test Pattern:**

```swift
func testProductionConfiguration_SatisfiesAllFactories() {
    // Given - Production configuration
    let container = ServiceContainer()
    ServiceConfiguration.configureServices(container: container)

    // When/Then - All factories should succeed without fatalError
    // Note: If any service is missing, fatalError() will crash the test
    _ = ViewModelFactory.makeDashboardViewModel(container: container)
    _ = ViewModelFactory.makeHistoryViewModel(container: container)
    _ = ViewModelFactory.makeTestTakingViewModel(container: container)
    _ = ViewModelFactory.makeFeedbackViewModel(container: container)
    _ = ViewModelFactory.makeNotificationSettingsViewModel(container: container)
    _ = ViewModelFactory.makeLoginViewModel(container: container)
    _ = ViewModelFactory.makeRegistrationViewModel(container: container)
    // ... verify all factory methods
}
```

**Why This Matters:**
- Catches configuration gaps at test time instead of production runtime
- Prevents app crashes from missing dependency registrations
- Documents the relationship between ServiceConfiguration and ViewModelFactory
- Fails fast in CI when new factories are added without corresponding service registration
- Ensures all app entry points will succeed (main app, extensions, widgets)

**When to Add This Test:**
- When creating a new factory method in `ViewModelFactory`
- When adding a new service registration in `ServiceConfiguration`
- As part of any DI infrastructure changes

### UI Testing Helpers

Create reusable helpers in `AIQUITests/Helpers/`:

```swift
class RegistrationHelper {
    static func fillRegistrationForm(
        app: XCUIApplication,
        email: String,
        password: String,
        firstName: String,
        lastName: String
    ) {
        // Helper implementation
    }
}
```

### UI Test Wait Patterns

**NEVER use `Thread.sleep()` in UI tests** - it creates fragile, slow tests. Always wait for specific UI state changes using XCTest wait APIs.

**Bad** - Arbitrary delays that are fragile and slow:
```swift
button.tap()
Thread.sleep(forTimeInterval: 0.5)  // DON'T DO THIS
XCTAssertTrue(resultLabel.exists)
```

**Good** - Wait for element existence:
```swift
button.tap()
XCTAssertTrue(resultLabel.waitForExistence(timeout: 5.0))
```

**Good** - Wait for element to be hittable (animation complete):
```swift
button.tap()
let predicate = NSPredicate(format: "exists == true AND hittable == true")
let expectation = XCTNSPredicateExpectation(predicate: predicate, object: resultLabel)
let result = XCTWaiter.wait(for: [expectation], timeout: 5.0)
XCTAssertEqual(result, .completed)
```

**Good** - Wait for specific text content to change:
```swift
testHelper.tapNextButton()
// Wait for progress label to show next question
let predicate = NSPredicate(format: "label CONTAINS[c] 'Question 2'")
let expectation = XCTNSPredicateExpectation(predicate: predicate, object: progressLabel)
_ = XCTWaiter.wait(for: [expectation], timeout: 5.0)
```

**Available Wait Helpers in BaseUITest:**
- `wait(for:timeout:)` - Wait for element to exist
- `waitForHittable(_:timeout:)` - Wait for element to be tappable (animation complete)
- `waitForDisappearance(of:timeout:)` - Wait for element to disappear

**Exception - App Termination:**
The only valid use of `Thread.sleep` is waiting for app termination before relaunch:
```swift
app.terminate()
Thread.sleep(forTimeInterval: 0.5)  // OK - no UI to wait on after termination
app.launch()
```

### Verify Implementation Before Testing Advanced Capabilities

When writing tests for advanced capabilities (concurrency, thread-safety, security), **verify the implementation has the required primitives BEFORE writing tests that assume them**.

#### Thread Safety Testing

**DO:**
1. Read the implementation to confirm thread-safety primitives exist (DispatchQueue, NSLock, actors, etc.)
2. Then write concurrent access tests
3. Document what synchronization mechanism you verified

**DON'T:**
- Write concurrent tests assuming implementation is thread-safe without verifying
- Test capabilities that don't exist in the implementation
- Assume thread-safety unless explicitly implemented with synchronization primitives

**Example:**
```swift
// ✅ Good: Verified implementation uses DispatchQueue before writing test
func testConcurrentSave_ThreadSafety() {
    // Implementation verified: Uses DispatchQueue(label: "com.aiq.localStorage")
    // to synchronize access, so concurrent tests are valid

    let iterations = 100
    let expectation = expectation(description: "All saves complete")
    expectation.expectedFulfillmentCount = iterations

    for i in 0 ..< iterations {
        DispatchQueue.global().async {
            // Safe to test concurrently
            try? self.sut.save(data: "test-\(i)")
            expectation.fulfill()
        }
    }

    wait(for: [expectation], timeout: 10.0)
}

// ❌ Bad: Writing concurrent test without verifying synchronization exists
func testConcurrentSave_ThreadSafety() {
    // Did you verify the implementation has synchronization?
    // If not, this test may pass inconsistently or give false confidence
    // ...
}
```

**How to Verify Thread Safety:**
Look for these primitives in the implementation:
- `DispatchQueue` with `.sync` or `.async(flags: .barrier)` calls
- `NSLock`, `NSRecursiveLock`, or `os_unfair_lock`
- `actor` keyword (Swift concurrency)
- `@MainActor` annotation (for UI-bound classes)

**If Thread Safety Doesn't Exist:**
Don't write concurrent tests. Either:
1. File a bug to add thread-safety if needed
2. Document that the class is not thread-safe
3. Test single-threaded behavior only

#### Time-Based Tests Require Safe Margins

When testing time-based logic (expiration, timeouts, TTL), use **generous margins** to account for:
- Test execution overhead (encoding, I/O, decoding)
- Slower CI environments
- Debug builds with reduced optimization
- Potential system load during test runs

**DO:**
- Use margins of 10+ minutes for hour-scale boundaries
- Use margins of 10+ seconds for minute-scale boundaries
- Document the margin and reasoning in test comments
- Test "well within boundary" rather than "exactly at boundary"

**DON'T:**
- Use margins of 1 second for tests with file I/O or encoding
- Assume tests execute instantly
- Test exact boundary conditions without margin for execution time

**Example:**
```swift
// ✅ Good: 10-minute margin for 24-hour boundary
func testEdgeCase_SavedAtJustUnderExpiration() throws {
    // Given - Progress saved 23 hours and 50 minutes ago
    // (10-minute margin accounts for test execution time)
    let almostExpiredDate = Date().addingTimeInterval(-(23 * 60 * 60 + 50 * 60))
    let progress = createTestProgress(savedAt: almostExpiredDate)
    try sut.saveProgress(progress)

    // When
    let loaded = sut.loadProgress()

    // Then
    XCTAssertNotNil(loaded, "Progress well within 24 hours should still be valid")
}

// ❌ Bad: 1-second margin too tight for test with encoding + I/O
func testEdgeCase_SavedAtJustUnderExpiration() throws {
    // Given - Progress saved just under 24 hours ago
    let almostExpiredDate = Date().addingTimeInterval(-(24 * 60 * 60 - 1))  // FLAKY!
    let progress = createTestProgress(savedAt: almostExpiredDate)

    // Between creating almostExpiredDate and checking expiration,
    // encoding + UserDefaults write + decoding may take >1 second,
    // causing this test to fail intermittently
    try sut.saveProgress(progress)

    let loaded = sut.loadProgress()
    XCTAssertNotNil(loaded)  // May fail in CI or under load
}
```

**Safe Margin Guidelines:**

| Time Scale | Boundary | Recommended Margin | Example |
|------------|----------|-------------------|---------|
| 24 hours | Expiration | 10-30 minutes | 23h 50m for "just under 24h" |
| 1 hour | Timeout | 5-10 minutes | 55m for "just under 1h" |
| 1 minute | Rate limit | 10-30 seconds | 50s for "just under 1m" |
| 1 second | Debounce | 100-500ms | 0.5s for "just under 1s" |

**Why This Matters:**
Flaky tests undermine confidence in the test suite. A test that fails 1% of the time in CI:
- Requires re-running builds
- Wastes developer time investigating non-issues
- Erodes trust in all tests
- May mask real failures when team assumes "it's just flaky"

### Test Helper Anti-Patterns

Test helpers are useful for reducing boilerplate, but they can inadvertently duplicate production logic. When helpers encode business rules, tests give false confidence because they're testing the helper's implementation rather than the actual code.

#### When Helpers Duplicate Too Much Logic

**Anti-pattern**: Helper encodes business rules being tested.

```swift
// ❌ BAD - Helper duplicates the 90-day business rule
private func createOldTest() -> TestResult {
    // Helper encodes the 90-day rule we're supposed to be testing
    let date = Calendar.current.date(byAdding: .day, value: -91, to: Date())!
    return TestResult(id: UUID(), completedAt: date, iqScore: 120)
}

func testAvailability_OldTestMakesNewTestAvailable() async throws {
    let test = createOldTest()  // Business rule hidden in helper
    mockAPIClient.setTestHistoryResponse([test])

    let available = try await sut.checkTestAvailability()

    // This passes even if production logic is broken!
    // If production checks 89 days instead of 90, test still passes
    // because helper uses 91 days
    XCTAssertTrue(available)
}
```

**Problem**: If the production code's threshold changes from 90 to 120 days, this test would still pass because the helper creates a 91-day-old test (which satisfies both 90 and 120 day thresholds). The test isn't testing the actual boundary.

#### Boundary Testing Best Practices

Test exact boundaries explicitly to catch off-by-one errors and threshold changes:

```swift
// ✅ GOOD - Explicit boundary testing
func testCheckTestAvailability_ExactlyAt90Days_IsAvailable() async throws {
    // Test the EXACT boundary - 90 days
    let exactly90DaysAgo = Calendar.current.date(byAdding: .day, value: -90, to: Date())!
    let testResult = TestResult(id: UUID(), completedAt: exactly90DaysAgo, iqScore: 120)
    mockAPIClient.setTestHistoryResponse([testResult])

    let available = try await sut.checkTestAvailability()

    // Business rule explicit in test name and assertion
    XCTAssertTrue(available, "Test should be available at exactly 90-day boundary")
}

func testCheckTestAvailability_At89Days_IsNotAvailable() async throws {
    // Test just BEFORE the boundary - 89 days
    let only89DaysAgo = Calendar.current.date(byAdding: .day, value: -89, to: Date())!
    let testResult = TestResult(id: UUID(), completedAt: only89DaysAgo, iqScore: 120)
    mockAPIClient.setTestHistoryResponse([testResult])

    let available = try await sut.checkTestAvailability()

    // Tests the inverse boundary
    XCTAssertFalse(available, "Test should NOT be available before 90 days")
}
```

**Why This Is Better:**
- If threshold changes to 120 days, both tests fail (alerting you to update tests)
- Business rules are explicit in test names
- Catches off-by-one errors in production code
- No magic numbers hidden in helpers

#### When Helpers Are Appropriate

Helpers ARE appropriate for:

1. **Boilerplate Setup** - Creating complex test objects with many required fields:
```swift
// ✅ GOOD - Helper for boilerplate, not business logic
private func createTestResult(
    id: UUID = UUID(),
    completedAt: Date,  // Caller specifies date explicitly
    iqScore: Int = 120,
    percentileRank: Double = 85.0
) -> TestResult {
    TestResult(
        id: id,
        completedAt: completedAt,
        iqScore: iqScore,
        percentileRank: percentileRank,
        domainScores: createDefaultDomainScores(),
        duration: 1800
    )
}
```

2. **Shared Test Data** - Valid model instances without business logic:
```swift
// ✅ GOOD - Valid mock response, no business logic
private var validTestHistoryResponse: [TestResult] {
    [createTestResult(completedAt: Date())]
}
```

3. **UI Test Flows** - Navigation and interaction sequences:
```swift
// ✅ GOOD - UI flow helper
private func loginAndNavigateToSettings() {
    loginHelper.login(username: testUser, password: testPassword)
    app.tabBars.buttons["Settings"].tap()
}
```

#### Rule of Thumb

**Ask yourself**: "If the production code's threshold/rule changes, would this test fail?"

- If **YES** → Test is properly testing the boundary
- If **NO** → Test may be duplicating logic in a helper

**Helper Checklist:**
- [ ] Helper does NOT encode thresholds being tested (e.g., 90 days, rate limits)
- [ ] Helper does NOT encode business rules (e.g., "what makes a test 'old'")
- [ ] Business-critical values are passed as explicit parameters
- [ ] Test name clearly states what boundary/rule is being tested

---

## Code Formatting

### SwiftLint Configuration

The project uses SwiftLint with the following key rules:
- Line length: 120 warning, 150 error
- File length: 800 warning, 1000 error
- Function body length: 50 warning, 100 error
- Cyclomatic complexity: 10 warning, 20 error

### SwiftFormat Configuration

The project uses SwiftFormat with:
- 4-space indentation
- LF line endings
- Import sorting enabled
- Blank lines between scopes

### Manual Formatting

Run formatters before committing:

```bash
# Lint code
swiftlint lint --config .swiftlint.yml

# Format code
swiftformat --config .swiftformat AIQ/
```

### Pre-commit Hooks

Pre-commit hooks run automatically on commit. They include:
- **SwiftLint/SwiftFormat**: Code style enforcement for Swift
- **Black/Flake8/MyPy**: Python linting and formatting
- **detect-secrets**: Prevents committing API keys, passwords, and tokens

Ensure all hooks pass before committing.

---

## Accessibility

> **⚠️ IMPORTANT: Consult This Document, Not Existing Code**
>
> When implementing accessibility features, always consult this document rather than copying patterns from existing code. Existing code may contain errors that predate these standards. This is especially important for accessibility traits like `.updatesFrequently` which are commonly misused.

> **📋 Comprehensive Audit Reference**
>
> For detailed audit findings and screen-by-screen accessibility status, see [VOICEOVER_AUDIT.md](VOICEOVER_AUDIT.md). This audit documents all screens, their current accessibility status, and specific recommendations.

### Accessibility Review Requirement

**All new views must include an accessibility review before merging.** This review should verify:

- All interactive elements have appropriate `accessibilityLabel` and `accessibilityHint`
- Compound elements are properly combined for VoiceOver navigation
- Decorative elements are hidden from VoiceOver
- Dynamic content uses appropriate traits (e.g., `.updatesFrequently` for timers)
- Touch targets meet the 44x44pt minimum requirement
- Dynamic Type is properly supported

### Common Pitfalls

Before implementing accessibility, review these frequent mistakes:

| Pitfall | Wrong | Right |
|---------|-------|-------|
| `.updatesFrequently` on loading views | Adding to LoadingOverlay, LoadingView | Only use for timers, live counters |
| `.accessibilityValue` overuse | Using on static text elements | Only for adjustable controls (sliders, steppers) |
| Missing menu hints | Menu without `.accessibilityHint` | Always explain "Double tap to open menu..." |

### VoiceOver Support

Provide accessibility labels and hints for all interactive elements.

#### Labels, Values, and Hints

**`.accessibilityLabel`** - Describes WHAT the element is. Always required for interactive elements.

**`.accessibilityValue`** - Only for adjustable controls (sliders, steppers, pickers with increment/decrement). VoiceOver announces this separately after the label.

**`.accessibilityHint`** - Describes HOW to interact. Required for non-obvious interactions (menus, custom gestures).

```swift
// ✅ Good - Button with label and hint
Button("Submit") {
    // Action
}
.accessibilityLabel("Submit test")
.accessibilityHint("Double tap to submit your test answers")
.accessibilityAddTraits(.isButton)

// ✅ Good - Menu with hint explaining interaction
Menu {
    // Menu items
} label: {
    Text(selectedOption ?? "Select option")
}
.accessibilityLabel("Category, \(selectedOption ?? "not selected")")
.accessibilityHint("Double tap to open menu and select a category")

// ✅ Good - Slider with value (adjustable control)
Slider(value: $volume, in: 0...100)
    .accessibilityLabel("Volume")
    .accessibilityValue("\(Int(volume)) percent")

// ❌ Bad - Redundant value duplicates label content
Text("Time: \(formattedTime)")
    .accessibilityLabel("Time remaining: \(formattedTime)")
    .accessibilityValue(formattedTime)  // VoiceOver says time twice!

// ✅ Good - Combine all info into label for non-adjustable elements
Text("Time: \(formattedTime)")
    .accessibilityLabel("Time remaining: \(formattedTime)")
```

#### Accessibility Traits

> **🚨 COMMON MISTAKE**: Do NOT add `.updatesFrequently` to loading views or overlays just because they're visible for a period of time. This trait causes VoiceOver to poll the element continuously and should ONLY be used for content that actually updates (like timers counting down).

**`.updatesFrequently`** - Only for elements that change continuously while visible (timers, live counters). Do NOT use for elements that simply appear/disappear.

```swift
// ✅ Good - Timer updates every second while visible
Text(timerManager.formattedTime)
    .accessibilityLabel("Time remaining: \(timerManager.formattedTime)")
    .accessibilityAddTraits(.updatesFrequently)

// ❌ Bad - Loading overlay appears/disappears but content doesn't update
LoadingOverlay()
    .accessibilityLabel("Loading")
    .accessibilityAddTraits(.updatesFrequently)  // Wrong! Content is static

// ✅ Good - Static loading state
LoadingOverlay()
    .accessibilityLabel("Loading")  // No updatesFrequently needed
```

#### Conveying Visual State

When hiding decorative icons from VoiceOver, ensure any meaningful visual state (colors, urgency indicators) is conveyed in the accessibility label.

```swift
// ❌ Bad - Icon hidden but urgency state lost
HStack {
    Image(systemName: timerIcon)  // Changes based on urgency
        .foregroundColor(urgencyColor)
        .accessibilityHidden(true)
    Text(formattedTime)
}
.accessibilityLabel("Time remaining: \(formattedTime)")

// ✅ Good - Urgency state included in label
HStack {
    Image(systemName: timerIcon)
        .foregroundColor(urgencyColor)
        .accessibilityHidden(true)
    Text(formattedTime)
}
.accessibilityLabel("\(urgencyPrefix)Time remaining: \(formattedTime)")
// urgencyPrefix returns "Critical: ", "Warning: ", or "" based on state
```

#### Grouping Elements (Compound Element Combining)

Use `.accessibilityElement(children: .combine)` to group related content into a single VoiceOver element. This improves navigation by reducing the number of swipes needed and providing meaningful context.

**When to Use Compound Combining:**

- Card components with multiple text elements (icon + title + description)
- Stat displays (label + value)
- List items with multiple pieces of information
- Any UI element where the individual parts only make sense together

```swift
// ✅ Good - Card content read as single element
HStack {
    Image(systemName: "star.fill")
        .accessibilityHidden(true)  // Decorative
    VStack {
        Text("Score")
        Text("95")
    }
}
.accessibilityElement(children: .combine)

// ✅ Good - Feature card with meaningful combined description
VStack {
    Image(systemName: "brain.head.profile")
        .accessibilityHidden(true)
    Text("Fresh AI Challenges")
        .font(Typography.h3)
    Text("New questions generated daily")
        .font(Typography.bodySmall)
}
.accessibilityElement(children: .combine)
.accessibilityLabel("Fresh AI Challenges: New questions generated daily")

// ✅ Good - Stat card with explicit combined label
HStack {
    Image(systemName: "person.2.fill")
        .accessibilityHidden(true)
    VStack {
        Text("10,000+")
        Text("Users")
    }
}
.accessibilityElement(children: .combine)
.accessibilityLabel("10,000+ Users")
```

#### Dynamic Content Updates

For content that changes while visible (timers, live counters, progress indicators), use `.accessibilityAddTraits(.updatesFrequently)` to inform VoiceOver that it should poll for updates.

> **🚨 REMINDER**: Only use `.updatesFrequently` for content that actually updates continuously. Do NOT use for loading states that simply appear/disappear.

```swift
// ✅ Good - Timer that counts down every second
Text(timerManager.formattedTime)
    .accessibilityLabel("Time remaining: \(timerManager.formattedTime)")
    .accessibilityAddTraits(.updatesFrequently)

// ✅ Good - Progress indicator that updates as questions are answered
ProgressView(value: progress)
    .accessibilityLabel("Test progress: \(Int(progress * 100)) percent complete")
    .accessibilityAddTraits(.updatesFrequently)

// ❌ Bad - Loading spinner (static content, just appears/disappears)
ProgressView()
    .accessibilityLabel("Loading")
    .accessibilityAddTraits(.updatesFrequently)  // Wrong!
```

#### Hiding Decorative Elements

Use `.accessibilityHidden(true)` for purely decorative elements that provide no additional information when read by VoiceOver. This includes:

- Decorative icons that duplicate adjacent text
- Background images or patterns
- Animated elements that are purely visual
- Dividers and separators

```swift
// ✅ Good - Decorative icon hidden, info conveyed in label
HStack {
    Image(systemName: "trophy.fill")
        .foregroundColor(.yellow)
        .accessibilityHidden(true)  // Decorative - label conveys meaning
    Text("High Score")
}
.accessibilityLabel("High Score")

// ✅ Good - Animated brain icon hidden (purely decorative)
Image("brain_animation")
    .accessibilityHidden(true)

// ✅ Good - Divider hidden
Divider()
    .accessibilityHidden(true)
```

**Important:** When hiding elements that convey visual state (like colored icons indicating urgency), ensure that state is included in the accessibility label of a related element. See "Conveying Visual State" above.

### Dynamic Type

All text in the app MUST support Dynamic Type to ensure accessibility for users with vision impairments. The Typography system provides automatic Dynamic Type scaling.

**DO:**
- Use Typography system constants for all text styling
- Test layouts at multiple text sizes (M, XL, XXXL, AX5)
- Use ScrollView for screens with substantial content
- Avoid fixed height constraints on text containers
- Use `.lineLimit(nil)` or `.minimumScaleFactor()` for text that might truncate

**DON'T:**
- Use `Font.system(size:)` with hardcoded pixel values
- Apply fixed height constraints that could truncate scaled text
- Assume text will fit within a fixed container

**Examples:**

```swift
// Good - Uses Typography system which scales automatically
Text("Welcome")
    .font(Typography.h1)  // Scales from ~28pt to ~53pt+ with Dynamic Type

Text("Description")
    .font(Typography.bodyMedium)  // Scales with user preferences

// Bad - Fixed size that doesn't scale
Text("Welcome")
    .font(.system(size: 28))  // Never scales

// Good - Flexible layout for scaled text
VStack(spacing: DesignSystem.Spacing.lg) {
    Text("Title")
        .font(Typography.h1)
    Text("Subtitle")
        .font(Typography.bodyMedium)
}
.frame(maxWidth: .infinity)  // No fixed height

// Bad - Fixed height truncates large text
VStack {
    Text("Title")
}
.frame(height: 50)  // Will truncate at larger sizes
```

**Typography System Implementation:**

The Typography enum uses a combination of semantic text styles and `@ScaledMetric` for Dynamic Type support:

- **Semantic styles** (h1, h2, body, etc.) - Use SwiftUI's built-in text styles that automatically scale
- **Special sizes** (scoreDisplay, displayLarge, etc.) - Use `@ScaledMetric` to preserve base sizes while enabling scaling

```swift
// Semantic text styles (automatically scale)
static let h1 = Font.title.weight(.bold)
static let bodyMedium = Font.body.weight(.regular)

// Special sizes with @ScaledMetric (preserve base size + scale)
static var scoreDisplay: Font {
    FontScaling.scoreDisplay  // 72pt base, scales proportionally
}
```

**Testing Dynamic Type:**

Test all major screens at these sizes:
- M (Medium) - Default size
- XL (Extra Large) - Common accessibility size
- XXXL (Extra Extra Extra Large) - Largest non-accessibility size
- AX5 (Accessibility XXXL) - Largest accessibility size

```swift
// SwiftUI Preview with Dynamic Type size
#Preview("Large Text") {
    DashboardView()
        .environment(\.sizeCategory, .accessibilityExtraExtraExtraLarge)
}
```

### Semantic Colors

Use semantic colors from `ColorPalette` which adapt to light/dark mode:

```swift
.foregroundColor(ColorPalette.textPrimary)  // Adapts to light/dark mode
```

### Touch Target Sizes

All interactive elements MUST meet Apple's minimum touch target size of 44x44pt to ensure accessibility for users with motor impairments.

**DO:**
- Use `.frame(minWidth: 44, minHeight: 44)` for all interactive elements
- Use the `IconButton` component for icon-only buttons (guarantees 44x44pt)
- Add `.contentShape(Rectangle())` when needed to ensure the full hit area is tappable
- Test touch targets on smallest supported device (iPhone SE)

**DON'T:**
- Create icon-only buttons without explicit sizing
- Rely on default touch areas for small text buttons
- Use `.font(.caption)` or smaller fonts for buttons without padding compensation

**Examples:**

```swift
// Good - Icon button with guaranteed 44x44pt
IconButton(
    icon: "xmark",
    action: onDismiss,
    accessibilityLabel: "Close",
    foregroundColor: .white
)

// Good - Text button with explicit minimum size
Button("Sign In") {
    // Action
}
.frame(minHeight: 44)

// Good - Toolbar button with explicit sizing
Button("Exit") {
    // Action
}
.frame(minWidth: 44, minHeight: 44)

// Bad - Icon-only button without sizing (likely ~17-20pt)
Button {
    // Action
} label: {
    Image(systemName: "xmark")
}

// Bad - Small text button without sizing
Button {
    // Action
} label: {
    Text("Clear Filters")
        .font(.caption)
}
```

**Common Patterns:**

| Element Type | Minimum Requirement |
|--------------|-------------------|
| Icon-only buttons | Use `IconButton` component or `.frame(width: 44, height: 44)` |
| Text-only buttons | `.frame(minHeight: 44)` |
| Toolbar buttons | `.frame(minWidth: 44, minHeight: 44)` |
| Menu labels | `.frame(minWidth: 44, minHeight: 44)` |
| Grid cells | `.frame(minWidth: 44, height: 44)` with `.contentShape(Rectangle())` |

**Component Reference:**
- **IconButton** (`Views/Common/IconButton.swift`): Reusable component for icon-only buttons that guarantees 44x44pt minimum

### RTL (Right-to-Left) Support

The app supports RTL languages (Arabic, Hebrew). Follow these standards:

**DO:**
- Use semantic alignment (`.leading`, `.trailing`)
- Let SwiftUI handle directionality automatically
- Use SF Symbols for directional icons (they flip automatically)
- Test layouts with RTL enabled

```swift
// Good - Semantic directions
HStack {
    Text("Title")
    Spacer()
    Image(systemName: "chevron.right")  // Flips to chevron.left in RTL
}
.frame(maxWidth: .infinity, alignment: .leading)  // Becomes .trailing in RTL
.padding(.leading, 16)  // Becomes .trailing in RTL
```

**DON'T:**
- Use absolute directions (`.left`, `.right`) for layout
- Hardcode directional offsets without considering RTL
- Assume left-to-right flow

```swift
// Bad - Absolute directions (don't use these)
.frame(alignment: .left)
.padding(.left, 16)
```

**Testing RTL:**
Enable RTL testing in the scheme by checking the launch arguments in Edit Scheme > Run > Arguments:
- `-AppleLanguages (ar)`
- `-AppleLocale ar_SA`
- `-AppleTextDirection YES`

See [RTL Testing Guide](RTL_TESTING_GUIDE.md) for comprehensive testing instructions.

### Accessibility Testing

Test with:
- VoiceOver enabled
- Different Dynamic Type sizes
- Light and dark modes
- Reduced motion settings
- RTL language settings (Arabic/Hebrew)

---

## Concurrency

### Main Actor

Mark all ViewModels with `@MainActor` to ensure UI updates occur on the main thread:

```swift
@MainActor
class DashboardViewModel: BaseViewModel {
    @Published var state: String = ""

    func updateState() {
        // Automatically runs on main thread
        state = "Updated"
    }
}
```

### Async/Await

Use async/await for asynchronous operations:

```swift
func fetchData() async {
    do {
        let result = try await apiClient.request(...)
        updateUI(with: result)
    } catch {
        handleError(error)
    }
}
```

### Task Management

Use SwiftUI's `.task` modifier for view lifecycle tasks:

```swift
struct DashboardView: View {
    var body: some View {
        content
            .task {
                await viewModel.fetchDashboardData()
            }
    }
}
```

### Structured Concurrency

Use task groups for parallel operations:

```swift
async let historyTask: Void = fetchTestHistory()
async let sessionTask: Void = fetchActiveSession()

await historyTask
await sessionTask
```

### Main Actor Synchronization and Race Conditions

`@MainActor` guarantees synchronous execution on the main thread, which eliminates race conditions for UI state. Understanding when race conditions are and aren't possible prevents false flags in code reviews.

**When Race Conditions Are NOT Possible:**

All operations within `@MainActor` context execute sequentially on the main thread:

```swift
// ✅ No race condition - @MainActor guarantees sequential execution
@MainActor
class AppRouter: ObservableObject {
    @Published var selectedTab: TabDestination = .dashboard
    @Published var currentTab: TabDestination = .dashboard

    func switchTab(to tab: TabDestination) {
        // These assignments are synchronous and sequential
        selectedTab = tab   // Completes before next line
        currentTab = tab    // Completes after previous line
        // No race condition possible - all on main thread
    }
}

// ✅ No race condition - SwiftUI onChange runs on @MainActor
struct MainTabView: View {
    @StateObject var router = AppRouter()
    @State private var selectedTab: TabDestination = .dashboard

    var body: some View {
        TabView(selection: $selectedTab) {
            // Tab content...
        }
        .onChange(of: selectedTab) { newTab in
            // This runs on @MainActor, synchronous with other router updates
            router.currentTab = newTab
        }
    }
}
```

**When Race Conditions ARE Possible:**

Race conditions can occur with multiple async tasks updating shared state:

```swift
// ⚠️ Potential race - Multiple async tasks updating shared state
@MainActor
class DataManager: ObservableObject {
    @Published var data: String = ""

    func fetchConcurrently() async {
        async let userTask = fetchUser()
        async let profileTask = fetchProfile()

        // If both tasks complete and update data, order is non-deterministic
        let user = await userTask
        self.data = user.name  // Could race with profile update

        let profile = await profileTask
        self.data = profile.bio  // Final value depends on timing
    }
}
```

**Rule of Thumb for Code Reviews:**

| Scenario | Race Condition Risk |
|----------|---------------------|
| `@MainActor` + synchronous property updates | ❌ No risk |
| SwiftUI `onChange`/`onAppear` modifiers | ❌ No risk (runs on main) |
| Multiple `async let` tasks updating same property | ⚠️ Possible risk |
| Background tasks without `@MainActor` isolation | ⚠️ Possible risk |
| Combine publishers on main scheduler | ❌ No risk |

**Don't Flag Race Conditions When:**
- All state updates are within `@MainActor` classes
- SwiftUI view modifiers (`onChange`, `onAppear`) update `@MainActor` state
- Deep link handlers explicitly sync state before navigation

**Do Flag Race Conditions When:**
- Multiple concurrent async operations update shared state
- State updates happen outside `@MainActor` context
- Background queues update published properties without actor isolation

### Cross-Actor Property Access

When a Swift actor needs to read state from `@MainActor`-isolated classes (like `ObservableObject` with `@Published` properties), direct access causes cross-actor isolation violations in Swift 6 strict concurrency.

**Why It's a Problem:**

`@Published` properties on `ObservableObject` are implicitly `@MainActor`-isolated. Accessing them from an actor method crosses actor isolation boundaries, which Swift 6 strict concurrency mode flags as an error.

**Anti-Pattern - Direct Access:**

```swift
// ❌ Don't access MainActor-isolated properties directly from actors
actor MyQueue {
    private let monitor: NetworkMonitor  // ObservableObject is MainActor-isolated

    func checkStatus() -> Bool {
        monitor.isConnected  // ❌ Cross-actor isolation violation
    }
}
```

**Correct Pattern - Cache State via Combine Observation:**

The solution is to cache the state within the actor and update it through Combine observation, which safely transfers values across actor boundaries.

> **Note:** This pattern requires `import Combine` in files that use `AnyCancellable`, `.sink`, or other Combine APIs.

```swift
// ✅ Cache state within the actor via Combine observation
import Combine

actor MyQueue {
    private var isNetworkConnected: Bool = true  // Actor-isolated cache
    private var cancellables = Set<AnyCancellable>()

    func observeNetwork(monitor: NetworkMonitor) {
        monitor.$isConnected
            .sink { [weak self] isConnected in
                Task { await self?.updateNetworkState(isConnected) }
            }
            .store(in: &cancellables)
    }

    private func updateNetworkState(_ isConnected: Bool) {
        isNetworkConnected = isConnected  // Update within actor context
    }

    func checkStatus() -> Bool {
        isNetworkConnected  // ✅ Actor-isolated access
    }
}
```

**Why This Works:**
- Combine publishers deliver values across isolation boundaries safely
- The `Task { await ... }` call transfers execution to the actor's isolation context
- The cached property is actor-isolated, so all reads are synchronous and safe
- No cross-actor property access occurs in the actor's methods
- The `[weak self]` capture prevents retain cycles between the actor and the Combine subscription stored in `cancellables`—without it, the actor would hold the subscription via `cancellables`, and the subscription's closure would hold the actor, preventing deallocation

**Alternative - Async/Await for One-Time Reads:**

If the actor only needs to read `@MainActor` state once (not reactively observe changes), use `await` directly instead of setting up Combine observation:

```swift
// ✅ Use await for one-time reads of @MainActor state
actor MyQueue {
    private let monitor: NetworkMonitor

    func checkStatus() async -> Bool {
        await monitor.isConnected  // Explicitly crosses actor boundary
    }
}
```

Use Combine caching (above) when the actor needs to react to ongoing state changes. Use `await` when the actor just needs a snapshot of the current value.

**Real-World Example:**

See `OfflineOperationQueue.swift` for a production implementation of this pattern:

```swift
actor OfflineOperationQueue {
    /// Cached network connectivity state (actor-isolated to avoid cross-actor access)
    private var isNetworkConnected: Bool = true

    private var cancellables = Set<AnyCancellable>()

    /// Set up network observation (must be called from actor context)
    private func observeNetworkChanges() {
        networkMonitor.$isConnected
            .dropFirst()
            .removeDuplicates()
            .sink { [weak self] (isConnected: Bool) in
                Task { [weak self] in
                    await self?.handleNetworkStateChange(isConnected: isConnected)
                }
            }
            .store(in: &cancellables)
    }

    private func handleNetworkStateChange(isConnected: Bool) async {
        // Update cached network state (actor-isolated)
        isNetworkConnected = isConnected
        // ... trigger sync if connected
    }

    private func canStartSync() -> Bool {
        // ✅ Safe actor-isolated access
        !internalIsSyncing && !pendingOperations.isEmpty && isNetworkConnected
    }
}
```

**When to Apply This Pattern:**

| Scenario | Use This Pattern? |
|----------|-------------------|
| Actor needs reactive state from `@MainActor` class | ✅ Yes |
| Actor needs one-time read of `@MainActor` state | ❌ No (use `await` directly) |
| Actor needs state from another actor | ❌ No (use `await` instead) |
| `@MainActor` class needs state from actor | ❌ No (use `await` instead) |
| Non-actor code needs `@Published` state | ❌ No (use Combine directly) |

### Background Task Execution Patterns

Background tasks (BGAppRefreshTask, BGProcessingTask) operate under fundamentally different constraints than normal app execution. Understanding these differences prevents critical bugs.

**Key Differences from Normal App Execution:**

| Aspect | Normal App | Background Task |
|--------|-----------|-----------------|
| Scheduling | User-initiated | iOS-controlled |
| Time Budget | Unlimited | ~30 seconds |
| Termination | Graceful | Abrupt (no warning) |
| Thread | Main thread available | Background queue |
| UserDefaults sync | Automatic | Must be explicit |

#### Race Condition in Task Completion

The `expirationHandler` and normal completion path can race. Always guard against double-completion:

```swift
// ✅ CORRECT - Guard against race condition
@MainActor
class BackgroundRefreshManager {
    private var taskCompleted = false

    func handleBackgroundRefresh(task: BGAppRefreshTask) async {
        taskCompleted = false

        // Expiration handler runs on background queue
        task.expirationHandler = { [weak self] in
            guard let self else { return }
            Task { @MainActor in
                guard !self.taskCompleted else { return }  // Guard
                self.taskCompleted = true
                task.setTaskCompleted(success: false)
            }
        }

        let success = await performRefresh()

        // Guard against race with expiration handler
        guard !taskCompleted else { return }
        taskCompleted = true
        task.setTaskCompleted(success: success)
    }
}

// ❌ WRONG - No protection against double setTaskCompleted()
func handleBackgroundRefresh(task: BGAppRefreshTask) async {
    task.expirationHandler = {
        // Could race with normal completion below
        task.setTaskCompleted(success: false)
    }

    let success = await performRefresh()
    task.setTaskCompleted(success: success)  // May crash if expiration fired
}
```

**Why This Matters:**
- Calling `setTaskCompleted()` twice causes undefined behavior
- iOS may terminate the app immediately after first completion
- The race window is small but real in production

#### UserDefaults in Background Contexts

**General Rule**: `synchronize()` is unnecessary in normal app contexts.

**Exception for Background Tasks**: Must call `synchronize()` after writes.

```swift
// ✅ CORRECT for background tasks
func handleBackgroundRefresh(task: BGAppRefreshTask) async {
    // ... perform work ...

    // Explicit sync required - task may terminate abruptly
    UserDefaults.standard.set(Date(), forKey: "lastRefresh")
    UserDefaults.standard.synchronize()

    task.setTaskCompleted(success: true)
}

// ❌ WRONG in background context (may lose data)
func handleBackgroundRefresh(task: BGAppRefreshTask) async {
    UserDefaults.standard.set(Date(), forKey: "lastRefresh")
    // No sync - iOS may terminate before automatic flush
    task.setTaskCompleted(success: true)
}

// ✅ CORRECT for normal app context (no sync needed)
class SettingsManager {
    func saveSetting(_ value: String) {
        UserDefaults.standard.set(value, forKey: "setting")
        // No synchronize() needed - automatic sync is sufficient
    }
}
```

**Why Background Tasks Are Different:**
- iOS can terminate background tasks abruptly after `setTaskCompleted()`
- No graceful shutdown, no guaranteed automatic sync
- UserDefaults buffers writes in memory before disk flush
- Without explicit sync, data may be lost

**When to Use synchronize():**

| Context | Use synchronize()? | Reason |
|---------|-------------------|--------|
| Normal app execution | ❌ No | Automatic sync sufficient |
| App entering background | ❌ No | System handles gracefully |
| Background task completion | ✅ Yes | Abrupt termination possible |
| App extensions | ✅ Yes | Limited lifecycle |
| Before app exit (rare) | ✅ Yes | No graceful shutdown |

**Alternative for Critical Data:**

For highly critical data, consider file-based storage with explicit write:

```swift
// More robust alternative for critical background data
func persistCriticalData(_ data: CriticalData) throws {
    let encoded = try JSONEncoder().encode(data)
    let url = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        .appendingPathComponent("critical_data.json")
    try encoded.write(to: url, options: .atomic)  // Atomic write guarantees consistency
}
```

#### Battery Optimization Patterns

Background tasks should minimize resource usage:

```swift
// ✅ GOOD - Fast-fail checks minimize battery usage
func performRefresh() async -> Bool {
    // 1. Check preconditions first (no network call needed)
    guard authManager.isAuthenticated else { return true }
    guard networkMonitor.isConnected else { return true }

    // 2. Rate limiting (prevent excessive API calls)
    if let lastRefresh = getLastRefreshDate(),
       Date().timeIntervalSince(lastRefresh) < minimumInterval {
        return true  // Not an error, respecting rate limit
    }

    // 3. Only now make network request
    do {
        try await fetchData()
        return true
    } catch {
        return false
    }
}
```

**Battery Optimization Checklist:**
- [ ] Fast-fail on auth/network preconditions
- [ ] Rate limit API calls (4+ hour intervals typical)
- [ ] Complete work in <20 seconds (target, not limit)
- [ ] Track duration for analytics
- [ ] Use `limit: 1` when only checking for existence

---

## Performance

### Caching Strategy

Implement caching for expensive operations:

```swift
// API responses are cached automatically
try await apiClient.request(
    endpoint: .testHistory,
    cacheKey: DataCache.Key.testHistory,
    cacheDuration: 300  // 5 minutes
)
```

### Lazy Loading

Use lazy properties for expensive computations:

```swift
lazy var formattedDate: String = {
    let formatter = DateFormatter()
    formatter.dateStyle = .medium
    return formatter.string(from: date)
}()
```

### Analytics

Track performance issues automatically:
- Slow API requests (> 2 seconds) are tracked via `AnalyticsService`
- API errors are tracked with endpoint and status code
- Use `#if DEBUG` for development-only logging

```swift
#if DEBUG
    print("✅ Dashboard data loaded successfully")
#endif
```

### Image Optimization

- Use SF Symbols when possible
- Compress images before adding to assets
- Use appropriate resolutions for different device sizes

### SwiftUI View Performance

SwiftUI recomputes view bodies when state changes. Understanding and controlling this behavior is critical for smooth UI performance.

#### Equatable Conformance

When a view conforms to `Equatable`, SwiftUI uses that conformance to determine if the view body needs recomputation. Without it, SwiftUI uses reflection-based comparison which is slower and may trigger unnecessary re-renders.

**DO:**

```swift
struct ScoreCard: View, Equatable {
    let score: Int
    let category: String

    static func == (lhs: ScoreCard, rhs: ScoreCard) -> Bool {
        lhs.score == rhs.score && lhs.category == rhs.category
    }

    var body: some View {
        VStack {
            Text("\(score)")
            Text(category)
        }
    }
}

// Use .equatable() modifier for existing views
ScoreCard(score: 85, category: "Memory")
    .equatable()
```

**DON'T:**

```swift
// Closures prevent Equatable conformance - avoid passing closures as props when possible
struct ScoreCard: View {
    let onTap: () -> Void  // This breaks automatic diffing
}
```

#### drawingGroup() for Complex Graphics

The `.drawingGroup()` modifier renders view content into an off-screen Metal texture, which is faster for complex graphical elements. This is used in our `IQTrendChart` component.

**DO:**

```swift
// Complex charts or graphics with gradients/overlays
Chart(data) { point in
    LineMark(x: .value("Date", point.date), y: .value("Score", point.score))
}
.drawingGroup() // Rasterize chart for better rendering performance
```

**DON'T:**

```swift
// Simple views - drawingGroup adds overhead without benefit
Text("Hello")
    .drawingGroup() // Unnecessary, may actually slow down rendering
```

#### .task(id:) for Efficient Async Work

Use `.task(id:)` instead of `.onAppear` + manual cancellation for async operations that should restart when a dependency changes.

**DO:**

```swift
struct TestHistoryView: View {
    @State private var selectedCategory: Category = .all
    @State private var results: [TestResult] = []

    var body: some View {
        List(results) { result in
            TestResultRow(result: result)
        }
        .task(id: selectedCategory) {
            // Automatically cancelled and restarted when selectedCategory changes
            results = await fetchResults(for: selectedCategory)
        }
    }
}
```

**DON'T:**

```swift
// Manual cancellation is error-prone and verbose
.onAppear { task = Task { await fetch() } }
.onDisappear { task?.cancel() }
.onChange(of: category) { task?.cancel(); task = Task { await fetch() } }
```

#### View Body Complexity

Keep view bodies focused on layout description, not computation. Extract complex logic to ViewModels or computed properties.

**DO:**

```swift
struct DashboardView: View {
    @StateObject private var viewModel: DashboardViewModel

    var body: some View {
        // Body only describes layout
        VStack {
            ScoreDisplay(score: viewModel.currentScore)
            TrendIndicator(trend: viewModel.trendDirection)
        }
    }
}

// Logic lives in ViewModel
class DashboardViewModel: ObservableObject {
    var trendDirection: TrendDirection {
        // Computation extracted from view body
        scores.suffix(5).average > scores.prefix(5).average ? .up : .down
    }
}
```

**DON'T:**

```swift
var body: some View {
    // Heavy computation in body - runs on every re-render
    let filteredResults = allResults.filter { $0.date > cutoffDate }
    let average = filteredResults.map(\.score).reduce(0, +) / filteredResults.count
    let trend = calculateTrend(from: filteredResults)

    VStack {
        Text("\(average)")
        TrendIndicator(trend: trend)
    }
}
```

#### LazyVStack and LazyHStack

Use lazy stacks for scrollable content to render only visible items. Always provide stable identifiers for efficient diffing.

**DO:**

```swift
ScrollView {
    LazyVStack(spacing: 16) {
        ForEach(testResults) { result in
            TestResultRow(result: result)
        }
    }
}
```

**DON'T:**

```swift
// VStack renders ALL items immediately regardless of visibility
ScrollView {
    VStack(spacing: 16) {
        ForEach(largeDataset) { item in  // 1000+ items loaded at once
            ExpensiveRow(item: item)
        }
    }
}

// Unstable identifiers force full reloads
LazyVStack {
    ForEach(items, id: \.self) { item in  // If items are modified, entire list re-renders
        ItemRow(item: item)
    }
}
```

#### State Management Performance

Choose the right property wrapper based on ownership and lifecycle requirements.

| Wrapper | Use When | Initialization |
|---------|----------|----------------|
| `@State` | Simple value types owned by the view | Initialized inline |
| `@StateObject` | ObservableObject owned by the view | Initialized once, survives re-renders |
| `@ObservedObject` | ObservableObject passed from parent | Re-initialized on parent re-render |

**DO:**

```swift
struct TestTakingView: View {
    // ViewModel owned by this view - use @StateObject
    @StateObject private var viewModel: TestTakingViewModel
    @StateObject private var timerManager = TestTimerManager()
}

struct ChildView: View {
    // ViewModel passed from parent - use @ObservedObject
    @ObservedObject var viewModel: ParentViewModel
}
```

**DON'T:**

```swift
struct TestTakingView: View {
    // WRONG: @ObservedObject recreates the instance on every parent re-render
    @ObservedObject private var viewModel = TestTakingViewModel()
}
```

#### @ViewBuilder Performance

Use `@ViewBuilder` for conditional view composition, but avoid excessive branching that creates unstable view identities.

**DO:**

```swift
@ViewBuilder
private var contentView: some View {
    if viewModel.isLoading {
        LoadingView()
    } else if let error = viewModel.error {
        ErrorView(error: error)
    } else {
        ResultsView(results: viewModel.results)
    }
}
```

**DON'T:**

```swift
// Avoid deep nesting that obscures view identity
@ViewBuilder
private var content: some View {
    if condition1 {
        if condition2 {
            if condition3 {
                View1()
            } else {
                View2()
            }
        } else {
            View3()
        }
    } else {
        View4()
    }
}
```

#### Profiling SwiftUI Performance

Before optimizing, profile with Instruments to identify actual bottlenecks:

1. **Product > Profile** (Cmd+I) in Xcode
2. Select **SwiftUI** instrument
3. Look for:
   - Views with high body evaluation counts
   - Slow body evaluation times (>16ms blocks 60fps)
   - Unexpected re-renders during scrolling

Address only confirmed bottlenecks—premature optimization adds complexity without benefit.

---

## Security

### Certificate Pinning

The app uses TrustKit for SSL certificate pinning to prevent man-in-the-middle (MITM) attacks. This ensures the app only trusts specific SSL certificates for backend connections.

**Configuration Location:** `AIQ/TrustKit.plist`

#### Requirements

- **Minimum 2 pins required:** Primary certificate + backup certificate
- **Fail secure:** Production builds will crash if certificate pinning fails to initialize
- **Test periodically:** Certificate pinning does not work against localhost in DEBUG builds

#### DO

- Update certificate hashes at least 30 days before expiration
- Verify hashes using multiple methods before deployment
- Test certificate pinning against production backend in DEBUG mode
- Keep track of certificate expiration dates

#### DON'T

- Hardcode certificate hashes in code (use TrustKit.plist)
- Deploy without verifying pinning is active
- Ignore pinning validation failures in logs
- Let certificates expire without updating hashes

#### Updating Certificate Hashes

1. Get new certificate hash:
```bash
openssl s_client -servername aiq-backend-production.up.railway.app \
  -showcerts -connect aiq-backend-production.up.railway.app:443 2>/dev/null | \
  openssl x509 -pubkey -noout | \
  openssl pkey -pubin -outform der | \
  openssl dgst -sha256 -binary | \
  base64
```

2. Verify hash using alternative method (different network/machine)
3. Update `TrustKit.plist` with new hash
4. Keep old hash as backup pin until new version is deployed
5. Test against production backend in DEBUG mode
6. Submit app update
7. Remove old hash after new version reaches 95%+ adoption

#### Current Certificate Expiration

- **Railway certificate:** March 6, 2026
- **R12 intermediate:** March 12, 2027

Set calendar reminders 30 days before expiration to update hashes.

#### Emergency Certificate Pinning Recovery

If certificate pinning causes production outages (e.g., unexpected certificate rotation, invalid hash deployment), follow this recovery runbook:

**1. Immediate Mitigation (Preferred)**

Release a hotfix with the updated certificate hash:

```bash
# Get the new certificate hash
openssl s_client -servername aiq-backend-production.up.railway.app \
  -showcerts -connect aiq-backend-production.up.railway.app:443 2>/dev/null | \
  openssl x509 -pubkey -noout | \
  openssl pkey -pubin -outform der | \
  openssl dgst -sha256 -binary | \
  base64
```

1. Update `TrustKit.plist` with the new hash
2. Submit for expedited App Store review
3. Request expedited review citing "critical bug fix"

**2. Short-Term Workaround (NOT RECOMMENDED - Security Risk)**

> **⚠️ WARNING: This temporarily disables certificate pinning and exposes users to MITM attacks. Only use as a last resort when a hotfix cannot be deployed quickly enough.**

If the hotfix cannot be deployed in time:

1. Open `ios/AIQ/TrustKit.plist`
2. Locate the `TSKEnforcePinning` key under the Railway domain configuration (line 19)
3. Change `<true/>` to `<false/>` to temporarily disable enforcement
4. Deploy via expedited review
5. **Immediately** begin work on a proper fix with correct hashes
6. Re-enable pinning within 48 hours maximum

```xml
<!-- TEMPORARY EMERGENCY ONLY - Re-enable immediately after deploying fix -->
<key>TSKEnforcePinning</key>
<false/>  <!-- Changed from <true/> to disable enforcement -->
```

**Note**: In DEBUG builds, certificate pinning is already disabled (see `AppDelegate.swift:24-27`). This workaround is only needed for production builds.

**3. Monitoring During Outage**

Check TrustKit logs for validation failures:

```swift
// In console or Crashlytics, look for:
// - "TrustKit: Pin validation failed for domain..."
// - "TrustKit: Certificate chain validation failed..."
```

Monitor:
- App Store review status
- User complaints and crash reports
- Crashlytics for pinning-related crashes

**4. Post-Mortem Template**

After resolving the incident, complete this template:

```markdown
## Certificate Pinning Incident Post-Mortem

**Date:** [Date of incident]
**Duration:** [How long users were affected]
**Severity:** [Critical/High/Medium]

### What Happened
[Description of the failure - certificate rotation, wrong hash deployed, etc.]

### Timeline
- [Time]: Incident detected
- [Time]: Investigation started
- [Time]: Root cause identified
- [Time]: Fix deployed
- [Time]: Incident resolved

### Root Cause
[Detailed explanation of why the pinning failed]

### Impact
- Users affected: [Number/percentage]
- Duration of outage: [Time]
- Security implications: [Any exposure during workaround]

### What Went Wrong
1. [Factor 1]
2. [Factor 2]

### What Went Right
1. [Factor 1]
2. [Factor 2]

### Action Items
- [ ] [Action 1 with owner and due date]
- [ ] [Action 2 with owner and due date]

### Lessons Learned
[Key takeaways to prevent recurrence]
```

**5. Prevention Checklist**

To prevent future certificate pinning emergencies:

- [ ] **Test hash updates in TestFlight** before production release
- [ ] **Keep backup pin valid** for at least 30 days after certificate rotation
- [ ] **Set up monitoring** for certificate expiration (30-day warning)
- [ ] **Document certificate expiration dates** in team calendar
- [ ] **Verify hashes from multiple sources** before deployment
- [ ] **Have expedited review request ready** as template
- [ ] **Test pinning against production** in DEBUG builds before release
- [ ] **Maintain runbook familiarity** - review quarterly

**Certificate Expiration Monitoring:**

Add these dates to team calendar with 30-day advance warnings:
- Railway certificate: March 6, 2026
- R12 intermediate: March 12, 2027

### Sensitive Data Logging

See [SENSITIVE_LOGGING_AUDIT.md](./SENSITIVE_LOGGING_AUDIT.md) for guidelines on logging sensitive data.

---

## Third-Party Dependencies

This section establishes standards for managing third-party dependencies in the AIQ iOS application. Thoughtful dependency management reduces security risks, minimizes maintenance burden, and ensures long-term project health.

### Criteria for Adding Dependencies

Before adding any new dependency, evaluate it against these criteria:

**Required (Must Meet All):**

| Criterion | Requirement |
|-----------|-------------|
| Real Problem | Solves a genuine problem that cannot be reasonably solved with native APIs |
| Active Maintenance | Has been updated within the last 6 months |
| License Compatibility | Uses MIT, Apache 2.0, BSD, or similarly permissive license |
| Security Track Record | No unpatched critical vulnerabilities; responsive to security reports |

**Evaluation Questions:**

1. **Can we solve this with native APIs?** Apple's frameworks should always be preferred. SwiftUI, Combine, URLSession, and other system frameworks are well-maintained and have no dependency overhead.

2. **Is this a "nice to have" or essential?** Dependencies add maintenance burden. Only add them for essential functionality.

3. **What's the migration cost if abandoned?** Consider how difficult it would be to replace if the library becomes unmaintained.

4. **Does it pull in excessive transitive dependencies?** A library that adds dozens of indirect dependencies should be scrutinized heavily.

**DO:**
- Prefer Apple's native frameworks (Foundation, SwiftUI, Combine, URLSession)
- Use established, well-maintained libraries from reputable sources (Apple, Google, etc.)
- Review the dependency's source code for quality and security practices

**DON'T:**
- Add dependencies for trivial functionality (e.g., string manipulation utilities)
- Use dependencies that haven't been updated in over 6 months
- Add dependencies with GPL or other restrictive licenses without legal review
- Use dependencies with known unpatched security vulnerabilities

### Swift Package Manager vs CocoaPods

**Prefer Swift Package Manager (SPM)** for all new dependencies. SPM is Apple's official dependency manager and provides:
- Native Xcode integration
- Better build performance
- First-class support from Apple
- Simpler project configuration

**When to Use CocoaPods:**
- The library is not available via SPM (increasingly rare)
- Migrating from CocoaPods and the library requires significant effort to port

**Current Project Setup:**

The AIQ project uses SPM exclusively. Dependencies are declared in:
- **Xcode project**: Main app dependencies (Firebase, TrustKit, OpenAPI runtime)
- **Local package**: `ios/Packages/AIQAPIClient/Package.swift` for the API client

```swift
// Example from AIQAPIClient/Package.swift
dependencies: [
    .package(
        url: "https://github.com/apple/swift-openapi-generator",
        from: "1.10.4"  // Uses semantic versioning with "from" constraint
    ),
    .package(
        url: "https://github.com/apple/swift-openapi-runtime",
        from: "1.9.0"
    )
]
```

**Migration from CocoaPods:**
If migrating an existing CocoaPods dependency to SPM:
1. Verify SPM support in the library's repository
2. Add the SPM package reference in Xcode
3. Remove the pod from Podfile
4. Run `pod install` to update the Pods project
5. Test thoroughly, as some libraries behave differently between package managers

### Version Pinning Strategy

Use semantic versioning constraints that balance stability with receiving security updates:

| Constraint Type | Syntax | Use When |
|----------------|--------|----------|
| **From version** | `from: "1.10.4"` | Default choice—allows minor and patch updates |
| **Up to next major** | `.upToNextMajor(from: "1.0.0")` | Same as `from:`, explicit about major version lock |
| **Up to next minor** | `.upToNextMinor(from: "1.10.0")` | Critical dependencies where minor changes have caused issues |
| **Exact version** | `.exact("1.10.4")` | Only for troubleshooting or temporary pins |

**Standards:**

```swift
// PREFERRED: Allow compatible updates (default)
.package(url: "...", from: "1.10.4")

// ACCEPTABLE: When you need stricter control
.package(url: "...", .upToNextMinor(from: "1.10.0"))

// AVOID: Exact pins block security patches
.package(url: "...", .exact("1.10.4"))  // Only use temporarily

// NEVER: Using branch names in production
.package(url: "...", branch: "main")  // Unstable, unpredictable
```

**Lockfile Management:**
- SPM generates `Package.resolved` which locks exact versions
- This file **must** be committed to version control
- Use `swift package update` deliberately, not automatically

### Dependency Update Process

Dependencies should be updated regularly to receive security patches and bug fixes.

**Update Cadence:**

| Update Type | Frequency | Process |
|-------------|-----------|---------|
| Security patches | Immediately | Hotfix branch, expedited review |
| Patch versions (x.x.Y) | Monthly | Batch with other patches |
| Minor versions (x.Y.0) | Quarterly | Individual review, test thoroughly |
| Major versions (X.0.0) | As needed | Dedicated PR, full regression testing |

**Update Procedure:**

1. **Check for updates:**
   ```bash
   # In Xcode: File > Packages > Update to Latest Package Versions
   # Or via command line for local packages:
   cd ios/Packages/AIQAPIClient
   swift package update
   ```

2. **Review changelog:** Read release notes for breaking changes, deprecations, and security fixes

3. **Run full test suite:**
   ```bash
   # Build and test
   xcodebuild clean build test \
     -project ios/AIQ.xcodeproj \
     -scheme AIQ \
     -destination 'platform=iOS Simulator,name=iPhone 16 Pro'
   ```

4. **Create dedicated PR:** Don't bundle dependency updates with feature work
   - Title: `[Deps] Update <package-name> from X.Y.Z to A.B.C`
   - Include changelog summary and any migration steps

5. **Verify in staging:** For critical dependencies (Firebase, networking), verify in TestFlight build

### Security Audit Requirements

**For New Dependencies:**

Before adding any new dependency, perform a security review:

1. **Check for known vulnerabilities:**
   - Search GitHub Security Advisories for the package
   - Check [Snyk Vulnerability Database](https://snyk.io/vuln)
   - Review the library's security policy (SECURITY.md)

2. **Assess security practices:**
   - Does the maintainer respond to security reports?
   - Is there a responsible disclosure process?
   - Are releases signed or verified?

3. **Review code quality:**
   - Are there obvious security anti-patterns?
   - Does it follow secure coding practices?
   - How does it handle sensitive data?

**For Existing Dependencies:**

- **Quarterly audit:** Review all dependencies for newly disclosed vulnerabilities
- **Automated scanning:** GitHub Dependabot alerts are enabled—address immediately
- **Supply chain attacks:** Be alert to maintainer changes or suspicious releases

**Incident Response:**

If a critical vulnerability is discovered in a dependency:
1. Assess impact on AIQ immediately
2. If exploitable, create hotfix branch
3. Update or patch the dependency
4. If no update available, consider:
   - Forking and patching
   - Removing the dependency
   - Implementing mitigating controls
5. Deploy fix through expedited review process

### Evaluating Dependency Health

Use these indicators to evaluate whether a dependency is healthy:

| Indicator | Healthy | Warning Signs |
|-----------|---------|---------------|
| **Last commit** | Within 3 months | Over 6 months |
| **Open issues** | Reasonable backlog, active triage | Hundreds ignored, no maintainer response |
| **Release frequency** | Regular releases | No releases in 12+ months |
| **Bus factor** | Multiple active contributors | Single maintainer, no activity |
| **Documentation** | Clear README, API docs | Sparse or outdated docs |
| **Test coverage** | Comprehensive tests, CI passing | No tests or broken CI |
| **Community** | Active discussions, responsive maintainers | Unanswered questions, abandoned PRs |

**Current Dependencies Health Check:**

| Dependency | Purpose | Health Status |
|------------|---------|---------------|
| Firebase iOS SDK | Analytics, crash reporting, auth | ✅ Actively maintained by Google |
| TrustKit | Certificate pinning | ✅ Active, security-focused maintainers |
| swift-openapi-runtime | OpenAPI client runtime library | ✅ Maintained by Apple |
| swift-openapi-generator | Build-time API client code generation | ✅ Maintained by Apple |
| swift-openapi-urlsession | URLSession transport | ✅ Maintained by Apple |
| swift-http-types | HTTP type definitions | ✅ Maintained by Apple |

### Documentation Requirements

Every dependency must be documented. Maintain awareness of what's in the dependency tree.

**Required Documentation:**

For each direct dependency, document in this file or a dedicated `DEPENDENCIES.md`:

1. **Why it exists:** What problem does it solve?
2. **Alternatives considered:** Why was this chosen over alternatives?
3. **Usage scope:** Where in the codebase is it used?
4. **Migration path:** How would we remove it if needed?

**Current Dependencies:**

| Package | Purpose | Scope | Notes |
|---------|---------|-------|-------|
| Firebase iOS SDK | Analytics, Crashlytics, Remote Config | App-wide | Core infrastructure; would require significant effort to replace |
| TrustKit | Certificate pinning for API security | Networking layer | Could implement manually if needed, but TrustKit handles edge cases well |
| swift-openapi-* | Type-safe API client from OpenAPI spec | API layer | Could switch to manual implementation, but auto-generation reduces bugs |

**When Adding a New Dependency:**

1. Update this section with the dependency's entry
2. Include the evaluation checklist results in the PR description
3. Document any special configuration or initialization requirements

---

## CI/CD Pipeline

This section documents the complete build, test, and deploy pipeline for the AIQ iOS application.

### GitHub Actions Workflow Overview

The iOS CI pipeline is defined in `.github/workflows/ios-ci.yml` and runs on:
- **Pull requests** that modify `ios/**`, `backend/**`, `docs/api/**`, or the workflow file itself
- **Pushes to main** with the same path filters

The pipeline consists of two jobs that run sequentially:

#### Job 1: lint-and-build

Runs on `macos-15` and performs:

1. **SwiftLint** - Static code analysis with strict mode
2. **SwiftFormat** - Code formatting verification (lint mode)
3. **OpenAPI Spec Sync** - Verifies iOS OpenAPI spec matches source in `docs/api/`
4. **Build** - Compiles the project for iOS Simulator
5. **Unit Tests** - Runs all unit tests in the AIQ scheme

#### Job 2: ui-tests

Runs after `lint-and-build` succeeds:

1. **Simulator Boot** - Pre-boots iPhone 16 Pro simulator for stability
2. **UI Tests** - Runs the `AIQUITests` target with test credentials from secrets

### Required Checks

All of the following must pass before a PR can be merged:

| Check | Tool | Fails On |
|-------|------|----------|
| Linting | SwiftLint | Any violation in strict mode |
| Formatting | SwiftFormat | Any formatting deviation |
| OpenAPI Sync | Custom script | Spec mismatch between `docs/api/` and iOS package |
| Build | xcodebuild | Compilation errors |
| Unit Tests | xcodebuild test | Any test failure |
| UI Tests | xcodebuild test | Any UI test failure |

### Build Configuration

#### Debug vs Release

| Configuration | Use Case | Optimizations | Code Signing |
|--------------|----------|---------------|--------------|
| Debug | Development, CI | Disabled | Not required |
| Release | TestFlight, App Store | Enabled | Required |

CI uses Debug configuration with code signing disabled:

```bash
xcodebuild -project AIQ.xcodeproj \
  -scheme AIQ \
  -sdk iphonesimulator \
  -destination 'platform=iOS Simulator,name=iPhone 16 Pro,OS=latest' \
  -skipPackagePluginValidation \
  clean build \
  CODE_SIGNING_ALLOWED=NO \
  CODE_SIGN_IDENTITY=""
```

#### Key Build Flags

- `CODE_SIGNING_ALLOWED=NO` - Disables code signing for CI builds
- `-skipPackagePluginValidation` - Speeds up Swift Package Manager resolution
- `-sdk iphonesimulator` - Targets simulator (no provisioning needed)

### Branch Protection Rules

The `main` branch is protected with:

- **Required status checks**: `lint-and-build` and `ui-tests` must pass
- **Required reviews**: At least one approving review (Claude Code review runs automatically)
- **No force pushes**: History cannot be rewritten
- **No deletions**: Branch cannot be deleted

### Deployment Process

#### TestFlight Distribution

TestFlight builds are created manually through Xcode or Xcode Cloud:

1. Increment build number in project settings
2. Archive with Release configuration
3. Upload to App Store Connect
4. TestFlight processes and distributes to testers

#### App Store Release

1. Complete TestFlight testing
2. Submit for App Review from App Store Connect
3. Upon approval, release manually or schedule release

### Certificate and Provisioning Management

#### Required Certificates

| Certificate | Purpose | Managed By |
|------------|---------|------------|
| Apple Development | Local development builds | Xcode automatic signing |
| Apple Distribution | App Store and TestFlight | Xcode automatic signing |

#### Provisioning Profiles

| Profile | Use Case |
|---------|----------|
| Development | Running on physical devices during development |
| App Store | Distribution through App Store and TestFlight |

**Best Practices:**
- Use Xcode's automatic signing for simplicity
- Keep Apple Developer account credentials secure
- Monitor certificate expiration dates (see Security section for Railway certificates)

### Claude Code Review Integration

Every PR automatically receives a code review from Claude via `.github/workflows/claude-code-review.yml`:

- Reviews code quality, potential bugs, performance, security, and test coverage
- Posts review as a PR comment
- References `CLAUDE.md` for project-specific conventions

Additionally, `.github/workflows/claude.yml` enables interactive Claude assistance:
- Mention `@claude` in any issue or PR comment to get help
- Claude can analyze code, suggest fixes, and answer questions

### Other CI Workflows

| Workflow | Purpose | Trigger |
|----------|---------|---------|
| `pre-commit.yml` | Runs pre-commit hooks on backend/question-service | All PRs and main pushes |
| `backend-ci.yml` | Tests backend with Black, Flake8, MyPy, pytest | Backend file changes |
| `question-service-ci.yml` | Tests question service | Question service file changes |
| `close-jira-on-merge.yml` | Auto-closes Jira tickets when PRs merge | PR merge events |

### Running CI Checks Locally

Before pushing, run checks locally to catch issues early:

```bash
# Linting
cd ios
swiftlint lint --config .swiftlint.yml --strict

# Formatting check
swiftformat --config .swiftformat --lint AIQ/

# Build
xcodebuild -project AIQ.xcodeproj \
  -scheme AIQ \
  -sdk iphonesimulator \
  -destination 'platform=iOS Simulator,name=iPhone 16 Pro,OS=latest' \
  build

# Unit tests
xcodebuild test \
  -project AIQ.xcodeproj \
  -scheme AIQ \
  -sdk iphonesimulator \
  -destination 'platform=iOS Simulator,name=iPhone 16 Pro,OS=latest'
```

### Troubleshooting CI Failures

#### SwiftLint Violations

```bash
# See all violations with auto-fix suggestions
swiftlint lint --config .swiftlint.yml

# Auto-fix correctable violations
swiftlint --fix --config .swiftlint.yml
```

#### SwiftFormat Violations

```bash
# Auto-format all files
swiftformat --config .swiftformat AIQ/
```

#### OpenAPI Spec Out of Sync

```bash
# Sync the spec from source
cd ios
scripts/sync_openapi_spec.sh
```

#### Test Failures

- Check the uploaded test artifacts in GitHub Actions for `.xcresult` files
- Open in Xcode: `xcrun xcresulttool get --path <file>.xcresult --format json`
- Look for screenshots and logs in UI test failures

---

## Git and Version Control

### Branching Strategy

We use a simple trunk-based workflow with short-lived feature branches:

| Branch Type | Pattern | Purpose |
|-------------|---------|---------|
| Main | `main` | Production-ready code, always deployable |
| Feature | `feature/TASK-XXX-brief-description` | New features and enhancements |
| Bugfix | `bugfix/TASK-XXX-brief-description` | Bug fixes |
| Hotfix | `hotfix/TASK-XXX-brief-description` | Urgent production fixes |

**Guidelines:**
- All feature branches should be created from `main`
- Keep feature branches short-lived (merge within a few days)
- Delete branches after merging
- Never commit directly to `main`

### Commit Message Format

All commits must follow this format:

```
[TASK-XXX] Brief imperative description

Optional longer description explaining:
- What changed
- Why it changed
- Any important context

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

**Examples:**
```
# Good
[TASK-123] Add pull-to-refresh to dashboard view
[TASK-456] Fix memory leak in test session handler
[TASK-789] Refactor navigation to use typed destinations

# Bad
fixed stuff
WIP
TASK-123 adding feature
```

**Rules:**
- Use imperative mood ("Add" not "Added" or "Adds")
- Keep the first line under 72 characters
- Reference the task ID in brackets
- Capitalize the first word after the task ID
- No period at the end of the subject line
- Include `Co-Authored-By` when AI-assisted

### Pull Request Guidelines

#### PR Size
- **Target**: 200-400 lines of changes
- **Maximum**: 500 lines (excluding auto-generated files, tests)
- Large changes should be split into smaller, logical PRs

#### PR Title Format
```
[TASK-XXX] Brief description
```

#### PR Description Template
```markdown
## Summary
- Bullet point summary of changes

## Test plan
- [ ] Unit tests added/updated
- [ ] UI tests pass
- [ ] Manual testing on device/simulator

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

#### Before Opening a PR
- [ ] Build succeeds (`/build-ios-project`)
- [ ] All tests pass (`/run-ios-test`)
- [ ] SwiftLint and SwiftFormat pass
- [ ] No secrets or credentials committed
- [ ] PR description is complete
- [ ] Self-review completed

### Merge Policy

We use **squash merges** to `main`:
- Keeps history clean and linear
- Each PR becomes a single commit
- Feature branch commits are preserved in PR history

**To merge:**
```bash
gh pr merge <PR_NUMBER> --squash --delete-branch
```

### Handling Merge Conflicts

1. **Pull latest main:**
   ```bash
   git fetch origin main
   git rebase origin/main
   ```

2. **Resolve conflicts:**
   - Resolve each file conflict
   - For `project.pbxproj` conflicts, prefer regenerating via Xcode or `/xcode-file-manager`
   - Run build after resolution to verify
   - Continue rebase: `git rebase --continue`

3. **Force push your branch:**
   ```bash
   git push --force-with-lease
   ```

**Prefer rebase over merge** for updating feature branches to keep history clean.

### Xcode Project File Conflicts

The `project.pbxproj` file frequently causes merge conflicts. Best practices:

1. **Minimize concurrent changes**: Coordinate with team when adding new files
2. **Use the `/xcode-file-manager` skill**: Ensures proper Xcode integration
3. **When conflicts occur**: Often easier to:
   - Accept one version completely
   - Re-add missing files via `/xcode-file-manager`
   - Verify build succeeds

### Tagging and Versioning

We use semantic versioning (SemVer) for releases:

| Version Part | When to Increment |
|--------------|------------------|
| Major (X.0.0) | Breaking changes, major features |
| Minor (0.X.0) | New features, backward compatible |
| Patch (0.0.X) | Bug fixes, backward compatible |

**Creating a release tag:**
```bash
git tag -a v1.2.3 -m "Release v1.2.3: Brief description"
git push origin v1.2.3
```

### Git Safety Rules

**NEVER:**
- Force push to `main`
- Commit secrets, API keys, or credentials
- Use `git commit --amend` on shared branches
- Use `--no-verify` to skip hooks
- Perform hard resets on shared branches

**ALWAYS:**
- Pull before starting work
- Create a branch for your changes
- Review your diff before committing
- Keep commits atomic and focused
- Build and test before pushing

---

## Recommended Enhancements

The standards above are **required** and reflect current codebase patterns. The enhancements below are **recommended** for consideration in new code. When an enhancement is implemented across the codebase, it should be promoted to a required standard in the appropriate section above.

### 1. Dependency Injection Container

**Recommendation:** Implement a formal DI container for managing dependencies.

**Current State:** Dependencies are passed via initializers, which works but becomes cumbersome with many dependencies.

**Suggested Approach:**

```swift
class DependencyContainer {
    static let shared = DependencyContainer()

    lazy var apiClient: APIClientProtocol = APIClient.shared
    lazy var authService: AuthServiceProtocol = AuthService.shared

    // Factory methods for ViewModels
    func makeDashboardViewModel() -> DashboardViewModel {
        DashboardViewModel(apiClient: apiClient)
    }
}

// Usage in views
@StateObject private var viewModel = DependencyContainer.shared.makeDashboardViewModel()
```

### 2. Result Builders for Complex Views

**Recommendation:** Use result builders for complex view hierarchies.

**Current State:** Views are well-structured but could benefit from custom result builders.

**Suggested Approach:**

```swift
@resultBuilder
struct ConditionalViewBuilder {
    static func buildBlock(_ components: AnyView...) -> [AnyView] {
        components
    }

    static func buildOptional(_ component: [AnyView]?) -> [AnyView] {
        component ?? []
    }
}
```

### 3. View State Machines

**Recommendation:** Implement explicit state machines for complex view states.

**Current State:** Views use boolean flags (`isLoading`, `error != nil`).

**Suggested Approach:**

```swift
enum ViewState<T> {
    case idle
    case loading
    case loaded(T)
    case error(Error)
}

@Published var state: ViewState<[TestResult]> = .idle

// In view
switch viewModel.state {
case .idle:
    EmptyView()
case .loading:
    LoadingView()
case .loaded(let results):
    ResultsView(results: results)
case .error(let error):
    ErrorView(error: error)
}
```

### 4. Coordinator Pattern for Navigation

**Recommendation:** Implement a Coordinator pattern for complex navigation flows.

**Current State:** Navigation uses `AppRouter` which is good, but could be enhanced with coordinators.

**Suggested Approach:**

```swift
protocol Coordinator {
    func start()
    func coordinate(to destination: Destination)
}

class AuthCoordinator: Coordinator {
    func start() {
        // Show login screen
    }

    func coordinate(to destination: Destination) {
        switch destination {
        case .login:
            // Show login
        case .register:
            // Show registration
        }
    }
}
```

### 5. Snapshot Testing

**Recommendation:** Add snapshot testing for views to catch visual regressions.

**Suggested Tool:** [swift-snapshot-testing](https://github.com/pointfreeco/swift-snapshot-testing)

```swift
func testDashboardViewAppearance() {
    let view = DashboardView()
    assertSnapshot(matching: view, as: .image)
}
```

### 6. Localization

**Recommendation:** Prepare for internationalization with proper string management.

**Suggested Approach:**

```swift
enum Strings {
    enum Dashboard {
        static let title = NSLocalizedString("dashboard.title", comment: "Dashboard title")
        static let welcomeMessage = NSLocalizedString("dashboard.welcome", comment: "Welcome message")
    }
}

// Usage
Text(Strings.Dashboard.title)
```

### 7. Feature Flags

**Recommendation:** Implement a feature flag system for gradual rollouts.

**Suggested Approach:**

```swift
enum FeatureFlags {
    @FeatureFlag("new_dashboard") static var newDashboardEnabled: Bool
    @FeatureFlag("push_notifications") static var pushNotificationsEnabled: Bool
}

// Usage
if FeatureFlags.newDashboardEnabled {
    NewDashboardView()
} else {
    LegacyDashboardView()
}
```

### 8. Memory Leak Detection

**Recommendation:** Add automated memory leak detection in tests.

**Suggested Approach:**

```swift
func testViewModelDoesNotLeak() {
    weak var weakViewModel: DashboardViewModel?

    autoreleasepool {
        let viewModel = DashboardViewModel()
        weakViewModel = viewModel
        // Use viewModel
    }

    XCTAssertNil(weakViewModel, "ViewModel should be deallocated")
}
```

### 9. API Response Validation

**Recommendation:** Add JSON schema validation for API responses.

**Suggested Approach:**

```swift
protocol ValidatableResponse {
    func validate() throws
}

struct TestResult: Codable, ValidatableResponse {
    func validate() throws {
        guard iqScore >= 40 && iqScore <= 160 else {
            throw ValidationError.invalidIQScore
        }
    }
}
```

### 10. Combine Publishers for Validation

**Recommendation:** Use Combine for form validation.

**Current State:** Validation is computed property-based, which works but could be more reactive.

**Suggested Approach:**

```swift
var isFormValidPublisher: AnyPublisher<Bool, Never> {
    Publishers.CombineLatest($email, $password)
        .map { email, password in
            Validators.validateEmail(email).isValid &&
            Validators.validatePassword(password).isValid
        }
        .eraseToAnyPublisher()
}
```

---

## Summary

These coding standards ensure:
- **Consistency**: All code follows the same patterns and conventions
- **Maintainability**: Code is well-organized and documented
- **Quality**: Proper error handling, testing, and accessibility
- **Performance**: Efficient caching, async operations, and resource management

**Required vs Recommended:**
- All sections before "Recommended Enhancements" are **required standards** - follow them strictly
- The "Recommended Enhancements" section contains **future considerations** - implement when appropriate and promote to required when adopted

When in doubt:
1. Follow the required standards in this document
2. Consult Apple's official documentation
3. Prioritize clarity and simplicity over cleverness
4. Write code as if a team will inherit it tomorrow
5. Update this document when establishing new patterns

For questions or clarifications, refer to the [iOS README](../README.md).
