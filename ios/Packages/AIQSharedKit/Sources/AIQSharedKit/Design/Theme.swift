import SwiftUI

// MARK: - Color Tokens

/// Semantic color tokens available for theming
public struct ColorTokens {
    /// Brand
    /// Primary brand color
    public let primary: Color
    /// Secondary brand color
    public let secondary: Color

    /// Semantic (icon use; low contrast in light mode — use accessible text variants for text)
    /// Success state color (icon use; low contrast on white — use successText for text)
    public let success: Color
    /// Warning state color (icon use; low contrast on white — use warningText for text)
    public let warning: Color
    /// Error state color (icon use; low contrast on white — use errorText for text)
    public let error: Color
    /// Info state color (icon use; low contrast on white — use infoText for text)
    public let info: Color

    /// Accessible text variants (WCAG AA compliant; use for text, not icons)
    /// WCAG AA–compliant success text color
    public let successText: Color
    /// WCAG AA–compliant warning text color
    public let warningText: Color
    /// WCAG AA–compliant error text color
    public let errorText: Color
    /// WCAG AA–compliant info text color
    public let infoText: Color

    /// Text
    /// Primary text color
    public let textPrimary: Color
    /// Secondary text color
    public let textSecondary: Color
    /// Tertiary / disabled text color
    public let textTertiary: Color

    /// Background
    /// Primary background color
    public let background: Color
    /// Secondary background (cards, elevated surfaces)
    public let backgroundSecondary: Color
    /// Tertiary background
    public let backgroundTertiary: Color
    /// Grouped-list background (mirrors UIColor.systemGroupedBackground)
    public let backgroundGrouped: Color

    /// Stats (icon use; low contrast on white — do not use for text)
    /// Stat color for tests-taken / correct-count metrics (blue)
    public let statBlue: Color
    /// Stat color for accuracy metrics (green)
    public let statGreen: Color
    /// Stat color for percentile / duration metrics (purple)
    public let statPurple: Color
    /// Stat color for time metrics (orange)
    public let statOrange: Color

    /// Creates a ColorTokens instance
    public init(
        primary: Color,
        secondary: Color,
        success: Color,
        warning: Color,
        error: Color,
        info: Color,
        successText: Color,
        warningText: Color,
        errorText: Color,
        infoText: Color,
        textPrimary: Color,
        textSecondary: Color,
        textTertiary: Color,
        background: Color,
        backgroundSecondary: Color,
        backgroundTertiary: Color,
        backgroundGrouped: Color,
        statBlue: Color,
        statGreen: Color,
        statPurple: Color,
        statOrange: Color
    ) {
        self.primary = primary
        self.secondary = secondary
        self.success = success
        self.warning = warning
        self.error = error
        self.info = info
        self.successText = successText
        self.warningText = warningText
        self.errorText = errorText
        self.infoText = infoText
        self.textPrimary = textPrimary
        self.textSecondary = textSecondary
        self.textTertiary = textTertiary
        self.background = background
        self.backgroundSecondary = backgroundSecondary
        self.backgroundTertiary = backgroundTertiary
        self.backgroundGrouped = backgroundGrouped
        self.statBlue = statBlue
        self.statGreen = statGreen
        self.statPurple = statPurple
        self.statOrange = statOrange
    }
}

// MARK: - Typography Tokens

/// Typography tokens mirroring the Typography enum
public struct TypographyTokens {
    /// Heading 1 font
    public let h1: Font
    /// Heading 2 font
    public let h2: Font
    /// Heading 3 font
    public let h3: Font
    /// Heading 4 font
    public let h4: Font
    /// Large body font
    public let bodyLarge: Font
    /// Medium body font
    public let bodyMedium: Font
    /// Small body font
    public let bodySmall: Font
    /// Large label font
    public let labelLarge: Font
    /// Medium label font
    public let labelMedium: Font
    /// Small label font
    public let labelSmall: Font
    /// Large caption font
    public let captionLarge: Font
    /// Medium caption font
    public let captionMedium: Font
    /// Small caption font
    public let captionSmall: Font
    /// Stat value display font
    public let statValue: Font
    /// Button label font
    public let button: Font

    /// Creates a TypographyTokens instance
    public init(
        h1: Font,
        h2: Font,
        h3: Font,
        h4: Font,
        bodyLarge: Font,
        bodyMedium: Font,
        bodySmall: Font,
        labelLarge: Font,
        labelMedium: Font,
        labelSmall: Font,
        captionLarge: Font,
        captionMedium: Font,
        captionSmall: Font,
        statValue: Font,
        button: Font
    ) {
        self.h1 = h1
        self.h2 = h2
        self.h3 = h3
        self.h4 = h4
        self.bodyLarge = bodyLarge
        self.bodyMedium = bodyMedium
        self.bodySmall = bodySmall
        self.labelLarge = labelLarge
        self.labelMedium = labelMedium
        self.labelSmall = labelSmall
        self.captionLarge = captionLarge
        self.captionMedium = captionMedium
        self.captionSmall = captionSmall
        self.statValue = statValue
        self.button = button
    }
}

// MARK: - Spacing Tokens

/// Spacing tokens mirroring DesignSystem.Spacing
public struct SpacingTokens {
    /// Extra-small spacing
    public let xs: CGFloat
    /// Small spacing
    public let sm: CGFloat
    /// Medium spacing
    public let md: CGFloat
    /// Large spacing
    public let lg: CGFloat
    /// Extra-large spacing
    public let xl: CGFloat
    /// 2× extra-large spacing
    public let xxl: CGFloat
    /// 3× extra-large spacing
    public let xxxl: CGFloat
    /// Huge spacing
    public let huge: CGFloat
    /// Section-level spacing
    public let section: CGFloat

    /// Creates a SpacingTokens instance
    public init(
        xs: CGFloat,
        sm: CGFloat,
        md: CGFloat,
        lg: CGFloat,
        xl: CGFloat,
        xxl: CGFloat,
        xxxl: CGFloat,
        huge: CGFloat,
        section: CGFloat
    ) {
        self.xs = xs
        self.sm = sm
        self.md = md
        self.lg = lg
        self.xl = xl
        self.xxl = xxl
        self.xxxl = xxxl
        self.huge = huge
        self.section = section
    }
}

// MARK: - Corner Radius Tokens

/// Corner radius tokens mirroring DesignSystem.CornerRadius
public struct CornerRadiusTokens {
    /// Small corner radius
    public let sm: CGFloat
    /// Medium corner radius
    public let md: CGFloat
    /// Large corner radius
    public let lg: CGFloat
    /// Extra-large corner radius
    public let xl: CGFloat
    /// Full (pill) corner radius
    public let full: CGFloat

    /// Creates a CornerRadiusTokens instance
    public init(sm: CGFloat, md: CGFloat, lg: CGFloat, xl: CGFloat, full: CGFloat) {
        self.sm = sm
        self.md = md
        self.lg = lg
        self.xl = xl
        self.full = full
    }
}

// MARK: - Shadow Tokens

/// Shadow tokens mirroring DesignSystem.Shadow
public struct ShadowTokens {
    /// Small shadow
    public let sm: ShadowStyle
    /// Medium shadow
    public let md: ShadowStyle
    /// Large shadow
    public let lg: ShadowStyle

    /// Creates a ShadowTokens instance
    public init(sm: ShadowStyle, md: ShadowStyle, lg: ShadowStyle) {
        self.sm = sm
        self.md = md
        self.lg = lg
    }
}

// MARK: - Icon Size Tokens

/// Icon size tokens mirroring DesignSystem.IconSize
public struct IconSizeTokens {
    /// Small icon size
    public let sm: CGFloat
    /// Medium icon size
    public let md: CGFloat
    /// Large icon size
    public let lg: CGFloat
    /// Extra-large icon size
    public let xl: CGFloat
    /// Huge icon size
    public let huge: CGFloat

    /// Creates an IconSizeTokens instance
    public init(sm: CGFloat, md: CGFloat, lg: CGFloat, xl: CGFloat, huge: CGFloat) {
        self.sm = sm
        self.md = md
        self.lg = lg
        self.xl = xl
        self.huge = huge
    }
}

// MARK: - Animation Tokens

/// Animation tokens mirroring DesignSystem.Animation
public struct AnimationTokens {
    /// Quick animation curve
    public let quick: Animation
    /// Standard animation curve
    public let standard: Animation
    /// Smooth animation curve
    public let smooth: Animation
    /// Bouncy animation curve
    public let bouncy: Animation

    /// Creates an AnimationTokens instance
    public init(quick: Animation, standard: Animation, smooth: Animation, bouncy: Animation) {
        self.quick = quick
        self.standard = standard
        self.smooth = smooth
        self.bouncy = bouncy
    }
}

// MARK: - Gradient Tokens

/// Gradient tokens for branded gradient fills
public struct GradientTokens {
    /// Blue-to-purple gradient used for IQ score display and hero UI
    public let scoreGradient: LinearGradient
    /// Yellow-to-orange gradient used for trophy and achievement icons
    public let trophyGradient: LinearGradient

    /// Creates a GradientTokens instance
    public init(scoreGradient: LinearGradient, trophyGradient: LinearGradient) {
        self.scoreGradient = scoreGradient
        self.trophyGradient = trophyGradient
    }
}

// MARK: - AnimationDelay — intentionally NOT tokenized

//
// DesignSystem.AnimationDelay (short/medium/mediumLong/long/extraLong) defines entrance-sequence
// stagger timings used as: theme.animations.smooth.delay(DesignSystem.AnimationDelay.medium).
//
// These are NOT added to AppThemeProtocol as AnimationDelayTokens because:
//   1. They are plain Double timing constants, not visual design tokens.
//   2. The hybrid pattern is semantically correct — the animation style is theme-driven,
//      but the delay is view-choreography logic that belongs with the view.
//   3. A future theme would never need different stagger delays.

// MARK: - AppThemeProtocol

/// Protocol for app-wide visual theming. Conforming types supply typed token groups
/// that components read via @Environment(\.appTheme). Enables future theme variants
/// (high-contrast, seasonal, white-label) without touching component internals.
public protocol AppThemeProtocol {
    /// Semantic color tokens
    var colors: ColorTokens { get }
    /// Gradient tokens
    var gradients: GradientTokens { get }
    /// Typography tokens
    var typography: TypographyTokens { get }
    /// Spacing tokens
    var spacing: SpacingTokens { get }
    /// Corner radius tokens
    var cornerRadius: CornerRadiusTokens { get }
    /// Shadow tokens
    var shadows: ShadowTokens { get }
    /// Icon size tokens
    var iconSizes: IconSizeTokens { get }
    /// Animation tokens
    var animations: AnimationTokens { get }
}

// MARK: - DefaultTheme

/// Default theme that delegates to existing ColorPalette, Typography, and DesignSystem.
/// No visual values change — this is a thin wrapper enabling the theme environment.
public struct DefaultTheme: AppThemeProtocol {
    /// Creates a DefaultTheme instance
    public init() {}

    /// Semantic color tokens
    public let colors = ColorTokens(
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
        backgroundTertiary: ColorPalette.backgroundTertiary,
        backgroundGrouped: ColorPalette.backgroundGrouped,
        statBlue: ColorPalette.statBlue,
        statGreen: ColorPalette.statGreen,
        statPurple: ColorPalette.statPurple,
        statOrange: ColorPalette.statOrange
    )

    /// Gradient tokens
    public let gradients = GradientTokens(
        scoreGradient: ColorPalette.scoreGradient,
        trophyGradient: ColorPalette.trophyGradient
    )

    /// Typography tokens
    public let typography = TypographyTokens(
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

    /// Spacing tokens
    public let spacing = SpacingTokens(
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

    /// Corner radius tokens
    public let cornerRadius = CornerRadiusTokens(
        sm: DesignSystem.CornerRadius.sm,
        md: DesignSystem.CornerRadius.md,
        lg: DesignSystem.CornerRadius.lg,
        xl: DesignSystem.CornerRadius.xl,
        full: DesignSystem.CornerRadius.full
    )

    /// Shadow tokens
    public let shadows = ShadowTokens(
        sm: DesignSystem.Shadow.sm,
        md: DesignSystem.Shadow.md,
        lg: DesignSystem.Shadow.lg
    )

    /// Icon size tokens
    public let iconSizes = IconSizeTokens(
        sm: DesignSystem.IconSize.sm,
        md: DesignSystem.IconSize.md,
        lg: DesignSystem.IconSize.lg,
        xl: DesignSystem.IconSize.xl,
        huge: DesignSystem.IconSize.huge
    )

    /// Animation tokens
    public let animations = AnimationTokens(
        quick: DesignSystem.Animation.quick,
        standard: DesignSystem.Animation.standard,
        smooth: DesignSystem.Animation.smooth,
        bouncy: DesignSystem.Animation.bouncy
    )
}
