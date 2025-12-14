import SwiftUI

/// Centralized color palette for the AIQ app
/// Provides consistent colors across light and dark modes
enum ColorPalette {
    // MARK: - Primary Colors

    /// Primary brand color (blue)
    static let primary = Color.accentColor

    /// Secondary brand color (purple)
    static let secondary = Color.purple

    // MARK: - Semantic Colors

    /// Success color (green) - for positive feedback, high scores
    static let success = Color.green

    /// Warning color (orange) - for warnings, medium scores
    static let warning = Color.orange

    /// Error color (red) - for errors, low scores
    static let error = Color.red

    /// Info color (blue) - for informational content
    static let info = Color.blue

    // MARK: - Neutral Colors

    /// Primary text color
    static let textPrimary = Color.primary

    /// Secondary text color (lighter)
    static let textSecondary = Color.secondary

    /// Tertiary text color (lightest)
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

    /// Color for "Tests Taken" stat
    static let statBlue = Color.blue

    /// Color for "Average IQ" stat
    static let statGreen = Color.green

    /// Color for "Best Score" stat
    static let statOrange = Color.orange

    /// Color for time/duration stats
    static let statPurple = Color.purple

    // MARK: - Performance Level Colors

    /// Color for excellent performance (>= 90th percentile)
    static let performanceExcellent = Color.green

    /// Color for good performance (75-90th percentile)
    static let performanceGood = Color.teal

    /// Color for average performance (50-75th percentile)
    static let performanceAverage = Color.blue

    /// Color for below average performance (25-50th percentile)
    static let performanceBelowAverage = Color.orange

    /// Color for needs work performance (< 25th percentile)
    static let performanceNeedsWork = Color.red
}
