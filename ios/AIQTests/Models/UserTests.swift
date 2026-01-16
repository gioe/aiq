import XCTest

@testable import AIQ

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

    func testUserDecodingWithAllFields() throws {
        let json = """
        {
            "id": 123,
            "email": "test@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "created_at": "2025-01-01T10:00:00Z",
            "last_login_at": "2025-01-02T15:30:00Z",
            "notification_enabled": true,
            "birth_year": 1990,
            "education_level": "bachelors",
            "country": "United States",
            "region": "California"
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
        XCTAssertEqual(user.birthYear, 1990)
        XCTAssertEqual(user.educationLevel, .bachelors)
        XCTAssertEqual(user.country, "United States")
        XCTAssertEqual(user.region, "California")
        XCTAssertNotNil(user.createdAt)
        XCTAssertNotNil(user.lastLoginAt)
    }

    func testUserDecodingWithRequiredFieldsOnly() throws {
        let json = """
        {
            "id": 456,
            "email": "minimal@example.com",
            "first_name": "Jane",
            "last_name": "Smith",
            "created_at": "2025-01-01T10:00:00Z",
            "notification_enabled": false
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let user = try decoder.decode(User.self, from: data)

        XCTAssertEqual(user.id, 456)
        XCTAssertEqual(user.email, "minimal@example.com")
        XCTAssertEqual(user.firstName, "Jane")
        XCTAssertEqual(user.lastName, "Smith")
        XCTAssertFalse(user.notificationEnabled)
        XCTAssertNil(user.lastLoginAt)
        XCTAssertNil(user.birthYear)
        XCTAssertNil(user.educationLevel)
        XCTAssertNil(user.country)
        XCTAssertNil(user.region)
        XCTAssertNotNil(user.createdAt)
    }

    func testUserDecodingWithNullOptionalFields() throws {
        let json = """
        {
            "id": 789,
            "email": "nulls@example.com",
            "first_name": "Test",
            "last_name": "User",
            "created_at": "2025-01-01T10:00:00Z",
            "last_login_at": null,
            "notification_enabled": true,
            "birth_year": null,
            "education_level": null,
            "country": null,
            "region": null
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let user = try decoder.decode(User.self, from: data)

        XCTAssertEqual(user.id, 789)
        XCTAssertNil(user.lastLoginAt)
        XCTAssertNil(user.birthYear)
        XCTAssertNil(user.educationLevel)
        XCTAssertNil(user.country)
        XCTAssertNil(user.region)
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
            "last_login_at": "2025-01-02T10:00:00Z",
            "notification_enabled": false,
            "birth_year": 1995,
            "education_level": "masters"
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
        XCTAssertEqual(user.birthYear, 1995)
        XCTAssertEqual(user.educationLevel, .masters)
        XCTAssertNotNil(user.createdAt)
        XCTAssertNotNil(user.lastLoginAt)
    }

    func testUserDecodingWithAllEducationLevels() throws {
        let educationLevels: [(String, EducationLevel)] = [
            ("high_school", .highSchool),
            ("some_college", .someCollege),
            ("associates", .associates),
            ("bachelors", .bachelors),
            ("masters", .masters),
            ("doctorate", .doctorate),
            ("prefer_not_to_say", .preferNotToSay)
        ]

        for (rawValue, expectedLevel) in educationLevels {
            let json = """
            {
                "id": 1,
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "User",
                "created_at": "2025-01-01T10:00:00Z",
                "notification_enabled": true,
                "education_level": "\(rawValue)"
            }
            """

            let data = try XCTUnwrap(json.data(using: .utf8))
            let decoder = JSONDecoder()
            decoder.dateDecodingStrategy = .iso8601
            let user = try decoder.decode(User.self, from: data)

            XCTAssertEqual(
                user.educationLevel,
                expectedLevel,
                "Failed to decode education level: \(rawValue)"
            )
        }
    }

    // MARK: - User Computed Properties Tests

    func testUserFullName() {
        let user = User(
            id: 1,
            email: "test@example.com",
            firstName: "John",
            lastName: "Doe",
            createdAt: Date(),
            lastLoginAt: nil,
            notificationEnabled: true,
            birthYear: nil,
            educationLevel: nil,
            country: nil,
            region: nil
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
            let user = User(
                id: 1,
                email: "test@example.com",
                firstName: firstName,
                lastName: lastName,
                createdAt: Date(),
                lastLoginAt: nil,
                notificationEnabled: true,
                birthYear: nil,
                educationLevel: nil,
                country: nil,
                region: nil
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
        let user1 = User(
            id: 1,
            email: "test@example.com",
            firstName: "John",
            lastName: "Doe",
            createdAt: date,
            lastLoginAt: date,
            notificationEnabled: true,
            birthYear: 1990,
            educationLevel: .bachelors,
            country: "US",
            region: "CA"
        )

        let user2 = User(
            id: 1,
            email: "test@example.com",
            firstName: "John",
            lastName: "Doe",
            createdAt: date,
            lastLoginAt: date,
            notificationEnabled: true,
            birthYear: 1990,
            educationLevel: .bachelors,
            country: "US",
            region: "CA"
        )

        XCTAssertEqual(user1, user2)
    }

    func testUserInequality() {
        let date = Date()
        let user1 = User(
            id: 1,
            email: "test@example.com",
            firstName: "John",
            lastName: "Doe",
            createdAt: date,
            lastLoginAt: nil,
            notificationEnabled: true,
            birthYear: nil,
            educationLevel: nil,
            country: nil,
            region: nil
        )

        // Different ID
        let user2 = User(
            id: 2,
            email: "test@example.com",
            firstName: "John",
            lastName: "Doe",
            createdAt: date,
            lastLoginAt: nil,
            notificationEnabled: true,
            birthYear: nil,
            educationLevel: nil,
            country: nil,
            region: nil
        )
        XCTAssertNotEqual(user1, user2)

        // Different email
        let user3 = User(
            id: 1,
            email: "different@example.com",
            firstName: "John",
            lastName: "Doe",
            createdAt: date,
            lastLoginAt: nil,
            notificationEnabled: true,
            birthYear: nil,
            educationLevel: nil,
            country: nil,
            region: nil
        )
        XCTAssertNotEqual(user1, user3)

        // Different firstName
        let user4 = User(
            id: 1,
            email: "test@example.com",
            firstName: "Jane",
            lastName: "Doe",
            createdAt: date,
            lastLoginAt: nil,
            notificationEnabled: true,
            birthYear: nil,
            educationLevel: nil,
            country: nil,
            region: nil
        )
        XCTAssertNotEqual(user1, user4)
    }

    // MARK: - User Encoding Tests

    func testUserEncodingRoundTrip() throws {
        let originalDate = Date()
        let user = User(
            id: 123,
            email: "roundtrip@example.com",
            firstName: "Round",
            lastName: "Trip",
            createdAt: originalDate,
            lastLoginAt: originalDate,
            notificationEnabled: true,
            birthYear: 1985,
            educationLevel: .doctorate,
            country: "Canada",
            region: "Ontario"
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
        XCTAssertEqual(user.birthYear, decodedUser.birthYear)
        XCTAssertEqual(user.educationLevel, decodedUser.educationLevel)
        XCTAssertEqual(user.country, decodedUser.country)
        XCTAssertEqual(user.region, decodedUser.region)
    }

    func testUserEncodingUsesSnakeCase() throws {
        let user = User(
            id: 1,
            email: "snake@example.com",
            firstName: "Snake",
            lastName: "Case",
            createdAt: Date(),
            lastLoginAt: nil,
            notificationEnabled: false,
            birthYear: 2000,
            educationLevel: .associates,
            country: nil,
            region: nil
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
        XCTAssertTrue(jsonString.contains("birth_year"))
        XCTAssertTrue(jsonString.contains("education_level"))

        // Verify camelCase keys are NOT in JSON
        XCTAssertFalse(jsonString.contains("firstName"))
        XCTAssertFalse(jsonString.contains("lastName"))
        XCTAssertFalse(jsonString.contains("createdAt"))
        XCTAssertFalse(jsonString.contains("notificationEnabled"))
        XCTAssertFalse(jsonString.contains("birthYear"))
        XCTAssertFalse(jsonString.contains("educationLevel"))
    }

    // MARK: - User Identifiable Tests

    func testUserIdentifiable() {
        let user = User(
            id: 42,
            email: "identifiable@example.com",
            firstName: "Test",
            lastName: "User",
            createdAt: Date(),
            lastLoginAt: nil,
            notificationEnabled: true,
            birthYear: nil,
            educationLevel: nil,
            country: nil,
            region: nil
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
            "notification_enabled": true,
            "country": "São Paulo",
            "region": "Île-de-France"
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let user = try decoder.decode(User.self, from: data)

        XCTAssertEqual(user.email, "test+tag@example.com")
        XCTAssertEqual(user.firstName, "José")
        XCTAssertEqual(user.lastName, "O'Brien-Smith")
        XCTAssertEqual(user.country, "São Paulo")
        XCTAssertEqual(user.region, "Île-de-France")
        XCTAssertEqual(user.fullName, "José O'Brien-Smith")
    }

    func testUserDecodingWithBirthYearEdgeCases() throws {
        let testCases = [1900, 1950, 2000, 2024, 2025]

        for year in testCases {
            let json = """
            {
                "id": 1,
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "User",
                "created_at": "2025-01-01T10:00:00Z",
                "notification_enabled": true,
                "birth_year": \(year)
            }
            """

            let data = try XCTUnwrap(json.data(using: .utf8))
            let decoder = JSONDecoder()
            decoder.dateDecodingStrategy = .iso8601
            let user = try decoder.decode(User.self, from: data)

            XCTAssertEqual(user.birthYear, year, "Failed to decode birth year: \(year)")
        }
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

    func testUserDecodingFailsWithInvalidEducationLevel() throws {
        let json = """
        {
            "id": 1,
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User",
            "created_at": "2025-01-01T10:00:00Z",
            "notification_enabled": true,
            "education_level": "invalid_level"
        }
        """

        let data = try XCTUnwrap(json.data(using: .utf8))
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        XCTAssertThrowsError(try decoder.decode(User.self, from: data)) { error in
            XCTAssertTrue(error is DecodingError, "Should throw DecodingError for invalid education level")
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
}
