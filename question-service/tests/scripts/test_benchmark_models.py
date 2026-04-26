"""Tests for the production benchmark CLI helper."""

from pathlib import Path
import sys

import httpx
import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import benchmark_models  # noqa: E402


class DummyClient:
    def __init__(self, status_code: int, payload: dict | None = None):
        """Create a fake HTTP client returning one configured response."""
        self.status_code = status_code
        self.payload = payload or {"detail": "Unknown vendor '__auth_check__'."}
        self.requests = []

    def post(self, url, json, headers, timeout):
        self.requests.append(
            {
                "url": url,
                "json": json,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return httpx.Response(
            self.status_code,
            json=self.payload,
            request=httpx.Request("POST", url),
        )


def test_auth_check_succeeds_on_authenticated_unknown_vendor() -> None:
    client = DummyClient(status_code=400)

    benchmark_models.check_benchmark_auth(
        client,
        "https://example.test/",
        "admin-token",
    )

    assert client.requests == [
        {
            "url": "https://example.test/v1/admin/llm-benchmark/run",
            "json": {"vendor": "__auth_check__", "model_id": "__auth_check__"},
            "headers": {"X-Admin-Token": "admin-token"},
            "timeout": 30.0,
        }
    ]


def test_auth_check_fails_on_invalid_admin_token() -> None:
    client = DummyClient(status_code=401, payload={"detail": "Invalid admin token."})

    with pytest.raises(httpx.HTTPStatusError):
        benchmark_models.check_benchmark_auth(
            client,
            "https://example.test",
            "stale-token",
        )


def test_select_models_returns_explicit_vendor_model_pairs() -> None:
    configured_models = [
        ("openai", "gpt-5.5"),
        ("anthropic", "claude-opus-4-7"),
        ("google", "gemini-2.5-pro"),
    ]

    assert benchmark_models.select_models(
        configured_models,
        ["openai/gpt-5.5", "google/gemini-2.5-pro"],
    ) == [
        ("openai", "gpt-5.5"),
        ("google", "gemini-2.5-pro"),
    ]


def test_select_models_returns_configured_models_without_targets() -> None:
    configured_models = [
        ("openai", "gpt-5.5"),
        ("anthropic", "claude-opus-4-7"),
    ]

    assert benchmark_models.select_models(configured_models, []) == configured_models


def test_select_models_rejects_malformed_target() -> None:
    with pytest.raises(ValueError, match="expected vendor/model"):
        benchmark_models.select_models([("openai", "gpt-5.5")], ["openai:gpt-5.5"])


def test_select_models_rejects_unknown_target() -> None:
    with pytest.raises(ValueError, match="not found in configured models"):
        benchmark_models.select_models(
            [("openai", "gpt-5.5")], ["google/gemini-2.5-pro"]
        )
