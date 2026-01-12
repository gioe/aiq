import Foundation

/// Input validation utilities
///
/// This enum provides centralized validation logic for user input across the application.
/// All validation methods return a `ValidationResult` that can be either `.valid` or
/// `.invalid(String)` with a user-friendly error message.
enum Validators {
    // MARK: - Email Validation

    /// Validate email format
    ///
    /// Email Requirements:
    /// - Must not be empty or whitespace-only
    /// - Must match a valid email pattern (user@domain.tld)
    ///
    /// This is the single source of truth for email validation across the app.
    /// All ViewModels use this method to ensure consistent validation rules.
    ///
    /// - Parameter email: The email address to validate
    /// - Returns: `.valid` if email meets all requirements, `.invalid(message)` otherwise
    static func validateEmail(_ email: String) -> ValidationResult {
        guard email.isNotEmpty else {
            return .invalid("Email is required")
        }

        // Email regex pattern: user@domain.tld
        let emailRegex = #"^[A-Z0-9a-z._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"#
        let predicate = NSPredicate(format: "SELF MATCHES %@", emailRegex)
        guard predicate.evaluate(with: email) else {
            return .invalid("Please enter a valid email address")
        }

        return .valid
    }

    // MARK: - Password Validation

    /// Validate password meets security requirements
    ///
    /// Password Requirements:
    /// - Minimum length: 8 characters
    /// - Must not be empty or whitespace-only
    ///
    /// This is the single source of truth for password validation across the app.
    /// Both LoginViewModel and RegistrationViewModel use this method to ensure
    /// consistent validation rules.
    ///
    /// - Parameter password: The password to validate
    /// - Returns: `.valid` if password meets all requirements, `.invalid(message)` otherwise
    static func validatePassword(_ password: String) -> ValidationResult {
        guard password.isNotEmpty else {
            return .invalid("Password is required")
        }
        guard password.count >= Constants.Validation.minPasswordLength else {
            return .invalid("Password must be at least \(Constants.Validation.minPasswordLength) characters")
        }
        return .valid
    }

    // MARK: - Name Validation

    /// Validate name field
    ///
    /// Requirements:
    /// - Name must not be empty or whitespace-only
    /// - Name must be at least 2 characters
    ///
    /// - Parameters:
    ///   - name: The name to validate
    ///   - fieldName: The display name for the field (used in error messages)
    /// - Returns: `.valid` if name meets all requirements, `.invalid(message)` otherwise
    static func validateName(_ name: String, fieldName: String = "Name") -> ValidationResult {
        guard name.isNotEmpty else {
            return .invalid("\(fieldName) is required")
        }
        guard name.count >= Constants.Validation.minNameLength else {
            return .invalid("\(fieldName) must be at least \(Constants.Validation.minNameLength) characters")
        }
        return .valid
    }

    // MARK: - Password Confirmation Validation

    /// Validate password confirmation matches original password
    ///
    /// Requirements:
    /// - Confirmation must exactly match the original password
    ///
    /// - Parameters:
    ///   - password: The original password
    ///   - confirmation: The confirmation password
    /// - Returns: `.valid` if passwords match, `.invalid(message)` otherwise
    static func validatePasswordConfirmation(_ password: String, _ confirmation: String) -> ValidationResult {
        guard password == confirmation else {
            return .invalid("Passwords do not match")
        }
        return .valid
    }

    // MARK: - Feedback Description Validation

    /// Validate feedback description field
    ///
    /// Requirements:
    /// - Description must not be empty or whitespace-only
    /// - Description must be at least 10 characters to ensure meaningful feedback
    ///
    /// - Parameter description: The feedback description to validate
    /// - Returns: `.valid` if description meets all requirements, `.invalid(message)` otherwise
    static func validateFeedbackDescription(_ description: String) -> ValidationResult {
        guard description.isNotEmpty else {
            return .invalid("Description is required")
        }
        guard description.count >= 10 else {
            return .invalid("Description must be at least 10 characters")
        }
        return .valid
    }

    // MARK: - Birth Year Validation

    /// Validate birth year field
    ///
    /// Requirements:
    /// - Year must be a valid integer
    /// - Year must be between 1900 and current year (inclusive)
    ///
    /// - Parameter birthYear: The birth year string to validate
    /// - Returns: `.valid` if birth year meets all requirements, `.invalid(message)` otherwise
    static func validateBirthYear(_ birthYear: String) -> ValidationResult {
        // Empty birth year is valid (optional field)
        let trimmed = birthYear.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else {
            return .valid
        }

        // Must be a valid integer
        guard let year = Int(trimmed) else {
            return .invalid("Birth year must be a valid year")
        }

        // Get current year dynamically
        let currentYear = Calendar.current.component(.year, from: Date())

        // Year must be >= 1900
        guard year >= Constants.Validation.minBirthYear else {
            return .invalid("Birth year must be 1900 or later")
        }

        // Year must be <= current year
        guard year <= currentYear else {
            return .invalid("Birth year cannot be in the future")
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
