import AIQAPIClientCore
import Foundation

// MARK: - User Extensions

// Extensions for the User type (Components.Schemas.UserResponse)
//
// This file provides UI-specific computed properties for UserResponse.
// These were migrated from the APIClient package to the app target (TASK-711)
// following the 'bring your own extensions' pattern.
//
// Pattern: Following TASK-365, we extend generated types rather than duplicating them.

// MARK: - Core UI Properties (migrated from APIClient package, TASK-711)

extension Components.Schemas.UserResponse {
    /// Notification status as human-readable text
    var notificationStatus: String {
        notificationEnabled ? "Notifications enabled" : "Notifications disabled"
    }

    /// Accessibility description for the user profile
    var accessibilityDescription: String {
        "email \(email), \(notificationStatus)"
    }
}
