"""
Unit tests for LLM benchmark runner helpers and orchestration.

Covers _normalize_answer, _parse_answer_from_response, and
run_llm_benchmark (with mocked provider).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.llm_benchmark.runner import (
    _normalize_answer,
    _parse_answer_from_response,
    _estimate_cost,
    run_llm_benchmark,
)
from app.services.llm_benchmark.providers import LLMResponse as ProviderResponse


# ---------------------------------------------------------------------------
# _normalize_answer
# ---------------------------------------------------------------------------


class TestNormalizeAnswer:
    def test_strips_whitespace(self):
        assert _normalize_answer("  hello  ") == "hello"

    def test_lowercases(self):
        assert _normalize_answer("Hello World") == "hello world"

    def test_removes_letter_dot_prefix(self):
        assert _normalize_answer("A. Paris") == "paris"
        assert _normalize_answer("b. London") == "london"

    def test_removes_letter_paren_prefix(self):
        assert _normalize_answer("A) Paris") == "paris"
        assert _normalize_answer("c) Tokyo") == "tokyo"

    def test_removes_number_dot_prefix(self):
        assert _normalize_answer("1. First option") == "first option"
        assert _normalize_answer("3. Third") == "third"

    def test_removes_number_paren_prefix(self):
        assert _normalize_answer("2) Second") == "second"

    def test_no_prefix_unchanged(self):
        assert _normalize_answer("paris") == "paris"

    def test_empty_string(self):
        assert _normalize_answer("") == ""

    def test_whitespace_only(self):
        assert _normalize_answer("   ") == ""

    def test_prefix_with_extra_whitespace(self):
        assert _normalize_answer("  A.   Paris  ") == "paris"

    def test_no_prefix_removal_for_long_prefix(self):
        # "AB." should NOT be stripped (only single char prefixes)
        assert _normalize_answer("AB. Something") == "ab. something"


# ---------------------------------------------------------------------------
# _parse_answer_from_response
# ---------------------------------------------------------------------------


class TestParseAnswerFromResponse:
    def test_valid_json(self):
        assert _parse_answer_from_response('{"answer": "Paris"}') == "Paris"

    def test_json_missing_answer_key(self):
        assert _parse_answer_from_response('{"result": "Paris"}') == ""

    def test_json_answer_is_int(self):
        assert _parse_answer_from_response('{"answer": 42}') == "42"

    def test_markdown_fenced_json(self):
        raw = '```json\n{"answer": "London"}\n```'
        assert _parse_answer_from_response(raw) == "London"

    def test_markdown_fenced_no_lang(self):
        raw = '```\n{"answer": "Tokyo"}\n```'
        assert _parse_answer_from_response(raw) == "Tokyo"

    def test_invalid_json(self):
        assert _parse_answer_from_response("not json at all") == ""

    def test_empty_string(self):
        assert _parse_answer_from_response("") == ""

    def test_nested_json_returns_str_repr(self):
        raw = '{"answer": ["a", "b"]}'
        # str(["a", "b"]) => "['a', 'b']"
        result = _parse_answer_from_response(raw)
        assert result == "['a', 'b']"

    def test_json_with_extra_keys(self):
        raw = '{"answer": "Paris", "confidence": 0.9}'
        assert _parse_answer_from_response(raw) == "Paris"

    def test_double_fenced_markdown(self):
        # Only outer fences should be stripped
        raw = '```json\n{"answer": "42"}\n```'
        assert _parse_answer_from_response(raw) == "42"


# ---------------------------------------------------------------------------
# _estimate_cost
# ---------------------------------------------------------------------------


class TestEstimateCost:
    def test_openai_cost(self):
        # 1M input tokens @ $0.15 + 1M output tokens @ $0.60 = $0.75
        cost = _estimate_cost("openai", 1_000_000, 1_000_000)
        assert cost == pytest.approx(0.75)

    def test_unknown_vendor_uses_defaults(self):
        # Unknown vendor falls back to (1.0, 3.0) per 1M tokens
        cost = _estimate_cost("unknown", 1_000_000, 1_000_000)
        assert cost == pytest.approx(4.0)

    def test_zero_tokens(self):
        assert _estimate_cost("openai", 0, 0) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# run_llm_benchmark (mocked provider)
# ---------------------------------------------------------------------------


class TestRunLlmBenchmark:
    """Tests for the full orchestration with a mocked provider and DB."""

    @staticmethod
    def _make_question(
        qid: int,
        question_type_value: str = "logic",
        correct_answer: str = "Paris",
        answer_options: list[str] | None = None,
    ):
        """Create a lightweight mock Question object."""
        q = MagicMock()
        q.id = qid
        q.question_text = f"Test question {qid}"
        q.correct_answer = correct_answer
        q.answer_options = answer_options or ["Paris", "London", "Tokyo"]
        q.stimulus = None
        q.question_type = MagicMock()
        q.question_type.value = question_type_value
        return q

    @pytest.mark.asyncio
    @patch("app.services.llm_benchmark.runner.async_select_stratified_questions")
    async def test_basic_scoring(self, mock_select):
        """Provider returns correct answer -> is_correct=True, score calculated."""
        q1 = self._make_question(1, correct_answer="Paris")
        q2 = self._make_question(2, correct_answer="42")
        mock_select.return_value = (
            [q1, q2],
            {"pattern": 1, "logic": 1},
        )

        provider_responses = [
            ProviderResponse(
                answer='{"answer": "Paris"}',
                input_tokens=100,
                output_tokens=20,
                model="test-model",
            ),
            ProviderResponse(
                answer='{"answer": "wrong"}',
                input_tokens=100,
                output_tokens=20,
                model="test-model",
            ),
        ]

        mock_provider = AsyncMock(side_effect=provider_responses)

        db = AsyncMock()
        # Make flush/commit no-ops and give session_record an id
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        # Capture objects added to db so we can assign id
        added_objects = []

        def capture_add(obj):
            added_objects.append(obj)
            from app.models.llm_benchmark import LLMTestSession

            if isinstance(obj, LLMTestSession):
                obj.id = 99

        db.add = MagicMock(side_effect=capture_add)

        with (
            patch(
                "app.services.llm_benchmark.runner._PROVIDER_DISPATCH",
                {"openai": mock_provider},
            ),
            patch("app.services.llm_benchmark.runner.settings") as mock_settings,
            patch("app.services.llm_benchmark.runner.calculate_iq_score") as mock_iq,
            patch("app.services.llm_benchmark.runner.iq_to_percentile") as mock_pctile,
            patch(
                "app.services.llm_benchmark.runner.calculate_domain_scores",
                return_value={"logic": 0.5},
            ),
        ):
            mock_settings.LLM_BENCHMARK_COST_CAP_USD = 5.0
            mock_settings.TEST_TOTAL_QUESTIONS = 25
            mock_iq.return_value = MagicMock(iq_score=110)
            mock_pctile.return_value = 75.0

            session_id = await run_llm_benchmark(
                db, "openai", "test-model", total_questions=2
            )

        assert session_id == 99
        assert mock_provider.await_count == 2
        mock_iq.assert_called_once_with(1, 2)  # 1 correct out of 2

    @pytest.mark.asyncio
    @patch("app.services.llm_benchmark.runner.async_select_stratified_questions")
    async def test_unknown_vendor_raises(self, mock_select):
        db = AsyncMock()
        with pytest.raises(ValueError, match="Unknown vendor"):
            await run_llm_benchmark(db, "deepseek", "model-x")

    @pytest.mark.asyncio
    @patch("app.services.llm_benchmark.runner.async_select_stratified_questions")
    async def test_cost_cap_stops_early(self, mock_select):
        """When cost exceeds cap, loop should break with cost_cap_exceeded status."""
        questions = [self._make_question(i, correct_answer="X") for i in range(5)]
        mock_select.return_value = (questions, {})

        # Each response costs a lot to trigger the cap
        expensive_response = ProviderResponse(
            answer='{"answer": "X"}',
            input_tokens=10_000_000,  # huge token count -> high cost
            output_tokens=5_000_000,
            model="test-model",
        )
        mock_provider = AsyncMock(return_value=expensive_response)

        db = AsyncMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        added_objects = []

        def capture_add(obj):
            added_objects.append(obj)
            from app.models.llm_benchmark import LLMTestSession

            if isinstance(obj, LLMTestSession):
                obj.id = 50

        db.add = MagicMock(side_effect=capture_add)

        with (
            patch(
                "app.services.llm_benchmark.runner._PROVIDER_DISPATCH",
                {"openai": mock_provider},
            ),
            patch("app.services.llm_benchmark.runner.settings") as mock_settings,
            patch("app.services.llm_benchmark.runner.calculate_iq_score") as mock_iq,
            patch(
                "app.services.llm_benchmark.runner.iq_to_percentile",
                return_value=50.0,
            ),
            patch(
                "app.services.llm_benchmark.runner.calculate_domain_scores",
                return_value={},
            ),
        ):
            mock_settings.LLM_BENCHMARK_COST_CAP_USD = 0.01  # very low cap
            mock_settings.TEST_TOTAL_QUESTIONS = 25
            mock_iq.return_value = MagicMock(iq_score=100)

            await run_llm_benchmark(db, "openai", "test-model", total_questions=5)

        # First question runs (cost checked BEFORE each call), second triggers cap
        # So provider should be called fewer times than total questions
        assert mock_provider.await_count < 5

        # Session status should be cost_cap_exceeded
        session_obj = added_objects[0]
        assert session_obj.status == "cost_cap_exceeded"

    @pytest.mark.asyncio
    @patch("app.services.llm_benchmark.runner.async_select_stratified_questions")
    async def test_provider_exception_handled(self, mock_select):
        """Unhandled provider exception -> empty answer, not a crash."""
        q = self._make_question(1, correct_answer="Paris")
        mock_select.return_value = ([q], {})

        mock_provider = AsyncMock(side_effect=RuntimeError("API down"))

        db = AsyncMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        def capture_add(obj):
            from app.models.llm_benchmark import LLMTestSession

            if isinstance(obj, LLMTestSession):
                obj.id = 77

        db.add = MagicMock(side_effect=capture_add)

        with (
            patch(
                "app.services.llm_benchmark.runner._PROVIDER_DISPATCH",
                {"openai": mock_provider},
            ),
            patch(
                "app.services.llm_benchmark.runner.calculate_iq_score",
            ) as mock_iq,
            patch(
                "app.services.llm_benchmark.runner.iq_to_percentile",
                return_value=25.0,
            ),
            patch(
                "app.services.llm_benchmark.runner.calculate_domain_scores",
                return_value={},
            ),
        ):
            mock_iq.return_value = MagicMock(iq_score=85)

            session_id = await run_llm_benchmark(
                db, "openai", "test-model", total_questions=1
            )

        assert session_id == 77
        # Should complete without raising; 0 correct out of 1 answered
        mock_iq.assert_called_once_with(0, 1)
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("app.services.llm_benchmark.runner.async_select_stratified_questions")
    async def test_empty_answer_not_marked_correct(self, mock_select):
        """Even if correct_answer normalizes to empty, is_correct should be False."""
        q = self._make_question(1, correct_answer="Paris")
        mock_select.return_value = ([q], {})

        # Provider returns empty answer
        mock_provider = AsyncMock(
            return_value=ProviderResponse(
                answer='{"answer": ""}',
                input_tokens=50,
                output_tokens=10,
                model="test-model",
            )
        )

        db = AsyncMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        added_objects = []

        def capture_add(obj):
            added_objects.append(obj)
            from app.models.llm_benchmark import LLMTestSession

            if isinstance(obj, LLMTestSession):
                obj.id = 88

        db.add = MagicMock(side_effect=capture_add)

        with (
            patch(
                "app.services.llm_benchmark.runner._PROVIDER_DISPATCH",
                {"openai": mock_provider},
            ),
            patch("app.services.llm_benchmark.runner.calculate_iq_score") as mock_iq,
            patch(
                "app.services.llm_benchmark.runner.iq_to_percentile",
                return_value=None,
            ),
            patch(
                "app.services.llm_benchmark.runner.calculate_domain_scores",
                return_value={},
            ),
        ):
            mock_iq.return_value = MagicMock(iq_score=85)

            await run_llm_benchmark(db, "openai", "test-model", total_questions=1)

        # 0 correct: empty normalized answer is never marked correct
        mock_iq.assert_called_once_with(0, 1)
