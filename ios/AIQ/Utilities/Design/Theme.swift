import SwiftUI

// MARK: - Color Tokens

/// Semantic color tokens available for theming
struct ColorTokens {
    // Brand
    let primary: Color
    let secondary: Color

    // Semantic (icon use; low contrast in light mode — use accessible text variants for text)
    let success: Color
    let warning: Color
    let error: Color
    let info: Color

    // Accessible text variants (WCAG AA compliant; use for text, not icons)
    let successText: Color
    let warningText: Color
    let errorText: Color
    let infoText: Color

    // Text
    let textPrimary: Color
    let textSecondary: Color
    let textTertiary: Color

    // Background
    let background: Color
    let backgroundSecondary: Color
    let backgroundTertiary: Color
}

// MARK: - Typography Tokens

/// Typography tokens mirroring the Typography enum
struct TypographyTokens {
    let h1: Font
    let h2: Font
    let h3: Font
    let h4: Font
    let bodyLarge: Font
    let bodyMedium: Font
    let bodySmall: Font
    let labelLarge: Font
    let labelMedium: Font
    let labelSmall: Font
    let captionLarge: Font
    let captionMedium: Font
    let captionSmall: Font
    let statValue: Font
    let button: Font
}

// MARK: - Spacing Tokens

/// Spacing tokens mirroring DesignSystem.Spacing
struct SpacingTokens {
    let xs: CGFloat
    let sm: CGFloat
    let md: CGFloat
    let lg: CGFloat
    let xl: CGFloat
    let xxl: CGFloat
    let xxxl: CGFloat
    let huge: CGFloat
    let section: CGFloat
}

// MARK: - Corner Radius Tokens

/// Corner radius tokens mirroring DesignSystem.CornerRadius
struct CornerRadiusTokens {
    let sm: CGFloat
    let md: CGFloat
    let lg: CGFloat
    let xl: CGFloat
    let full: CGFloat
}

// MARK: - Shadow Tokens

/// Shadow tokens mirroring DesignSystem.Shadow
struct ShadowTokens {
    let sm: ShadowStyle
    let md: ShadowStyle
    let lg: ShadowStyle
}

// MARK: - AppThemeProtocol

/// Protocol for app-wide visual theming. Conforming types supply typed token groups
/// that components read via @Environment(\.appTheme). Enables future theme variants
/// (high-contrast, seasonal, white-label) without touching component internals.
protocol AppThemeProtocol {
    var colors: ColorTokens { get }
    var typography: TypographyTokens { get }
    var spacing: SpacingTokens { get }
    var cornerRadius: CornerRadiusTokens { get }
    var shadows: ShadowTokens { get }
}

// MARK: - DefaultTheme

/// Default theme that delegates to existing ColorPalette, Typography, and DesignSystem.
/// No visual values change — this is a thin wrapper enabling the theme environment.
struct DefaultTheme: AppThemeProtocol {
    let colors = ColorTokens(
        primary: ColorPalette.primary,
        secondary: ColorPalette.secondary,
        success: ColorPalette.success,
        warning: ColorPalette.warning,
        error: ColorPalette.error,
        info: ColorPalette.info,
        successText: ColorPalette.successText,
        warningText: ColorPalette.warningText,
        errorText: ColorPalette.errorText,
        infoText: ColorPalette.infoText,
        textPrimary: ColorPalette.textPrimary,
        textSecondary: ColorPalette.textSecondary,
        textTertiary: ColorPalette.textTertiary,
        background: ColorPalette.background,
        backgroundSecondary: ColorPalette.backgroundSecondary,
        backgroundTertiary: ColorPalette.backgroundTertiary
    )

    let typography = TypographyTokens(
        h1: Typography.h1,
        h2: Typography.h2,
        h3: Typography.h3,
        h4: Typography.h4,
        bodyLarge: Typography.bodyLarge,
        bodyMedium: Typography.bodyMedium,
        bodySmall: Typography.bodySmall,
        labelLarge: Typography.labelLarge,
        labelMedium: Typography.labelMedium,
        labelSmall: Typography.labelSmall,
        captionLarge: Typography.captionLarge,
        captionMedium: Typography.captionMedium,
        captionSmall: Typography.captionSmall,
        statValue: Typography.statValue,
        button: Typography.button
    )

    let spacing = SpacingTokens(
        xs: DesignSystem.Spacing.xs,
        sm: DesignSystem.Spacing.sm,
        md: DesignSystem.Spacing.md,
        lg: DesignSystem.Spacing.lg,
        xl: DesignSystem.Spacing.xl,
        xxl: DesignSystem.Spacing.xxl,
        xxxl: DesignSystem.Spacing.xxxl,
        huge: DesignSystem.Spacing.huge,
        section: DesignSystem.Spacing.section
    )

    let cornerRadius = CornerRadiusTokens(
        sm: DesignSystem.CornerRadius.sm,
        md: DesignSystem.CornerRadius.md,
        lg: DesignSystem.CornerRadius.lg,
        xl: DesignSystem.CornerRadius.xl,
        full: DesignSystem.CornerRadius.full
    )

    let shadows = ShadowTokens(
        sm: DesignSystem.Shadow.sm,
        md: DesignSystem.Shadow.md,
        lg: DesignSystem.Shadow.lg
    )
}
