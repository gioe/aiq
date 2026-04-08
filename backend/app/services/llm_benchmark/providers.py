"""
Async provider functions for calling OpenAI, Anthropic, and Google LLMs.

Each function sends a question prompt and returns the model's answer
plus token usage. Uses httpx directly — no vendor SDK dependency.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


@dataclass(frozen=True)
class LLMResponse:
    """Standardised result from any LLM provider."""

    answer: str
    input_tokens: int
    output_tokens: int
    model: str
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def _error_response(model: str, error: str) -> LLMResponse:
    return LLMResponse(
        answer="", input_tokens=0, output_tokens=0, model=model, error=error
    )


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------

_OPENAI_URL = "https://api.openai.com/v1/chat/completions"
_OPENAI_MODEL = "gpt-4o-mini"


async def complete_openai(prompt: str, *, model: str = _OPENAI_MODEL) -> LLMResponse:
    """Call the OpenAI chat completions API with JSON mode."""
    api_key = settings.LLM_OPENAI_API_KEY
    if not api_key:
        return _error_response(model, "LLM_OPENAI_API_KEY not configured")

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(_OPENAI_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        usage = data.get("usage", {})
        content = data["choices"][0]["message"]["content"]
        return LLMResponse(
            answer=content,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            model=data.get("model", model),
        )
    except httpx.HTTPStatusError as exc:
        msg = f"OpenAI API error {exc.response.status_code}: {exc.response.text[:200]}"
        logger.error(msg)
        return _error_response(model, msg)
    except httpx.HTTPError as exc:
        msg = f"OpenAI request failed: {exc}"
        logger.error(msg)
        return _error_response(model, msg)


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------

_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_MODEL = "claude-sonnet-4-20250514"


async def complete_anthropic(
    prompt: str, *, model: str = _ANTHROPIC_MODEL
) -> LLMResponse:
    """Call the Anthropic messages API."""
    api_key = settings.LLM_ANTHROPIC_API_KEY
    if not api_key:
        return _error_response(model, "LLM_ANTHROPIC_API_KEY not configured")

    payload = {
        "model": model,
        "max_tokens": 1024,
        "temperature": 0,
        "messages": [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": "{"},
        ],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(_ANTHROPIC_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        usage = data.get("usage", {})
        content_blocks = data.get("content", [])
        text = "".join(b["text"] for b in content_blocks if b.get("type") == "text")
        # Prepend the "{" consumed by the assistant prefill to reconstruct valid JSON
        text = "{" + text
        return LLMResponse(
            answer=text,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            model=data.get("model", model),
        )
    except httpx.HTTPStatusError as exc:
        msg = (
            f"Anthropic API error {exc.response.status_code}: {exc.response.text[:200]}"
        )
        logger.error(msg)
        return _error_response(model, msg)
    except httpx.HTTPError as exc:
        msg = f"Anthropic request failed: {exc}"
        logger.error(msg)
        return _error_response(model, msg)


# ---------------------------------------------------------------------------
# Google (Gemini)
# ---------------------------------------------------------------------------

_GOOGLE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
_GOOGLE_MODEL = "gemini-2.5-flash"


async def complete_google(prompt: str, *, model: str = _GOOGLE_MODEL) -> LLMResponse:
    """Call the Google Gemini generateContent API."""
    api_key = settings.LLM_GOOGLE_API_KEY
    if not api_key:
        return _error_response(model, "LLM_GOOGLE_API_KEY not configured")

    url = f"{_GOOGLE_URL}/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }
    headers = {"Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        usage = data.get("usageMetadata", {})
        candidates = data.get("candidates", [{}])
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        text = "".join(p.get("text", "") for p in parts)
        return LLMResponse(
            answer=text,
            input_tokens=usage.get("promptTokenCount", 0),
            output_tokens=usage.get("candidatesTokenCount", 0),
            model=model,
        )
    except httpx.HTTPStatusError as exc:
        msg = f"Google API error {exc.response.status_code}: {exc.response.text[:200]}"
        logger.error(msg)
        return _error_response(model, msg)
    except httpx.HTTPError as exc:
        msg = f"Google request failed: {exc}"
        logger.error(msg)
        return _error_response(model, msg)
