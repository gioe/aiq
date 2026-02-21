"""
Tests for SystemConfig model and helper functions.
"""

import pytest
from app.core.datetime_utils import utc_now

from app.models.models import SystemConfig
from app.core.system_config import (
    get_config,
    set_config,
    delete_config,
    get_all_configs,
    config_exists,
    get_domain_weights,
    set_domain_weights,
    is_weighted_scoring_enabled,
    set_weighted_scoring_enabled,
    get_domain_population_stats,
    set_domain_population_stats,
)


class TestSystemConfigModel:
    """Tests for the SystemConfig model."""

    def test_create_config(self, db_session):
        """Test creating a SystemConfig entry."""
        config = SystemConfig(
            key="test_key",
            value={"test": "value"},
            updated_at=utc_now(),
        )
        db_session.add(config)
        db_session.commit()
        db_session.refresh(config)

        assert config.key == "test_key"
        assert config.value == {"test": "value"}
        assert config.updated_at is not None

    def test_primary_key_uniqueness(self, db_session):
        """Test that key is the primary key and must be unique."""
        config1 = SystemConfig(
            key="unique_key",
            value={"first": True},
            updated_at=utc_now(),
        )
        db_session.add(config1)
        db_session.commit()

        # Attempting to add another config with same key should fail
        config2 = SystemConfig(
            key="unique_key",
            value={"second": True},
            updated_at=utc_now(),
        )
        db_session.add(config2)
        with pytest.raises(Exception):  # IntegrityError
            db_session.commit()

    def test_value_accepts_various_json_types(self, db_session):
        """Test that value column accepts various JSON-serializable types."""
        test_cases = [
            ("string_value", "just a string"),
            ("number_value", 42),
            ("float_value", 3.14159),
            ("bool_value", True),
            ("null_value", None),
            ("array_value", [1, 2, 3, "four"]),
            ("nested_object", {"a": {"b": {"c": 1}}}),
        ]

        for key, value in test_cases:
            config = SystemConfig(key=key, value=value, updated_at=utc_now())
            db_session.add(config)

        db_session.commit()

        # Verify all values were stored correctly
        for key, expected_value in test_cases:
            config = (
                db_session.query(SystemConfig).filter(SystemConfig.key == key).first()
            )
            assert config.value == expected_value


class TestGetConfig:
    """Tests for get_config function."""

    def test_get_existing_config(self, db_session):
        """Test getting an existing configuration value."""
        config = SystemConfig(
            key="existing_key",
            value={"data": "test"},
            updated_at=utc_now(),
        )
        db_session.add(config)
        db_session.commit()

        result = get_config(db_session, "existing_key")
        assert result == {"data": "test"}

    def test_get_nonexistent_config_returns_none(self, db_session):
        """Test getting a non-existent key returns None by default."""
        result = get_config(db_session, "nonexistent_key")
        assert result is None

    def test_get_nonexistent_config_returns_default(self, db_session):
        """Test getting a non-existent key returns the provided default."""
        default = {"default": "value"}
        result = get_config(db_session, "nonexistent_key", default=default)
        assert result == default


class TestSetConfig:
    """Tests for set_config function."""

    def test_set_new_config(self, db_session):
        """Test setting a new configuration value."""
        result = set_config(db_session, "new_key", {"new": "value"})

        assert result.key == "new_key"
        assert result.value == {"new": "value"}
        assert result.updated_at is not None

        # Verify it was persisted
        stored = (
            db_session.query(SystemConfig).filter(SystemConfig.key == "new_key").first()
        )
        assert stored is not None
        assert stored.value == {"new": "value"}

    def test_update_existing_config(self, db_session):
        """Test updating an existing configuration value."""
        # Create initial config
        config = SystemConfig(
            key="update_key",
            value={"original": True},
            updated_at=utc_now(),
        )
        db_session.add(config)
        db_session.commit()
        original_updated_at = config.updated_at

        # Update the config
        result = set_config(db_session, "update_key", {"updated": True})

        assert result.key == "update_key"
        assert result.value == {"updated": True}
        assert result.updated_at >= original_updated_at

        # Verify only one entry exists
        count = (
            db_session.query(SystemConfig)
            .filter(SystemConfig.key == "update_key")
            .count()
        )
        assert count == 1


class TestDeleteConfig:
    """Tests for delete_config function."""

    def test_delete_existing_config(self, db_session):
        """Test deleting an existing configuration."""
        config = SystemConfig(
            key="delete_key",
            value={"to_delete": True},
            updated_at=utc_now(),
        )
        db_session.add(config)
        db_session.commit()

        result = delete_config(db_session, "delete_key")
        assert result is True

        # Verify it was deleted
        stored = (
            db_session.query(SystemConfig)
            .filter(SystemConfig.key == "delete_key")
            .first()
        )
        assert stored is None

    def test_delete_nonexistent_config(self, db_session):
        """Test deleting a non-existent configuration returns False."""
        result = delete_config(db_session, "nonexistent_key")
        assert result is False


class TestGetAllConfigs:
    """Tests for get_all_configs function."""

    def test_get_all_configs_empty(self, db_session):
        """Test getting all configs when none exist."""
        result = get_all_configs(db_session)
        assert result == {}

    def test_get_all_configs_multiple(self, db_session):
        """Test getting all configs with multiple entries."""
        configs = [
            SystemConfig(key="key1", value="value1", updated_at=utc_now()),
            SystemConfig(
                key="key2",
                value={"nested": True},
                updated_at=utc_now(),
            ),
            SystemConfig(key="key3", value=[1, 2, 3], updated_at=utc_now()),
        ]
        for config in configs:
            db_session.add(config)
        db_session.commit()

        result = get_all_configs(db_session)
        assert result == {
            "key1": "value1",
            "key2": {"nested": True},
            "key3": [1, 2, 3],
        }


class TestConfigExists:
    """Tests for config_exists function."""

    def test_config_exists_true(self, db_session):
        """Test that config_exists returns True for existing key."""
        config = SystemConfig(key="exists_key", value="exists", updated_at=utc_now())
        db_session.add(config)
        db_session.commit()

        assert config_exists(db_session, "exists_key") is True

    def test_config_exists_false(self, db_session):
        """Test that config_exists returns False for non-existing key."""
        assert config_exists(db_session, "nonexistent_key") is False


class TestDomainWeightsHelpers:
    """Tests for domain weights convenience functions."""

    def test_get_domain_weights_not_set(self, db_session):
        """Test getting domain weights when not configured."""
        result = get_domain_weights(db_session)
        assert result is None

    def test_set_and_get_domain_weights(self, db_session):
        """Test setting and getting domain weights."""
        weights = {
            "pattern": 0.20,
            "logic": 0.18,
            "spatial": 0.16,
            "math": 0.17,
            "verbal": 0.15,
            "memory": 0.14,
        }
        set_domain_weights(db_session, weights)
        result = get_domain_weights(db_session)
        assert result == weights


class TestWeightedScoringHelpers:
    """Tests for weighted scoring enable/disable functions."""

    def test_weighted_scoring_default_disabled(self, db_session):
        """Test that weighted scoring is disabled by default."""
        result = is_weighted_scoring_enabled(db_session)
        assert result is False

    def test_enable_weighted_scoring(self, db_session):
        """Test enabling weighted scoring."""
        set_weighted_scoring_enabled(db_session, True)
        result = is_weighted_scoring_enabled(db_session)
        assert result is True

    def test_disable_weighted_scoring(self, db_session):
        """Test disabling weighted scoring."""
        set_weighted_scoring_enabled(db_session, True)
        set_weighted_scoring_enabled(db_session, False)
        result = is_weighted_scoring_enabled(db_session)
        assert result is False


class TestDomainPopulationStatsHelpers:
    """Tests for domain population stats convenience functions."""

    def test_get_population_stats_not_set(self, db_session):
        """Test getting population stats when not configured."""
        result = get_domain_population_stats(db_session)
        assert result is None

    def test_set_and_get_population_stats(self, db_session):
        """Test setting and getting population stats."""
        stats = {
            "pattern": {"mean_accuracy": 0.65, "sd_accuracy": 0.18},
            "logic": {"mean_accuracy": 0.60, "sd_accuracy": 0.20},
            "spatial": {"mean_accuracy": 0.55, "sd_accuracy": 0.22},
            "math": {"mean_accuracy": 0.70, "sd_accuracy": 0.15},
            "verbal": {"mean_accuracy": 0.68, "sd_accuracy": 0.17},
            "memory": {"mean_accuracy": 0.58, "sd_accuracy": 0.21},
        }
        set_domain_population_stats(db_session, stats)
        result = get_domain_population_stats(db_session)
        assert result == stats
