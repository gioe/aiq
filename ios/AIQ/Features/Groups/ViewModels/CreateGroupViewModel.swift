import AIQAPIClientCore
import AIQSharedKit
import Foundation

/// ViewModel for the create group screen
@MainActor
class CreateGroupViewModel: BaseViewModel {
    // MARK: - Published Properties

    @Published var groupName: String = ""
    @Published var createdGroup: Components.Schemas.GroupResponse?

    // MARK: - Private Properties

    private let apiService: OpenAPIServiceProtocol

    // MARK: - Constants

    static let maxGroupNameLength = 30

    // MARK: - Initialization

    init(apiService: OpenAPIServiceProtocol) {
        self.apiService = apiService
        super.init()
    }

    // MARK: - Public Methods

    /// Create a new group with the current name
    func createGroup() async -> Bool {
        let trimmedName = groupName.trimmingCharacters(in: .whitespacesAndNewlines)
        guard isValidGroupName else { return false }

        setLoading(true)
        clearError()
        do {
            createdGroup = try await apiService.createGroup(name: trimmedName)
            setLoading(false)
            return true
        } catch {
            handleError(error, context: "createGroup") { [weak self] in
                _ = await self?.createGroup()
            }
            return false
        }
    }

    // MARK: - Computed Properties

    /// Whether the group name is valid
    var isValidGroupName: Bool {
        let trimmed = groupName.trimmingCharacters(in: .whitespacesAndNewlines)
        return !trimmed.isEmpty && trimmed.count <= Self.maxGroupNameLength
    }

    /// Remaining characters for the group name
    var remainingCharacters: Int {
        Self.maxGroupNameLength - groupName.count
    }
}
