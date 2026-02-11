-- Migration: Backfill remaining NULL task_type values
-- Date: 2026-02-08
-- Fixes: First migration used [Dd] character classes in LIKE patterns,
--   but SQLite LIKE treats brackets as literals. This pass uses explicit
--   case variants instead.
-- Backup: tasks.db.backup-20260208

BEGIN TRANSACTION;

-- ============================================================
-- Phase 1: Specific classifications (most specific first)
-- ============================================================

-- Tests
UPDATE tasks SET task_type = 'test', updated_at = datetime('now')
  WHERE task_type IS NULL
    AND (
      summary LIKE '%test%' OR summary LIKE '%Test%'
      OR summary LIKE '%assertion%'
      OR summary LIKE '%mock%' OR summary LIKE '%Mock%'
      OR summary LIKE '%fixture%'
    );

-- Docs
UPDATE tasks SET task_type = 'docs', updated_at = datetime('now')
  WHERE task_type IS NULL
    AND (
      summary LIKE '%Document%' OR summary LIKE '%document%'
      OR summary LIKE '%README%' OR summary LIKE '%docstring%'
      OR summary LIKE '%documentation%'
      OR summary LIKE '%.md %' OR summary LIKE '%.md'
      OR summary LIKE '%comment%' OR summary LIKE '%Comment%'
      OR summary LIKE '%docs %' OR summary LIKE '%docs/%'
      OR summary LIKE '%ARCHITECTURE%' OR summary LIKE '%METHODOLOGY%'
      OR summary LIKE '%CONTRIBUTING%' OR summary LIKE '%DEPLOYMENT%'
      OR summary LIKE '%PERFORMANCE%'
    );

-- Infrastructure
UPDATE tasks SET task_type = 'infrastructure', updated_at = datetime('now')
  WHERE task_type IS NULL
    AND (
      summary LIKE '%deploy%' OR summary LIKE '%Deploy%'
      OR summary LIKE '%Railway%' OR summary LIKE '%Docker%'
      OR summary LIKE '% CI %' OR summary LIKE '%CI/%'
      OR summary LIKE '%GitHub Actions%'
      OR summary LIKE '%monitor%' OR summary LIKE '%Monitor%'
      OR summary LIKE '%Alembic%'
      OR summary LIKE '%migrat%' OR summary LIKE '%Migrat%'
      OR summary LIKE '%certificate%' OR summary LIKE '%linter%'
      OR summary LIKE '%pre-commit%'
      OR summary LIKE '%Dependabot%'
      OR summary LIKE '%OpenTelemetry%' OR summary LIKE '%OTEL%'
      OR summary LIKE '%Sentry%' OR summary LIKE '%Prometheus%'
      OR summary LIKE '%metrics%' OR summary LIKE '%Metrics%'
      OR summary LIKE '%observability%' OR summary LIKE '%Observability%'
      OR summary LIKE '%log rotation%'
      OR summary LIKE '%merge conflict%'
      OR summary LIKE '%Configure %generator%'
    );

-- Refactor
UPDATE tasks SET task_type = 'refactor', updated_at = datetime('now')
  WHERE task_type IS NULL
    AND (
      summary LIKE '%Refactor%' OR summary LIKE '%refactor%'
      OR summary LIKE '%Rename%' OR summary LIKE '%rename%'
      OR summary LIKE '%Clean up%' OR summary LIKE '%clean up%'
      OR summary LIKE '%Simplif%' OR summary LIKE '%simplif%'
      OR summary LIKE '%Extract%' OR summary LIKE '%extract%'
      OR summary LIKE '%Remove redundant%' OR summary LIKE '%remove redundant%'
      OR summary LIKE '%Reduce duplication%' OR summary LIKE '%reduce duplication%'
      OR summary LIKE '%Consolidate%' OR summary LIKE '%consolidate%'
      OR summary LIKE '%Remove legacy%' OR summary LIKE '%remove legacy%'
      OR summary LIKE '%Remove unused%' OR summary LIKE '%remove unused%'
      OR summary LIKE '%Standardize%' OR summary LIKE '%standardize%'
      OR summary LIKE '%Unify%' OR summary LIKE '%unify%'
      OR summary LIKE '%Optimize%' OR summary LIKE '%optimize%'
      OR summary LIKE '%Clarify%' OR summary LIKE '%clarify%'
      OR summary LIKE '%Derive%' OR summary LIKE '%derive%'
      OR summary LIKE '%Move %to %'
    );

-- Bug
UPDATE tasks SET task_type = 'bug', updated_at = datetime('now')
  WHERE task_type IS NULL
    AND (
      summary LIKE '%bug%' OR summary LIKE '%Bug%'
      OR summary LIKE 'Fix %' OR summary LIKE '%fix %'
      OR summary LIKE '%crash%' OR summary LIKE '%Crash%'
      OR summary LIKE '%race condition%' OR summary LIKE '%memory leak%'
      OR summary LIKE '%error handling%'
      OR summary LIKE '%thread-safety%' OR summary LIKE '%thread safety%'
      OR summary LIKE '%memory growth%'
      OR summary LIKE '%sanitization%'
    );

-- Feature (broad patterns for remaining classifiable tasks)
UPDATE tasks SET task_type = 'feature', updated_at = datetime('now')
  WHERE task_type IS NULL
    AND (
      summary LIKE '%Add %' OR summary LIKE '%add %'
      OR summary LIKE '%Implement%' OR summary LIKE '%implement%'
      OR summary LIKE '%Create%' OR summary LIKE '%create%'
      OR summary LIKE '%Enable%' OR summary LIKE '%enable%'
      OR summary LIKE '%Integrate%' OR summary LIKE '%integrate%'
      OR summary LIKE '%Support%' OR summary LIKE '%support%'
      OR summary LIKE '%Consider%' OR summary LIKE '%consider%'
      OR summary LIKE '%Improve%' OR summary LIKE '%improve%'
      OR summary LIKE '%Enhance%' OR summary LIKE '%enhance%'
      OR summary LIKE '%Make %' OR summary LIKE '%make %'
      OR summary LIKE '%Schedule%' OR summary LIKE '%Localize%'
      OR summary LIKE '%Use %'
      OR summary LIKE '%Update%' OR summary LIKE '%update%'
      OR summary LIKE '%Persist%' OR summary LIKE '%persist%'
      OR summary LIKE '%Distinguish%' OR summary LIKE '%Include%'
      OR summary LIKE '%Evaluate%' OR summary LIKE '%Verify%'
      OR summary LIKE '%Regenerate%'
    );

-- ============================================================
-- Phase 2: Default remaining NULLs to 'feature'
-- ============================================================

UPDATE tasks SET task_type = 'feature', updated_at = datetime('now')
  WHERE task_type IS NULL;

COMMIT;
