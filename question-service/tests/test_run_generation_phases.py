"""Unit tests for the extracted phase functions in run_generation.py.

Each test exercises a phase function in isolation without instantiating the
full pipeline. Observability and other singletons are patched at the module level.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# run_optionally_async
# ---------------------------------------------------------------------------


class TestRunOptionallyAsync:
    def test_calls_sync_fn_when_use_async_false(self):
        from app.generation.runner import run_optionally_async

        sync_fn = MagicMock(return_value="sync_result")

        async def async_fn():
            return "async_result"

        result = run_optionally_async(async_fn, sync_fn, use_async=False)
        assert result == "sync_result"
        sync_fn.assert_called_once()

    def test_calls_async_fn_when_use_async_true(self):
        from app.generation.runner import run_optionally_async

        sync_fn = MagicMock()

        async def async_fn():
            return "async_result"

        result = run_optionally_async(async_fn, sync_fn, use_async=True)
        assert result == "async_result"
        sync_fn.assert_not_called()

    def test_cleanup_called_in_async_path(self):
        from app.generation.runner import run_optionally_async

        cleanup_called = []

        async def async_fn():
            return "result"

        async def cleanup_fn():
            cleanup_called.append(True)

        result = run_optionally_async(
            async_fn, lambda: None, use_async=True, cleanup_fn=cleanup_fn
        )
        assert result == "result"
        assert cleanup_called == [True]

    def test_cleanup_not_called_in_sync_path(self):
        from app.generation.runner import run_optionally_async

        cleanup_called = []

        async def async_fn():
            return "result"

        async def cleanup_fn():
            cleanup_called.append(True)

        run_optionally_async(
            async_fn, lambda: "sync", use_async=False, cleanup_fn=cleanup_fn
        )
        assert cleanup_called == []

    def test_cleanup_called_even_when_async_fn_raises(self):
        from app.generation.runner import run_optionally_async

        cleanup_called = []

        async def async_fn():
            raise ValueError("boom")

        async def cleanup_fn():
            cleanup_called.append(True)

        with pytest.raises(ValueError, match="boom"):
            run_optionally_async(
                async_fn, lambda: None, use_async=True, cleanup_fn=cleanup_fn
            )
        assert cleanup_called == [True]


# ---------------------------------------------------------------------------
# send_phase_alert
# ---------------------------------------------------------------------------


class TestSendPhaseAlert:
    def test_constructs_and_sends_classified_error(self):
        from app.infrastructure.error_classifier import ErrorCategory, ErrorSeverity
        from run_generation import send_phase_alert

        mock_alert_manager = MagicMock()
        send_phase_alert(
            alert_manager=mock_alert_manager,
            category=ErrorCategory.UNKNOWN,
            severity=ErrorSeverity.HIGH,
            provider="test-provider",
            original_error="TestError",
            message="something went wrong",
            context="[run_id=abc] details here",
            is_retryable=True,
        )

        mock_alert_manager.send_alert.assert_called_once()
        _, kwargs = mock_alert_manager.send_alert.call_args
        assert kwargs["context"] == "[run_id=abc] details here"

    def test_passes_is_retryable_false(self):
        from app.infrastructure.error_classifier import (
            ClassifiedError,
            ErrorCategory,
            ErrorSeverity,
        )
        from run_generation import send_phase_alert

        mock_alert_manager = MagicMock()
        send_phase_alert(
            alert_manager=mock_alert_manager,
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.CRITICAL,
            provider="system",
            original_error="ConfigError",
            message="no keys",
            context="ctx",
            is_retryable=False,
        )

        sent_error = mock_alert_manager.send_alert.call_args.args[0]
        assert isinstance(sent_error, ClassifiedError)
        assert sent_error.is_retryable is False


# ---------------------------------------------------------------------------
# run_inventory_analysis
# ---------------------------------------------------------------------------


class TestRunInventoryAnalysis:
    def test_raises_when_db_is_none(self):
        from run_generation import run_inventory_analysis

        with pytest.raises(RuntimeError, match="Auto-balance requires database"):
            run_inventory_analysis(
                db=None,
                healthy_threshold=50,
                warning_threshold=20,
                target_per_stratum=100,
                target_count=30,
                alerting_config_path="./config/alerting.yaml",
                skip_inventory_alerts=True,
                alert_manager=MagicMock(),
                logger=MagicMock(),
            )

    def test_returns_none_when_plan_has_zero_questions(self):
        from run_generation import run_inventory_analysis

        mock_plan = MagicMock()
        mock_plan.total_questions = 0
        mock_plan.to_log_summary.return_value = "no gaps"

        mock_analysis = MagicMock()
        mock_analysis.strata = []
        mock_analysis.total_questions = 100
        mock_analysis.strata_below_target = []
        mock_analysis.critical_strata = []

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_inventory.return_value = mock_analysis
        mock_analyzer.compute_generation_plan.return_value = mock_plan

        with patch(
            "app.inventory.runner.InventoryAnalyzer", return_value=mock_analyzer
        ):
            result = run_inventory_analysis(
                db=MagicMock(),
                healthy_threshold=50,
                warning_threshold=20,
                target_per_stratum=100,
                target_count=30,
                alerting_config_path="./config/alerting.yaml",
                skip_inventory_alerts=True,
                alert_manager=MagicMock(),
                logger=MagicMock(),
            )

        assert result is None

    def test_returns_plan_when_questions_needed(self):
        from run_generation import run_inventory_analysis

        mock_plan = MagicMock()
        mock_plan.total_questions = 15
        mock_plan.to_log_summary.return_value = "15 questions needed"

        mock_analysis = MagicMock()
        mock_analysis.strata = []

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_inventory.return_value = mock_analysis
        mock_analyzer.compute_generation_plan.return_value = mock_plan

        with patch(
            "app.inventory.runner.InventoryAnalyzer", return_value=mock_analyzer
        ):
            result = run_inventory_analysis(
                db=MagicMock(),
                healthy_threshold=50,
                warning_threshold=20,
                target_per_stratum=100,
                target_count=15,
                alerting_config_path="./config/alerting.yaml",
                skip_inventory_alerts=True,
                alert_manager=MagicMock(),
                logger=MagicMock(),
            )

        assert result is mock_plan


# ---------------------------------------------------------------------------
# run_generation_phase
# ---------------------------------------------------------------------------


class TestRunGenerationPhase:
    def _make_mock_span(self):
        span = MagicMock()
        span.__enter__ = MagicMock(return_value=span)
        span.__exit__ = MagicMock(return_value=False)
        return span

    def _make_job_result(self, questions=None, n=2):
        if questions is None:
            questions = [MagicMock() for _ in range(n)]
            for q in questions:
                q.question_text = f"Question text {id(q)}"
        return {
            "questions": questions,
            "statistics": {
                "questions_generated": len(questions),
                "target_questions": n,
                "success_rate": len(questions) / n,
                "duration_seconds": 1.2,
                "questions_by_type": {},
                "questions_by_difficulty": {},
            },
        }

    @patch("app.generation.runner.observability")
    def test_sync_generation_returns_questions_and_stats(self, mock_obs):
        from app.reporting.run_summary import RunSummary as PipelineRunSummary
        from run_generation import run_generation_phase

        mock_obs.start_span.return_value = self._make_mock_span()

        mock_pipeline = MagicMock()
        mock_pipeline.run_generation_job.return_value = self._make_job_result(n=3)

        metrics = PipelineRunSummary()
        metrics.start_run()

        questions, stats = run_generation_phase(
            pipeline=mock_pipeline,
            generation_plan=None,
            question_types=None,
            difficulty_distribution=None,
            use_async=False,
            max_concurrent=10,
            timeout=60,
            provider_tier="primary",
            count=3,
            metrics=metrics,
            logger=MagicMock(),
        )

        assert len(questions) == 3
        assert stats["questions_generated"] == 3
        mock_pipeline.run_generation_job.assert_called_once()

    @patch("app.generation.runner.observability")
    def test_async_generation_calls_async_method(self, mock_obs):
        from app.reporting.run_summary import RunSummary as PipelineRunSummary
        from run_generation import run_generation_phase

        mock_obs.start_span.return_value = self._make_mock_span()

        mock_pipeline = MagicMock()
        job_result = self._make_job_result(n=2)
        mock_pipeline.run_generation_job_async = AsyncMock(return_value=job_result)
        mock_pipeline.cleanup = AsyncMock()

        metrics = PipelineRunSummary()
        metrics.start_run()

        questions, stats = run_generation_phase(
            pipeline=mock_pipeline,
            generation_plan=None,
            question_types=None,
            difficulty_distribution=None,
            use_async=True,
            max_concurrent=5,
            timeout=30,
            provider_tier="primary",
            count=2,
            metrics=metrics,
            logger=MagicMock(),
        )

        mock_pipeline.run_generation_job_async.assert_called_once()
        mock_pipeline.cleanup.assert_called_once()
        assert stats["questions_generated"] == 2

    @patch("app.generation.runner.observability")
    def test_balanced_generation_uses_plan_allocations(self, mock_obs):
        from app.reporting.run_summary import RunSummary as PipelineRunSummary
        from run_generation import run_generation_phase

        mock_obs.start_span.return_value = self._make_mock_span()

        mock_plan = MagicMock()
        mock_plan.allocations = {"verbal/easy": 5}

        mock_pipeline = MagicMock()
        mock_pipeline.run_balanced_generation_job.return_value = self._make_job_result(
            n=5
        )

        metrics = PipelineRunSummary()
        metrics.start_run()

        run_generation_phase(
            pipeline=mock_pipeline,
            generation_plan=mock_plan,
            question_types=None,
            difficulty_distribution=None,
            use_async=False,
            max_concurrent=10,
            timeout=60,
            provider_tier="primary",
            count=5,
            metrics=metrics,
            logger=MagicMock(),
        )

        mock_pipeline.run_balanced_generation_job.assert_called_once_with(
            stratum_allocations=mock_plan.allocations,
            provider_tier="primary",
        )


# ---------------------------------------------------------------------------
# run_judge_phase
# ---------------------------------------------------------------------------


class TestRunJudgePhase:
    def _make_mock_span(self):
        span = MagicMock()
        span.__enter__ = MagicMock(return_value=span)
        span.__exit__ = MagicMock(return_value=False)
        return span

    def _make_evaluated(self, score: float):
        eq = MagicMock()
        eq.evaluation.overall_score = score
        eq.evaluation.clarity_score = 0.8
        eq.evaluation.difficulty_score = 0.8
        eq.evaluation.validity_score = 0.8
        eq.evaluation.formatting_score = 0.8
        eq.evaluation.creativity_score = 0.8
        eq.evaluation.feedback = None
        eq.judge_model = "test-judge"
        # Stub difficulty placement so apply_difficulty_placement returns eq unchanged
        eq.question.difficulty_level = MagicMock()
        return eq

    @patch("app.evaluation.runner.observability")
    def test_sync_separates_approved_and_rejected(self, mock_obs):
        from app.reporting.run_summary import RunSummary as PipelineRunSummary
        from run_generation import run_judge_phase

        mock_obs.start_span.return_value = self._make_mock_span()

        eq_approved = self._make_evaluated(0.9)
        eq_rejected = self._make_evaluated(0.4)

        mock_judge = MagicMock()
        mock_judge.evaluate_question.side_effect = [eq_approved, eq_rejected]
        mock_judge.determine_difficulty_placement.return_value = (MagicMock(), None)

        metrics = PipelineRunSummary()
        metrics.start_run()

        approved, rejected, rate = run_judge_phase(
            generated_questions=[MagicMock(), MagicMock()],
            judge=mock_judge,
            min_score=0.7,
            use_async_judge=False,
            metrics=metrics,
            logger=MagicMock(),
        )

        assert len(approved) == 1
        assert len(rejected) == 1
        assert rate == pytest.approx(50.0)

    @patch("app.evaluation.runner.observability")
    def test_sync_skips_question_on_evaluation_error(self, mock_obs):
        from app.reporting.run_summary import RunSummary as PipelineRunSummary
        from run_generation import run_judge_phase

        mock_obs.start_span.return_value = self._make_mock_span()

        eq_ok = self._make_evaluated(0.9)
        mock_judge = MagicMock()
        mock_judge.evaluate_question.side_effect = [
            RuntimeError("API timeout"),
            eq_ok,
        ]
        mock_judge.determine_difficulty_placement.return_value = (MagicMock(), None)

        metrics = PipelineRunSummary()
        metrics.start_run()

        approved, rejected, rate = run_judge_phase(
            generated_questions=[MagicMock(), MagicMock()],
            judge=mock_judge,
            min_score=0.7,
            use_async_judge=False,
            metrics=metrics,
            logger=MagicMock(),
        )

        # One failed (skipped), one approved
        assert len(approved) == 1
        assert len(rejected) == 0
        assert rate == pytest.approx(50.0)  # 1 approved / 2 generated

    @patch("app.evaluation.runner.observability")
    def test_async_judge_calls_batch_method(self, mock_obs):
        from app.reporting.run_summary import RunSummary as PipelineRunSummary
        from run_generation import run_judge_phase

        mock_obs.start_span.return_value = self._make_mock_span()

        eq1 = self._make_evaluated(0.85)
        eq2 = self._make_evaluated(0.9)

        mock_judge = MagicMock()
        mock_judge.evaluate_questions_list_async = AsyncMock(return_value=[eq1, eq2])
        mock_judge.cleanup = AsyncMock()
        mock_judge.determine_difficulty_placement.return_value = (MagicMock(), None)

        metrics = PipelineRunSummary()
        metrics.start_run()

        approved, rejected, rate = run_judge_phase(
            generated_questions=[MagicMock(), MagicMock()],
            judge=mock_judge,
            min_score=0.7,
            use_async_judge=True,
            metrics=metrics,
            logger=MagicMock(),
        )

        mock_judge.evaluate_questions_list_async.assert_called_once()
        mock_judge.cleanup.assert_called_once()
        assert len(approved) == 2
        assert len(rejected) == 0
        assert rate == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# run_salvage_phase
# ---------------------------------------------------------------------------


class TestRunSalvagePhase:
    def _make_rejected(self):
        q = MagicMock()
        q.evaluation.feedback = None
        q.evaluation.validity_score = 0.3
        q.question.answer_options = []
        return q

    def test_salvages_question_via_answer_repair(self):
        from run_generation import run_salvage_phase

        rejected = self._make_rejected()
        repaired = MagicMock()
        repaired.question_text = "Repaired question text here"
        mock_salvaged_eval = MagicMock()

        with (
            patch("run_generation.attempt_answer_repair") as mock_repair,
            patch("run_generation.attempt_difficulty_reclassification") as mock_reclass,
            patch("app.data.models.EvaluatedQuestion", return_value=mock_salvaged_eval),
            patch("app.data.models.EvaluationScore", return_value=MagicMock()),
        ):
            mock_repair.return_value = (repaired, "Fixed answer from A to B")
            mock_reclass.return_value = None

            approved, rate = run_salvage_phase(
                rejected_questions=[rejected],
                approved_questions=[],
                generated_questions=[rejected],
                pipeline=MagicMock(),
                judge=MagicMock(),
                min_score=0.7,
                logger=MagicMock(),
            )

        assert len(approved) == 1
        assert rate == pytest.approx(100.0)

    def test_no_salvage_leaves_approved_unchanged(self):
        from run_generation import run_salvage_phase

        pre_approved = MagicMock()
        rejected = self._make_rejected()

        async def _async_regen(*a, **kw):
            return [], [rejected]

        with (
            patch("run_generation.attempt_answer_repair", return_value=None),
            patch(
                "run_generation.attempt_difficulty_reclassification", return_value=None
            ),
            patch("run_generation.attempt_regeneration_with_feedback", _async_regen),
        ):
            approved, rate = run_salvage_phase(
                rejected_questions=[rejected],
                approved_questions=[pre_approved],
                generated_questions=[pre_approved, rejected],
                pipeline=MagicMock(),
                judge=MagicMock(),
                min_score=0.7,
                logger=MagicMock(),
            )

        # pre_approved still in list; rejected was not salvaged
        assert pre_approved in approved
        assert rate == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# run_dedup_phase
# ---------------------------------------------------------------------------


class TestRunDedupPhase:
    def _make_mock_span(self):
        span = MagicMock()
        span.__enter__ = MagicMock(return_value=span)
        span.__exit__ = MagicMock(return_value=False)
        return span

    def _make_evaluated_question(self, difficulty="medium"):
        eq = MagicMock()
        eq.question.difficulty_level.value = difficulty
        eq.question.question_text = f"What is {difficulty}?"
        return eq

    @patch("run_generation.observability")
    def test_removes_duplicates(self, mock_obs):
        from app.data.deduplicator import DuplicateCheckResult
        from app.reporting.run_summary import RunSummary as PipelineRunSummary
        from run_generation import run_dedup_phase

        mock_obs.start_span.return_value = self._make_mock_span()

        mock_db = MagicMock()
        mock_db.get_all_questions.return_value = []

        mock_deduplicator = MagicMock()
        mock_deduplicator.check_duplicate.side_effect = [
            DuplicateCheckResult(
                is_duplicate=False, duplicate_type=None, similarity_score=0.1
            ),
            DuplicateCheckResult(
                is_duplicate=True, duplicate_type="exact", similarity_score=1.0
            ),
        ]
        mock_deduplicator.get_stats.return_value = {"cache": {"hits": 1, "misses": 1}}

        q1 = self._make_evaluated_question("easy")
        q2 = self._make_evaluated_question("easy")

        metrics = PipelineRunSummary()
        metrics.start_run()

        unique = run_dedup_phase(
            approved_questions=[q1, q2],
            db=mock_db,
            deduplicator=mock_deduplicator,
            metrics=metrics,
            logger=MagicMock(),
        )

        assert len(unique) == 1
        assert unique[0] is q1

    @patch("run_generation.observability")
    def test_fail_open_on_dedup_error(self, mock_obs):
        from app.reporting.run_summary import RunSummary as PipelineRunSummary
        from run_generation import run_dedup_phase

        mock_obs.start_span.return_value = self._make_mock_span()

        mock_db = MagicMock()
        mock_db.get_all_questions.return_value = []

        mock_deduplicator = MagicMock()
        mock_deduplicator.check_duplicate.side_effect = RuntimeError(
            "embedding API down"
        )
        mock_deduplicator.get_stats.return_value = {"cache": {"hits": 0, "misses": 0}}

        q1 = self._make_evaluated_question()

        metrics = PipelineRunSummary()
        metrics.start_run()

        # Should not raise; should include question (fail open)
        unique = run_dedup_phase(
            approved_questions=[q1],
            db=mock_db,
            deduplicator=mock_deduplicator,
            metrics=metrics,
            logger=MagicMock(),
        )

        assert len(unique) == 1
        assert unique[0] is q1


# ---------------------------------------------------------------------------
# run_insertion_phase
# ---------------------------------------------------------------------------


class TestRunInsertionPhase:
    def _make_mock_span(self):
        span = MagicMock()
        span.__enter__ = MagicMock(return_value=span)
        span.__exit__ = MagicMock(return_value=False)
        return span

    def _make_evaluated_question(self):
        eq = MagicMock()
        eq.evaluation.overall_score = 0.88
        eq.question.question_type.value = "verbal"
        return eq

    @patch("run_generation.observability")
    def test_returns_inserted_count(self, mock_obs):
        from app.reporting.run_summary import RunSummary as PipelineRunSummary
        from run_generation import run_insertion_phase

        mock_obs.start_span.return_value = self._make_mock_span()

        mock_db = MagicMock()
        mock_db.insert_evaluated_question.side_effect = [101, 102, 103]

        questions = [self._make_evaluated_question() for _ in range(3)]
        metrics = PipelineRunSummary()
        metrics.start_run()

        inserted = run_insertion_phase(
            unique_questions=questions,
            db=mock_db,
            metrics=metrics,
            logger=MagicMock(),
        )

        assert inserted == 3

    @patch("run_generation.observability")
    def test_skips_failed_insertions_and_counts_successes(self, mock_obs):
        from app.reporting.run_summary import RunSummary as PipelineRunSummary
        from run_generation import run_insertion_phase

        mock_obs.start_span.return_value = self._make_mock_span()

        mock_db = MagicMock()
        mock_db.insert_evaluated_question.side_effect = [
            201,
            Exception("constraint violation"),
            203,
        ]

        questions = [self._make_evaluated_question() for _ in range(3)]
        metrics = PipelineRunSummary()
        metrics.start_run()

        inserted = run_insertion_phase(
            unique_questions=questions,
            db=mock_db,
            metrics=metrics,
            logger=MagicMock(),
        )

        assert inserted == 2

    @patch("run_generation.observability")
    def test_all_failures_returns_zero(self, mock_obs):
        from app.reporting.run_summary import RunSummary as PipelineRunSummary
        from run_generation import run_insertion_phase

        mock_obs.start_span.return_value = self._make_mock_span()

        mock_db = MagicMock()
        mock_db.insert_evaluated_question.side_effect = Exception("DB down")

        questions = [self._make_evaluated_question() for _ in range(2)]
        metrics = PipelineRunSummary()
        metrics.start_run()

        inserted = run_insertion_phase(
            unique_questions=questions,
            db=mock_db,
            metrics=metrics,
            logger=MagicMock(),
        )

        assert inserted == 0


# ---------------------------------------------------------------------------
# _build_run_stats
# ---------------------------------------------------------------------------


class TestBuildRunStats:
    def test_basic_fields(self):
        from run_generation import _build_run_stats

        stats = {
            "target_questions": 10,
            "questions_generated": 8,
            "duration_seconds": 5.0,
        }
        summary = {
            "database": {"inserted_by_type": {"math": 3}},
            "generation": {"by_difficulty": {"easy": 4}},
            "evaluation": {"rejected": 2},
            "deduplication": {"duplicates_found": 1},
        }
        result = _build_run_stats(
            stats, inserted_count=7, approval_rate=87.5, summary=summary
        )

        assert result["questions_generated"] == 8
        assert result["questions_inserted"] == 7
        assert result["approval_rate"] == pytest.approx(87.5)
        assert result["questions_requested"] == 10
        assert result["generation_loss"] == 2
        assert result["generation_loss_pct"] == pytest.approx(20.0)
        assert result["duration_seconds"] == pytest.approx(5.0)
        assert result["by_type"] == {"math": 3}
        assert result["by_difficulty"] == {"easy": 4}
        assert result["questions_rejected"] == 2
        assert result["duplicates_found"] == 1

    def test_zero_requested_avoids_division_by_zero(self):
        from run_generation import _build_run_stats

        stats = {"target_questions": 0, "questions_generated": 0}
        result = _build_run_stats(
            stats, inserted_count=0, approval_rate=0.0, summary={}
        )

        assert result["generation_loss_pct"] == pytest.approx(0.0)
        assert result["generation_loss"] == 0

    def test_missing_stats_keys_default_to_zero(self):
        from run_generation import _build_run_stats

        result = _build_run_stats({}, inserted_count=0, approval_rate=0.0, summary={})

        assert result["questions_generated"] == 0
        assert result["questions_requested"] == 0
        assert result["duration_seconds"] == 0
        assert result["by_type"] == {}
        assert result["by_difficulty"] == {}
