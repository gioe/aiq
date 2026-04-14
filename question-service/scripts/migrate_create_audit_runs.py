"""Migration: Create the audit_runs table.

Matches the AuditRunModel schema in app/data/db_models.py.
Idempotent — safe to run multiple times (checks IF NOT EXISTS).

Usage:
    DATABASE_URL=postgresql://... python scripts/migrate_create_audit_runs.py
"""

import logging
import os
import sys

from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS audit_runs (
    id              SERIAL PRIMARY KEY,
    started_at      TIMESTAMP NOT NULL,
    completed_at    TIMESTAMP NOT NULL,
    duration_seconds DOUBLE PRECISION,

    -- Audit outcome counters
    scanned          INTEGER NOT NULL DEFAULT 0,
    verified_correct INTEGER NOT NULL DEFAULT 0,
    failed           INTEGER NOT NULL DEFAULT 0,
    deactivated      INTEGER NOT NULL DEFAULT 0,
    skipped          INTEGER NOT NULL DEFAULT 0,
    errors           INTEGER NOT NULL DEFAULT 0,

    -- Cost tracking
    total_cost_usd     DOUBLE PRECISION,
    total_input_tokens  INTEGER,
    total_output_tokens INTEGER,
    cost_by_provider    JSONB
);
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS ix_audit_runs_id ON audit_runs (id);
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
    logger.info("audit_runs table created (or already exists).")


if __name__ == "__main__":
    main()
