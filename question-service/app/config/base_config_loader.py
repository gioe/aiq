"""Shared base class for configuration loaders.

Provides the common skeleton shared by GeneratorConfigLoader and JudgeConfigLoader:
YAML loading, Pydantic validation scaffolding, the singleton pattern helpers,
get_all_question_types(), and the provider resolution chain.
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generic, Optional, TypeVar

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

REQUIRED_QUESTION_TYPES: frozenset[str] = frozenset(
    {"math", "logic", "pattern", "spatial", "verbal", "memory"}
)

ConfigT = TypeVar("ConfigT")


class BaseAssignment(BaseModel):
    """Shared provider fields and validators for assignment models.

    Both GeneratorAssignment and JudgeModel extend this to inherit
    validate_provider and validate_fallback_model_requires_fallback.
    """

    provider: str = Field(..., pattern="^(openai|anthropic|google|xai)$")
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

    @model_validator(mode="after")
    def validate_fallback_model_requires_fallback(self) -> "BaseAssignment":
        """Validate that fallback_model is only set when fallback is also set."""
        if self.fallback_model is not None and self.fallback is None:
            raise ValueError("fallback_model cannot be set without a fallback provider")
        return self


class BaseConfigLoader(ABC, Generic[ConfigT]):
    """Abstract base for YAML-backed configuration loaders.

    Subclasses must implement:
    - _parse_config(raw_config): create and validate the typed config object
    - _get_assignments_dict(): return the {question_type: assignment} mapping
    - _on_load_success(config): emit a post-load info log (optional override)
    - _no_providers_error_message(question_type, available_providers): error message string
    """

    def __init__(self, config_path: str | Path) -> None:
        """Initialize the configuration loader.

        Args:
            config_path: Path to the configuration YAML file
        """
        self.config_path = Path(config_path)
        self._config: Optional[ConfigT] = None

    @property
    def _config_label(self) -> str:
        return "configuration"

    @abstractmethod
    def _parse_config(self, raw_config: dict) -> ConfigT:
        """Parse and validate raw YAML dict into the typed config model."""
        ...

    @abstractmethod
    def _get_assignments_dict(self) -> dict:
        """Return the {question_type: assignment} mapping from the loaded config."""
        ...

    def _on_load_success(self, config: ConfigT) -> None:
        logger.info(f"Successfully loaded {self._config_label}")

    def _no_providers_error_message(
        self, question_type: str, available_providers: list[str]
    ) -> str:
        return f"No providers available for question type '{question_type}'"

    def load(self) -> ConfigT:
        """Load and parse the configuration file.

        Returns:
            Parsed and validated configuration

        Raises:
            FileNotFoundError: If configuration file doesn't exist
            ValueError: If configuration is invalid
            yaml.YAMLError: If YAML parsing fails
        """
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"{self._config_label.capitalize()} file not found: {self.config_path}"
            )

        logger.info(f"Loading {self._config_label} from {self.config_path}")

        try:
            with open(self.config_path, "r") as f:
                raw_config = yaml.safe_load(f)

            self._config = self._parse_config(raw_config)
            self._on_load_success(self._config)
            return self._config

        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML configuration: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load {self._config_label}: {e}")
            raise

    @property
    def config(self) -> ConfigT:
        """Get the loaded configuration.

        Raises:
            RuntimeError: If configuration hasn't been loaded yet
        """
        if self._config is None:
            raise RuntimeError("Configuration not loaded. Call load() first.")
        return self._config

    def get_all_question_types(self) -> list[str]:
        """Get all configured question types.

        Raises:
            RuntimeError: If configuration hasn't been loaded
        """
        return list(self._get_assignments_dict().keys())

    def _resolve_provider(
        self,
        preferred: tuple[Optional[str], Optional[str]],
        alternate: tuple[Optional[str], Optional[str]],
        question_type: str,
        available_providers: list[str],
        provider_tier: str = "primary",
    ) -> tuple[Optional[str], Optional[str]]:
        """Resolve the best available provider using a preferred -> alternate -> any chain.

        Args:
            preferred: (provider, model) to try first
            alternate: (provider, model) to try if preferred is unavailable
            question_type: Question type for logging
            available_providers: Currently available provider names
            provider_tier: Tier name for logging ("primary" or "fallback")

        Returns:
            Tuple of (provider_name, model_override)

        Raises:
            ValueError: If no suitable provider is available
        """
        pref_provider, pref_model = preferred
        alt_provider, alt_model = alternate

        # 1. Try preferred provider
        if pref_provider and pref_provider in available_providers:
            if provider_tier == "fallback":
                logger.info(
                    f"Using fallback provider '{pref_provider}' for "
                    f"'{question_type}' (tier={provider_tier})"
                    f"{f' with model {pref_model}' if pref_model else ''}"
                )
            return (pref_provider, pref_model)

        # 2. Try alternate provider
        if alt_provider and alt_provider in available_providers:
            logger.warning(
                f"Preferred provider '{pref_provider}' unavailable for "
                f"'{question_type}' (tier={provider_tier}), "
                f"using alternate '{alt_provider}'"
            )
            return (alt_provider, alt_model)

        # 3. Fall back to any available provider
        if available_providers:
            any_provider = available_providers[0]
            logger.warning(
                f"Neither preferred '{pref_provider}' nor alternate "
                f"'{alt_provider}' available for '{question_type}', "
                f"using '{any_provider}' (no model override)"
            )
            return (any_provider, None)

        raise ValueError(
            self._no_providers_error_message(question_type, available_providers)
        )
