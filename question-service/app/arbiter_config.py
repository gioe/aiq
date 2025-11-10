"""Arbiter configuration management.

This module provides functionality to load and access arbiter configuration
from YAML files. It maps question types to specific arbiter models for
quality evaluation.
"""

import logging
from pathlib import Path
from typing import Dict, Optional

import yaml
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class ArbiterModel(BaseModel):
    """Configuration for a single arbiter model.

    Attributes:
        model: Model identifier (e.g., "gpt-4", "claude-3-5-sonnet-20241022")
        provider: Provider name ("openai", "anthropic", or "google")
        rationale: Explanation of why this model was chosen
        enabled: Whether this arbiter is active
    """

    model: str = Field(..., min_length=1)
    provider: str = Field(..., pattern="^(openai|anthropic|google)$")
    rationale: str = Field(..., min_length=1)
    enabled: bool = True

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """Validate provider is one of the supported options."""
        valid_providers = {"openai", "anthropic", "google"}
        if v not in valid_providers:
            raise ValueError(f"Provider must be one of {valid_providers}, got '{v}'")
        return v


class EvaluationCriteria(BaseModel):
    """Weights for evaluation criteria (should sum to 1.0).

    Attributes:
        clarity: Weight for question clarity and lack of ambiguity
        difficulty: Weight for appropriate difficulty level
        validity: Weight for validity as an IQ test question
        formatting: Weight for proper formatting
        creativity: Weight for novelty and interest
    """

    clarity: float = Field(..., ge=0.0, le=1.0)
    difficulty: float = Field(..., ge=0.0, le=1.0)
    validity: float = Field(..., ge=0.0, le=1.0)
    formatting: float = Field(..., ge=0.0, le=1.0)
    creativity: float = Field(..., ge=0.0, le=1.0)

    @field_validator("creativity")
    @classmethod
    def validate_sum(cls, v: float, info) -> float:
        """Validate that all weights sum to approximately 1.0."""
        if info.data:
            total = (
                info.data.get("clarity", 0.0)
                + info.data.get("difficulty", 0.0)
                + info.data.get("validity", 0.0)
                + info.data.get("formatting", 0.0)
                + v
            )
            if not (0.99 <= total <= 1.01):  # Allow small floating point errors
                raise ValueError(
                    f"Evaluation criteria weights must sum to 1.0, got {total}"
                )
        return v


class ArbiterConfig(BaseModel):
    """Complete arbiter configuration.

    Attributes:
        version: Configuration version
        arbiters: Mapping of question types to arbiter models
        default_arbiter: Fallback arbiter for unknown question types
        evaluation_criteria: Weights for evaluation criteria
        min_arbiter_score: Minimum score threshold for approval
    """

    version: str
    arbiters: Dict[str, ArbiterModel]
    default_arbiter: ArbiterModel
    evaluation_criteria: EvaluationCriteria
    min_arbiter_score: float = Field(..., ge=0.0, le=1.0)

    @field_validator("arbiters")
    @classmethod
    def validate_arbiters(cls, v: Dict[str, ArbiterModel]) -> Dict[str, ArbiterModel]:
        """Validate that required question types are present."""
        required_types = {
            "mathematical",
            "logical_reasoning",
            "pattern_recognition",
            "spatial_reasoning",
            "verbal_reasoning",
            "memory",
        }
        missing = required_types - set(v.keys())
        if missing:
            raise ValueError(
                f"Missing required question types in arbiter config: {missing}"
            )
        return v


class ArbiterConfigLoader:
    """Loader for arbiter configuration files.

    This class handles loading, parsing, and validating arbiter configuration
    from YAML files.
    """

    def __init__(self, config_path: str | Path):
        """Initialize the configuration loader.

        Args:
            config_path: Path to the arbiter configuration YAML file
        """
        self.config_path = Path(config_path)
        self._config: Optional[ArbiterConfig] = None

    def load(self) -> ArbiterConfig:
        """Load and parse the configuration file.

        Returns:
            Parsed and validated arbiter configuration

        Raises:
            FileNotFoundError: If configuration file doesn't exist
            ValueError: If configuration is invalid
            yaml.YAMLError: If YAML parsing fails
        """
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Arbiter configuration file not found: {self.config_path}"
            )

        logger.info(f"Loading arbiter configuration from {self.config_path}")

        try:
            with open(self.config_path, "r") as f:
                raw_config = yaml.safe_load(f)

            self._config = ArbiterConfig(**raw_config)
            logger.info(
                f"Successfully loaded arbiter configuration (version {self._config.version})"
            )
            return self._config

        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML configuration: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load arbiter configuration: {e}")
            raise

    @property
    def config(self) -> ArbiterConfig:
        """Get the loaded configuration.

        Returns:
            Loaded configuration

        Raises:
            RuntimeError: If configuration hasn't been loaded yet
        """
        if self._config is None:
            raise RuntimeError("Configuration not loaded. Call load() first.")
        return self._config

    def get_arbiter_for_question_type(self, question_type: str) -> ArbiterModel:
        """Get the arbiter model for a specific question type.

        Args:
            question_type: Type of question (e.g., "mathematical", "logical_reasoning")

        Returns:
            Arbiter model configuration for the question type

        Raises:
            RuntimeError: If configuration hasn't been loaded
        """
        config = self.config  # Ensures config is loaded

        # Return specific arbiter if found and enabled
        if question_type in config.arbiters:
            arbiter = config.arbiters[question_type]
            if arbiter.enabled:
                return arbiter
            else:
                logger.warning(
                    f"Arbiter for '{question_type}' is disabled, using default"
                )

        # Fall back to default arbiter
        logger.info(f"Using default arbiter for question type '{question_type}'")
        return config.default_arbiter

    def get_all_question_types(self) -> list[str]:
        """Get all configured question types.

        Returns:
            List of question type names

        Raises:
            RuntimeError: If configuration hasn't been loaded
        """
        return list(self.config.arbiters.keys())

    def get_evaluation_criteria(self) -> EvaluationCriteria:
        """Get evaluation criteria weights.

        Returns:
            Evaluation criteria configuration

        Raises:
            RuntimeError: If configuration hasn't been loaded
        """
        return self.config.evaluation_criteria

    def get_min_arbiter_score(self) -> float:
        """Get minimum arbiter score threshold.

        Returns:
            Minimum score for question approval

        Raises:
            RuntimeError: If configuration hasn't been loaded
        """
        return self.config.min_arbiter_score


# Global loader instance (to be initialized on application startup)
_loader: Optional[ArbiterConfigLoader] = None


def initialize_arbiter_config(config_path: str | Path) -> None:
    """Initialize the global arbiter configuration loader.

    Args:
        config_path: Path to the arbiter configuration YAML file

    Raises:
        FileNotFoundError: If configuration file doesn't exist
        ValueError: If configuration is invalid
    """
    global _loader
    _loader = ArbiterConfigLoader(config_path)
    _loader.load()


def get_arbiter_config() -> ArbiterConfigLoader:
    """Get the global arbiter configuration loader.

    Returns:
        Initialized configuration loader

    Raises:
        RuntimeError: If configuration hasn't been initialized
    """
    if _loader is None:
        raise RuntimeError(
            "Arbiter configuration not initialized. "
            "Call initialize_arbiter_config() first."
        )
    return _loader
