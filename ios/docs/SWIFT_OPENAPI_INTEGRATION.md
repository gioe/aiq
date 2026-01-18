# Swift OpenAPI Generator Integration

## Overview

The AIQ iOS project now includes Apple's Swift OpenAPI Generator to enable automatic generation of Swift types and client code from OpenAPI specifications. This ensures type safety between the iOS app and backend API.

## Dependencies Added

### Primary Dependencies

| Package | Version | Repository | Purpose |
|---------|---------|------------|---------|
| swift-openapi-generator | 1.10.4+ | [apple/swift-openapi-generator](https://github.com/apple/swift-openapi-generator) | Build tool plugin for generating Swift code from OpenAPI specs |
| swift-openapi-runtime | 1.9.0+ | [apple/swift-openapi-runtime](https://github.com/apple/swift-openapi-runtime) | Runtime library for generated OpenAPI code |

### Transitive Dependencies

The Swift OpenAPI Generator also brought in the following dependencies:

- **swift-http-types** (1.5.1) - HTTP types for Swift
- **OpenAPIKit** (3.9.0) - OpenAPI document parsing
- **swift-collections** (1.3.0) - Swift collections library
- **swift-algorithms** (1.2.1) - Swift algorithms library
- **swift-numerics** (1.1.1) - Swift numerics library
- **swift-argument-parser** (1.7.0) - Command line argument parsing
- **Yams** (6.2.0) - YAML parser

## Version Requirements

- **iOS**: 16.0+
- **Swift**: 5.9+
- **Xcode**: 15.0+

## Integration Details

### Package Manager

The project uses Swift Package Manager (SPM) integrated directly into the Xcode project. The packages are configured with "up to next major version" semantic versioning to receive bug fixes and minor updates while maintaining compatibility.

### Current Configuration

```swift
// Package References in project.pbxproj
- swift-openapi-generator: upToNextMajorVersion from 1.10.4
- swift-openapi-runtime: upToNextMajorVersion from 1.9.0
```

### Target Dependencies

The `OpenAPIRuntime` product is linked to the main `AIQ` target, providing runtime support for generated code.

## Verification

The integration was verified with a successful build:

```bash
cd ios && xcodebuild build -project AIQ.xcodeproj -scheme AIQ \
  -destination 'platform=iOS Simulator,name=iPhone 16,OS=18.3.1'
```

**Result**: BUILD SUCCEEDED

## Configuration

### Generator Configuration

The Swift OpenAPI Generator is configured via `ios/AIQ/openapi-generator-config.yaml`:

```yaml
# Generate both types (models) and client code
generate:
  - types
  - client

# Keep generated code internal to the AIQ module
accessModifier: internal

# Use idiomatic Swift naming conventions
namingStrategy: idiomatic
```

**Key Configuration Choices:**

- **generate: types + client** - Generates both model types and API client code for type-safe networking
- **accessModifier: internal** - Keeps generated code internal to prevent exposing OpenAPI types as public API
- **namingStrategy: idiomatic** - Converts OpenAPI identifiers (snake_case, etc.) to Swift-idiomatic names (camelCase)

### OpenAPI Specification

The OpenAPI specification is located at:
- **Source**: `docs/api/openapi.json` (exported by backend CI via TASK-360)
- **Copy in iOS project**: `ios/AIQ/openapi.json` (required by Swift OpenAPI Generator build plugin)

**Spec Stats:**
- **Endpoints**: 51 API endpoints
- **Schemas**: 125 data models
- **Version**: 0.1.0

### Build Plugin Setup

The Swift OpenAPI Generator runs as a build plugin during Xcode builds. To complete the setup:

1. **Files are already added to the project** (NOT to Compile Sources):
   - `openapi-generator-config.yaml` - visible in Xcode project navigator
   - `openapi.json` - visible in Xcode project navigator
   - The build plugin discovers these files automatically from the project directory

2. **Configure the build plugin**:
   - In Target → Build Phases → Run Build Tool Plug-ins
   - Add the "OpenAPIGenerator Plugin"
   - Xcode will display a security dialog on first build (approve it)

3. **Sync the OpenAPI spec** before building:
   ```bash
   ./ios/scripts/sync_openapi_spec.sh
   ```
   Note: `openapi.json` is gitignored and copied from `docs/api/openapi.json` at build time.

4. **Generated code location**:
   - The plugin generates Swift code automatically in the derived data directory
   - Generated code is NOT committed to source control
   - Code regenerates on each build when the OpenAPI spec changes

## Next Steps

To complete the integration:

1. **Add build plugin** (see "Build Plugin Setup" above)

2. **Build the project**: Run `/build-ios-project` to trigger code generation

3. **Verify generated code**: Check build logs for generated Swift files

4. **Integrate with APIService**: Update `Services/API/` to use generated models instead of manually-written types

5. **Update API calls**: Migrate from manual `URLSession` code to generated client methods

See the [Swift OpenAPI Generator documentation](https://swiftpackageindex.com/apple/swift-openapi-generator/documentation) for detailed usage instructions.

**Related**: TASK-360 (OpenAPI spec export to `docs/api/openapi.json`)

## Package Resolution

The complete dependency graph is tracked in:
- `ios/AIQ.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved`

## References

- [Swift OpenAPI Generator](https://github.com/apple/swift-openapi-generator)
- [Swift OpenAPI Runtime](https://github.com/apple/swift-openapi-runtime)
- [WWDC23: Meet Swift OpenAPI Generator](https://developer.apple.com/videos/play/wwdc2023/10171/)
- [Swift.org: Introducing Swift OpenAPI Generator](https://www.swift.org/blog/introducing-swift-openapi-generator/)
- [Swift.org: Swift OpenAPI Generator 1.0 Released](https://www.swift.org/blog/swift-openapi-generator-1.0/)

## Task Information

- **Task**: TASK-362
- **Implementation Date**: 2026-01-17
- **Implemented By**: Claude Code
