"""Tests for InventoryConfig YAML loading and fallback behavior."""

import textwrap
from pathlib import Path

from app.inventory.inventory_config import InventoryConfig


class TestInventoryConfig:
    """Tests for InventoryConfig.from_yaml()."""

    def test_valid_yaml_load(self, tmp_path: Path) -> None:
        """Loads thresholds from a well-formed YAML file."""
        config_file = tmp_path / "inventory.yaml"
        config_file.write_text(
            textwrap.dedent(
                """\
                inventory:
                  thresholds:
                    healthy_threshold: 80
                    warning_threshold: 30
                    target_per_stratum: 100
            """
            )
        )

        cfg = InventoryConfig.from_yaml(config_file)

        assert cfg.healthy_threshold == 80
        assert cfg.warning_threshold == 30
        assert cfg.target_per_stratum == 100

    def test_missing_file_falls_back_to_defaults(self, tmp_path: Path) -> None:
        """Returns dataclass defaults when the config file does not exist."""
        cfg = InventoryConfig.from_yaml(tmp_path / "nonexistent.yaml")

        assert cfg.healthy_threshold == 50
        assert cfg.warning_threshold == 20
        assert cfg.target_per_stratum == 50

    def test_malformed_yaml_falls_back_to_defaults(self, tmp_path: Path) -> None:
        """Returns dataclass defaults when the YAML cannot be parsed."""
        config_file = tmp_path / "inventory.yaml"
        config_file.write_text("{ this is not: valid yaml: [")

        cfg = InventoryConfig.from_yaml(config_file)

        assert cfg.healthy_threshold == 50
        assert cfg.warning_threshold == 20
        assert cfg.target_per_stratum == 50

    def test_missing_keys_fall_back_to_defaults(self, tmp_path: Path) -> None:
        """Returns dataclass defaults when the thresholds block is absent."""
        config_file = tmp_path / "inventory.yaml"
        config_file.write_text("inventory: {}\n")

        cfg = InventoryConfig.from_yaml(config_file)

        assert cfg.healthy_threshold == 50
        assert cfg.warning_threshold == 20
        assert cfg.target_per_stratum == 50

    def test_non_integer_value_falls_back_to_defaults(self, tmp_path: Path) -> None:
        """Returns dataclass defaults when a threshold value is not an integer."""
        config_file = tmp_path / "inventory.yaml"
        config_file.write_text(
            textwrap.dedent(
                """\
                inventory:
                  thresholds:
                    healthy_threshold: "not_a_number"
                    warning_threshold: 20
                    target_per_stratum: 50
            """
            )
        )

        cfg = InventoryConfig.from_yaml(config_file)

        assert cfg.healthy_threshold == 50
        assert cfg.warning_threshold == 20
        assert cfg.target_per_stratum == 50
