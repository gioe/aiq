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
///   - Error is recorded to Crashlytics via the injected `errorRecorder`
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
    @Published var isBiometricEnabled: Bool = false

    /// Error from delete account operation. Uses a separate property (not BaseViewModel.error)
    /// because delete account requires a specific alert title and should not trigger retry logic.
    /// See class documentation for the full architectural rationale.
    @Published var deleteAccountError: Error?
    @Published var isLoggingOut = false
    @Published var isDeletingAccount = false
    @Published var showOnboarding = false

    // MARK: - Type Aliases

    /// Closure type for error recording. Used for dependency injection to enable testing.
    typealias ErrorRecorder = (Error, CrashlyticsErrorRecorder.ErrorContext) -> Void

    // MARK: - Computed Properties

    var isBiometricAvailable: Bool {
        biometricAuthManager.isBiometricAvailable
    }

    var biometricType: BiometricType {
        biometricAuthManager.biometricType
    }

    // MARK: - Private Properties

    private let authManager: AuthManagerProtocol
    private let biometricAuthManager: BiometricAuthManagerProtocol
    private let biometricPreferenceStorage: BiometricPreferenceStorageProtocol
    private let errorRecorder: ErrorRecorder

    // MARK: - Initialization

    /// Initialize the ViewModel with dependencies
    /// - Parameters:
    ///   - authManager: Authentication manager for account operations
    ///   - biometricAuthManager: Manager for querying biometric availability and type
    ///   - biometricPreferenceStorage: Storage for persisting the biometric toggle preference
    ///   - errorRecorder: Closure for recording errors (defaults to CrashlyticsErrorRecorder)
    init(
        authManager: AuthManagerProtocol,
        biometricAuthManager: BiometricAuthManagerProtocol,
        biometricPreferenceStorage: BiometricPreferenceStorageProtocol,
        errorRecorder: @escaping ErrorRecorder = { CrashlyticsErrorRecorder.recordError($0, context: $1) }
    ) {
        self.authManager = authManager
        self.biometricAuthManager = biometricAuthManager
        self.biometricPreferenceStorage = biometricPreferenceStorage
        self.errorRecorder = errorRecorder
        super.init()

        // Load saved biometric preference
        isBiometricEnabled = biometricPreferenceStorage.isBiometricEnabled

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
    ///
    /// - Note: Unlike `deleteAccount()`, this method does not require error handling because
    ///   `AuthManagerProtocol.logout()` is non-throwing by design. The AuthManager catches any
    ///   server-side errors internally and always completes the local logout regardless of
    ///   network failures. This ensures users can always sign out, even offline.
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
            // Record to Crashlytics for production monitoring
            // Uses deleteAccountError instead of handleError() - see class documentation for rationale
            errorRecorder(error, .deleteAccount)
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

    /// Toggle biometric authentication on or off
    func toggleBiometric() {
        isBiometricEnabled.toggle()
        biometricPreferenceStorage.isBiometricEnabled = isBiometricEnabled
    }
}
