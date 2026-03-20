## iOS App Context

When working on the iOS app, read these docs first:

| Topic | Document |
|-------|----------|
| Coding standards & patterns | [docs/CODING_STANDARDS.md](docs/CODING_STANDARDS.md) |
| Architecture | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| OpenAPI integration | [docs/SWIFT_OPENAPI_INTEGRATION.md](docs/SWIFT_OPENAPI_INTEGRATION.md) |
| Setup & features | [README.md](README.md) |

### Required skills

Always use these skills instead of running commands directly:

| Operation | Skill |
|-----------|-------|
| Build the project | `/build-ios-project` |
| Run tests | `/run-ios-test` |
| Add new Swift files to Xcode | `/xcode-file-manager` |
| Create Xcode group hierarchies | `/xcode-group-manager` |

### Key source files

| File | Contains |
|------|----------|
| `Packages/SharedKit/Sources/SharedKit/Architecture/BaseViewModel.swift` | Base class all ViewModels inherit from (loading, errors) — lives in SharedKit; `AIQ/Shared/Architecture/BaseViewModel.swift` re-exports it as a typealias |
| `Packages/SharedKit/Sources/SharedKit/Design/` | Design system (ColorPalette, Typography, DesignSystem) — includes `shadowStyle(_ style: ShadowStyle)` View extension; use `.shadowStyle(DesignSystem.Shadow.md)` instead of expanding properties inline (expanded form exceeds SwiftLint's 120-char limit). When auditing call sites, search for both `DesignSystem.Shadow.` and `theme.shadows.` patterns — views using `@Environment(\.appTheme)` use the latter. |
| `Packages/SharedKit/Sources/SharedKit/Extensions/` | Generic Swift/SwiftUI extensions (Date, String, View, Int, Number) |
| `Packages/SharedKit/Sources/SharedKit/Components/` | Generic reusable UI components |
| `Packages/SharedKit/Sources/SharedKit/Services/` | App-independent services (BiometricAuthManager, HapticManager, KeychainStorage, NetworkMonitor, ToastManager) |
| `Packages/SharedKit/Sources/SharedKit/Protocols/` | `ErrorRecorder` and `RetryableError` — protocols implemented by AIQ app-layer adapters |
| `AIQ/Services/API/` | Network client with retry and token refresh |
| `AIQ/Services/Auth/AuthManager.swift` | Authentication, token management |
| `AIQ/Utilities/Extensions/` | AIQ-specific extensions (String+Localization) |
| `AIQ/Utilities/Helpers/CrashlyticsRecorderAdapter.swift` | Bridges SharedKit's `ErrorRecorder` to Firebase Crashlytics |
| `AIQ/Models/RetryableErrorConformances.swift` | Declares `APIError: RetryableError` and `ContextualError: RetryableError` |
| `AIQ/Views/Components/` | AIQ-specific UI components (RootView, MainTabView, BiometricLockView, etc.) |
| `APIClient` (remote: gioe/ios-libs) | OpenAPI-generated type-safe API client — remote Swift package dependency, not a local path |
| `AIQ/Models/*+Extensions.swift` | UI computed properties for generated types (bring-your-own-extensions pattern; migrated from ios-libs in TASK-113) |

### Key patterns

- **MVVM**: All ViewModels inherit from `BaseViewModel`. Views observe `@Published` properties. ViewModels should not import SwiftUI (except for `ObservableObject`).
- **OpenAPI code-gen**: The backend Pydantic schemas generate `openapi.json`, which Swift OpenAPI Generator turns into type-safe client code. The generated `APIClient` is published as a remote Swift package in `gioe/ios-libs` — spec changes require updating and publishing a new release there.
- **Model extensions**: UI computed properties for generated types go in the app's `AIQ/Models/` directory as `<TypeName>+Extensions.swift` (bring-your-own-extensions pattern, TASK-113). The `APIClient` package in `gioe/ios-libs` is kept clean of product-specific code. Date formatting stays in the main app's `Date+Extensions.swift`.
- **Accessibility**: Full VoiceOver support, Dynamic Type, semantic colors, RTL layout support required.
- **Branding string sweeps**: When replacing a user-visible term (e.g., "IQ" → "AIQ"), use `grep -rn '\bIQ\b' ios/` (no quote anchors) rather than `grep '"[^"]*IQ[^"]*"'`. The quote-anchored pattern misses Swift string interpolations like `"IQ score \(iqScore)"` in model/extension files. Also check the `AIQAPIClient` extensions in `gioe/ios-libs` (the remote Swift package — search there or in the local Swift package cache) and `AIQ/Models/` for accessibility computed properties.
- **Certificate pinning**: TrustKit enabled in RELEASE builds only. DEBUG builds use `http://localhost:8000`.
- **`screenshotPrevented` XCTest element type**: `ScreenshotContainerView` (the UIKit view backing `.screenshotPrevented()`) has `isAccessibilityElement = true` but no `accessibilityTraits`, so XCTest maps it to `XCUIElementType.other` — not `.staticText`. Always query these elements with `app.descendants(matching: .any)[identifier]` or `app.otherElements[identifier]`; `app.staticTexts[identifier]` will never find them.
