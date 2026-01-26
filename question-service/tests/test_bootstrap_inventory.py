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
    TypeResult,
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
        """Test that long error messages are truncated."""
        reporter = ProgressReporter(quiet=False)

        long_error = "x" * 300
        reporter.type_error(long_error)

        captured = capsys.readouterr()
        # Should be truncated to 200 chars
        assert len(captured.out.split("Error: ")[1].strip()) == 200

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
