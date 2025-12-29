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
}
