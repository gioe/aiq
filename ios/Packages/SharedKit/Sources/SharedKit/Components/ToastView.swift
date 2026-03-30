import SwiftUI

/// Type of toast message to display
public enum ToastType {
    case error
    case warning
    case info

    public var icon: String {
        switch self {
        case .error: "exclamationmark.circle.fill"
        case .warning: "exclamationmark.triangle.fill"
        case .info: "info.circle.fill"
        }
    }

    public var backgroundColor: Color {
        switch self {
        case .error: Color.red
        case .warning: Color.orange
        case .info: Color.blue
        }
    }
}

/// A toast notification that appears at the bottom of the screen
///
/// Toasts provide brief, non-intrusive feedback to users about operations or errors.
/// They auto-dismiss after a timeout and can also be manually dismissed.
///
/// Usage:
/// ```swift
/// ToastView(
///     message: "Unable to open link",
///     type: .error,
///     onDismiss: { /* handle dismissal */ }
/// )
/// ```
public struct ToastView: View {
    public let message: String
    public let type: ToastType
    public let onDismiss: () -> Void
    public var hapticManager: (any HapticManagerProtocol)?

    @Environment(\.accessibilityReduceMotion) var reduceMotion
    @Environment(\.appTheme) private var theme

    public init(
        message: String,
        type: ToastType,
        onDismiss: @escaping () -> Void,
        hapticManager: (any HapticManagerProtocol)? = nil
    ) {
        self.message = message
        self.type = type
        self.onDismiss = onDismiss
        self.hapticManager = hapticManager
    }

    public var body: some View {
        HStack(spacing: theme.spacing.md) {
            Image(systemName: type.icon)
                .foregroundColor(.white)
                .font(.system(size: theme.iconSizes.sm))

            Text(message)
                .font(.subheadline)
                .foregroundColor(.white)
                .multilineTextAlignment(.leading)
                .lineLimit(3)

            Spacer()

            IconButton(
                icon: "xmark",
                action: onDismiss,
                accessibilityLabel: "Dismiss",
                foregroundColor: .white,
                hapticManager: hapticManager
            )
            .accessibilityIdentifier("toast.dismissButton")
        }
        .padding(theme.spacing.lg)
        .background(type.backgroundColor)
        .cornerRadius(theme.cornerRadius.md)
        .shadowStyle(theme.shadows.lg)
        .padding(.horizontal, theme.spacing.lg)
        .padding(.bottom, theme.spacing.lg)
        .accessibilityElement(children: .contain)
        .accessibilityLabel("\(accessibilityTypeLabel): \(message)")
        .onTapGesture {
            onDismiss()
        }
    }

    private var accessibilityTypeLabel: String {
        switch type {
        case .error: "Error"
        case .warning: "Warning"
        case .info: "Info"
        }
    }
}

#Preview("Error Toast") {
    VStack {
        Spacer()
        ToastView(
            message: "Unable to open this link",
            type: .error,
            onDismiss: {}
        )
    }
}

#Preview("Warning Toast") {
    VStack {
        Spacer()
        ToastView(
            message: "This feature is not yet available",
            type: .warning,
            onDismiss: {}
        )
    }
}

#Preview("Info Toast") {
    VStack {
        Spacer()
        ToastView(
            message: "Your test has been saved",
            type: .info,
            onDismiss: {}
        )
    }
}
