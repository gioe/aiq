"""Load model configuration from config/models.yaml.

This module is the single entry point for model IDs and pricing data.
All providers and cost_tracking.py load from here.
"""

from functools import lru_cache
from pathlib import Path
from typing import Dict, List

import yaml

_MODELS_YAML = Path(__file__).parent.parent.parent / "config" / "models.yaml"


@lru_cache(maxsize=1)
def _load_yaml() -> dict:
    with _MODELS_YAML.open() as f:
        return yaml.safe_load(f)


def get_known_models(provider: str) -> List[str]:
    """Return the known model IDs for a provider, ordered newest to oldest."""
    data = _load_yaml()
    return list(data["providers"][provider]["known_models"])


def get_all_pricing() -> Dict[str, Dict[str, float]]:
    """Return a merged pricing dict for all providers (model_id -> {input, output})."""
    data = _load_yaml()
    pricing: Dict[str, Dict[str, float]] = {}
    for provider_data in data["providers"].values():
        pricing.update(provider_data.get("pricing", {}))
    return pricing
