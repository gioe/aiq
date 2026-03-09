import SwiftUI

private struct AppThemeKey: EnvironmentKey {
    static let defaultValue: any AppThemeProtocol = DefaultTheme()
}

extension EnvironmentValues {
    /// The current app theme. Inject a custom conformance at the root to enable
    /// theme variants (high-contrast, seasonal, white-label) without modifying components.
    var appTheme: any AppThemeProtocol {
        get { self[AppThemeKey.self] }
        set { self[AppThemeKey.self] = newValue }
    }
}
