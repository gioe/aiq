"""Generator configuration management.

This module provides functionality to load and access generator configuration
from YAML files. It maps question types to specific LLM providers for
question generation (specialist routing).
"""

import logging
from pathlib import Path
from typing import Dict, Optional

import yaml
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class GeneratorAssignment(BaseModel):
    """Configuration for a single generator assignment.

    Attributes:
        provider: Provider name ("openai", "anthropic", "google", or "xai")
        model: Optional specific model to use (overrides provider default)
        rationale: Explanation of why this provider was chosen
        fallback: Fallback provider if primary is unavailable
        fallback_model: Optional specific model to use when fallback provider is activated
    """

    provider: str = Field(..., pattern="^(openai|anthropic|google|xai)$")
    model: Optional[str] = Field(
        None, description="Specific model to use for this question type"
    )
    rationale: str = Field(..., min_length=1)
    fallback: Optional[str] = Field(None, pattern="^(openai|anthropic|google|xai)$")
    fallback_model: Optional[str] = Field(
        None, description="Specific model to use when fallback provider is activated"
    )

    @field_validator("provider", "fallback")
    @classmethod
    def validate_provider(cls, v: Optional[str]) -> Optional[str]:
        """Validate provider is one of the supported options."""
        if v is None:
            return v
        valid_providers = {"openai", "anthropic", "google", "xai"}
        if v not in valid_providers:
            raise ValueError(f"Provider must be one of {valid_providers}, got '{v}'")
        return v


class GeneratorConfig(BaseModel):
    """Complete generator configuration.

    Attributes:
        version: Configuration version
        generators: Mapping of question types to generator providers
        default_generator: Fallback generator for unknown question types
        use_specialist_routing: Whether to use specialist routing or round-robin
    """

    version: str
    generators: Dict[str, GeneratorAssignment]
    default_generator: GeneratorAssignment
    use_specialist_routing: bool = True

    @field_validator("generators")
    @classmethod
    def validate_generators(
        cls, v: Dict[str, GeneratorAssignment]
    ) -> Dict[str, GeneratorAssignment]:
        """Validate that required question types are present."""
        required_types = {
            "math",
            "logic",
            "pattern",
            "spatial",
            "verbal",
            "memory",
        }
        missing = required_types - set(v.keys())
        if missing:
            raise ValueError(
                f"Missing required question types in generator config: {missing}"
            )
        return v


class GeneratorConfigLoader:
    """Loader for generator configuration files.

    This class handles loading, parsing, and validating generator configuration
    from YAML files.
    """

    def __init__(self, config_path: str | Path):
        """Initialize the configuration loader.

        Args:
            config_path: Path to the generator configuration YAML file
        """
        self.config_path = Path(config_path)
        self._config: Optional[GeneratorConfig] = None

    def load(self) -> GeneratorConfig:
        """Load and parse the configuration file.

        Returns:
            Parsed and validated generator configuration

        Raises:
            FileNotFoundError: If configuration file doesn't exist
            ValueError: If configuration is invalid
            yaml.YAMLError: If YAML parsing fails
        """
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Generator configuration file not found: {self.config_path}"
            )

        logger.info(f"Loading generator configuration from {self.config_path}")

        try:
            with open(self.config_path, "r") as f:
                raw_config = yaml.safe_load(f)

            self._config = GeneratorConfig(**raw_config)
            logger.info(
                f"Successfully loaded generator configuration "
                f"(version {self._config.version}, "
                f"specialist_routing={self._config.use_specialist_routing})"
            )
            return self._config

        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML configuration: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load generator configuration: {e}")
            raise

    @property
    def config(self) -> GeneratorConfig:
        """Get the loaded configuration.

        Returns:
            Loaded configuration

        Raises:
            RuntimeError: If configuration hasn't been loaded yet
        """
        if self._config is None:
            raise RuntimeError("Configuration not loaded. Call load() first.")
        return self._config

    def get_provider_for_question_type(
        self, question_type: str, available_providers: list[str]
    ) -> Optional[str]:
        """Get the preferred provider for a specific question type.

        Args:
            question_type: Type of question (e.g., "math", "logic", "pattern")
            available_providers: List of currently available provider names

        Returns:
            Provider name to use for generation, or None if no providers available

        Raises:
            RuntimeError: If configuration hasn't been loaded
            ValueError: If no suitable provider is available
        """
        config = self.config  # Ensures config is loaded

        # If specialist routing is disabled, return first available or None
        if not config.use_specialist_routing:
            return available_providers[0] if available_providers else None

        # Get assignment for this question type
        if question_type in config.generators:
            assignment = config.generators[question_type]
        else:
            logger.info(f"No generator assignment for '{question_type}', using default")
            assignment = config.default_generator

        # Check if primary provider is available
        if assignment.provider in available_providers:
            return assignment.provider

        # Try fallback provider
        if assignment.fallback and assignment.fallback in available_providers:
            logger.warning(
                f"Primary provider '{assignment.provider}' unavailable for "
                f"'{question_type}', using fallback '{assignment.fallback}'"
            )
            return assignment.fallback

        # Fall back to any available provider
        if available_providers:
            fallback = available_providers[0]
            logger.warning(
                f"Neither primary '{assignment.provider}' nor fallback "
                f"'{assignment.fallback}' available for '{question_type}', "
                f"using '{fallback}'"
            )
            return fallback

        raise ValueError(f"No providers available for question type '{question_type}'")

    def get_provider_and_model_for_question_type(
        self, question_type: str, available_providers: list[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """Get the preferred provider and model for a specific question type.

        Args:
            question_type: Type of question (e.g., "math", "logic", "pattern")
            available_providers: List of currently available provider names

        Returns:
            Tuple of (provider_name, model_override). Model may be None if not specified.

        Raises:
            RuntimeError: If configuration hasn't been loaded
            ValueError: If no suitable provider is available
        """
        config = self.config  # Ensures config is loaded

        # If specialist routing is disabled, return first available with no model override
        if not config.use_specialist_routing:
            provider = available_providers[0] if available_providers else None
            return (provider, None)

        # Get assignment for this question type
        if question_type in config.generators:
            assignment = config.generators[question_type]
        else:
            logger.info(f"No generator assignment for '{question_type}', using default")
            assignment = config.default_generator

        # Check if primary provider is available
        if assignment.provider in available_providers:
            return (assignment.provider, assignment.model)

        # Try fallback provider
        if assignment.fallback and assignment.fallback in available_providers:
            logger.warning(
                f"Primary provider '{assignment.provider}' unavailable for "
                f"'{question_type}', using fallback '{assignment.fallback}'"
                f"{f' with model {assignment.fallback_model}' if assignment.fallback_model else ''}"
            )
            return (assignment.fallback, assignment.fallback_model)

        # Fall back to any available provider (no model override)
        if available_providers:
            fallback = available_providers[0]
            logger.warning(
                f"Neither primary '{assignment.provider}' nor fallback "
                f"'{assignment.fallback}' available for '{question_type}', "
                f"using '{fallback}' (no model override)"
            )
            return (fallback, None)

        raise ValueError(f"No providers available for question type '{question_type}'")

    def is_specialist_routing_enabled(self) -> bool:
        """Check if specialist routing is enabled.

        Returns:
            True if specialist routing is enabled, False for round-robin
        """
        return self.config.use_specialist_routing

    def get_all_question_types(self) -> list[str]:
        """Get all configured question types.

        Returns:
            List of question type names

        Raises:
            RuntimeError: If configuration hasn't been loaded
        """
        return list(self.config.generators.keys())

    def get_provider_summary(self) -> Dict[str, list[str]]:
        """Get a summary of which providers handle which question types.

        Returns:
            Dictionary mapping provider names to list of question types
        """
        summary: Dict[str, list[str]] = {}
        for qtype, assignment in self.config.generators.items():
            provider = assignment.provider
            if provider not in summary:
                summary[provider] = []
            summary[provider].append(qtype)
        return summary


# Global loader instance (to be initialized on application startup)
_loader: Optional[GeneratorConfigLoader] = None


def initialize_generator_config(config_path: str | Path) -> None:
    """Initialize the global generator configuration loader.

    Args:
        config_path: Path to the generator configuration YAML file

    Raises:
        FileNotFoundError: If configuration file doesn't exist
        ValueError: If configuration is invalid
    """
    global _loader
    _loader = GeneratorConfigLoader(config_path)
    _loader.load()


def get_generator_config() -> GeneratorConfigLoader:
    """Get the global generator configuration loader.

    Returns:
        Initialized configuration loader

    Raises:
        RuntimeError: If configuration hasn't been initialized
    """
    if _loader is None:
        raise RuntimeError(
            "Generator configuration not initialized. "
            "Call initialize_generator_config() first."
        )
    return _loader


def is_generator_config_initialized() -> bool:
    """Check if generator configuration has been initialized.

    Returns:
        True if initialized, False otherwise
    """
    return _loader is not None
