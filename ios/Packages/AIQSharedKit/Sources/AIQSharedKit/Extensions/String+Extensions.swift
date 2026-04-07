import Foundation

public extension String {
    /// Check if string is not empty (ignoring whitespace)
    var isNotEmpty: Bool {
        !trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    /// Trim whitespace and newlines
    var trimmed: String {
        trimmingCharacters(in: .whitespacesAndNewlines)
    }

    /// Parses markdown bold markers (`**text**`) into an `AttributedString`.
    /// Returns a plain `AttributedString` if parsing fails or no markdown is present.
    var markdownAttributed: AttributedString {
        let options = AttributedString.MarkdownParsingOptions(
            interpretedSyntax: .inlineOnlyPreservingWhitespace
        )
        return (try? AttributedString(markdown: self, options: options))
            ?? AttributedString(self)
    }
}
