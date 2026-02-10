import SwiftUI

/// Centralized design system for consistent UI elements
/// Provides standardized spacing, corner radius, shadows, and other design tokens
enum DesignSystem {
    // MARK: - Spacing

    enum Spacing {
        /// Extra small spacing (4pt)
        static let xs: CGFloat = 4

        /// Small spacing (8pt)
        static let sm: CGFloat = 8

        /// Medium spacing (12pt)
        static let md: CGFloat = 12

        /// Large spacing (16pt)
        static let lg: CGFloat = 16

        /// Extra large spacing (20pt)
        static let xl: CGFloat = 20

        /// 2X large spacing (24pt)
        static let xxl: CGFloat = 24

        /// 3X large spacing (32pt)
        static let xxxl: CGFloat = 32

        /// 4X large spacing (40pt)
        static let huge: CGFloat = 40

        /// Section spacing (60pt) - for major sections
        static let section: CGFloat = 60
    }

    // MARK: - Corner Radius

    enum CornerRadius {
        /// Small corner radius (8pt)
        static let sm: CGFloat = 8

        /// Medium corner radius (12pt)
        static let md: CGFloat = 12

        /// Large corner radius (16pt)
        static let lg: CGFloat = 16

        /// Extra large corner radius (20pt)
        static let xl: CGFloat = 20

        /// Full corner radius (for circular elements)
        static let full: CGFloat = 9999
    }

    // MARK: - Shadows

    enum Shadow {
        /// Small shadow for subtle elevation
        static let sm = ShadowStyle(
            color: Color.black.opacity(0.05),
            radius: 4,
            x: 0,
            y: 1
        )

        /// Medium shadow for cards
        static let md = ShadowStyle(
            color: Color.black.opacity(0.08),
            radius: 8,
            x: 0,
            y: 2
        )

        /// Large shadow for prominent elements
        static let lg = ShadowStyle(
            color: Color.black.opacity(0.12),
            radius: 16,
            x: 0,
            y: 4
        )
    }

    // MARK: - Animation

    enum Animation {
        /// Quick spring animation for small UI changes
        static let quick = SwiftUI.Animation.spring(response: 0.3, dampingFraction: 0.7)

        /// Standard spring animation for most interactions
        static let standard = SwiftUI.Animation.spring(response: 0.5, dampingFraction: 0.7)

        /// Smooth spring animation for larger movements
        static let smooth = SwiftUI.Animation.spring(response: 0.6, dampingFraction: 0.7)

        /// Bouncy animation for playful interactions
        static let bouncy = SwiftUI.Animation.spring(response: 0.6, dampingFraction: 0.6)
    }

    // MARK: - Animation Delay

    enum AnimationDelay {
        /// Short delay (0.2s) for staggered element entrance
        static let short: Double = 0.2

        /// Medium delay (0.4s) for secondary element entrance
        static let medium: Double = 0.4

        /// Medium-long delay (0.5s) for tertiary element entrance
        static let mediumLong: Double = 0.5

        /// Long delay (0.6s) for delayed element entrance
        static let long: Double = 0.6

        /// Extra long delay (0.8s) for final element entrance
        static let extraLong: Double = 0.8
    }

    // MARK: - Icon Sizes

    enum IconSize {
        /// Small icon size (16pt)
        static let sm: CGFloat = 16

        /// Medium icon size (24pt)
        static let md: CGFloat = 24

        /// Large icon size (32pt)
        static let lg: CGFloat = 32

        /// Extra large icon size (48pt)
        static let xl: CGFloat = 48

        /// Huge icon size (64pt) - for empty states, etc.
        static let huge: CGFloat = 64
    }
}

// MARK: - Shadow Style

/// A custom shadow configuration
struct ShadowStyle {
    let color: Color
    let radius: CGFloat
    let x: CGFloat
    let y: CGFloat
}

// MARK: - View Extensions for Design System

extension View {
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

    /// Apply standard padding based on design system
    /// - Parameter size: The padding size (xs, sm, md, lg, xl, xxl, xxxl)
    func padding(_: DesignSystem.Spacing.Type) -> some View {
        padding(DesignSystem.Spacing.md)
    }
}
