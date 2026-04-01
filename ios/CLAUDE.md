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
| `Packages/SharedKit/Sources/SharedKit/Design/` | Design system (ColorPalette, Typography, DesignSystem) — includes `shadowStyle(_ style: ShadowStyle)` View extension; use `.shadowStyle(DesignSystem.Shadow.md)` instead of expanding properties inline (expanded form exceeds SwiftLint's 120-char limit). When auditing call sites, search for both `DesignSystem.Shadow.` and `theme.shadows.` patterns — views using `@Environment(\.appTheme)` use the latter. **SharedKit View components that use `@Environment(\.appTheme)` must access design tokens via `theme.spacing.*`, `theme.cornerRadius.*`, `theme.shadows.*` — never via `DesignSystem.Spacing.*`, `DesignSystem.CornerRadius.*`, or `DesignSystem.Shadow.*` directly.** |
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
| `Packages/APIClient/Sources/APIClient/openapi.json` | The project's OpenAPI 3.x spec — update this file when the backend spec changes (`cp docs/api/openapi.json ios/Packages/APIClient/Sources/APIClient/openapi.json`) |
| `Packages/APIClient/` | Local Swift Package — `APIClient` target (generated client) + `AIQAPIClient` target (product-specific UI extensions); replaces the remote `gioe/ios-libs` package |
| `Packages/SharedKit/` | Local Swift Package — shared utilities; was previously part of `gioe/ios-libs` |
| `AIQ/Models/*+Extensions.swift` | UI computed properties for generated types (bring-your-own-extensions pattern; migrated from ios-libs in TASK-113) |

### Key patterns

- **MVVM**: All ViewModels inherit from `BaseViewModel`. Views observe `@Published` properties. ViewModels should not import SwiftUI (except for `ObservableObject`).
- **OpenAPI code-gen**: The backend Pydantic schemas generate `openapi.json`, which Swift OpenAPI Generator turns into type-safe client code at build time via the local `Packages/APIClient` package. When the backend API changes, copy the new spec: `cp docs/api/openapi.json ios/Packages/APIClient/Sources/APIClient/openapi.json` — no remote release required.
- **Model extensions**: UI computed properties for generated types go in the app's `AIQ/Models/` directory as `<TypeName>+Extensions.swift` (bring-your-own-extensions pattern, TASK-113). The local `APIClient` package is kept clean of product-specific code; use `Packages/APIClient/Sources/AIQAPIClient/` for API-layer display helpers, and `AIQ/Models/` for app-level domain logic. Date formatting stays in the main app's `Date+Extensions.swift`.
- **Accessibility**: Full VoiceOver support, Dynamic Type, semantic colors, RTL layout support required.
- **Branding string sweeps**: When replacing a user-visible term (e.g., "IQ" → "AIQ"), use `grep -rn '\bIQ\b' ios/` (no quote anchors) rather than `grep '"[^"]*IQ[^"]*"'`. The quote-anchored pattern misses Swift string interpolations like `"IQ score \(iqScore)"` in model/extension files. Also check `Packages/APIClient/Sources/AIQAPIClient/` and `AIQ/Models/` for accessibility computed properties.
- **Certificate pinning**: TrustKit enabled in RELEASE builds only. DEBUG builds use `http://localhost:8000`.
- **Accessibility identifiers must be applied, not just defined**: Adding an identifier to `AccessibilityIdentifiers.swift` is not enough — it must also be wired into the view via `.accessibilityIdentifier(...)`. When adding a new identifier, apply it to the view in the same commit. If an identifier exists in `AccessibilityIdentifiers.swift` but is missing from the view, XCUITest will silently fail to find the element.
- **`screenshotPrevented` XCTest element type**: `ScreenshotContainerView` (the UIKit view backing `.screenshotPrevented()`) has `isAccessibilityElement = true` but no `accessibilityTraits`, so XCTest maps it to `XCUIElementType.other` — not `.staticText`. Always query these elements with `app.descendants(matching: .any)[identifier]` or `app.otherElements[identifier]`; `app.staticTexts[identifier]` will never find them.
- **SwiftLint `--strict` and `missing_docs`**: Pre-commit runs SwiftLint with `--strict`, which promotes all warnings (including `missing_docs`) to errors. Adding new `public` properties to a file that already has pre-existing `missing_docs` violations will block the commit until every `public` symbol in that file has a `///` doc comment — not just the new ones. When adding new public symbols to any file in `Packages/SharedKit/`, check for pre-existing violations first (`swiftlint lint --path <file>`) and add `///` doc comments to all public properties, inits, and protocol requirements in the file before committing.
- **Theme migration call site searches**: When searching for `ColorPalette.*` usages to migrate, always search `ios/` recursively — not just `ios/AIQ/`. The `ios/Packages/SharedKit/Sources/SharedKit/Components/` directory contains reusable UI components (e.g. `LoadingOverlay.swift`) that reference `ColorPalette` directly and will be missed if the search scope is too narrow.
- **SharedKitTests and the Xcode native target**: `SharedKitTests` is wired into `AIQ.xcscheme` as a `PBXNativeTarget` with an explicit `Sources` build phase. Unlike the SPM `testTarget` (which auto-discovers all `.swift` files under `Tests/SharedKitTests/`), the Xcode native target only compiles files explicitly listed in `project.pbxproj`. When adding a new test file under `Packages/SharedKit/Tests/SharedKitTests/`, also register it via `/xcode-file-manager` so it is compiled by `xcodebuild test -scheme AIQ`.
- **`.accessibilityIdentifier` on SwiftUI containers requires `.accessibilityElement(children: .contain)`**: Applying `.accessibilityIdentifier` to a SwiftUI container (VStack, custom component) does NOT make it findable via `app.otherElements[id]` in XCUITest. SwiftUI sets the identifier on the underlying UIView but leaves `isAccessibilityElement = false`, so XCUITest never surfaces it. Fix: add `.accessibilityElement(children: .contain)` before `.accessibilityIdentifier` at the call site. Note: container elements are never `isHittable`; use `waitForExistence(timeout:)` (or `wait(for:)`) for presence assertions, not `waitForHittable(_:)`.
