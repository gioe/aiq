# Trigger Service

The question generation service includes an HTTP API for manually triggering question generation jobs on-demand.

## Endpoint

**`POST /trigger`**

**Authentication:** Requires `X-Admin-Token` header matching the `ADMIN_TOKEN` environment variable.

**Request Body:**
```json
{
  "count": 50,
  "dry_run": false,
  "verbose": true
}
```

**Response (200 OK):**
```json
{
  "message": "Question generation job started (count=50, dry_run=False)",
  "status": "started",
  "timestamp": "2026-01-23T10:30:00.000000"
}
```

**Error Responses:**
- `401 Unauthorized`: Invalid or missing admin token
- `409 Conflict`: A generation job is already running
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server configuration error

## Rate Limiting

- **Limit:** 10 requests per minute per IP address
- **Window:** Fixed 60-second windows
- **Exemptions:** The `/health` endpoint is exempt

**Response Headers (all responses):**
| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Maximum requests per window (10) |
| `X-RateLimit-Remaining` | Requests remaining in current window |
| `X-RateLimit-Reset` | Unix timestamp when the window resets |
| `Retry-After` | Seconds to wait before retrying (429 responses only) |

**Implementation Details:**
- Fixed-window rate limiting algorithm
- Per-IP tracking using `X-Envoy-External-Address` header for Railway proxy environments (secure, cannot be spoofed)
- Automatic cleanup of expired entries prevents memory leaks
- Thread-safe with proper locking for concurrent requests

## Example Usage

```bash
# Trigger question generation
curl -X POST https://your-service.railway.app/trigger \
  -H "X-Admin-Token: your-secret-token" \
  -H "Content-Type: application/json" \
  -d '{"count": 50, "verbose": true}'

# Check rate limit headers
curl -i -X POST https://your-service.railway.app/trigger \
  -H "X-Admin-Token: your-secret-token" \
  -H "Content-Type: application/json" \
  -d '{"count": 10}'
```
