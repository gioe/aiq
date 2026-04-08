"""
Prompt templates for LLM benchmark question-answering.

Each question type gets its own template. All prompts instruct the model to
respond with a JSON object of the form {"answer": "..."}.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.models import Question

logger = logging.getLogger(__name__)

_SYSTEM_PREAMBLE = (
    "You are taking a cognitive assessment test. "
    "Read the question carefully and answer it to the best of your ability. "
    'Respond ONLY with a valid JSON object in the format: {"answer": "..."}. '
    "Do not include any explanation, commentary, or additional keys."
)

_MULTIPLE_CHOICE_NOTE = (
    "For multiple-choice questions, return the full text of the answer you choose "
    "(not the option letter or number)."
)


def _format_options(answer_options: list[str]) -> str:
    """Return a numbered list of answer options as a string."""
    return "\n".join(f"{i + 1}. {opt}" for i, opt in enumerate(answer_options))


def _build_pattern_prompt(question: "Question") -> str:
    lines = [
        _SYSTEM_PREAMBLE,
        "",
        "QUESTION TYPE: Pattern Recognition",
        "",
        f"Question: {question.question_text}",
    ]
    if question.answer_options:
        options = (
            question.answer_options
            if isinstance(question.answer_options, list)
            else json.loads(question.answer_options)
        )
        lines.append("")
        lines.append("Options:")
        lines.append(_format_options(options))
        lines.append("")
        lines.append(_MULTIPLE_CHOICE_NOTE)
    return "\n".join(lines)


def _build_logic_prompt(question: "Question") -> str:
    lines = [
        _SYSTEM_PREAMBLE,
        "",
        "QUESTION TYPE: Logical Reasoning",
        "",
        f"Question: {question.question_text}",
    ]
    if question.answer_options:
        options = (
            question.answer_options
            if isinstance(question.answer_options, list)
            else json.loads(question.answer_options)
        )
        lines.append("")
        lines.append("Options:")
        lines.append(_format_options(options))
        lines.append("")
        lines.append(_MULTIPLE_CHOICE_NOTE)
    return "\n".join(lines)


def _build_spatial_prompt(question: "Question") -> str:
    lines = [
        _SYSTEM_PREAMBLE,
        "",
        "QUESTION TYPE: Spatial Reasoning",
        "",
        f"Question: {question.question_text}",
    ]
    if question.answer_options:
        options = (
            question.answer_options
            if isinstance(question.answer_options, list)
            else json.loads(question.answer_options)
        )
        lines.append("")
        lines.append("Options:")
        lines.append(_format_options(options))
        lines.append("")
        lines.append(_MULTIPLE_CHOICE_NOTE)
    return "\n".join(lines)


def _build_math_prompt(question: "Question") -> str:
    lines = [
        _SYSTEM_PREAMBLE,
        "",
        "QUESTION TYPE: Mathematical Reasoning",
        "",
        f"Question: {question.question_text}",
    ]
    if question.answer_options:
        options = (
            question.answer_options
            if isinstance(question.answer_options, list)
            else json.loads(question.answer_options)
        )
        lines.append("")
        lines.append("Options:")
        lines.append(_format_options(options))
        lines.append("")
        lines.append(_MULTIPLE_CHOICE_NOTE)
    return "\n".join(lines)


def _build_verbal_prompt(question: "Question") -> str:
    lines = [
        _SYSTEM_PREAMBLE,
        "",
        "QUESTION TYPE: Verbal Reasoning",
        "",
        f"Question: {question.question_text}",
    ]
    if question.answer_options:
        options = (
            question.answer_options
            if isinstance(question.answer_options, list)
            else json.loads(question.answer_options)
        )
        lines.append("")
        lines.append("Options:")
        lines.append(_format_options(options))
        lines.append("")
        lines.append(_MULTIPLE_CHOICE_NOTE)
    return "\n".join(lines)


def _build_memory_prompt(question: "Question") -> str:
    # LLMs see the full prompt at once, so we present the stimulus inline
    # with the question rather than simulating the timed exposure that humans get.
    lines = [_SYSTEM_PREAMBLE, "", "QUESTION TYPE: Working Memory", ""]

    if question.stimulus:
        lines.append("Study the following information carefully:")
        lines.append("")
        lines.append(question.stimulus)
        lines.append("")

    lines.append(f"Question: {question.question_text}")

    if question.answer_options:
        options = (
            question.answer_options
            if isinstance(question.answer_options, list)
            else json.loads(question.answer_options)
        )
        lines.append("")
        lines.append("Options:")
        lines.append(_format_options(options))
        lines.append("")
        lines.append(_MULTIPLE_CHOICE_NOTE)

    return "\n".join(lines)


# Map question type values to builder functions
_BUILDERS = {
    "pattern": _build_pattern_prompt,
    "logic": _build_logic_prompt,
    "spatial": _build_spatial_prompt,
    "math": _build_math_prompt,
    "verbal": _build_verbal_prompt,
    "memory": _build_memory_prompt,
}


def build_prompt(question: "Question") -> str:
    """Build the full prompt string for a question based on its type.

    Args:
        question: A Question ORM instance with question_text, question_type,
            answer_options (JSON list or None), and optionally stimulus.

    Returns:
        A formatted prompt string that instructs the LLM to respond with
        a JSON object: {"answer": "..."}.
    """
    question_type_value = question.question_type.value
    builder = _BUILDERS.get(question_type_value)
    if builder is None:
        logger.warning(
            "No prompt builder for question type %r; falling back to generic prompt.",
            question_type_value,
        )
        # Generic fallback
        return f"{_SYSTEM_PREAMBLE}\n\nQuestion: {question.question_text}"
    return builder(question)
