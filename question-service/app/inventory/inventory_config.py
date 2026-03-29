"""Inventory configuration loader.

Loads threshold values from config/inventory.yaml so they can be adjusted
per-environment without a code change.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Union

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "inventory.yaml"


@dataclass
class InventoryConfig:
    """Threshold configuration for inventory health assessment."""

    healthy_threshold: int = 50
    warning_threshold: int = 20
    target_per_stratum: int = 50

    @classmethod
    def from_yaml(
        cls, config_path: Union[str, Path] = _DEFAULT_CONFIG_PATH
    ) -> "InventoryConfig":
        """Load inventory configuration from a YAML file.

        Falls back to dataclass defaults if the file is missing or invalid.
        """
        path = Path(config_path)
        if not path.exists():
            logger.warning(
                f"Inventory config not found at {config_path}, using defaults"
            )
            return cls()

        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            thresholds = (data or {}).get("inventory", {}).get("thresholds", {})

            def _int(key: str, default: int) -> int:
                value = thresholds.get(key, default)
                try:
                    return int(value)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"inventory.thresholds.{key} must be an integer, got {value!r}"
                    ) from exc

            return cls(
                healthy_threshold=_int("healthy_threshold", 50),
                warning_threshold=_int("warning_threshold", 20),
                target_per_stratum=_int("target_per_stratum", 50),
            )
        except Exception as e:
            logger.error(f"Failed to load inventory config from {config_path}: {e}")
            return cls()


# Module-level constants sourced from the config file.
# Exposed here so callers can import them as named defaults.
_config = InventoryConfig.from_yaml()

DEFAULT_HEALTHY_THRESHOLD: int = _config.healthy_threshold
DEFAULT_WARNING_THRESHOLD: int = _config.warning_threshold
DEFAULT_TARGET_QUESTIONS_PER_STRATUM: int = _config.target_per_stratum
