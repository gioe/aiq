import SwiftUI

/// A full-screen loading overlay with animated spinner and optional message
public struct LoadingOverlay: View {
    public let message: String?
    @State private var isAnimating = false
    @State private var rotationAngle: Double = 0
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @Environment(\.appTheme) private var theme

    public init(message: String? = nil) {
        self.message = message
    }

    public var body: some View {
        ZStack {
            // Semi-transparent backdrop
            theme.colors.background
                .opacity(0.8)
                .ignoresSafeArea()

            // Loading card
            VStack(spacing: theme.spacing.xl) {
                // Animated brain icon
                Image(systemName: "brain.head.profile")
                    .font(.system(size: 48))
                    .foregroundStyle(ColorPalette.scoreGradient)
                    .rotationEffect(.degrees(rotationAngle))
                    .scaleEffect(reduceMotion ? 1.0 : (isAnimating ? 1.1 : 1.0))
                    .accessibilityHidden(true)

                if let message {
                    Text(message)
                        .font(theme.typography.bodyLarge)
                        .foregroundColor(theme.colors.textPrimary)
                        .multilineTextAlignment(.center)
                        .opacity(isAnimating ? 1.0 : 0.0)
                }
            }
            .padding(theme.spacing.xxxl)
            .background(
                RoundedRectangle(cornerRadius: theme.cornerRadius.xl)
                    .fill(theme.colors.backgroundSecondary)
                    .shadowStyle(theme.shadows.lg)
            )
            .scaleEffect(isAnimating ? 1.0 : 0.85)
            .opacity(isAnimating ? 1.0 : 0.0)
            .accessibilityElement(children: .combine)
            .accessibilityLabel(message ?? "Loading")
            .accessibilityIdentifier("loadingOverlay.container")
        }
        .onAppear {
            // Entrance animation
            if reduceMotion {
                isAnimating = true
            } else {
                withAnimation(theme.animations.smooth) {
                    isAnimating = true
                }
            }

            // Continuous rotation animation - disabled when Reduce Motion is enabled
            if !reduceMotion {
                withAnimation(
                    Animation.linear(duration: 2.0)
                        .repeatForever(autoreverses: false)
                ) {
                    rotationAngle = 360
                }
            }
        }
    }
}

#Preview {
    ZStack {
        ColorPalette.background
            .ignoresSafeArea()

        LoadingOverlay(message: "Signing in...")
    }
}
