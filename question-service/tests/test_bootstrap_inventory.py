"""Tests for bootstrap inventory script."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Importing from scripts directory requires adding to path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from bootstrap_inventory import (  # noqa: E402
    BootstrapConfig,
    BootstrapInventory,
    EventLogger,
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
