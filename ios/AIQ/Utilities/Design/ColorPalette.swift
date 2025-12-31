import SwiftUI

/// Centralized color palette for the AIQ app
/// Provides consistent colors across light and dark modes
///
/// # WCAG AA Accessibility Guidelines
///
/// This color palette has been audited for WCAG 2.1 Level AA compliance.
/// See `ios/docs/WCAG_COLOR_CONTRAST_ANALYSIS.md` for the full contrast ratio analysis.
///
/// ## Key Contrast Requirements
/// - **Normal text** (< 18pt): 4.5:1 minimum contrast ratio
/// - **Large text** (>= 18pt or >= 14pt bold): 3:1 minimum contrast ratio
/// - **UI components**: 3:1 minimum contrast ratio
///
/// ## Light Mode Limitations
/// The following colors have **insufficient contrast** for text on white backgrounds:
/// - `success` (green): 2.6:1 - Use for icons only, never text
/// - `warning` (orange): 2.3:1 - Use for icons only, never text
/// - `performanceGood` (teal): 2.3:1 - Use for icons only, never text
/// - `info` (blue): 3.9:1 - Large text only (>= 18pt)
/// - `error` (red): 4.0:1 - Large text only (>= 18pt)
///
/// ## Recommended Patterns
/// - Use colored icons with `textPrimary` labels (not colored text)
/// - For colored badges: use black/white text on colored backgrounds
/// - Purple is the only semantic color safe for normal text in light mode
///
/// ## Dark Mode
/// All semantic colors have excellent contrast (7.5:1 to 11.4:1) on dark backgrounds.
enum ColorPalette {
    // MARK: - Primary Colors

    /// Primary brand color (blue)
    static let primary = Color.accentColor

    /// Secondary brand color (purple)
    static let secondary = Color.purple

    // MARK: - Semantic Colors

    // Note: See WCAG documentation above for accessibility guidance on these colors

    /// Success color (green) - for positive feedback, high scores
    /// - Warning: Light mode contrast 2.6:1 on white - use for icons only, not text
    /// - Dark mode: Excellent contrast (10.2:1) - safe for text
    static let success = Color.green

    /// Warning color (orange) - for warnings, medium scores
    /// - Warning: Light mode contrast 2.3:1 on white - use for icons only, not text
    /// - Dark mode: Excellent contrast (11.4:1) - safe for text
    static let warning = Color.orange

    /// Error color (red) - for errors, low scores
    /// - Warning: Light mode contrast 4.0:1 on white - large text only (>= 18pt)
    /// - Dark mode: Excellent contrast (9.6:1) - safe for text
    static let error = Color.red

    /// Info color (blue) - for informational content
    /// - Warning: Light mode contrast 3.9:1 on white - large text only (>= 18pt)
    /// - Dark mode: Excellent contrast (8.6:1) - safe for text
    static let info = Color.blue

    // MARK: - Neutral Colors

    /// Primary text color
    static let textPrimary = Color.primary

    /// Secondary text color (lighter)
    static let textSecondary = Color.secondary

    /// Tertiary text color (lightest)
    /// - Warning: Light mode contrast 2.9:1 on white - large text only (>= 18pt)
    /// - Warning: Dark mode contrast 2.1:1 on black - use for decorative content only
    static let textTertiary = Color(uiColor: .tertiaryLabel)

    // MARK: - Background Colors

    /// Primary background color
    static let background = Color(uiColor: .systemBackground)

    /// Secondary background color (for cards, elevated surfaces)
    static let backgroundSecondary = Color(uiColor: .secondarySystemBackground)

    /// Tertiary background color (for nested content)
    static let backgroundTertiary = Color(uiColor: .tertiarySystemBackground)

    /// Grouped background (for lists, table views)
    static let backgroundGrouped = Color(uiColor: .systemGroupedBackground)

    // MARK: - Chart Colors

    /// Colors for charts and data visualization
    static let chartColors: [Color] = [
        .blue,
        .purple,
        .green,
        .orange,
        .pink,
        .teal
    ]

    // MARK: - Gradient Colors

    /// Trophy gradient (yellow to orange)
    static let trophyGradient = LinearGradient(
        colors: [.yellow, .orange],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
    )

    /// Score gradient (blue to purple)
    static let scoreGradient = LinearGradient(
        colors: [.blue, .purple],
        startPoint: .leading,
        endPoint: .trailing
    )

    /// Success gradient (light green to green)
    static let successGradient = LinearGradient(
        colors: [Color.green.opacity(0.6), Color.green],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
    )

    // MARK: - Stat Card Colors

    // Note: In light mode, use for icons with textPrimary for values. In dark mode, safe for text.

    /// Color for "Tests Taken" stat
    /// - Warning: Light mode contrast 3.9:1 on white - use for icons, not text
    static let statBlue = Color.blue

    /// Color for "Average IQ" stat
    /// - Warning: Light mode contrast 2.6:1 on white - use for icons, not text
    static let statGreen = Color.green

    /// Color for "Best Score" stat
    /// - Warning: Light mode contrast 2.3:1 on white - use for icons, not text
    static let statOrange = Color.orange

    /// Color for time/duration stats (purple is safe for normal text in light mode)
    static let statPurple = Color.purple

    // MARK: - Performance Level Colors

    // Note: In light mode, use these colors for icons/indicators only, with textPrimary for labels

    /// Color for excellent performance (>= 90th percentile)
    /// - Warning: Light mode contrast 2.6:1 on white - use for icons only
    static let performanceExcellent = Color.green

    /// Color for good performance (75-90th percentile)
    /// - Warning: Light mode contrast 2.3:1 on white - use for icons only
    static let performanceGood = Color.teal

    /// Color for average performance (50-75th percentile)
    /// - Warning: Light mode contrast 3.9:1 on white - large text only (>= 18pt)
    static let performanceAverage = Color.blue

    /// Color for below average performance (25-50th percentile)
    /// - Warning: Light mode contrast 2.3:1 on white - use for icons only
    static let performanceBelowAverage = Color.orange

    /// Color for needs work performance (< 25th percentile)
    /// - Warning: Light mode contrast 4.0:1 on white - large text only (>= 18pt)
    static let performanceNeedsWork = Color.red
}
