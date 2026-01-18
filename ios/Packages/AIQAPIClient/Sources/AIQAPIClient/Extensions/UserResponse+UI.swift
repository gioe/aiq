// MARK: - UserResponse UI Extensions

//
// Extends the generated UserResponse type with UI-specific computed properties.
// These extensions add display helpers for user profile information.
//
// Pattern: Each extension file follows the naming convention `<TypeName>+UI.swift`.
//
// NOTE: Date formatting should be done in the UI layer using the main app's Date+Extensions
// which provides cached, locale-aware formatters. This package provides raw computed values.

import Foundation

public extension Components.Schemas.UserResponse {
    /// Full name combining first and last name (e.g., "John Smith")
    var fullName: String {
        "\(firstName) \(lastName)"
    }

    /// User's initials (e.g., "JS" for John Smith)
    /// Returns "?" for empty or whitespace-only names
    var initials: String {
        let first = firstName.trimmingCharacters(in: .whitespaces)
        let last = lastName.trimmingCharacters(in: .whitespaces)
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
