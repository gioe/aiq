"""Migration: Create the pipeline_runs table.

Matches the PipelineRunModel schema in app/data/db_models.py.
Idempotent — safe to run multiple times (checks IF NOT EXISTS).

Usage:
    DATABASE_URL=postgresql://... python scripts/migrate_create_pipeline_runs.py
"""

import logging
import os
import sys

from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id               SERIAL PRIMARY KEY,
    pipeline_type    VARCHAR(50) NOT NULL,
    started_at       TIMESTAMP NOT NULL,
    completed_at     TIMESTAMP NOT NULL,
    duration_seconds DOUBLE PRECISION,

    -- Cost tracking
    total_cost_usd      DOUBLE PRECISION,
    total_input_tokens   INTEGER,
    total_output_tokens  INTEGER,
    cost_by_provider     JSONB,

    -- Pipeline-specific outcome data
    result_summary       JSONB
);
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS ix_pipeline_runs_pipeline_type
    ON pipeline_runs (pipeline_type);
"""


def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable is required.")
        sys.exit(1)

    engine = create_engine(database_url)
    with engine.begin() as conn:
        conn.execute(text(CREATE_TABLE_SQL))
        conn.execute(text(CREATE_INDEX_SQL))
    logger.info("pipeline_runs table created (or already exists).")


if __name__ == "__main__":
    main()
