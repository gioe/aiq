"""
Tests for secure IP extraction utility (app.core.ip_extraction).

This module tests the security-critical IP extraction logic that prevents
X-Forwarded-For and X-Real-IP header spoofing attacks.
"""
from unittest.mock import MagicMock

from fastapi import Request

from app.core.ip_extraction import get_secure_client_ip


class TestGetSecureClientIP:
    """Tests for get_secure_client_ip function."""

    def _create_mock_request(
        self,
        envoy_ip: str | None = None,
        forwarded_for: str | None = None,
        real_ip: str | None = None,
        client_host: str | None = "127.0.0.1",
    ) -> MagicMock:
        """Create a mock request with specified headers."""
        request = MagicMock(spec=Request)

        # Mock headers
        headers = {}
        if envoy_ip:
            headers["X-Envoy-External-Address"] = envoy_ip
        if forwarded_for:
            headers["X-Forwarded-For"] = forwarded_for
        if real_ip:
            headers["X-Real-IP"] = real_ip
        request.headers.get = lambda key, default=None: headers.get(key, default)

        # Mock client
        if client_host:
            request.client = MagicMock()
            request.client.host = client_host
        else:
            request.client = None

        return request

    # ========== Priority 1: X-Envoy-External-Address Tests ==========

    def test_uses_envoy_external_address_when_present(self):
        """Test that X-Envoy-External-Address is used when present."""
        request = self._create_mock_request(envoy_ip="203.0.113.50")

        result = get_secure_client_ip(request)

        assert result == "203.0.113.50"

    def test_strips_whitespace_from_envoy_header(self):
        """Test that whitespace is stripped from Envoy header value."""
        request = self._create_mock_request(envoy_ip="  203.0.113.50  ")

        result = get_secure_client_ip(request)

        assert result == "203.0.113.50"

    def test_handles_comma_separated_envoy_header(self):
        """Test that only first IP is used if Envoy header has multiple values."""
        request = self._create_mock_request(envoy_ip="203.0.113.1, 10.0.0.1")

        result = get_secure_client_ip(request)

        assert result == "203.0.113.1"

    # ========== Security Tests: Spoofed Headers ==========

    def test_ignores_x_forwarded_for_header(self):
        """
        Test that X-Forwarded-For is NEVER used (security fix BTS-221).

        This is a critical security test. X-Forwarded-For can be spoofed
        by clients to bypass rate limiting.
        """
        request = self._create_mock_request(
            forwarded_for="1.2.3.4", client_host="192.168.1.100"
        )

        result = get_secure_client_ip(request)

        # MUST use client.host, not the spoofable X-Forwarded-For
        assert result == "192.168.1.100"
        assert result != "1.2.3.4"

    def test_ignores_x_real_ip_header(self):
        """
        Test that X-Real-IP is NEVER used (security fix BTS-221).

        This is a critical security test. X-Real-IP can be spoofed
        by clients to bypass rate limiting.
        """
        request = self._create_mock_request(
            real_ip="5.6.7.8", client_host="192.168.1.100"
        )

        result = get_secure_client_ip(request)

        # MUST use client.host, not the spoofable X-Real-IP
        assert result == "192.168.1.100"
        assert result != "5.6.7.8"

    def test_envoy_header_takes_priority_over_spoofed_headers(self):
        """
        Test that Envoy header takes priority over all other headers.

        When Envoy header is present (Railway infrastructure), it should
        be used regardless of any spoofed headers.
        """
        request = self._create_mock_request(
            envoy_ip="203.0.113.99",
            forwarded_for="spoofed.ip.1",
            real_ip="spoofed.ip.2",
            client_host="192.168.1.100",
        )

        result = get_secure_client_ip(request)

        assert result == "203.0.113.99"

    def test_spoofed_headers_cannot_override_envoy(self):
        """Test that spoofed headers cannot be used to override Envoy header."""
        # This test ensures an attacker can't trick the system
        request = self._create_mock_request(
            envoy_ip="203.0.113.1", forwarded_for="attacker.controlled.ip"
        )

        result = get_secure_client_ip(request)

        assert result == "203.0.113.1"
        assert "attacker" not in result.lower()

    # ========== Priority 2: request.client.host Tests ==========

    def test_uses_client_host_without_envoy_header(self):
        """Test fallback to request.client.host when no Envoy header present."""
        request = self._create_mock_request(client_host="10.0.0.50")

        result = get_secure_client_ip(request)

        assert result == "10.0.0.50"

    def test_uses_client_host_with_empty_envoy_header(self):
        """Test fallback when Envoy header is empty string."""
        request = self._create_mock_request(envoy_ip="", client_host="10.0.0.50")

        result = get_secure_client_ip(request)

        # Empty string is falsy, should fallback to client.host
        assert result == "10.0.0.50"

    # ========== Priority 3: Unknown Fallback Tests ==========

    def test_returns_unknown_when_no_client(self):
        """Test that 'unknown' is returned when request.client is None."""
        request = self._create_mock_request(client_host=None)

        result = get_secure_client_ip(request)

        assert result == "unknown"

    def test_returns_unknown_when_no_headers_and_no_client(self):
        """Test complete fallback scenario."""
        request = self._create_mock_request(client_host=None)

        result = get_secure_client_ip(request)

        assert result == "unknown"

    # ========== IPv6 Support Tests ==========

    def test_handles_ipv6_address_in_envoy_header(self):
        """Test that IPv6 addresses are handled correctly."""
        request = self._create_mock_request(envoy_ip="2001:db8::1")

        result = get_secure_client_ip(request)

        assert result == "2001:db8::1"

    def test_handles_ipv6_loopback(self):
        """Test IPv6 loopback address."""
        request = self._create_mock_request(envoy_ip="::1")

        result = get_secure_client_ip(request)

        assert result == "::1"

    # ========== Local Development Tests ==========

    def test_local_development_without_proxy(self):
        """
        Test behavior in local development (no proxy, no Envoy header).

        In local development, request.client.host provides the actual client IP.
        """
        request = self._create_mock_request(client_host="127.0.0.1")

        result = get_secure_client_ip(request)

        assert result == "127.0.0.1"

    def test_docker_compose_local_development(self):
        """Test behavior in Docker Compose local development."""
        request = self._create_mock_request(client_host="172.18.0.1")

        result = get_secure_client_ip(request)

        assert result == "172.18.0.1"


class TestSecurityScenarios:
    """
    Security scenario tests that simulate real attack patterns.

    These tests verify that the IP extraction cannot be bypassed by
    various attack techniques.
    """

    def _create_mock_request(
        self,
        envoy_ip: str | None = None,
        forwarded_for: str | None = None,
        real_ip: str | None = None,
        client_host: str = "127.0.0.1",
    ) -> MagicMock:
        """Create a mock request with specified headers."""
        request = MagicMock(spec=Request)

        headers = {}
        if envoy_ip:
            headers["X-Envoy-External-Address"] = envoy_ip
        if forwarded_for:
            headers["X-Forwarded-For"] = forwarded_for
        if real_ip:
            headers["X-Real-IP"] = real_ip
        request.headers.get = lambda key, default=None: headers.get(key, default)

        request.client = MagicMock()
        request.client.host = client_host

        return request

    def test_rate_limit_bypass_attempt_with_rotating_ips(self):
        """
        Simulate attacker rotating X-Forwarded-For IPs to bypass rate limiting.

        This attack pattern was the original vulnerability (BTS-221).
        """
        # Simulate requests from same attacker with different spoofed IPs
        spoofed_ips = ["1.1.1.1", "2.2.2.2", "3.3.3.3", "4.4.4.4"]
        actual_client_ip = "192.168.1.100"  # Attacker's real IP

        extracted_ips = []
        for spoofed_ip in spoofed_ips:
            request = self._create_mock_request(
                forwarded_for=spoofed_ip, client_host=actual_client_ip
            )
            extracted_ips.append(get_secure_client_ip(request))

        # All extracted IPs should be the same (the actual client IP)
        # NOT the spoofed IPs
        assert all(ip == actual_client_ip for ip in extracted_ips)
        assert not any(ip in spoofed_ips for ip in extracted_ips)

    def test_attacker_cannot_impersonate_another_user(self):
        """
        Test that an attacker cannot impersonate another user's IP.

        An attacker might try to set X-Forwarded-For to another user's IP
        to frame them or access their rate limit quota.
        """
        legitimate_user_ip = "203.0.113.50"
        attacker_real_ip = "198.51.100.1"

        # Attacker tries to impersonate legitimate user
        request = self._create_mock_request(
            forwarded_for=legitimate_user_ip,  # Trying to impersonate
            client_host=attacker_real_ip,  # But this is the real IP
        )

        result = get_secure_client_ip(request)

        # Should be attacker's real IP, not the impersonated IP
        assert result == attacker_real_ip
        assert result != legitimate_user_ip

    def test_proxy_chain_spoofing_attempt(self):
        """
        Test that proxy chain in X-Forwarded-For cannot be abused.

        Attackers might try to inject a chain like "trusted.proxy,attacker.ip"
        hoping the first IP in the chain is trusted.
        """
        request = self._create_mock_request(
            forwarded_for="trusted.proxy.ip, attacker.ip", client_host="192.168.1.100"
        )

        result = get_secure_client_ip(request)

        # Should NOT use any part of the spoofed X-Forwarded-For chain
        assert result == "192.168.1.100"
        assert "trusted" not in result
        assert "attacker" not in result
