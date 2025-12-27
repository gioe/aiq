import Foundation

// MARK: - Double Extensions for Locale-Aware Formatting

extension Double {
    /// Format as a percentage string with locale-aware formatting
    /// - Parameters:
    ///   - fractionDigits: Number of decimal places (default: 1)
    ///   - locale: The locale to use for formatting. Defaults to user's current locale.
    /// - Returns: Localized percentage string (e.g., "75.5%" in en_US, "75,5 %" in fr_FR)
    func toPercentageString(fractionDigits: Int = 1, locale: Locale = .current) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .percent
        formatter.minimumFractionDigits = fractionDigits
        formatter.maximumFractionDigits = fractionDigits
        formatter.locale = locale

        // Convert to percentage (0.755 -> 75.5%)
        let percentValue = self / 100.0
        return formatter.string(from: NSNumber(value: percentValue)) ?? "\(self)%"
    }

    /// Format as a decimal number with locale-aware formatting
    /// - Parameters:
    ///   - fractionDigits: Number of decimal places (default: 2)
    ///   - locale: The locale to use for formatting. Defaults to user's current locale.
    /// - Returns: Localized decimal string (e.g., "1,234.56" in en_US, "1 234,56" in fr_FR)
    func toDecimalString(fractionDigits: Int = 2, locale: Locale = .current) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        formatter.minimumFractionDigits = fractionDigits
        formatter.maximumFractionDigits = fractionDigits
        formatter.locale = locale

        return formatter.string(from: NSNumber(value: self)) ?? "\(self)"
    }

    /// Format as currency with locale-aware formatting
    /// - Parameters:
    ///   - currencyCode: ISO 4217 currency code (e.g., "USD", "EUR"). If nil, uses locale's currency.
    ///   - locale: The locale to use for formatting. Defaults to user's current locale.
    /// - Returns: Localized currency string (e.g., "$9.99" in en_US, "9,99 €" in de_DE)
    func toCurrencyString(currencyCode: String? = nil, locale: Locale = .current) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        formatter.locale = locale

        if let code = currencyCode {
            formatter.currencyCode = code
        }

        return formatter.string(from: NSNumber(value: self)) ?? "\(self)"
    }

    /// Format as a compact number (e.g., 1.2K, 3.4M)
    /// - Parameter locale: The locale to use for formatting. Defaults to user's current locale.
    /// - Returns: Localized compact number string
    @available(iOS 16.0, *)
    func toCompactString(locale: Locale = .current) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        formatter.locale = locale
        formatter.maximumFractionDigits = 1
        formatter.usesGroupingSeparator = true

        let absValue = abs(self)
        let sign = self < 0 ? "-" : ""

        switch absValue {
        case 1_000_000_000...:
            let value = absValue / 1_000_000_000
            return "\(sign)\(formatter.string(from: NSNumber(value: value)) ?? "\(value)")B"
        case 1_000_000...:
            let value = absValue / 1_000_000
            return "\(sign)\(formatter.string(from: NSNumber(value: value)) ?? "\(value)")M"
        case 1000...:
            let value = absValue / 1000
            return "\(sign)\(formatter.string(from: NSNumber(value: value)) ?? "\(value)")K"
        default:
            return formatter.string(from: NSNumber(value: self)) ?? "\(self)"
        }
    }
}

// MARK: - Int Extensions for Locale-Aware Formatting

extension Int {
    /// Format as a decimal number with locale-aware grouping separators
    /// - Parameter locale: The locale to use for formatting. Defaults to user's current locale.
    /// - Returns: Localized decimal string (e.g., "1,234" in en_US, "1.234" in de_DE, "1 234" in fr_FR)
    func toDecimalString(locale: Locale = .current) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        formatter.locale = locale

        return formatter.string(from: NSNumber(value: self)) ?? "\(self)"
    }

    /// Format as currency with locale-aware formatting
    /// - Parameters:
    ///   - currencyCode: ISO 4217 currency code (e.g., "USD", "EUR"). If nil, uses locale's currency.
    ///   - locale: The locale to use for formatting. Defaults to user's current locale.
    /// - Returns: Localized currency string (e.g., "$10" in en_US, "10 €" in de_DE)
    func toCurrencyString(currencyCode: String? = nil, locale: Locale = .current) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        formatter.locale = locale

        if let code = currencyCode {
            formatter.currencyCode = code
        }

        return formatter.string(from: NSNumber(value: self)) ?? "\(self)"
    }

    /// Format as a compact number (e.g., 1.2K, 3.4M)
    /// - Parameter locale: The locale to use for formatting. Defaults to user's current locale.
    /// - Returns: Localized compact number string
    @available(iOS 16.0, *)
    func toCompactString(locale: Locale = .current) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        formatter.locale = locale
        formatter.maximumFractionDigits = 1
        formatter.usesGroupingSeparator = true

        let absValue = abs(self)
        let sign = self < 0 ? "-" : ""

        switch absValue {
        case 1_000_000_000...:
            let value = Double(absValue) / 1_000_000_000
            return "\(sign)\(formatter.string(from: NSNumber(value: value)) ?? "\(value)")B"
        case 1_000_000...:
            let value = Double(absValue) / 1_000_000
            return "\(sign)\(formatter.string(from: NSNumber(value: value)) ?? "\(value)")M"
        case 1000...:
            let value = Double(absValue) / 1000
            return "\(sign)\(formatter.string(from: NSNumber(value: value)) ?? "\(value)")K"
        default:
            return formatter.string(from: NSNumber(value: self)) ?? "\(self)"
        }
    }
}

// MARK: - Time Formatting Extensions

extension Int {
    /// Format seconds as time duration string (MM:SS format)
    /// This uses a fixed format for consistency across locales (time durations are not typically localized)
    /// - Returns: Time duration string (e.g., "4:32", "12:05")
    func toTimeString() -> String {
        let minutes = self / 60
        let seconds = self % 60
        return String(format: "%d:%02d", minutes, seconds)
    }

    /// Format seconds as long duration string with locale-aware units
    /// - Parameter locale: The locale to use for formatting. Defaults to user's current locale.
    /// - Returns: Localized duration string (e.g., "4 minutes, 32 seconds" in en_US)
    func toLongDurationString(locale _: Locale = .current) -> String {
        let minutes = self / 60
        let seconds = self % 60

        let formatter = DateComponentsFormatter()
        formatter.unitsStyle = .full
        formatter.allowedUnits = [.minute, .second]
        formatter.zeroFormattingBehavior = .dropLeading

        // DateComponentsFormatter doesn't have a locale property, but it uses the system locale automatically
        return formatter.string(from: TimeInterval(self)) ?? toTimeString()
    }

    /// Format seconds as short duration string with locale-aware units
    /// - Parameter locale: The locale to use for formatting. Defaults to user's current locale.
    /// - Returns: Localized short duration string (e.g., "4m 32s" in en_US)
    func toShortDurationString(locale _: Locale = .current) -> String {
        let formatter = DateComponentsFormatter()
        formatter.unitsStyle = .abbreviated
        formatter.allowedUnits = [.minute, .second]
        formatter.zeroFormattingBehavior = .dropLeading

        return formatter.string(from: TimeInterval(self)) ?? toTimeString()
    }
}
