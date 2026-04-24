import AIQAPIClientCore
import Combine
import Foundation

#if DebugBuild

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
        @Published var guestResultClaimStatus: GuestResultClaimStatus = .idle

        var userFullName: String? {
            currentUser?.email
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

            case .loggedInNoHistory, .loggedInWithHistory, .loggedInWithHistoryNilDate, .testInProgress,
                 .startTestNetworkFailure, .startTestFailureThenSuccess, .startTestNonRetryableFailure,
                 .memoryInProgress, .timerExpiredZeroAnswers, .timerExpiredWithAnswers,
                 .notificationsDisabled, .timerNearWarning:
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

        func prepareGuestResultClaim(token: String?) {
            guestResultClaimStatus = token?.isEmpty == false ? .pending : .missingToken
        }

        // swiftlint:disable:next function_parameter_count
        func register(
            email: String,
            password _: String,
            firstName _: String,
            lastName _: String,
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
                    id: 1,
                    email: email,
                    createdAt: Date(),
                    notificationEnabled: false,
                    isAdmin: false
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
                APIError.api(.timeout)
            case .serverError:
                APIError.api(.serverError(statusCode: 500, message: "Internal server error"))
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
                    id: 1,
                    email: email,
                    createdAt: Date(),
                    notificationEnabled: true,
                    isAdmin: false
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

        func loginWithApple(identityToken _: String) async throws {
            print("[UITestMockAuthManager] loginWithApple() called")
            isLoading = true
            authError = nil

            try await Task.sleep(nanoseconds: 300_000_000) // 0.3 seconds

            if shouldSucceedLogin {
                isAuthenticated = true
                currentUser = Components.Schemas.UserResponse(
                    id: 1,
                    email: "apple-user@example.com",
                    createdAt: Date(),
                    notificationEnabled: true,
                    isAdmin: false
                )
                isLoading = false
            } else {
                let error = NSError(
                    domain: "UITestMockAuthManager",
                    code: -1,
                    userInfo: [NSLocalizedDescriptionKey: "Invalid Apple identity token"]
                )
                authError = error
                isLoading = false
                throw error
            }
        }

        func loginWithGoogle(identityToken _: String) async throws {
            print("[UITestMockAuthManager] loginWithGoogle() called")
            isLoading = true
            authError = nil

            try await Task.sleep(nanoseconds: 300_000_000) // 0.3 seconds

            if shouldSucceedLogin {
                isAuthenticated = true
                currentUser = Components.Schemas.UserResponse(
                    id: 1,
                    email: "google-user@example.com",
                    createdAt: Date(),
                    notificationEnabled: true,
                    isAdmin: false
                )
                isLoading = false
            } else {
                let error = NSError(
                    domain: "UITestMockAuthManager",
                    code: -1,
                    userInfo: [NSLocalizedDescriptionKey: "Invalid Google identity token"]
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
            id: 1,
            email: "john@example.com",
            firstName: "John",
            createdAt: Date().addingTimeInterval(-30 * 24 * 60 * 60), // 30 days ago
            notificationEnabled: true,
            isAdmin: false
        )
    }

#endif
