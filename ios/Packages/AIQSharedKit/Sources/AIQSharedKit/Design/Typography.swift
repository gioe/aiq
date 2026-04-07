import SwiftUI

/// Centralized typography system for consistent text styling
/// All styles support Dynamic Type for accessibility
public enum Typography {
    // MARK: - Heading Styles

    // Uses semantic text styles that automatically scale with Dynamic Type

    /// Heading 1 (title, bold) - maps to ~28pt at default size
    public static let h1 = Font.title.weight(.bold)

    /// Heading 2 (title2, semibold) - maps to ~22pt at default size
    public static let h2 = Font.title2.weight(.semibold)

    /// Heading 3 (title3, semibold) - maps to ~20pt at default size
    public static let h3 = Font.title3.weight(.semibold)

    /// Heading 4 (headline, semibold) - maps to ~17pt at default size
    public static let h4 = Font.headline.weight(.semibold)

    // MARK: - Body Styles

    /// Large body text (body, regular) - standard reading text (~17pt at default)
    public static let bodyLarge = Font.body.weight(.regular)

    /// Medium body text (callout, regular) - default body text (~16pt at default)
    public static let bodyMedium = Font.callout.weight(.regular)

    /// Small body text (subheadline, regular) - secondary content (~15pt at default)
    public static let bodySmall = Font.subheadline.weight(.regular)

    // MARK: - Label Styles

    /// Large label (subheadline, medium) - for prominent labels (~15pt at default)
    public static let labelLarge = Font.subheadline.weight(.medium)

    /// Medium label (callout, medium) - for standard labels (~16pt at default)
    public static let labelMedium = Font.callout.weight(.medium)

    /// Small label (footnote, medium) - for compact labels (~13pt at default)
    public static let labelSmall = Font.footnote.weight(.medium)

    // MARK: - Caption Styles

    /// Large caption (footnote, regular) - for secondary information (~13pt at default)
    public static let captionLarge = Font.footnote.weight(.regular)

    /// Medium caption (caption, regular) - for timestamps, metadata (~12pt at default)
    public static let captionMedium = Font.caption.weight(.regular)

    /// Small caption (caption2, regular) - for fine print (~11pt at default)
    public static let captionSmall = Font.caption2.weight(.regular)

    // MARK: - Special Styles

    /// Stat value (title, bold) - for dashboard stats
    public static let statValue = Font.title.weight(.bold)

    /// Button text (headline) - for buttons
    public static let button = Font.headline
}
