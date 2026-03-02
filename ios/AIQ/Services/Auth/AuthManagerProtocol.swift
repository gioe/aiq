import Combine
import Foundation

/// Protocol defining the public interface of AuthManager
@MainActor
protocol AuthManagerProtocol: AnyObject {
    var isAuthenticated: Bool { get }
    var currentUser: User? { get }
    var isLoading: Bool { get }
    var authError: Error? { get }

    var isAuthenticatedPublisher: Published<Bool>.Publisher { get }
    var isLoadingPublisher: Published<Bool>.Publisher { get }
    var authErrorPublisher: Published<Error?>.Publisher { get }

    /// The authenticated user's full name, or nil if not authenticated
    var userFullName: String? { get }

    func register( // swiftlint:disable:this function_parameter_count
        email: String,
        password: String,
        firstName: String,
        lastName: String,
        birthYear: Int?,
        educationLevel: EducationLevel?,
        country: String?,
        region: String?
    ) async throws

    func login(email: String, password: String) async throws
    func logout() async
    func deleteAccount() async throws
    func clearError()

    /// Restore session from stored credentials
    ///
    /// Called on app launch to restore authentication state from secure storage.
    /// For mock implementations, this may be a no-op if state is pre-configured.
    func restoreSession() async
}
