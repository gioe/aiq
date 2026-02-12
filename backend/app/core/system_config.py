"""
System configuration helper functions for accessing SystemConfig table.

This module provides convenient get/set functions for system-wide configuration
stored in the database. Configuration values are stored as JSON, allowing
flexible data structures.

Common configuration keys:
- domain_weights: {"pattern": 0.20, "logic": 0.18, ...}
- use_weighted_scoring: {"enabled": false}
- domain_population_stats: {"pattern": {"mean_accuracy": 0.65, "sd_accuracy": 0.18}, ...}
"""
from app.core.datetime_utils import utc_now
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.models import SystemConfig


def get_config(db: Session, key: str, default: Any = None) -> Any:
    """
    Get a configuration value from the SystemConfig table.

    Args:
        db: Database session
        key: Configuration key to retrieve
        default: Default value to return if key doesn't exist

    Returns:
        The configuration value, or default if not found
    """
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if config is None:
        return default
    return config.value


def set_config(db: Session, key: str, value: Any) -> SystemConfig:
    """
    Set a configuration value in the SystemConfig table.

    If the key already exists, updates the value. Otherwise, creates a new entry.

    Args:
        db: Database session
        key: Configuration key to set
        value: Value to store (must be JSON-serializable)

    Returns:
        The SystemConfig instance (new or updated)
    """
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()

    if config is None:
        config = SystemConfig(key=key, value=value, updated_at=utc_now())
        db.add(config)
    else:
        config.value = value
        config.updated_at = utc_now()

    db.commit()
    db.refresh(config)
    return config


def delete_config(db: Session, key: str) -> bool:
    """
    Delete a configuration entry from the SystemConfig table.

    Args:
        db: Database session
        key: Configuration key to delete

    Returns:
        True if the key was found and deleted, False if not found
    """
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if config is None:
        return False

    db.delete(config)
    db.commit()
    return True


def get_all_configs(db: Session) -> dict[str, Any]:
    """
    Get all configuration values from the SystemConfig table.

    Args:
        db: Database session

    Returns:
        Dictionary mapping keys to their values
    """
    configs = db.query(SystemConfig).all()
    return {str(config.key): config.value for config in configs}


def config_exists(db: Session, key: str) -> bool:
    """
    Check if a configuration key exists.

    Args:
        db: Database session
        key: Configuration key to check

    Returns:
        True if the key exists, False otherwise
    """
    return db.query(SystemConfig).filter(SystemConfig.key == key).first() is not None


# Convenience functions for specific configuration keys


def get_domain_weights(db: Session) -> Optional[dict[str, float]]:
    """
    Get the configured domain weights for weighted scoring.

    Args:
        db: Database session

    Returns:
        Dictionary mapping domain names to weights, or None if not configured
    """
    return get_config(db, "domain_weights")


def set_domain_weights(db: Session, weights: dict[str, float]) -> SystemConfig:
    """
    Set the domain weights for weighted scoring.

    Args:
        db: Database session
        weights: Dictionary mapping domain names to weights (should sum to 1.0)

    Returns:
        The SystemConfig instance
    """
    return set_config(db, "domain_weights", weights)


def is_weighted_scoring_enabled(db: Session) -> bool:
    """
    Check if weighted scoring is enabled.

    Args:
        db: Database session

    Returns:
        True if weighted scoring is enabled, False otherwise (default)
    """
    config = get_config(db, "use_weighted_scoring", {"enabled": False})
    return config.get("enabled", False)


def set_weighted_scoring_enabled(db: Session, enabled: bool) -> SystemConfig:
    """
    Enable or disable weighted scoring.

    Args:
        db: Database session
        enabled: Whether to enable weighted scoring

    Returns:
        The SystemConfig instance
    """
    return set_config(db, "use_weighted_scoring", {"enabled": enabled})


def is_cat_enabled(db: Session) -> bool:
    """
    Check if CAT (Computerized Adaptive Testing) is enabled.

    Single-row lookup suitable for the hot path in start_test().

    Args:
        db: Database session

    Returns:
        True if CAT is enabled, False otherwise (default)
    """
    config = get_config(db, "cat_readiness")
    if config is None:
        return False
    return config.get("enabled", False)


def get_cat_readiness_status(db: Session) -> Optional[dict]:
    """
    Get the full CAT readiness evaluation result.

    Args:
        db: Database session

    Returns:
        Dictionary with readiness details, or None if never evaluated
    """
    return get_config(db, "cat_readiness")


def set_cat_readiness(db: Session, result: dict) -> "SystemConfig":
    """
    Persist a CAT readiness evaluation result.

    Args:
        db: Database session
        result: Dictionary with readiness evaluation data

    Returns:
        The SystemConfig instance
    """
    return set_config(db, "cat_readiness", result)


def get_domain_population_stats(db: Session) -> Optional[dict[str, dict[str, float]]]:
    """
    Get domain population statistics for percentile calculations.

    Args:
        db: Database session

    Returns:
        Dictionary mapping domain names to their stats (mean_accuracy, sd_accuracy),
        or None if not configured
    """
    return get_config(db, "domain_population_stats")


def set_domain_population_stats(
    db: Session, stats: dict[str, dict[str, float]]
) -> SystemConfig:
    """
    Set domain population statistics.

    Args:
        db: Database session
        stats: Dictionary mapping domain names to their stats

    Returns:
        The SystemConfig instance
    """
    return set_config(db, "domain_population_stats", stats)


# Async versions for async endpoints


async def async_get_config(db: AsyncSession, key: str, default: Any = None) -> Any:
    """
    Get a configuration value from the SystemConfig table (async version).

    Args:
        db: Async database session
        key: Configuration key to retrieve
        default: Default value to return if key doesn't exist

    Returns:
        The configuration value, or default if not found
    """
    result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    config = result.scalar_one_or_none()
    if config is None:
        return default
    return config.value


async def async_is_weighted_scoring_enabled(db: AsyncSession) -> bool:
    """
    Check if weighted scoring is enabled (async version).

    Args:
        db: Async database session

    Returns:
        True if weighted scoring is enabled, False otherwise (default)
    """
    config = await async_get_config(db, "use_weighted_scoring", {"enabled": False})
    return config.get("enabled", False)


async def async_get_domain_weights(db: AsyncSession) -> Optional[dict[str, float]]:
    """
    Get the configured domain weights for weighted scoring (async version).

    Args:
        db: Async database session

    Returns:
        Dictionary mapping domain names to weights, or None if not configured
    """
    return await async_get_config(db, "domain_weights")


async def async_is_cat_enabled(db: AsyncSession) -> bool:
    """
    Check if CAT (Computerized Adaptive Testing) is enabled (async version).

    Single-row lookup suitable for the hot path in start_test().

    Args:
        db: Async database session

    Returns:
        True if CAT is enabled, False otherwise (default)
    """
    config = await async_get_config(db, "cat_readiness")
    if config is None:
        return False
    return config.get("enabled", False)


async def async_get_domain_population_stats(
    db: AsyncSession,
) -> Optional[dict[str, dict[str, float]]]:
    """
    Get domain population statistics for percentile calculations (async version).

    Args:
        db: Async database session

    Returns:
        Dictionary mapping domain names to their stats (mean_accuracy, sd_accuracy),
        or None if not configured
    """
    return await async_get_config(db, "domain_population_stats")
