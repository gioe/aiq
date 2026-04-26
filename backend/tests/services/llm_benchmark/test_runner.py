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
    _extract_json_from_prose,
    _estimate_cost,
    run_llm_benchmark,
)
from app.services.llm_benchmark.providers import (
    LLMResponse as ProviderResponse,
    complete_anthropic,
    complete_openai,
)

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

    def test_json_embedded_in_prose(self):
        raw = 'The answer to this question is {"answer": "Paris"}.'
        assert _parse_answer_from_response(raw) == "Paris"

    def test_json_embedded_in_multiline_prose(self):
        raw = (
            "After careful consideration, I believe the correct answer is:\n\n"
            '{"answer": "42"}\n\n'
            "This is because the question asks about the meaning of life."
        )
        assert _parse_answer_from_response(raw) == "42"

    def test_json_embedded_with_int_answer(self):
        raw = 'Based on my analysis, {"answer": 7} is the correct response.'
        assert _parse_answer_from_response(raw) == "7"

    def test_prose_without_json(self):
        raw = "The answer is Paris, the capital of France."
        assert _parse_answer_from_response(raw) == ""

    def test_prose_with_non_answer_json(self):
        raw = 'Here is some data: {"result": "Paris"} for reference.'
        assert _parse_answer_from_response(raw) == ""


# ---------------------------------------------------------------------------
# _extract_json_from_prose
# ---------------------------------------------------------------------------


class TestExtractJsonFromProse:
    def test_extracts_answer_from_prose(self):
        text = 'The answer is {"answer": "London"} based on the clues.'
        assert _extract_json_from_prose(text) == "London"

    def test_returns_empty_for_no_json(self):
        assert _extract_json_from_prose("just plain text") == ""

    def test_returns_empty_for_json_without_answer_key(self):
        text = 'Here is {"result": "Paris"} for you.'
        assert _extract_json_from_prose(text) == ""

    def test_picks_first_json_with_answer(self):
        text = 'Ignore {"x": 1}. The real one is {"answer": "Tokyo"}.'
        assert _extract_json_from_prose(text) == "Tokyo"


# ---------------------------------------------------------------------------
# _estimate_cost
# ---------------------------------------------------------------------------


class TestEstimateCost:
    def test_gpt4o_mini_cost(self):
        # 1M input @ $0.15 + 1M output @ $0.60 = $0.75
        cost = _estimate_cost("gpt-4o-mini", 1_000_000, 1_000_000)
        assert cost == pytest.approx(0.75)

    def test_opus_cost(self):
        # 1M input @ $5.00 + 1M output @ $25.00 = $30.00
        cost = _estimate_cost("claude-opus-4-7", 1_000_000, 1_000_000)
        assert cost == pytest.approx(30.0)

    def test_sonnet_cost(self):
        # 1M input @ $3.00 + 1M output @ $15.00 = $18.00
        cost = _estimate_cost("claude-sonnet-4-5-20250929", 1_000_000, 1_000_000)
        assert cost == pytest.approx(18.0)

    def test_gemini_cost(self):
        # 1M input @ $1.25 + 1M output @ $10.00 = $11.25
        cost = _estimate_cost("gemini-2.5-pro", 1_000_000, 1_000_000)
        assert cost == pytest.approx(11.25)

    def test_unknown_model_uses_conservative_fallback(self):
        # Unknown model falls back to (10.0, 30.0) per 1M tokens
        cost = _estimate_cost("unknown-model-xyz", 1_000_000, 1_000_000)
        assert cost == pytest.approx(40.0)

    def test_zero_tokens(self):
        assert _estimate_cost("gpt-4o-mini", 0, 0) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# provider payloads
# ---------------------------------------------------------------------------


class TestProviderPayloads:
    @pytest.mark.asyncio
    async def test_openai_gpt55_omits_unsupported_temperature(self):
        captured_payload = {}

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "usage": {"prompt_tokens": 10, "completion_tokens": 2},
                    "choices": [{"message": {"content": '{"answer": "A"}'}}],
                    "model": "gpt-5.5",
                }

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def post(self, _url, *, json, headers):
                captured_payload.update(json)
                return FakeResponse()

        with (
            patch(
                "app.services.llm_benchmark.providers.httpx.AsyncClient",
                FakeAsyncClient,
            ),
            patch("app.services.llm_benchmark.providers.settings") as mock_settings,
        ):
            mock_settings.LLM_OPENAI_API_KEY = "placeholder"  # pragma: allowlist secret

            result = await complete_openai("Question?", model="gpt-5.5")

        assert result.ok
        assert "temperature" not in captured_payload

    @pytest.mark.asyncio
    async def test_anthropic_opus47_omits_deprecated_temperature(self):
        captured_payload = {}

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "usage": {"input_tokens": 10, "output_tokens": 2},
                    "content": [{"type": "text", "text": '{"answer": "A"}'}],
                    "model": "claude-opus-4-7",
                }

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def post(self, _url, *, json, headers):
                captured_payload.update(json)
                return FakeResponse()

        with (
            patch(
                "app.services.llm_benchmark.providers.httpx.AsyncClient",
                FakeAsyncClient,
            ),
            patch("app.services.llm_benchmark.providers.settings") as mock_settings,
        ):
            mock_settings.LLM_ANTHROPIC_API_KEY = (
                "placeholder"  # pragma: allowlist secret
            )

            result = await complete_anthropic("Question?", model="claude-opus-4-7")

        assert result.ok
        assert "temperature" not in captured_payload


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
    async def test_all_provider_errors_mark_session_failed_without_iq_score(
        self, mock_select
    ):
        """All provider-error responses should not persist as a quality score."""
        questions = [self._make_question(i, correct_answer="X") for i in range(3)]
        mock_select.return_value = (questions, {})

        mock_provider = AsyncMock(
            return_value=ProviderResponse(
                answer="",
                input_tokens=0,
                output_tokens=0,
                model="test-model",
                error="Provider payload rejected",
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
                obj.id = 91

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
                return_value={},
            ),
        ):
            mock_settings.LLM_BENCHMARK_COST_CAP_USD = 5.0
            mock_settings.TEST_TOTAL_QUESTIONS = 25

            await run_llm_benchmark(db, "openai", "test-model", total_questions=3)

        from app.models.llm_benchmark import LLMTestResult, LLMTestSession

        session_obj = next(
            obj for obj in added_objects if isinstance(obj, LLMTestSession)
        )
        result_obj = next(
            obj for obj in added_objects if isinstance(obj, LLMTestResult)
        )

        assert session_obj.status == "failed"
        assert result_obj.iq_score is None
        assert result_obj.percentile_rank is None
        assert result_obj.total_questions == 3
        assert result_obj.correct_answers == 0
        mock_iq.assert_not_called()
        mock_pctile.assert_not_called()

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

        added_objects = []

        def capture_add(obj):
            added_objects.append(obj)
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
        # Should complete without raising, but no IQ score is recorded because
        # every provider call failed.
        from app.models.llm_benchmark import LLMTestResult, LLMTestSession

        session_obj = next(
            obj for obj in added_objects if isinstance(obj, LLMTestSession)
        )
        result_obj = next(
            obj for obj in added_objects if isinstance(obj, LLMTestResult)
        )
        assert session_obj.status == "failed"
        assert result_obj.iq_score is None
        mock_iq.assert_not_called()
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
