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
    /// Full name combining firstName and lastName
    var fullName: String {
        [firstName, lastName].compactMap { $0 }.joined(separator: " ")
    }

    /// Initials from first and last name, using "?" for missing/empty names
    var initials: String {
        let firstInitial = firstName?.trimmingCharacters(in: .whitespaces).first.map { String($0).uppercased() } ?? "?"
        let lastInitial = lastName?.trimmingCharacters(in: .whitespaces).first.map { String($0).uppercased() } ?? "?"
        return firstInitial + lastInitial
    }

    /// Notification status as human-readable text
    var notificationStatus: String {
        notificationEnabled ? "Notifications enabled" : "Notifications disabled"
    }

    /// Accessibility description for the user profile
    var accessibilityDescription: String {
        "email \(email), \(notificationStatus)"
    }
}

// MARK: - Optional Property Extensions

extension Components.Schemas.UserResponse {
    /// Approximate age based on birth year
    var approximateAge: Int? {
        guard let birthYear else { return nil }
        return Calendar.current.component(.year, from: Date()) - birthYear
    }

    /// Location display combining region and country
    var locationDisplay: String? {
        let parts = [region, country].compactMap { $0 }
        return parts.isEmpty ? nil : parts.joined(separator: ", ")
    }

    /// Human-readable education level
    var educationLevelDisplay: String? {
        guard let educationLevel else { return nil }
        switch educationLevel {
        case .highSchool: return "High School"
        case .someCollege: return "Some College"
        case .associates: return "Associate's Degree"
        case .bachelors: return "Bachelor's Degree"
        case .masters: return "Master's Degree"
        case .doctorate: return "Doctorate"
        case .preferNotToSay: return "Prefer Not to Say"
        }
    }
}
