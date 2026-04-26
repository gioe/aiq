"""Shared text utility functions for the question service.

Provides common text processing functions used across providers
and other modules.
"""

import json
import logging
import re
from typing import Any, Dict

logger = logging.getLogger(__name__)


def safe_json_loads(text: str) -> Dict[str, Any]:
    """Parse a JSON object from text that may contain extra data.

    LLMs sometimes return concatenated JSON objects (e.g. two objects
    separated by a newline). Standard json.loads() raises
    ``json.JSONDecodeError`` with "Extra data" in this case.
    This function strips markdown fencing first, then uses
    ``json.JSONDecoder.raw_decode`` to extract only the first
    valid JSON object.

    Args:
        text: Raw text from an LLM response.

    Returns:
        The first parsed JSON object as a dict.

    Raises:
        json.JSONDecodeError: If no valid JSON object can be parsed.
    """
    cleaned = strip_markdown_code_blocks(text)
    try:
        return json.loads(cleaned)  # type: ignore[no-any-return]
    except json.JSONDecodeError as exc:
        if "Extra data" not in str(exc):
            raise
        logger.warning(
            "LLM response contained extra data after first JSON object; "
            "extracting first object only (pos %s)",
            exc.pos,
        )
        decoder = json.JSONDecoder()
        result, _ = decoder.raw_decode(cleaned)
        return result  # type: ignore[no-any-return]


def strip_markdown_code_blocks(text: str) -> str:
    """Strip markdown code blocks from text.

    LLMs often wrap JSON responses in markdown code blocks like:
    ```json
    {...}
    ```

    This function extracts the content from such blocks.

    Args:
        text: Raw text that may contain markdown code blocks

    Returns:
        Text with markdown code blocks stripped, or original text if no blocks found
    """
    if not text:
        return text

    stripped = text.strip()
    opening_fence = re.match(r"^```(?:json)?\s*\n?", stripped)
    if opening_fence:
        content = stripped[opening_fence.end() :]
        closing_fence = re.search(r"\n?```$", content)
        if closing_fence:
            content = content[: closing_fence.start()]
        return content.strip()

    return text
