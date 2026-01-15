# iOS-Backend Coordination Workflow

This document describes the coordination workflow between iOS and backend development for the AIQ project. Following these patterns ensures smooth integration, clear communication, and fewer surprises during development.

## When to Coordinate

Backend coordination is needed when iOS work:

1. **Requires new API endpoints** - New features that need data from the server
2. **Changes existing API contracts** - Modifications to request/response formats
3. **Depends on backend changes** - Features blocked until backend work is complete
4. **Affects shared data models** - Changes to entities used by both iOS and backend

## Coordination Workflow

### Phase 1: Define the Contract

Before implementation begins, establish the API contract:

1. **Document the endpoint specification**:
   - HTTP method and path
   - Request body structure (JSON fields, types, required vs optional)
   - Response body structure (field names in snake_case, types, pagination if applicable)
   - Error responses (HTTP status codes and error body format)

2. **Agree on field naming**:
   - Backend uses **snake_case** for JSON fields
   - iOS uses **camelCase** internally with `CodingKeys` for mapping
   - Required backend fields should NOT be optional in iOS models

3. **Create or update Jira tickets** for both iOS and backend work, linking them as dependencies

### Phase 2: Parallel Development

Once the contract is agreed upon:

**iOS Development**:
- Create Swift models matching the contract
- Implement UI with mock data matching the expected response
- Add API endpoint definition to `APIEndpoint.swift`
- Write ViewModel with stubbed API calls

**Backend Development**:
- Implement the endpoint following the contract
- Use Pydantic schemas that match the documented response
- Write tests verifying the response structure
- Deploy to staging when ready

### Phase 3: Integration

When both sides are ready:

1. **Test against staging** - Point iOS simulator at staging backend
2. **Verify response parsing** - Check that Swift Codable decoding works correctly
3. **Test error scenarios** - Verify error handling for 4xx and 5xx responses
4. **Confirm edge cases** - Empty results, pagination boundaries, validation errors

## Communication Channels

### For Synchronous Decisions
- Jira ticket comments for design decisions
- Link related tickets with "blocks" / "is blocked by" relationships

### For Contract Documentation
- PR descriptions should include the API contract for new endpoints
- Link to Swagger/OpenAPI docs when available: `https://aiq-backend-production.up.railway.app/v1/docs`

## Common Coordination Patterns

### Pattern: New Feature with New Endpoint

1. iOS creates ticket with proposed API contract
2. Backend reviews and adjusts contract as needed
3. Both teams implement in parallel
4. iOS tests against staging once backend deploys
5. Both PRs merged together or iOS waits for backend merge

### Pattern: iOS Feature Using Existing Endpoint

1. iOS reviews existing endpoint documentation
2. iOS creates models matching the response exactly
3. iOS tests against production/staging early
4. No backend changes needed

### Pattern: Backend Breaking Change

1. Backend creates migration plan (versioned endpoints or backwards-compatible changes)
2. Backend notifies iOS team of timeline
3. iOS updates after backend deploys new version
4. Old endpoint deprecated after iOS update ships

## Checklist for New Endpoints

Before starting implementation:

- [ ] HTTP method and path documented
- [ ] Request body fields documented (names, types, required/optional)
- [ ] Response body fields documented (names in snake_case, types)
- [ ] Error responses documented (status codes, error body format)
- [ ] Authentication requirements specified (auth token, admin token, etc.)
- [ ] Jira tickets created and linked

## Schema Matching Reference

### Backend Pydantic → iOS Swift

| Pydantic Type | Swift Type | Notes |
|---------------|------------|-------|
| `str` | `String` | |
| `int` | `Int` | |
| `float` | `Double` | |
| `bool` | `Bool` | |
| `datetime` | `Date` | Use ISO8601 decoder |
| `Optional[T]` | `T?` | Swift optional |
| `List[T]` | `[T]` | Swift array |
| `dict` / JSON field | Nested struct or `[String: Any]` | Prefer typed structs |

### Field Naming

```swift
// Backend returns snake_case
{
    "user_id": 123,
    "created_at": "2024-01-15T10:30:00Z",
    "iq_score": 115
}

// iOS model with CodingKeys
struct TestResult: Codable {
    let userId: Int
    let createdAt: Date
    let iqScore: Int

    enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case createdAt = "created_at"
        case iqScore = "iq_score"
    }
}
```

## Troubleshooting Integration Issues

### Decoding Failures

1. Check field names match exactly (case-sensitive)
2. Verify types match (Int vs String, Date format)
3. Check optionality matches (required fields must not be optional in iOS)
4. Use `JSONDecoder` with `keyDecodingStrategy: .convertFromSnakeCase` or explicit `CodingKeys`

### Unexpected Nil Values

1. Verify backend actually returns the field in all cases
2. Check if field is conditionally included based on data state
3. Update iOS model optionality to match backend behavior

### Authentication Issues

1. Verify correct auth header is being sent (`Authorization: Bearer <token>`)
2. Check token expiration and refresh logic
3. Verify endpoint authentication requirements

## Related Documentation

- [iOS CODING_STANDARDS.md](./CODING_STANDARDS.md) - iOS development standards
- [Backend API Docs](https://aiq-backend-production.up.railway.app/v1/docs) - Swagger documentation
- [Architecture Overview](../../docs/architecture/OVERVIEW.md) - System architecture
