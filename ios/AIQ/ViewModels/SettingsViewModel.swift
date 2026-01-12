import Combine
import Foundation

/// ViewModel for managing settings and account actions
@MainActor
class SettingsViewModel: BaseViewModel {
    // MARK: - Published Properties

    @Published var currentUser: User?
    @Published var showLogoutConfirmation = false
    @Published var showDeleteAccountConfirmation = false
    @Published var deleteAccountError: Error?
    @Published var isLoggingOut = false
    @Published var isDeletingAccount = false
    @Published var showOnboarding = false

    // MARK: - Private Properties

    private let authManager: AuthManagerProtocol

    // MARK: - Initialization

    /// Initialize the ViewModel with dependencies
    /// - Parameter authManager: Authentication manager for account operations
    init(authManager: AuthManagerProtocol) {
        self.authManager = authManager
        super.init()

        // Observe current user from AuthManager
        authManager.isAuthenticatedPublisher
            .sink { [weak self] _ in
                self?.currentUser = authManager.currentUser
            }
            .store(in: &cancellables)

        // Set initial user
        currentUser = authManager.currentUser
    }

    // MARK: - Public Methods

    /// Perform logout
    func logout() async {
        isLoggingOut = true
        clearError()

        await authManager.logout()

        isLoggingOut = false
        // Navigation to welcome screen is handled automatically by auth state change
    }

    /// Delete user account
    func deleteAccount() async {
        isDeletingAccount = true
        deleteAccountError = nil
        clearError()

        do {
            try await authManager.deleteAccount()
            isDeletingAccount = false
            // Navigation to welcome screen is handled automatically by auth state change
        } catch {
            deleteAccountError = error
            isDeletingAccount = false
            // Note: AuthManager already logs this error to Crashlytics with proper context
            // We don't need to call handleError here since we're setting deleteAccountError
        }
    }

    /// Show logout confirmation dialog
    func showLogoutDialog() {
        showLogoutConfirmation = true
    }

    /// Show delete account confirmation dialog
    func showDeleteAccountDialog() {
        showDeleteAccountConfirmation = true
    }

    /// Show onboarding flow
    func showOnboardingFlow() {
        showOnboarding = true
    }

    /// Clear delete account error
    func clearDeleteAccountError() {
        deleteAccountError = nil
    }
}
