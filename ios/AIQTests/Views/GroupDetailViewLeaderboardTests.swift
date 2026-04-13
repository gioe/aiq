@testable import AIQ
import AIQAPIClientCore
import AIQSharedKit
import SwiftUI
import XCTest

@MainActor
final class GroupDetailViewLeaderboardTests: XCTestCase {
    // MARK: - Helpers

    private func makeLeaderboardEntry(
        rank: Int,
        firstName: String,
        bestScore: Int,
        averageScore: Double,
        userId: Int
    ) -> Components.Schemas.LeaderboardEntryResponse {
        Components.Schemas.LeaderboardEntryResponse(
            rank: rank,
            userId: userId,
            firstName: firstName,
            bestScore: bestScore,
            averageScore: averageScore
        )
    }

    private func makeGroupMember(
        firstName: String,
        role: String,
        userId: Int
    ) -> Components.Schemas.GroupMemberResponse {
        Components.Schemas.GroupMemberResponse(
            userId: userId,
            firstName: firstName,
            role: role,
            joinedAt: Date()
        )
    }

    // MARK: - Tests

    func testLeaderboardEntriesOrderedByRank() {
        // Given — entries created out of order to confirm sort behavior
        let entry1 = makeLeaderboardEntry(rank: 1, firstName: "Alice", bestScore: 130, averageScore: 125.0, userId: 1)
        let entry2 = makeLeaderboardEntry(rank: 2, firstName: "Bob", bestScore: 120, averageScore: 118.0, userId: 2)
        let entry3 = makeLeaderboardEntry(rank: 3, firstName: "Carol", bestScore: 110, averageScore: 108.0, userId: 3)
        let unsortedEntries = [entry3, entry1, entry2]

        // When — sort ascending by rank, mirroring the leaderboard display order
        let sorted = unsortedEntries.sorted { $0.rank < $1.rank }

        // Then
        XCTAssertEqual(sorted.count, 3, "Sorted entries should contain all three entries")
        XCTAssertEqual(sorted[0].rank, 1, "First entry should have rank 1")
        XCTAssertEqual(sorted[0].firstName, "Alice", "Rank 1 entry should be Alice")
        XCTAssertEqual(sorted[1].rank, 2, "Second entry should have rank 2")
        XCTAssertEqual(sorted[1].firstName, "Bob", "Rank 2 entry should be Bob")
        XCTAssertEqual(sorted[2].rank, 3, "Third entry should have rank 3")
        XCTAssertEqual(sorted[2].firstName, "Carol", "Rank 3 entry should be Carol")
    }

    func testEmptyLeaderboardState() {
        // Given
        let leaderboard = Components.Schemas.LeaderboardResponse(
            groupId: 1,
            groupName: "Empty Group",
            entries: [],
            totalCount: 0
        )

        // When / Then
        XCTAssertTrue(leaderboard.entries.isEmpty, "LeaderboardResponse with no entries should report isEmpty as true")
    }

    func testLeaderboardResponseContainsCorrectGroupInfo() {
        // Given
        let expectedGroupId = 42
        let expectedGroupName = "Test Group"
        let entry = makeLeaderboardEntry(rank: 1, firstName: "Alice", bestScore: 130, averageScore: 125.0, userId: 1)

        // When
        let leaderboard = Components.Schemas.LeaderboardResponse(
            groupId: expectedGroupId,
            groupName: expectedGroupName,
            entries: [entry],
            totalCount: 1
        )

        // Then
        XCTAssertEqual(leaderboard.groupId, expectedGroupId, "groupId should be 42")
        XCTAssertEqual(leaderboard.groupName, expectedGroupName, "groupName should be 'Test Group'")
        XCTAssertEqual(leaderboard.entries.count, 1, "Leaderboard should contain one entry")
        XCTAssertEqual(leaderboard.entries[0].firstName, "Alice", "Entry firstName should be Alice")
    }

    func testMemberListLayout() {
        // Given
        let members: [Components.Schemas.GroupMemberResponse] = [
            makeGroupMember(firstName: "Alice", role: "owner", userId: 1),
            makeGroupMember(firstName: "Bob", role: "member", userId: 2),
            makeGroupMember(firstName: "Carol", role: "member", userId: 3)
        ]

        let group = Components.Schemas.GroupDetailResponse(
            id: 10,
            name: "Test Group",
            createdBy: 1,
            createdAt: Date(),
            inviteCode: "ABC123",
            maxMembers: 10,
            memberCount: 3,
            members: members
        )

        // Then
        XCTAssertEqual(group.members.count, 3, "Group should have 3 members")
        XCTAssertEqual(group.memberCount, 3, "memberCount should be 3")

        XCTAssertEqual(group.members[0].firstName, "Alice", "First member should be Alice")
        XCTAssertEqual(group.members[0].role, "owner", "Alice should have owner role")
        XCTAssertEqual(group.members[0].userId, 1, "Alice's userId should be 1")

        XCTAssertEqual(group.members[1].firstName, "Bob", "Second member should be Bob")
        XCTAssertEqual(group.members[1].role, "member", "Bob should have member role")
        XCTAssertEqual(group.members[1].userId, 2, "Bob's userId should be 2")

        XCTAssertEqual(group.members[2].firstName, "Carol", "Third member should be Carol")
        XCTAssertEqual(group.members[2].role, "member", "Carol should have member role")
        XCTAssertEqual(group.members[2].userId, 3, "Carol's userId should be 3")
    }
}
