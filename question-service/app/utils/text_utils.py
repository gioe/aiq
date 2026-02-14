"""Shared text utility functions for the question service.

Provides common text processing functions used across providers
and other modules.
"""

import re


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

    # Pattern matches ```json or ``` at start, content, then ``` at end
    pattern = r"^```(?:json)?\s*\n?(.*?)\n?```$"
    match = re.match(pattern, text.strip(), re.DOTALL)
    if match:
        return match.group(1).strip()

    return text
