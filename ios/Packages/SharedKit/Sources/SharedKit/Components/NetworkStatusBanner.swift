import SwiftUI

/// A dismissible banner displayed when the device loses network connectivity.
///
/// The banner observes ``NetworkMonitor/shared`` and automatically appears when
/// `isConnected` becomes `false`. The user can dismiss it manually; the banner
/// reappears if connectivity drops again after being restored.
///
/// All visual properties are parameterizable, with defaults drawn from the active
/// ``AppThemeProtocol`` so the banner integrates seamlessly with any theme.
///
/// ```swift
/// NetworkStatusBanner()          // default colors + message
/// NetworkStatusBanner(
///     message: "Offline mode",
///     backgroundColor: .red,
///     textColor: .white
/// )
/// ```
public struct NetworkStatusBanner: View {
    // MARK: - Configuration

    /// The message displayed when connectivity is lost.
    public let message: String

    /// Background color of the banner. Defaults to the theme's warning color.
    public let backgroundColor: Color?

    /// Text and icon color. Defaults to the theme's `textOnPrimary` color.
    public let textColor: Color?

    // MARK: - Environment & State

    @Environment(\.appTheme) private var theme
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    @ObservedObject private var monitor: NetworkMonitor

    /// Tracks whether the user has manually dismissed the current offline episode.
    /// Resets when connectivity is restored so the banner can reappear on the next drop.
    @State private var isDismissed = false

    // MARK: - Init

    /// Creates a network status banner.
    /// - Parameters:
    ///   - message: Text to display. Defaults to `"No network connection"`.
    ///   - backgroundColor: Banner background. `nil` uses the theme's warning color.
    ///   - textColor: Text and icon color. `nil` uses the theme's `textOnPrimary`.
    ///   - monitor: The network monitor to observe. Defaults to `.shared`.
    public init(
        message: String = "No network connection",
        backgroundColor: Color? = nil,
        textColor: Color? = nil,
        monitor: NetworkMonitor = .shared
    ) {
        self.message = message
        self.backgroundColor = backgroundColor
        self.textColor = textColor
        self.monitor = monitor
    }

    // MARK: - Body

    public var body: some View {
        Group {
            if !monitor.isConnected && !isDismissed {
                HStack(spacing: theme.spacing.sm) {
                    Image(systemName: "wifi.slash")
                        .foregroundColor(resolvedTextColor)

                    Text(message)
                        .font(theme.typography.bodySmall)
                        .foregroundColor(resolvedTextColor)

                    Spacer()

                    Button {
                        isDismissed = true
                    } label: {
                        Image(systemName: "xmark")
                            .foregroundColor(resolvedTextColor)
                            .font(.caption.weight(.semibold))
                    }
                    .accessibilityLabel("Dismiss")
                    .accessibilityIdentifier("networkStatusBanner.dismissButton")
                }
                .padding(.horizontal, theme.spacing.md)
                .padding(.vertical, theme.spacing.sm)
                .frame(maxWidth: .infinity)
                .background(resolvedBackgroundColor)
                .transition(
                    reduceMotion
                        ? .opacity
                        : .move(edge: .top).combined(with: .opacity)
                )
                .accessibilityElement(children: .contain)
                .accessibilityLabel("Network status: \(message)")
            }
        }
        .onChange(of: monitor.isConnected) { isConnected in
            if isConnected {
                isDismissed = false
            }
        }
    }

    // MARK: - Resolved Colors

    private var resolvedBackgroundColor: Color {
        backgroundColor ?? theme.colors.warning
    }

    private var resolvedTextColor: Color {
        textColor ?? .white
    }
}

// MARK: - View Modifier

public extension View {
    /// Overlays a ``NetworkStatusBanner`` at the top of the view.
    ///
    /// - Parameters:
    ///   - message: Banner message text.
    ///   - backgroundColor: Optional custom background color.
    ///   - textColor: Optional custom text/icon color.
    func networkStatusBanner(
        message: String = "No network connection",
        backgroundColor: Color? = nil,
        textColor: Color? = nil
    ) -> some View {
        overlay(alignment: .top) {
            NetworkStatusBanner(
                message: message,
                backgroundColor: backgroundColor,
                textColor: textColor
            )
            .animation(
                .easeInOut(duration: 0.3),
                value: NetworkMonitor.shared.isConnected
            )
        }
    }
}

#Preview {
    VStack {
        Text("Content behind the banner")
            .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
    .networkStatusBanner()
}
