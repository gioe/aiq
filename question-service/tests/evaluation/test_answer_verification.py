"""Tests for adversarial answer verification (verify_answer / verify_answer_async).

Covers all verification outcomes, edge cases, prompt builders,
config parsing, and runner integration (Phase 2b).
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch

from app.observability.cost_tracking import CompletionResult
from app.evaluation.judge import QuestionJudge
from app.config.judge_config import (
    DifficultyPlacement,
    JudgeConfig,
    JudgeConfigLoader,
    JudgeModel,
    EvaluationCriteria,
)
from app.data.models import (
    DifficultyLevel,
    EvaluatedQuestion,
    EvaluationScore,
    GeneratedQuestion,
    QuestionType,
)
from app.generation.prompts import (
    build_blind_solve_prompt,
    build_generator_defense_prompt,
    build_judge_final_ruling_prompt,
)


def make_completion_result(content):
    """Helper to create a CompletionResult from content."""
    return CompletionResult(content=content, token_usage=None)


@pytest.fixture
def mock_judge_config():
    """Create a mock judge config loader for verification tests."""
    config = JudgeConfig(
        version="1.0.0",
        judges={
            "math": JudgeModel(
                model="gpt-4", provider="openai", rationale="Math", enabled=True
            ),
            "logic": JudgeModel(
                model="claude-3-5-sonnet-20241022",
                provider="anthropic",
                rationale="Logic",
                enabled=True,
            ),
            "pattern": JudgeModel(
                model="gemini-pro", provider="google", rationale="Pattern", enabled=True
            ),
            "spatial": JudgeModel(
                model="gpt-4", provider="openai", rationale="Spatial", enabled=True
            ),
            "verbal": JudgeModel(
                model="claude-3-5-sonnet-20241022",
                provider="anthropic",
                rationale="Verbal",
                enabled=True,
            ),
            "memory": JudgeModel(
                model="gpt-4", provider="openai", rationale="Memory", enabled=True
            ),
        },
        default_judge=JudgeModel(
            model="gpt-4", provider="openai", rationale="Default", enabled=True
        ),
        evaluation_criteria=EvaluationCriteria(
            clarity=0.30, validity=0.40, formatting=0.15, creativity=0.15
        ),
        min_judge_score=0.7,
        difficulty_placement=DifficultyPlacement(),
    )

    loader = Mock(spec=JudgeConfigLoader)
    loader.config = config

    def _resolve(qt, available):
        judge = config.judges.get(qt, config.default_judge)
        if judge.provider in available:
            return (judge.provider, judge.model)
        if available:
            return (available[0], None)
        raise ValueError(f"No providers for '{qt}'")

    loader.resolve_judge_provider.side_effect = _resolve
    loader.get_answer_verification_enabled.return_value = True
    loader.get_evaluation_criteria.return_value = config.evaluation_criteria
    loader.get_min_judge_score.return_value = config.min_judge_score
    loader.get_difficulty_placement.return_value = config.difficulty_placement
    return loader


@pytest.fixture
def sample_question():
    """Question with 4 answer options for verification tests."""
    return GeneratedQuestion(
        question_text="Which of the following is the product of seven and eight?",
        question_type=QuestionType.MATH,
        difficulty_level=DifficultyLevel.EASY,
        correct_answer="fifty-six",
        answer_options=["forty-two", "forty-eight", "fifty-four", "fifty-six"],
        explanation="7 * 8 = 56",
        metadata={},
        source_llm="openai",
        source_model="gpt-4",
    )


@pytest.fixture
def sample_memory_question():
    """Memory question with stimulus for verification tests."""
    return GeneratedQuestion(
        question_text="Which item from the list is a mammal that is NOT the fourth item?",
        question_type=QuestionType.MEMORY,
        difficulty_level=DifficultyLevel.MEDIUM,
        correct_answer="whale",
        answer_options=["dolphin", "whale", "salmon", "cherry", "oak"],
        explanation="Whale is the mammal not at position 4.",
        stimulus="maple, oak, dolphin, cherry, whale, birch, salmon",
        metadata={},
        source_llm="openai",
        source_model="gpt-4",
    )


@pytest.fixture
def judge(mock_judge_config):
    """Create a QuestionJudge with mocked providers."""
    with patch("app.evaluation.judge.OpenAIProvider"):
        j = QuestionJudge(judge_config=mock_judge_config, openai_api_key="test-key")
    # Replace with a controllable mock provider
    mock_provider = Mock()
    mock_provider.model = "gpt-4"
    j.providers = {"openai": mock_provider}
    return j


# ---------------------------------------------------------------------------
# Prompt builder tests
# ---------------------------------------------------------------------------
class TestPromptBuilders:
    """Tests for the three adversarial verification prompt builders."""

    def test_blind_solve_prompt_basic(self):
        prompt = build_blind_solve_prompt(
            question="What is 2+2?",
            answer_options=["3", "4", "5"],
            question_type="math",
            difficulty="easy",
        )
        assert "What is 2+2?" in prompt
        assert "math" in prompt
        assert "easy" in prompt
        assert "chosen_answer" in prompt
        assert "confidence" in prompt

    def test_blind_solve_prompt_with_stimulus(self):
        prompt = build_blind_solve_prompt(
            question="Recall the items",
            answer_options=["a", "b", "c"],
            question_type="memory",
            difficulty="medium",
            stimulus="apple, banana, cherry",
        )
        assert "apple, banana, cherry" in prompt
        assert "Stimulus" in prompt

    def test_blind_solve_prompt_without_stimulus(self):
        prompt = build_blind_solve_prompt(
            question="Simple question",
            answer_options=["x", "y"],
            question_type="logic",
            difficulty="hard",
            stimulus=None,
        )
        assert "Stimulus" not in prompt

    def test_generator_defense_prompt_basic(self):
        prompt = build_generator_defense_prompt(
            question="What is 2+2?",
            answer_options=["3", "4", "5"],
            marked_correct_answer="4",
            judge_chosen_answer="3",
            judge_reasoning="I thought 2+2=3",
            question_type="math",
            difficulty="easy",
        )
        assert "YOUR MARKED ANSWER: 4" in prompt
        assert "REVIEWER'S ANSWER: 3" in prompt
        assert "CONCEDE" in prompt
        assert "DEFEND" in prompt

    def test_generator_defense_prompt_with_stimulus(self):
        prompt = build_generator_defense_prompt(
            question="Recall items",
            answer_options=["a", "b"],
            marked_correct_answer="a",
            judge_chosen_answer="b",
            judge_reasoning="reason",
            question_type="memory",
            difficulty="medium",
            stimulus="some stimulus content",
        )
        assert "some stimulus content" in prompt

    def test_judge_final_ruling_prompt_basic(self):
        prompt = build_judge_final_ruling_prompt(
            question="What is 2+2?",
            answer_options=["3", "4", "5"],
            marked_correct_answer="4",
            judge_original_answer="3",
            judge_original_reasoning="I think 3",
            generator_defense="4 is correct because...",
            question_type="math",
            difficulty="easy",
        )
        assert "GENERATOR'S MARKED ANSWER: 4" in prompt
        assert "YOUR ORIGINAL ANSWER: 3" in prompt
        assert "GENERATOR'S DEFENSE: 4 is correct because..." in prompt
        assert "ACCEPT" in prompt
        assert "REJECT" in prompt

    def test_judge_final_ruling_prompt_with_stimulus(self):
        prompt = build_judge_final_ruling_prompt(
            question="Recall items",
            answer_options=["a", "b"],
            marked_correct_answer="a",
            judge_original_answer="b",
            judge_original_reasoning="reason",
            generator_defense="defense text",
            question_type="memory",
            difficulty="hard",
            stimulus="stimulus content here",
        )
        assert "stimulus content here" in prompt


# ---------------------------------------------------------------------------
# verify_answer (sync) tests
# ---------------------------------------------------------------------------
class TestVerifyAnswer:
    """Tests for QuestionJudge.verify_answer (sync)."""

    def test_pass_judge_agrees(self, judge, sample_question):
        """Judge's blind-solve matches the marked answer → pass."""
        judge.providers[
            "openai"
        ].generate_structured_completion_with_usage.return_value = make_completion_result(
            {
                "chosen_answer": "fifty-six",
                "confidence": 0.95,
                "reasoning": "7*8=56",
            }
        )

        verified, details = judge.verify_answer(sample_question, "openai", "gpt-4")

        assert verified is True
        assert details["outcome"] == "pass"
        assert details["judge_chosen_answer"] == "fifty-six"
        assert details["confidence"] == pytest.approx(0.95)

    def test_pass_case_insensitive(self, judge, sample_question):
        """Case-insensitive comparison: 'Fifty-Six' matches 'fifty-six'."""
        judge.providers[
            "openai"
        ].generate_structured_completion_with_usage.return_value = make_completion_result(
            {
                "chosen_answer": "  Fifty-Six  ",
                "confidence": 0.9,
                "reasoning": "...",
            }
        )

        verified, details = judge.verify_answer(sample_question, "openai", "gpt-4")

        assert verified is True
        assert details["outcome"] == "pass"

    def test_concession_generator_concedes(self, judge, sample_question):
        """Mismatch → generator concedes → question rejected."""
        provider = judge.providers["openai"]
        provider.generate_structured_completion_with_usage.side_effect = [
            # Blind solve: judge picks wrong answer
            make_completion_result(
                {
                    "chosen_answer": "forty-two",
                    "confidence": 0.8,
                    "reasoning": "I think 42",
                }
            ),
            # Generator defense: concede
            make_completion_result(
                {
                    "action": "concede",
                    "reasoning": "The reviewer is correct, 42 is right",
                    "concession_answer": "forty-two",
                }
            ),
        ]

        verified, details = judge.verify_answer(sample_question, "openai", "gpt-4")

        assert verified is False
        assert details["outcome"] == "concession"
        assert details["judge_chosen_answer"] == "forty-two"

    def test_defense_accepted(self, judge, sample_question):
        """Mismatch → generator defends → judge accepts defense."""
        provider = judge.providers["openai"]
        provider.generate_structured_completion_with_usage.side_effect = [
            # Blind solve: mismatch
            make_completion_result(
                {
                    "chosen_answer": "forty-eight",
                    "confidence": 0.6,
                    "reasoning": "Hmm",
                }
            ),
            # Generator defense: defend
            make_completion_result(
                {
                    "action": "defend",
                    "reasoning": "56 is correct because 7*8=56",
                }
            ),
            # Final ruling: accept
            make_completion_result(
                {
                    "ruling": "accept",
                    "reasoning": "Generator's defense is convincing",
                }
            ),
        ]

        verified, details = judge.verify_answer(sample_question, "openai", "gpt-4")

        assert verified is True
        assert details["outcome"] == "defense_accepted"
        assert "final_ruling_reasoning" in details

    def test_defense_rejected(self, judge, sample_question):
        """Mismatch → generator defends → judge rejects defense."""
        provider = judge.providers["openai"]
        provider.generate_structured_completion_with_usage.side_effect = [
            # Blind solve: mismatch
            make_completion_result(
                {
                    "chosen_answer": "forty-eight",
                    "confidence": 0.9,
                    "reasoning": "Clearly 48",
                }
            ),
            # Generator defense: defend
            make_completion_result(
                {
                    "action": "defend",
                    "reasoning": "No, 56 is correct",
                }
            ),
            # Final ruling: reject
            make_completion_result(
                {
                    "ruling": "reject",
                    "reasoning": "The question is flawed",
                }
            ),
        ]

        verified, details = judge.verify_answer(sample_question, "openai", "gpt-4")

        assert verified is False
        assert details["outcome"] == "defense_rejected"
        assert "final_ruling_reasoning" in details
        assert "generator_defense" in details

    def test_single_option_skip(self, judge):
        """Question with fewer than 2 answer options is skipped."""
        q = Mock()
        q.question_type.value = "math"
        q.difficulty_level.value = "easy"
        q.answer_options = ["only-one"]
        q.correct_answer = "only-one"
        q.source_llm = "openai"
        q.source_model = "gpt-4"

        verified, details = judge.verify_answer(q, "openai", "gpt-4")

        assert verified is True
        assert details["outcome"] == "skipped"
        assert details["reason"] == "insufficient_answer_options"

    def test_no_answer_options_skip(self, judge):
        """Question with None answer_options is skipped."""
        q = Mock()
        q.question_type.value = "logic"
        q.difficulty_level.value = "medium"
        q.answer_options = None
        q.correct_answer = "something"

        verified, details = judge.verify_answer(q, "openai", "gpt-4")

        assert verified is True
        assert details["outcome"] == "skipped"
        assert details["reason"] == "insufficient_answer_options"

    def test_empty_answer_options_skip(self, judge):
        """Question with empty answer_options list is skipped."""
        q = Mock()
        q.question_type.value = "math"
        q.difficulty_level.value = "easy"
        q.answer_options = []
        q.correct_answer = "x"

        verified, details = judge.verify_answer(q, "openai", "gpt-4")

        assert verified is True
        assert details["outcome"] == "skipped"
        assert details["reason"] == "insufficient_answer_options"

    def test_generator_provider_unavailable_skip(self, judge, sample_question):
        """When generator provider is not available, skip with fail-open."""
        # source_llm is "openai" but only "anthropic" provider available
        judge.providers = {"anthropic": Mock()}
        judge.providers[
            "anthropic"
        ].generate_structured_completion_with_usage.return_value = make_completion_result(
            {
                "chosen_answer": "forty-two",  # mismatch triggers defense
                "confidence": 0.7,
                "reasoning": "...",
            }
        )

        verified, details = judge.verify_answer(
            sample_question, "anthropic", "claude-3-5-sonnet-20241022"
        )

        assert verified is True
        assert details["outcome"] == "skipped"
        assert details["reason"] == "generator_provider_unavailable"

    def test_error_propagates(self, judge, sample_question):
        """Exceptions during verification are re-raised."""
        judge.providers[
            "openai"
        ].generate_structured_completion_with_usage.side_effect = RuntimeError(
            "API error"
        )

        with pytest.raises(RuntimeError, match="API error"):
            judge.verify_answer(sample_question, "openai", "gpt-4")


# ---------------------------------------------------------------------------
# verify_answer_async tests
# ---------------------------------------------------------------------------
class TestVerifyAnswerAsync:
    """Tests for QuestionJudge.verify_answer_async."""

    @pytest.mark.asyncio
    async def test_pass_async(self, judge, sample_question):
        """Async path: judge agrees → pass."""
        provider = judge.providers["openai"]
        provider.generate_structured_completion_with_usage_async = AsyncMock(
            return_value=make_completion_result(
                {
                    "chosen_answer": "fifty-six",
                    "confidence": 0.95,
                    "reasoning": "7*8=56",
                }
            )
        )

        verified, details = await judge.verify_answer_async(
            sample_question, "openai", "gpt-4"
        )

        assert verified is True
        assert details["outcome"] == "pass"

    @pytest.mark.asyncio
    async def test_case_insensitive_async(self, judge, sample_question):
        """Async path: case-insensitive comparison."""
        provider = judge.providers["openai"]
        provider.generate_structured_completion_with_usage_async = AsyncMock(
            return_value=make_completion_result(
                {
                    "chosen_answer": "FIFTY-SIX",
                    "confidence": 0.9,
                    "reasoning": "...",
                }
            )
        )

        verified, details = await judge.verify_answer_async(
            sample_question, "openai", "gpt-4"
        )

        assert verified is True
        assert details["outcome"] == "pass"

    @pytest.mark.asyncio
    async def test_concession_async(self, judge, sample_question):
        """Async path: generator concedes."""
        provider = judge.providers["openai"]
        provider.generate_structured_completion_with_usage_async = AsyncMock(
            side_effect=[
                make_completion_result(
                    {
                        "chosen_answer": "forty-two",
                        "confidence": 0.8,
                        "reasoning": "...",
                    }
                ),
                make_completion_result(
                    {
                        "action": "concede",
                        "reasoning": "Reviewer is right",
                    }
                ),
            ]
        )

        verified, details = await judge.verify_answer_async(
            sample_question, "openai", "gpt-4"
        )

        assert verified is False
        assert details["outcome"] == "concession"

    @pytest.mark.asyncio
    async def test_defense_accepted_async(self, judge, sample_question):
        """Async path: defense accepted."""
        provider = judge.providers["openai"]
        provider.generate_structured_completion_with_usage_async = AsyncMock(
            side_effect=[
                make_completion_result(
                    {
                        "chosen_answer": "forty-two",
                        "confidence": 0.6,
                        "reasoning": "...",
                    }
                ),
                make_completion_result(
                    {"action": "defend", "reasoning": "56 is right"}
                ),
                make_completion_result({"ruling": "accept", "reasoning": "Convinced"}),
            ]
        )

        verified, details = await judge.verify_answer_async(
            sample_question, "openai", "gpt-4"
        )

        assert verified is True
        assert details["outcome"] == "defense_accepted"

    @pytest.mark.asyncio
    async def test_defense_rejected_async(self, judge, sample_question):
        """Async path: defense rejected."""
        provider = judge.providers["openai"]
        provider.generate_structured_completion_with_usage_async = AsyncMock(
            side_effect=[
                make_completion_result(
                    {
                        "chosen_answer": "forty-two",
                        "confidence": 0.9,
                        "reasoning": "...",
                    }
                ),
                make_completion_result({"action": "defend", "reasoning": "No"}),
                make_completion_result(
                    {"ruling": "reject", "reasoning": "Flawed question"}
                ),
            ]
        )

        verified, details = await judge.verify_answer_async(
            sample_question, "openai", "gpt-4"
        )

        assert verified is False
        assert details["outcome"] == "defense_rejected"

    @pytest.mark.asyncio
    async def test_single_option_skip_async(self, judge):
        """Async path: single-option skip."""
        q = Mock()
        q.question_type.value = "math"
        q.difficulty_level.value = "easy"
        q.answer_options = ["only-one"]

        verified, details = await judge.verify_answer_async(q, "openai", "gpt-4")

        assert verified is True
        assert details["outcome"] == "skipped"
        assert details["reason"] == "insufficient_answer_options"

    @pytest.mark.asyncio
    async def test_generator_unavailable_skip_async(self, judge, sample_question):
        """Async path: generator provider unavailable."""
        judge.providers = {"anthropic": Mock()}
        judge.providers["anthropic"].generate_structured_completion_with_usage_async = (
            AsyncMock(
                return_value=make_completion_result(
                    {
                        "chosen_answer": "forty-two",
                        "confidence": 0.7,
                        "reasoning": "...",
                    }
                )
            )
        )

        verified, details = await judge.verify_answer_async(
            sample_question, "anthropic", "claude"
        )

        assert verified is True
        assert details["outcome"] == "skipped"
        assert details["reason"] == "generator_provider_unavailable"

    @pytest.mark.asyncio
    async def test_timeout_error_propagates_async(self, judge, sample_question):
        """Async path: TimeoutError is re-raised."""
        provider = judge.providers["openai"]
        provider.generate_structured_completion_with_usage_async = AsyncMock(
            side_effect=asyncio.TimeoutError()
        )

        with pytest.raises(asyncio.TimeoutError):
            await judge.verify_answer_async(
                sample_question, "openai", "gpt-4", timeout=0.1
            )

    @pytest.mark.asyncio
    async def test_general_error_propagates_async(self, judge, sample_question):
        """Async path: generic exceptions re-raised."""
        provider = judge.providers["openai"]
        provider.generate_structured_completion_with_usage_async = AsyncMock(
            side_effect=ValueError("bad response")
        )

        with pytest.raises(ValueError, match="bad response"):
            await judge.verify_answer_async(sample_question, "openai", "gpt-4")


# ---------------------------------------------------------------------------
# Config parsing tests
# ---------------------------------------------------------------------------
class TestAnswerVerificationConfig:
    """Tests for answer_verification_enabled config parsing."""

    def test_default_enabled(self):
        """Default config has answer_verification_enabled=True."""
        config = JudgeConfig(
            version="1.0.0",
            judges={
                "math": JudgeModel(
                    model="gpt-4", provider="openai", rationale="m", enabled=True
                ),
                "logic": JudgeModel(
                    model="gpt-4", provider="openai", rationale="l", enabled=True
                ),
                "pattern": JudgeModel(
                    model="gpt-4", provider="openai", rationale="p", enabled=True
                ),
                "spatial": JudgeModel(
                    model="gpt-4", provider="openai", rationale="s", enabled=True
                ),
                "verbal": JudgeModel(
                    model="gpt-4", provider="openai", rationale="v", enabled=True
                ),
                "memory": JudgeModel(
                    model="gpt-4", provider="openai", rationale="m", enabled=True
                ),
            },
            default_judge=JudgeModel(
                model="gpt-4", provider="openai", rationale="d", enabled=True
            ),
            evaluation_criteria=EvaluationCriteria(
                clarity=0.3, validity=0.4, formatting=0.15, creativity=0.15
            ),
            min_judge_score=0.7,
        )
        assert config.answer_verification_enabled is True

    def test_explicit_enabled(self):
        """Explicitly set answer_verification_enabled=True."""
        config = JudgeConfig(
            version="1.0.0",
            judges={
                "math": JudgeModel(
                    model="gpt-4", provider="openai", rationale="m", enabled=True
                ),
                "logic": JudgeModel(
                    model="gpt-4", provider="openai", rationale="l", enabled=True
                ),
                "pattern": JudgeModel(
                    model="gpt-4", provider="openai", rationale="p", enabled=True
                ),
                "spatial": JudgeModel(
                    model="gpt-4", provider="openai", rationale="s", enabled=True
                ),
                "verbal": JudgeModel(
                    model="gpt-4", provider="openai", rationale="v", enabled=True
                ),
                "memory": JudgeModel(
                    model="gpt-4", provider="openai", rationale="m", enabled=True
                ),
            },
            default_judge=JudgeModel(
                model="gpt-4", provider="openai", rationale="d", enabled=True
            ),
            evaluation_criteria=EvaluationCriteria(
                clarity=0.3, validity=0.4, formatting=0.15, creativity=0.15
            ),
            min_judge_score=0.7,
            answer_verification_enabled=False,
        )
        assert config.answer_verification_enabled is False

    def test_parse_config_extracts_enabled(self):
        """_parse_config extracts answer_verification.enabled from raw YAML dict."""
        loader = JudgeConfigLoader.__new__(JudgeConfigLoader)
        raw = {
            "version": "1.0.0",
            "judges": {
                "math": {
                    "model": "gpt-4",
                    "provider": "openai",
                    "rationale": "m",
                    "enabled": True,
                },
                "logic": {
                    "model": "gpt-4",
                    "provider": "openai",
                    "rationale": "l",
                    "enabled": True,
                },
                "pattern": {
                    "model": "gpt-4",
                    "provider": "openai",
                    "rationale": "p",
                    "enabled": True,
                },
                "spatial": {
                    "model": "gpt-4",
                    "provider": "openai",
                    "rationale": "s",
                    "enabled": True,
                },
                "verbal": {
                    "model": "gpt-4",
                    "provider": "openai",
                    "rationale": "v",
                    "enabled": True,
                },
                "memory": {
                    "model": "gpt-4",
                    "provider": "openai",
                    "rationale": "m",
                    "enabled": True,
                },
            },
            "default_judge": {
                "model": "gpt-4",
                "provider": "openai",
                "rationale": "d",
                "enabled": True,
            },
            "evaluation_criteria": {
                "clarity": 0.3,
                "validity": 0.4,
                "formatting": 0.15,
                "creativity": 0.15,
            },
            "min_judge_score": 0.7,
            "answer_verification": {"enabled": False},
        }
        config = loader._parse_config(raw)
        assert config.answer_verification_enabled is False

    def test_parse_config_defaults_when_missing(self):
        """_parse_config defaults to True when answer_verification key is absent."""
        loader = JudgeConfigLoader.__new__(JudgeConfigLoader)
        raw = {
            "version": "1.0.0",
            "judges": {
                "math": {
                    "model": "gpt-4",
                    "provider": "openai",
                    "rationale": "m",
                    "enabled": True,
                },
                "logic": {
                    "model": "gpt-4",
                    "provider": "openai",
                    "rationale": "l",
                    "enabled": True,
                },
                "pattern": {
                    "model": "gpt-4",
                    "provider": "openai",
                    "rationale": "p",
                    "enabled": True,
                },
                "spatial": {
                    "model": "gpt-4",
                    "provider": "openai",
                    "rationale": "s",
                    "enabled": True,
                },
                "verbal": {
                    "model": "gpt-4",
                    "provider": "openai",
                    "rationale": "v",
                    "enabled": True,
                },
                "memory": {
                    "model": "gpt-4",
                    "provider": "openai",
                    "rationale": "m",
                    "enabled": True,
                },
            },
            "default_judge": {
                "model": "gpt-4",
                "provider": "openai",
                "rationale": "d",
                "enabled": True,
            },
            "evaluation_criteria": {
                "clarity": 0.3,
                "validity": 0.4,
                "formatting": 0.15,
                "creativity": 0.15,
            },
            "min_judge_score": 0.7,
        }
        config = loader._parse_config(raw)
        assert config.answer_verification_enabled is True

    def test_loader_get_answer_verification_enabled(self, mock_judge_config):
        """JudgeConfigLoader.get_answer_verification_enabled returns bool."""
        assert mock_judge_config.get_answer_verification_enabled() is True


# ---------------------------------------------------------------------------
# Runner integration (Phase 2b) tests
# ---------------------------------------------------------------------------
class TestRunnerPhase2bIntegration:
    """Tests for Phase 2b answer verification integration in the runner."""

    def _make_evaluated_question(self, correct_answer="fifty-six", source_llm="openai"):
        """Helper to create an EvaluatedQuestion for runner tests."""
        question = GeneratedQuestion(
            question_text="Which of the following is the product of seven and eight?",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer=correct_answer,
            answer_options=["forty-two", "forty-eight", "fifty-four", "fifty-six"],
            explanation="7*8=56",
            metadata={},
            source_llm=source_llm,
            source_model="gpt-4",
        )
        evaluation = EvaluationScore(
            clarity_score=0.9,
            difficulty_score=0.8,
            validity_score=0.9,
            formatting_score=0.85,
            creativity_score=0.7,
            overall_score=0.85,
        )
        return EvaluatedQuestion(
            question=question, evaluation=evaluation, judge_model="gpt-4", approved=True
        )

    @patch("app.evaluation.runner.observability")
    def test_fail_open_on_error(self, mock_obs):
        """When verify_answer raises, the question stays approved (fail-open)."""
        mock_judge = Mock()
        mock_judge.judge_config.get_answer_verification_enabled.return_value = True
        mock_judge.providers = {"openai": Mock(model="gpt-4")}
        mock_judge.judge_config.resolve_judge_provider.return_value = (
            "openai",
            "gpt-4",
        )
        mock_judge.verify_answer.side_effect = RuntimeError("LLM API down")

        eq = self._make_evaluated_question()
        approved = [eq]
        rejected = []
        metrics = Mock()
        metrics.questions_approved = 1
        metrics.questions_rejected = 0

        # Simulate Phase 2b logic
        if mock_judge.judge_config.get_answer_verification_enabled() and approved:
            verified_approved = []
            for eq_item in approved:
                try:
                    q_type = eq_item.question.question_type.value
                    available = list(mock_judge.providers.keys())
                    j_provider, j_model = (
                        mock_judge.judge_config.resolve_judge_provider(
                            q_type, available
                        )
                    )
                    effective_model = j_model or mock_judge.providers[j_provider].model
                    verified, details = mock_judge.verify_answer(
                        question=eq_item.question,
                        judge_provider_name=j_provider,
                        judge_model_name=effective_model,
                    )
                    eq_item.evaluation.answer_verified = verified
                    eq_item.evaluation.verification_details = details
                    if verified:
                        verified_approved.append(eq_item)
                    else:
                        rejected.append(eq_item)
                        metrics.questions_approved -= 1
                        metrics.questions_rejected += 1
                except Exception:
                    # Fail-open: keep approved
                    verified_approved.append(eq_item)
            approved = verified_approved

        # Question should remain approved despite the error
        assert len(approved) == 1
        assert len(rejected) == 0
        # answer_verified should NOT have been set (error before assignment)
        assert approved[0].evaluation.answer_verified is None

    @patch("app.evaluation.runner.observability")
    def test_verification_disabled_skips_phase2b(self, mock_obs):
        """When verification is disabled, Phase 2b is skipped entirely."""
        mock_judge = Mock()
        mock_judge.judge_config.get_answer_verification_enabled.return_value = False

        eq = self._make_evaluated_question()
        approved = [eq]

        if mock_judge.judge_config.get_answer_verification_enabled() and approved:
            pytest.fail("Phase 2b should not run when disabled")

        assert len(approved) == 1
        mock_judge.verify_answer.assert_not_called()

    @patch("app.evaluation.runner.observability")
    def test_rejected_questions_moved_on_failure(self, mock_obs):
        """Failed verification moves question from approved to rejected."""
        mock_judge = Mock()
        mock_judge.judge_config.get_answer_verification_enabled.return_value = True
        mock_judge.providers = {"openai": Mock(model="gpt-4")}
        mock_judge.judge_config.resolve_judge_provider.return_value = (
            "openai",
            "gpt-4",
        )
        mock_judge.verify_answer.return_value = (
            False,
            {"outcome": "concession", "judge_chosen_answer": "forty-two"},
        )

        eq = self._make_evaluated_question()
        approved = [eq]
        rejected = []
        metrics = Mock()
        metrics.questions_approved = 1
        metrics.questions_rejected = 0

        if mock_judge.judge_config.get_answer_verification_enabled() and approved:
            verified_approved = []
            for eq_item in approved:
                try:
                    q_type = eq_item.question.question_type.value
                    available = list(mock_judge.providers.keys())
                    j_provider, j_model = (
                        mock_judge.judge_config.resolve_judge_provider(
                            q_type, available
                        )
                    )
                    effective_model = j_model or mock_judge.providers[j_provider].model
                    verified, details = mock_judge.verify_answer(
                        question=eq_item.question,
                        judge_provider_name=j_provider,
                        judge_model_name=effective_model,
                    )
                    eq_item.evaluation.answer_verified = verified
                    eq_item.evaluation.verification_details = details
                    if verified:
                        verified_approved.append(eq_item)
                    else:
                        rejected.append(eq_item)
                        metrics.questions_approved -= 1
                        metrics.questions_rejected += 1
                except Exception:
                    verified_approved.append(eq_item)
            approved = verified_approved

        assert len(approved) == 0
        assert len(rejected) == 1
        assert rejected[0].evaluation.answer_verified is False
        assert rejected[0].evaluation.verification_details["outcome"] == "concession"
        assert metrics.questions_approved == 0
        assert metrics.questions_rejected == 1

    @patch("app.evaluation.runner.observability")
    def test_verified_questions_stay_approved(self, mock_obs):
        """Verified questions remain in the approved list."""
        mock_judge = Mock()
        mock_judge.judge_config.get_answer_verification_enabled.return_value = True
        mock_judge.providers = {"openai": Mock(model="gpt-4")}
        mock_judge.judge_config.resolve_judge_provider.return_value = (
            "openai",
            "gpt-4",
        )
        mock_judge.verify_answer.return_value = (
            True,
            {"outcome": "pass", "judge_chosen_answer": "fifty-six", "confidence": 0.95},
        )

        eq = self._make_evaluated_question()
        approved = [eq]
        rejected = []
        metrics = Mock()
        metrics.questions_approved = 1
        metrics.questions_rejected = 0

        if mock_judge.judge_config.get_answer_verification_enabled() and approved:
            verified_approved = []
            for eq_item in approved:
                try:
                    q_type = eq_item.question.question_type.value
                    available = list(mock_judge.providers.keys())
                    j_provider, j_model = (
                        mock_judge.judge_config.resolve_judge_provider(
                            q_type, available
                        )
                    )
                    effective_model = j_model or mock_judge.providers[j_provider].model
                    verified, details = mock_judge.verify_answer(
                        question=eq_item.question,
                        judge_provider_name=j_provider,
                        judge_model_name=effective_model,
                    )
                    eq_item.evaluation.answer_verified = verified
                    eq_item.evaluation.verification_details = details
                    if verified:
                        verified_approved.append(eq_item)
                    else:
                        rejected.append(eq_item)
                except Exception:
                    verified_approved.append(eq_item)
            approved = verified_approved

        assert len(approved) == 1
        assert len(rejected) == 0
        assert approved[0].evaluation.answer_verified is True
        assert approved[0].evaluation.verification_details["outcome"] == "pass"
