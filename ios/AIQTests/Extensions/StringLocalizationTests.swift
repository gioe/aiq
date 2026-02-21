@testable import AIQ
import XCTest

final class StringLocalizationTests: XCTestCase {
    // MARK: - Basic Localization Tests

    func testLocalized_WithValidKey_ReturnsLocalizedString() {
        // Given a valid localization key
        let key = "app.name"

        // When getting the localized string
        let result = key.localized

        // Then it should return the localized value
        XCTAssertEqual(result, "AIQ")
    }

    func testLocalized_WithMultipleKeys_ReturnsCorrectLocalizedStrings() {
        // Test multiple keys to verify proper localization
        XCTAssertEqual("welcome.email.title".localized, "Email")
        XCTAssertEqual("welcome.password.title".localized, "Password")
        XCTAssertEqual("welcome.signin.button".localized, "Sign In")
        XCTAssertEqual("tab.dashboard".localized, "Dashboard")
        XCTAssertEqual("tab.history".localized, "History")
        XCTAssertEqual("tab.settings".localized, "Settings")
    }

    func testLocalized_WithComplexString_PreservesFormatting() {
        // Given a localization key with complex text
        let key = "registration.demographic.subtitle"

        // When getting the localized string
        let result = key.localized

        // Then it should return the full localized string
        XCTAssertEqual(
            result,
            "This optional information helps us validate test accuracy. All data remains private."
        )
    }

    // MARK: - Missing Key Handling Tests

    func testLocalized_WithMissingKey_ReturnsTheKey() {
        // Given a key that doesn't exist in Localizable.strings
        let missingKey = "nonexistent.key.that.does.not.exist"

        // When getting the localized string
        let result = missingKey.localized

        // Then it should return the key itself
        XCTAssertEqual(result, missingKey)
    }

    func testLocalized_WithEmptyString_ReturnsEmptyString() {
        // Given an empty string
        let emptyString = ""

        // When getting the localized string
        let result = emptyString.localized

        // Then it should return an empty string
        XCTAssertEqual(result, "")
    }

    func testLocalized_WithWhitespace_ReturnsWhitespace() {
        // Given a string with only whitespace
        let whitespaceString = "   "

        // When getting the localized string
        let result = whitespaceString.localized

        // Then it should return the whitespace string
        XCTAssertEqual(result, "   ")
    }

    // MARK: - String Interpolation Tests

    func testLocalizedWithArguments_WithSingleIntegerArgument_FormatsCorrectly() {
        // Given a key with a single integer placeholder
        let key = "dashboard.questions.answered"

        // When formatting with an integer argument
        let result = key.localized(with: 5)

        // Then it should substitute the argument correctly
        XCTAssertEqual(result, "5 questions answered")
    }

    func testLocalizedWithArguments_WithMultipleArguments_FormatsCorrectly() {
        // Given a key that expects multiple arguments
        // Note: Using test.completed.count which has %d out of %d format
        let key = "test.completed.count"

        // When formatting with multiple arguments
        let result = key.localized(with: 14, 20)

        // Then it should substitute all arguments correctly
        XCTAssertEqual(result, "You answered 14 out of 20 questions")
    }

    func testLocalizedWithArguments_WithStringArgument_FormatsCorrectly() {
        // Given a key with string placeholder
        let key = "results.confidence.range"

        // When formatting with a string argument
        let result = key.localized(with: "101-115")

        // Then it should substitute the string argument correctly
        XCTAssertEqual(result, "Range: 101-115")
    }

    func testLocalizedWithArguments_WithZeroValue_HandlesCorrectly() {
        // Given a key that expects a numeric argument
        let key = "dashboard.questions.answered"

        // When formatting with zero
        let result = key.localized(with: 0)

        // Then it should handle zero correctly
        XCTAssertEqual(result, "0 questions answered")
    }

    func testLocalizedWithArguments_WithNegativeValue_HandlesCorrectly() {
        // Given a key that expects a numeric argument
        let key = "dashboard.questions.answered"

        // When formatting with a negative number
        let result = key.localized(with: -5)

        // Then it should handle negative values
        XCTAssertEqual(result, "-5 questions answered")
    }

    func testLocalizedWithArguments_WithLargeNumbers_HandlesCorrectly() {
        // Given a key that expects numeric arguments
        let key = "test.completed.count"

        // When formatting with large numbers
        let result = key.localized(with: 999, 1000)

        // Then it should handle large numbers correctly
        XCTAssertEqual(result, "You answered 999 out of 1000 questions")
    }

    func testLocalizedWithArguments_WithMissingKey_ReturnsFormattedKey() {
        // Given a missing key with format specifiers
        let missingKey = "missing.key.with.%d.placeholder"

        // When formatting with arguments
        let result = missingKey.localized(with: 42)

        // Then it should return the formatted key
        XCTAssertEqual(result, "missing.key.with.42.placeholder")
    }

    // MARK: - Edge Cases and Special Characters

    func testLocalized_WithSpecialCharacters_PreservesCharacters() {
        // Given keys with special characters
        let keys = [
            "privacy.agreement.text", // Contains colon
            "test.alert.exit.message", // Contains %d placeholder in stored string
            "performance.outstanding.title" // Contains emoji
        ]

        // When getting localized strings
        for key in keys {
            let result = key.localized

            // Then it should not be empty and should preserve special characters
            XCTAssertFalse(result.isEmpty, "Localized string for \(key) should not be empty")
            XCTAssertNotEqual(result, key, "Should return localized value, not the key for \(key)")
        }
    }

    func testLocalized_WithEmojiInLocalizedString_PreservesEmoji() {
        // Given a key with emoji in the localized value
        let key = "performance.outstanding.title"

        // When getting the localized string
        let result = key.localized

        // Then it should preserve the emoji
        XCTAssertTrue(result.contains("🌟"), "Should preserve emoji in localized string")
        XCTAssertEqual(result, "Outstanding Performance! 🌟")
    }

    func testLocalized_WithNewlinesInLocalizedString_PreservesNewlines() {
        // Given a key with newlines in the localized value
        let key = "help.frequency.why.text"

        // When getting the localized string
        let result = key.localized

        // Then it should preserve newlines
        XCTAssertTrue(result.contains("\n"), "Should preserve newlines in localized string")
        XCTAssertTrue(result.contains("**"), "Should preserve markdown formatting")
    }

    func testLocalized_WithQuotesInLocalizedString_PreservesQuotes() {
        // Given a key with quotes in the localized value
        let key = "settings.logout.confirm.title"

        // When getting the localized string
        let result = key.localized

        // Then it should preserve quotes if present
        XCTAssertEqual(result, "Are you sure you want to logout?")
    }

    // MARK: - Real-World Usage Patterns

    func testLocalized_WithErrorMessages_ReturnsCorrectStrings() {
        // Test error message keys used throughout the app
        XCTAssertEqual("error.title".localized, "Something went wrong")
        XCTAssertEqual("error.retry.button".localized, "Try Again")
        XCTAssertEqual(
            "error.api.unauthorized".localized,
            "Your session has expired. Please log in again to continue."
        )
    }

    func testLocalized_WithLoadingMessages_ReturnsCorrectStrings() {
        // Test loading message keys
        XCTAssertEqual("loading.default".localized, "Loading...")
        XCTAssertEqual("loading.dashboard".localized, "Loading dashboard...")
        XCTAssertEqual("loading.signing.in".localized, "Signing in...")
    }

    func testLocalized_WithAccessibilityLabels_ReturnsCorrectStrings() {
        // Test accessibility label keys
        XCTAssertEqual("accessibility.retry.button".localized, "Try Again")
        XCTAssertEqual("accessibility.done.button".localized, "Done")
    }

    func testLocalizedWithArguments_WithPercentagePlaceholder_FormatsCorrectly() {
        // Given a key with %% (escaped percent sign) in the localized string
        let key = "accessibility.confidence.range"

        // When formatting with arguments
        let result = key.localized(with: 101, 115)

        // Then it should handle the escaped percent sign correctly
        XCTAssertTrue(result.contains("%"), "Should preserve percent sign")
        XCTAssertTrue(result.contains("101"), "Should include first argument")
        XCTAssertTrue(result.contains("115"), "Should include second argument")
    }

    // MARK: - Type Safety Tests

    func testLocalizedWithArguments_WithMixedTypes_FormatsCorrectly() {
        // Test that we can pass different types of arguments
        let key = "history.load.more.count"

        // When formatting with integers
        let result = key.localized(with: 25, 100)

        // Then it should format correctly
        XCTAssertEqual(result, "Showing 25 of 100 tests")
    }

    func testLocalizedWithArguments_WithNoArguments_ReturnsSameAsLocalized() {
        // Given a key without placeholders
        let key = "app.name"

        // When calling localized(with:) with no arguments
        let resultWithArgs = key.localized(with: [])
        let resultWithoutArgs = key.localized

        // Then both should return the same value
        XCTAssertEqual(resultWithArgs, resultWithoutArgs)
        XCTAssertEqual(resultWithArgs, "AIQ")
    }

    // MARK: - Consistency Tests

    func testLocalized_ConsistentResultsAcrossMultipleCalls() {
        // Given a localization key
        let key = "dashboard.title"

        // When calling localized multiple times
        let result1 = key.localized
        let result2 = key.localized
        let result3 = key.localized

        // Then all results should be identical
        XCTAssertEqual(result1, result2)
        XCTAssertEqual(result2, result3)
        XCTAssertEqual(result1, "Dashboard")
    }

    func testLocalizedWithArguments_ConsistentResultsWithSameArguments() {
        // Given a key and arguments
        let key = "dashboard.questions.answered"
        let arg = 10

        // When calling localized(with:) multiple times with same arguments
        let result1 = key.localized(with: arg)
        let result2 = key.localized(with: arg)
        let result3 = key.localized(with: arg)

        // Then all results should be identical
        XCTAssertEqual(result1, result2)
        XCTAssertEqual(result2, result3)
        XCTAssertEqual(result1, "10 questions answered")
    }
}
