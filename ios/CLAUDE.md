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

### Key source files

| File | Contains |
|------|----------|
| `AIQ/ViewModels/BaseViewModel.swift` | Base class all ViewModels inherit from (loading, errors) |
| `AIQ/Services/API/` | Network client with retry and token refresh |
| `AIQ/Services/Auth/AuthManager.swift` | Authentication, token management |
| `AIQ/Utilities/Design/` | Design system (ColorPalette, Typography, DesignSystem) |
| `AIQ/Utilities/Extensions/` | Swift extensions (Date, String, View) |
| `AIQ/Views/Common/` | Reusable UI components |
| `Packages/AIQAPIClient/` | OpenAPI-generated type-safe API client |
| `Packages/AIQAPIClient/Sources/AIQAPIClient/Extensions/` | UI computed properties for generated types |

### Key patterns

- **MVVM**: All ViewModels inherit from `BaseViewModel`. Views observe `@Published` properties. ViewModels should not import SwiftUI (except for `ObservableObject`).
- **OpenAPI code-gen**: The backend Pydantic schemas generate `openapi.json`, which Swift OpenAPI Generator turns into type-safe client code in `Packages/AIQAPIClient`. Run `./scripts/sync_openapi_spec.sh` after pulling backend changes.
- **Model extensions**: UI computed properties for generated types go in `Packages/AIQAPIClient/Sources/AIQAPIClient/Extensions/` as `<TypeName>+UI.swift`. Date formatting stays in the main app's `Date+Extensions.swift`.
- **Accessibility**: Full VoiceOver support, Dynamic Type, semantic colors, RTL layout support required.
- **Certificate pinning**: TrustKit enabled in RELEASE builds only. DEBUG builds use `http://localhost:8000`.
