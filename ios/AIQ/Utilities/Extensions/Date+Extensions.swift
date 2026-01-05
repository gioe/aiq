import Foundation

extension Date {
    // MARK: - Cached Formatters

    /// Cached date formatter for medium date style (e.g., "Jan 15, 2024")
    /// Thread-safe: DateFormatter is thread-safe for read-only use on iOS 7+/macOS 10.9+.
    /// Uses autoupdatingCurrent to track user locale changes without app restart.
    private static let mediumDateFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .none
        formatter.locale = .autoupdatingCurrent
        return formatter
    }()

    /// Cached date formatter for long date + short time (e.g., "January 15, 2024 at 3:45 PM")
    /// Thread-safe: DateFormatter is thread-safe for read-only use on iOS 7+/macOS 10.9+.
    /// Uses autoupdatingCurrent to track user locale changes without app restart.
    private static let longDateShortTimeFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateStyle = .long
        formatter.timeStyle = .short
        formatter.locale = .autoupdatingCurrent
        return formatter
    }()

    /// Cached date formatter for short date + short time (e.g., "1/15/24, 3:45 PM")
    /// Thread-safe: DateFormatter is thread-safe for read-only use on iOS 7+/macOS 10.9+.
    /// Uses autoupdatingCurrent to track user locale changes without app restart.
    private static let shortDateShortTimeFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateStyle = .short
        formatter.timeStyle = .short
        formatter.locale = .autoupdatingCurrent
        return formatter
    }()

    /// Cached relative date formatter (e.g., "2 days ago")
    /// Thread-safe: RelativeDateTimeFormatter is thread-safe for read-only use.
    /// Uses autoupdatingCurrent to track user locale changes without app restart.
    private static let relativeFormatter: RelativeDateTimeFormatter = {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .full
        formatter.locale = .autoupdatingCurrent
        return formatter
    }()

    /// Cached ISO 8601 formatter for API communication
    /// Thread-safe for read-only use after initialization
    private static let iso8601Formatter = ISO8601DateFormatter()

    // MARK: - Public Methods

    /// Format date as a short string (e.g., "Jan 15, 2024")
    /// - Parameter locale: The locale to use for formatting. Defaults to user's current locale.
    /// - Returns: Localized date string with medium date style
    func toShortString(locale: Locale = .current) -> String {
        // Use cached formatter for current locale, create new one for custom locale
        if locale == .current {
            return Self.mediumDateFormatter.string(from: self)
        } else {
            let formatter = DateFormatter()
            formatter.dateStyle = .medium
            formatter.timeStyle = .none
            formatter.locale = locale
            return formatter.string(from: self)
        }
    }

    /// Format date as a long string (e.g., "January 15, 2024 at 3:45 PM")
    /// - Parameter locale: The locale to use for formatting. Defaults to user's current locale.
    /// - Returns: Localized date string with long date style and short time style
    func toLongString(locale: Locale = .current) -> String {
        // Use cached formatter for current locale, create new one for custom locale
        if locale == .current {
            return Self.longDateShortTimeFormatter.string(from: self)
        } else {
            let formatter = DateFormatter()
            formatter.dateStyle = .long
            formatter.timeStyle = .short
            formatter.locale = locale
            return formatter.string(from: self)
        }
    }

    /// Format date as a compact string (e.g., "1/15/24, 3:45 PM")
    /// - Parameter locale: The locale to use for formatting. Defaults to user's current locale.
    /// - Returns: Localized date string with short date style and short time style
    func toCompactString(locale: Locale = .current) -> String {
        // Use cached formatter for current locale, create new one for custom locale
        if locale == .current {
            return Self.shortDateShortTimeFormatter.string(from: self)
        } else {
            let formatter = DateFormatter()
            formatter.dateStyle = .short
            formatter.timeStyle = .short
            formatter.locale = locale
            return formatter.string(from: self)
        }
    }

    /// Format date as relative string (e.g., "2 days ago")
    /// - Parameter locale: The locale to use for formatting. Defaults to user's current locale.
    /// - Returns: Localized relative date string
    func toRelativeString(locale: Locale = .current) -> String {
        // Use cached formatter for current locale, create new one for custom locale
        if locale == .current {
            return Self.relativeFormatter.localizedString(for: self, relativeTo: Date())
        } else {
            let formatter = RelativeDateTimeFormatter()
            formatter.unitsStyle = .full
            formatter.locale = locale
            return formatter.localizedString(for: self, relativeTo: Date())
        }
    }

    /// Format date for API communication (ISO 8601 format)
    /// Uses en_US_POSIX locale to ensure consistent format regardless of user's locale
    /// - Returns: ISO 8601 formatted date string (e.g., "2024-01-15T15:45:30Z")
    func toAPIString() -> String {
        Self.iso8601Formatter.string(from: self)
    }

    /// Check if date is today
    var isToday: Bool {
        Calendar.current.isDateInToday(self)
    }

    /// Check if date is in the past
    var isPast: Bool {
        self < Date()
    }
}
