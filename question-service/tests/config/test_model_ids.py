"""Tests that model IDs in judges.yaml and generators.yaml are valid.

Prevents invalid model IDs from reaching production — catches the class of
bug from TASK-143 where 'claude-opus-4-5-20251101' (wrong date suffix) was
only caught at deploy time via a 400 from Anthropic.
"""

from pathlib import Path

import yaml

from app.config.models_config import get_known_models

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"
JUDGES_YAML = CONFIG_DIR / "judges.yaml"
GENERATORS_YAML = CONFIG_DIR / "generators.yaml"

# Known model lists loaded from config/models.yaml — no API keys or provider
# instantiation needed. To add a new model: edit config/models.yaml only.
PROVIDER_MODELS: dict[str, list[str]] = {
    provider: get_known_models(provider)
    for provider in ("anthropic", "openai", "google", "xai")
}


def _extract_model_entries(config: dict) -> list[tuple[str, str, str]]:
    """Return (source_key, provider, model_id) tuples from a loaded YAML dict.

    Handles the top-level section (judges/generators), the default entry,
    and both 'model'/'fallback_model' fields.
    """
    entries: list[tuple[str, str, str]] = []

    # Determine the top-level section key (judges or generators).
    section_key = next((k for k in ("judges", "generators") if k in config), None)

    def _add(label: str, provider: str | None, model: str | None) -> None:
        if provider and model:
            entries.append((label, provider, model))

    if section_key:
        for qtype, cfg in config[section_key].items():
            _add(f"{section_key}.{qtype}.model", cfg.get("provider"), cfg.get("model"))
            _add(
                f"{section_key}.{qtype}.fallback_model",
                cfg.get("fallback"),
                cfg.get("fallback_model"),
            )

    # default_judge / default_generator
    for default_key in ("default_judge", "default_generator"):
        if default_key in config:
            cfg = config[default_key]
            _add(f"{default_key}.model", cfg.get("provider"), cfg.get("model"))
            _add(
                f"{default_key}.fallback_model",
                cfg.get("fallback"),
                cfg.get("fallback_model"),
            )

    return entries


def _load(path: Path) -> dict:
    with path.open() as f:
        return yaml.safe_load(f)


class TestJudgesYamlModelIds:
    """Validate every model ID in judges.yaml against its provider's known list."""

    def test_all_model_ids_are_valid(self):
        config = _load(JUDGES_YAML)
        entries = _extract_model_entries(config)
        assert entries, "No model entries extracted from judges.yaml"

        errors: list[str] = []
        for label, provider, model_id in entries:
            known = PROVIDER_MODELS.get(provider)
            if known is None:
                errors.append(f"{label}: unknown provider '{provider}'")
            elif model_id not in known:
                errors.append(
                    f"{label}: model '{model_id}' not in {provider} known-model list"
                )

        assert not errors, "Invalid model IDs in judges.yaml:\n" + "\n".join(errors)

    def test_invalid_anthropic_model_id_is_caught(self):
        """Regression: invalid date suffix (20251101 vs 20251001) must be detected."""
        bad_model = "claude-opus-4-5-20251101"
        anthropic_models = PROVIDER_MODELS["anthropic"]
        assert bad_model not in anthropic_models, (
            f"Expected '{bad_model}' to be absent from anthropic known-model list — "
            "it was the invalid ID that triggered TASK-143"
        )


class TestGeneratorsYamlModelIds:
    """Validate every model ID in generators.yaml against its provider's known list."""

    def test_all_model_ids_are_valid(self):
        config = _load(GENERATORS_YAML)
        entries = _extract_model_entries(config)
        assert entries, "No model entries extracted from generators.yaml"

        errors: list[str] = []
        for label, provider, model_id in entries:
            known = PROVIDER_MODELS.get(provider)
            if known is None:
                errors.append(f"{label}: unknown provider '{provider}'")
            elif model_id not in known:
                errors.append(
                    f"{label}: model '{model_id}' not in {provider} known-model list"
                )

        assert not errors, "Invalid model IDs in generators.yaml:\n" + "\n".join(errors)
