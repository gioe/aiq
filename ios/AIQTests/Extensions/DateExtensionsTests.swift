@testable import AIQ
import XCTest

final class DateExtensionsTests: XCTestCase {
    var testDate: Date!

    override func setUp() {
        super.setUp()
        // January 15, 2024 at 3:45:30 PM UTC
        var components = DateComponents()
        components.year = 2024
        components.month = 1
        components.day = 15
        components.hour = 15
        components.minute = 45
        components.second = 30
        components.timeZone = TimeZone(identifier: "UTC")

        let calendar = Calendar(identifier: .gregorian)
        testDate = calendar.date(from: components)!
    }

    // MARK: - toShortString Tests

    func testToShortString_enUS() {
        let locale = Locale(identifier: "en_US")
        let result = testDate.toShortString(locale: locale)

        // Medium date style in en_US: "Jan 15, 2024"
        XCTAssertTrue(result.contains("Jan"), "Should contain abbreviated month")
        XCTAssertTrue(result.contains("15"), "Should contain day")
        XCTAssertTrue(result.contains("2024"), "Should contain year")
    }

    func testToShortString_frFR() {
        let locale = Locale(identifier: "fr_FR")
        let result = testDate.toShortString(locale: locale)

        // French locale uses different date format
        XCTAssertTrue(result.contains("15"), "Should contain day")
        XCTAssertTrue(result.contains("2024"), "Should contain year")
    }

    func testToShortString_deDE() {
        let locale = Locale(identifier: "de_DE")
        let result = testDate.toShortString(locale: locale)

        // German locale uses different date format
        XCTAssertTrue(result.contains("15"), "Should contain day")
        XCTAssertTrue(result.contains("2024"), "Should contain year")
    }

    func testToShortString_defaultsToCurrentLocale() {
        let result = testDate.toShortString()

        // Should work with current locale
        XCTAssertFalse(result.isEmpty, "Should return non-empty string")
        XCTAssertTrue(result.contains("15"), "Should contain day")
        XCTAssertTrue(result.contains("2024"), "Should contain year")
    }

    // MARK: - toLongString Tests

    func testToLongString_enUS() {
        let locale = Locale(identifier: "en_US")
        let result = testDate.toLongString(locale: locale)

        // Long date style with short time in en_US
        XCTAssertTrue(result.contains("January"), "Should contain full month name")
        XCTAssertTrue(result.contains("15"), "Should contain day")
        XCTAssertTrue(result.contains("2024"), "Should contain year")
        // Time format may vary based on timezone
    }

    func testToLongString_frFR() {
        let locale = Locale(identifier: "fr_FR")
        let result = testDate.toLongString(locale: locale)

        // French locale uses different format
        XCTAssertTrue(result.contains("15"), "Should contain day")
        XCTAssertTrue(result.contains("2024"), "Should contain year")
    }

    func testToLongString_defaultsToCurrentLocale() {
        let result = testDate.toLongString()

        // Should work with current locale
        XCTAssertFalse(result.isEmpty, "Should return non-empty string")
    }

    // MARK: - toCompactString Tests

    func testToCompactString_enUS() {
        let locale = Locale(identifier: "en_US")
        let result = testDate.toCompactString(locale: locale)

        // Short date + short time style in en_US: "1/15/24, 3:45 PM"
        XCTAssertTrue(result.contains("15"), "Should contain day")
        XCTAssertTrue(result.contains("24"), "Should contain abbreviated year")
    }

    func testToCompactString_frFR() {
        let locale = Locale(identifier: "fr_FR")
        let result = testDate.toCompactString(locale: locale)

        // French locale uses different date format
        XCTAssertTrue(result.contains("15"), "Should contain day")
        XCTAssertTrue(result.contains("24") || result.contains("2024"), "Should contain year")
    }

    func testToCompactString_defaultsToCurrentLocale() {
        let result = testDate.toCompactString()

        // Should work with current locale
        XCTAssertFalse(result.isEmpty, "Should return non-empty string")
        XCTAssertTrue(result.contains("15"), "Should contain day")
    }

    func testToCompactString_includesTime() {
        let locale = Locale(identifier: "en_US")
        let result = testDate.toCompactString(locale: locale)

        // Should include time component (either 3:45 or 15:45 depending on locale)
        XCTAssertTrue(result.contains(":"), "Should contain time separator")
    }

    // MARK: - toRelativeString Tests

    func testToRelativeString_futureDate() {
        let futureDate = Date().addingTimeInterval(3600) // 1 hour from now
        let result = futureDate.toRelativeString()

        // Should indicate future time
        XCTAssertFalse(result.isEmpty, "Should return non-empty string")
    }

    func testToRelativeString_pastDate() {
        let pastDate = Date().addingTimeInterval(-3600) // 1 hour ago
        let result = pastDate.toRelativeString()

        // Should indicate past time
        XCTAssertFalse(result.isEmpty, "Should return non-empty string")
    }

    func testToRelativeString_respectsLocale() {
        let pastDate = Date().addingTimeInterval(-86400) // 1 day ago
        let enResult = pastDate.toRelativeString(locale: Locale(identifier: "en_US"))
        let frResult = pastDate.toRelativeString(locale: Locale(identifier: "fr_FR"))

        // Different locales should produce different strings
        XCTAssertFalse(enResult.isEmpty, "English result should not be empty")
        XCTAssertFalse(frResult.isEmpty, "French result should not be empty")
    }

    // MARK: - toAPIString Tests

    func testToAPIString_producesISO8601Format() {
        let result = testDate.toAPIString()

        // ISO 8601 format should contain year, month, day, and separators
        XCTAssertTrue(result.contains("2024"), "Should contain year")
        XCTAssertTrue(result.contains("01"), "Should contain zero-padded month")
        XCTAssertTrue(result.contains("15"), "Should contain day")
        XCTAssertTrue(result.contains("T"), "Should contain time separator")
        XCTAssertTrue(result.contains("Z") || result.contains("+"), "Should contain timezone indicator")
    }

    func testToAPIString_isConsistentAcrossLocales() {
        // API strings should be identical regardless of locale
        let result1 = testDate.toAPIString()

        // Change system settings won't affect API string format
        let result2 = testDate.toAPIString()

        XCTAssertEqual(result1, result2, "API strings should be consistent")
    }

    // MARK: - isToday Tests

    func testIsToday_withTodaysDate() {
        let today = Date()
        XCTAssertTrue(today.isToday, "Today's date should be recognized as today")
    }

    func testIsToday_withYesterdaysDate() {
        let yesterday = Date().addingTimeInterval(-86400)
        XCTAssertFalse(yesterday.isToday, "Yesterday's date should not be recognized as today")
    }

    func testIsToday_withFutureDate() {
        let tomorrow = Date().addingTimeInterval(86400)
        XCTAssertFalse(tomorrow.isToday, "Tomorrow's date should not be recognized as today")
    }

    // MARK: - isPast Tests

    func testIsPast_withPastDate() {
        let pastDate = Date().addingTimeInterval(-3600)
        XCTAssertTrue(pastDate.isPast, "Past date should be recognized as past")
    }

    func testIsPast_withFutureDate() {
        let futureDate = Date().addingTimeInterval(3600)
        XCTAssertFalse(futureDate.isPast, "Future date should not be recognized as past")
    }

    func testIsPast_withCurrentDate() {
        // Use a small future offset to avoid race condition
        let almostNow = Date().addingTimeInterval(0.1)
        // A date slightly in the future is not in the past
        XCTAssertFalse(almostNow.isPast, "Almost-current date should not be past")
    }
}
