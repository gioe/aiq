import SwiftUI

private struct AppThemeKey: EnvironmentKey {
    /// DefaultTheme() here serves previews and unit tests that don't inject .environment(\.appTheme).
    /// In production, the host app always injects DefaultTheme at the root, making this unreachable.
    static let defaultValue: any AppThemeProtocol = DefaultTheme()
}

public extension EnvironmentValues {
    /// The current app theme. Inject a custom conformance at the root to enable
    /// theme variants (high-contrast, seasonal, white-label) without modifying components.
    var appTheme: any AppThemeProtocol {
        get { self[AppThemeKey.self] }
        set { self[AppThemeKey.self] = newValue }
    }
}
