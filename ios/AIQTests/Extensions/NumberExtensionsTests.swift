@testable import AIQ
import XCTest

final class NumberExtensionsTests: XCTestCase {
    // MARK: - Double.toPercentageString Tests

    func testDoubleToPercentageString_enUS() {
        let locale = Locale(identifier: "en_US")
        let value = 75.5

        let result = value.toPercentageString(locale: locale)

        // US locale uses period for decimal separator
        XCTAssertTrue(result.contains("75"), "Should contain integer part")
        XCTAssertTrue(result.contains("%"), "Should contain percent symbol")
    }

    func testDoubleToPercentageString_frFR() {
        let locale = Locale(identifier: "fr_FR")
        let value = 75.5

        let result = value.toPercentageString(locale: locale)

        // French locale uses comma for decimal separator and space before %
        XCTAssertTrue(result.contains("75"), "Should contain integer part")
        XCTAssertTrue(result.contains("%"), "Should contain percent symbol")
    }

    func testDoubleToPercentageString_customFractionDigits() {
        let locale = Locale(identifier: "en_US")
        let value = 75.555

        let result1 = value.toPercentageString(fractionDigits: 0, locale: locale)
        let result2 = value.toPercentageString(fractionDigits: 2, locale: locale)

        // Different fraction digits should produce different results
        XCTAssertNotEqual(result1, result2, "Different fraction digits should produce different results")
        XCTAssertTrue(result1.contains("%"), "Should contain percent symbol")
        XCTAssertTrue(result2.contains("%"), "Should contain percent symbol")
    }

    func testDoubleToPercentageString_zeroValue() {
        let locale = Locale(identifier: "en_US")
        let value = 0.0

        let result = value.toPercentageString(locale: locale)

        XCTAssertTrue(result.contains("0"), "Should contain zero")
        XCTAssertTrue(result.contains("%"), "Should contain percent symbol")
    }

    func testDoubleToPercentageString_hundredPercent() {
        let locale = Locale(identifier: "en_US")
        let value = 100.0

        let result = value.toPercentageString(locale: locale)

        XCTAssertTrue(result.contains("100"), "Should contain 100")
        XCTAssertTrue(result.contains("%"), "Should contain percent symbol")
    }

    // MARK: - Double.toDecimalString Tests

    func testDoubleToDecimalString_enUS() {
        let locale = Locale(identifier: "en_US")
        let value = 1234.56

        let result = value.toDecimalString(locale: locale)

        // US locale uses comma for thousands separator and period for decimal
        XCTAssertTrue(result.contains("1") && result.contains("234"), "Should contain all digits")
        XCTAssertTrue(result.contains(",") || !result.contains("1234"), "Should use grouping separator")
    }

    func testDoubleToDecimalString_deDE() {
        let locale = Locale(identifier: "de_DE")
        let value = 1234.56

        let result = value.toDecimalString(locale: locale)

        // German locale uses period for thousands separator and comma for decimal
        XCTAssertTrue(result.contains("1") && result.contains("234"), "Should contain all digits")
    }

    func testDoubleToDecimalString_frFR() {
        let locale = Locale(identifier: "fr_FR")
        let value = 1234.56

        let result = value.toDecimalString(locale: locale)

        // French locale uses space for thousands separator and comma for decimal
        XCTAssertTrue(result.contains("1") && result.contains("234"), "Should contain all digits")
    }

    func testDoubleToDecimalString_customFractionDigits() {
        let locale = Locale(identifier: "en_US")
        let value = 123.456789

        let result1 = value.toDecimalString(fractionDigits: 0, locale: locale)
        let result2 = value.toDecimalString(fractionDigits: 4, locale: locale)

        // Different fraction digits should produce different precision
        XCTAssertTrue(result1.contains("123"), "Should contain integer part")
        XCTAssertTrue(result2.contains("123"), "Should contain integer part")
        XCTAssertNotEqual(result1, result2, "Different fraction digits should produce different results")
    }

    // MARK: - Double.toCurrencyString Tests

    func testDoubleToCurrencyString_enUS_USD() {
        let locale = Locale(identifier: "en_US")
        let value = 9.99

        let result = value.toCurrencyString(currencyCode: "USD", locale: locale)

        // US locale USD format
        XCTAssertTrue(result.contains("9"), "Should contain amount")
        XCTAssertTrue(result.contains("$") || result.contains("USD"), "Should contain currency symbol")
    }

    func testDoubleToCurrencyString_deDE_EUR() {
        let locale = Locale(identifier: "de_DE")
        let value = 9.99

        let result = value.toCurrencyString(currencyCode: "EUR", locale: locale)

        // German locale EUR format
        XCTAssertTrue(result.contains("9"), "Should contain amount")
        XCTAssertTrue(result.contains("€") || result.contains("EUR"), "Should contain currency symbol")
    }

    func testDoubleToCurrencyString_enGB_GBP() {
        let locale = Locale(identifier: "en_GB")
        let value = 9.99

        let result = value.toCurrencyString(currencyCode: "GBP", locale: locale)

        // UK locale GBP format
        XCTAssertTrue(result.contains("9"), "Should contain amount")
        XCTAssertTrue(result.contains("£") || result.contains("GBP"), "Should contain currency symbol")
    }

    func testDoubleToCurrencyString_usesLocaleCurrencyWhenCodeNotProvided() {
        let locale = Locale(identifier: "en_US")
        let value = 9.99

        let result = value.toCurrencyString(locale: locale)

        // Should use locale's default currency
        XCTAssertFalse(result.isEmpty, "Should return non-empty string")
        XCTAssertTrue(result.contains("9"), "Should contain amount")
    }

    func testDoubleToCurrencyString_largeAmount() {
        let locale = Locale(identifier: "en_US")
        let value = 1_234_567.89

        let result = value.toCurrencyString(currencyCode: "USD", locale: locale)

        // Should handle large amounts with grouping separators
        XCTAssertTrue(result.contains("1"), "Should contain amount")
        XCTAssertTrue(result.contains("$") || result.contains("USD"), "Should contain currency symbol")
    }

    // MARK: - Double.toCompactString Tests (iOS 16+)

    @available(iOS 16.0, *)
    func testDoubleToCompactString_thousands() {
        let locale = Locale(identifier: "en_US")
        let value = 1234.0

        let result = value.toCompactString(locale: locale)

        // Should format as "1.2K"
        XCTAssertTrue(result.contains("1"), "Should contain value")
        XCTAssertTrue(result.contains("K"), "Should contain K suffix")
    }

    @available(iOS 16.0, *)
    func testDoubleToCompactString_millions() {
        let locale = Locale(identifier: "en_US")
        let value = 2_500_000.0

        let result = value.toCompactString(locale: locale)

        // Should format as "2.5M"
        XCTAssertTrue(result.contains("2"), "Should contain value")
        XCTAssertTrue(result.contains("M"), "Should contain M suffix")
    }

    @available(iOS 16.0, *)
    func testDoubleToCompactString_billions() {
        let locale = Locale(identifier: "en_US")
        let value = 3_400_000_000.0

        let result = value.toCompactString(locale: locale)

        // Should format as "3.4B"
        XCTAssertTrue(result.contains("3"), "Should contain value")
        XCTAssertTrue(result.contains("B"), "Should contain B suffix")
    }

    @available(iOS 16.0, *)
    func testDoubleToCompactString_smallValue() {
        let locale = Locale(identifier: "en_US")
        let value = 123.0

        let result = value.toCompactString(locale: locale)

        // Should not use suffix for small values
        XCTAssertTrue(result.contains("123"), "Should contain full value")
        XCTAssertFalse(result.contains("K"), "Should not contain K suffix")
    }

    @available(iOS 16.0, *)
    func testDoubleToCompactString_negativeValue() {
        let locale = Locale(identifier: "en_US")
        let value: Double = -1234.0

        let result = value.toCompactString(locale: locale)

        // Should handle negative values
        XCTAssertTrue(result.contains("-"), "Should contain negative sign")
        XCTAssertTrue(result.contains("K"), "Should contain K suffix")
    }

    // MARK: - Int.toDecimalString Tests

    func testIntToDecimalString_enUS() {
        let locale = Locale(identifier: "en_US")
        let value = 1234

        let result = value.toDecimalString(locale: locale)

        // US locale uses comma for thousands separator
        XCTAssertTrue(result.contains("1"), "Should contain all digits")
        XCTAssertTrue(result.contains("234"), "Should contain all digits")
    }

    func testIntToDecimalString_deDE() {
        let locale = Locale(identifier: "de_DE")
        let value = 1234

        let result = value.toDecimalString(locale: locale)

        // German locale uses period for thousands separator
        XCTAssertTrue(result.contains("1"), "Should contain all digits")
        XCTAssertTrue(result.contains("234"), "Should contain all digits")
    }

    func testIntToDecimalString_frFR() {
        let locale = Locale(identifier: "fr_FR")
        let value = 1234

        let result = value.toDecimalString(locale: locale)

        // French locale uses space for thousands separator
        XCTAssertTrue(result.contains("1"), "Should contain all digits")
        XCTAssertTrue(result.contains("234"), "Should contain all digits")
    }

    func testIntToDecimalString_smallValue() {
        let locale = Locale(identifier: "en_US")
        let value = 123

        let result = value.toDecimalString(locale: locale)

        // Small values don't have grouping separators
        XCTAssertEqual(result, "123", "Should be exactly 123")
    }

    // MARK: - Int.toCurrencyString Tests

    func testIntToCurrencyString_enUS_USD() {
        let locale = Locale(identifier: "en_US")
        let value = 10

        let result = value.toCurrencyString(currencyCode: "USD", locale: locale)

        // Should format as currency
        XCTAssertTrue(result.contains("10"), "Should contain amount")
        XCTAssertTrue(result.contains("$") || result.contains("USD"), "Should contain currency symbol")
    }

    func testIntToCurrencyString_jaJP_JPY() {
        let locale = Locale(identifier: "ja_JP")
        let value = 1000

        let result = value.toCurrencyString(currencyCode: "JPY", locale: locale)

        // Japanese Yen format
        XCTAssertTrue(result.contains("1"), "Should contain amount")
        XCTAssertTrue(result.contains("¥") || result.contains("JPY"), "Should contain currency symbol")
    }

    // MARK: - Int.toTimeString Tests

    func testIntToTimeString_underOneMinute() {
        let value = 45 // 45 seconds

        let result = value.toTimeString()

        XCTAssertEqual(result, "0:45", "Should format as 0:45")
    }

    func testIntToTimeString_oneMinute() {
        let value = 60 // 1 minute

        let result = value.toTimeString()

        XCTAssertEqual(result, "1:00", "Should format as 1:00")
    }

    func testIntToTimeString_severalMinutes() {
        let value = 272 // 4 minutes 32 seconds

        let result = value.toTimeString()

        XCTAssertEqual(result, "4:32", "Should format as 4:32")
    }

    func testIntToTimeString_overTenMinutes() {
        let value = 725 // 12 minutes 5 seconds

        let result = value.toTimeString()

        XCTAssertEqual(result, "12:05", "Should format as 12:05")
    }

    func testIntToTimeString_zeroSeconds() {
        let value = 0

        let result = value.toTimeString()

        XCTAssertEqual(result, "0:00", "Should format as 0:00")
    }

    // MARK: - Int.toLongDurationString Tests

    func testIntToLongDurationString_severalMinutes() {
        let value = 272 // 4 minutes 32 seconds

        let result = value.toLongDurationString()

        // Should contain time components (format may vary by locale)
        XCTAssertFalse(result.isEmpty, "Should return non-empty string")
    }

    func testIntToLongDurationString_underOneMinute() {
        let value = 45 // 45 seconds

        let result = value.toLongDurationString()

        // Should handle under one minute
        XCTAssertFalse(result.isEmpty, "Should return non-empty string")
    }

    // MARK: - Int.toShortDurationString Tests

    func testIntToShortDurationString_severalMinutes() {
        let value = 272 // 4 minutes 32 seconds

        let result = value.toShortDurationString()

        // Should contain abbreviated time components
        XCTAssertFalse(result.isEmpty, "Should return non-empty string")
    }

    func testIntToShortDurationString_underOneMinute() {
        let value = 45 // 45 seconds

        let result = value.toShortDurationString()

        // Should handle under one minute with abbreviated format
        XCTAssertFalse(result.isEmpty, "Should return non-empty string")
    }
}
