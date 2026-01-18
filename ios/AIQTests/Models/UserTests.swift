import XCTest

@testable import AIQ
import AIQAPIClient

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

    // Note: User is now a typealias for Components.Schemas.UserResponse from the OpenAPI generated types.
    // The generated type only includes required fields: id, email, firstName, lastName, createdAt, notificationEnabled.
    // Optional demographic fields (birthYear, educationLevel, country, region, lastLoginAt) are NOT in the generated type.

    func testUserDecodingWithRequiredFields() throws {
        let json = """
        {
            "id": 123,
            "email": "test@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "created_at": "2025-01-01T10:00:00Z",
            "notification_enabled": true
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let user = try decoder.decode(User.self, from: data)

        XCTAssertEqual(user.id, 123)
        XCTAssertEqual(user.email, "test@example.com")
        XCTAssertEqual(user.firstName, "John")
        XCTAssertEqual(user.lastName, "Doe")
        XCTAssertTrue(user.notificationEnabled)
        XCTAssertNotNil(user.createdAt)
    }

    func testUserDecodingCodingKeysMapping() throws {
        // Verify snake_case to camelCase conversion
        let json = """
        {
            "id": 1,
            "email": "keys@example.com",
            "first_name": "Coding",
            "last_name": "Keys",
            "created_at": "2025-01-01T10:00:00Z",
            "notification_enabled": false
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let user = try decoder.decode(User.self, from: data)

        // Verify snake_case fields are properly mapped
        XCTAssertEqual(user.firstName, "Coding")
        XCTAssertEqual(user.lastName, "Keys")
        XCTAssertFalse(user.notificationEnabled)
        XCTAssertNotNil(user.createdAt)
    }

    // MARK: - User Computed Properties Tests

    func testUserFullName() {
        let user = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "test@example.com",
            firstName: "John",
            id: 1,
            lastName: "Doe",
            notificationEnabled: true
        )

        XCTAssertEqual(user.fullName, "John Doe")
    }

    func testUserFullNameWithDifferentNames() {
        let testCases: [(String, String, String)] = [
            ("Alice", "Smith", "Alice Smith"),
            ("Bob", "Johnson", "Bob Johnson"),
            ("María", "García", "María García"),
            ("李", "明", "李 明")
        ]

        for (firstName, lastName, expectedFullName) in testCases {
            let user = Components.Schemas.UserResponse(
                createdAt: Date(),
                email: "test@example.com",
                firstName: firstName,
                id: 1,
                lastName: lastName,
                notificationEnabled: true
            )

            XCTAssertEqual(
                user.fullName,
                expectedFullName,
                "Full name should be '\(expectedFullName)' for \(firstName) \(lastName)"
            )
        }
    }

    // MARK: - User Equatable Tests

    func testUserEquality() {
        let date = Date()
        let user1 = Components.Schemas.UserResponse(
            createdAt: date,
            email: "test@example.com",
            firstName: "John",
            id: 1,
            lastName: "Doe",
            notificationEnabled: true
        )

        let user2 = Components.Schemas.UserResponse(
            createdAt: date,
            email: "test@example.com",
            firstName: "John",
            id: 1,
            lastName: "Doe",
            notificationEnabled: true
        )

        XCTAssertEqual(user1, user2)
    }

    func testUserInequality() {
        let date = Date()
        let user1 = Components.Schemas.UserResponse(
            createdAt: date,
            email: "test@example.com",
            firstName: "John",
            id: 1,
            lastName: "Doe",
            notificationEnabled: true
        )

        // Different ID
        let user2 = Components.Schemas.UserResponse(
            createdAt: date,
            email: "test@example.com",
            firstName: "John",
            id: 2,
            lastName: "Doe",
            notificationEnabled: true
        )
        XCTAssertNotEqual(user1, user2)

        // Different email
        let user3 = Components.Schemas.UserResponse(
            createdAt: date,
            email: "different@example.com",
            firstName: "John",
            id: 1,
            lastName: "Doe",
            notificationEnabled: true
        )
        XCTAssertNotEqual(user1, user3)

        // Different firstName
        let user4 = Components.Schemas.UserResponse(
            createdAt: date,
            email: "test@example.com",
            firstName: "Jane",
            id: 1,
            lastName: "Doe",
            notificationEnabled: true
        )
        XCTAssertNotEqual(user1, user4)
    }

    // MARK: - User Encoding Tests

    func testUserEncodingRoundTrip() throws {
        let originalDate = Date()
        let user = Components.Schemas.UserResponse(
            createdAt: originalDate,
            email: "roundtrip@example.com",
            firstName: "Round",
            id: 123,
            lastName: "Trip",
            notificationEnabled: true
        )

        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let data = try encoder.encode(user)

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let decodedUser = try decoder.decode(User.self, from: data)

        XCTAssertEqual(user.id, decodedUser.id)
        XCTAssertEqual(user.email, decodedUser.email)
        XCTAssertEqual(user.firstName, decodedUser.firstName)
        XCTAssertEqual(user.lastName, decodedUser.lastName)
        XCTAssertEqual(user.notificationEnabled, decodedUser.notificationEnabled)
    }

    func testUserEncodingUsesSnakeCase() throws {
        let user = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "snake@example.com",
            firstName: "Snake",
            id: 1,
            lastName: "Case",
            notificationEnabled: false
        )

        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = .sortedKeys
        let data = try encoder.encode(user)
        let jsonString = String(data: data, encoding: .utf8)!

        // Verify snake_case keys are used in JSON
        XCTAssertTrue(jsonString.contains("first_name"))
        XCTAssertTrue(jsonString.contains("last_name"))
        XCTAssertTrue(jsonString.contains("created_at"))
        XCTAssertTrue(jsonString.contains("notification_enabled"))

        // Verify camelCase keys are NOT in JSON
        XCTAssertFalse(jsonString.contains("firstName"))
        XCTAssertFalse(jsonString.contains("lastName"))
        XCTAssertFalse(jsonString.contains("createdAt"))
        XCTAssertFalse(jsonString.contains("notificationEnabled"))
    }

    // MARK: - User Identifiable Tests

    func testUserIdentifiable() {
        let user = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "identifiable@example.com",
            firstName: "Test",
            id: 42,
            lastName: "User",
            notificationEnabled: true
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
        XCTAssertEqual(profile.lastName, "Test")
        XCTAssertTrue(profile.notificationEnabled)
    }

    func testUserProfileCodingKeysMapping() throws {
        let json = """
        {
            "first_name": "First",
            "last_name": "Last",
            "notification_enabled": false
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let profile = try JSONDecoder().decode(UserProfile.self, from: data)

        // Verify snake_case to camelCase mapping
        XCTAssertEqual(profile.firstName, "First")
        XCTAssertEqual(profile.lastName, "Last")
        XCTAssertFalse(profile.notificationEnabled)
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
        let jsonString = String(data: data, encoding: .utf8)!

        // Verify snake_case keys
        XCTAssertTrue(jsonString.contains("first_name"))
        XCTAssertTrue(jsonString.contains("last_name"))
        XCTAssertTrue(jsonString.contains("notification_enabled"))

        // Verify no camelCase keys
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

    func testUserDecodingWithEmptyStrings() throws {
        // While not ideal, the model should handle empty strings
        let json = """
        {
            "id": 1,
            "email": "",
            "first_name": "",
            "last_name": "",
            "created_at": "2025-01-01T10:00:00Z",
            "notification_enabled": true
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let user = try decoder.decode(User.self, from: data)

        XCTAssertEqual(user.email, "")
        XCTAssertEqual(user.firstName, "")
        XCTAssertEqual(user.lastName, "")
        XCTAssertEqual(user.fullName, " ") // Empty first + space + empty last
    }

    func testUserDecodingWithSpecialCharacters() throws {
        let json = """
        {
            "id": 1,
            "email": "test+tag@example.com",
            "first_name": "José",
            "last_name": "O'Brien-Smith",
            "created_at": "2025-01-01T10:00:00Z",
            "notification_enabled": true
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let user = try decoder.decode(User.self, from: data)

        XCTAssertEqual(user.email, "test+tag@example.com")
        XCTAssertEqual(user.firstName, "José")
        XCTAssertEqual(user.lastName, "O'Brien-Smith")
        XCTAssertEqual(user.fullName, "José O'Brien-Smith")
    }

    func testUserDecodingFailsWithMissingRequiredFields() throws {
        let invalidJsons = [
            // Missing id
            """
            {
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "User",
                "created_at": "2025-01-01T10:00:00Z",
                "notification_enabled": true
            }
            """,
            // Missing email
            """
            {
                "id": 1,
                "first_name": "Test",
                "last_name": "User",
                "created_at": "2025-01-01T10:00:00Z",
                "notification_enabled": true
            }
            """,
            // Missing firstName
            """
            {
                "id": 1,
                "email": "test@example.com",
                "last_name": "User",
                "created_at": "2025-01-01T10:00:00Z",
                "notification_enabled": true
            }
            """,
            // Missing lastName
            """
            {
                "id": 1,
                "email": "test@example.com",
                "first_name": "Test",
                "created_at": "2025-01-01T10:00:00Z",
                "notification_enabled": true
            }
            """,
            // Missing createdAt
            """
            {
                "id": 1,
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "User",
                "notification_enabled": true
            }
            """,
            // Missing notificationEnabled
            """
            {
                "id": 1,
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "User",
                "created_at": "2025-01-01T10:00:00Z"
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
            "first_name": "Test",
            "last_name": "User",
            "created_at": "2025-01-01 10:00:00",
            "notification_enabled": true
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

    func testUserInitials() {
        let user = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "test@example.com",
            firstName: "John",
            id: 1,
            lastName: "Smith",
            notificationEnabled: true
        )

        XCTAssertEqual(user.initials, "JS")
    }

    func testUserInitialsWithEmptyNames() {
        let user = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "test@example.com",
            firstName: "",
            id: 1,
            lastName: "",
            notificationEnabled: true
        )

        XCTAssertEqual(user.initials, "??")
    }

    func testUserNotificationStatus() {
        let enabledUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "test@example.com",
            firstName: "Test",
            id: 1,
            lastName: "User",
            notificationEnabled: true
        )

        let disabledUser = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "test@example.com",
            firstName: "Test",
            id: 1,
            lastName: "User",
            notificationEnabled: false
        )

        XCTAssertEqual(enabledUser.notificationStatus, "Notifications enabled")
        XCTAssertEqual(disabledUser.notificationStatus, "Notifications disabled")
    }

    func testUserAccessibilityDescription() {
        let user = Components.Schemas.UserResponse(
            createdAt: Date(),
            email: "test@example.com",
            firstName: "John",
            id: 1,
            lastName: "Smith",
            notificationEnabled: true
        )

        XCTAssertEqual(user.accessibilityDescription, "John Smith, email test@example.com, Notifications enabled")
    }
}
