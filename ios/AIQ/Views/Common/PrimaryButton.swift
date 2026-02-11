import SwiftUI

/// A reusable primary action button with consistent styling
struct PrimaryButton: View {
    let title: String
    let action: () -> Void
    var isLoading: Bool = false
    var isDisabled: Bool = false
    var accessibilityId: String?

    var body: some View {
        Button(
            action: {
                ServiceContainer.shared.resolve(HapticManagerProtocol.self)?.trigger(.light)
                action()
            },
            label: {
                HStack {
                    if isLoading {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .white))
                            .scaleEffect(0.8)
                            .accessibilityHidden(true) // Hide visual loading indicator
                    }
                    Text(title)
                        .font(Typography.button)
                        .frame(maxWidth: .infinity)
                }
                .padding(DesignSystem.Spacing.lg)
                .background(isDisabled ? ColorPalette.textSecondary : ColorPalette.primary)
                .foregroundColor(.white)
                .cornerRadius(DesignSystem.CornerRadius.md)
            }
        )
        .disabled(isDisabled || isLoading)
        .accessibilityLabel(title)
        .accessibilityHint(accessibilityHintText)
        .accessibilityAddTraits(accessibilityTraits)
        .optionalAccessibilityIdentifier(accessibilityId)
    }

    private var accessibilityHintText: String {
        if isLoading {
            "Loading, please wait"
        } else if isDisabled {
            "Button is disabled"
        } else {
            "Double tap to activate"
        }
    }

    private var accessibilityTraits: AccessibilityTraits {
        // .isButton is the only trait we need
        // The .disabled() modifier automatically handles accessibility for disabled state
        [.isButton]
    }
}

#Preview {
    VStack(spacing: 20) {
        PrimaryButton(title: "Sign In", action: {})
        PrimaryButton(title: "Loading...", action: {}, isLoading: true)
        PrimaryButton(title: "Disabled", action: {}, isDisabled: true)
    }
    .padding()
}
