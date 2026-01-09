# Rate Limiter Module

A flexible, library-ready rate limiting solution for FastAPI applications with multiple strategies, pluggable storage backends, and comprehensive configuration options.

## Features

- ✅ **Multiple Strategies**: Token Bucket, Sliding Window, Fixed Window
- ✅ **Pluggable Storage**: In-memory (with Redis-ready interface)
- ✅ **FastAPI Integration**: Middleware and dependency injection
- ✅ **Per-Endpoint Limits**: Configure different limits for different endpoints
- ✅ **Rate Limit Headers**: Automatic X-RateLimit-* headers in responses
- ✅ **Library-Ready**: Clean interfaces, well-tested, easily extractable
- ✅ **Thread-Safe**: Safe for concurrent use
- ✅ **Comprehensive Tests**: Full test coverage

## Quick Start

### Basic Usage

```python
from fastapi import FastAPI
from app.ratelimit import RateLimiter, RateLimitMiddleware, RateLimitConfig

app = FastAPI()

# Create rate limiter with default configuration
config = RateLimitConfig(
    strategy="token_bucket",
    default_limit=100,  # 100 requests
    default_window=60,  # per 60 seconds
)

limiter = RateLimiter(
    default_limit=config.default_limit,
    default_window=config.default_window
)

# Add middleware
app.add_middleware(
    RateLimitMiddleware,
    limiter=limiter,
    skip_paths=config.skip_paths
)
```

### With Per-Endpoint Limits

```python
from app.ratelimit import RateLimitConfig, RateLimitPresets

# Use a preset configuration
config = RateLimitPresets.MODERATE

# Or create custom configuration with per-endpoint limits
config = RateLimitConfig(
    strategy="sliding_window",
    default_limit=100,
    default_window=60,
    endpoint_limits={
        "/v1/auth/login": {"limit": 5, "window": 300},  # 5 per 5 minutes
        "/v1/auth/register": {"limit": 3, "window": 3600"},  # 3 per hour
    }
)
```

### Using User ID Instead of IP

```python
from app.ratelimit import RateLimitMiddleware, get_user_identifier

app.add_middleware(
    RateLimitMiddleware,
    limiter=limiter,
    identifier_resolver=get_user_identifier  # Uses user ID if authenticated
)
```

## Strategies

### Token Bucket

**Best for**: APIs that need to allow occasional bursts while maintaining an average rate.

```python
from app.ratelimit import TokenBucketStrategy, InMemoryStorage

storage = InMemoryStorage()
strategy = TokenBucketStrategy(storage)
limiter = RateLimiter(strategy=strategy)
```

**Characteristics**:
- Allows bursts up to the limit
- Tokens refill at a constant rate
- Good balance between strictness and flexibility

### Sliding Window

**Best for**: High-precision rate limiting with accurate enforcement.

```python
from app.ratelimit import SlidingWindowStrategy

strategy = SlidingWindowStrategy(storage)
limiter = RateLimiter(strategy=strategy)
```

**Characteristics**:
- Most accurate rate limiting
- No edge case bursts at window boundaries
- Slightly more memory usage

### Fixed Window

**Best for**: Simple rate limiting where edge cases are acceptable.

```python
from app.ratelimit import FixedWindowStrategy

strategy = FixedWindowStrategy(storage)
limiter = RateLimiter(strategy=strategy)
```

**Characteristics**:
- Simplest implementation
- Lowest memory usage
- Possible 2x burst at window boundaries

## Storage Backends

### In-Memory Storage

**Current implementation**. Thread-safe with automatic cleanup of expired entries and LRU eviction to prevent memory exhaustion.

```python
from app.ratelimit import InMemoryStorage

# Basic usage with default settings
storage = InMemoryStorage()

# With custom cleanup interval and max keys
storage = InMemoryStorage(
    cleanup_interval=60,  # Cleanup expired entries every 60 seconds
    max_keys=100000       # Maximum 100k keys (LRU eviction when exceeded)
)

# Unlimited keys (not recommended for production)
storage = InMemoryStorage(max_keys=0)  # 0 = unlimited
```

**Features**:
- **TTL-based cleanup**: Expired entries are automatically removed
- **LRU eviction**: When `max_keys` is exceeded, least recently used entries are evicted
- **Memory protection**: Prevents memory exhaustion attacks from unique identifiers
- **Thread-safe**: Safe for concurrent access with RLock

**Limitations**:
- Data lost on process restart
- Not suitable for multi-worker deployments (each worker has its own memory)

**Recommended Settings**:
- Development: `max_keys=10000` (10k keys)
- Production: `max_keys=100000` (100k keys, default)
- High-traffic: Consider Redis storage instead

### Redis Storage (Future)

**Interface ready** for Redis implementation. Example:

```python
# Future implementation
from app.ratelimit import RedisStorage
import redis

redis_client = redis.Redis(host='localhost', port=6379)
storage = RedisStorage(redis_client)
```

## Configuration

### Presets

```python
from app.ratelimit import RateLimitPresets

# Strict limits (for sensitive endpoints)
RateLimitPresets.STRICT  # 10 req/min, strict limits on auth endpoints

# Moderate limits (good default)
RateLimitPresets.MODERATE  # 100 req/min

# Generous limits (for development)
RateLimitPresets.GENEROUS  # 1000 req/min

# Disabled (no rate limiting)
RateLimitPresets.DISABLED
```

### Custom Configuration

```python
from app.ratelimit import RateLimitConfig

config = RateLimitConfig(
    strategy="token_bucket",          # Algorithm to use
    default_limit=100,                 # Default max requests
    default_window=60,                 # Default time window (seconds)
    storage_type="memory",             # Storage backend
    enabled=True,                      # Enable/disable rate limiting
    add_headers=True,                  # Add X-RateLimit-* headers
    skip_paths=["/health", "/docs"],   # Paths to skip
    endpoint_limits={                  # Per-endpoint overrides
        "/v1/auth/login": {"limit": 5, "window": 300},
        "/v1/auth/register": {"limit": 3, "window": 3600},
    }
)
```

## Response Headers

When rate limiting is active, responses include these headers:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1234567890
```

When rate limit is exceeded (429 status):

```
HTTP/1.1 429 Too Many Requests
Retry-After: 30
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1234567890

{
  "error": "rate_limit_exceeded",
  "message": "Too many requests. Please try again later.",
  "retry_after": 30
}
```

## Testing

The module includes comprehensive tests:

```bash
pytest tests/test_ratelimit_*.py -v
```

### Example: Manual Testing

```python
from app.ratelimit import RateLimiter

limiter = RateLimiter(default_limit=3, default_window=10)

# Check rate limit
for i in range(5):
    allowed, metadata = limiter.check("user123")
    print(f"Request {i+1}: Allowed={allowed}, Remaining={metadata['remaining']}")

# Reset rate limit
limiter.reset("user123")
```

## Architecture

```
┌─────────────────────┐
│   FastAPI App       │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  RateLimitMiddleware│
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│    RateLimiter      │
└──────┬───────┬──────┘
       │       │
   ┌───▼───┐ ┌▼──────────┐
   │Strategy│ │  Storage  │
   └───┬───┘ └───────────┘
       │
   ┌───▼───────────────┐
   │ • TokenBucket     │
   │ • SlidingWindow   │
   │ • FixedWindow     │
   └───────────────────┘
```

## Future Enhancements

- [ ] Redis storage backend
- [ ] Distributed rate limiting across multiple servers
- [ ] Rate limit analytics and monitoring
- [ ] Custom rate limit response handlers
- [ ] Rate limit by API key
- [ ] Dynamic rate limit adjustment
- [ ] Extract as standalone library

## License

Part of the AIQ project.
