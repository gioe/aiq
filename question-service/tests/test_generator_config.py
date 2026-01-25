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


class TestGlobalConfiguration:
    """Tests for global configuration functions."""

    def test_initialize_and_get(self, valid_config_file):
        """Test initializing and getting global configuration."""
        # Reset global loader
        import app.generator_config as config_module

        config_module._loader = None

        # Initialize
        initialize_generator_config(valid_config_file)

        # Get and verify
        loader = get_generator_config()
        assert isinstance(loader, GeneratorConfigLoader)

        config = loader.config
        assert config.version == "1.0"

    def test_get_before_initialize(self):
        """Test that getting config before initialize raises error."""
        # Reset global loader
        import app.generator_config as config_module

        config_module._loader = None

        with pytest.raises(RuntimeError) as exc_info:
            get_generator_config()
        assert "not initialized" in str(exc_info.value).lower()

    def test_is_generator_config_initialized(self, valid_config_file):
        """Test checking if generator config is initialized."""
        import app.generator_config as config_module

        # Reset and check not initialized
        config_module._loader = None
        assert is_generator_config_initialized() is False

        # Initialize and check
        initialize_generator_config(valid_config_file)
        assert is_generator_config_initialized() is True


class TestProductionGeneratorsYaml:
    """Integration tests for the production generators.yaml configuration.

    These tests validate that the actual generators.yaml file in config/
    loads successfully and contains expected values.
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

    def test_generators_yaml_pattern_uses_google(self, production_config_path):
        """Test that pattern questions use Google provider."""
        loader = GeneratorConfigLoader(production_config_path)
        config = loader.load()

        assert config.generators["pattern"].provider == "google"
        assert config.generators["pattern"].model == "gemini-3-pro-preview"

    def test_generators_yaml_spatial_uses_google(self, production_config_path):
        """Test that spatial questions use Google provider."""
        loader = GeneratorConfigLoader(production_config_path)
        config = loader.load()

        assert config.generators["spatial"].provider == "google"
        assert config.generators["spatial"].model == "gemini-3-pro-preview"

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

    def test_generators_yaml_memory_uses_anthropic(self, production_config_path):
        """Test that memory questions use Anthropic provider."""
        loader = GeneratorConfigLoader(production_config_path)
        config = loader.load()

        assert config.generators["memory"].provider == "anthropic"
        assert config.generators["memory"].model == "claude-sonnet-4-5-20250929"

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
