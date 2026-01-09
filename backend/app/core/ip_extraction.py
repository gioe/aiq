"""
Secure IP address extraction utilities.

This module provides secure IP extraction that prevents header spoofing attacks.
For use in rate limiting and other IP-based security features.

Security Context:
Railway.app (our production environment) uses Envoy proxy, which sets the
X-Envoy-External-Address header with the actual client IP. This header is
set by the infrastructure and cannot be spoofed by clients.

WARNING: Do NOT use X-Forwarded-For or X-Real-IP headers for security-sensitive
operations. These headers can be easily spoofed by clients.

References:
- Railway IP extraction: https://manikumar.in/blog/railway.app-fastapi-client-ip-using-envoy-headers/
- FastAPI behind proxy: https://fastapi.tiangolo.com/advanced/behind-a-proxy/
- X-Forwarded-For injection: https://github.com/rennf93/fastapi-guard/security/advisories/GHSA-77q8-qmj7-x7pp
"""

from fastapi import Request


def get_secure_client_ip(request: Request) -> str:
    """
    Securely extract the real client IP address from request.

    This function uses ONLY trusted headers set by infrastructure proxies,
    specifically the X-Envoy-External-Address header from Railway's Envoy proxy.

    Security rationale:
    - X-Forwarded-For is UNTRUSTED: clients can inject arbitrary values
    - X-Real-IP is UNTRUSTED: clients can inject arbitrary values
    - X-Envoy-External-Address is TRUSTED: set by Railway's infrastructure
    - request.client.host is RELIABLE: direct connection IP (for local dev)

    For rate limiting to be effective, we must use a header that attackers
    cannot manipulate to bypass limits.

    Args:
        request: FastAPI request object

    Returns:
        Client IP address as string, or "unknown" if unavailable
    """
    # Priority 1: X-Envoy-External-Address (Railway-specific, infrastructure-set)
    # This is the ONLY header we trust for proxied requests on Railway
    envoy_ip = request.headers.get("X-Envoy-External-Address")
    if envoy_ip:
        # Handle potential comma-separated values (defensive coding)
        return envoy_ip.split(",")[0].strip()

    # Priority 2: Direct client IP (for local development without proxy)
    # When running locally, there's no proxy, so request.client.host is accurate
    if request.client:
        return request.client.host

    # Priority 3: Unknown fallback (should rarely occur)
    # This happens only if request.client is None (very unusual)
    return "unknown"
