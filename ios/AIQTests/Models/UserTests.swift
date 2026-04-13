@testable import AIQ
import AIQAPIClientCore
import AIQSharedKit
import XCTest

final class UserTests: XCTestCase {
    // MARK: - EducationLevel Tests

    func testEducationLevelDisplayNames() {
        XCTAssertEqual(EducationLevel.highSchool.displayName, "High School")
        XCTAssertEqual(EducationLevel.someCollege.displayName, "Some College")
        XCTAssertEqual(EducationLevel.associates.displayName, "Associate's Degree")
        XCTAssertEqual(EducationLevel.bachelors.displayName, "Bachelor's Degree")
        XCTAssertEqual(EducationLevel.masters.displayName, "Master's Degree")
        XCTAssertEqual(EducationLevel.doctorate.displayName, "Doctorate")
        XCTAssertEqual(EducationLevel.preferNotToSay.displayName, "Prefer not to say")
    }

    func testEducationLevelRawValues() {
        XCTAssertEqual(EducationLevel.highSchool.rawValue, "high_school")
        XCTAssertEqual(EducationLevel.someCollege.rawValue, "some_college")
        XCTAssertEqual(EducationLevel.associates.rawValue, "associates")
        XCTAssertEqual(EducationLevel.bachelors.rawValue, "bachelors")
        XCTAssertEqual(EducationLevel.masters.rawValue, "masters")
        XCTAssertEqual(EducationLevel.doctorate.rawValue, "doctorate")
        XCTAssertEqual(EducationLevel.preferNotToSay.rawValue, "prefer_not_to_say")
    }

    func testEducationLevelCaseIterable() {
        let allCases = EducationLevel.allCases
        XCTAssertEqual(allCases.count, 7)
        XCTAssertTrue(allCases.contains(.highSchool))
        XCTAssertTrue(allCases.contains(.someCollege))
        XCTAssertTrue(allCases.contains(.associates))
        XCTAssertTrue(allCases.contains(.bachelors))
        XCTAssertTrue(allCases.contains(.masters))
        XCTAssertTrue(allCases.contains(.doctorate))
        XCTAssertTrue(allCases.contains(.preferNotToSay))
    }

    func testEducationLevelDecoding() throws {
        let json = """
        "bachelors"
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let educationLevel = try JSONDecoder().decode(EducationLevel.self, from: data)

        XCTAssertEqual(educationLevel, .bachelors)
        XCTAssertEqual(educationLevel.displayName, "Bachelor's Degree")
    }

    func testEducationLevelDecodingWithSnakeCase() throws {
        let json = """
        "high_school"
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let educationLevel = try JSONDecoder().decode(EducationLevel.self, from: data)

        XCTAssertEqual(educationLevel, .highSchool)
        XCTAssertEqual(educationLevel.displayName, "High School")
    }

    // MARK: - User Decoding Tests

    func testUserDecodingWithRequiredFields() throws {
        let json = """
        {
            "id": 123,
            "email": "test@example.com",
            "created_at": "2025-01-01T10:00:00Z",
            "notification_enabled": true,
            "is_admin": false
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let user = try decoder.decode(User.self, from: data)

        XCTAssertEqual(user.id, 123)
        XCTAssertEqual(user.email, "test@example.com")
        XCTAssertTrue(user.notificationEnabled)
        XCTAssertFalse(user.isAdmin)
        XCTAssertNotNil(user.createdAt)
    }

    func testUserDecodingCodingKeysMapping() throws {
        let json = """
        {
            "id": 1,
            "email": "keys@example.com",
            "created_at": "2025-01-01T10:00:00Z",
            "notification_enabled": false,
            "is_admin": true
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let user = try decoder.decode(User.self, from: data)

        XCTAssertFalse(user.notificationEnabled)
        XCTAssertTrue(user.isAdmin)
        XCTAssertNotNil(user.createdAt)
    }

    // MARK: - User Computed Properties Tests

    func testUserEquality() {
        let date = Date()
        let user1 = Components.Schemas.UserResponse(
            id: 1,
            email: "test@example.com",
            createdAt: date,
            notificationEnabled: true,
            isAdmin: false
        )

        let user2 = Components.Schemas.UserResponse(
            id: 1,
            email: "test@example.com",
            createdAt: date,
            notificationEnabled: true,
            isAdmin: false
        )

        XCTAssertEqual(user1, user2)
    }

    func testUserInequality() {
        let date = Date()
        let user1 = Components.Schemas.UserResponse(
            id: 1,
            email: "test@example.com",
            createdAt: date,
            notificationEnabled: true,
            isAdmin: false
        )

        let user2 = Components.Schemas.UserResponse(
            id: 2,
            email: "test@example.com",
            createdAt: date,
            notificationEnabled: true,
            isAdmin: false
        )
        XCTAssertNotEqual(user1, user2)

        let user3 = Components.Schemas.UserResponse(
            id: 1,
            email: "different@example.com",
            createdAt: date,
            notificationEnabled: true,
            isAdmin: false
        )
        XCTAssertNotEqual(user1, user3)

        let user4 = Components.Schemas.UserResponse(
            id: 1,
            email: "test@example.com",
            createdAt: date,
            notificationEnabled: false,
            isAdmin: false
        )
        XCTAssertNotEqual(user1, user4)
    }

    // MARK: - User Encoding Tests

    func testUserEncodingRoundTrip() throws {
        let originalDate = Date()
        let user = Components.Schemas.UserResponse(
            id: 123,
            email: "roundtrip@example.com",
            createdAt: originalDate,
            notificationEnabled: true,
            isAdmin: false
        )

        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let data = try encoder.encode(user)

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let decodedUser = try decoder.decode(User.self, from: data)

        XCTAssertEqual(user.id, decodedUser.id)
        XCTAssertEqual(user.email, decodedUser.email)
        XCTAssertEqual(user.notificationEnabled, decodedUser.notificationEnabled)
        XCTAssertEqual(user.isAdmin, decodedUser.isAdmin)
    }

    func testUserEncodingUsesSnakeCase() throws {
        let user = Components.Schemas.UserResponse(
            id: 1,
            email: "snake@example.com",
            createdAt: Date(),
            notificationEnabled: false,
            isAdmin: true
        )

        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = .sortedKeys
        let data = try encoder.encode(user)
        let jsonString = try XCTUnwrap(String(data: data, encoding: .utf8))

        XCTAssertTrue(jsonString.contains("created_at"))
        XCTAssertTrue(jsonString.contains("notification_enabled"))
        XCTAssertTrue(jsonString.contains("is_admin"))
        XCTAssertFalse(jsonString.contains("createdAt"))
        XCTAssertFalse(jsonString.contains("notificationEnabled"))
        XCTAssertFalse(jsonString.contains("isAdmin"))
    }

    // MARK: - User Identifiable Tests

    func testUserIdentifiable() {
        let user = Components.Schemas.UserResponse(
            id: 42,
            email: "identifiable@example.com",
            createdAt: Date(),
            notificationEnabled: true,
            isAdmin: false
        )

        XCTAssertEqual(user.id, 42)
    }

    // MARK: - UserProfile Tests

    func testUserProfileDecoding() throws {
        let json = """
        {
            "first_name": "Profile",
            "last_name": "Test",
            "notification_enabled": true
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let profile = try JSONDecoder().decode(UserProfile.self, from: data)

        XCTAssertEqual(profile.firstName, "Profile")
    }

    func testUserProfileCodingKeys() throws {
        let json = """
        {
            "first_name": "First",
            "last_name": "Last",
            "notification_enabled": false
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let profile = try JSONDecoder().decode(UserProfile.self, from: data)

        XCTAssertEqual(profile.firstName, "First")
        XCTAssertEqual(profile.lastName, "Last")
        XCTAssertEqual(profile.notificationEnabled, false)
    }

    func testUserProfileEncodingRoundTrip() throws {
        let profile = UserProfile(
            firstName: "Encode",
            lastName: "Decode",
            notificationEnabled: true
        )

        let encoder = JSONEncoder()
        let data = try encoder.encode(profile)

        let decoder = JSONDecoder()
        let decodedProfile = try decoder.decode(UserProfile.self, from: data)

        XCTAssertEqual(profile, decodedProfile)
    }

    func testUserProfileEncodingUsesSnakeCase() throws {
        let profile = UserProfile(
            firstName: "Snake",
            lastName: "Case",
            notificationEnabled: false
        )

        let encoder = JSONEncoder()
        encoder.outputFormatting = .sortedKeys
        let data = try encoder.encode(profile)
        let jsonString = try XCTUnwrap(String(data: data, encoding: .utf8))

        XCTAssertTrue(jsonString.contains("first_name"))
        XCTAssertTrue(jsonString.contains("last_name"))
        XCTAssertTrue(jsonString.contains("notification_enabled"))
        XCTAssertFalse(jsonString.contains("firstName"))
        XCTAssertFalse(jsonString.contains("lastName"))
        XCTAssertFalse(jsonString.contains("notificationEnabled"))
    }

    func testUserProfileEquality() {
        let profile1 = UserProfile(
            firstName: "Equal",
            lastName: "Test",
            notificationEnabled: true
        )

        let profile2 = UserProfile(
            firstName: "Equal",
            lastName: "Test",
            notificationEnabled: true
        )

        XCTAssertEqual(profile1, profile2)
    }

    func testUserProfileInequality() {
        let profile1 = UserProfile(
            firstName: "First",
            lastName: "Last",
            notificationEnabled: true
        )

        let profile2 = UserProfile(
            firstName: "Different",
            lastName: "Last",
            notificationEnabled: true
        )

        let profile3 = UserProfile(
            firstName: "First",
            lastName: "Different",
            notificationEnabled: true
        )

        let profile4 = UserProfile(
            firstName: "First",
            lastName: "Last",
            notificationEnabled: false
        )

        XCTAssertNotEqual(profile1, profile2)
        XCTAssertNotEqual(profile1, profile3)
        XCTAssertNotEqual(profile1, profile4)
    }

    // MARK: - Edge Cases and Validation Tests

    func testUserDecodingWithEmptyEmail() throws {
        let json = """
        {
            "id": 1,
            "email": "",
            "created_at": "2025-01-01T10:00:00Z",
            "notification_enabled": true,
            "is_admin": false
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let user = try decoder.decode(User.self, from: data)

        XCTAssertEqual(user.email, "")
    }

    func testUserDecodingWithSpecialCharactersInEmail() throws {
        let json = """
        {
            "id": 1,
            "email": "test+tag@example.com",
            "created_at": "2025-01-01T10:00:00Z",
            "notification_enabled": true,
            "is_admin": false
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let user = try decoder.decode(User.self, from: data)

        XCTAssertEqual(user.email, "test+tag@example.com")
    }

    func testUserDecodingFailsWithMissingRequiredFields() throws {
        let invalidJsons = [
            // Missing id
            """
            {
                "email": "test@example.com",
                "created_at": "2025-01-01T10:00:00Z",
                "notification_enabled": true,
                "is_admin": false
            }
            """,
            // Missing email
            """
            {
                "id": 1,
                "created_at": "2025-01-01T10:00:00Z",
                "notification_enabled": true,
                "is_admin": false
            }
            """,
            // Missing createdAt
            """
            {
                "id": 1,
                "email": "test@example.com",
                "notification_enabled": true,
                "is_admin": false
            }
            """,
            // Missing notificationEnabled
            """
            {
                "id": 1,
                "email": "test@example.com",
                "created_at": "2025-01-01T10:00:00Z",
                "is_admin": false
            }
            """,
            // Missing isAdmin
            """
            {
                "id": 1,
                "email": "test@example.com",
                "created_at": "2025-01-01T10:00:00Z",
                "notification_enabled": true
            }
            """
        ]

        for invalidJson in invalidJsons {
            let data = try XCTUnwrap(invalidJson.data(using: .utf8))
            let decoder = JSONDecoder()
            decoder.dateDecodingStrategy = .iso8601

            XCTAssertThrowsError(try decoder.decode(User.self, from: data)) { error in
                XCTAssertTrue(error is DecodingError, "Should throw DecodingError for missing required field")
            }
        }
    }

    func testUserDecodingFailsWithInvalidDateFormat() throws {
        let json = """
        {
            "id": 1,
            "email": "test@example.com",
            "created_at": "2025-01-01 10:00:00",
            "notification_enabled": true,
            "is_admin": false
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        XCTAssertThrowsError(try decoder.decode(User.self, from: data)) { error in
            XCTAssertTrue(error is DecodingError, "Should throw DecodingError for invalid date format")
        }
    }

    // MARK: - User UI Extension Tests

    func testUserNotificationStatus() {
        let enabledUser = Components.Schemas.UserResponse(
            id: 1,
            email: "test@example.com",
            createdAt: Date(),
            notificationEnabled: true,
            isAdmin: false
        )

        let disabledUser = Components.Schemas.UserResponse(
            id: 1,
            email: "test@example.com",
            createdAt: Date(),
            notificationEnabled: false,
            isAdmin: false
        )

        XCTAssertEqual(enabledUser.notificationStatus, "Notifications enabled")
        XCTAssertEqual(disabledUser.notificationStatus, "Notifications disabled")
    }

    func testUserAccessibilityDescription() {
        let user = Components.Schemas.UserResponse(
            id: 1,
            email: "test@example.com",
            createdAt: Date(),
            notificationEnabled: true,
            isAdmin: false
        )

        XCTAssertEqual(user.accessibilityDescription, "email test@example.com, Notifications enabled")
    }

    // MARK: - isAdmin Field Tests

    func testIsAdminDefaultsFalse() {
        let user = Components.Schemas.UserResponse(
            id: 1,
            email: "user@example.com",
            createdAt: Date(),
            notificationEnabled: true,
            isAdmin: false
        )
        XCTAssertFalse(user.isAdmin)
    }

    func testIsAdminTrue() {
        let user = Components.Schemas.UserResponse(
            id: 1,
            email: "admin@example.com",
            createdAt: Date(),
            notificationEnabled: true,
            isAdmin: true
        )
        XCTAssertTrue(user.isAdmin)
    }

    func testIsAdminDecodesFromJSON() throws {
        let json = """
        {
            "id": 1,
            "email": "admin@example.com",
            "created_at": "2025-01-01T10:00:00Z",
            "notification_enabled": true,
            "is_admin": true
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let user = try decoder.decode(User.self, from: data)

        XCTAssertTrue(user.isAdmin)
    }
}
