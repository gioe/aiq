import Foundation

/// Input validation utilities
enum Validators {
    /// Validate email format
    static func validateEmail(_ email: String) -> ValidationResult {
        guard email.isNotEmpty else {
            return .invalid("Email is required")
        }
        guard email.isValidEmail else {
            return .invalid("Please enter a valid email address")
        }
        return .valid
    }

    /// Validate password
    static func validatePassword(_ password: String) -> ValidationResult {
        guard password.isNotEmpty else {
            return .invalid("Password is required")
        }
        guard password.isValidPassword else {
            return .invalid("Password must be at least 8 characters")
        }
        return .valid
    }

    /// Validate name
    static func validateName(_ name: String, fieldName: String = "Name") -> ValidationResult {
        guard name.isNotEmpty else {
            return .invalid("\(fieldName) is required")
        }
        guard name.count >= 2 else {
            return .invalid("\(fieldName) must be at least 2 characters")
        }
        return .valid
    }

    /// Validate password confirmation
    static func validatePasswordConfirmation(_ password: String, _ confirmation: String) -> ValidationResult {
        guard password == confirmation else {
            return .invalid("Passwords do not match")
        }
        return .valid
    }
}

/// Result of validation
enum ValidationResult {
    case valid
    case invalid(String)

    var isValid: Bool {
        if case .valid = self {
            return true
        }
        return false
    }

    var errorMessage: String? {
        if case let .invalid(message) = self {
            return message
        }
        return nil
    }
}
