"""Tests for shared text utility functions."""

import json

import pytest

from app.utils.text_utils import safe_json_loads, strip_markdown_code_blocks


class TestStripMarkdownCodeBlocks:
    """Tests for strip_markdown_code_blocks function."""

    def test_strips_json_code_block(self):
        """Test stripping ```json ... ``` blocks."""
        text = '```json\n{"key": "value"}\n```'
        assert strip_markdown_code_blocks(text) == '{"key": "value"}'

    def test_strips_plain_code_block(self):
        """Test stripping ``` ... ``` blocks without language."""
        text = '```\n{"key": "value"}\n```'
        assert strip_markdown_code_blocks(text) == '{"key": "value"}'

    def test_returns_plain_text_unchanged(self):
        """Test that plain text without code blocks is returned as-is."""
        text = '{"key": "value"}'
        assert strip_markdown_code_blocks(text) == '{"key": "value"}'

    def test_handles_empty_string(self):
        """Test that empty string returns empty string."""
        assert strip_markdown_code_blocks("") == ""

    def test_handles_none_like_empty(self):
        """Test that falsy values are returned as-is."""
        assert strip_markdown_code_blocks("") == ""

    def test_strips_surrounding_whitespace(self):
        """Test that surrounding whitespace is handled."""
        text = '  ```json\n{"key": "value"}\n```  '
        assert strip_markdown_code_blocks(text) == '{"key": "value"}'

    def test_multiline_json(self):
        """Test stripping code blocks with multiline JSON content."""
        text = '```json\n{\n  "key": "value",\n  "items": [1, 2, 3]\n}\n```'
        result = strip_markdown_code_blocks(text)
        assert '"key": "value"' in result
        assert '"items": [1, 2, 3]' in result

    def test_no_match_partial_fences(self):
        """Test that partial fences don't match."""
        text = '```json\n{"key": "value"}'
        assert strip_markdown_code_blocks(text) == text


class TestSafeJsonLoads:
    """Tests for safe_json_loads function."""

    def test_single_json_object(self):
        """Single valid JSON object parses normally."""
        text = '{"key": "value", "count": 42}'
        result = safe_json_loads(text)
        assert result == {"key": "value", "count": 42}

    def test_concatenated_json_objects(self):
        """Two concatenated JSON objects returns only the first."""
        text = '{"a": 1}\n{"b": 2}'
        result = safe_json_loads(text)
        assert result == {"a": 1}

    def test_concatenated_json_no_newline(self):
        """Concatenated JSON without newline separator."""
        text = '{"a": 1}{"b": 2}'
        result = safe_json_loads(text)
        assert result == {"a": 1}

    def test_markdown_wrapped_concatenated_json(self):
        """Markdown-wrapped response with concatenated JSON."""
        text = '```json\n{"a": 1}\n{"b": 2}\n```'
        result = safe_json_loads(text)
        assert result == {"a": 1}

    def test_markdown_wrapped_single_json(self):
        """Markdown-wrapped single JSON object."""
        text = '```json\n{"key": "value"}\n```'
        result = safe_json_loads(text)
        assert result == {"key": "value"}

    def test_empty_response_raises(self):
        """Empty string raises JSONDecodeError."""
        with pytest.raises(json.JSONDecodeError):
            safe_json_loads("")

    def test_invalid_json_raises(self):
        """Completely invalid JSON raises JSONDecodeError."""
        with pytest.raises(json.JSONDecodeError):
            safe_json_loads("not json at all")
