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
- [Naming Conventions](#naming-conventions)
- [SwiftUI Best Practices](#swiftui-best-practices)
- [State Management](#state-management)
- [Error Handling](#error-handling)
  - [Parsing and Validation Utilities](#parsing-and-validation-utilities)
- [Networking](#networking)
- [Design System](#design-system)
- [Documentation](#documentation)
- [Testing](#testing)
- [Code Formatting](#code-formatting)
- [Accessibility](#accessibility)
- [Concurrency](#concurrency)
- [Performance](#performance)
- [Security](#security)
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
    handleError(error, context: .fetchDashboard) {
        await self.fetchDashboardData()  // Retry closure
    }
}
```

### Error Display in Views

Use `ErrorView` for displaying errors with retry capability:

```swift
if let error = viewModel.error {
    ErrorView(error: error) {
        Task { await viewModel.retry() }
    }
}
```

### Crashlytics Integration

All errors handled through `BaseViewModel.handleError()` are automatically recorded to Crashlytics with context:

```swift
handleError(error, context: .login)  // Provides context for debugging
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

Formatting tools run automatically via pre-commit hooks. Ensure they pass before committing.

---

## Accessibility

> **⚠️ IMPORTANT: Consult This Document, Not Existing Code**
>
> When implementing accessibility features, always consult this document rather than copying patterns from existing code. Existing code may contain errors that predate these standards. This is especially important for accessibility traits like `.updatesFrequently` which are commonly misused.

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

#### Grouping Elements

Use `.accessibilityElement(children: .combine)` to group related content into a single VoiceOver element:

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
```

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

### Sensitive Data Logging

See [SENSITIVE_LOGGING_AUDIT.md](./SENSITIVE_LOGGING_AUDIT.md) for guidelines on logging sensitive data.

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
