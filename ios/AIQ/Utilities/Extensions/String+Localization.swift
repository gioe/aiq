import Foundation

extension String {
    /// Returns the localized version of this string using the main bundle
    ///
    /// If the string key is not found in Localizable.strings, returns the key itself.
    /// This prevents displaying placeholder text and makes missing translations obvious during development.
    ///
    /// Example:
    /// ```swift
    /// let title = "dashboard.title".localized
    /// ```
    var localized: String {
        NSLocalizedString(self, comment: "")
    }

    /// Returns the localized version of this string with format arguments
    ///
    /// Useful for strings with placeholders that need to be filled in with dynamic values.
    /// If the string key is not found, returns the key itself formatted with the arguments.
    ///
    /// Example:
    /// ```swift
    /// let message = "dashboard.questions.answered".localized(with: 5)
    /// // Returns: "5 questions answered"
    /// ```
    ///
    /// - Parameter arguments: The arguments to substitute into the format string
    /// - Returns: The localized and formatted string
    func localized(with arguments: CVarArg...) -> String {
        let localizedFormat = NSLocalizedString(self, comment: "")
        return String(format: localizedFormat, arguments: arguments)
    }
}
