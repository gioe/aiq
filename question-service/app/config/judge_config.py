"""Judge configuration management.

This module provides functionality to load and access judge configuration
from YAML files. It maps question types to specific judge models for
quality evaluation.
"""

import logging
from pathlib import Path
from typing import Dict, Optional

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

# Tolerance bounds for floating point comparison when checking weights sum to 1.0
WEIGHT_SUM_TOLERANCE_LOW = 0.99
WEIGHT_SUM_TOLERANCE_HIGH = 1.01


class JudgeModel(BaseModel):
    """Configuration for a single judge model.

    Attributes:
        model: Model identifier (e.g., "gpt-4", "claude-3-5-sonnet-20241022")
        provider: Provider name ("openai", "anthropic", or "google")
        rationale: Explanation of why this model was chosen
        enabled: Whether this judge is active
        fallback: Optional fallback provider if primary is unavailable
        fallback_model: Optional specific model to use when fallback provider is activated
    """

    model: str = Field(..., min_length=1)
    provider: str = Field(..., pattern="^(openai|anthropic|google|xai)$")
    rationale: str = Field(..., min_length=1)
    enabled: bool = True
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
    def validate_fallback_model_requires_fallback(self) -> "JudgeModel":
        """Validate that fallback_model is only set when fallback is also set."""
        if self.fallback_model is not None and self.fallback is None:
            raise ValueError("fallback_model cannot be set without a fallback provider")
        return self


class EvaluationCriteria(BaseModel):
    """Weights for ACCEPTANCE criteria (should sum to 1.0).

    Note: Difficulty is NOT included here. Difficulty determines PLACEMENT,
    not acceptance. A high-quality question that's "too easy for hard" will
    be accepted but placed at the appropriate difficulty level.

    Attributes:
        clarity: Weight for question clarity and lack of ambiguity
        validity: Weight for validity as an IQ test question
        formatting: Weight for proper formatting
        creativity: Weight for novelty and interest
    """

    clarity: float = Field(..., ge=0.0, le=1.0)
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
                + info.data.get("validity", 0.0)
                + info.data.get("formatting", 0.0)
                + v
            )
            if not (WEIGHT_SUM_TOLERANCE_LOW <= total <= WEIGHT_SUM_TOLERANCE_HIGH):
                raise ValueError(
                    f"Evaluation criteria weights must sum to 1.0, got {total}"
                )
        return v


class DifficultyPlacement(BaseModel):
    """Configuration for difficulty-based placement of questions.

    The difficulty score from the judge determines where a question is placed,
    not whether it's accepted. This allows high-quality questions that are
    "too easy" or "too hard" for their target level to be reclassified.

    Attributes:
        downgrade_threshold: Score below which to downgrade one level
        upgrade_threshold: Score above which to upgrade one level
        too_easy_patterns: Feedback patterns indicating question is too easy
        too_hard_patterns: Feedback patterns indicating question is too hard
    """

    downgrade_threshold: float = Field(default=0.4, ge=0.0, le=1.0)
    upgrade_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    too_easy_patterns: list[str] = Field(
        default_factory=lambda: ["too easy", "straightforward"]
    )
    too_hard_patterns: list[str] = Field(
        default_factory=lambda: ["too hard", "too difficult"]
    )


class JudgeConfig(BaseModel):
    """Complete judge configuration.

    Attributes:
        version: Configuration version
        judges: Mapping of question types to judge models
        default_judge: Fallback judge for unknown question types
        evaluation_criteria: Weights for acceptance criteria (excludes difficulty)
        min_judge_score: Minimum score threshold for approval
        difficulty_placement: Configuration for difficulty-based placement
    """

    version: str
    judges: Dict[str, JudgeModel]
    default_judge: JudgeModel
    evaluation_criteria: EvaluationCriteria
    min_judge_score: float = Field(..., ge=0.0, le=1.0)
    difficulty_placement: DifficultyPlacement = Field(
        default_factory=lambda: DifficultyPlacement()
    )

    @field_validator("judges")
    @classmethod
    def validate_judges(cls, v: Dict[str, JudgeModel]) -> Dict[str, JudgeModel]:
        """Validate that required question types are present.

        Note: Keys must match QuestionType enum values from app/models.py
        (pattern, logic, spatial, math, verbal, memory).
        """
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
                f"Missing required question types in judge config: {missing}"
            )
        return v


class JudgeConfigLoader:
    """Loader for judge configuration files.

    This class handles loading, parsing, and validating judge configuration
    from YAML files.
    """

    def __init__(self, config_path: str | Path):
        """Initialize the configuration loader.

        Args:
            config_path: Path to the judge configuration YAML file
        """
        self.config_path = Path(config_path)
        self._config: Optional[JudgeConfig] = None

    def load(self) -> JudgeConfig:
        """Load and parse the configuration file.

        Returns:
            Parsed and validated judge configuration

        Raises:
            FileNotFoundError: If configuration file doesn't exist
            ValueError: If configuration is invalid
            yaml.YAMLError: If YAML parsing fails
        """
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Judge configuration file not found: {self.config_path}"
            )

        logger.info(f"Loading judge configuration from {self.config_path}")

        try:
            with open(self.config_path, "r") as f:
                raw_config = yaml.safe_load(f)

            self._config = JudgeConfig(**raw_config)
            logger.info(
                f"Successfully loaded judge configuration (version {self._config.version})"
            )
            return self._config

        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML configuration: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load judge configuration: {e}")
            raise

    @property
    def config(self) -> JudgeConfig:
        """Get the loaded configuration.

        Returns:
            Loaded configuration

        Raises:
            RuntimeError: If configuration hasn't been loaded yet
        """
        if self._config is None:
            raise RuntimeError("Configuration not loaded. Call load() first.")
        return self._config

    def get_judge_for_question_type(self, question_type: str) -> JudgeModel:
        """Get the judge model for a specific question type.

        Args:
            question_type: Type of question (e.g., "math", "logic", "pattern")

        Returns:
            Judge model configuration for the question type

        Raises:
            RuntimeError: If configuration hasn't been loaded
        """
        config = self.config  # Ensures config is loaded

        # Return specific judge if found and enabled
        if question_type in config.judges:
            judge = config.judges[question_type]
            if judge.enabled:
                return judge
            else:
                logger.warning(
                    f"Judge for '{question_type}' is disabled, using default"
                )

        # Fall back to default judge
        logger.info(f"Using default judge for question type '{question_type}'")
        return config.default_judge

    def resolve_judge_provider(
        self,
        question_type: str,
        available_providers: list[str],
    ) -> tuple[str, Optional[str]]:
        """Resolve the best available provider and model for judging a question type.

        Uses a preferred -> alternate -> any resolution chain, matching the
        pattern in GeneratorConfigLoader._resolve_provider.

        Args:
            question_type: Type of question (e.g., "math", "logic", "pattern")
            available_providers: List of currently available provider names

        Returns:
            Tuple of (provider_name, model_override). Model may be None if not specified.

        Raises:
            RuntimeError: If configuration hasn't been loaded
            ValueError: If no suitable provider is available
        """
        judge_model = self.get_judge_for_question_type(question_type)

        preferred = (judge_model.provider, judge_model.model)
        alternate = (judge_model.fallback, judge_model.fallback_model)

        return self._resolve_provider(
            preferred, alternate, question_type, available_providers
        )

    def _resolve_provider(
        self,
        preferred: tuple[str, Optional[str]],
        alternate: tuple[Optional[str], Optional[str]],
        question_type: str,
        available_providers: list[str],
    ) -> tuple[str, Optional[str]]:
        """Resolve the best available provider using a preferred -> alternate -> any chain.

        Args:
            preferred: (provider, model) to try first
            alternate: (provider, model) to try if preferred is unavailable
            question_type: Question type for logging
            available_providers: Currently available provider names

        Returns:
            Tuple of (provider_name, model_override). Model may be None if not specified.

        Raises:
            ValueError: If no suitable provider is available
        """
        pref_provider, pref_model = preferred
        alt_provider, alt_model = alternate

        # 1. Try preferred provider
        if pref_provider in available_providers:
            return (pref_provider, pref_model)

        # 2. Try alternate (fallback) provider
        if alt_provider and alt_provider in available_providers:
            logger.warning(
                f"Judge provider '{pref_provider}' unavailable for "
                f"'{question_type}', using fallback '{alt_provider}'"
                f"{f' with model {alt_model}' if alt_model else ''}"
            )
            return (alt_provider, alt_model)

        # 3. Fall back to any available provider
        if available_providers:
            any_provider = available_providers[0]
            logger.warning(
                f"Neither preferred '{pref_provider}' nor fallback "
                f"'{alt_provider}' available for '{question_type}', "
                f"using '{any_provider}' (no model override)"
            )
            return (any_provider, None)

        raise ValueError(
            f"No judge providers available for question type '{question_type}'. "
            f"Available providers: {available_providers}"
        )

    def get_all_question_types(self) -> list[str]:
        """Get all configured question types.

        Returns:
            List of question type names

        Raises:
            RuntimeError: If configuration hasn't been loaded
        """
        return list(self.config.judges.keys())

    def get_evaluation_criteria(self) -> EvaluationCriteria:
        """Get evaluation criteria weights.

        Returns:
            Evaluation criteria configuration

        Raises:
            RuntimeError: If configuration hasn't been loaded
        """
        return self.config.evaluation_criteria

    def get_min_judge_score(self) -> float:
        """Get minimum judge score threshold.

        Returns:
            Minimum score for question approval

        Raises:
            RuntimeError: If configuration hasn't been loaded
        """
        return self.config.min_judge_score

    def get_difficulty_placement(self) -> DifficultyPlacement:
        """Get difficulty placement configuration.

        Returns:
            Difficulty placement configuration

        Raises:
            RuntimeError: If configuration hasn't been loaded
        """
        return self.config.difficulty_placement


# Global loader instance (to be initialized on application startup)
_loader: Optional[JudgeConfigLoader] = None


def initialize_judge_config(config_path: str | Path) -> None:
    """Initialize the global judge configuration loader.

    Args:
        config_path: Path to the judge configuration YAML file

    Raises:
        FileNotFoundError: If configuration file doesn't exist
        ValueError: If configuration is invalid
    """
    global _loader
    _loader = JudgeConfigLoader(config_path)
    _loader.load()


def get_judge_config() -> JudgeConfigLoader:
    """Get the global judge configuration loader.

    Returns:
        Initialized configuration loader

    Raises:
        RuntimeError: If configuration hasn't been initialized
    """
    if _loader is None:
        raise RuntimeError(
            "Judge configuration not initialized. "
            "Call initialize_judge_config() first."
        )
    return _loader
