# Security Event Logging

The backend includes a dedicated security audit logging system for tracking security-relevant events. This provides an audit trail for compliance, incident investigation, and attack detection.

## Security Event Types

| Event | Description |
|-------|-------------|
| `LOGIN_SUCCESS` | Successful user authentication |
| `LOGIN_FAILED` | Failed login attempt (wrong password, user not found) |
| `TOKEN_VALIDATION_FAILED` | Token validation failure (expired, invalid, revoked) |
| `TOKEN_REVOKED` | User logout or forced token revocation |
| `PERMISSION_DENIED` | Unauthorized access attempt (403) |
| `ADMIN_AUTH_FAILED` | Failed admin token validation |
| `SERVICE_AUTH_FAILED` | Failed service key validation |
| `PASSWORD_RESET_INITIATED` | Password reset request submitted |
| `PASSWORD_RESET_COMPLETED` | Password reset successfully completed |
| `PASSWORD_RESET_FAILED` | Password reset token validation failed |
| `RATE_LIMIT_EXCEEDED` | Request blocked by rate limiter |
| `ACCOUNT_CREATED` | New user registration |
| `ACCOUNT_DELETED` | User account deletion |

## Log Format

Security events are logged with consistent structured fields:

```json
{
  "timestamp": "2026-01-24T10:30:15.123456+00:00",
  "level": "WARNING",
  "logger": "app.core.security_audit",
  "message": "SECURITY_EVENT: LOGIN_FAILED",
  "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "event_type": "LOGIN_FAILED",
  "email": "joh***@example.com",
  "client_ip": "10.0.0.1",
  "user_agent": "Mozilla/5.0...",
  "reason": "invalid_password"
}
```

## Sensitive Data Handling

The security logger implements privacy protections:

- **Email Masking**: Emails are displayed as `abc***@domain.com` (first 3 chars + masked + domain)
- **Token JTI Partial**: Only first 8 characters of token JTI are logged
- **No Passwords**: Passwords are never logged under any circumstance
- **No Full Tokens**: Access/refresh tokens are never logged

## Integration Points

Security events are automatically logged at these locations:

| Location | Events Logged |
|----------|---------------|
| `app/api/v1/auth.py` | Login, registration, logout, password reset |
| `app/core/auth.py` | Token validation failures |
| `app/api/v1/admin/_dependencies.py` | Admin/service authentication |

## Usage in Custom Code

```python
from app.core.security_audit import security_logger, SecurityEventType

# Log a permission denied event
security_logger.log_permission_denied(
    user_id="user-123",
    resource="/v1/admin/users",
    action="GET",
    ip="10.0.0.1"
)

# Log a custom security event
security_logger.log_security_event(
    event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
    message="Rate limit exceeded",
    ip="10.0.0.1",
    extra={"endpoint": "/v1/test/start", "limit": "5/5min"}
)
```

## Monitoring and Alerting

In production, security events can be filtered and alerted on:

```bash
# Railway logs - filter for security events
railway logs | grep "SECURITY_EVENT"

# Filter by event type
railway logs | grep "LOGIN_FAILED"

# High-priority events (WARNING/ERROR level)
railway logs | grep -E "(LOGIN_FAILED|ADMIN_AUTH_FAILED|TOKEN_VALIDATION_FAILED)"
```

Recommended alerting thresholds:
- 5+ `LOGIN_FAILED` from same IP in 5 minutes: Potential brute force
- Any `ADMIN_AUTH_FAILED`: Investigate immediately
- 10+ `TOKEN_VALIDATION_FAILED` in 1 minute: Potential token theft/replay
