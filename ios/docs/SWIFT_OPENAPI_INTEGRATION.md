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

## Next Steps

To use the generator:

1. Create an `openapi.yaml` or `openapi.json` file in your project
2. Create an `openapi-generator-config.yaml` configuration file
3. Add the generator build plugin to your target
4. Import `OpenAPIRuntime` in files that use generated code

See the [Swift OpenAPI Generator documentation](https://swiftpackageindex.com/apple/swift-openapi-generator/documentation) for detailed usage instructions.

## Package Resolution

The complete dependency graph is tracked in:
- `/Users/mattgioe/aiq/ios/AIQ.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved`

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
