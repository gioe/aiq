import Combine
import Foundation
@testable import AIQ

/// Mock implementation of AuthManager for testing
@MainActor
class MockAuthManager: ObservableObject, AuthManagerProtocol {
    @Published var isAuthenticated: Bool = false
    @Published var currentUser: User?
    @Published var isLoading: Bool = false
    @Published var authError: Error?

    var isLoadingPublisher: Published<Bool>.Publisher { $isLoading }
    var authErrorPublisher: Published<Error?>.Publisher { $authError }

    // Test configuration
    var shouldSucceedLogin: Bool = true
    var shouldSucceedRegister: Bool = true
    var loginDelay: TimeInterval = 0
    var registerDelay: TimeInterval = 0

    // Track method calls
    var loginCalled: Bool = false
    var registerCalled: Bool = false
    var logoutCalled: Bool = false
    var clearErrorCalled: Bool = false

    // Stored credentials for verification
    var lastLoginEmail: String?
    var lastLoginPassword: String?
    var lastRegisterEmail: String?
    var lastRegisterPassword: String?
    var lastRegisterFirstName: String?
    var lastRegisterLastName: String?

    func register(
        email: String,
        password: String,
        firstName: String,
        lastName: String
    ) async throws {
        registerCalled = true
        lastRegisterEmail = email
        lastRegisterPassword = password
        lastRegisterFirstName = firstName
        lastRegisterLastName = lastName

        isLoading = true
        authError = nil

        if registerDelay > 0 {
            try await Task.sleep(nanoseconds: UInt64(registerDelay * 1_000_000_000))
        }

        if shouldSucceedRegister {
            let mockUser = User(
                id: "test-user-id",
                email: email,
                firstName: firstName,
                lastName: lastName,
                createdAt: Date(),
                lastLoginAt: nil,
                notificationEnabled: false
            )
            isAuthenticated = true
            currentUser = mockUser
            isLoading = false
        } else {
            let error = NSError(
                domain: "MockAuthManager",
                code: -1,
                userInfo: [NSLocalizedDescriptionKey: "Registration failed"]
            )
            authError = error
            isLoading = false
            throw error
        }
    }

    func login(email: String, password: String) async throws {
        loginCalled = true
        lastLoginEmail = email
        lastLoginPassword = password

        isLoading = true
        authError = nil

        if loginDelay > 0 {
            try await Task.sleep(nanoseconds: UInt64(loginDelay * 1_000_000_000))
        }

        if shouldSucceedLogin {
            let mockUser = User(
                id: "test-user-id",
                email: email,
                firstName: "Test",
                lastName: "User",
                createdAt: Date(),
                lastLoginAt: Date(),
                notificationEnabled: true
            )
            isAuthenticated = true
            currentUser = mockUser
            isLoading = false
        } else {
            let error = NSError(
                domain: "MockAuthManager",
                code: -1,
                userInfo: [NSLocalizedDescriptionKey: "Invalid credentials"]
            )
            authError = error
            isLoading = false
            throw error
        }
    }

    func logout() async {
        logoutCalled = true
        isLoading = true
        isAuthenticated = false
        currentUser = nil
        isLoading = false
        authError = nil
    }

    func clearError() {
        clearErrorCalled = true
        authError = nil
    }

    // Test helper methods
    func reset() {
        isAuthenticated = false
        currentUser = nil
        isLoading = false
        authError = nil
        shouldSucceedLogin = true
        shouldSucceedRegister = true
        loginDelay = 0
        registerDelay = 0
        loginCalled = false
        registerCalled = false
        logoutCalled = false
        clearErrorCalled = false
        lastLoginEmail = nil
        lastLoginPassword = nil
        lastRegisterEmail = nil
        lastRegisterPassword = nil
        lastRegisterFirstName = nil
        lastRegisterLastName = nil
    }
}
