import Combine
import Foundation

/// ViewModel for managing settings and account actions.
///
/// ## Concurrency
/// This class is `@MainActor`-isolated, ensuring all property access and method calls
/// execute on the main thread. The `logout()` and `deleteAccount()` methods include
/// guards to prevent concurrent execution if called multiple times before completion.
///
/// ## Error Handling Architecture
/// This ViewModel uses a **hybrid error handling approach**:
///
/// - **`error` (inherited from BaseViewModel)**: Used for general operations where:
///   - ErrorBanner/ErrorView display is appropriate
///   - The operation can be retried (e.g., network requests, data fetches)
///   - Standard error presentation is acceptable
///
/// - **`deleteAccountError` (operation-specific)**: Used for delete account because:
///   - Requires a specific alert title ("Delete Account Failed") for clarity
///   - Should not trigger retry logic (account deletion is not retryable)
///   - AuthManager already records the error to Crashlytics
///   - Uses a modal alert rather than inline error display
///
/// This pattern is intentional. When an operation requires specialized error
/// presentation (custom titles, different UI treatment), use an operation-specific
/// error property rather than forcing all errors through `handleError()`.
@MainActor
class SettingsViewModel: BaseViewModel {
    // MARK: - Published Properties

    @Published var currentUser: User?
    @Published var showLogoutConfirmation = false
    @Published var showDeleteAccountConfirmation = false

    /// Error from delete account operation. Uses a separate property (not BaseViewModel.error)
    /// because delete account requires a specific alert title and should not trigger retry logic.
    /// See class documentation for the full architectural rationale.
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

    /// Perform logout.
    ///
    /// This method should not be called concurrently. The guard ensures idempotent
    /// behavior if the UI accidentally triggers multiple logout attempts.
    func logout() async {
        guard !isLoggingOut else { return }

        isLoggingOut = true
        clearError()

        await authManager.logout()

        isLoggingOut = false
        // Navigation to welcome screen is handled automatically by auth state change
    }

    /// Delete user account.
    ///
    /// This method should not be called concurrently. The guard ensures idempotent
    /// behavior if the UI accidentally triggers multiple delete attempts.
    func deleteAccount() async {
        guard !isDeletingAccount else { return }

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
            // Uses deleteAccountError instead of handleError() - see class documentation for rationale
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
