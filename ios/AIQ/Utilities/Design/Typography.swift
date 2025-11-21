import SwiftUI

/// Centralized typography system for consistent text styling
/// Provides standardized font styles that adapt to Dynamic Type
enum Typography {
    // MARK: - Display Styles (Large, prominent text)

    /// Extra large display text (48pt, bold) - for major headings
    static let displayLarge = Font.system(size: 48, weight: .bold, design: .rounded)

    /// Medium display text (42pt, bold) - for app title, major headings
    static let displayMedium = Font.system(size: 42, weight: .bold, design: .default)

    /// Small display text (36pt, bold) - for section headings
    static let displaySmall = Font.system(size: 36, weight: .bold, design: .default)

    // MARK: - Heading Styles

    /// Heading 1 (28pt, bold)
    static let h1 = Font.system(size: 28, weight: .bold)

    /// Heading 2 (24pt, semibold)
    static let h2 = Font.system(size: 24, weight: .semibold)

    /// Heading 3 (20pt, semibold)
    static let h3 = Font.system(size: 20, weight: .semibold)

    /// Heading 4 (18pt, semibold)
    static let h4 = Font.system(size: 18, weight: .semibold)

    // MARK: - Body Styles

    /// Large body text (17pt, regular) - standard reading text
    static let bodyLarge = Font.system(size: 17, weight: .regular)

    /// Medium body text (15pt, regular) - default body text
    static let bodyMedium = Font.system(size: 15, weight: .regular)

    /// Small body text (13pt, regular) - secondary content
    static let bodySmall = Font.system(size: 13, weight: .regular)

    // MARK: - Label Styles

    /// Large label (15pt, medium) - for prominent labels
    static let labelLarge = Font.system(size: 15, weight: .medium)

    /// Medium label (13pt, medium) - for standard labels
    static let labelMedium = Font.system(size: 13, weight: .medium)

    /// Small label (11pt, medium) - for compact labels
    static let labelSmall = Font.system(size: 11, weight: .medium)

    // MARK: - Caption Styles

    /// Large caption (12pt, regular) - for secondary information
    static let captionLarge = Font.system(size: 12, weight: .regular)

    /// Medium caption (11pt, regular) - for timestamps, metadata
    static let captionMedium = Font.system(size: 11, weight: .regular)

    /// Small caption (10pt, regular) - for fine print
    static let captionSmall = Font.system(size: 10, weight: .regular)

    // MARK: - Special Styles

    /// Score display (72pt, bold, rounded) - for IQ scores
    static let scoreDisplay = Font.system(size: 72, weight: .bold, design: .rounded)

    /// Stat value (title, bold) - for dashboard stats
    static let statValue = Font.title.weight(.bold)

    /// Button text (headline) - for buttons
    static let button = Font.headline
}

// MARK: - View Extensions for Typography

extension View {
    /// Apply typography style with semantic color
    /// - Parameters:
    ///   - typography: The typography style to apply
    ///   - color: The color to apply (default: primary text)
    func style(
        _ typography: Font,
        color: Color = ColorPalette.textPrimary
    ) -> some View {
        font(typography)
            .foregroundColor(color)
    }
}

// MARK: - Text Extensions

extension Text {
    /// Create text with heading 1 style
    func h1(_ color: Color = ColorPalette.textPrimary) -> some View {
        style(Typography.h1, color: color)
    }

    /// Create text with heading 2 style
    func h2(_ color: Color = ColorPalette.textPrimary) -> some View {
        style(Typography.h2, color: color)
    }

    /// Create text with heading 3 style
    func h3(_ color: Color = ColorPalette.textPrimary) -> some View {
        style(Typography.h3, color: color)
    }

    /// Create text with body style
    func body(_ color: Color = ColorPalette.textPrimary) -> some View {
        style(Typography.bodyMedium, color: color)
    }

    /// Create text with caption style
    func caption(_ color: Color = ColorPalette.textSecondary) -> some View {
        style(Typography.captionMedium, color: color)
    }
}
