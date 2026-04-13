import AIQAPIClientCore
import AIQSharedKit
import Foundation

/// ViewModel for the group detail/leaderboard screen
@MainActor
class GroupDetailViewModel: BaseViewModel {
    // MARK: - Published Properties

    @Published var group: Components.Schemas.GroupDetailResponse?
    @Published var leaderboard: Components.Schemas.LeaderboardResponse?
    @Published var showInviteSheet = false
    @Published var showDeleteConfirmation = false
    @Published var showLeaveConfirmation = false

    // MARK: - Private Properties

    private let apiService: OpenAPIServiceProtocol
    private let authManager: AuthManagerProtocol
    let groupId: Int

    // MARK: - Initialization

    init(apiService: OpenAPIServiceProtocol, authManager: AuthManagerProtocol, groupId: Int) {
        self.apiService = apiService
        self.authManager = authManager
        self.groupId = groupId
        super.init()
    }

    // MARK: - Public Methods

    /// Fetch group detail and leaderboard in parallel
    func fetchGroupData() async {
        setLoading(true)
        clearError()
        do {
            async let groupResult = apiService.getGroup(groupId: groupId)
            async let leaderboardResult = apiService.getLeaderboard(groupId: groupId)
            group = try await groupResult
            leaderboard = try await leaderboardResult
            setLoading(false)
        } catch is CancellationError {
            return
        } catch {
            handleError(error, context: "fetchGroupData") { [weak self] in
                await self?.fetchGroupData()
            }
        }
    }

    /// Refresh group data (pull-to-refresh)
    func refreshGroupData() async {
        await withRefreshing {
            await self.fetchGroupData()
        }
    }

    /// Generate a new invite code for this group
    func generateInvite() async -> Components.Schemas.GroupInviteResponse? {
        do {
            return try await apiService.generateInvite(groupId: groupId)
        } catch {
            handleError(error, context: "generateInvite")
            return nil
        }
    }

    /// Remove a member from the group
    func removeMember(userId: Int) async {
        do {
            try await apiService.removeMember(groupId: groupId, userId: userId)
            await fetchGroupData()
        } catch {
            handleError(error, context: "removeMember")
        }
    }

    /// Leave the group (non-owner members only)
    func leaveGroup() async -> Bool {
        guard let userId = currentUserId else { return false }
        do {
            try await apiService.removeMember(groupId: groupId, userId: userId)
            return true
        } catch {
            handleError(error, context: "leaveGroup")
            return false
        }
    }

    /// Delete the group (owner only)
    func deleteGroup() async -> Bool {
        do {
            try await apiService.deleteGroup(groupId: groupId)
            return true
        } catch {
            handleError(error, context: "deleteGroup")
            return false
        }
    }

    // MARK: - Computed Properties

    /// Current user's ID
    var currentUserId: Int? {
        authManager.currentUser?.id
    }

    /// Whether the current user is the owner of this group
    var isOwner: Bool {
        guard let userId = currentUserId else { return false }
        return group?.createdBy == userId
    }

    /// The invite code for sharing
    var inviteCode: String? {
        group?.inviteCode
    }

    /// The invite link to share
    var inviteLink: String? {
        guard let code = inviteCode else { return nil }
        return "aiq://groups/join?code=\(code)"
    }
}
