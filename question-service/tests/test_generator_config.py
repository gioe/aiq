"""Tests for generator configuration loading.

Tests both the Pydantic models and the actual generators.yaml configuration file.
"""

import tempfile
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from app.generator_config import (
    GeneratorAssignment,
    GeneratorConfig,
    GeneratorConfigLoader,
    get_generator_config,
    initialize_generator_config,
    is_generator_config_initialized,
)


@pytest.fixture
def valid_config_dict():
    """Fixture providing a valid configuration dictionary."""
    return {
        "version": "1.0",
        "generators": {
            "math": {
                "provider": "openai",
                "model": "gpt-4-turbo",
                "rationale": "Strong math performance",
                "fallback": "anthropic",
            },
            "logic": {
                "provider": "anthropic",
                "model": "claude-sonnet-4-5-20250929",
                "rationale": "Excellent reasoning",
                "fallback": "openai",
            },
            "pattern": {
                "provider": "google",
                "model": "gemini-3-pro-preview",
                "rationale": "Good pattern recognition",
                "fallback": "anthropic",
            },
            "spatial": {
                "provider": "google",
                "model": "gemini-3-pro-preview",
                "rationale": "Spatial reasoning",
                "fallback": "anthropic",
            },
            "verbal": {
                "provider": "anthropic",
                "model": "claude-sonnet-4-5-20250929",
                "rationale": "Verbal skills",
                "fallback": "openai",
            },
            "memory": {
                "provider": "anthropic",
                "model": "claude-sonnet-4-5-20250929",
                "rationale": "Memory tasks",
                "fallback": "openai",
            },
        },
        "default_generator": {
            "provider": "openai",
            "model": "gpt-4-turbo",
            "rationale": "Default fallback generator",
        },
        "use_specialist_routing": True,
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


class TestGeneratorAssignment:
    """Tests for GeneratorAssignment validation."""

    def test_valid_assignment(self):
        """Test creating a valid generator assignment."""
        assignment = GeneratorAssignment(
            provider="openai",
            model="gpt-4-turbo",
            rationale="Test rationale",
            fallback="anthropic",
        )
        assert assignment.provider == "openai"
        assert assignment.model == "gpt-4-turbo"
        assert assignment.rationale == "Test rationale"
        assert assignment.fallback == "anthropic"

    def test_invalid_provider(self):
        """Test that invalid provider raises validation error."""
        with pytest.raises(ValidationError):
            GeneratorAssignment(
                provider="invalid_provider",
                rationale="Test rationale",
            )

    def test_invalid_fallback(self):
        """Test that invalid fallback raises validation error."""
        with pytest.raises(ValidationError):
            GeneratorAssignment(
                provider="openai",
                rationale="Test rationale",
                fallback="invalid_fallback",
            )

    def test_optional_model(self):
        """Test that model is optional."""
        assignment = GeneratorAssignment(
            provider="openai",
            rationale="Test rationale",
        )
        assert assignment.model is None

    def test_optional_fallback(self):
        """Test that fallback is optional."""
        assignment = GeneratorAssignment(
            provider="openai",
            rationale="Test rationale",
        )
        assert assignment.fallback is None

    def test_empty_rationale_fails(self):
        """Test that empty rationale raises validation error."""
        with pytest.raises(ValidationError):
            GeneratorAssignment(
                provider="openai",
                rationale="",
            )

    def test_all_valid_providers(self):
        """Test that all valid providers are accepted."""
        for provider in ["openai", "anthropic", "google", "xai"]:
            assignment = GeneratorAssignment(
                provider=provider,
                rationale="Test rationale",
            )
            assert assignment.provider == provider

    def test_optional_fallback_model(self):
        """Test that fallback_model is optional and defaults to None."""
        assignment = GeneratorAssignment(
            provider="openai",
            rationale="Test rationale",
        )
        assert assignment.fallback_model is None

    def test_fallback_model_accepts_string(self):
        """Test that fallback_model accepts a valid model string."""
        assignment = GeneratorAssignment(
            provider="openai",
            rationale="Test rationale",
            fallback="anthropic",
            fallback_model="claude-sonnet-4-5-20250929",
        )
        assert assignment.fallback_model == "claude-sonnet-4-5-20250929"

    def test_fallback_model_with_fallback_provider(self):
        """Test that both fallback and fallback_model can be set together."""
        assignment = GeneratorAssignment(
            provider="openai",
            model="gpt-4-turbo",
            rationale="Test rationale",
            fallback="anthropic",
            fallback_model="claude-opus-4-5-20251101",
        )
        assert assignment.fallback == "anthropic"
        assert assignment.fallback_model == "claude-opus-4-5-20251101"

    def test_fallback_model_without_fallback_fails(self):
        """Test that fallback_model without fallback provider raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            GeneratorAssignment(
                provider="openai",
                rationale="Test rationale",
                fallback_model="claude-opus-4-5-20251101",
            )
        assert "fallback_model cannot be set without a fallback provider" in str(
            exc_info.value
        )


class TestMaxBatchSizeConfig:
    """Tests for max_batch_size field on GeneratorAssignment."""

    def test_max_batch_size_defaults_to_none(self):
        """Test that max_batch_size defaults to None when omitted."""
        assignment = GeneratorAssignment(
            provider="openai",
            rationale="Test rationale",
        )
        assert assignment.max_batch_size is None

    def test_max_batch_size_accepts_positive_int(self):
        """Test that max_batch_size accepts a positive integer."""
        assignment = GeneratorAssignment(
            provider="openai",
            rationale="Test rationale",
            max_batch_size=10,
        )
        assert assignment.max_batch_size == 10

    def test_max_batch_size_rejects_zero(self):
        """Test that max_batch_size=0 raises validation error."""
        with pytest.raises(ValidationError, match="max_batch_size must be positive"):
            GeneratorAssignment(
                provider="openai",
                rationale="Test rationale",
                max_batch_size=0,
            )

    def test_max_batch_size_rejects_negative(self):
        """Test that negative max_batch_size raises validation error."""
        with pytest.raises(ValidationError, match="max_batch_size must be positive"):
            GeneratorAssignment(
                provider="openai",
                rationale="Test rationale",
                max_batch_size=-5,
            )

    def test_max_batch_size_parsed_from_yaml(self):
        """Test that max_batch_size is correctly parsed from a YAML config file."""
        config_dict = {
            "version": "1.0",
            "generators": {
                "math": {"provider": "openai", "rationale": "r"},
                "logic": {"provider": "openai", "rationale": "r"},
                "pattern": {
                    "provider": "openai",
                    "rationale": "Patterns",
                    "max_batch_size": 10,
                },
                "spatial": {
                    "provider": "openai",
                    "rationale": "Spatial",
                    "max_batch_size": 15,
                },
                "verbal": {"provider": "openai", "rationale": "r"},
                "memory": {"provider": "openai", "rationale": "r"},
            },
            "default_generator": {"provider": "openai", "rationale": "Default"},
            "use_specialist_routing": True,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_dict, f)
            temp_path = Path(f.name)

        try:
            loader = GeneratorConfigLoader(temp_path)
            config = loader.load()

            assert config.generators["pattern"].max_batch_size == 10
            assert config.generators["spatial"].max_batch_size == 15
            assert config.generators["math"].max_batch_size is None
            assert config.generators["verbal"].max_batch_size is None
        finally:
            temp_path.unlink()

    def test_get_max_batch_size_returns_configured_value(self):
        """Test that get_max_batch_size returns the configured value for a type."""
        config_dict = {
            "version": "1.0",
            "generators": {
                "math": {"provider": "openai", "rationale": "r"},
                "logic": {"provider": "openai", "rationale": "r"},
                "pattern": {
                    "provider": "openai",
                    "rationale": "Patterns",
                    "max_batch_size": 10,
                },
                "spatial": {"provider": "openai", "rationale": "r"},
                "verbal": {"provider": "openai", "rationale": "r"},
                "memory": {"provider": "openai", "rationale": "r"},
            },
            "default_generator": {"provider": "openai", "rationale": "Default"},
            "use_specialist_routing": True,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_dict, f)
            temp_path = Path(f.name)

        try:
            loader = GeneratorConfigLoader(temp_path)
            loader.load()

            assert loader.get_max_batch_size("pattern") == 10
            assert loader.get_max_batch_size("math") is None
            assert loader.get_max_batch_size("unknown_type") is None
        finally:
            temp_path.unlink()


class TestGeneratorConfig:
    """Tests for GeneratorConfig validation."""

    def test_valid_config(self, valid_config_dict):
        """Test creating a valid configuration."""
        config = GeneratorConfig(**valid_config_dict)
        assert config.version == "1.0"
        assert len(config.generators) == 6
        assert config.use_specialist_routing is True

    def test_missing_required_question_type(self, valid_config_dict):
        """Test that missing required question types raise error."""
        del valid_config_dict["generators"]["math"]

        with pytest.raises(ValidationError) as exc_info:
            GeneratorConfig(**valid_config_dict)
        assert "Missing required question types" in str(exc_info.value)
        assert "math" in str(exc_info.value)

    def test_all_required_types_present(self, valid_config_dict):
        """Test that all required question types are present."""
        config = GeneratorConfig(**valid_config_dict)
        required_types = {"math", "logic", "pattern", "spatial", "verbal", "memory"}
        assert set(config.generators.keys()) == required_types

    def test_specialist_routing_default(self):
        """Test that use_specialist_routing defaults to True."""
        config_dict = {
            "version": "1.0",
            "generators": {
                "math": {"provider": "openai", "rationale": "r"},
                "logic": {"provider": "openai", "rationale": "r"},
                "pattern": {"provider": "openai", "rationale": "r"},
                "spatial": {"provider": "openai", "rationale": "r"},
                "verbal": {"provider": "openai", "rationale": "r"},
                "memory": {"provider": "openai", "rationale": "r"},
            },
            "default_generator": {"provider": "openai", "rationale": "r"},
        }
        config = GeneratorConfig(**config_dict)
        assert config.use_specialist_routing is True


class TestGeneratorConfigLoader:
    """Tests for GeneratorConfigLoader."""

    def test_load_valid_config(self, valid_config_file):
        """Test loading a valid configuration file."""
        loader = GeneratorConfigLoader(valid_config_file)
        config = loader.load()

        assert isinstance(config, GeneratorConfig)
        assert config.version == "1.0"
        assert len(config.generators) == 6

    def test_load_nonexistent_file(self):
        """Test that loading nonexistent file raises FileNotFoundError."""
        loader = GeneratorConfigLoader("/nonexistent/path.yaml")

        with pytest.raises(FileNotFoundError):
            loader.load()

    def test_get_config_before_load(self, valid_config_file):
        """Test that accessing config before load raises RuntimeError."""
        loader = GeneratorConfigLoader(valid_config_file)

        with pytest.raises(RuntimeError) as exc_info:
            _ = loader.config
        assert "not loaded" in str(exc_info.value).lower()

    def test_get_provider_for_question_type(self, valid_config_file):
        """Test getting provider for specific question type."""
        loader = GeneratorConfigLoader(valid_config_file)
        loader.load()

        provider = loader.get_provider_for_question_type(
            "math", ["openai", "anthropic"]
        )
        assert provider == "openai"

    def test_get_provider_for_unknown_type(self, valid_config_file):
        """Test that unknown question type returns default provider."""
        loader = GeneratorConfigLoader(valid_config_file)
        loader.load()

        provider = loader.get_provider_for_question_type(
            "unknown_type", ["openai", "anthropic"]
        )
        assert provider == "openai"  # Default

    def test_get_provider_uses_fallback(self, valid_config_file):
        """Test that fallback provider is used when primary unavailable."""
        loader = GeneratorConfigLoader(valid_config_file)
        loader.load()

        # math is configured with openai primary, anthropic fallback
        # Only anthropic is available
        provider = loader.get_provider_for_question_type("math", ["anthropic"])
        assert provider == "anthropic"

    def test_get_provider_and_model(self, valid_config_file):
        """Test getting provider and model for question type."""
        loader = GeneratorConfigLoader(valid_config_file)
        loader.load()

        provider, model = loader.get_provider_and_model_for_question_type(
            "math", ["openai", "anthropic"]
        )
        assert provider == "openai"
        assert model == "gpt-4-turbo"

    def test_get_all_question_types(self, valid_config_file):
        """Test getting all configured question types."""
        loader = GeneratorConfigLoader(valid_config_file)
        loader.load()

        types = loader.get_all_question_types()
        assert len(types) == 6
        assert "math" in types
        assert "logic" in types
        assert "pattern" in types
        assert "spatial" in types
        assert "verbal" in types
        assert "memory" in types

    def test_get_provider_summary(self, valid_config_file):
        """Test getting provider summary."""
        loader = GeneratorConfigLoader(valid_config_file)
        loader.load()

        summary = loader.get_provider_summary()
        assert isinstance(summary, dict)
        # Check that all providers that have question types are in summary
        assert "openai" in summary or "anthropic" in summary or "google" in summary

    def test_is_specialist_routing_enabled(self, valid_config_file):
        """Test checking if specialist routing is enabled."""
        loader = GeneratorConfigLoader(valid_config_file)
        loader.load()

        assert loader.is_specialist_routing_enabled() is True

    def test_invalid_yaml(self):
        """Test that invalid YAML raises error."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [")
            temp_path = Path(f.name)

        try:
            loader = GeneratorConfigLoader(temp_path)
            with pytest.raises(yaml.YAMLError):
                loader.load()
        finally:
            temp_path.unlink()

    def test_specialist_routing_disabled(self, valid_config_dict):
        """Test behavior when specialist routing is disabled."""
        valid_config_dict["use_specialist_routing"] = False

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(valid_config_dict, f)
            temp_path = Path(f.name)

        try:
            loader = GeneratorConfigLoader(temp_path)
            loader.load()

            # When disabled, should return first available provider
            provider = loader.get_provider_for_question_type(
                "math", ["anthropic", "openai"]
            )
            assert provider == "anthropic"  # First in list

            assert loader.is_specialist_routing_enabled() is False
        finally:
            temp_path.unlink()

    def test_get_provider_and_model_uses_fallback_model(self):
        """Test that fallback_model is returned when primary provider is unavailable."""
        config_dict = {
            "version": "1.0",
            "generators": {
                "math": {
                    "provider": "openai",
                    "model": "gpt-4-turbo",
                    "rationale": "Strong math performance",
                    "fallback": "anthropic",
                    "fallback_model": "claude-opus-4-5-20251101",
                },
                "logic": {"provider": "openai", "rationale": "r"},
                "pattern": {"provider": "openai", "rationale": "r"},
                "spatial": {"provider": "openai", "rationale": "r"},
                "verbal": {"provider": "openai", "rationale": "r"},
                "memory": {"provider": "openai", "rationale": "r"},
            },
            "default_generator": {"provider": "openai", "rationale": "r"},
            "use_specialist_routing": True,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_dict, f)
            temp_path = Path(f.name)

        try:
            loader = GeneratorConfigLoader(temp_path)
            loader.load()

            # Primary provider (openai) is not available, only fallback (anthropic)
            provider, model = loader.get_provider_and_model_for_question_type(
                "math", ["anthropic"]
            )
            assert provider == "anthropic"
            assert model == "claude-opus-4-5-20251101"
        finally:
            temp_path.unlink()

    def test_fallback_model_parsed_from_yaml(self):
        """Test that fallback_model is correctly parsed from a YAML config file."""
        config_dict = {
            "version": "1.0",
            "generators": {
                "math": {
                    "provider": "xai",
                    "model": "grok-4",
                    "rationale": "Math performance",
                    "fallback": "anthropic",
                    "fallback_model": "claude-sonnet-4-5-20250929",
                },
                "logic": {
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-5-20250929",
                    "rationale": "Reasoning",
                    "fallback": "openai",
                    "fallback_model": "gpt-5.2",
                },
                "pattern": {
                    "provider": "google",
                    "rationale": "Patterns",
                    "fallback": "anthropic",
                },
                "spatial": {"provider": "google", "rationale": "Spatial"},
                "verbal": {"provider": "anthropic", "rationale": "Verbal"},
                "memory": {"provider": "anthropic", "rationale": "Memory"},
            },
            "default_generator": {"provider": "openai", "rationale": "Default"},
            "use_specialist_routing": True,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_dict, f)
            temp_path = Path(f.name)

        try:
            loader = GeneratorConfigLoader(temp_path)
            config = loader.load()

            # Generators with fallback_model should have it parsed
            assert (
                config.generators["math"].fallback_model == "claude-sonnet-4-5-20250929"
            )
            assert config.generators["logic"].fallback_model == "gpt-5.2"
            # Generators without fallback_model should default to None
            assert config.generators["pattern"].fallback_model is None
            assert config.generators["spatial"].fallback_model is None
        finally:
            temp_path.unlink()

    def test_fallback_returns_none_model_when_no_fallback_model(
        self, valid_config_file
    ):
        """Test that fallback routing returns None model when fallback_model is not configured."""
        loader = GeneratorConfigLoader(valid_config_file)
        loader.load()

        # valid_config_dict has math: openai primary, anthropic fallback, NO fallback_model
        # Only anthropic available -> should use fallback with model=None
        provider, model = loader.get_provider_and_model_for_question_type(
            "math", ["anthropic"]
        )
        assert provider == "anthropic"
        assert model is None

    def test_primary_provider_returns_primary_model_not_fallback_model(self):
        """Test that primary provider returns primary model, not fallback_model."""
        config_dict = {
            "version": "1.0",
            "generators": {
                "math": {
                    "provider": "openai",
                    "model": "gpt-4-turbo",
                    "rationale": "Math",
                    "fallback": "anthropic",
                    "fallback_model": "claude-opus-4-5-20251101",
                },
                "logic": {"provider": "openai", "rationale": "r"},
                "pattern": {"provider": "openai", "rationale": "r"},
                "spatial": {"provider": "openai", "rationale": "r"},
                "verbal": {"provider": "openai", "rationale": "r"},
                "memory": {"provider": "openai", "rationale": "r"},
            },
            "default_generator": {"provider": "openai", "rationale": "r"},
            "use_specialist_routing": True,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_dict, f)
            temp_path = Path(f.name)

        try:
            loader = GeneratorConfigLoader(temp_path)
            loader.load()

            # Primary provider (openai) IS available -> should return primary model
            provider, model = loader.get_provider_and_model_for_question_type(
                "math", ["openai", "anthropic"]
            )
            assert provider == "openai"
            assert model == "gpt-4-turbo"  # Primary model, NOT fallback_model
        finally:
            temp_path.unlink()

    def test_neither_primary_nor_fallback_returns_no_model_override(self):
        """Test that when neither primary nor fallback is available, no model override is used."""
        config_dict = {
            "version": "1.0",
            "generators": {
                "math": {
                    "provider": "openai",
                    "model": "gpt-4-turbo",
                    "rationale": "Math",
                    "fallback": "anthropic",
                    "fallback_model": "claude-opus-4-5-20251101",
                },
                "logic": {"provider": "openai", "rationale": "r"},
                "pattern": {"provider": "openai", "rationale": "r"},
                "spatial": {"provider": "openai", "rationale": "r"},
                "verbal": {"provider": "openai", "rationale": "r"},
                "memory": {"provider": "openai", "rationale": "r"},
            },
            "default_generator": {"provider": "openai", "rationale": "r"},
            "use_specialist_routing": True,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_dict, f)
            temp_path = Path(f.name)

        try:
            loader = GeneratorConfigLoader(temp_path)
            loader.load()

            # Neither openai nor anthropic available, only google
            provider, model = loader.get_provider_and_model_for_question_type(
                "math", ["google"]
            )
            assert provider == "google"
            assert model is None  # No model override for last-resort fallback
        finally:
            temp_path.unlink()

    def test_backward_compat_config_without_fallback_model(self):
        """Test that configs without fallback_model field work correctly (backward compatibility)."""
        # This simulates an older config that doesn't have fallback_model at all
        config_dict = {
            "version": "1.0",
            "generators": {
                "math": {
                    "provider": "openai",
                    "model": "gpt-4-turbo",
                    "rationale": "Math",
                    "fallback": "anthropic",
                },
                "logic": {
                    "provider": "anthropic",
                    "rationale": "Logic",
                    "fallback": "openai",
                },
                "pattern": {"provider": "google", "rationale": "Patterns"},
                "spatial": {"provider": "google", "rationale": "Spatial"},
                "verbal": {"provider": "anthropic", "rationale": "Verbal"},
                "memory": {"provider": "anthropic", "rationale": "Memory"},
            },
            "default_generator": {"provider": "openai", "rationale": "Default"},
            "use_specialist_routing": True,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_dict, f)
            temp_path = Path(f.name)

        try:
            loader = GeneratorConfigLoader(temp_path)
            config = loader.load()

            # Config should load successfully
            assert config is not None
            assert len(config.generators) == 6

            # All fallback_model fields should be None
            for qtype, assignment in config.generators.items():
                assert (
                    assignment.fallback_model is None
                ), f"{qtype} should have fallback_model=None"

            # Routing should still work: fallback returns None model
            provider, model = loader.get_provider_and_model_for_question_type(
                "math", ["anthropic"]
            )
            assert provider == "anthropic"
            assert model is None
        finally:
            temp_path.unlink()

    def test_fallback_model_ignored_when_specialist_routing_disabled(self):
        """Test that fallback_model is not used when specialist routing is disabled."""
        config_dict = {
            "version": "1.0",
            "generators": {
                "math": {
                    "provider": "openai",
                    "model": "gpt-4-turbo",
                    "rationale": "Math",
                    "fallback": "anthropic",
                    "fallback_model": "claude-opus-4-5-20251101",
                },
                "logic": {"provider": "openai", "rationale": "r"},
                "pattern": {"provider": "openai", "rationale": "r"},
                "spatial": {"provider": "openai", "rationale": "r"},
                "verbal": {"provider": "openai", "rationale": "r"},
                "memory": {"provider": "openai", "rationale": "r"},
            },
            "default_generator": {"provider": "openai", "rationale": "r"},
            "use_specialist_routing": False,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_dict, f)
            temp_path = Path(f.name)

        try:
            loader = GeneratorConfigLoader(temp_path)
            loader.load()

            # Even though anthropic is the fallback with a fallback_model,
            # disabled routing should return first available with no model
            provider, model = loader.get_provider_and_model_for_question_type(
                "math", ["anthropic"]
            )
            assert provider == "anthropic"
            assert model is None  # No model override when routing is disabled
        finally:
            temp_path.unlink()

    def test_unknown_type_returns_default_model_not_fallback(self, valid_config_file):
        """Test that unknown question type returns default generator's model."""
        loader = GeneratorConfigLoader(valid_config_file)
        loader.load()

        provider, model = loader.get_provider_and_model_for_question_type(
            "unknown_type", ["openai", "anthropic"]
        )
        assert provider == "openai"
        assert model == "gpt-4-turbo"  # Default generator's model

    def test_fallback_model_across_all_question_types(self):
        """Test that fallback_model routing works for every question type."""
        config_dict = {
            "version": "1.0",
            "generators": {
                "math": {
                    "provider": "openai",
                    "rationale": "r",
                    "fallback": "anthropic",
                    "fallback_model": "claude-math-model",
                },
                "logic": {
                    "provider": "openai",
                    "rationale": "r",
                    "fallback": "google",
                    "fallback_model": "gemini-logic-model",
                },
                "pattern": {
                    "provider": "openai",
                    "rationale": "r",
                    "fallback": "xai",
                    "fallback_model": "grok-pattern-model",
                },
                "spatial": {
                    "provider": "openai",
                    "rationale": "r",
                    "fallback": "anthropic",
                    "fallback_model": "claude-spatial-model",
                },
                "verbal": {
                    "provider": "openai",
                    "rationale": "r",
                    "fallback": "google",
                    "fallback_model": "gemini-verbal-model",
                },
                "memory": {
                    "provider": "openai",
                    "rationale": "r",
                    "fallback": "xai",
                    "fallback_model": "grok-memory-model",
                },
            },
            "default_generator": {"provider": "openai", "rationale": "r"},
            "use_specialist_routing": True,
        }

        expected_fallbacks = {
            "math": ("anthropic", "claude-math-model"),
            "logic": ("google", "gemini-logic-model"),
            "pattern": ("xai", "grok-pattern-model"),
            "spatial": ("anthropic", "claude-spatial-model"),
            "verbal": ("google", "gemini-verbal-model"),
            "memory": ("xai", "grok-memory-model"),
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_dict, f)
            temp_path = Path(f.name)

        try:
            loader = GeneratorConfigLoader(temp_path)
            loader.load()

            for qtype, (exp_provider, exp_model) in expected_fallbacks.items():
                # Only fallback provider is available (not openai)
                provider, model = loader.get_provider_and_model_for_question_type(
                    qtype, [exp_provider]
                )
                assert (
                    provider == exp_provider
                ), f"{qtype}: expected provider {exp_provider}"
                assert model == exp_model, f"{qtype}: expected model {exp_model}"
        finally:
            temp_path.unlink()


class TestGlobalConfiguration:
    """Tests for global configuration functions."""

    @pytest.fixture(autouse=True)
    def reset_global_config(self):
        """Reset global config state before and after each test.

        This prevents test pollution from global state changes.
        """
        import app.generator_config as config_module

        original = config_module._loader
        config_module._loader = None
        yield
        config_module._loader = original

    def test_initialize_and_get(self, valid_config_file):
        """Test initializing and getting global configuration."""
        # Initialize
        initialize_generator_config(valid_config_file)

        # Get and verify
        loader = get_generator_config()
        assert isinstance(loader, GeneratorConfigLoader)

        config = loader.config
        assert config.version == "1.0"

    def test_get_before_initialize(self):
        """Test that getting config before initialize raises error."""
        with pytest.raises(RuntimeError) as exc_info:
            get_generator_config()
        assert "not initialized" in str(exc_info.value).lower()

    def test_is_generator_config_initialized(self, valid_config_file):
        """Test checking if generator config is initialized."""
        # Check not initialized (fixture reset it)
        assert is_generator_config_initialized() is False

        # Initialize and check
        initialize_generator_config(valid_config_file)
        assert is_generator_config_initialized() is True


class TestProductionGeneratorsYaml:
    """Integration tests for the production generators.yaml configuration.

    These tests validate that the actual generators.yaml file in config/
    loads successfully and contains expected values.

    NOTE: Tests that assert specific provider/model assignments (e.g.,
    test_generators_yaml_pattern_uses_google) are intentionally strict.
    These tests SHOULD fail when the production config is updated - this
    ensures config changes are intentional and reviewed. When updating
    generators.yaml, update these tests to match the new expected values.
    """

    @pytest.fixture
    def production_config_path(self):
        """Get the path to the production generators.yaml."""
        return Path(__file__).parent.parent / "config" / "generators.yaml"

    def test_generators_yaml_loads_successfully(self, production_config_path):
        """Test that the production generators.yaml loads without errors."""
        loader = GeneratorConfigLoader(production_config_path)
        config = loader.load()

        assert config is not None
        assert isinstance(config, GeneratorConfig)

    def test_generators_yaml_has_all_required_types(self, production_config_path):
        """Test that all required question types are configured."""
        loader = GeneratorConfigLoader(production_config_path)
        config = loader.load()

        required_types = {"math", "logic", "pattern", "spatial", "verbal", "memory"}
        configured_types = set(config.generators.keys())
        assert required_types == configured_types

    def test_generators_yaml_pattern_uses_openai(self, production_config_path):
        """Test that pattern questions use OpenAI provider."""
        loader = GeneratorConfigLoader(production_config_path)
        config = loader.load()

        assert config.generators["pattern"].provider == "openai"
        assert config.generators["pattern"].model == "gpt-5.2"

    def test_generators_yaml_spatial_uses_openai(self, production_config_path):
        """Test that spatial questions use OpenAI provider."""
        loader = GeneratorConfigLoader(production_config_path)
        config = loader.load()

        assert config.generators["spatial"].provider == "openai"
        assert config.generators["spatial"].model == "gpt-5.2"

    def test_generators_yaml_math_uses_xai(self, production_config_path):
        """Test that math questions use xAI provider."""
        loader = GeneratorConfigLoader(production_config_path)
        config = loader.load()

        assert config.generators["math"].provider == "xai"
        assert config.generators["math"].model == "grok-4"

    def test_generators_yaml_logic_uses_anthropic(self, production_config_path):
        """Test that logic questions use Anthropic provider."""
        loader = GeneratorConfigLoader(production_config_path)
        config = loader.load()

        assert config.generators["logic"].provider == "anthropic"
        assert config.generators["logic"].model == "claude-sonnet-4-5-20250929"

    def test_generators_yaml_verbal_uses_anthropic(self, production_config_path):
        """Test that verbal questions use Anthropic provider."""
        loader = GeneratorConfigLoader(production_config_path)
        config = loader.load()

        assert config.generators["verbal"].provider == "anthropic"
        assert config.generators["verbal"].model == "claude-sonnet-4-5-20250929"

    def test_generators_yaml_memory_uses_google(self, production_config_path):
        """Test that memory questions use Google provider."""
        loader = GeneratorConfigLoader(production_config_path)
        config = loader.load()

        assert config.generators["memory"].provider == "google"
        assert config.generators["memory"].model == "gemini-3-pro-preview"

    def test_generators_yaml_has_default_generator(self, production_config_path):
        """Test that default generator is configured."""
        loader = GeneratorConfigLoader(production_config_path)
        config = loader.load()

        assert config.default_generator is not None
        assert config.default_generator.provider == "openai"
        assert config.default_generator.model == "gpt-4-turbo"

    def test_generators_yaml_specialist_routing_enabled(self, production_config_path):
        """Test that specialist routing is enabled in production config."""
        loader = GeneratorConfigLoader(production_config_path)
        config = loader.load()

        assert config.use_specialist_routing is True

    def test_generators_yaml_all_have_fallbacks(self, production_config_path):
        """Test that all generators have fallback providers configured."""
        loader = GeneratorConfigLoader(production_config_path)
        config = loader.load()

        for qtype, assignment in config.generators.items():
            assert assignment.fallback is not None, f"{qtype} missing fallback"
            assert assignment.fallback in {
                "openai",
                "anthropic",
                "google",
                "xai",
            }, f"{qtype} has invalid fallback: {assignment.fallback}"

    def test_generators_yaml_all_have_fallback_models(self, production_config_path):
        """Test that all generators have fallback_model configured."""
        loader = GeneratorConfigLoader(production_config_path)
        config = loader.load()

        for qtype, assignment in config.generators.items():
            assert (
                assignment.fallback_model is not None
            ), f"{qtype} missing fallback_model"
            assert (
                len(assignment.fallback_model) > 0
            ), f"{qtype} has empty fallback_model"

    def test_generators_yaml_fallback_model_routing(self, production_config_path):
        """Test that production config fallback routing returns correct fallback_model values."""
        loader = GeneratorConfigLoader(production_config_path)
        config = loader.load()

        for qtype, assignment in config.generators.items():
            # Make only the fallback provider available (not the primary)
            provider, model = loader.get_provider_and_model_for_question_type(
                qtype, [assignment.fallback]
            )
            assert (
                provider == assignment.fallback
            ), f"{qtype}: expected fallback provider {assignment.fallback}, got {provider}"
            assert (
                model == assignment.fallback_model
            ), f"{qtype}: expected fallback_model {assignment.fallback_model}, got {model}"

    def test_generators_yaml_all_have_rationales(self, production_config_path):
        """Test that all generators have rationales."""
        loader = GeneratorConfigLoader(production_config_path)
        config = loader.load()

        for qtype, assignment in config.generators.items():
            assert assignment.rationale is not None, f"{qtype} missing rationale"
            assert len(assignment.rationale) > 10, f"{qtype} rationale too short"

    def test_generators_yaml_version(self, production_config_path):
        """Test that configuration has a version."""
        loader = GeneratorConfigLoader(production_config_path)
        config = loader.load()

        assert config.version is not None
        assert config.version == "1.0"


class TestProviderTierSelection:
    """Tests for provider_tier parameter in get_provider_and_model_for_question_type."""

    @pytest.fixture
    def fallback_config_loader(self):
        """Fixture providing a loader with fallback_model configured for all types."""
        config_dict = {
            "version": "1.0",
            "generators": {
                "math": {
                    "provider": "openai",
                    "model": "gpt-4-turbo",
                    "rationale": "Math",
                    "fallback": "anthropic",
                    "fallback_model": "claude-opus-4-5-20251101",
                },
                "logic": {
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-5-20250929",
                    "rationale": "Logic",
                    "fallback": "openai",
                    "fallback_model": "gpt-4-turbo",
                },
                "pattern": {
                    "provider": "google",
                    "model": "gemini-3-pro-preview",
                    "rationale": "Patterns",
                    "fallback": "anthropic",
                    "fallback_model": "claude-sonnet-4-5-20250929",
                },
                "spatial": {
                    "provider": "google",
                    "model": "gemini-3-pro-preview",
                    "rationale": "Spatial",
                    "fallback": "openai",
                    "fallback_model": "gpt-4-turbo",
                },
                "verbal": {
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-5-20250929",
                    "rationale": "Verbal",
                    "fallback": "google",
                    "fallback_model": "gemini-3-pro-preview",
                },
                "memory": {
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-5-20250929",
                    "rationale": "Memory",
                    "fallback": "xai",
                    "fallback_model": "grok-4",
                },
            },
            "default_generator": {
                "provider": "openai",
                "model": "gpt-4-turbo",
                "rationale": "Default",
            },
            "use_specialist_routing": True,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_dict, f)
            temp_path = Path(f.name)

        loader = GeneratorConfigLoader(temp_path)
        loader.load()
        yield loader
        temp_path.unlink()

    def test_primary_tier_returns_primary_provider(self, fallback_config_loader):
        """Test that provider_tier='primary' returns the primary provider."""
        (
            provider,
            model,
        ) = fallback_config_loader.get_provider_and_model_for_question_type(
            "math", ["openai", "anthropic"], provider_tier="primary"
        )
        assert provider == "openai"
        assert model == "gpt-4-turbo"

    def test_fallback_tier_returns_fallback_provider(self, fallback_config_loader):
        """Test that provider_tier='fallback' returns the fallback provider and model."""
        (
            provider,
            model,
        ) = fallback_config_loader.get_provider_and_model_for_question_type(
            "math", ["openai", "anthropic"], provider_tier="fallback"
        )
        assert provider == "anthropic"
        assert model == "claude-opus-4-5-20251101"

    def test_fallback_tier_falls_back_to_primary_when_no_fallback_configured(self):
        """Test that fallback tier uses primary when no fallback is configured."""
        config_dict = {
            "version": "1.0",
            "generators": {
                "math": {
                    "provider": "openai",
                    "model": "gpt-4-turbo",
                    "rationale": "Math",
                    # No fallback configured
                },
                "logic": {"provider": "openai", "rationale": "r"},
                "pattern": {"provider": "openai", "rationale": "r"},
                "spatial": {"provider": "openai", "rationale": "r"},
                "verbal": {"provider": "openai", "rationale": "r"},
                "memory": {"provider": "openai", "rationale": "r"},
            },
            "default_generator": {"provider": "openai", "rationale": "r"},
            "use_specialist_routing": True,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_dict, f)
            temp_path = Path(f.name)

        try:
            loader = GeneratorConfigLoader(temp_path)
            loader.load()

            provider, model = loader.get_provider_and_model_for_question_type(
                "math", ["openai"], provider_tier="fallback"
            )
            assert provider == "openai"
            assert model == "gpt-4-turbo"
        finally:
            temp_path.unlink()

    def test_fallback_tier_falls_back_to_primary_when_fallback_unavailable(
        self, fallback_config_loader
    ):
        """Test fallback tier uses primary when fallback provider is unavailable."""
        # math: primary=openai, fallback=anthropic
        # Only openai is available
        (
            provider,
            model,
        ) = fallback_config_loader.get_provider_and_model_for_question_type(
            "math", ["openai"], provider_tier="fallback"
        )
        assert provider == "openai"
        assert model == "gpt-4-turbo"

    def test_fallback_tier_across_all_question_types(self, fallback_config_loader):
        """Test that fallback tier correctly selects fallback for each question type."""
        expected = {
            "math": ("anthropic", "claude-opus-4-5-20251101"),
            "logic": ("openai", "gpt-4-turbo"),
            "pattern": ("anthropic", "claude-sonnet-4-5-20250929"),
            "spatial": ("openai", "gpt-4-turbo"),
            "verbal": ("google", "gemini-3-pro-preview"),
            "memory": ("xai", "grok-4"),
        }

        all_providers = ["openai", "anthropic", "google", "xai"]
        for qtype, (exp_provider, exp_model) in expected.items():
            (
                provider,
                model,
            ) = fallback_config_loader.get_provider_and_model_for_question_type(
                qtype, all_providers, provider_tier="fallback"
            )
            assert (
                provider == exp_provider
            ), f"{qtype}: expected {exp_provider}, got {provider}"
            assert model == exp_model, f"{qtype}: expected {exp_model}, got {model}"

    def test_default_tier_is_primary(self, fallback_config_loader):
        """Test that default provider_tier (not specified) behaves as primary."""
        # Without specifying provider_tier (uses default "primary")
        (
            provider_default,
            model_default,
        ) = fallback_config_loader.get_provider_and_model_for_question_type(
            "math", ["openai", "anthropic"]
        )
        # Explicitly specifying "primary"
        (
            provider_primary,
            model_primary,
        ) = fallback_config_loader.get_provider_and_model_for_question_type(
            "math", ["openai", "anthropic"], provider_tier="primary"
        )
        assert provider_default == provider_primary
        assert model_default == model_primary

    def test_fallback_tier_with_no_providers_available_raises(
        self, fallback_config_loader
    ):
        """Test that fallback tier raises ValueError when no providers available."""
        with pytest.raises(ValueError, match="No providers available"):
            fallback_config_loader.get_provider_and_model_for_question_type(
                "math", [], provider_tier="fallback"
            )

    def test_fallback_tier_uses_any_available_when_neither_configured(
        self, fallback_config_loader
    ):
        """Test fallback tier uses any available provider when neither primary nor fallback available."""
        # math: primary=openai, fallback=anthropic
        # Only xai available (neither primary nor fallback)
        (
            provider,
            model,
        ) = fallback_config_loader.get_provider_and_model_for_question_type(
            "math", ["xai"], provider_tier="fallback"
        )
        assert provider == "xai"
        assert model is None  # No model override for last-resort fallback


class TestFallbackModelEdgeCases:
    """Edge case tests for fallback_model behavior.

    Covers scenarios where fallback_model interacts with default_generator
    and where the primary provider is available so fallback_model is not used.
    """

    def test_default_generator_uses_fallback_model_when_primary_unavailable(self):
        """Test that default_generator's fallback_model is used for unknown question types."""
        config_dict = {
            "version": "1.0",
            "generators": {
                "math": {"provider": "openai", "rationale": "r"},
                "logic": {"provider": "openai", "rationale": "r"},
                "pattern": {"provider": "openai", "rationale": "r"},
                "spatial": {"provider": "openai", "rationale": "r"},
                "verbal": {"provider": "openai", "rationale": "r"},
                "memory": {"provider": "openai", "rationale": "r"},
            },
            "default_generator": {
                "provider": "openai",
                "model": "gpt-4-turbo",
                "rationale": "Default generator",
                "fallback": "anthropic",
                "fallback_model": "claude-sonnet-4-5-20250929",
            },
            "use_specialist_routing": True,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_dict, f)
            temp_path = Path(f.name)

        try:
            loader = GeneratorConfigLoader(temp_path)
            loader.load()

            # Unknown type falls back to default_generator.
            # Primary (openai) is unavailable, only anthropic available.
            provider, model = loader.get_provider_and_model_for_question_type(
                "unknown_type", ["anthropic"]
            )
            assert provider == "anthropic"
            assert model == "claude-sonnet-4-5-20250929"
        finally:
            temp_path.unlink()

    def test_default_generator_returns_primary_model_when_primary_available(self):
        """Test that default_generator returns primary model when primary provider is available."""
        config_dict = {
            "version": "1.0",
            "generators": {
                "math": {"provider": "openai", "rationale": "r"},
                "logic": {"provider": "openai", "rationale": "r"},
                "pattern": {"provider": "openai", "rationale": "r"},
                "spatial": {"provider": "openai", "rationale": "r"},
                "verbal": {"provider": "openai", "rationale": "r"},
                "memory": {"provider": "openai", "rationale": "r"},
            },
            "default_generator": {
                "provider": "openai",
                "model": "gpt-4-turbo",
                "rationale": "Default generator",
                "fallback": "anthropic",
                "fallback_model": "claude-sonnet-4-5-20250929",
            },
            "use_specialist_routing": True,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_dict, f)
            temp_path = Path(f.name)

        try:
            loader = GeneratorConfigLoader(temp_path)
            loader.load()

            # Unknown type falls back to default_generator.
            # Primary (openai) IS available, so fallback_model should NOT be used.
            provider, model = loader.get_provider_and_model_for_question_type(
                "unknown_type", ["openai", "anthropic"]
            )
            assert provider == "openai"
            assert model == "gpt-4-turbo"  # Primary model, not fallback_model
        finally:
            temp_path.unlink()

    def test_default_generator_fallback_tier_uses_fallback_model(self):
        """Test that provider_tier='fallback' uses default_generator's fallback_model."""
        config_dict = {
            "version": "1.0",
            "generators": {
                "math": {"provider": "openai", "rationale": "r"},
                "logic": {"provider": "openai", "rationale": "r"},
                "pattern": {"provider": "openai", "rationale": "r"},
                "spatial": {"provider": "openai", "rationale": "r"},
                "verbal": {"provider": "openai", "rationale": "r"},
                "memory": {"provider": "openai", "rationale": "r"},
            },
            "default_generator": {
                "provider": "openai",
                "model": "gpt-4-turbo",
                "rationale": "Default generator",
                "fallback": "anthropic",
                "fallback_model": "claude-sonnet-4-5-20250929",
            },
            "use_specialist_routing": True,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_dict, f)
            temp_path = Path(f.name)

        try:
            loader = GeneratorConfigLoader(temp_path)
            loader.load()

            # Explicitly request fallback tier for an unknown question type.
            # Should use default_generator's fallback provider and fallback_model.
            provider, model = loader.get_provider_and_model_for_question_type(
                "unknown_type", ["openai", "anthropic"], provider_tier="fallback"
            )
            assert provider == "anthropic"
            assert model == "claude-sonnet-4-5-20250929"
        finally:
            temp_path.unlink()

    def test_fallback_model_not_used_when_primary_available(self):
        """Test that fallback_model is ignored when primary provider is available (no fallback needed)."""
        config_dict = {
            "version": "1.0",
            "generators": {
                "math": {
                    "provider": "xai",
                    "model": "grok-4",
                    "rationale": "Math",
                    "fallback": "anthropic",
                    "fallback_model": "claude-sonnet-4-5-20250929",
                },
                "logic": {
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-5-20250929",
                    "rationale": "Logic",
                    "fallback": "openai",
                    "fallback_model": "gpt-5.2",
                },
                "pattern": {"provider": "openai", "rationale": "r"},
                "spatial": {"provider": "openai", "rationale": "r"},
                "verbal": {"provider": "openai", "rationale": "r"},
                "memory": {"provider": "openai", "rationale": "r"},
            },
            "default_generator": {"provider": "openai", "rationale": "Default"},
            "use_specialist_routing": True,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_dict, f)
            temp_path = Path(f.name)

        try:
            loader = GeneratorConfigLoader(temp_path)
            loader.load()

            # All providers available - primary should be used, fallback_model ignored
            all_providers = ["openai", "anthropic", "google", "xai"]

            provider, model = loader.get_provider_and_model_for_question_type(
                "math", all_providers
            )
            assert provider == "xai"
            assert model == "grok-4"  # Primary model, NOT fallback_model

            provider, model = loader.get_provider_and_model_for_question_type(
                "logic", all_providers
            )
            assert provider == "anthropic"
            assert model == "claude-sonnet-4-5-20250929"  # Primary model, NOT gpt-5.2
        finally:
            temp_path.unlink()

    def test_fallback_model_not_used_when_primary_available_explicit_tier(self):
        """Test that explicitly requesting primary tier ignores fallback_model even when configured."""
        config_dict = {
            "version": "1.0",
            "generators": {
                "math": {
                    "provider": "xai",
                    "model": "grok-4",
                    "rationale": "Math",
                    "fallback": "anthropic",
                    "fallback_model": "claude-opus-4-5-20251101",
                },
                "logic": {"provider": "openai", "rationale": "r"},
                "pattern": {"provider": "openai", "rationale": "r"},
                "spatial": {"provider": "openai", "rationale": "r"},
                "verbal": {"provider": "openai", "rationale": "r"},
                "memory": {"provider": "openai", "rationale": "r"},
            },
            "default_generator": {"provider": "openai", "rationale": "Default"},
            "use_specialist_routing": True,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_dict, f)
            temp_path = Path(f.name)

        try:
            loader = GeneratorConfigLoader(temp_path)
            loader.load()

            # Explicitly request primary tier - should return primary model
            provider, model = loader.get_provider_and_model_for_question_type(
                "math", ["xai", "anthropic"], provider_tier="primary"
            )
            assert provider == "xai"
            assert model == "grok-4"  # Primary model, NOT claude-opus-4-5-20251101
        finally:
            temp_path.unlink()
