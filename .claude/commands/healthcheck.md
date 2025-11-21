---
description: Check if the Railway backend service is healthy
---

Check the health of the AIQ backend service deployed on Railway.

Run this command:
```bash
curl -w "\nHTTP Status: %{http_code}\nResponse Time: %{time_total}s\n" -s https://aiq-backend-production.up.railway.app/v1/health
```

Display the results in a clear format showing:
- ✅ if status is "healthy", ❌ if not
- Timestamp from response
- Service name and version
- HTTP status code (should be 200)
- Response time

If the request fails, show a clear error message with troubleshooting suggestions.
