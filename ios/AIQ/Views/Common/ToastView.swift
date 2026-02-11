import SwiftUI

/// Type of toast message to display
enum ToastType {
    case error
    case warning
    case info

    var icon: String {
        switch self {
        case .error: "exclamationmark.circle.fill"
        case .warning: "exclamationmark.triangle.fill"
        case .info: "info.circle.fill"
        }
    }

    var backgroundColor: Color {
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
struct ToastView: View {
    let message: String
    let type: ToastType
    let onDismiss: () -> Void

    @Environment(\.accessibilityReduceMotion) var reduceMotion

    var body: some View {
        HStack(spacing: DesignSystem.Spacing.md) {
            Image(systemName: type.icon)
                .foregroundColor(.white)
                .font(.system(size: DesignSystem.IconSize.sm))

            Text(message)
                .font(.subheadline)
                .foregroundColor(.white)
                .multilineTextAlignment(.leading)
                .lineLimit(3)

            Spacer()

            IconButton(
                icon: "xmark",
                action: onDismiss,
                accessibilityLabel: "toast.dismiss".localized,
                foregroundColor: .white
            )
            .accessibilityIdentifier(AccessibilityIdentifiers.ToastView.dismissButton)
        }
        .padding(DesignSystem.Spacing.lg)
        .background(type.backgroundColor)
        .cornerRadius(DesignSystem.CornerRadius.md)
        .shadow(
            color: DesignSystem.Shadow.lg.color,
            radius: DesignSystem.Shadow.lg.radius,
            x: DesignSystem.Shadow.lg.x,
            y: DesignSystem.Shadow.lg.y
        )
        .padding(.horizontal, DesignSystem.Spacing.lg)
        .padding(.bottom, DesignSystem.Spacing.lg)
        .accessibilityElement(children: .contain)
        .accessibilityLabel("\(accessibilityTypeLabel): \(message)")
        .onTapGesture {
            onDismiss()
        }
    }

    private var accessibilityTypeLabel: String {
        switch type {
        case .error: "toast.type.error".localized
        case .warning: "toast.type.warning".localized
        case .info: "toast.type.info".localized
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

#Preview("Long Message") {
    VStack {
        Spacer()
        ToastView(
            message: "This is a very long toast message that should wrap to multiple lines",
            type: .error,
            onDismiss: {}
        )
    }
}
