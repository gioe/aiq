# Dependency Injection (DI)

This directory contains the dependency injection infrastructure for the AIQ iOS app.

## ServiceContainer

`ServiceContainer` is a thread-safe dependency injection container that implements the Service Locator pattern with protocol-based registration.

### Features

- **Protocol-based injection**: Register protocols and resolve to concrete implementations
- **Thread-safe**: Uses `NSLock` for synchronization, safe for concurrent access
- **Flexible lifetime management**: Supports both singleton and transient lifetimes
- **SwiftUI integration**: Built-in environment key for SwiftUI views
- **Singleton pattern**: Shared instance for global access

### Basic Usage

#### 1. Register Dependencies

Register services during app initialization (typically in `AppDelegate` or app entry point):

```swift
// Register singletons
ServiceContainer.shared.register(APIClientProtocol.self) {
    APIClient.shared
}

ServiceContainer.shared.register(AuthServiceProtocol.self) {
    AuthService.shared
}

// Register transient (new instance each time)
ServiceContainer.shared.register(ViewModelProtocol.self) {
    ConcreteViewModel()
}
```

#### 2. Resolve Dependencies

##### In ViewModels

```swift
@MainActor
class DashboardViewModel: BaseViewModel {
    private let apiClient: APIClientProtocol

    init(apiClient: APIClientProtocol? = nil) {
        // Resolve from container if not provided (supports DI for tests)
        self.apiClient = apiClient ?? ServiceContainer.shared.resolve(APIClientProtocol.self)!
        super.init()
    }
}
```

##### In SwiftUI Views

```swift
struct DashboardView: View {
    @Environment(\.serviceContainer) var container

    var body: some View {
        // Use container to resolve dependencies
        let apiClient = container.resolve(APIClientProtocol.self)
        // ...
    }
}
```

##### Direct Resolution

```swift
// Simple resolution
if let authService = ServiceContainer.shared.resolve(AuthServiceProtocol.self) {
    // Use authService
}
```

### Lifetime Management

#### Singleton Lifetime

Register a factory that returns the same instance:

```swift
ServiceContainer.shared.register(AuthServiceProtocol.self) {
    AuthService.shared  // Always returns the same instance
}
```

#### Transient Lifetime

Register a factory that creates a new instance:

```swift
ServiceContainer.shared.register(ViewModelProtocol.self) {
    ConcreteViewModel()  // New instance each time
}
```

### Testing Support

The container provides methods to support testing:

```swift
class MyTests: XCTestCase {
    override func setUp() {
        super.setUp()

        // Reset container for test isolation
        ServiceContainer.shared.reset()

        // Register mocks
        ServiceContainer.shared.register(APIClientProtocol.self) {
            MockAPIClient()
        }
    }

    override func tearDown() {
        ServiceContainer.shared.reset()
        super.tearDown()
    }

    func testSomething() {
        // Tests use mocked dependencies
    }
}
```

### API Reference

#### Registration

```swift
func register<T>(_ type: T.Type, factory: @escaping () -> T)
```

Registers a factory closure for the given type. The factory is executed each time `resolve()` is called.

#### Resolution

```swift
func resolve<T>(_ type: T.Type) -> T?
```

Executes the factory for the given type and returns the result. Returns `nil` if no factory is registered.

#### Checking Registration

```swift
func isRegistered<T>(_ type: T.Type) -> Bool
```

Returns `true` if a factory is registered for the given type.

#### Reset

```swift
func reset()
```

Removes all registered services. Primarily used for testing.

### Best Practices

1. **Register early**: Register all dependencies during app initialization
2. **Use protocols**: Register protocol types, not concrete types (enables testing)
3. **Support DI in init**: Allow dependencies to be injected via initializer parameters
4. **Fallback to container**: Provide default values that resolve from container
5. **Test with mocks**: Reset container in test setUp/tearDown and register mocks

### Example: Complete Setup

```swift
// AppDelegate.swift
class AppDelegate: NSObject, UIApplicationDelegate {
    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
    ) -> Bool {
        registerDependencies()
        return true
    }

    private func registerDependencies() {
        // API & Networking
        ServiceContainer.shared.register(APIClientProtocol.self) {
            APIClient.shared
        }

        // Authentication
        ServiceContainer.shared.register(AuthServiceProtocol.self) {
            AuthService.shared
        }

        // Storage
        ServiceContainer.shared.register(SecureStorageProtocol.self) {
            KeychainService.shared
        }

        // Analytics
        ServiceContainer.shared.register(AnalyticsServiceProtocol.self) {
            AnalyticsService.shared
        }
    }
}

// ViewModel
@MainActor
class LoginViewModel: BaseViewModel {
    private let authService: AuthServiceProtocol

    init(authService: AuthServiceProtocol? = nil) {
        self.authService = authService ?? ServiceContainer.shared.resolve(AuthServiceProtocol.self)!
        super.init()
    }

    func login() async {
        // Use authService
    }
}

// Tests
class LoginViewModelTests: XCTestCase {
    var sut: LoginViewModel!
    var mockAuthService: MockAuthService!

    override func setUp() {
        super.setUp()
        mockAuthService = MockAuthService()

        // Inject mock via initializer (preferred for unit tests)
        sut = LoginViewModel(authService: mockAuthService)
    }

    func testLogin() async {
        // Test uses mock
        await sut.login()
        XCTAssertTrue(mockAuthService.loginCalled)
    }
}
```

## Future Enhancements

This implementation could be extended with:

- **Scope management**: Request, session, or custom scopes
- **Property injection**: Automatic property resolution
- **Circular dependency detection**: Warn about circular dependencies
- **Registration validation**: Verify all required dependencies are registered at startup
