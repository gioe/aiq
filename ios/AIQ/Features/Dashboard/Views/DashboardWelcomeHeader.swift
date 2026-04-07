import AIQSharedKit
import SwiftUI

// MARK: - Welcome Header

struct DashboardWelcomeHeader: View {
    let userName: String?

    @Environment(\.appTheme) private var theme

    var body: some View {
        VStack(spacing: DesignSystem.Spacing.md) {
            // Greeting with time-based context
            HStack(spacing: DesignSystem.Spacing.xs) {
                Image(systemName: greetingIcon)
                    .font(.system(size: theme.iconSizes.lg))
                    .foregroundStyle(
                        LinearGradient(
                            colors: [theme.colors.primary, theme.colors.primary.opacity(0.7)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )

                if let userName {
                    Text("\(greetingText), \(userName)!")
                        .font(theme.typography.h1)
                        .foregroundStyle(
                            LinearGradient(
                                colors: [theme.colors.textPrimary, theme.colors.textSecondary],
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                        )
                } else {
                    Text("\(greetingText)!")
                        .font(theme.typography.h1)
                        .foregroundColor(theme.colors.textPrimary)
                }
            }

            Text("Track your cognitive performance over time")
                .font(theme.typography.bodyMedium)
                .foregroundColor(theme.colors.textSecondary)
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
