# Redis Rate Limiting

Both the global rate limiter and feedback rate limiter support Redis for multi-worker deployments. When `RATE_LIMIT_STORAGE=redis` is set, the rate limiters use Redis for shared state across workers. If Redis is unavailable, they gracefully fall back to in-memory storage.

## Configuration

**Local Development (no Redis)**:
```bash
# Uses in-memory storage by default
RATE_LIMIT_STORAGE=memory
```

**Production with Redis**:
```bash
# Enable Redis storage
RATE_LIMIT_STORAGE=redis

# Development (local Redis)
RATE_LIMIT_REDIS_URL=redis://localhost:6379/0

# Production (TLS + auth)
RATE_LIMIT_REDIS_URL=rediss://:${REDIS_PASSWORD}@${REDIS_HOST}:6379/0
```

## Security Checklist (Production)

- [ ] Use `rediss://` (TLS) instead of `redis://`
- [ ] Enable Redis AUTH with strong password (32+ chars)
- [ ] Bind to private network interfaces only
- [ ] Keep behind firewall, not public internet

## Error Handling

- Redis connection failures are logged but don't crash the application
- Automatic fallback to in-memory storage if Redis is unavailable
- Rate limiting continues to work (within single worker) even if Redis fails
