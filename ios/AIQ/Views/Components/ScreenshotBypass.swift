import AIQSharedKit
import SwiftUI

// MARK: - Admin Environment Key

private struct IsAdminEnvironmentKey: EnvironmentKey {
    static let defaultValue: Bool = false
}

extension EnvironmentValues {
    var isAdmin: Bool {
        get { self[IsAdminEnvironmentKey.self] }
        set { self[IsAdminEnvironmentKey.self] = newValue }
    }
}

// MARK: - Screenshot Bypass Helper

extension View {
    @ViewBuilder
    func screenshotPreventedUnlessAdmin(
        isAdmin: Bool,
        accessibilityIdentifier: String? = nil,
        accessibilityLabel: String? = nil
    ) -> some View {
        if isAdmin {
            self
        } else {
            screenshotPrevented(
                accessibilityIdentifier: accessibilityIdentifier,
                accessibilityLabel: accessibilityLabel
            )
        }
    }
}
