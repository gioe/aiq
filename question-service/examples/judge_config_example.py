"""Example usage of judge configuration system.

This script demonstrates how to:
1. Initialize the judge configuration
2. Get judge models for specific question types
3. Access evaluation criteria and thresholds
"""

import logging
from pathlib import Path

from app import get_judge_config, initialize_judge_config

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Demonstrate judge configuration usage."""
    # Get the path to the configuration file
    config_path = Path(__file__).parent.parent / "config" / "judges.yaml"

    # Initialize the configuration (do this once at application startup)
    logger.info("Initializing judge configuration...")
    initialize_judge_config(config_path)

    # Get the configuration loader
    config = get_judge_config()

    # Example 1: Get judge for a mathematical question
    logger.info("\n=== Example 1: Mathematical Question ===")
    math_judge = config.get_judge_for_question_type("mathematical")
    logger.info("Question Type: mathematical")
    logger.info(f"Model: {math_judge.model}")
    logger.info(f"Provider: {math_judge.provider}")
    logger.info(f"Rationale: {math_judge.rationale}")

    # Example 2: Get judge for a logical reasoning question
    logger.info("\n=== Example 2: Logical Reasoning Question ===")
    logic_judge = config.get_judge_for_question_type("logical_reasoning")
    logger.info("Question Type: logical_reasoning")
    logger.info(f"Model: {logic_judge.model}")
    logger.info(f"Provider: {logic_judge.provider}")
    logger.info(f"Rationale: {logic_judge.rationale}")

    # Example 3: Get all configured question types
    logger.info("\n=== Example 3: All Question Types ===")
    question_types = config.get_all_question_types()
    logger.info(f"Configured question types: {', '.join(question_types)}")

    # Example 4: Get evaluation criteria
    logger.info("\n=== Example 4: Evaluation Criteria ===")
    criteria = config.get_evaluation_criteria()
    logger.info(f"Clarity weight: {criteria.clarity}")
    logger.info(f"Difficulty weight: {criteria.difficulty}")
    logger.info(f"Validity weight: {criteria.validity}")
    logger.info(f"Formatting weight: {criteria.formatting}")
    logger.info(f"Creativity weight: {criteria.creativity}")

    # Example 5: Get minimum judge score threshold
    logger.info("\n=== Example 5: Approval Threshold ===")
    min_score = config.get_min_judge_score()
    logger.info(f"Minimum judge score for approval: {min_score}")

    # Example 6: Unknown question type (falls back to default)
    logger.info("\n=== Example 6: Unknown Question Type ===")
    default_judge = config.get_judge_for_question_type("unknown_type")
    logger.info("Question Type: unknown_type (using default)")
    logger.info(f"Model: {default_judge.model}")
    logger.info(f"Provider: {default_judge.provider}")

    # Example 7: Access the full configuration
    logger.info("\n=== Example 7: Configuration Summary ===")
    full_config = config.config
    logger.info(f"Configuration version: {full_config.version}")
    logger.info(f"Number of configured judges: {len(full_config.judges)}")
    logger.info(f"Default judge model: {full_config.default_judge.model}")


if __name__ == "__main__":
    main()
