"""Tests for judge configuration system."""

import tempfile
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from app.judge_config import (
    JudgeConfig,
    JudgeConfigLoader,
    JudgeModel,
    EvaluationCriteria,
)


@pytest.fixture
def valid_config_dict():
    """Fixture providing a valid configuration dictionary."""
    return {
        "version": "1.0",
        "judges": {
            "math": {
                "model": "gpt-4-turbo",
                "provider": "openai",
                "rationale": "Strong math performance",
                "enabled": True,
            },
            "logic": {
                "model": "claude-3-5-sonnet-20241022",
                "provider": "anthropic",
                "rationale": "Excellent reasoning",
                "enabled": True,
            },
            "pattern": {
                "model": "gpt-4-turbo",
                "provider": "openai",
                "rationale": "Good pattern recognition",
                "enabled": True,
            },
            "spatial": {
                "model": "claude-3-5-sonnet-20241022",
                "provider": "anthropic",
                "rationale": "Spatial reasoning",
                "enabled": True,
            },
            "verbal": {
                "model": "claude-3-5-sonnet-20241022",
                "provider": "anthropic",
                "rationale": "Verbal skills",
                "enabled": True,
            },
            "memory": {
                "model": "gpt-4-turbo",
                "provider": "openai",
                "rationale": "Memory tasks",
                "enabled": True,
            },
        },
        "default_judge": {
            "model": "gpt-4-turbo",
            "provider": "openai",
            "rationale": "Default fallback",
            "enabled": True,
        },
        "evaluation_criteria": {
            "clarity": 0.25,
            "difficulty": 0.20,
            "validity": 0.30,
            "formatting": 0.15,
            "creativity": 0.10,
        },
        "min_judge_score": 0.7,
    }


@pytest.fixture
def valid_config_file(valid_config_dict):
    """Fixture providing a temporary valid configuration file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(valid_config_dict, f)
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    temp_path.unlink()


class TestJudgeModel:
    """Tests for JudgeModel validation."""

    def test_valid_judge_model(self):
        """Test creating a valid judge model."""
        model = JudgeModel(
            model="gpt-4-turbo",
            provider="openai",
            rationale="Test rationale",
            enabled=True,
        )
        assert model.model == "gpt-4-turbo"
        assert model.provider == "openai"
        assert model.rationale == "Test rationale"
        assert model.enabled is True

    def test_invalid_provider(self):
        """Test that invalid provider raises validation error."""
        with pytest.raises(ValidationError):
            JudgeModel(
                model="gpt-4-turbo",
                provider="invalid_provider",
                rationale="Test rationale",
            )

    def test_empty_model_name(self):
        """Test that empty model name raises validation error."""
        with pytest.raises(ValidationError):
            JudgeModel(
                model="",
                provider="openai",
                rationale="Test rationale",
            )

    def test_default_enabled(self):
        """Test that enabled defaults to True."""
        model = JudgeModel(
            model="gpt-4-turbo",
            provider="openai",
            rationale="Test rationale",
        )
        assert model.enabled is True


class TestEvaluationCriteria:
    """Tests for EvaluationCriteria validation."""

    def test_valid_criteria(self):
        """Test creating valid evaluation criteria."""
        criteria = EvaluationCriteria(
            clarity=0.25,
            difficulty=0.20,
            validity=0.30,
            formatting=0.15,
            creativity=0.10,
        )
        assert criteria.clarity == 0.25
        assert criteria.difficulty == 0.20
        assert criteria.validity == 0.30
        assert criteria.formatting == 0.15
        assert criteria.creativity == 0.10

    def test_criteria_sum_not_one(self):
        """Test that criteria weights must sum to 1.0."""
        with pytest.raises(ValidationError) as exc_info:
            EvaluationCriteria(
                clarity=0.25,
                difficulty=0.25,
                validity=0.25,
                formatting=0.25,
                creativity=0.25,  # Sum is 1.25, should fail
            )
        assert "must sum to 1.0" in str(exc_info.value)

    def test_negative_weight(self):
        """Test that negative weights are invalid."""
        with pytest.raises(ValidationError):
            EvaluationCriteria(
                clarity=-0.1,
                difficulty=0.30,
                validity=0.30,
                formatting=0.30,
                creativity=0.20,
            )

    def test_weight_over_one(self):
        """Test that weights over 1.0 are invalid."""
        with pytest.raises(ValidationError):
            EvaluationCriteria(
                clarity=1.5,
                difficulty=0.0,
                validity=0.0,
                formatting=0.0,
                creativity=0.0,
            )


class TestJudgeConfig:
    """Tests for JudgeConfig validation."""

    def test_valid_config(self, valid_config_dict):
        """Test creating a valid configuration."""
        config = JudgeConfig(**valid_config_dict)
        assert config.version == "1.0"
        assert len(config.judges) == 6
        assert config.min_judge_score == 0.7

    def test_missing_required_question_type(self, valid_config_dict):
        """Test that missing required question types raise error."""
        # Remove a required question type
        del valid_config_dict["judges"]["math"]

        with pytest.raises(ValidationError) as exc_info:
            JudgeConfig(**valid_config_dict)
        assert "Missing required question types" in str(exc_info.value)
        assert "math" in str(exc_info.value)

    def test_invalid_min_score(self, valid_config_dict):
        """Test that invalid min_judge_score raises error."""
        valid_config_dict["min_judge_score"] = 1.5  # Over 1.0

        with pytest.raises(ValidationError):
            JudgeConfig(**valid_config_dict)


class TestJudgeConfigLoader:
    """Tests for JudgeConfigLoader."""

    def test_load_valid_config(self, valid_config_file):
        """Test loading a valid configuration file."""
        loader = JudgeConfigLoader(valid_config_file)
        config = loader.load()

        assert isinstance(config, JudgeConfig)
        assert config.version == "1.0"
        assert len(config.judges) == 6

    def test_load_nonexistent_file(self):
        """Test that loading nonexistent file raises FileNotFoundError."""
        loader = JudgeConfigLoader("/nonexistent/path.yaml")

        with pytest.raises(FileNotFoundError):
            loader.load()

    def test_get_config_before_load(self, valid_config_file):
        """Test that accessing config before load raises RuntimeError."""
        loader = JudgeConfigLoader(valid_config_file)

        with pytest.raises(RuntimeError) as exc_info:
            _ = loader.config
        assert "not loaded" in str(exc_info.value).lower()

    def test_get_judge_for_question_type(self, valid_config_file):
        """Test getting judge for specific question type."""
        loader = JudgeConfigLoader(valid_config_file)
        loader.load()

        judge = loader.get_judge_for_question_type("math")
        assert judge.model == "gpt-4-turbo"
        assert judge.provider == "openai"

    def test_get_judge_for_unknown_type(self, valid_config_file):
        """Test that unknown question type returns default judge."""
        loader = JudgeConfigLoader(valid_config_file)
        loader.load()

        judge = loader.get_judge_for_question_type("unknown_type")
        assert judge.model == "gpt-4-turbo"  # Default
        assert judge.provider == "openai"

    def test_get_judge_for_disabled_type(self, valid_config_file):
        """Test that disabled judge falls back to default."""
        # Modify config to disable one judge
        with open(valid_config_file, "r") as f:
            config_dict = yaml.safe_load(f)

        config_dict["judges"]["math"]["enabled"] = False

        with open(valid_config_file, "w") as f:
            yaml.dump(config_dict, f)

        loader = JudgeConfigLoader(valid_config_file)
        loader.load()

        judge = loader.get_judge_for_question_type("math")
        # Should fall back to default
        assert judge == loader.config.default_judge

    def test_get_all_question_types(self, valid_config_file):
        """Test getting all configured question types."""
        loader = JudgeConfigLoader(valid_config_file)
        loader.load()

        types = loader.get_all_question_types()
        assert len(types) == 6
        assert "math" in types
        assert "logic" in types
        assert "pattern" in types
        assert "spatial" in types
        assert "verbal" in types
        assert "memory" in types

    def test_get_evaluation_criteria(self, valid_config_file):
        """Test getting evaluation criteria."""
        loader = JudgeConfigLoader(valid_config_file)
        loader.load()

        criteria = loader.get_evaluation_criteria()
        assert criteria.clarity == 0.25
        assert criteria.difficulty == 0.20
        assert criteria.validity == 0.30
        assert criteria.formatting == 0.15
        assert criteria.creativity == 0.10

    def test_get_min_judge_score(self, valid_config_file):
        """Test getting minimum judge score."""
        loader = JudgeConfigLoader(valid_config_file)
        loader.load()

        min_score = loader.get_min_judge_score()
        assert min_score == 0.7

    def test_invalid_yaml(self):
        """Test that invalid YAML raises error."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [")
            temp_path = Path(f.name)

        try:
            loader = JudgeConfigLoader(temp_path)
            with pytest.raises(yaml.YAMLError):
                loader.load()
        finally:
            temp_path.unlink()


class TestGlobalConfiguration:
    """Tests for global configuration functions."""

    def test_initialize_and_get(self, valid_config_file):
        """Test initializing and getting global configuration."""
        from app.judge_config import (
            get_judge_config,
            initialize_judge_config,
        )

        # Initialize
        initialize_judge_config(valid_config_file)

        # Get and verify
        loader = get_judge_config()
        assert isinstance(loader, JudgeConfigLoader)

        config = loader.config
        assert config.version == "1.0"

    def test_get_before_initialize(self):
        """Test that getting config before initialize raises error."""
        from app.judge_config import get_judge_config

        # Ensure loader is None
        import app.judge_config as config_module

        config_module._loader = None

        with pytest.raises(RuntimeError) as exc_info:
            get_judge_config()
        assert "not initialized" in str(exc_info.value).lower()
