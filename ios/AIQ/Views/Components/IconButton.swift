import SwiftUI

/// A reusable icon button component that guarantees 44x44pt minimum touch target
/// Ensures accessibility compliance with Apple HIG minimum touch target requirements
struct IconButton: View {
    let icon: String
    let action: () -> Void
    var accessibilityLabel: String
    var foregroundColor: Color = .primary
    var size: CGFloat = 44

    var body: some View {
        Button(
            action: {
                ServiceContainer.shared.resolve(HapticManagerProtocol.self)?.trigger(.selection)
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

#Preview("White on Dark") {
    HStack(spacing: 20) {
        IconButton(
            icon: "xmark",
            action: {},
            accessibilityLabel: "Close",
            foregroundColor: .white
        )

        IconButton(
            icon: "xmark.circle.fill",
            action: {},
            accessibilityLabel: "Dismiss",
            foregroundColor: .white
        )
    }
    .padding()
    .background(Color.red)
}
