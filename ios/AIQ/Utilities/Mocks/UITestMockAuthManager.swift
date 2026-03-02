import AIQAPIClient
import Combine
import Foundation

#if DEBUG

    /// Mock AuthManager for UI tests
    ///
    /// This mock provides configurable authentication state for UI testing.
    /// Unlike the unit test mock, it doesn't track method calls since UI tests
    /// verify behavior through the UI, not method invocations.
    ///
    /// ## Usage
    ///
    /// Configure the initial state based on the test scenario:
    /// ```swift
    /// let mock = UITestMockAuthManager()
    /// mock.configureForScenario(.loggedInWithHistory)
    /// ```
    @MainActor
    final class UITestMockAuthManager: ObservableObject, AuthManagerProtocol {
        @Published var isAuthenticated: Bool = false
        @Published var currentUser: User?
        @Published var isLoading: Bool = false
        @Published var authError: Error?

        var userFullName: String? {
            currentUser?.fullName
        }

        var isAuthenticatedPublisher: Published<Bool>.Publisher {
            $isAuthenticated
        }

        var isLoadingPublisher: Published<Bool>.Publisher {
            $isLoading
        }

        var authErrorPublisher: Published<Error?>.Publisher {
            $authError
        }

        /// Whether login should succeed (configurable per test)
        var shouldSucceedLogin: Bool = true

        /// Whether registration should succeed (configurable per test)
        var shouldSucceedRegister: Bool = true

        /// The type of registration error to simulate (if shouldSucceedRegister is false)
        var registrationErrorType: RegistrationErrorType = .generic

        /// Types of registration errors that can be simulated
        enum RegistrationErrorType {
            case generic
            case timeout
            case serverError
        }

        init() {}

        /// Configure the mock for a specific test scenario
        func configureForScenario(_ scenario: MockScenario) {
            switch scenario {
            case .default, .loggedOut:
                isAuthenticated = false
                currentUser = nil
                shouldSucceedLogin = true

            case .loggedInNoHistory, .loggedInWithHistory, .testInProgress:
                isAuthenticated = true
                currentUser = Self.mockUser
                shouldSucceedLogin = true

            case .loginFailure:
                isAuthenticated = false
                currentUser = nil
                shouldSucceedLogin = false

            case .networkError:
                isAuthenticated = false
                currentUser = nil
                shouldSucceedLogin = false

            case .registrationTimeout:
                isAuthenticated = false
                currentUser = nil
                shouldSucceedLogin = true
                shouldSucceedRegister = false
                registrationErrorType = .timeout

            case .registrationServerError:
                isAuthenticated = false
                currentUser = nil
                shouldSucceedLogin = true
                shouldSucceedRegister = false
                registrationErrorType = .serverError
            }
        }

        // MARK: - AuthManagerProtocol

        // swiftlint:disable:next function_parameter_count
        func register(
            email: String,
            password _: String,
            firstName: String,
            lastName: String,
            birthYear _: Int?,
            educationLevel _: EducationLevel?,
            country _: String?,
            region _: String?
        ) async throws {
            isLoading = true
            authError = nil

            // Simulate network delay
            try await Task.sleep(nanoseconds: 300_000_000) // 0.3 seconds

            if shouldSucceedRegister {
                let mockUser = Components.Schemas.UserResponse(
                    createdAt: Date(),
                    email: email,
                    firstName: firstName,
                    id: 1,
                    lastName: lastName,
                    notificationEnabled: false
                )
                isAuthenticated = true
                currentUser = mockUser
                isLoading = false
            } else {
                let error = makeRegistrationError()
                authError = error
                isLoading = false
                throw error
            }
        }

        /// Create the appropriate error based on the configured registration error type
        private func makeRegistrationError() -> Error {
            switch registrationErrorType {
            case .generic:
                NSError(
                    domain: "UITestMockAuthManager",
                    code: -1,
                    userInfo: [NSLocalizedDescriptionKey: "Registration failed"]
                )
            case .timeout:
                APIError.timeout
            case .serverError:
                APIError.serverError(statusCode: 500, message: "Internal server error")
            }
        }

        func login(email: String, password _: String) async throws {
            print("[UITestMockAuthManager] login() called with email: \(email)")
            print("[UITestMockAuthManager] shouldSucceedLogin: \(shouldSucceedLogin)")
            isLoading = true
            authError = nil

            // Simulate network delay
            try await Task.sleep(nanoseconds: 300_000_000) // 0.3 seconds

            if shouldSucceedLogin {
                let mockUser = Components.Schemas.UserResponse(
                    createdAt: Date(),
                    email: email,
                    firstName: "Test",
                    id: 1,
                    lastName: "User",
                    notificationEnabled: true
                )
                print("[UITestMockAuthManager] Setting isAuthenticated = true")
                isAuthenticated = true
                currentUser = mockUser
                isLoading = false
                print("[UITestMockAuthManager] Login complete, isAuthenticated: \(isAuthenticated)")
            } else {
                let error = NSError(
                    domain: "UITestMockAuthManager",
                    code: -1,
                    userInfo: [NSLocalizedDescriptionKey: "Invalid credentials"]
                )
                authError = error
                isLoading = false
                throw error
            }
        }

        func logout() async {
            isLoading = true

            // Simulate network delay
            try? await Task.sleep(nanoseconds: 200_000_000) // 0.2 seconds

            isAuthenticated = false
            currentUser = nil
            isLoading = false
            authError = nil
        }

        func deleteAccount() async throws {
            isLoading = true
            authError = nil

            // Simulate network delay
            try await Task.sleep(nanoseconds: 300_000_000) // 0.3 seconds

            isAuthenticated = false
            currentUser = nil
            isLoading = false
        }

        func clearError() {
            authError = nil
        }

        func restoreSession() async {
            // No-op for UI tests - state is pre-configured via scenario
            // Simulate brief delay for realism
            try? await Task.sleep(nanoseconds: 100_000_000) // 0.1 seconds
        }

        // MARK: - Mock Data

        /// Standard mock user for authenticated scenarios
        static let mockUser = Components.Schemas.UserResponse(
            createdAt: Date().addingTimeInterval(-30 * 24 * 60 * 60), // 30 days ago
            email: "test@example.com",
            firstName: "Test",
            id: 1,
            lastName: "User",
            notificationEnabled: true
        )
    }

#endif
