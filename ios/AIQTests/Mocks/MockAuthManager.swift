@testable import AIQ
import AIQAPIClient
import Combine
import Foundation

/// Mock implementation of AuthManager for testing
@MainActor
class MockAuthManager: ObservableObject, AuthManagerProtocol {
    @Published var isAuthenticated: Bool = false
    @Published var currentUser: User?
    @Published var isLoading: Bool = false
    @Published var authError: Error?

    var isAuthenticatedPublisher: Published<Bool>.Publisher { $isAuthenticated }
    var isLoadingPublisher: Published<Bool>.Publisher { $isLoading }
    var authErrorPublisher: Published<Error?>.Publisher { $authError }

    // Test configuration
    var shouldSucceedLogin: Bool = true
    var shouldSucceedRegister: Bool = true
    var shouldSucceedDeleteAccount: Bool = true
    var loginDelay: TimeInterval = 0
    var registerDelay: TimeInterval = 0
    var logoutDelay: TimeInterval = 0
    var deleteAccountDelay: TimeInterval = 0

    // Track method calls
    var loginCalled: Bool = false
    var registerCalled: Bool = false
    var logoutCalled: Bool = false
    var deleteAccountCalled: Bool = false
    var clearErrorCalled: Bool = false

    // Stored credentials for verification
    var lastLoginEmail: String?
    var lastLoginPassword: String?
    var lastRegisterEmail: String?
    var lastRegisterPassword: String?
    var lastRegisterFirstName: String?
    var lastRegisterLastName: String?
    var lastRegisterBirthYear: Int?
    var lastRegisterEducationLevel: EducationLevel?
    var lastRegisterCountry: String?
    var lastRegisterRegion: String?

    func register(
        email: String,
        password: String,
        firstName: String,
        lastName: String,
        birthYear: Int? = nil,
        educationLevel: EducationLevel? = nil,
        country: String? = nil,
        region: String? = nil
    ) async throws {
        registerCalled = true
        lastRegisterEmail = email
        lastRegisterPassword = password
        lastRegisterFirstName = firstName
        lastRegisterLastName = lastName
        lastRegisterBirthYear = birthYear
        lastRegisterEducationLevel = educationLevel
        lastRegisterCountry = country
        lastRegisterRegion = region

        isLoading = true
        authError = nil

        if registerDelay > 0 {
            try await Task.sleep(nanoseconds: UInt64(registerDelay * 1_000_000_000))
        }

        if shouldSucceedRegister {
            // Note: Generated UserResponse type only has required fields.
            // Demographic fields (birthYear, educationLevel, country, region) are not available.
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
            let mockUser = Components.Schemas.UserResponse(
                createdAt: Date(),
                email: email,
                firstName: "Test",
                id: 1,
                lastName: "User",
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

        if logoutDelay > 0 {
            try? await Task.sleep(nanoseconds: UInt64(logoutDelay * 1_000_000_000))
        }

        isAuthenticated = false
        currentUser = nil
        isLoading = false
        authError = nil
    }

    func deleteAccount() async throws {
        deleteAccountCalled = true
        isLoading = true
        authError = nil

        if deleteAccountDelay > 0 {
            try await Task.sleep(nanoseconds: UInt64(deleteAccountDelay * 1_000_000_000))
        }

        if shouldSucceedDeleteAccount {
            isAuthenticated = false
            currentUser = nil
            isLoading = false
        } else {
            let error = NSError(
                domain: "MockAuthManager",
                code: -1,
                userInfo: [NSLocalizedDescriptionKey: "Failed to delete account"]
            )
            authError = error
            isLoading = false
            throw error
        }
    }

    func clearError() {
        clearErrorCalled = true
        authError = nil
    }

    func restoreSession() async {
        // No-op for unit tests - state is configured directly
    }

    // Test helper methods
    func reset() {
        isAuthenticated = false
        currentUser = nil
        isLoading = false
        authError = nil
        shouldSucceedLogin = true
        shouldSucceedRegister = true
        shouldSucceedDeleteAccount = true
        loginDelay = 0
        registerDelay = 0
        logoutDelay = 0
        deleteAccountDelay = 0
        loginCalled = false
        registerCalled = false
        logoutCalled = false
        deleteAccountCalled = false
        clearErrorCalled = false
        lastLoginEmail = nil
        lastLoginPassword = nil
        lastRegisterEmail = nil
        lastRegisterPassword = nil
        lastRegisterFirstName = nil
        lastRegisterLastName = nil
        lastRegisterBirthYear = nil
        lastRegisterEducationLevel = nil
        lastRegisterCountry = nil
        lastRegisterRegion = nil
    }
}
