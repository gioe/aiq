import AIQAPIClientCore
import AIQSharedKit
import Foundation

/// ViewModel for the groups list screen
@MainActor
class GroupsListViewModel: BaseViewModel {
    // MARK: - Published Properties

    @Published var groups: [Components.Schemas.GroupResponse] = []

    // MARK: - Private Properties

    private let apiService: OpenAPIServiceProtocol

    // MARK: - Initialization

    init(apiService: OpenAPIServiceProtocol) {
        self.apiService = apiService
        super.init()
    }

    // MARK: - Public Methods

    /// Fetch all groups the user belongs to
    func fetchGroups() async {
        setLoading(true)
        clearError()
        do {
            groups = try await apiService.listGroups()
            setLoading(false)
        } catch is CancellationError {
            return
        } catch {
            handleError(error, context: "fetchGroups") { [weak self] in
                await self?.fetchGroups()
            }
        }
    }

    /// Refresh groups (pull-to-refresh)
    func refreshGroups() async {
        await withRefreshing {
            await self.fetchGroups()
        }
    }

    // MARK: - Computed Properties

    /// Whether the user has any groups
    var hasGroups: Bool {
        !groups.isEmpty
    }
}
