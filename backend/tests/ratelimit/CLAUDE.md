## Rate Limit Tests

Never use `create_application()` from `app.main` in this directory. It boots the full production stack (async DB, Sentry, OpenTelemetry) and causes event-loop conflicts with sync `TestClient`.

Use `create_test_app_with_rate_limiting()` from `conftest.py` instead. It provides a lightweight FastAPI app with stub routes and the real rate limit middleware — everything needed to test rate limiting behavior without infrastructure dependencies.
