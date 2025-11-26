import SwiftUI

/// A full-screen loading overlay with animated spinner and optional message
struct LoadingOverlay: View {
    let message: String?
    @State private var isAnimating = false
    @State private var rotationAngle: Double = 0

    init(message: String? = nil) {
        self.message = message
    }

    var body: some View {
        ZStack {
            // Semi-transparent backdrop
            ColorPalette.backgroundPrimary
                .opacity(0.8)
                .ignoresSafeArea()

            // Loading card
            VStack(spacing: DesignSystem.Spacing.xl) {
                // Animated brain icon
                Image(systemName: "brain.head.profile")
                    .font(.system(size: 48))
                    .foregroundStyle(ColorPalette.scoreGradient)
                    .rotationEffect(.degrees(rotationAngle))
                    .scaleEffect(isAnimating ? 1.1 : 1.0)

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
        }
        .onAppear {
            // Entrance animation
            withAnimation(DesignSystem.Animation.smooth) {
                isAnimating = true
            }

            // Continuous rotation animation
            withAnimation(
                Animation.linear(duration: 2.0)
                    .repeatForever(autoreverses: false)
            ) {
                rotationAngle = 360
            }
        }
    }
}

#Preview {
    ZStack {
        ColorPalette.backgroundPrimary
            .ignoresSafeArea()

        LoadingOverlay(message: "Signing in...")
    }
}
