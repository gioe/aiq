// MARK: - UserResponse UI Extensions

//
// Extends the generated UserResponse type with UI-specific computed properties.
// These extensions add display helpers for user profile information.
//
// Pattern: Each extension file follows the naming convention `<TypeName>+UI.swift`.

import Foundation

public extension Components.Schemas.UserResponse {
    /// Full name combining first and last name (e.g., "John Smith")
    var fullName: String {
        "\(firstName) \(lastName)"
    }

    /// User's initials (e.g., "JS" for John Smith)
    var initials: String {
        let firstInitial = firstName.prefix(1).uppercased()
        let lastInitial = lastName.prefix(1).uppercased()
        return "\(firstInitial)\(lastInitial)"
    }

    /// Formatted account creation date (e.g., "Jan 15, 2024")
    var createdAtFormatted: String {
        createdAt.toShortString()
    }

    /// Relative account creation date (e.g., "Member for 2 months")
    var memberSince: String {
        "Member since \(createdAt.toShortString())"
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
