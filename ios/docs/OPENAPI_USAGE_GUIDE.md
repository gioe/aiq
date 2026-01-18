# Swift OpenAPI Generator Usage Guide

This guide explains how to use the Swift OpenAPI Generator in the AIQ iOS project after completing the build plugin setup.

## Overview

The Swift OpenAPI Generator automatically creates type-safe Swift code from the OpenAPI specification at build time. This eliminates manual API client code and ensures the iOS app stays in sync with the backend API.

## What Gets Generated

When you build the project, the generator creates:

1. **Types** (`Components.swift`):
   - All request/response models from the OpenAPI spec
   - Enums for status codes and error types
   - Type-safe representations of all 125 schemas

2. **Client** (`Client.swift`):
   - Methods for all 51 API endpoints
   - Automatic request/response serialization
   - Built-in error handling

## Configuration Summary

| Setting | Value | Purpose |
|---------|-------|---------|
| **generate** | `types`, `client` | Generate both models and client code |
| **accessModifier** | `internal` | Keep generated code internal to module |
| **namingStrategy** | `idiomatic` | Convert to Swift naming conventions |

## Using the Generated Code

### 1. Import the Generated Types

```swift
import OpenAPIRuntime
import OpenAPIURLSession
```

### 2. Create a Client Instance

```swift
let client = Client(
    serverURL: URL(string: "https://aiq-backend-production.up.railway.app")!,
    transport: URLSessionTransport()
)
```

### 3. Make API Calls

```swift
// Example: Login
let loginRequest = Components.Schemas.LoginRequest(
    email: "user@example.com",
    password: "password"
)

do {
    let response = try await client.login(body: .json(loginRequest))
    switch response {
    case .ok(let okResponse):
        // Handle successful login
        let body = try okResponse.body.json
        print("Access token: \(body.access_token)")
    case .undocumented(statusCode: let statusCode, _):
        // Handle unexpected status code
        print("Unexpected status: \(statusCode)")
    }
} catch {
    // Handle network or decoding errors
    print("Error: \(error)")
}
```

### 4. Type Safety Benefits

The generated code provides compile-time guarantees:

```swift
// ✅ Correct - all required fields present
let user = Components.Schemas.UserProfile(
    id: 123,
    email: "user@example.com",
    created_at: Date()
)

// ❌ Won't compile - missing required fields
let invalidUser = Components.Schemas.UserProfile(
    email: "user@example.com"
)
```

## Integration with Existing Code

### Current State

The project currently uses manual `URLSession` code in `Services/API/APIClient.swift`:

```swift
// Current manual approach
func login(email: String, password: String) async throws -> TokenResponse {
    // Manual URLRequest construction
    // Manual JSON encoding/decoding
    // Manual error handling
}
```

### Migration Strategy

Replace manual API calls with generated client methods:

**Before:**
```swift
let tokenResponse = try await apiClient.login(
    email: email,
    password: password
)
```

**After:**
```swift
let loginRequest = Components.Schemas.LoginRequest(
    email: email,
    password: password
)
let response = try await openAPIClient.login(body: .json(loginRequest))
```

### Recommended Approach

1. **Create an adapter layer** in `Services/API/OpenAPIAdapter.swift` to bridge between:
   - Existing `APIClient` interface (used by ViewModels)
   - New generated OpenAPI client

2. **Gradually migrate endpoints**:
   - Start with auth endpoints (login, registration, token refresh)
   - Move to test session endpoints
   - Migrate remaining endpoints

3. **Maintain backward compatibility** during migration:
   - Keep existing `APIClient` methods working
   - Internally delegate to OpenAPI client
   - Update ViewModels only after testing

## Error Handling

The generated client uses Swift's structured concurrency:

```swift
do {
    let response = try await client.getTestHistory()
    switch response {
    case .ok(let okResponse):
        let tests = try okResponse.body.json
        // Process test history
    case .unauthorized:
        // Token expired - trigger refresh
    case .undocumented(statusCode: let code, _):
        // Log unexpected response
    }
} catch let error as URLError {
    // Network connectivity issues
} catch {
    // Other errors (decoding, etc.)
}
```

## Testing with Generated Code

### Mock Transport

Create a mock transport for testing without network calls:

```swift
struct MockTransport: ClientTransport {
    let mockResponses: [String: HTTPResponse]

    func send(_ request: HTTPRequest, baseURL: URL) async throws -> HTTPResponse {
        // Return mock response based on request
    }
}

// In tests
let mockClient = Client(
    serverURL: URL(string: "https://mock.example.com")!,
    transport: MockTransport(mockResponses: [...])
)
```

## Build Plugin Details

### How It Works

1. **Build time**: Xcode runs the OpenAPIGenerator plugin
2. **Input files**:
   - `ios/AIQ/openapi.json` (OpenAPI spec)
   - `ios/AIQ/openapi-generator-config.yaml` (configuration)
3. **Output location**: Derived data directory (not source controlled)
4. **Regeneration**: Happens automatically when spec changes

### Troubleshooting

**Problem**: "No config file found in the target"
- **Solution**: Ensure both `openapi.json` and `openapi-generator-config.yaml` are visible in the Xcode project navigator (added to the project, NOT to Compile Sources)

**Problem**: "Build plugin not executing"
- **Solution**: Add "OpenAPIGenerator Plugin" to Build Phases → Run Build Tool Plug-ins

**Problem**: Security dialog on build
- **Solution**: This is expected on first build - approve the plugin execution

**Note**: The config files should NOT be added to "Compile Sources" - they are discovered by the build plugin automatically from the project directory.

## Keeping Spec in Sync

The OpenAPI spec is automatically exported by backend CI (TASK-360) to `docs/api/openapi.json`.

### Automatic Sync (Recommended)

Run the sync script before building:
```bash
./ios/scripts/sync_openapi_spec.sh
```

Or add it as a pre-build script phase in Xcode.

### Manual Sync

1. **Backend CI updates** `docs/api/openapi.json` after schema changes
2. **Copy** to `ios/AIQ/openapi.json`:
   ```bash
   cp docs/api/openapi.json ios/AIQ/openapi.json
   ```
3. **Build** triggers automatic regeneration of Swift code

## References

- [Swift OpenAPI Generator GitHub](https://github.com/apple/swift-openapi-generator)
- [Apple's Official Tutorial](https://swiftinit.org/docs/swift-openapi-generator/swift_openapi_generator/clientxcode.tutorial)
- [WWDC23: Meet Swift OpenAPI Generator](https://developer.apple.com/videos/play/wwdc2023/10171/)
- [Swift.org Blog Post](https://www.swift.org/blog/introducing-swift-openapi-generator/)

## Related Documentation

- [SWIFT_OPENAPI_INTEGRATION.md](./SWIFT_OPENAPI_INTEGRATION.md) - Integration and setup details
- [CODING_STANDARDS.md](./CODING_STANDARDS.md) - iOS coding standards
- [/docs/api/openapi.json](/docs/api/openapi.json) - OpenAPI specification source

---

**Task**: TASK-362
**Last Updated**: 2026-01-17
**Status**: Configuration complete, build plugin setup pending
