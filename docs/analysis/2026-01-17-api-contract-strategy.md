# Analysis: API Contract Strategy for iOS-Backend Communication

**Date:** 2026-01-17
**Scope:** Investigation of the current API contract situation between the iOS app and backend, evaluation of solutions including Protocol Buffers, and recommendations for establishing an explicit, centralized API specification.

## Executive Summary

The AIQ project currently lacks a centralized, explicit API contract. API specifications are implicitly defined in two places: Pydantic schemas on the backend and Codable structs on iOS. While these are largely in sync today, this approach creates risk of contract drift, requires manual coordination, and makes it difficult for developers to understand the full API surface without reading code.

**The core problem:** API specifications are only discoverable by reading implementation code on both sides. There is no single source of truth that both platforms derive from.

**Recommendation:** Adopt **OpenAPI as the single source of truth** with **Apple's Swift OpenAPI Generator** for iOS client generation. This leverages your existing FastAPI infrastructure (which already generates OpenAPI specs) while providing type-safe Swift code generation and build-time contract verification. Protocol Buffers would require significant architectural changes for marginal benefit in this use case.

## Methodology

### Tools and Techniques Used
- Codebase exploration using Glob and Grep tools
- File analysis of iOS networking layer (`ios/AIQ/Services/API/`, `ios/AIQ/Models/`)
- File analysis of backend schemas (`backend/app/schemas/`, `backend/app/api/v1/`)
- Web research on API contract solutions (OpenAPI, Protobuf, gRPC)
- Review of Apple's Swift OpenAPI Generator documentation

### Files and Directories Examined
- iOS: `APIClient.swift`, `APIEndpoint`, all model files (`Auth.swift`, `TestResult.swift`, etc.)
- Backend: All Pydantic schemas, FastAPI router definitions, `main.py` OpenAPI configuration
- Documentation: `BACKEND_COORDINATION.md`

## Findings

### Finding 1: Current Contract Definition is Duplicated and Manual

The API contract is currently defined in two independent locations:

**Backend (Source of Implementation):**
```python
# backend/app/schemas/auth.py
class UserRegister(BaseModel):
    email: EmailStr
    password: str
    first_name: str      # snake_case
    last_name: str
    birth_year: Optional[int]
    education_level: Optional[EducationLevelSchema]
    country: Optional[str]
    region: Optional[str]
```

**iOS (Independent Re-implementation):**
```swift
// ios/AIQ/Models/Auth.swift
struct RegisterRequest: Codable {
    let email: String
    let password: String
    let firstName: String     // camelCase with CodingKeys mapping
    let lastName: String
    let birthYear: Int?
    let educationLevel: EducationLevel?
    let country: String?
    let region: String?

    enum CodingKeys: String, CodingKey {
        case firstName = "first_name"  // Manual mapping
        // ...
    }
}
```

**Evidence:**
- 17 schema files in `backend/app/schemas/` defining Pydantic models
- 9+ model files in `ios/AIQ/Models/` independently defining Codable structs
- Manual `CodingKeys` enums for every snake_case to camelCase mapping
- No automated verification that these stay in sync

### Finding 2: FastAPI Already Generates OpenAPI - But It's Not Leveraged

FastAPI automatically generates OpenAPI documentation, but it's not being used as a contract:

**File:** `backend/app/main.py:216-217`
```python
app = FastAPI(
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    openapi_tags=tags_metadata,
    # ...
)
```

The OpenAPI spec is available at `/v1/docs` (Swagger UI) and `/v1/openapi.json`, but:
- iOS models are not generated from this spec
- There's no CI/CD validation that iOS models match the spec
- The spec is an output, not a shared input

### Finding 3: Existing Coordination Process is Documentation-Heavy

The project has a `BACKEND_COORDINATION.md` document that describes a manual coordination workflow:

**File:** `ios/docs/BACKEND_COORDINATION.md`
- Requires manual documentation of every endpoint
- Relies on PR descriptions to communicate contracts
- Includes a checklist that must be followed manually
- Schema matching reference table (Pydantic → Swift) for manual implementation

This process is thorough but doesn't prevent drift - it relies on developers correctly following the process every time.

### Finding 4: Contract Drift Risk is Real

The iOS `TestResultResponse` and backend `TestResultResponse` schemas show minor differences that could cause issues:

**Backend returns but iOS doesn't model:**
- `response_time_flags` - Backend returns this, iOS doesn't decode it
- `strongest_domain` / `weakest_domain` - Backend returns strings, iOS computes them locally
- `validity_status` - Present in backend schema, absent in iOS model

**iOS computes locally what backend provides:**
```swift
// iOS computes these from domainScores
var strongestDomain: (domain: CognitiveDomain, score: DomainScore)? {
    sortedDomainScores?
        .filter { $0.score.pct != nil && $0.score.total > 0 }
        .max { ($0.score.pct ?? 0) < ($1.score.pct ?? 0) }
}
```

This isn't necessarily wrong, but it demonstrates how the contract is not enforced - iOS simply ignores fields it doesn't need and computes what the backend could provide.

### Finding 5: Endpoint Definitions are Spread Across Multiple Locations

**Backend:** Endpoints defined in router files with inline path strings
```python
# backend/app/api/v1/test.py
@router.post("/submit", response_model=SubmitTestResponse)
async def submit_test(submission: ResponseSubmission, ...):
```

**iOS:** Endpoints defined in an enum with computed paths
```swift
// ios/AIQ/Services/API/APIClient.swift
enum APIEndpoint: Equatable {
    case testSubmit   // POST /v1/test/submit

    var path: String {
        switch self {
        case .testSubmit: return "/test/submit"
        }
    }
}
```

Both maintain their own URL path strings independently.

## Solution Evaluation

### Option 1: Protocol Buffers + gRPC

**Pros:**
- Binary format is more efficient than JSON
- Strong typing enforced across all platforms
- Excellent for high-performance, low-latency scenarios
- Forces contract-first development

**Cons for AIQ:**
- Requires replacing the entire FastAPI REST architecture
- gRPC has limited browser support (would need gRPC-Web gateway)
- Overkill for a mobile app with moderate API usage
- Significant migration effort with no immediate user benefit
- Team would need to learn new tooling

**Verdict:** Not recommended. The overhead of migrating to gRPC exceeds the benefits for this use case.

### Option 2: OpenAPI with Swift Code Generation (Recommended)

**Pros:**
- FastAPI already generates OpenAPI specs automatically
- Apple's Swift OpenAPI Generator provides official, maintained tooling
- Build-time code generation catches contract drift at compile time
- No changes to backend architecture required
- Leverages existing investment in Pydantic schemas
- Human-readable specs for documentation and discussion

**Cons:**
- Generated code may not match existing coding style
- Initial setup effort to integrate the generator
- Need to ensure OpenAPI spec is complete and accurate

**Verdict:** Strongly recommended. This is the most pragmatic path forward.

### Option 3: Status Quo with Better Process

**Pros:**
- No tooling changes
- Team already understands the workflow

**Cons:**
- Relies entirely on human diligence
- No compile-time verification
- Contract drift remains a risk
- Discoverability problem persists

**Verdict:** Not recommended as a long-term solution.

### Option 4: Shared TypeScript/JSON Schema

Some teams use JSON Schema as an intermediate format with code generation for both platforms.

**Pros:**
- Language-agnostic specification
- Good ecosystem support

**Cons:**
- FastAPI doesn't natively generate JSON Schema (uses OpenAPI)
- Would require custom tooling
- Less mature Swift code generation options

**Verdict:** Inferior to OpenAPI for this stack.

## Recommendations

| Priority | Recommendation | Effort | Impact |
|----------|---------------|--------|--------|
| High | Adopt OpenAPI as single source of truth | Medium | High |
| High | Integrate Swift OpenAPI Generator | Medium | High |
| Medium | Add contract validation to CI/CD | Low | Medium |
| Medium | Export OpenAPI spec to repository | Low | Medium |
| Low | Add API versioning headers | Low | Low |

### Detailed Recommendations

#### 1. Adopt OpenAPI as the Single Source of Truth

**Problem:** API specifications are duplicated between backend Pydantic schemas and iOS Codable structs.

**Solution:**
- Recognize the OpenAPI spec generated by FastAPI as the authoritative contract
- Export the spec to the repository (e.g., `docs/api/openapi.json`) on each backend deploy
- Use this exported spec for iOS code generation

**Files Affected:**
- Add CI step to export OpenAPI spec on backend changes
- Create `docs/api/` directory for spec storage

#### 2. Integrate Apple's Swift OpenAPI Generator

**Problem:** iOS models are manually written and can drift from backend.

**Solution:**
- Add `swift-openapi-generator` as a Swift Package dependency
- Configure it to generate client code from the OpenAPI spec
- Replace manually-written API models with generated types

**Implementation Approach:**
```swift
// Package.swift
.package(url: "https://github.com/apple/swift-openapi-generator", from: "1.0.0"),
```

**Benefits:**
- Build-time verification that iOS matches the contract
- Generated code includes all response fields (no accidental omissions)
- Automatic snake_case to camelCase conversion
- Type-safe operation methods replace manual endpoint definitions

**Trade-offs:**
- Generated code style may differ from existing code
- May need to wrap generated types for UI-specific computed properties
- Initial migration requires updating all API call sites

#### 3. Add Contract Validation to CI/CD

**Problem:** Contract drift can go unnoticed until runtime.

**Solution:**
- Add a CI step that regenerates iOS client code and fails if there are differences
- Use schema diffing tools to detect breaking changes in the OpenAPI spec

**Example CI Check:**
```yaml
- name: Verify API contract sync
  run: |
    swift package plugin generate-openapi-spec
    diff -q generated/ current/ || exit 1
```

#### 4. Export OpenAPI Spec to Repository

**Problem:** The OpenAPI spec is only available from the running server.

**Solution:**
- Add a script to export the OpenAPI JSON during backend CI/CD
- Commit the spec to `docs/api/openapi.json`
- iOS CI can then use this checked-in spec for generation

**Script:**
```bash
# scripts/export-openapi.sh
curl https://aiq-backend-production.up.railway.app/v1/openapi.json > docs/api/openapi.json
```

## Why Not Protobuf?

Protobuf is excellent for:
- High-frequency internal microservice communication
- Bandwidth-constrained environments
- Scenarios requiring maximum serialization performance

Protobuf is overkill for AIQ because:
1. **Low API call frequency:** Users take tests infrequently (daily/weekly), not thousands of requests per second
2. **Payload size is small:** Test questions and results are kilobytes, not megabytes
3. **Existing architecture works well:** FastAPI + REST is appropriate for this use case
4. **Migration cost:** Would require rewriting both backend and iOS networking layers
5. **Human readability:** JSON is debuggable with standard tools; Protobuf requires specialized tooling

The right use case for Protobuf in a mobile app would be something like a real-time gaming backend, chat application, or streaming data scenario - not a cognitive testing app with occasional API calls.

## Implementation Roadmap

### Phase 1: Spec Export (1 task)
1. Add CI step to export OpenAPI spec to repository after backend deploys
2. Commit initial `docs/api/openapi.json`

### Phase 2: Generator Integration (3-4 tasks)
1. Add Swift OpenAPI Generator to iOS project
2. Configure generator with OpenAPI spec path
3. Generate initial client code
4. Create wrapper types for UI-specific computed properties

### Phase 3: Migration (5-6 tasks)
1. Replace `APIEndpoint` enum with generated operation methods
2. Update `APIClient` to use generated request/response types
3. Migrate model files to use generated types (with extension files for computed properties)
4. Update ViewModels to use new API interface
5. Remove manual `CodingKeys` mappings (now handled by generator)

### Phase 4: CI/CD Integration (2 tasks)
1. Add CI step to verify generated code matches checked-in code
2. Add breaking change detection for OpenAPI spec modifications

## Appendix

### Files Analyzed

**iOS Networking Layer:**
- `ios/AIQ/Services/API/APIClient.swift` (614 lines)
- `ios/AIQ/Services/API/RequestInterceptor.swift`
- `ios/AIQ/Services/API/RetryPolicy.swift`
- `ios/AIQ/Services/API/NetworkLogger.swift`
- `ios/AIQ/Services/API/NetworkMonitor.swift`
- `ios/AIQ/Services/Auth/TokenRefreshInterceptor.swift`

**iOS Models:**
- `ios/AIQ/Models/Auth.swift`
- `ios/AIQ/Models/User.swift`
- `ios/AIQ/Models/Question.swift`
- `ios/AIQ/Models/TestSession.swift`
- `ios/AIQ/Models/TestResult.swift`
- `ios/AIQ/Models/Feedback.swift`
- `ios/AIQ/Models/APIError.swift`

**Backend Schemas:**
- `backend/app/schemas/auth.py`
- `backend/app/schemas/responses.py`
- `backend/app/schemas/test_sessions.py`
- `backend/app/schemas/questions.py`
- `backend/app/schemas/notifications.py`
- `backend/app/schemas/feedback.py`
- Plus 11 additional admin/analytics schemas

**Backend Routers:**
- `backend/app/api/v1/api.py`
- `backend/app/api/v1/auth.py`
- `backend/app/api/v1/test.py`
- `backend/app/api/v1/user.py`
- Plus notification, feedback, and admin routers

**Documentation:**
- `ios/docs/BACKEND_COORDINATION.md`
- `backend/README.md`

### Related Resources

- [Apple Swift OpenAPI Generator](https://github.com/apple/swift-openapi-generator) - Official Swift package for OpenAPI code generation
- [Introducing Swift OpenAPI Generator](https://www.swift.org/blog/introducing-swift-openapi-generator/) - Swift.org blog post
- [Meet Swift OpenAPI Generator - WWDC23](https://developer.apple.com/videos/play/wwdc2023/10171/) - Apple developer session
- [Practicing Spec-Driven API Development](https://swiftinit.org/docs/swift-openapi-generator/swift_openapi_generator/practicing-spec-driven-api-development) - Best practices guide
- [How to Build Robust Networking Layers in Swift with OpenAPI](https://www.freecodecamp.org/news/how-to-build-robust-networking-layers-in-swift-with-openapi/) - Tutorial
- [The Modern Way of Managing APIs Using Protobuf and OpenAPI](https://dev.to/apssouza22/the-modern-way-of-managing-apis-using-protobuf-and-openapi-4366) - Comparison article
- [API Design Best Practices in 2025](https://myappapi.com/blog/api-design-best-practices-2025) - Industry trends
