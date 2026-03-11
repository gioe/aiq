import SwiftUI

/// A reusable icon button component that guarantees 44x44pt minimum touch target
/// Ensures accessibility compliance with Apple HIG minimum touch target requirements
public struct IconButton: View {
    public let icon: String
    public let action: () -> Void
    public var accessibilityLabel: String
    public var foregroundColor: Color = .primary
    public var size: CGFloat = 44
    public var hapticManager: (any HapticManagerProtocol)?

    public init(
        icon: String,
        action: @escaping () -> Void,
        accessibilityLabel: String,
        foregroundColor: Color = .primary,
        size: CGFloat = 44,
        hapticManager: (any HapticManagerProtocol)? = nil
    ) {
        self.icon = icon
        self.action = action
        self.accessibilityLabel = accessibilityLabel
        self.foregroundColor = foregroundColor
        self.size = size
        self.hapticManager = hapticManager
    }

    public var body: some View {
        Button(
            action: {
                hapticManager?.trigger(.selection)
                action()
            },
            label: {
                Image(systemName: icon)
                    .foregroundColor(foregroundColor)
                    .fontWeight(.semibold)
                    .frame(width: size, height: size)
                    .contentShape(Rectangle())
            }
        )
        .accessibilityLabel(accessibilityLabel)
    }
}

#Preview("Default") {
    HStack(spacing: 20) {
        IconButton(
            icon: "xmark",
            action: {},
            accessibilityLabel: "Close"
        )

        IconButton(
            icon: "xmark.circle.fill",
            action: {},
            accessibilityLabel: "Dismiss",
            foregroundColor: .red
        )

        IconButton(
            icon: "chevron.left",
            action: {},
            accessibilityLabel: "Back",
            foregroundColor: .blue
        )
    }
    .padding()
    .background(Color(.systemGroupedBackground))
}
