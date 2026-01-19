import AIQAPIClient
import Foundation

// MARK: - TestSession Extensions

// Extensions for the TestSession type (Components.Schemas.TestSessionResponse)
//
// This file provides extensions for the OpenAPI generated TestSessionResponse type.
// Unlike the manually-defined TestSession which used a TestStatus enum, the generated
// type uses a String for the status property.
//
// Pattern: Following TASK-368 and TASK-365, we extend generated types rather than duplicating them.

// MARK: - Protocol Conformance

extension Components.Schemas.TestSessionResponse: Identifiable {
    // id property already exists on the generated type
}

extension Components.Schemas.TestSessionResponse: Equatable {
    // swiftlint:disable:next line_length
    public static func == (lhs: Components.Schemas.TestSessionResponse, rhs: Components.Schemas.TestSessionResponse) -> Bool {
        lhs.id == rhs.id &&
            lhs.userId == rhs.userId &&
            lhs.status == rhs.status &&
            lhs.startedAt == rhs.startedAt &&
            lhs.timeLimitExceeded == rhs.timeLimitExceeded
        // Note: completedAt is not generated due to anyOf nullable limitation
    }
}

// MARK: - Status Helpers

extension Components.Schemas.TestSessionResponse {
    /// Test status enumeration for type-safe status checks
    ///
    /// This enum mirrors the backend's test status values and provides
    /// type-safe helpers for working with the status string property.
    enum Status: String {
        case inProgress = "in_progress"
        case completed
        case abandoned
    }

    /// Returns the parsed status as an enum value
    ///
    /// **Note:** This returns nil if the status string doesn't match known values.
    /// The backend should only return valid status strings, but we handle unknown
    /// values gracefully.
    var statusEnum: Status? {
        Status(rawValue: status)
    }

    /// Whether this test session is currently in progress
    var isInProgress: Bool {
        status == Status.inProgress.rawValue
    }

    /// Whether this test session has been completed
    var isCompleted: Bool {
        status == Status.completed.rawValue
    }

    /// Whether this test session has been abandoned
    var isAbandoned: Bool {
        status == Status.abandoned.rawValue
    }

    /// Display text for the status
    var statusDisplay: String {
        switch statusEnum {
        case .inProgress:
            "In Progress"
        case .completed:
            "Completed"
        case .abandoned:
            "Abandoned"
        case .none:
            // Fallback for unknown status values
            status.capitalized
        }
    }
}

// MARK: - Validation (Moved from Manual Type)

// MARK: - Test Status

//
// TestStatus enum is defined in TestSession.swift for backward compatibility
