import SwiftUI

/// Centralized typography system for consistent text styling
/// All styles support Dynamic Type for accessibility
enum Typography {
    // MARK: - Display Styles (Large, prominent text)

    // Note: Uses helper class for @ScaledMetric since enums cannot have property wrappers

    /// Extra large display text (48pt base, scales with Dynamic Type) - for major headings
    static var displayLarge: Font {
        FontScaling.displayLarge
    }

    /// Medium display text (42pt base, scales with Dynamic Type) - for app title, major headings
    static var displayMedium: Font {
        FontScaling.displayMedium
    }

    /// Small display text (36pt base, scales with Dynamic Type) - for section headings
    static var displaySmall: Font {
        FontScaling.displaySmall
    }

    // MARK: - Heading Styles

    // Uses semantic text styles that automatically scale with Dynamic Type

    /// Heading 1 (title, bold) - maps to ~28pt at default size
    static let h1 = Font.title.weight(.bold)

    /// Heading 2 (title2, semibold) - maps to ~22pt at default size
    static let h2 = Font.title2.weight(.semibold)

    /// Heading 3 (title3, semibold) - maps to ~20pt at default size
    static let h3 = Font.title3.weight(.semibold)

    /// Heading 4 (headline, semibold) - maps to ~17pt at default size
    static let h4 = Font.headline.weight(.semibold)

    // MARK: - Body Styles

    // Uses semantic text styles that automatically scale with Dynamic Type

    /// Large body text (body, regular) - standard reading text (~17pt at default)
    static let bodyLarge = Font.body.weight(.regular)

    /// Medium body text (callout, regular) - default body text (~16pt at default)
    static let bodyMedium = Font.callout.weight(.regular)

    /// Small body text (subheadline, regular) - secondary content (~15pt at default)
    static let bodySmall = Font.subheadline.weight(.regular)

    // MARK: - Label Styles

    // Uses semantic text styles that automatically scale with Dynamic Type

    /// Large label (subheadline, medium) - for prominent labels (~15pt at default)
    static let labelLarge = Font.subheadline.weight(.medium)

    /// Medium label (callout, medium) - for standard labels (~16pt at default)
    static let labelMedium = Font.callout.weight(.medium)

    /// Small label (footnote, medium) - for compact labels (~13pt at default)
    static let labelSmall = Font.footnote.weight(.medium)

    // MARK: - Caption Styles

    // Uses semantic text styles that automatically scale with Dynamic Type

    /// Large caption (footnote, regular) - for secondary information (~13pt at default)
    static let captionLarge = Font.footnote.weight(.regular)

    /// Medium caption (caption, regular) - for timestamps, metadata (~12pt at default)
    static let captionMedium = Font.caption.weight(.regular)

    /// Small caption (caption2, regular) - for fine print (~11pt at default)
    static let captionSmall = Font.caption2.weight(.regular)

    // MARK: - Special Styles

    /// Score display (72pt base, scales with Dynamic Type) - for IQ scores
    static var scoreDisplay: Font {
        FontScaling.scoreDisplay
    }

    /// Stat value (title, bold) - for dashboard stats
    static let statValue = Font.title.weight(.bold)

    /// Button text (headline) - for buttons
    static let button = Font.headline
}

// MARK: - Font Scaling Helper

/// Helper class to enable @ScaledMetric for special font sizes
/// SwiftUI's @ScaledMetric property wrapper cannot be used directly in enums,
/// so we use a helper class with static computed properties
private enum FontScaling {
    // MARK: - Scaled Metrics

    /// Scaled metric for score display (72pt base)
    @ScaledMetric(relativeTo: .largeTitle) private static var scoreSize: CGFloat = 72

    /// Scaled metric for display large (48pt base)
    @ScaledMetric(relativeTo: .largeTitle) private static var displayLargeSize: CGFloat = 48

    /// Scaled metric for display medium (42pt base)
    @ScaledMetric(relativeTo: .largeTitle) private static var displayMediumSize: CGFloat = 42

    /// Scaled metric for display small (36pt base)
    @ScaledMetric(relativeTo: .title) private static var displaySmallSize: CGFloat = 36

    // MARK: - Font Getters

    /// Score display font with Dynamic Type scaling
    static var scoreDisplay: Font {
        Font.system(size: scoreSize, weight: .bold, design: .rounded)
    }

    /// Display large font with Dynamic Type scaling
    static var displayLarge: Font {
        Font.system(size: displayLargeSize, weight: .bold, design: .rounded)
    }

    /// Display medium font with Dynamic Type scaling
    static var displayMedium: Font {
        Font.system(size: displayMediumSize, weight: .bold, design: .default)
    }

    /// Display small font with Dynamic Type scaling
    static var displaySmall: Font {
        Font.system(size: displaySmallSize, weight: .bold, design: .default)
    }
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
