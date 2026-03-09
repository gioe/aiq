import SwiftUI

/// A full-screen loading overlay with animated spinner and optional message
struct LoadingOverlay: View {
    let message: String?
    @State private var isAnimating = false
    @State private var rotationAngle: Double = 0
    @Environment(\.accessibilityReduceMotion) var reduceMotion

    init(message: String? = nil) {
        self.message = message
    }

    var body: some View {
        ZStack {
            // Semi-transparent backdrop
            ColorPalette.background
                .opacity(0.8)
                .ignoresSafeArea()

            // Loading card
            VStack(spacing: DesignSystem.Spacing.xl) {
                // Animated brain icon
                Image(systemName: "brain.head.profile")
                    .font(.system(size: 48))
                    .foregroundStyle(ColorPalette.scoreGradient)
                    .rotationEffect(.degrees(rotationAngle))
                    .scaleEffect(reduceMotion ? 1.0 : (isAnimating ? 1.1 : 1.0))
                    .accessibilityHidden(true)

                if let message {
                    Text(message)
                        .font(Typography.bodyLarge)
                        .foregroundColor(ColorPalette.textPrimary)
                        .multilineTextAlignment(.center)
                        .opacity(isAnimating ? 1.0 : 0.0)
                }
            }
            .padding(DesignSystem.Spacing.xxxl)
            .background(
                RoundedRectangle(cornerRadius: DesignSystem.CornerRadius.xl)
                    .fill(ColorPalette.backgroundSecondary)
                    .shadow(
                        color: DesignSystem.Shadow.lg.color,
                        radius: DesignSystem.Shadow.lg.radius,
                        x: DesignSystem.Shadow.lg.x,
                        y: DesignSystem.Shadow.lg.y
                    )
            )
            .scaleEffect(isAnimating ? 1.0 : 0.85)
            .opacity(isAnimating ? 1.0 : 0.0)
            .accessibilityElement(children: .combine)
            .accessibilityLabel(message ?? "Loading")
            .accessibilityIdentifier(AccessibilityIdentifiers.LoadingOverlay.container)
        }
        .onAppear {
            // Entrance animation
            if reduceMotion {
                isAnimating = true
            } else {
                withAnimation(DesignSystem.Animation.smooth) {
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
