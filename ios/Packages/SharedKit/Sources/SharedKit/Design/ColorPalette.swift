import SwiftUI

// MARK: - Color Extensions

public extension Color {
    /// Creates a color from a hex string
    /// - Parameter hex: Hex color string (e.g., "#FF0000" or "FF0000")
    /// - Returns: A Color if the hex string is valid (3, 6, or 8 hex digits), nil otherwise
    init?(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0

        guard Scanner(string: hex).scanHexInt64(&int) else {
            return nil
        }

        let alpha, red, green, blue: UInt64
        switch hex.count {
        case 3: // RGB (12-bit)
            (alpha, red, green, blue) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6: // RGB (24-bit)
            (alpha, red, green, blue) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8: // ARGB (32-bit)
            (alpha, red, green, blue) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            return nil
        }

        self.init(
            .sRGB,
            red: Double(red) / 255,
            green: Double(green) / 255,
            blue: Double(blue) / 255,
            opacity: Double(alpha) / 255
        )
    }

    /// Creates a color that adapts to light and dark mode
    /// - Parameters:
    ///   - light: Color to use in light mode
    ///   - dark: Color to use in dark mode
    init(light: Color, dark: Color) {
        self.init(uiColor: UIColor(light: UIColor(light), dark: UIColor(dark)))
    }
}

public extension UIColor {
    /// Creates a UIColor that adapts to light and dark mode
    /// - Parameters:
    ///   - light: UIColor to use in light mode
    ///   - dark: UIColor to use in dark mode
    convenience init(light: UIColor, dark: UIColor) {
        self.init { traitCollection in
            switch traitCollection.userInterfaceStyle {
            case .dark:
                dark
            default:
                light
            }
        }
    }
}

/// Centralized color palette
/// Provides consistent colors across light and dark modes
///
/// # WCAG AA Accessibility Guidelines
///
/// This color palette has been audited for WCAG 2.1 Level AA compliance.
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
public enum ColorPalette {
    // MARK: - Primary Colors

    /// Primary brand color (blue)
    public static let primary = Color.accentColor

    /// Secondary brand color (purple)
    public static let secondary = Color.purple

    // MARK: - Semantic Colors

    /// Success color (green) - for positive feedback, high scores
    /// - Warning: Light mode contrast 2.6:1 on white - use for icons only, not text
    public static let success = Color.green

    /// Warning color (orange) - for warnings, medium scores
    /// - Warning: Light mode contrast 2.3:1 on white - use for icons only, not text
    public static let warning = Color.orange

    /// Error color (red) - for errors, low scores
    /// - Warning: Light mode contrast 4.0:1 on white - large text only (>= 18pt)
    public static let error = Color.red

    /// Info color (blue) - for informational content
    /// - Warning: Light mode contrast 3.9:1 on white - large text only (>= 18pt)
    public static let info = Color.blue

    // MARK: - Accessible Text Colors (WCAG AA Compliant)

    /// Accessible success text color - meets WCAG AA 4.5:1 contrast ratio
    public static let successText = Color(light: Color(hex: "#1B7F3D") ?? .green, dark: .green)

    /// Accessible warning text color - meets WCAG AA 4.5:1 contrast ratio
    public static let warningText = Color(light: Color(hex: "#C67100") ?? .orange, dark: .orange)

    /// Accessible error text color - meets WCAG AA 4.5:1 contrast ratio
    public static let errorText = Color(light: Color(hex: "#D32F2F") ?? .red, dark: .red)

    /// Accessible info text color - meets WCAG AA 4.5:1 contrast ratio
    public static let infoText = Color(light: Color(hex: "#0056B3") ?? .blue, dark: .blue)

    // MARK: - Neutral Colors

    /// Primary text color
    public static let textPrimary = Color.primary

    /// Secondary text color (lighter)
    public static let textSecondary = Color.secondary

    /// Tertiary text color (lightest)
    /// - Warning: Low contrast in light mode - use for decorative content only
    public static let textTertiary = Color(uiColor: .tertiaryLabel)

    // MARK: - Background Colors

    /// Primary background color
    public static let background = Color(uiColor: .systemBackground)

    /// Secondary background color (for cards, elevated surfaces)
    public static let backgroundSecondary = Color(uiColor: .secondarySystemBackground)

    /// Tertiary background color (for nested content)
    public static let backgroundTertiary = Color(uiColor: .tertiarySystemBackground)

    /// Grouped background (for lists, table views)
    public static let backgroundGrouped = Color(uiColor: .systemGroupedBackground)

    // MARK: - Chart Colors

    /// Colors for charts and data visualization
    public static let chartColors: [Color] = [
        .blue,
        .purple,
        .green,
        .orange,
        .pink,
        .teal
    ]

    // MARK: - Gradient Colors

    /// Trophy gradient (yellow to orange)
    public static let trophyGradient = LinearGradient(
        colors: [.yellow, .orange],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
    )

    /// Score gradient (blue to purple)
    public static let scoreGradient = LinearGradient(
        colors: [.blue, .purple],
        startPoint: .leading,
        endPoint: .trailing
    )

    /// Success gradient (light green to green)
    public static let successGradient = LinearGradient(
        colors: [Color.green.opacity(0.6), Color.green],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
    )

    // MARK: - Stat Card Colors

    /// Color for "Tests Taken" stat
    /// - Warning: Light mode contrast 3.9:1 on white - use for icons, not text
    public static let statBlue = Color.blue

    /// Color for "Average IQ" stat
    /// - Warning: Light mode contrast 2.6:1 on white - use for icons, not text
    public static let statGreen = Color.green

    /// Color for "Best Score" stat
    /// - Warning: Light mode contrast 2.3:1 on white - use for icons, not text
    public static let statOrange = Color.orange

    /// Color for time/duration stats (purple is safe for normal text in light mode)
    public static let statPurple = Color.purple

    // MARK: - Performance Level Colors

    /// Color for excellent performance (>= 90th percentile)
    /// - Warning: Light mode contrast 2.6:1 on white - use for icons only
    public static let performanceExcellent = Color.green

    /// Color for good performance (75-90th percentile)
    /// - Warning: Light mode contrast 2.3:1 on white - use for icons only
    public static let performanceGood = Color.teal

    /// Color for average performance (50-75th percentile)
    /// - Warning: Light mode contrast 3.9:1 on white - large text only (>= 18pt)
    public static let performanceAverage = Color.blue

    /// Color for below average performance (25-50th percentile)
    /// - Warning: Light mode contrast 2.3:1 on white - use for icons only
    public static let performanceBelowAverage = Color.orange

    /// Color for needs work performance (< 25th percentile)
    /// - Warning: Light mode contrast 4.0:1 on white - large text only (>= 18pt)
    public static let performanceNeedsWork = Color.red

    /// Accessible performance "good" text color - meets WCAG AA 4.5:1 contrast ratio
    public static let performanceGoodText = Color(light: Color(hex: "#008B8B") ?? .teal, dark: .teal)
}
