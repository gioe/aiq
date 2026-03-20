import APIClient
import Foundation

// MARK: - User Extensions

// Extensions for the User type (Components.Schemas.UserResponse)
//
// This file provides UI-specific computed properties for UserResponse.
// These were migrated from the APIClient package to the app target (TASK-711)
// following the 'bring your own extensions' pattern.
//
// Pattern: Following TASK-365, we extend generated types rather than duplicating them.

// MARK: - Demographic Data Limitation

// **IMPORTANT LIMITATION:** The generated UserResponse type does not include optional demographic fields.
//
// The OpenAPI spec defines these optional fields:
// - birth_year: Int?
// - education_level: EducationLevel?
// - country: String?
// - region: String?
// - last_login_at: Date?
//
// However, the Swift OpenAPI generator only creates properties for required fields.
// Until we can update the generator configuration or the API spec, these fields cannot be decoded.
//
// **Workaround:** If demographic data is needed, it must be stored separately or the API contract
// must be updated to mark these fields as required (with nullable values) in the OpenAPI spec.
//
// See: TASK-368 for tracking this limitation

// MARK: - Core UI Properties (migrated from APIClient package, TASK-711)

extension Components.Schemas.UserResponse {
    /// Full name combining first and last name (e.g., "John Smith")
    /// Returns empty string components gracefully (e.g., "John" if last name is nil)
    var fullName: String {
        [firstName, lastName]
            .compactMap { $0 }
            .joined(separator: " ")
    }

    /// User's initials (e.g., "JS" for John Smith)
    /// Returns "?" for empty, whitespace-only, or nil names
    var initials: String {
        let first = (firstName ?? "").trimmingCharacters(in: .whitespaces)
        let last = (lastName ?? "").trimmingCharacters(in: .whitespaces)
        let firstInitial = first.isEmpty ? "?" : first.prefix(1).uppercased()
        let lastInitial = last.isEmpty ? "?" : last.prefix(1).uppercased()
        return "\(firstInitial)\(lastInitial)"
    }

    /// Notification status as human-readable text
    var notificationStatus: String {
        notificationEnabled ? "Notifications enabled" : "Notifications disabled"
    }

    /// Accessibility description for the user profile
    var accessibilityDescription: String {
        "\(fullName), email \(email), \(notificationStatus)"
    }
}

// MARK: - Optional Property Extensions (migrated from APIClient package, TASK-711)

extension Components.Schemas.UserResponse {
    /// Approximate age calculated from birth year
    /// Returns nil if birthYear is not available
    /// Note: May be off by ±1 year since birth month/day is not available
    var approximateAge: Int? {
        guard let year = birthYear else { return nil }
        let currentYear = Calendar.current.component(.year, from: Date())
        return currentYear - year
    }

    /// Display text for user's location combining country and region
    /// Returns nil if neither country nor region is available
    /// Examples: "California, United States", "United States", "California"
    var locationDisplay: String? {
        switch (region, country) {
        case let (region?, country?):
            "\(region), \(country)"
        case let (nil, country?):
            country
        case let (region?, nil):
            region
        case (nil, nil):
            nil
        }
    }

    /// Display text for user's education level
    /// Returns nil if educationLevel is not available
    var educationLevelDisplay: String? {
        guard let education = educationLevel else { return nil }
        switch education.value1 {
        case .highSchool:
            return "High School"
        case .someCollege:
            return "Some College"
        case .associates:
            return "Associate's Degree"
        case .bachelors:
            return "Bachelor's Degree"
        case .masters:
            return "Master's Degree"
        case .doctorate:
            return "Doctorate"
        case .preferNotToSay:
            return "Prefer Not to Say"
        }
    }
}
