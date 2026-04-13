import AIQAPIClientCore
import AIQSharedKit
import Foundation

/// ViewModel for the join group screen
@MainActor
class JoinGroupViewModel: BaseViewModel {
    // MARK: - Published Properties

    @Published var inviteCode: String = ""
    @Published var joinedGroup: Components.Schemas.GroupResponse?

    // MARK: - Private Properties

    private let apiService: OpenAPIServiceProtocol

    // MARK: - Initialization

    init(apiService: OpenAPIServiceProtocol) {
        self.apiService = apiService
        super.init()
    }

    // MARK: - Public Methods

    /// Join a group using the invite code
    func joinGroup() async -> Bool {
        let trimmedCode = inviteCode.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedCode.isEmpty else { return false }

        setLoading(true)
        clearError()
        do {
            joinedGroup = try await apiService.joinGroup(inviteCode: trimmedCode)
            setLoading(false)
            return true
        } catch {
            handleError(error, context: "joinGroup") { [weak self] in
                _ = await self?.joinGroup()
            }
            return false
        }
    }

    // MARK: - Computed Properties

    /// Whether the invite code is valid for submission
    var isValidCode: Bool {
        !inviteCode.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }
}
