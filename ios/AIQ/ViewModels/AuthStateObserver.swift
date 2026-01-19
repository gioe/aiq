import Combine
import Foundation
import SwiftUI

/// Observable wrapper for AuthManagerProtocol
///
/// This class enables SwiftUI views to observe any `AuthManagerProtocol` implementation
/// through `@StateObject` or `@ObservedObject`. It subscribes to the protocol's
/// Combine publishers and exposes the state as `@Published` properties.
///
/// ## Usage
///
/// ```swift
/// struct SomeView: View {
///     @StateObject private var authState = AuthStateObserver()
///
///     var body: some View {
///         if authState.isAuthenticated {
///             MainView()
///         } else {
///             LoginView()
///         }
///     }
/// }
/// ```
///
/// ## Thread Safety
///
/// This class uses `@MainActor` to ensure all property updates occur on the main thread,
/// which is required for SwiftUI view updates.
@MainActor
final class AuthStateObserver: ObservableObject {
    // MARK: - Published State

    @Published private(set) var isAuthenticated: Bool = false
    @Published private(set) var isLoading: Bool = false
    @Published private(set) var authError: Error?
    @Published private(set) var currentUser: User?

    // MARK: - Private Properties

    private let authManager: any AuthManagerProtocol
    private var cancellables = Set<AnyCancellable>()

    // MARK: - Initialization

    /// Creates an observer for the AuthManager resolved from the service container
    ///
    /// - Parameter container: The service container to resolve the AuthManager from.
    ///                        Defaults to the shared container.
    init(container: ServiceContainer = .shared) {
        guard let manager = container.resolve(AuthManagerProtocol.self) else {
            fatalError("AuthManagerProtocol not registered in ServiceContainer")
        }
        authManager = manager

        // Set initial state
        isAuthenticated = manager.isAuthenticated
        isLoading = manager.isLoading
        authError = manager.authError
        currentUser = manager.currentUser

        // Subscribe to publishers
        setupSubscriptions()
    }

    /// Creates an observer with an explicit AuthManager (for testing)
    ///
    /// - Parameter authManager: The auth manager to observe
    init(authManager: any AuthManagerProtocol) {
        self.authManager = authManager

        // Set initial state
        isAuthenticated = authManager.isAuthenticated
        isLoading = authManager.isLoading
        authError = authManager.authError
        currentUser = authManager.currentUser

        // Subscribe to publishers
        setupSubscriptions()
    }

    // MARK: - Setup

    private func setupSubscriptions() {
        authManager.isAuthenticatedPublisher
            .receive(on: DispatchQueue.main)
            .sink { [weak self] value in
                print("[AuthStateObserver] Received isAuthenticated update: \(value)")
                self?.isAuthenticated = value
            }
            .store(in: &cancellables)

        authManager.isLoadingPublisher
            .receive(on: DispatchQueue.main)
            .sink { [weak self] value in
                self?.isLoading = value
            }
            .store(in: &cancellables)

        authManager.authErrorPublisher
            .receive(on: DispatchQueue.main)
            .sink { [weak self] value in
                self?.authError = value
            }
            .store(in: &cancellables)
    }

    // MARK: - Actions (Delegate to AuthManager)

    func restoreSession() async {
        await authManager.restoreSession()
    }

    func login(email: String, password: String) async throws {
        try await authManager.login(email: email, password: password)
    }

    func logout() async {
        await authManager.logout()
    }

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
        try await authManager.register(
            email: email,
            password: password,
            firstName: firstName,
            lastName: lastName,
            birthYear: birthYear,
            educationLevel: educationLevel,
            country: country,
            region: region
        )
    }

    func deleteAccount() async throws {
        try await authManager.deleteAccount()
    }

    func clearError() {
        authManager.clearError()
    }
}
