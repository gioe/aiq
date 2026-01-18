import AIQAPIClient
import Foundation

// MARK: - User Extensions

// Extensions for the User type (Components.Schemas.UserResponse)
//
// This file provides additional extensions beyond what's available in the AIQAPIClient package.
// The core UI properties (fullName, initials, notificationStatus, accessibilityDescription)
// are provided in UserResponse+UI.swift in the AIQAPIClient package.
//
// Pattern: Following TASK-365, we extend generated types rather than duplicating them.
// The generated UserResponse only includes required fields.

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
