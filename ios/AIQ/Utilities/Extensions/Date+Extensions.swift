import Foundation

extension Date {
    /// Format date as a short string (e.g., "Jan 15, 2024")
    /// - Parameter locale: The locale to use for formatting. Defaults to user's current locale.
    /// - Returns: Localized date string with medium date style
    func toShortString(locale: Locale = .current) -> String {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .none
        formatter.locale = locale
        return formatter.string(from: self)
    }

    /// Format date as a long string (e.g., "January 15, 2024 at 3:45 PM")
    /// - Parameter locale: The locale to use for formatting. Defaults to user's current locale.
    /// - Returns: Localized date string with long date style and short time style
    func toLongString(locale: Locale = .current) -> String {
        let formatter = DateFormatter()
        formatter.dateStyle = .long
        formatter.timeStyle = .short
        formatter.locale = locale
        return formatter.string(from: self)
    }

    /// Format date as relative string (e.g., "2 days ago")
    /// - Parameter locale: The locale to use for formatting. Defaults to user's current locale.
    /// - Returns: Localized relative date string
    func toRelativeString(locale: Locale = .current) -> String {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .full
        formatter.locale = locale
        return formatter.localizedString(for: self, relativeTo: Date())
    }

    /// Format date for API communication (ISO 8601 format)
    /// Uses en_US_POSIX locale to ensure consistent format regardless of user's locale
    /// - Returns: ISO 8601 formatted date string (e.g., "2024-01-15T15:45:30Z")
    func toAPIString() -> String {
        let formatter = ISO8601DateFormatter()
        return formatter.string(from: self)
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
