import SwiftUI

// MARK: - Welcome Header

struct DashboardWelcomeHeader: View {
    let userName: String?

    var body: some View {
        VStack(spacing: DesignSystem.Spacing.md) {
            // Greeting with time-based context
            HStack(spacing: DesignSystem.Spacing.xs) {
                Image(systemName: greetingIcon)
                    .font(.system(size: DesignSystem.IconSize.lg))
                    .foregroundStyle(
                        LinearGradient(
                            colors: [ColorPalette.primary, ColorPalette.primary.opacity(0.7)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )

                if let userName {
                    Text("\(greetingText), \(userName)!")
                        .font(Typography.h1)
                        .foregroundStyle(
                            LinearGradient(
                                colors: [ColorPalette.textPrimary, ColorPalette.textSecondary],
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                        )
                } else {
                    Text("\(greetingText)!")
                        .font(Typography.h1)
                        .foregroundColor(ColorPalette.textPrimary)
                }
            }

            Text("Track your cognitive performance over time")
                .font(Typography.bodyMedium)
                .foregroundColor(ColorPalette.textSecondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, DesignSystem.Spacing.lg)
    }

    /// Time-based greeting
    private var greetingText: String {
        let hour = Calendar.current.component(.hour, from: Date())
        switch hour {
        case 0 ..< 12: return "Good morning"
        case 12 ..< 17: return "Good afternoon"
        default: return "Good evening"
        }
    }

    private var greetingIcon: String {
        let hour = Calendar.current.component(.hour, from: Date())
        switch hour {
        case 0 ..< 12: return "sunrise.fill"
        case 12 ..< 17: return "sun.max.fill"
        default: return "moon.stars.fill"
        }
    }
}

#Preview {
    VStack(spacing: 24) {
        DashboardWelcomeHeader(userName: "Alex")
        DashboardWelcomeHeader(userName: nil)
    }
    .padding()
}
