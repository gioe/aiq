"""Tests for bootstrap inventory script."""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Importing from scripts directory requires adding to path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from bootstrap_inventory import (  # noqa: E402
    BootstrapAlerter,
    BootstrapConfig,
    BootstrapInventory,
    CRITICAL_FAILURE_THRESHOLD,
    EventLogger,
    ProgressReporter,
    SENSITIVE_PATTERNS,
    TypeResult,
    _sanitize_error,
    parse_arguments,
    validate_count,
    validate_types,
)


class TestBootstrapConfig:
    """Tests for BootstrapConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = BootstrapConfig()

        assert config.questions_per_type == 150
        assert len(config.types) == 6  # All question types
        assert config.dry_run is False
        assert config.use_async is True
        assert config.max_retries == 3
        assert config.retry_base_delay == pytest.approx(5.0)
        assert config.retry_max_delay == pytest.approx(60.0)

    def test_custom_values(self):
        """Test configuration with custom values."""
        config = BootstrapConfig(
            questions_per_type=50,
            types=["math", "logic"],
            dry_run=True,
            use_async=False,
            max_retries=5,
        )

        assert config.questions_per_type == 50
        assert config.types == ["math", "logic"]
        assert config.dry_run is True
        assert config.use_async is False
        assert config.max_retries == 5


class TestTypeResult:
    """Tests for TypeResult dataclass."""

    def test_success_result(self):
        """Test successful type result."""
        result = TypeResult(
            question_type="math",
            success=True,
            attempt_count=1,
            generated=50,
            inserted=45,
            approval_rate=90.0,
            duration_seconds=120.5,
        )

        assert result.success is True
        assert result.generated == 50
        assert result.error_message is None

    def test_failure_result(self):
        """Test failed type result."""
        result = TypeResult(
            question_type="verbal",
            success=False,
            attempt_count=3,
            error_message="API rate limit exceeded",
        )

        assert result.success is False
        assert result.attempt_count == 3
        assert "rate limit" in result.error_message


class TestEventLogger:
    """Tests for EventLogger class."""

    def test_log_event_creates_file(self):
        """Test that log_event creates JSONL file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            logger = EventLogger(log_dir)

            logger.log_event("test_event", "started", custom_field="value")

            assert logger.events_file.exists()

    def test_log_event_writes_json(self):
        """Test that log_event writes valid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            logger = EventLogger(log_dir)

            logger.log_event("test_event", "success", count=42)

            with open(logger.events_file) as f:
                line = f.readline()
                event = json.loads(line)

            assert event["event_type"] == "test_event"
            assert event["status"] == "success"
            assert event["count"] == 42
            assert "timestamp" in event

    def test_log_event_appends(self):
        """Test that multiple events are appended."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            logger = EventLogger(log_dir)

            logger.log_event("event1", "started")
            logger.log_event("event2", "success")
            logger.log_event("event3", "failed")

            with open(logger.events_file) as f:
                lines = f.readlines()

            assert len(lines) == 3

    def test_log_event_creates_parent_directory(self):
        """Test that log_event creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "nested" / "logs"
            logger = EventLogger(log_dir)

            logger.log_event("test", "started")

            assert log_dir.exists()
            assert logger.events_file.exists()


class TestValidateTypes:
    """Tests for validate_types function."""

    def test_validate_all_types(self):
        """Test validation with None (all types)."""
        types = validate_types(None)
        assert len(types) == 6
        assert "math" in types
        assert "logic" in types
        assert "pattern" in types

    def test_validate_single_type(self):
        """Test validation with single type."""
        types = validate_types("math")
        assert types == ["math"]

    def test_validate_multiple_types(self):
        """Test validation with comma-separated types."""
        types = validate_types("math,logic,verbal")
        assert types == ["math", "logic", "verbal"]

    def test_validate_types_with_spaces(self):
        """Test validation handles spaces in input."""
        types = validate_types("math, logic, verbal")
        assert types == ["math", "logic", "verbal"]

    def test_validate_invalid_type(self):
        """Test validation raises for invalid type."""
        with pytest.raises(ValueError) as exc_info:
            validate_types("invalid_type")

        assert "Invalid question type" in str(exc_info.value)

    def test_validate_partial_invalid(self):
        """Test validation raises even with partial invalid."""
        with pytest.raises(ValueError):
            validate_types("math,invalid,logic")


class TestValidateCount:
    """Tests for validate_count function."""

    def test_valid_count(self):
        """Test validation passes for valid count."""
        validate_count(150)  # Should not raise
        validate_count(1)  # Minimum
        validate_count(10000)  # Maximum

    def test_count_too_low(self):
        """Test validation fails for count below 1."""
        with pytest.raises(ValueError) as exc_info:
            validate_count(0)

        assert "between 1 and 10000" in str(exc_info.value)

    def test_count_too_high(self):
        """Test validation fails for count above 10000."""
        with pytest.raises(ValueError) as exc_info:
            validate_count(10001)

        assert "between 1 and 10000" in str(exc_info.value)


class TestParseArguments:
    """Tests for parse_arguments function."""

    def test_default_arguments(self):
        """Test parsing with no arguments."""
        with patch("sys.argv", ["bootstrap_inventory.py"]):
            args = parse_arguments()

        assert args.count == 150
        assert args.types is None
        assert args.dry_run is False
        assert args.no_async is False
        assert args.max_retries == 3

    def test_count_argument(self):
        """Test parsing --count argument."""
        with patch("sys.argv", ["bootstrap_inventory.py", "--count", "50"]):
            args = parse_arguments()

        assert args.count == 50

    def test_types_argument(self):
        """Test parsing --types argument."""
        with patch("sys.argv", ["bootstrap_inventory.py", "--types", "math,logic"]):
            args = parse_arguments()

        assert args.types == "math,logic"

    def test_dry_run_flag(self):
        """Test parsing --dry-run flag."""
        with patch("sys.argv", ["bootstrap_inventory.py", "--dry-run"]):
            args = parse_arguments()

        assert args.dry_run is True

    def test_no_async_flag(self):
        """Test parsing --no-async flag."""
        with patch("sys.argv", ["bootstrap_inventory.py", "--no-async"]):
            args = parse_arguments()

        assert args.no_async is True

    def test_max_retries_argument(self):
        """Test parsing --max-retries argument."""
        with patch("sys.argv", ["bootstrap_inventory.py", "--max-retries", "5"]):
            args = parse_arguments()

        assert args.max_retries == 5

    def test_verbose_flag(self):
        """Test parsing --verbose flag."""
        with patch("sys.argv", ["bootstrap_inventory.py", "--verbose"]):
            args = parse_arguments()

        assert args.verbose is True


class TestBootstrapInventory:
    """Tests for BootstrapInventory class."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return BootstrapConfig(
            questions_per_type=15,
            types=["math"],
            dry_run=True,
            use_async=True,
            max_retries=2,
        )

    @pytest.fixture
    def event_logger(self):
        """Create test event logger."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield EventLogger(Path(tmpdir))

    @pytest.fixture
    def logger(self):
        """Create test logger."""
        import logging

        return logging.getLogger("test")

    def test_calculate_retry_delay(self, config, event_logger, logger):
        """Test exponential backoff calculation with jitter."""
        bootstrap = BootstrapInventory(config, event_logger, logger)

        # With jitter, delay is base_delay + jitter (0 to 25% of base)
        # So delay 1 is between 5.0 and 5.0 + 1.25 = 6.25
        delay1 = bootstrap._calculate_retry_delay(1)
        assert 5.0 <= delay1 <= 6.25  # base delay + up to 25% jitter

        delay2 = bootstrap._calculate_retry_delay(2)
        assert 10.0 <= delay2 <= 12.5  # 5 * 2 + up to 25% jitter

        delay3 = bootstrap._calculate_retry_delay(3)
        assert 20.0 <= delay3 <= 25.0  # 5 * 4 + up to 25% jitter

        delay4 = bootstrap._calculate_retry_delay(4)
        assert 40.0 <= delay4 <= 50.0  # 5 * 8 + up to 25% jitter

        delay5 = bootstrap._calculate_retry_delay(5)
        assert 60.0 <= delay5 <= 75.0  # capped at max + up to 25% jitter

    @pytest.mark.asyncio
    async def test_initialize_pipeline(self, config, event_logger, logger):
        """Test pipeline initialization."""
        bootstrap = BootstrapInventory(config, event_logger, logger)

        with patch("bootstrap_inventory.QuestionGenerationPipeline") as mock_pipeline:
            mock_instance = Mock()
            mock_instance.generator.get_available_providers.return_value = ["openai"]
            mock_pipeline.return_value = mock_instance

            with patch("bootstrap_inventory.settings") as mock_settings:
                mock_settings.openai_api_key = (
                    "test-mock-api-key"  # pragma: allowlist secret
                )
                mock_settings.anthropic_api_key = None
                mock_settings.google_api_key = None
                mock_settings.xai_api_key = None

                pipeline = bootstrap._initialize_pipeline()

            assert pipeline is mock_instance

    @pytest.mark.asyncio
    async def test_process_type_with_retries_success(
        self, config, event_logger, logger
    ):
        """Test successful type processing."""
        bootstrap = BootstrapInventory(config, event_logger, logger)

        # Mock pipeline
        mock_pipeline = Mock()
        mock_batch = Mock()
        mock_batch.questions = [Mock() for _ in range(15)]
        mock_pipeline.generate_questions_async = AsyncMock(return_value=mock_batch)
        bootstrap.pipeline = mock_pipeline

        result = await bootstrap._process_type_with_retries("math")

        assert result.success is True
        assert result.question_type == "math"
        assert result.attempt_count == 1

    @pytest.mark.asyncio
    async def test_process_type_with_retries_failure(
        self, config, event_logger, logger
    ):
        """Test type processing with failures."""
        config.max_retries = 2
        bootstrap = BootstrapInventory(config, event_logger, logger)

        # Mock pipeline to always fail
        mock_pipeline = Mock()
        mock_pipeline.generate_questions_async = AsyncMock(
            side_effect=Exception("API Error")
        )
        bootstrap.pipeline = mock_pipeline

        result = await bootstrap._process_type_with_retries("math")

        assert result.success is False
        assert result.question_type == "math"
        assert result.attempt_count == 2
        assert "API Error" in result.error_message

    @pytest.mark.asyncio
    async def test_process_type_with_retries_eventual_success(
        self, config, event_logger, logger
    ):
        """Test type processing that succeeds on retry."""
        config.max_retries = 3
        config.retry_base_delay = 0.01  # Speed up test
        bootstrap = BootstrapInventory(config, event_logger, logger)

        # Mock pipeline to fail first, then succeed
        mock_pipeline = Mock()
        mock_batch = Mock()
        mock_batch.questions = [Mock() for _ in range(15)]

        call_count = 0

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Transient error")
            return mock_batch

        mock_pipeline.generate_questions_async = mock_generate
        bootstrap.pipeline = mock_pipeline

        result = await bootstrap._process_type_with_retries("math")

        assert result.success is True
        assert result.attempt_count == 2  # Failed once, succeeded on second

    @pytest.mark.asyncio
    async def test_run_success(self, event_logger, logger):
        """Test successful bootstrap run."""
        config = BootstrapConfig(
            questions_per_type=15,
            types=["math"],
            dry_run=True,
            use_async=True,
            max_retries=2,
        )
        bootstrap = BootstrapInventory(config, event_logger, logger)

        with patch.object(bootstrap, "_initialize_pipeline") as mock_init:
            mock_pipeline = Mock()
            mock_pipeline.generator.get_available_providers.return_value = ["openai"]
            mock_pipeline.cleanup = AsyncMock()
            mock_init.return_value = mock_pipeline

            with patch.object(bootstrap, "_process_type_with_retries") as mock_process:
                mock_process.return_value = TypeResult(
                    question_type="math",
                    success=True,
                    attempt_count=1,
                    generated=15,
                )

                exit_code = await bootstrap.run()

        assert exit_code == 0  # EXIT_SUCCESS

    @pytest.mark.asyncio
    async def test_run_partial_failure(self, event_logger, logger):
        """Test bootstrap run with some failures."""
        config = BootstrapConfig(
            questions_per_type=15,
            types=["math", "logic"],
            dry_run=True,
            use_async=True,
            max_retries=2,
        )
        bootstrap = BootstrapInventory(config, event_logger, logger)

        with patch.object(bootstrap, "_initialize_pipeline") as mock_init:
            mock_pipeline = Mock()
            mock_pipeline.generator.get_available_providers.return_value = ["openai"]
            mock_pipeline.cleanup = AsyncMock()
            mock_init.return_value = mock_pipeline

            results = [
                TypeResult(
                    question_type="math", success=True, attempt_count=1, generated=15
                ),
                TypeResult(
                    question_type="logic",
                    success=False,
                    attempt_count=2,
                    error_message="Failed",
                ),
            ]

            with patch.object(
                bootstrap, "_process_type_with_retries", side_effect=results
            ):
                exit_code = await bootstrap.run()

        assert exit_code == 1  # EXIT_PARTIAL_FAILURE

    @pytest.mark.asyncio
    async def test_run_config_error(self, event_logger, logger):
        """Test bootstrap run with configuration error."""
        config = BootstrapConfig(
            questions_per_type=15,
            types=["math"],
            dry_run=True,
        )
        bootstrap = BootstrapInventory(config, event_logger, logger)

        with patch.object(bootstrap, "_initialize_pipeline") as mock_init:
            mock_init.side_effect = ValueError("No API keys configured")

            exit_code = await bootstrap.run()

        assert exit_code == 2  # EXIT_CONFIG_ERROR


class TestSyncGeneration:
    """Tests for synchronous generation mode."""

    @pytest.fixture
    def config(self):
        """Create test configuration with async disabled."""
        return BootstrapConfig(
            questions_per_type=15,
            types=["math"],
            dry_run=True,
            use_async=False,  # Sync mode
            max_retries=2,
        )

    @pytest.fixture
    def event_logger(self):
        """Create test event logger."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield EventLogger(Path(tmpdir))

    @pytest.fixture
    def logger(self):
        """Create test logger."""
        import logging

        return logging.getLogger("test")

    def test_generate_type_sync(self, config, event_logger, logger):
        """Test synchronous type generation."""
        bootstrap = BootstrapInventory(config, event_logger, logger)

        mock_pipeline = Mock()
        mock_batch = Mock()
        mock_batch.questions = [Mock() for _ in range(5)]
        mock_pipeline.generate_questions.return_value = mock_batch
        bootstrap.pipeline = mock_pipeline

        from app.models import QuestionType

        result = bootstrap._generate_type_sync(QuestionType.MATH, 15)

        assert "questions" in result
        assert "generated" in result
        assert "target" in result
        # Called once per difficulty level
        assert mock_pipeline.generate_questions.call_count == 3


class TestDistributionAcrossDifficulties:
    """Tests for question distribution across difficulty levels."""

    @pytest.fixture
    def event_logger(self):
        """Create test event logger."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield EventLogger(Path(tmpdir))

    @pytest.fixture
    def logger(self):
        """Create test logger."""
        import logging

        return logging.getLogger("test")

    def test_even_distribution(self, event_logger, logger):
        """Test that questions are evenly distributed across difficulties."""
        config = BootstrapConfig(questions_per_type=30)  # 10 per difficulty
        bootstrap = BootstrapInventory(config, event_logger, logger)

        mock_pipeline = Mock()
        mock_batch = Mock()
        mock_batch.questions = []
        mock_pipeline.generate_questions.return_value = mock_batch
        bootstrap.pipeline = mock_pipeline

        from app.models import QuestionType

        bootstrap._generate_type_sync(QuestionType.MATH, 30)

        # Check the counts passed to generate_questions
        calls = mock_pipeline.generate_questions.call_args_list
        counts = [call.kwargs["count"] for call in calls]

        assert counts == [10, 10, 10]  # Even distribution

    def test_uneven_distribution(self, event_logger, logger):
        """Test distribution with remainder."""
        config = BootstrapConfig(questions_per_type=32)  # 10 + 10 + 10 + 2 remainder
        bootstrap = BootstrapInventory(config, event_logger, logger)

        mock_pipeline = Mock()
        mock_batch = Mock()
        mock_batch.questions = []
        mock_pipeline.generate_questions.return_value = mock_batch
        bootstrap.pipeline = mock_pipeline

        from app.models import QuestionType

        bootstrap._generate_type_sync(QuestionType.MATH, 32)

        calls = mock_pipeline.generate_questions.call_args_list
        counts = [call.kwargs["count"] for call in calls]

        # 32 / 3 = 10 with remainder 2
        # Remainder distributed to first two difficulties
        assert counts == [11, 11, 10]

    def test_small_count_distribution(self, event_logger, logger):
        """Test distribution with count smaller than 3."""
        config = BootstrapConfig(questions_per_type=2)
        bootstrap = BootstrapInventory(config, event_logger, logger)

        mock_pipeline = Mock()
        mock_batch = Mock()
        mock_batch.questions = []
        mock_pipeline.generate_questions.return_value = mock_batch
        bootstrap.pipeline = mock_pipeline

        from app.models import QuestionType

        bootstrap._generate_type_sync(QuestionType.MATH, 2)

        calls = mock_pipeline.generate_questions.call_args_list
        counts = [call.kwargs["count"] for call in calls]

        # Only 2 questions, distributed to first 2 difficulties
        assert counts == [1, 1]


class TestProgressReporter:
    """Tests for ProgressReporter class."""

    def test_quiet_mode_suppresses_output(self, capsys):
        """Test that quiet mode suppresses all output."""
        reporter = ProgressReporter(quiet=True)

        reporter.banner(
            questions_per_type=150,
            types=["math", "logic"],
            max_retries=3,
            use_async=True,
            use_batch=True,
            dry_run=False,
        )
        reporter.batch_mode_status(True, "Google provider detected")
        reporter.type_start(1, 2, "math", 150)
        reporter.phase_transition("GENERATION", "Starting")
        reporter.progress("Test message")
        reporter.approval_rate(100, 150)
        reporter.inserted(100)
        reporter.retry_warning(2, 3, "math", 5.0)
        reporter.type_complete("math", True, 60.0, 100)
        reporter.type_error("Test error")
        reporter.summary(1, 1, 2, 120.0, [])
        reporter.final_status(True)

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_normal_mode_prints_banner(self, capsys):
        """Test that normal mode prints banner."""
        reporter = ProgressReporter(quiet=False)

        reporter.banner(
            questions_per_type=150,
            types=["math", "logic"],
            max_retries=3,
            use_async=True,
            use_batch=True,
            dry_run=False,
        )

        captured = capsys.readouterr()
        assert "AIQ Question Inventory Bootstrap Script" in captured.out
        assert "Questions per type: 150" in captured.out
        assert "math, logic" in captured.out

    def test_batch_mode_status(self, capsys):
        """Test batch mode status output."""
        reporter = ProgressReporter(quiet=False)

        reporter.batch_mode_status(True, "Google provider detected")

        captured = capsys.readouterr()
        assert "ENABLED" in captured.out
        assert "Google provider detected" in captured.out

    def test_batch_mode_status_disabled(self, capsys):
        """Test batch mode status output when disabled."""
        reporter = ProgressReporter(quiet=False)

        reporter.batch_mode_status(False, "--no-batch flag")

        captured = capsys.readouterr()
        assert "DISABLED" in captured.out
        assert "--no-batch flag" in captured.out

    def test_type_start(self, capsys):
        """Test type start output."""
        reporter = ProgressReporter(quiet=False)

        reporter.type_start(1, 3, "math", 150)

        captured = capsys.readouterr()
        assert "[1/3]" in captured.out
        assert "math" in captured.out
        assert "150 questions" in captured.out

    def test_phase_transition(self, capsys):
        """Test phase transition output."""
        reporter = ProgressReporter(quiet=False)

        reporter.phase_transition("GENERATION", "Starting batch job")

        captured = capsys.readouterr()
        assert "[PHASE]" in captured.out
        assert "GENERATION" in captured.out
        assert "Starting batch job" in captured.out

    def test_phase_transition_no_detail(self, capsys):
        """Test phase transition output without detail."""
        reporter = ProgressReporter(quiet=False)

        reporter.phase_transition("VALIDATION")

        captured = capsys.readouterr()
        assert "[PHASE]" in captured.out
        assert "VALIDATION" in captured.out

    def test_progress_message(self, capsys):
        """Test progress message output."""
        reporter = ProgressReporter(quiet=False)

        reporter.progress("Processing 50/150 questions")

        captured = capsys.readouterr()
        assert "[PROGRESS]" in captured.out
        assert "Processing 50/150 questions" in captured.out

    def test_approval_rate(self, capsys):
        """Test approval rate output."""
        reporter = ProgressReporter(quiet=False)

        reporter.approval_rate(120, 150)

        captured = capsys.readouterr()
        assert "[PROGRESS]" in captured.out
        assert "Approved: 120/150" in captured.out
        assert "80.0%" in captured.out

    def test_approval_rate_zero_total(self, capsys):
        """Test approval rate with zero total."""
        reporter = ProgressReporter(quiet=False)

        reporter.approval_rate(0, 0)

        captured = capsys.readouterr()
        assert "0.0%" in captured.out

    def test_inserted(self, capsys):
        """Test inserted count output."""
        reporter = ProgressReporter(quiet=False)

        reporter.inserted(118)

        captured = capsys.readouterr()
        assert "[PROGRESS]" in captured.out
        assert "Inserted 118 questions" in captured.out

    def test_retry_warning(self, capsys):
        """Test retry warning output."""
        reporter = ProgressReporter(quiet=False)

        reporter.retry_warning(2, 3, "math", 10.5)

        captured = capsys.readouterr()
        assert "[RETRY]" in captured.out
        assert "2/3" in captured.out
        assert "math" in captured.out
        assert "10.5s" in captured.out

    def test_type_complete_success(self, capsys):
        """Test type complete output for success."""
        reporter = ProgressReporter(quiet=False)

        reporter.type_complete("math", True, 45.5, 148)

        captured = capsys.readouterr()
        assert "math" in captured.out
        assert "completed successfully" in captured.out
        assert "45.5s" in captured.out
        assert "148" in captured.out

    def test_type_complete_failure(self, capsys):
        """Test type complete output for failure."""
        reporter = ProgressReporter(quiet=False)

        reporter.type_complete("verbal", False, 30.2)

        captured = capsys.readouterr()
        assert "verbal" in captured.out
        assert "FAILED" in captured.out
        assert "30.2s" in captured.out

    def test_type_error(self, capsys):
        """Test type error output."""
        reporter = ProgressReporter(quiet=False)

        reporter.type_error("API rate limit exceeded")

        captured = capsys.readouterr()
        assert "Error:" in captured.out
        assert "API rate limit exceeded" in captured.out

    def test_type_error_truncation(self, capsys):
        """Test that long error messages are truncated with ellipsis."""
        reporter = ProgressReporter(quiet=False)

        long_error = "x" * 300
        reporter.type_error(long_error)

        captured = capsys.readouterr()
        # Should be truncated to 200 chars + "..." ellipsis = 203 total
        output = captured.out.split("Error: ")[1].strip()
        assert len(output) == 203
        assert output.endswith("...")

    def test_summary(self, capsys):
        """Test summary output."""
        reporter = ProgressReporter(quiet=False)

        results = [
            TypeResult("math", True, 1, 150, 148),
            TypeResult("logic", False, 3, error_message="API timeout"),
        ]
        reporter.summary(1, 1, 2, 120.5, results)

        captured = capsys.readouterr()
        assert "BOOTSTRAP SUMMARY" in captured.out
        assert "Successful types: 1 / 2" in captured.out
        assert "Failed types: 1" in captured.out
        assert "2m 0s" in captured.out
        assert "[OK]" in captured.out
        assert "math" in captured.out
        assert "[FAILED]" in captured.out
        assert "logic" in captured.out

    def test_final_status_success(self, capsys):
        """Test final status for success."""
        reporter = ProgressReporter(quiet=False)

        reporter.final_status(True)

        captured = capsys.readouterr()
        assert "completed successfully" in captured.out

    def test_final_status_failure(self, capsys):
        """Test final status for failure."""
        reporter = ProgressReporter(quiet=False)

        reporter.final_status(False)

        captured = capsys.readouterr()
        assert "completed with failures" in captured.out

    def test_truncate_short_message(self):
        """Test _truncate returns short messages unchanged."""
        reporter = ProgressReporter(quiet=False)

        result = reporter._truncate("Short message")

        assert result == "Short message"

    def test_truncate_exact_length_message(self):
        """Test _truncate returns message at exact limit unchanged."""
        reporter = ProgressReporter(quiet=False)

        # Exactly 200 characters
        message = "x" * 200
        result = reporter._truncate(message)

        assert result == message
        assert len(result) == 200

    def test_truncate_long_message(self):
        """Test _truncate truncates long messages with ellipsis."""
        reporter = ProgressReporter(quiet=False)

        message = "x" * 300
        result = reporter._truncate(message)

        # Should be 200 chars + "..." = 203 total
        assert len(result) == 203
        assert result.endswith("...")
        assert result == "x" * 200 + "..."

    def test_truncate_custom_max_length(self):
        """Test _truncate with custom max_length parameter."""
        reporter = ProgressReporter(quiet=False)

        message = "x" * 200
        result = reporter._truncate(message, max_length=100)

        # Should be 100 chars + "..." = 103 total
        assert len(result) == 103
        assert result.endswith("...")
        assert result == "x" * 100 + "..."


class TestQuietFlagParsing:
    """Tests for --quiet flag argument parsing."""

    def test_quiet_flag_short(self):
        """Test parsing -q flag."""
        with patch("sys.argv", ["bootstrap_inventory.py", "-q"]):
            args = parse_arguments()

        assert args.quiet is True

    def test_quiet_flag_long(self):
        """Test parsing --quiet flag."""
        with patch("sys.argv", ["bootstrap_inventory.py", "--quiet"]):
            args = parse_arguments()

        assert args.quiet is True

    def test_quiet_flag_default(self):
        """Test quiet defaults to False."""
        with patch("sys.argv", ["bootstrap_inventory.py"]):
            args = parse_arguments()

        assert args.quiet is False

    def test_quiet_with_other_flags(self):
        """Test --quiet combined with other flags."""
        with patch(
            "sys.argv",
            ["bootstrap_inventory.py", "--quiet", "--verbose", "--dry-run"],
        ):
            args = parse_arguments()

        assert args.quiet is True
        assert args.verbose is True
        assert args.dry_run is True


class TestBootstrapConfigQuiet:
    """Tests for quiet mode in BootstrapConfig."""

    def test_quiet_default(self):
        """Test quiet defaults to False."""
        config = BootstrapConfig()
        assert config.quiet is False

    def test_quiet_enabled(self):
        """Test quiet can be enabled."""
        config = BootstrapConfig(quiet=True)
        assert config.quiet is True


class TestBootstrapInventoryWithProgressReporter:
    """Tests for BootstrapInventory with ProgressReporter integration."""

    @pytest.fixture
    def event_logger(self):
        """Create test event logger."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield EventLogger(Path(tmpdir))

    @pytest.fixture
    def logger(self):
        """Create test logger."""
        import logging

        return logging.getLogger("test")

    def test_creates_progress_reporter_from_config(self, event_logger, logger):
        """Test that BootstrapInventory creates ProgressReporter from config."""
        config = BootstrapConfig(quiet=True)
        bootstrap = BootstrapInventory(config, event_logger, logger)

        assert bootstrap.progress is not None
        assert bootstrap.progress.quiet is True

    def test_uses_provided_progress_reporter(self, event_logger, logger):
        """Test that BootstrapInventory uses provided ProgressReporter."""
        config = BootstrapConfig(quiet=False)
        custom_reporter = ProgressReporter(quiet=True)

        bootstrap = BootstrapInventory(
            config, event_logger, logger, progress_reporter=custom_reporter
        )

        # Should use provided reporter, not create from config
        assert bootstrap.progress is custom_reporter
        assert bootstrap.progress.quiet is True

    @pytest.mark.asyncio
    async def test_run_quiet_mode(self, event_logger, logger, capsys):
        """Test that run() respects quiet mode."""
        config = BootstrapConfig(
            questions_per_type=15,
            types=["math"],
            dry_run=True,
            quiet=True,
        )
        bootstrap = BootstrapInventory(config, event_logger, logger)

        with patch.object(bootstrap, "_initialize_pipeline") as mock_init:
            mock_pipeline = Mock()
            mock_pipeline.generator.get_available_providers.return_value = ["openai"]
            mock_pipeline.cleanup = AsyncMock()
            mock_init.return_value = mock_pipeline

            with patch.object(bootstrap, "_process_type_with_retries") as mock_process:
                mock_process.return_value = TypeResult(
                    question_type="math",
                    success=True,
                    attempt_count=1,
                    generated=15,
                )

                await bootstrap.run()

        captured = capsys.readouterr()
        # Quiet mode should suppress all terminal output
        assert captured.out == ""


class TestBootstrapAlerter:
    """Tests for BootstrapAlerter class."""

    @pytest.fixture
    def event_logger(self):
        """Create test event logger."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield EventLogger(Path(tmpdir))

    @pytest.fixture
    def log_dir(self):
        """Create temporary log directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def logger(self):
        """Create test logger."""
        import logging

        return logging.getLogger("test_alerter")

    def test_no_alert_below_threshold(self, event_logger, log_dir, logger):
        """Test that no alert is sent when failures are below threshold."""
        alerter = BootstrapAlerter(
            alert_manager=None,
            event_logger=event_logger,
            logger=logger,
            log_dir=log_dir,
        )

        # Only 2 failures (below threshold of 3)
        results = [
            TypeResult("math", True, 1, 100),
            TypeResult("logic", False, 3, error_message="Error 1"),
            TypeResult("pattern", False, 3, error_message="Error 2"),
            TypeResult("verbal", True, 1, 100),
        ]

        alert_sent = alerter.check_and_alert(results)

        assert alert_sent is False
        # No failure flag should be written
        flag_path = log_dir / "bootstrap_failure.flag"
        assert not flag_path.exists()

    def test_alert_at_threshold(self, event_logger, log_dir, logger):
        """Test that alert is sent when failures meet threshold."""
        alerter = BootstrapAlerter(
            alert_manager=None,  # No email alerting configured
            event_logger=event_logger,
            logger=logger,
            log_dir=log_dir,
        )

        # Exactly CRITICAL_FAILURE_THRESHOLD failures
        results = [
            TypeResult("math", False, 3, error_message="Error 1"),
            TypeResult("logic", False, 3, error_message="Error 2"),
            TypeResult("pattern", False, 3, error_message="Error 3"),
            TypeResult("verbal", True, 1, 100),
        ]

        alert_sent = alerter.check_and_alert(results)

        # Even without AlertManager, should return False but write flag
        assert alert_sent is False

        # Failure flag should be written
        flag_path = log_dir / "bootstrap_failure.flag"
        assert flag_path.exists()

        # Verify flag content
        with open(flag_path) as f:
            content = json.load(f)

        assert content["failed_count"] == CRITICAL_FAILURE_THRESHOLD
        assert set(content["failed_types"]) == {"math", "logic", "pattern"}
        assert content["threshold"] == CRITICAL_FAILURE_THRESHOLD

    def test_alert_above_threshold(self, event_logger, log_dir, logger):
        """Test alert when failures exceed threshold."""
        alerter = BootstrapAlerter(
            alert_manager=None,
            event_logger=event_logger,
            logger=logger,
            log_dir=log_dir,
        )

        # 5 failures (above threshold of 3)
        results = [
            TypeResult("math", False, 3, error_message="Error 1"),
            TypeResult("logic", False, 3, error_message="Error 2"),
            TypeResult("pattern", False, 3, error_message="Error 3"),
            TypeResult("verbal", False, 3, error_message="Error 4"),
            TypeResult("spatial", False, 3, error_message="Error 5"),
        ]

        alerter.check_and_alert(results)

        flag_path = log_dir / "bootstrap_failure.flag"
        with open(flag_path) as f:
            content = json.load(f)

        assert content["failed_count"] == 5

    def test_no_duplicate_alerts(self, event_logger, log_dir, logger):
        """Test that duplicate alerts are prevented."""
        alerter = BootstrapAlerter(
            alert_manager=None,
            event_logger=event_logger,
            logger=logger,
            log_dir=log_dir,
        )

        results = [
            TypeResult("math", False, 3, error_message="Error 1"),
            TypeResult("logic", False, 3, error_message="Error 2"),
            TypeResult("pattern", False, 3, error_message="Error 3"),
        ]

        # First call - should process
        alerter.check_and_alert(results)
        assert alerter._alert_sent is True

        # Remove flag to verify second call doesn't recreate it
        flag_path = log_dir / "bootstrap_failure.flag"
        flag_path.unlink()

        # Second call - should be skipped
        result = alerter.check_and_alert(results)
        assert result is False
        assert not flag_path.exists()  # Should not be recreated

    def test_alert_with_alert_manager(self, event_logger, log_dir, logger):
        """Test alert is sent via AlertManager when configured."""
        mock_alert_manager = Mock()
        mock_alert_manager.send_alert.return_value = True

        alerter = BootstrapAlerter(
            alert_manager=mock_alert_manager,
            event_logger=event_logger,
            logger=logger,
            log_dir=log_dir,
        )

        results = [
            TypeResult("math", False, 3, error_message="API timeout"),
            TypeResult("logic", False, 3, error_message="Rate limit"),
            TypeResult("pattern", False, 3, error_message="Server error"),
        ]

        alert_sent = alerter.check_and_alert(results)

        assert alert_sent is True
        mock_alert_manager.send_alert.assert_called_once()

        # Verify the ClassifiedError was created correctly
        call_args = mock_alert_manager.send_alert.call_args
        classified_error = call_args[0][0]
        context = call_args[0][1]

        assert "SCRIPT_FAILURE" in str(classified_error.category)
        assert "CRITICAL" in str(classified_error.severity)
        assert "3 question types failed" in classified_error.message
        assert "math" in context
        assert "logic" in context
        assert "pattern" in context

    def test_alert_manager_failure(self, event_logger, log_dir, logger):
        """Test handling when AlertManager fails to send."""
        mock_alert_manager = Mock()
        mock_alert_manager.send_alert.return_value = False  # Simulate failure

        alerter = BootstrapAlerter(
            alert_manager=mock_alert_manager,
            event_logger=event_logger,
            logger=logger,
            log_dir=log_dir,
        )

        results = [
            TypeResult("math", False, 3, error_message="Error 1"),
            TypeResult("logic", False, 3, error_message="Error 2"),
            TypeResult("pattern", False, 3, error_message="Error 3"),
        ]

        alert_sent = alerter.check_and_alert(results)

        assert alert_sent is False
        # Flag should still be written even if email fails
        flag_path = log_dir / "bootstrap_failure.flag"
        assert flag_path.exists()

    def test_failure_flag_contains_error_sample(self, event_logger, log_dir, logger):
        """Test that failure flag includes error sample from first failure."""
        alerter = BootstrapAlerter(
            alert_manager=None,
            event_logger=event_logger,
            logger=logger,
            log_dir=log_dir,
        )

        results = [
            TypeResult("math", False, 3, error_message="First error: API timeout"),
            TypeResult("logic", False, 3, error_message="Second error: Rate limit"),
            TypeResult("pattern", False, 3, error_message="Third error: Server down"),
        ]

        alerter.check_and_alert(results)

        flag_path = log_dir / "bootstrap_failure.flag"
        with open(flag_path) as f:
            content = json.load(f)

        assert content["error_sample"] == "First error: API timeout"

    def test_failure_flag_truncates_long_error(self, event_logger, log_dir, logger):
        """Test that long error messages are truncated in failure flag."""
        alerter = BootstrapAlerter(
            alert_manager=None,
            event_logger=event_logger,
            logger=logger,
            log_dir=log_dir,
        )

        long_error = "x" * 500
        results = [
            TypeResult("math", False, 3, error_message=long_error),
            TypeResult("logic", False, 3, error_message="Error 2"),
            TypeResult("pattern", False, 3, error_message="Error 3"),
        ]

        alerter.check_and_alert(results)

        flag_path = log_dir / "bootstrap_failure.flag"
        with open(flag_path) as f:
            content = json.load(f)

        # Should be truncated to 200 chars
        assert len(content["error_sample"]) == 200

    def test_event_logged_on_critical_failure(self, log_dir, logger):
        """Test that multi_type_failure event is logged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            event_log_dir = Path(tmpdir)
            event_logger = EventLogger(event_log_dir)

            alerter = BootstrapAlerter(
                alert_manager=None,
                event_logger=event_logger,
                logger=logger,
                log_dir=log_dir,
            )

            results = [
                TypeResult("math", False, 3, error_message="Error 1"),
                TypeResult("logic", False, 3, error_message="Error 2"),
                TypeResult("pattern", False, 3, error_message="Error 3"),
            ]

            alerter.check_and_alert(results)

            # Read the event log
            with open(event_logger.events_file) as f:
                events = [json.loads(line) for line in f]

            # Find the multi_type_failure event
            failure_events = [
                e for e in events if e["event_type"] == "multi_type_failure"
            ]
            assert len(failure_events) == 1

            event = failure_events[0]
            assert event["status"] == "critical"
            assert event["failed_count"] == 3
            assert event["threshold"] == CRITICAL_FAILURE_THRESHOLD

    def test_zero_failures_no_action(self, event_logger, log_dir, logger):
        """Test that zero failures don't trigger any alerting."""
        alerter = BootstrapAlerter(
            alert_manager=None,
            event_logger=event_logger,
            logger=logger,
            log_dir=log_dir,
        )

        results = [
            TypeResult("math", True, 1, 100),
            TypeResult("logic", True, 1, 100),
            TypeResult("pattern", True, 1, 100),
        ]

        alert_sent = alerter.check_and_alert(results)

        assert alert_sent is False
        flag_path = log_dir / "bootstrap_failure.flag"
        assert not flag_path.exists()


class TestCriticalFailureThreshold:
    """Tests for CRITICAL_FAILURE_THRESHOLD constant."""

    def test_threshold_value(self):
        """Test that threshold is set to 3 (matching bash script)."""
        assert CRITICAL_FAILURE_THRESHOLD == 3


class TestBootstrapInventoryWithAlerter:
    """Tests for BootstrapInventory integration with BootstrapAlerter."""

    @pytest.fixture
    def event_logger(self):
        """Create test event logger."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield EventLogger(Path(tmpdir))

    @pytest.fixture
    def log_dir(self):
        """Create temporary log directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def logger(self):
        """Create test logger."""
        import logging

        return logging.getLogger("test")

    @pytest.mark.asyncio
    async def test_alerter_called_on_failures(self, event_logger, log_dir, logger):
        """Test that alerter is called when there are failures."""
        alerter = BootstrapAlerter(
            alert_manager=None,
            event_logger=event_logger,
            logger=logger,
            log_dir=log_dir,
        )

        config = BootstrapConfig(
            questions_per_type=15,
            types=["math", "logic", "pattern", "verbal"],
            dry_run=True,
        )
        bootstrap = BootstrapInventory(config, event_logger, logger, alerter=alerter)

        with patch.object(bootstrap, "_initialize_pipeline") as mock_init:
            mock_pipeline = Mock()
            mock_pipeline.generator.get_available_providers.return_value = ["openai"]
            mock_pipeline.cleanup = AsyncMock()
            mock_init.return_value = mock_pipeline

            # Create results that exceed threshold
            results = [
                TypeResult("math", False, 3, error_message="Error 1"),
                TypeResult("logic", False, 3, error_message="Error 2"),
                TypeResult("pattern", False, 3, error_message="Error 3"),
                TypeResult("verbal", True, 1, 100),
            ]

            with patch.object(
                bootstrap, "_process_type_with_retries", side_effect=results
            ):
                await bootstrap.run()

        # Alerter should have been triggered
        flag_path = log_dir / "bootstrap_failure.flag"
        assert flag_path.exists()

    @pytest.mark.asyncio
    async def test_alerter_not_called_on_success(self, event_logger, log_dir, logger):
        """Test that alerter is not called when all types succeed."""
        alerter = BootstrapAlerter(
            alert_manager=None,
            event_logger=event_logger,
            logger=logger,
            log_dir=log_dir,
        )

        config = BootstrapConfig(
            questions_per_type=15,
            types=["math"],
            dry_run=True,
        )
        bootstrap = BootstrapInventory(config, event_logger, logger, alerter=alerter)

        with patch.object(bootstrap, "_initialize_pipeline") as mock_init:
            mock_pipeline = Mock()
            mock_pipeline.generator.get_available_providers.return_value = ["openai"]
            mock_pipeline.cleanup = AsyncMock()
            mock_init.return_value = mock_pipeline

            with patch.object(bootstrap, "_process_type_with_retries") as mock_process:
                mock_process.return_value = TypeResult(
                    question_type="math",
                    success=True,
                    attempt_count=1,
                    generated=15,
                )

                await bootstrap.run()

        # No failure flag should exist
        flag_path = log_dir / "bootstrap_failure.flag"
        assert not flag_path.exists()


class TestParallelMode:
    """Tests for parallel generation mode."""

    @pytest.fixture
    def event_logger(self):
        """Create test event logger."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield EventLogger(Path(tmpdir))

    @pytest.fixture
    def logger(self):
        """Create test logger."""
        import logging

        return logging.getLogger("test_parallel")

    def test_parallel_config_defaults(self):
        """Test default parallel config values."""
        config = BootstrapConfig()

        assert config.parallel is False
        assert config.max_parallel == 2

    def test_parallel_config_custom(self):
        """Test custom parallel config values."""
        config = BootstrapConfig(parallel=True, max_parallel=4)

        assert config.parallel is True
        assert config.max_parallel == 4

    def test_parallel_flag_parsing(self):
        """Test parsing --parallel flag."""
        with patch("sys.argv", ["bootstrap_inventory.py", "--parallel"]):
            args = parse_arguments()

        assert args.parallel is True

    def test_max_parallel_argument_parsing(self):
        """Test parsing --max-parallel argument."""
        with patch(
            "sys.argv", ["bootstrap_inventory.py", "--parallel", "--max-parallel", "4"]
        ):
            args = parse_arguments()

        assert args.parallel is True
        assert args.max_parallel == 4

    def test_max_parallel_default(self):
        """Test that --max-parallel defaults to 2."""
        with patch("sys.argv", ["bootstrap_inventory.py"]):
            args = parse_arguments()

        assert args.max_parallel == 2

    @pytest.mark.asyncio
    async def test_process_types_parallel_creates_semaphore(self, event_logger, logger):
        """Test that parallel processing uses semaphore for rate limiting."""
        config = BootstrapConfig(
            questions_per_type=15,
            types=["math", "logic", "pattern"],
            dry_run=True,
            parallel=True,
            max_parallel=2,
        )
        bootstrap = BootstrapInventory(config, event_logger, logger)

        # Track concurrent operations
        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        async def mock_process(question_type):
            nonlocal max_concurrent, current_concurrent

            async with lock:
                current_concurrent += 1
                max_concurrent = max(max_concurrent, current_concurrent)

            await asyncio.sleep(0.1)  # Simulate work

            async with lock:
                current_concurrent -= 1

            return TypeResult(
                question_type=question_type,
                success=True,
                attempt_count=1,
                generated=15,
            )

        with patch.object(
            bootstrap, "_process_type_with_retries", side_effect=mock_process
        ):
            results = await bootstrap._process_types_parallel()

        # With max_parallel=2, we should never exceed 2 concurrent operations
        assert max_concurrent <= 2
        assert len(results) == 3
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_process_types_parallel_handles_failures(self, event_logger, logger):
        """Test that parallel processing handles partial failures gracefully."""
        config = BootstrapConfig(
            questions_per_type=15,
            types=["math", "logic", "pattern"],
            dry_run=True,
            parallel=True,
            max_parallel=3,
        )
        bootstrap = BootstrapInventory(config, event_logger, logger)

        async def mock_process(question_type):
            if question_type == "logic":
                return TypeResult(
                    question_type=question_type,
                    success=False,
                    attempt_count=3,
                    error_message="API timeout",
                )
            return TypeResult(
                question_type=question_type,
                success=True,
                attempt_count=1,
                generated=15,
            )

        with patch.object(
            bootstrap, "_process_type_with_retries", side_effect=mock_process
        ):
            results = await bootstrap._process_types_parallel()

        # All types should have results
        assert len(results) == 3

        # Count successes and failures
        successes = [r for r in results if r.success]
        failures = [r for r in results if not r.success]

        assert len(successes) == 2
        assert len(failures) == 1
        assert failures[0].question_type == "logic"

    @pytest.mark.asyncio
    async def test_process_types_parallel_handles_exceptions(
        self, event_logger, logger
    ):
        """Test that parallel processing handles unexpected exceptions."""
        config = BootstrapConfig(
            questions_per_type=15,
            types=["math", "logic"],
            dry_run=True,
            parallel=True,
            max_parallel=2,
        )
        bootstrap = BootstrapInventory(config, event_logger, logger)

        async def mock_process(question_type):
            if question_type == "logic":
                raise RuntimeError("Unexpected error in processing")
            return TypeResult(
                question_type=question_type,
                success=True,
                attempt_count=1,
                generated=15,
            )

        with patch.object(
            bootstrap, "_process_type_with_retries", side_effect=mock_process
        ):
            results = await bootstrap._process_types_parallel()

        # Both types should have results
        assert len(results) == 2

        # One should be success, one should be failed due to exception
        math_result = next(r for r in results if r.question_type == "math")
        logic_result = next(r for r in results if r.question_type == "logic")

        assert math_result.success is True
        assert logic_result.success is False
        assert "Unexpected error" in logic_result.error_message

    @pytest.mark.asyncio
    async def test_run_uses_parallel_when_enabled(self, event_logger, logger):
        """Test that run() uses parallel processing when parallel=True."""
        config = BootstrapConfig(
            questions_per_type=15,
            types=["math", "logic"],
            dry_run=True,
            parallel=True,
            max_parallel=2,
        )
        bootstrap = BootstrapInventory(config, event_logger, logger)

        with patch.object(bootstrap, "_initialize_pipeline") as mock_init:
            mock_pipeline = Mock()
            mock_pipeline.generator.get_available_providers.return_value = ["openai"]
            mock_pipeline.cleanup = AsyncMock()
            mock_init.return_value = mock_pipeline

            with patch.object(bootstrap, "_process_types_parallel") as mock_parallel:
                mock_parallel.return_value = [
                    TypeResult("math", True, 1, 15),
                    TypeResult("logic", True, 1, 15),
                ]

                await bootstrap.run()

            # Should have called parallel processing
            mock_parallel.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_uses_sequential_when_disabled(self, event_logger, logger):
        """Test that run() uses sequential processing when parallel=False."""
        config = BootstrapConfig(
            questions_per_type=15,
            types=["math"],
            dry_run=True,
            parallel=False,
        )
        bootstrap = BootstrapInventory(config, event_logger, logger)

        with patch.object(bootstrap, "_initialize_pipeline") as mock_init:
            mock_pipeline = Mock()
            mock_pipeline.generator.get_available_providers.return_value = ["openai"]
            mock_pipeline.cleanup = AsyncMock()
            mock_init.return_value = mock_pipeline

            with patch.object(bootstrap, "_process_types_parallel") as mock_parallel:
                with patch.object(
                    bootstrap, "_process_type_with_retries"
                ) as mock_sequential:
                    mock_sequential.return_value = TypeResult("math", True, 1, 15)

                    await bootstrap.run()

                # Should have called sequential processing, not parallel
                mock_parallel.assert_not_called()
                mock_sequential.assert_called_once()


class TestProgressReporterParallelMode:
    """Tests for ProgressReporter in parallel mode."""

    def test_banner_shows_parallel_disabled(self, capsys):
        """Test banner shows parallel mode disabled."""
        reporter = ProgressReporter(quiet=False)

        reporter.banner(
            questions_per_type=150,
            types=["math", "logic"],
            max_retries=3,
            use_async=True,
            use_batch=True,
            dry_run=False,
            parallel=False,
            max_parallel=2,
        )

        captured = capsys.readouterr()
        assert "Parallel mode: disabled" in captured.out

    def test_banner_shows_parallel_enabled(self, capsys):
        """Test banner shows parallel mode enabled with concurrency."""
        reporter = ProgressReporter(quiet=False)

        reporter.banner(
            questions_per_type=150,
            types=["math", "logic"],
            max_retries=3,
            use_async=True,
            use_batch=True,
            dry_run=False,
            parallel=True,
            max_parallel=3,
        )

        captured = capsys.readouterr()
        assert "Parallel mode: enabled (max 3 concurrent types)" in captured.out

    def test_type_start_parallel_mode(self, capsys):
        """Test type_start output in parallel mode."""
        reporter = ProgressReporter(quiet=False)

        reporter.type_start(1, 3, "math", 150, parallel=True)

        captured = capsys.readouterr()
        # In parallel mode, should just show type name without index
        assert "[math]" in captured.out
        assert "Starting generation" in captured.out
        assert "[1/3]" not in captured.out  # Sequential format should not appear

    def test_type_start_sequential_mode(self, capsys):
        """Test type_start output in sequential mode."""
        reporter = ProgressReporter(quiet=False)

        reporter.type_start(1, 3, "math", 150, parallel=False)

        captured = capsys.readouterr()
        # In sequential mode, should show index and type name
        assert "[1/3]" in captured.out
        assert "math" in captured.out

    def test_type_complete_parallel_mode(self, capsys):
        """Test type_complete output in parallel mode."""
        reporter = ProgressReporter(quiet=False)

        reporter.type_complete("math", True, 45.5, 148, parallel=True)

        captured = capsys.readouterr()
        assert "math" in captured.out
        assert "completed successfully" in captured.out
        # Should not include separator line in parallel mode
        assert "-" * 60 not in captured.out

    def test_type_complete_sequential_mode(self, capsys):
        """Test type_complete output in sequential mode."""
        reporter = ProgressReporter(quiet=False)

        reporter.type_complete("math", True, 45.5, 148, parallel=False)

        captured = capsys.readouterr()
        assert "math" in captured.out
        assert "completed successfully" in captured.out
        # Should include separator line in sequential mode
        assert "-" * 60 in captured.out

    def test_progress_with_type_context(self, capsys):
        """Test progress message with type context for parallel mode."""
        reporter = ProgressReporter(quiet=False)

        reporter.progress("Generated 50/150 questions", question_type="math")

        captured = capsys.readouterr()
        assert "[math]" in captured.out
        assert "Generated 50/150 questions" in captured.out

    def test_progress_without_type_context(self, capsys):
        """Test progress message without type context (sequential mode)."""
        reporter = ProgressReporter(quiet=False)

        reporter.progress("Generated 50/150 questions")

        captured = capsys.readouterr()
        assert "[PROGRESS]" in captured.out
        assert "Generated 50/150 questions" in captured.out


class TestBatchAPIFlow:
    """Tests for batch API generation flow."""

    @pytest.fixture
    def event_logger(self):
        """Create test event logger."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield EventLogger(Path(tmpdir))

    @pytest.fixture
    def logger(self):
        """Create test logger."""
        import logging

        return logging.getLogger("test_batch_api")

    @pytest.fixture
    def config(self):
        """Create test configuration with batch enabled."""
        return BootstrapConfig(
            questions_per_type=15,
            types=["math"],
            dry_run=True,
            use_async=True,
            use_batch=True,
            max_retries=2,
        )

    def test_supports_batch_api_without_pipeline(self, config, event_logger, logger):
        """Test that _supports_batch_api returns False when pipeline not initialized."""
        bootstrap = BootstrapInventory(config, event_logger, logger)

        assert bootstrap._supports_batch_api() is False

    def test_supports_batch_api_with_google_provider(
        self, config, event_logger, logger
    ):
        """Test that _supports_batch_api returns True when Google provider available."""
        bootstrap = BootstrapInventory(config, event_logger, logger)

        # Mock pipeline with Google provider
        mock_pipeline = Mock()
        mock_pipeline.generator.get_available_providers.return_value = ["google"]
        bootstrap.pipeline = mock_pipeline

        with patch("bootstrap_inventory.settings") as mock_settings:
            mock_settings.enable_batch_generation = True

            result = bootstrap._supports_batch_api()

        assert result is True

    def test_supports_batch_api_without_google_provider(
        self, config, event_logger, logger
    ):
        """Test that _supports_batch_api returns False when Google not available."""
        bootstrap = BootstrapInventory(config, event_logger, logger)

        # Mock pipeline without Google provider
        mock_pipeline = Mock()
        mock_pipeline.generator.get_available_providers.return_value = ["openai"]
        bootstrap.pipeline = mock_pipeline

        with patch("bootstrap_inventory.settings") as mock_settings:
            mock_settings.enable_batch_generation = True

            result = bootstrap._supports_batch_api()

        assert result is False

    def test_supports_batch_api_when_disabled_in_settings(
        self, config, event_logger, logger
    ):
        """Test that _supports_batch_api returns False when batch disabled."""
        bootstrap = BootstrapInventory(config, event_logger, logger)

        mock_pipeline = Mock()
        mock_pipeline.generator.get_available_providers.return_value = ["google"]
        bootstrap.pipeline = mock_pipeline

        with patch("bootstrap_inventory.settings") as mock_settings:
            mock_settings.enable_batch_generation = False

            result = bootstrap._supports_batch_api()

        assert result is False

    @pytest.mark.asyncio
    async def test_generate_type_with_batch_api_success(
        self, config, event_logger, logger
    ):
        """Test successful batch API generation."""
        from app.providers.google_provider import GoogleProvider

        bootstrap = BootstrapInventory(config, event_logger, logger)

        # Mock Google provider with spec to pass isinstance check
        mock_google_provider = Mock(spec=GoogleProvider)
        mock_batch_result = Mock()
        mock_batch_result.successful_requests = 15
        mock_batch_result.failed_requests = 0
        mock_batch_result.total_requests = 15
        mock_batch_result.responses = [
            {
                "key": f"request-{i}",
                "text": json.dumps(
                    {
                        "question_text": f"Question {i}",
                        "correct_answer": "A",
                        "answer_options": ["A", "B", "C", "D"],
                        "explanation": f"Explanation {i}",
                    }
                ),
            }
            for i in range(15)
        ]
        mock_google_provider.generate_batch_completions_async = AsyncMock(
            return_value=mock_batch_result
        )

        # Mock pipeline
        mock_pipeline = Mock()
        mock_pipeline.generator.providers = {"google": mock_google_provider}
        bootstrap.pipeline = mock_pipeline

        from app.models import QuestionType

        with patch("bootstrap_inventory.settings") as mock_settings:
            mock_settings.batch_generation_size = 100
            mock_settings.batch_generation_timeout = 300

            result = await bootstrap._generate_type_with_batch_api(
                QuestionType.MATH, 15
            )

        assert result["generated"] == 15
        assert result["target"] == 15
        assert len(result["questions"]) == 15

    @pytest.mark.asyncio
    async def test_generate_type_with_batch_api_parse_errors(
        self, config, event_logger, logger
    ):
        """Test batch API generation with some parse errors."""
        from app.providers.google_provider import GoogleProvider

        bootstrap = BootstrapInventory(config, event_logger, logger)

        # Mock Google provider with spec to pass isinstance check
        mock_google_provider = Mock(spec=GoogleProvider)
        mock_batch_result = Mock()
        mock_batch_result.successful_requests = 15
        mock_batch_result.failed_requests = 0
        mock_batch_result.total_requests = 15

        # Mix of valid and invalid responses
        responses = []
        for i in range(12):
            responses.append(
                {
                    "key": f"request-{i}",
                    "text": json.dumps(
                        {
                            "question_text": f"Question {i}",
                            "correct_answer": "A",
                            "answer_options": ["A", "B", "C", "D"],
                            "explanation": f"Explanation {i}",
                        }
                    ),
                }
            )
        # Add 3 invalid responses (will cause parse errors)
        responses.append({"key": "request-12", "text": "invalid json"})
        responses.append({"key": "request-13", "text": ""})  # Empty
        responses.append({"key": "request-14", "text": json.dumps([])})  # Not a dict

        mock_batch_result.responses = responses
        mock_google_provider.generate_batch_completions_async = AsyncMock(
            return_value=mock_batch_result
        )

        mock_pipeline = Mock()
        mock_pipeline.generator.providers = {"google": mock_google_provider}
        bootstrap.pipeline = mock_pipeline

        from app.models import QuestionType

        with patch("bootstrap_inventory.settings") as mock_settings:
            mock_settings.batch_generation_size = 100
            mock_settings.batch_generation_timeout = 300

            result = await bootstrap._generate_type_with_batch_api(
                QuestionType.MATH, 15
            )

        # Should have 12 valid questions (3 parse errors)
        assert result["generated"] == 12
        assert result["target"] == 15

    @pytest.mark.asyncio
    async def test_generate_type_with_batch_api_exceeds_parse_threshold(
        self, config, event_logger, logger
    ):
        """Test batch API fails when parse error rate exceeds threshold."""
        from app.providers.google_provider import GoogleProvider

        bootstrap = BootstrapInventory(config, event_logger, logger)

        # Mock Google provider with spec to pass isinstance check
        mock_google_provider = Mock(spec=GoogleProvider)
        mock_batch_result = Mock()
        mock_batch_result.successful_requests = 15
        mock_batch_result.failed_requests = 0
        mock_batch_result.total_requests = 15

        # Only 5 valid, 10 invalid (66% parse error rate)
        responses = []
        for i in range(5):
            responses.append(
                {
                    "key": f"request-{i}",
                    "text": json.dumps(
                        {
                            "question_text": f"Question {i}",
                            "correct_answer": "A",
                            "answer_options": ["A", "B", "C", "D"],
                            "explanation": f"Explanation {i}",
                        }
                    ),
                }
            )
        for i in range(5, 15):
            responses.append({"key": f"request-{i}", "text": "invalid"})

        mock_batch_result.responses = responses
        mock_google_provider.generate_batch_completions_async = AsyncMock(
            return_value=mock_batch_result
        )

        mock_pipeline = Mock()
        mock_pipeline.generator.providers = {"google": mock_google_provider}
        bootstrap.pipeline = mock_pipeline

        from app.models import QuestionType

        with patch("bootstrap_inventory.settings") as mock_settings:
            mock_settings.batch_generation_size = 100
            mock_settings.batch_generation_timeout = 300

            with pytest.raises(ValueError) as exc_info:
                await bootstrap._generate_type_with_batch_api(QuestionType.MATH, 15)

            assert "Parse error rate" in str(exc_info.value)
            assert "exceeds" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_type_with_batch_api_timeout(
        self, config, event_logger, logger
    ):
        """Test batch API handles timeout correctly."""
        from app.providers.google_provider import GoogleProvider

        bootstrap = BootstrapInventory(config, event_logger, logger)

        # Mock Google provider with spec to pass isinstance check
        mock_google_provider = Mock(spec=GoogleProvider)
        mock_google_provider.generate_batch_completions_async = AsyncMock(
            side_effect=TimeoutError("Batch job timed out")
        )

        mock_pipeline = Mock()
        mock_pipeline.generator.providers = {"google": mock_google_provider}
        bootstrap.pipeline = mock_pipeline

        from app.models import QuestionType

        with patch("bootstrap_inventory.settings") as mock_settings:
            mock_settings.batch_generation_size = 100
            mock_settings.batch_generation_timeout = 300

            with pytest.raises(TimeoutError):
                await bootstrap._generate_type_with_batch_api(QuestionType.MATH, 15)

    @pytest.mark.asyncio
    async def test_generate_type_with_batch_api_no_google_provider(
        self, config, event_logger, logger
    ):
        """Test batch API raises error when Google provider not available."""
        bootstrap = BootstrapInventory(config, event_logger, logger)

        # Mock pipeline without Google provider
        mock_pipeline = Mock()
        mock_pipeline.generator.providers = {"openai": Mock()}
        bootstrap.pipeline = mock_pipeline

        from app.models import QuestionType

        with pytest.raises(ValueError) as exc_info:
            await bootstrap._generate_type_with_batch_api(QuestionType.MATH, 15)

        assert "Google provider not available" in str(exc_info.value)


class TestJSONLEventFormatParity:
    """Tests to verify JSONL event format parity with bash script.

    The Python bootstrap script must emit events in the same format as
    the bash script for compatibility with monitoring tools.
    """

    @pytest.fixture
    def event_logger(self):
        """Create test event logger."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield EventLogger(Path(tmpdir))

    def test_event_contains_required_fields(self, event_logger):
        """Test that events contain timestamp, event_type, and status."""
        event_logger.log_event("test_event", "started", custom="value")

        with open(event_logger.events_file) as f:
            event = json.loads(f.readline())

        # Required fields from bash script format
        assert "timestamp" in event
        assert "event_type" in event
        assert "status" in event
        # Custom fields should also be present
        assert event["custom"] == "value"

    def test_timestamp_is_iso8601_utc(self, event_logger):
        """Test that timestamp is in ISO 8601 UTC format."""
        event_logger.log_event("test_event", "started")

        with open(event_logger.events_file) as f:
            event = json.loads(f.readline())

        timestamp = event["timestamp"]
        # Should be in format: 2026-01-25T12:00:00Z or 2026-01-25T12:00:00.123456+00:00
        from datetime import datetime

        # Try parsing - should not raise
        try:
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            pytest.fail(f"Invalid timestamp format: {timestamp}")

    def test_script_start_event_format(self, event_logger):
        """Test script_start event matches bash script format."""
        event_logger.log_event(
            "script_start",
            "started",
            total_types=6,
            target_per_type=150,
            types="math,logic,pattern,verbal,spatial,memory",
            async_mode="enabled",
            dry_run="no",
        )

        with open(event_logger.events_file) as f:
            event = json.loads(f.readline())

        # Verify fields match bash script's log_event call
        assert event["event_type"] == "script_start"
        assert event["status"] == "started"
        assert event["total_types"] == 6
        assert event["target_per_type"] == 150
        assert "types" in event
        assert event["async_mode"] == "enabled"
        assert event["dry_run"] == "no"

    def test_type_start_event_format(self, event_logger):
        """Test type_start event matches bash script format."""
        event_logger.log_event(
            "type_start",
            "started",
            type="math",
            attempt=1,
            max_retries=3,
            target_per_type=150,
        )

        with open(event_logger.events_file) as f:
            event = json.loads(f.readline())

        assert event["event_type"] == "type_start"
        assert event["status"] == "started"
        assert event["type"] == "math"
        assert event["attempt"] == 1
        assert event["max_retries"] == 3
        assert event["target_per_type"] == 150

    def test_type_end_success_event_format(self, event_logger):
        """Test type_end success event matches bash script format."""
        event_logger.log_event(
            "type_end",
            "success",
            type="math",
            attempt=1,
            duration_seconds=120.5,
            generated=150,
            target=150,
        )

        with open(event_logger.events_file) as f:
            event = json.loads(f.readline())

        assert event["event_type"] == "type_end"
        assert event["status"] == "success"
        assert event["type"] == "math"
        assert event["attempt"] == 1
        assert event["duration_seconds"] == pytest.approx(120.5)
        assert event["generated"] == 150
        assert event["target"] == 150

    def test_type_end_failed_event_format(self, event_logger):
        """Test type_end failed event matches bash script format."""
        event_logger.log_event(
            "type_end",
            "failed",
            type="math",
            attempt=3,
            duration_seconds=45.0,
            error="API timeout",
        )

        with open(event_logger.events_file) as f:
            event = json.loads(f.readline())

        assert event["event_type"] == "type_end"
        assert event["status"] == "failed"
        assert event["type"] == "math"
        assert event["attempt"] == 3
        assert "error" in event

    def test_type_end_retry_failed_event_format(self, event_logger):
        """Test type_end retry_failed event (intermediate failure)."""
        event_logger.log_event(
            "type_end",
            "retry_failed",
            type="math",
            attempt=1,
            duration_seconds=30.0,
        )

        with open(event_logger.events_file) as f:
            event = json.loads(f.readline())

        assert event["event_type"] == "type_end"
        assert event["status"] == "retry_failed"

    def test_script_end_success_event_format(self, event_logger):
        """Test script_end success event matches bash script format."""
        event_logger.log_event(
            "script_end",
            "success",
            successful_types=6,
            failed_types=0,
            total_duration_seconds=720.5,
            types_processed="math,logic,pattern,verbal,spatial,memory",
        )

        with open(event_logger.events_file) as f:
            event = json.loads(f.readline())

        assert event["event_type"] == "script_end"
        assert event["status"] == "success"
        assert event["successful_types"] == 6
        assert event["failed_types"] == 0
        assert event["total_duration_seconds"] == pytest.approx(720.5)

    def test_script_end_failed_event_format(self, event_logger):
        """Test script_end failed event matches bash script format."""
        event_logger.log_event(
            "script_end",
            "failed",
            successful_types=3,
            failed_types=3,
            total_duration_seconds=600.0,
            types_processed="math,logic,pattern,verbal,spatial,memory",
        )

        with open(event_logger.events_file) as f:
            event = json.loads(f.readline())

        assert event["event_type"] == "script_end"
        assert event["status"] == "failed"
        assert event["successful_types"] == 3
        assert event["failed_types"] == 3

    def test_multi_type_failure_event_format(self, event_logger):
        """Test multi_type_failure event matches bash script format."""
        event_logger.log_event(
            "multi_type_failure",
            "critical",
            failed_count=3,
            failed_types="math,logic,pattern",
            threshold=CRITICAL_FAILURE_THRESHOLD,
        )

        with open(event_logger.events_file) as f:
            event = json.loads(f.readline())

        assert event["event_type"] == "multi_type_failure"
        assert event["status"] == "critical"
        assert event["failed_count"] == 3
        assert event["failed_types"] == "math,logic,pattern"
        assert event["threshold"] == 3


class TestAPIFailureScenarios:
    """Mock-based tests for API failure scenarios."""

    @pytest.fixture
    def event_logger(self):
        """Create test event logger."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield EventLogger(Path(tmpdir))

    @pytest.fixture
    def logger(self):
        """Create test logger."""
        import logging

        return logging.getLogger("test_api_failures")

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return BootstrapConfig(
            questions_per_type=15,
            types=["math"],
            dry_run=True,
            use_async=True,
            max_retries=2,
            retry_base_delay=0.01,  # Fast retries for testing
        )

    @pytest.mark.asyncio
    async def test_api_rate_limit_error(self, config, event_logger, logger):
        """Test handling of API rate limit errors."""
        bootstrap = BootstrapInventory(config, event_logger, logger)

        mock_pipeline = Mock()
        mock_pipeline.generate_questions_async = AsyncMock(
            side_effect=Exception("Rate limit exceeded (429)")
        )
        bootstrap.pipeline = mock_pipeline

        result = await bootstrap._process_type_with_retries("math")

        assert result.success is False
        assert "Rate limit" in result.error_message
        assert result.attempt_count == 2  # Exhausted retries

    @pytest.mark.asyncio
    async def test_api_authentication_error(self, config, event_logger, logger):
        """Test handling of API authentication errors."""
        bootstrap = BootstrapInventory(config, event_logger, logger)

        mock_pipeline = Mock()
        mock_pipeline.generate_questions_async = AsyncMock(
            side_effect=Exception("Invalid API key (401 Unauthorized)")
        )
        bootstrap.pipeline = mock_pipeline

        result = await bootstrap._process_type_with_retries("math")

        assert result.success is False
        assert "401" in result.error_message or "API key" in result.error_message

    @pytest.mark.asyncio
    async def test_api_server_error(self, config, event_logger, logger):
        """Test handling of API server errors (5xx)."""
        bootstrap = BootstrapInventory(config, event_logger, logger)

        mock_pipeline = Mock()
        mock_pipeline.generate_questions_async = AsyncMock(
            side_effect=Exception("Internal server error (500)")
        )
        bootstrap.pipeline = mock_pipeline

        result = await bootstrap._process_type_with_retries("math")

        assert result.success is False
        assert "500" in result.error_message or "server error" in result.error_message

    @pytest.mark.asyncio
    async def test_api_timeout_error(self, config, event_logger, logger):
        """Test handling of API timeout errors."""
        bootstrap = BootstrapInventory(config, event_logger, logger)

        mock_pipeline = Mock()
        mock_pipeline.generate_questions_async = AsyncMock(
            side_effect=asyncio.TimeoutError("Request timed out")
        )
        bootstrap.pipeline = mock_pipeline

        result = await bootstrap._process_type_with_retries("math")

        assert result.success is False
        assert "timed out" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_transient_error_with_recovery(self, config, event_logger, logger):
        """Test that transient errors are retried and can recover."""
        config.max_retries = 3
        bootstrap = BootstrapInventory(config, event_logger, logger)

        mock_pipeline = Mock()
        mock_batch = Mock()
        mock_batch.questions = [Mock() for _ in range(15)]

        call_count = 0

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Transient network error")
            return mock_batch

        mock_pipeline.generate_questions_async = mock_generate
        bootstrap.pipeline = mock_pipeline

        result = await bootstrap._process_type_with_retries("math")

        assert result.success is True
        assert result.attempt_count == 3  # Failed twice, succeeded on third

    @pytest.mark.asyncio
    async def test_empty_response_handling(self, config, event_logger, logger):
        """Test handling of empty API response."""
        bootstrap = BootstrapInventory(config, event_logger, logger)

        mock_pipeline = Mock()
        mock_batch = Mock()
        mock_batch.questions = []  # Empty response
        mock_pipeline.generate_questions_async = AsyncMock(return_value=mock_batch)
        bootstrap.pipeline = mock_pipeline

        result = await bootstrap._process_type_with_retries("math")

        assert result.success is True  # Empty is not an error
        assert result.generated == 0

    @pytest.mark.asyncio
    async def test_partial_response_handling(self, config, event_logger, logger):
        """Test handling of partial API response (generation succeeds with fewer than target)."""
        bootstrap = BootstrapInventory(config, event_logger, logger)

        # Mock the _generate_type_async method directly since that's what returns the result dict
        mock_result = {
            "generated": 5,
            "target": 15,
            "questions": [Mock() for _ in range(5)],
        }

        with patch.object(
            bootstrap, "_generate_type_async", new=AsyncMock(return_value=mock_result)
        ):
            mock_pipeline = Mock()
            bootstrap.pipeline = mock_pipeline

            result = await bootstrap._process_type_with_retries("math")

        assert result.success is True
        assert result.generated == 5  # Partial is acceptable

    @pytest.mark.asyncio
    async def test_connection_error(self, config, event_logger, logger):
        """Test handling of connection errors."""
        bootstrap = BootstrapInventory(config, event_logger, logger)

        mock_pipeline = Mock()
        mock_pipeline.generate_questions_async = AsyncMock(
            side_effect=Exception("ConnectionError: Unable to reach server")
        )
        bootstrap.pipeline = mock_pipeline

        result = await bootstrap._process_type_with_retries("math")

        assert result.success is False
        assert (
            "ConnectionError" in result.error_message or "reach" in result.error_message
        )


class TestMigrationParity:
    """Tests to verify feature parity with the bash bootstrap script.

    These tests ensure the Python script behaves identically to the
    bash script for important behaviors.
    """

    def test_exit_codes_match_bash_script(self):
        """Test that exit codes match bash script definitions."""
        # Bash script exit codes (from bootstrap_inventory.sh):
        # 0 - All types completed successfully
        # 1 - Some types failed after retries
        # 2 - Configuration or setup error
        from bootstrap_inventory import (
            EXIT_SUCCESS,
            EXIT_PARTIAL_FAILURE,
            EXIT_CONFIG_ERROR,
        )

        assert EXIT_SUCCESS == 0
        assert EXIT_PARTIAL_FAILURE == 1
        assert EXIT_CONFIG_ERROR == 2

    def test_critical_failure_threshold_matches_bash_script(self):
        """Test that critical failure threshold matches bash script."""
        # Bash script: CRITICAL_FAILURE_THRESHOLD=3
        assert CRITICAL_FAILURE_THRESHOLD == 3

    def test_default_questions_per_type_matches_bash_script(self):
        """Test that default questions_per_type matches bash script."""
        # Bash script: DEFAULT_QUESTIONS_PER_TYPE=150
        config = BootstrapConfig()
        assert config.questions_per_type == 150

    def test_default_max_retries_matches_bash_script(self):
        """Test that default max_retries matches bash script."""
        # Bash script: DEFAULT_MAX_RETRIES=3
        config = BootstrapConfig()
        assert config.max_retries == 3

    def test_all_question_types_supported(self):
        """Test that all question types from bash script are supported."""
        # Bash script: ALL_TYPES="pattern logic spatial math verbal memory"
        config = BootstrapConfig()
        bash_types = {"pattern", "logic", "spatial", "math", "verbal", "memory"}

        assert set(config.types) == bash_types

    def test_max_questions_limit_matches_bash_script(self):
        """Test that max questions limit matches bash script validation."""
        # Bash script validates: --count must be between 1 and 10000
        from bootstrap_inventory import MAX_QUESTIONS_PER_TYPE

        assert MAX_QUESTIONS_PER_TYPE == 10000

    def test_validate_count_accepts_valid_range(self):
        """Test count validation accepts 1-10000."""
        # Should not raise for valid values
        validate_count(1)
        validate_count(150)
        validate_count(10000)

    def test_validate_count_rejects_zero(self):
        """Test count validation rejects 0."""
        with pytest.raises(ValueError) as exc_info:
            validate_count(0)
        assert "between 1 and 10000" in str(exc_info.value)

    def test_validate_count_rejects_over_max(self):
        """Test count validation rejects values over 10000."""
        with pytest.raises(ValueError) as exc_info:
            validate_count(10001)
        assert "between 1 and 10000" in str(exc_info.value)

    def test_validate_types_accepts_all_bash_types(self):
        """Test that all bash script types are accepted."""
        bash_types = ["pattern", "logic", "spatial", "math", "verbal", "memory"]

        for qtype in bash_types:
            result = validate_types(qtype)
            assert qtype in result

    def test_validate_types_rejects_invalid(self):
        """Test that invalid types are rejected."""
        with pytest.raises(ValueError) as exc_info:
            validate_types("invalid_type")
        assert "Invalid question type" in str(exc_info.value)

    def test_validate_types_handles_comma_separated(self):
        """Test that comma-separated types work like bash script."""
        # Bash: TYPES=$(echo "$TYPES_FILTER" | tr ',' ' ')
        result = validate_types("math,logic,pattern")
        assert result == ["math", "logic", "pattern"]

    def test_validate_types_handles_spaces(self):
        """Test that spaces around types are handled."""
        result = validate_types(" math , logic , pattern ")
        assert result == ["math", "logic", "pattern"]

    def test_questions_distributed_across_difficulties(self):
        """Test that questions are distributed across 3 difficulty levels."""
        # Bash script distributes across easy, medium, hard
        config = BootstrapConfig(questions_per_type=30)

        # 30 questions / 3 difficulties = 10 each
        expected_per_difficulty = 10

        # The distribution logic is tested indirectly through
        # TestDistributionAcrossDifficulties, but we verify the intention here
        assert config.questions_per_type % 3 == 0
        assert expected_per_difficulty == config.questions_per_type // 3

    def test_dry_run_default_matches_bash(self):
        """Test that dry_run defaults to False like bash script."""
        config = BootstrapConfig()
        assert config.dry_run is False

    def test_async_default_matches_bash(self):
        """Test that async defaults to True like bash script."""
        # Bash script: USE_ASYNC="--async --async-judge" (enabled by default)
        config = BootstrapConfig()
        assert config.use_async is True

    def test_argument_parsing_count(self):
        """Test --count argument parsing matches bash script."""
        with patch("sys.argv", ["bootstrap_inventory.py", "--count", "300"]):
            args = parse_arguments()
        assert args.count == 300

    def test_argument_parsing_types(self):
        """Test --types argument parsing matches bash script."""
        with patch("sys.argv", ["bootstrap_inventory.py", "--types", "math,logic"]):
            args = parse_arguments()
        assert args.types == "math,logic"

    def test_argument_parsing_dry_run(self):
        """Test --dry-run argument parsing matches bash script."""
        with patch("sys.argv", ["bootstrap_inventory.py", "--dry-run"]):
            args = parse_arguments()
        assert args.dry_run is True

    def test_argument_parsing_no_async(self):
        """Test --no-async argument parsing matches bash script."""
        with patch("sys.argv", ["bootstrap_inventory.py", "--no-async"]):
            args = parse_arguments()
        assert args.no_async is True

    def test_argument_parsing_max_retries(self):
        """Test --max-retries argument parsing matches bash script."""
        with patch("sys.argv", ["bootstrap_inventory.py", "--max-retries", "5"]):
            args = parse_arguments()
        assert args.max_retries == 5


class TestEventLogRotation:
    """Tests for JSONL event log file rotation."""

    def test_log_rotation_at_size_limit(self):
        """Test that log file is rotated when it exceeds size limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            logger = EventLogger(log_dir)

            # Create a large log file by writing directly
            # MAX_EVENT_FILE_SIZE_BYTES = 10MB, use smaller for test
            with patch("bootstrap_inventory.MAX_EVENT_FILE_SIZE_BYTES", 100):
                # Write enough data to trigger rotation
                with open(logger.events_file, "w") as f:
                    f.write("x" * 150)

                # This should trigger rotation
                logger.log_event("test", "started")

            # Check that rotation happened
            rotated_files = list(log_dir.glob("bootstrap_events_*.jsonl"))
            assert len(rotated_files) >= 1

    def test_log_creates_parent_directories(self):
        """Test that log directories are created if they don't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "nested" / "deep" / "logs"
            logger = EventLogger(log_dir)

            logger.log_event("test", "started")

            assert log_dir.exists()
            assert logger.events_file.exists()


class TestTruncateError:
    """Tests for error message truncation utility."""

    def test_truncate_short_error(self):
        """Test that short errors are not truncated."""
        from bootstrap_inventory import _truncate_error

        short_error = "Short error message"
        result = _truncate_error(short_error)
        assert result == short_error

    def test_truncate_long_error(self):
        """Test that long errors are truncated with ellipsis."""
        from bootstrap_inventory import _truncate_error, MAX_ERROR_MESSAGE_LENGTH

        long_error = "x" * (MAX_ERROR_MESSAGE_LENGTH + 100)
        result = _truncate_error(long_error)

        assert len(result) == MAX_ERROR_MESSAGE_LENGTH
        assert result.endswith("...")

    def test_truncate_exact_limit_error(self):
        """Test that error at exact limit is not truncated."""
        from bootstrap_inventory import _truncate_error, MAX_ERROR_MESSAGE_LENGTH

        exact_error = "x" * MAX_ERROR_MESSAGE_LENGTH
        result = _truncate_error(exact_error)
        assert result == exact_error
        assert "..." not in result

    def test_truncate_sanitizes_before_truncating(self):
        """Test that _truncate_error sanitizes sensitive data before truncating."""
        from bootstrap_inventory import _truncate_error

        # Error with API key should be sanitized
        error_with_key = "API call failed with key sk-1234567890abcdefghijklmnop"
        result = _truncate_error(error_with_key)
        assert "sk-1234567890" not in result
        assert "[REDACTED_OPENAI_KEY]" in result

    def test_truncate_sanitizes_then_truncates_long_error(self):
        """Test that long errors with sensitive data are sanitized then truncated."""
        from bootstrap_inventory import _truncate_error, MAX_ERROR_MESSAGE_LENGTH

        # Long error with API key
        long_error = f"Error: {'x' * 400} with key sk-1234567890abcdefghijklmnop"
        result = _truncate_error(long_error)

        # Should be truncated
        assert len(result) <= MAX_ERROR_MESSAGE_LENGTH
        # Should not contain the API key
        assert "sk-1234567890" not in result


class TestSanitizeError:
    """Tests for error message sanitization utility."""

    def test_sanitize_openai_api_key(self):
        """Test that OpenAI API keys are redacted."""
        error = "Authentication failed for API key sk-1234567890abcdefghijklmnopqrst"
        result = _sanitize_error(error)
        assert "sk-1234567890" not in result
        assert "[REDACTED_OPENAI_KEY]" in result

    def test_sanitize_anthropic_api_key(self):
        """Test that Anthropic API keys are redacted."""
        error = "Invalid API key: sk-ant-api03-abcdefghijklmnopqrstuvwxyz"
        result = _sanitize_error(error)
        assert "sk-ant-api03" not in result
        assert "[REDACTED_ANTHROPIC_KEY]" in result

    def test_sanitize_google_api_key(self):
        """Test that Google API keys are redacted."""
        error = "Request failed with key AIzaSyC-1234567890abcdefghijklmnopqrs"
        result = _sanitize_error(error)
        assert "AIzaSyC-1234567890" not in result
        assert "[REDACTED_GOOGLE_KEY]" in result

    def test_sanitize_xai_api_key(self):
        """Test that xAI API keys are redacted."""
        error = "Authentication error: xai-1234567890abcdefghijklmnop"
        result = _sanitize_error(error)
        assert "xai-1234567890" not in result
        assert "[REDACTED_XAI_KEY]" in result

    def test_sanitize_aws_access_key_id(self):
        """Test that AWS Access Key IDs are redacted."""
        # Standard AKIA key (pragma: allowlist secret)
        error = "AWS error with key AKIAIOSFODNN7EXAMPLE"  # pragma: allowlist secret
        result = _sanitize_error(error)
        assert "AKIAIOSFODNN7EXAMPLE" not in result  # pragma: allowlist secret
        assert "[REDACTED_AWS_KEY_ID]" in result

    def test_sanitize_aws_access_key_id_variants(self):
        """Test that AWS temporary credential key IDs (ASIA) are redacted."""
        # ASIA prefix for temp credentials (pragma: allowlist secret)
        error = "Temporary credential: ASIAJEXAMPLEKEY12345"  # pragma: allowlist secret
        result = _sanitize_error(error)
        assert "ASIAJEXAMPLEKEY12345" not in result  # pragma: allowlist secret
        assert "[REDACTED_AWS_KEY_ID]" in result

    def test_sanitize_aws_secret_access_key(self):
        """Test that AWS Secret Access Keys are redacted."""
        # 40-char base64-like secret after = sign (pragma: allowlist secret)
        secret = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"  # pragma: allowlist secret
        error = f"aws_secret_access_key={secret}"
        result = _sanitize_error(error)
        assert secret not in result
        assert "[REDACTED_AWS_SECRET]" in result

    def test_sanitize_aws_secret_access_key_after_colon(self):
        """Test that AWS Secret Access Keys after colon are redacted."""
        # pragma: allowlist secret (example AWS key from AWS docs)
        secret = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"  # pragma: allowlist secret
        error = f"secret: {secret},"
        result = _sanitize_error(error)
        assert secret not in result
        assert "[REDACTED_AWS_SECRET]" in result

    def test_sanitize_bearer_token(self):
        """Test that Bearer tokens are redacted."""
        error = "Request failed: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxx"
        result = _sanitize_error(error)
        # The JWT token should be redacted
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "[REDACTED_TOKEN]" in result

    def test_sanitize_basic_auth_in_url(self):
        """Test that basic auth credentials in URLs are redacted."""
        error = "Failed to connect to https://user:password123@api.example.com/v1"  # pragma: allowlist secret
        result = _sanitize_error(error)
        assert "user:password123" not in result
        assert "[REDACTED_CREDENTIALS]@" in result

    def test_sanitize_api_key_in_query_string(self):
        """Test that API keys in query strings are redacted."""
        error = "Request to https://api.example.com?api_key=secret123 failed"
        result = _sanitize_error(error)
        assert "secret123" not in result
        assert "[REDACTED]" in result
        # Verify the separator is preserved correctly
        assert "?api_key=[REDACTED]" in result

    def test_sanitize_api_key_in_query_string_with_ampersand(self):
        """Test that API keys with & separator are properly redacted."""
        error = "Request to https://api.example.com/endpoint?foo=bar&api_key=secret123&other=val"
        result = _sanitize_error(error)
        assert "secret123" not in result
        # Verify the & separator is preserved and URL structure is intact
        assert "&api_key=[REDACTED]" in result
        assert "?foo=bar" in result
        assert "&other=val" in result

    def test_sanitize_authorization_header(self):
        """Test that Authorization headers are redacted."""
        error = "Request headers: X-Api-Key: super_secret_key_12345"
        result = _sanitize_error(error)
        assert "super_secret_key_12345" not in result
        assert "[REDACTED]" in result

    def test_sanitize_preserves_non_sensitive_content(self):
        """Test that non-sensitive error content is preserved."""
        error = "Connection timeout after 30 seconds to api.example.com"
        result = _sanitize_error(error)
        assert result == error  # Should be unchanged

    def test_sanitize_multiple_keys_in_one_error(self):
        """Test that multiple sensitive items are all redacted."""
        error = (
            "Failed with OpenAI key sk-1234567890abcdefghijklmnop "
            "and Google key AIzaSyC-1234567890abcdefghijklmnopqrs"
        )
        result = _sanitize_error(error)
        assert "sk-1234567890" not in result
        assert "AIzaSyC-1234567890" not in result
        assert "[REDACTED_OPENAI_KEY]" in result
        assert "[REDACTED_GOOGLE_KEY]" in result

    def test_sanitize_handles_exception_object(self):
        """Test that _sanitize_error can handle Exception objects."""
        exc = Exception("API key sk-1234567890abcdefghijklmnop is invalid")
        result = _sanitize_error(exc)
        assert "sk-1234567890" not in result
        assert "[REDACTED_OPENAI_KEY]" in result

    def test_sanitize_handles_none_like_values(self):
        """Test that _sanitize_error handles edge cases gracefully."""
        assert _sanitize_error("") == ""
        assert _sanitize_error(None) == "None"

    def test_sensitive_patterns_are_defined(self):
        """Test that SENSITIVE_PATTERNS constant has expected patterns."""
        # Verify we have patterns for all major providers
        assert (
            len(SENSITIVE_PATTERNS) >= 5
        )  # At minimum: OpenAI, Anthropic, Google, xAI, Bearer
        # Verify patterns are tuples of (regex, replacement)
        for pattern, replacement in SENSITIVE_PATTERNS:
            assert hasattr(pattern, "sub")  # Is a compiled regex
            assert isinstance(replacement, str)


class TestProgressReporterSanitization:
    """Tests for ProgressReporter error sanitization."""

    def test_truncate_sanitizes_api_keys(self):
        """Test that ProgressReporter._truncate sanitizes API keys."""
        reporter = ProgressReporter(quiet=True)
        error = "Failed with key sk-1234567890abcdefghijklmnop"
        result = reporter._truncate(error)
        assert "sk-1234567890" not in result
        assert "[REDACTED_OPENAI_KEY]" in result

    def test_truncate_sanitizes_before_truncating(self):
        """Test that ProgressReporter sanitizes then truncates."""
        reporter = ProgressReporter(quiet=True)
        # Create a long error with sensitive data
        error = f"Error: {'x' * 150} with key sk-1234567890abcdefghijklmnop"
        result = reporter._truncate(error, max_length=100)
        # Should be truncated
        assert len(result) <= 103  # 100 + "..."
        # Should not contain the API key
        assert "sk-1234567890" not in result


class TestJudgeDeduplicationConfig:
    """Tests for judge and deduplication configuration options."""

    def test_config_defaults_for_judge_dedup(self):
        """Test default configuration values for judge and dedup settings."""
        config = BootstrapConfig()

        assert config.min_score is None  # Uses settings.min_judge_score
        assert config.skip_deduplication is False

    def test_config_custom_min_score(self):
        """Test configuration with custom min_score."""
        config = BootstrapConfig(min_score=0.75)

        assert config.min_score == pytest.approx(0.75)

    def test_config_skip_deduplication(self):
        """Test configuration with skip_deduplication enabled."""
        config = BootstrapConfig(skip_deduplication=True)

        assert config.skip_deduplication is True

    def test_config_combined_judge_dedup_settings(self):
        """Test configuration with both judge and dedup settings."""
        config = BootstrapConfig(
            min_score=0.8,
            skip_deduplication=True,
            dry_run=True,
        )

        assert config.min_score == pytest.approx(0.8)
        assert config.skip_deduplication is True
        assert config.dry_run is True


class TestMinScoreArgParsing:
    """Tests for --min-score argument parsing."""

    def test_min_score_argument(self):
        """Test parsing --min-score argument."""
        with patch("sys.argv", ["bootstrap_inventory.py", "--min-score", "0.75"]):
            args = parse_arguments()

        assert args.min_score == pytest.approx(0.75)

    def test_min_score_default(self):
        """Test that --min-score defaults to None."""
        with patch("sys.argv", ["bootstrap_inventory.py"]):
            args = parse_arguments()

        assert args.min_score is None

    def test_skip_deduplication_flag(self):
        """Test parsing --skip-deduplication flag."""
        with patch("sys.argv", ["bootstrap_inventory.py", "--skip-deduplication"]):
            args = parse_arguments()

        assert args.skip_deduplication is True

    def test_skip_deduplication_default(self):
        """Test that --skip-deduplication defaults to False."""
        with patch("sys.argv", ["bootstrap_inventory.py"]):
            args = parse_arguments()

        assert args.skip_deduplication is False

    def test_combined_judge_dedup_flags(self):
        """Test parsing combined judge/dedup flags."""
        with patch(
            "sys.argv",
            [
                "bootstrap_inventory.py",
                "--min-score",
                "0.85",
                "--skip-deduplication",
                "--dry-run",
            ],
        ):
            args = parse_arguments()

        assert args.min_score == pytest.approx(0.85)
        assert args.skip_deduplication is True
        assert args.dry_run is True


class TestProgressReporterNewMethods:
    """Tests for new ProgressReporter methods for evaluation/dedup/insertion."""

    def test_evaluation_start(self, capsys):
        """Test evaluation start output."""
        reporter = ProgressReporter(quiet=False)

        reporter.evaluation_start(150)

        captured = capsys.readouterr()
        assert "[EVAL]" in captured.out
        assert "150 questions" in captured.out

    def test_evaluation_complete(self, capsys):
        """Test evaluation complete output."""
        reporter = ProgressReporter(quiet=False)

        reporter.evaluation_complete(approved=120, rejected=30, rate=80.0)

        captured = capsys.readouterr()
        assert "[EVAL]" in captured.out
        assert "Approved: 120" in captured.out
        assert "Rejected: 30" in captured.out
        assert "80.0%" in captured.out

    def test_dedup_start(self, capsys):
        """Test deduplication start output."""
        reporter = ProgressReporter(quiet=False)

        reporter.dedup_start(120)

        captured = capsys.readouterr()
        assert "[DEDUP]" in captured.out
        assert "120 questions" in captured.out

    def test_dedup_complete(self, capsys):
        """Test deduplication complete output."""
        reporter = ProgressReporter(quiet=False)

        reporter.dedup_complete(unique=110, duplicates=10)

        captured = capsys.readouterr()
        assert "[DEDUP]" in captured.out
        assert "Unique: 110" in captured.out
        assert "Duplicates: 10" in captured.out

    def test_insertion_start(self, capsys):
        """Test insertion start output."""
        reporter = ProgressReporter(quiet=False)

        reporter.insertion_start(110)

        captured = capsys.readouterr()
        assert "[INSERT]" in captured.out
        assert "110 questions" in captured.out

    def test_insertion_complete_success(self, capsys):
        """Test insertion complete output with no failures."""
        reporter = ProgressReporter(quiet=False)

        reporter.insertion_complete(inserted=110, failed=0)

        captured = capsys.readouterr()
        assert "[INSERT]" in captured.out
        assert "Inserted: 110" in captured.out
        assert "Failed" not in captured.out

    def test_insertion_complete_with_failures(self, capsys):
        """Test insertion complete output with some failures."""
        reporter = ProgressReporter(quiet=False)

        reporter.insertion_complete(inserted=105, failed=5)

        captured = capsys.readouterr()
        assert "[INSERT]" in captured.out
        assert "Inserted: 105" in captured.out
        assert "Failed: 5" in captured.out

    def test_quiet_mode_suppresses_new_methods(self, capsys):
        """Test that quiet mode suppresses new evaluation/dedup/insertion output."""
        reporter = ProgressReporter(quiet=True)

        reporter.evaluation_start(150)
        reporter.evaluation_complete(120, 30, 80.0)
        reporter.dedup_start(120)
        reporter.dedup_complete(110, 10)
        reporter.insertion_start(110)
        reporter.insertion_complete(110, 0)

        captured = capsys.readouterr()
        assert captured.out == ""


class TestTypeResultWithInserted:
    """Tests for TypeResult with inserted field."""

    def test_type_result_with_inserted(self):
        """Test TypeResult with inserted count."""
        result = TypeResult(
            question_type="math",
            success=True,
            attempt_count=1,
            generated=150,
            inserted=120,
            approval_rate=80.0,
        )

        assert result.generated == 150
        assert result.inserted == 120
        assert result.approval_rate == pytest.approx(80.0)

    def test_type_result_default_inserted(self):
        """Test TypeResult defaults inserted to 0."""
        result = TypeResult(
            question_type="math",
            success=True,
            attempt_count=1,
            generated=150,
        )

        assert result.inserted == 0


class TestSummaryWithInsertedTotals:
    """Tests for summary output with inserted totals."""

    def test_summary_shows_inserted_totals(self, capsys):
        """Test that summary shows generated and inserted totals."""
        reporter = ProgressReporter(quiet=False)

        results = [
            TypeResult("math", True, 1, 150, 120, 80.0),
            TypeResult("logic", True, 1, 150, 130, 87.0),
            TypeResult("pattern", True, 1, 150, 100, 67.0),
        ]
        reporter.summary(3, 0, 3, 120.0, results)

        captured = capsys.readouterr()
        assert "Generated: 450" in captured.out
        assert "Inserted: 350" in captured.out

    def test_summary_shows_individual_type_details(self, capsys):
        """Test that summary shows per-type generated/inserted/approval."""
        reporter = ProgressReporter(quiet=False)

        results = [
            TypeResult("math", True, 1, 150, 120, 80.0),
        ]
        reporter.summary(1, 0, 1, 60.0, results)

        captured = capsys.readouterr()
        assert "generated: 150" in captured.out
        assert "inserted: 120" in captured.out
        assert "approval: 80.0%" in captured.out
