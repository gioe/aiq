import SwiftUI

/// Centralized design system for consistent UI elements
/// Provides standardized spacing, corner radius, shadows, and other design tokens
public enum DesignSystem {
    // MARK: - Spacing

    public enum Spacing {
        /// 2X extra small spacing (2pt)
        public static let xxs: CGFloat = 2

        /// Extra small spacing (4pt)
        public static let xs: CGFloat = 4

        /// Small spacing (8pt)
        public static let sm: CGFloat = 8

        /// Medium spacing (12pt)
        public static let md: CGFloat = 12

        /// Large spacing (16pt)
        public static let lg: CGFloat = 16

        /// Extra large spacing (20pt)
        public static let xl: CGFloat = 20

        /// 2X large spacing (24pt)
        public static let xxl: CGFloat = 24

        /// 3X large spacing (32pt)
        public static let xxxl: CGFloat = 32

        /// 4X large spacing (40pt)
        public static let huge: CGFloat = 40

        /// Section spacing (60pt) - for major sections
        public static let section: CGFloat = 60
    }

    // MARK: - Corner Radius

    public enum CornerRadius {
        /// Extra small corner radius (4pt)
        public static let xs: CGFloat = 4

        /// Small corner radius (8pt)
        public static let sm: CGFloat = 8

        /// Medium corner radius (12pt)
        public static let md: CGFloat = 12

        /// Large corner radius (16pt)
        public static let lg: CGFloat = 16

        /// Extra large corner radius (20pt)
        public static let xl: CGFloat = 20

        /// Full corner radius (for circular elements)
        public static let full: CGFloat = 9999
    }

    // MARK: - Shadows

    public enum Shadow {
        /// Small shadow for subtle elevation
        public static let sm = ShadowStyle(
            color: Color.black.opacity(0.05),
            radius: 4,
            x: 0,
            y: 1
        )

        /// Medium shadow for cards
        public static let md = ShadowStyle(
            color: Color.black.opacity(0.08),
            radius: 8,
            x: 0,
            y: 2
        )

        /// Large shadow for prominent elements
        public static let lg = ShadowStyle(
            color: Color.black.opacity(0.12),
            radius: 16,
            x: 0,
            y: 4
        )

        /// Subtle header bottom shadow for navigation/progress headers
        public static let header = ShadowStyle(
            color: Shadow.sm.color,
            radius: 2,
            x: 0,
            y: 1
        )
    }

    // MARK: - Animation

    public enum Animation {
        /// Quick spring animation for small UI changes
        public static let quick = SwiftUI.Animation.spring(response: 0.3, dampingFraction: 0.7)

        /// Standard spring animation for most interactions
        public static let standard = SwiftUI.Animation.spring(response: 0.5, dampingFraction: 0.7)

        /// Smooth spring animation for larger movements
        public static let smooth = SwiftUI.Animation.spring(response: 0.6, dampingFraction: 0.7)

        /// Bouncy animation for playful interactions
        public static let bouncy = SwiftUI.Animation.spring(response: 0.6, dampingFraction: 0.6)
    }

    // MARK: - Animation Delay

    public enum AnimationDelay {
        /// Short delay (0.2s) for staggered element entrance
        public static let short: Double = 0.2

        /// Medium delay (0.4s) for secondary element entrance
        public static let medium: Double = 0.4

        /// Medium-long delay (0.5s) for tertiary element entrance
        public static let mediumLong: Double = 0.5

        /// Long delay (0.6s) for delayed element entrance
        public static let long: Double = 0.6

        /// Extra long delay (0.8s) for final element entrance
        public static let extraLong: Double = 0.8
    }

    // MARK: - Icon Sizes

    public enum IconSize {
        /// Small icon size (16pt)
        public static let sm: CGFloat = 16

        /// Medium icon size (24pt)
        public static let md: CGFloat = 24

        /// Large icon size (32pt)
        public static let lg: CGFloat = 32

        /// Extra large icon size (48pt)
        public static let xl: CGFloat = 48

        /// Huge icon size (64pt) - for empty states, etc.
        public static let huge: CGFloat = 64
    }

    // MARK: - Adaptive Layout

    public enum Layout {
        /// Maximum readable content width for iPad and large displays (700pt)
        public static let readableContentWidth: CGFloat = 700
    }
}

// MARK: - Button Styles

/// Button style that scales down on press for tactile feedback
public struct ScaleButtonStyle: ButtonStyle {
    @Environment(\.accessibilityReduceMotion) var reduceMotion

    public init() {}

    public func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(reduceMotion ? 1.0 : (configuration.isPressed ? 0.95 : 1.0))
            .opacity(configuration.isPressed ? 0.8 : 1.0)
            .animation(reduceMotion ? nil : .easeInOut(duration: 0.1), value: configuration.isPressed)
    }
}

// MARK: - Shadow Style

/// A custom shadow configuration
public struct ShadowStyle {
    public let color: Color
    public let radius: CGFloat
    public let x: CGFloat
    public let y: CGFloat

    public init(color: Color, radius: CGFloat, x: CGFloat, y: CGFloat) {
        self.color = color
        self.radius = radius
        self.x = x
        self.y = y
    }
}

// MARK: - View Extensions for Design System

public extension View {
    /// Apply a card style with background, corner radius, and shadow
    /// - Parameters:
    ///   - cornerRadius: The corner radius to apply (default: medium)
    ///   - shadow: The shadow style to apply (default: medium)
    ///   - backgroundColor: The background color (default: secondary background)
    func cardStyle(
        cornerRadius: CGFloat = DesignSystem.CornerRadius.md,
        shadow: ShadowStyle = DesignSystem.Shadow.md,
        backgroundColor: Color = ColorPalette.backgroundSecondary
    ) -> some View {
        background(backgroundColor)
            .cornerRadius(cornerRadius)
            .shadow(color: shadow.color, radius: shadow.radius, x: shadow.x, y: shadow.y)
    }

    /// Apply a named shadow style from the design system
    func shadowStyle(_ style: ShadowStyle) -> some View {
        shadow(color: style.color, radius: style.radius, x: style.x, y: style.y)
    }

    /// Apply adaptive content width constraint for optimal readability on iPad
    func adaptiveContentWidth(maxWidth: CGFloat = DesignSystem.Layout.readableContentWidth) -> some View {
        modifier(AdaptiveContentWidthModifier(maxWidth: maxWidth))
    }
}

// MARK: - Adaptive Content Width Modifier

/// View modifier that constrains content width on iPad for better readability
private struct AdaptiveContentWidthModifier: ViewModifier {
    @Environment(\.horizontalSizeClass) var horizontalSizeClass
    let maxWidth: CGFloat

    func body(content: Content) -> some View {
        if horizontalSizeClass == .regular {
            // iPad: constrain width and center
            content
                .frame(maxWidth: maxWidth)
                .frame(maxWidth: .infinity) // Center within parent
        } else {
            // iPhone: use full width
            content
        }
    }
}
