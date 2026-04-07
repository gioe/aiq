import SwiftUI

/// A reusable primary action button with consistent styling
public struct PrimaryButton: View {
    public let title: String
    public let action: () -> Void
    public var isLoading: Bool = false
    public var isDisabled: Bool = false
    public var accessibilityId: String?
    public var hapticManager: (any HapticManagerProtocol)?

    @Environment(\.appTheme) private var theme

    public init(
        title: String,
        action: @escaping () -> Void,
        isLoading: Bool = false,
        isDisabled: Bool = false,
        accessibilityId: String? = nil,
        hapticManager: (any HapticManagerProtocol)? = nil
    ) {
        self.title = title
        self.action = action
        self.isLoading = isLoading
        self.isDisabled = isDisabled
        self.accessibilityId = accessibilityId
        self.hapticManager = hapticManager
    }

    public var body: some View {
        Button(
            action: {
                hapticManager?.trigger(.light)
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
                        .font(theme.typography.button)
                        .frame(maxWidth: .infinity)
                }
                .padding(theme.spacing.lg)
                .background(isDisabled ? theme.colors.textSecondary : theme.colors.primary)
                .foregroundColor(.white)
                .cornerRadius(theme.cornerRadius.md)
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
