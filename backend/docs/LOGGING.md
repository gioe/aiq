# Structured Logging

The backend uses structured logging with different formats based on environment.

## Formats

**Development** (`ENV=development`): Human-readable format for local debugging
```
2026-01-21 07:30:15 - app.middleware.request_logging - INFO - Request completed
```

**Production** (`ENV=production`): JSON format for log aggregation and parsing (ELK, CloudWatch, etc.)
```json
{
  "timestamp": "2026-01-21T12:30:15.123456+00:00",
  "level": "INFO",
  "logger": "app.middleware.request_logging",
  "message": "Request completed",
  "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "method": "GET",
  "path": "/v1/health",
  "status_code": 200,
  "duration_ms": 15.23,
  "client_host": "10.0.0.1",
  "user_identifier": "anonymous"
}
```

## Log Fields

| Field | Description |
|-------|-------------|
| `timestamp` | ISO 8601 format with timezone (UTC) |
| `level` | Log level (DEBUG, INFO, WARNING, ERROR) |
| `logger` | Python module name |
| `message` | Human-readable log message |
| `request_id` | Unique ID for request correlation (from `X-Request-ID` header or auto-generated) |
| `method` | HTTP method (GET, POST, etc.) |
| `path` | Request URL path |
| `status_code` | HTTP response status code |
| `duration_ms` | Request processing time in milliseconds |
| `client_host` | Client IP address |
| `user_identifier` | Token preview or "anonymous" |
| `source` | File:line (only for ERROR level logs) |
| `exception` | Stack trace (when exception occurs) |

## Request ID Correlation

- The `X-Request-ID` header is returned on all responses
- If provided in the request, it's used for tracing; otherwise auto-generated
- Use this to correlate logs across services and debug specific requests
