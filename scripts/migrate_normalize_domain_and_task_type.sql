-- Migration: Normalize domain and task_type values
-- Date: 2026-02-08
-- Backup: tasks.db.backup-20260208
--
-- Canonical domains:  iOS, Backend, Question Service, Infrastructure, Docs, Data, Testing, Web
-- Canonical task_types: bug, feature, refactor, test, docs, infrastructure

BEGIN TRANSACTION;

-- ============================================================
-- Phase 1: Fix domain inconsistencies (69 rows)
-- ============================================================

UPDATE tasks SET domain = 'Backend', updated_at = datetime('now')
  WHERE domain = 'backend';

UPDATE tasks SET domain = 'iOS', updated_at = datetime('now')
  WHERE domain = 'ios';

UPDATE tasks SET domain = 'Question Service', updated_at = datetime('now')
  WHERE domain = 'question-service';

UPDATE tasks SET domain = 'Infrastructure', updated_at = datetime('now')
  WHERE domain = 'devops';

UPDATE tasks SET domain = 'Docs', updated_at = datetime('now')
  WHERE domain = 'documentation';

-- ============================================================
-- Phase 2: Fix task_type inconsistencies (non-NULL values)
-- ============================================================

-- Direct synonym mappings
UPDATE tasks SET task_type = 'bug', updated_at = datetime('now')
  WHERE task_type IN ('bug_fix', 'Bug');

UPDATE tasks SET task_type = 'refactor', updated_at = datetime('now')
  WHERE task_type IN ('refactoring');

UPDATE tasks SET task_type = 'docs', updated_at = datetime('now')
  WHERE task_type IN ('documentation', 'analysis');

UPDATE tasks SET task_type = 'test', updated_at = datetime('now')
  WHERE task_type IN ('testing');

UPDATE tasks SET task_type = 'infrastructure', updated_at = datetime('now')
  WHERE task_type IN ('deployment', 'monitoring');

UPDATE tasks SET task_type = 'feature', updated_at = datetime('now')
  WHERE task_type IN ('production', 'engineering', 'implementation', 'enhancement', 'Technical');

-- 'deferred' is a status, not a type — classify by summary content
UPDATE tasks SET task_type = 'test', updated_at = datetime('now')
  WHERE task_type = 'deferred'
    AND (summary LIKE '%test%' OR summary LIKE '%Test%');

UPDATE tasks SET task_type = 'refactor', updated_at = datetime('now')
  WHERE task_type = 'deferred';

-- ============================================================
-- Phase 3: Best-effort classify NULLs (keyword matching)
-- Order matters: most specific patterns first.
-- ============================================================

-- Tests: strong signal keywords
UPDATE tasks SET task_type = 'test', updated_at = datetime('now')
  WHERE (task_type IS NULL OR task_type = '')
    AND (
      summary LIKE '%Add%test%'
      OR summary LIKE '%add%test%'
      OR summary LIKE '%Write%test%'
      OR summary LIKE '%test coverage%'
      OR summary LIKE '%test for %'
      OR summary LIKE '%tests for %'
      OR summary LIKE '%snapshot test%'
      OR summary LIKE '%XCTest%'
      OR summary LIKE '%pytest%'
    );

-- Docs: documentation-related
UPDATE tasks SET task_type = 'docs', updated_at = datetime('now')
  WHERE (task_type IS NULL OR task_type = '')
    AND (
      summary LIKE '%[Dd]ocument%'
      OR summary LIKE '%README%'
      OR summary LIKE '%docstring%'
      OR summary LIKE '%[Aa]dd%documentation%'
      OR summary LIKE '%[Aa]dd link to%doc%'
      OR summary LIKE '%CODING_STANDARDS%'
      OR summary LIKE '%Add%guidance%'
      OR summary LIKE '%Add%note to%'
    );

-- Infrastructure: deployment/CI/monitoring
UPDATE tasks SET task_type = 'infrastructure', updated_at = datetime('now')
  WHERE (task_type IS NULL OR task_type = '')
    AND (
      summary LIKE '%[Dd]eploy%'
      OR summary LIKE '%Railway%'
      OR summary LIKE '%Docker%'
      OR summary LIKE '% CI %'
      OR summary LIKE '%CI/%'
      OR summary LIKE '%GitHub Actions%'
      OR summary LIKE '%[Mm]onitor%'
      OR summary LIKE '%Alembic%'
      OR summary LIKE '%[Mm]igrat%'
      OR summary LIKE '%certificate%'
      OR summary LIKE '%linter%'
      OR summary LIKE '%pre-commit%'
    );

-- Refactor: code improvement without new behavior
UPDATE tasks SET task_type = 'refactor', updated_at = datetime('now')
  WHERE (task_type IS NULL OR task_type = '')
    AND (
      summary LIKE '%[Rr]efactor%'
      OR summary LIKE '%[Rr]ename%'
      OR summary LIKE '%[Cc]lean up%'
      OR summary LIKE '%[Ss]implif%'
      OR summary LIKE '%[Ee]xtract%'
      OR summary LIKE '%[Rr]emove redundant%'
      OR summary LIKE '%[Rr]educe duplication%'
      OR summary LIKE '%[Cc]onsolidate%'
      OR summary LIKE '%[Rr]emove legacy%'
      OR summary LIKE '%[Rr]emove unused%'
      OR summary LIKE '%[Bb]reak circular%'
    );

-- Bug: fixes to broken behavior
UPDATE tasks SET task_type = 'bug', updated_at = datetime('now')
  WHERE (task_type IS NULL OR task_type = '')
    AND (
      summary LIKE '%[Bb]ug%'
      OR summary LIKE 'Fix %'
      OR summary LIKE '%fix %'
      OR summary LIKE '%[Cc]rash%'
      OR summary LIKE '%race condition%'
      OR summary LIKE '%memory leak%'
    );

-- Leave remaining NULLs as NULL (not confidently classifiable)

-- ============================================================
-- Phase 4: Add enforcement triggers
-- ============================================================

CREATE TRIGGER validate_domain_insert
BEFORE INSERT ON tasks
FOR EACH ROW
WHEN NEW.domain IS NOT NULL AND NEW.domain NOT IN (
  'iOS', 'Backend', 'Question Service', 'Infrastructure', 'Docs', 'Data', 'Testing', 'Web'
)
BEGIN
  SELECT RAISE(ABORT, 'Invalid domain. Must be one of: iOS, Backend, Question Service, Infrastructure, Docs, Data, Testing, Web');
END;

CREATE TRIGGER validate_domain_update
BEFORE UPDATE OF domain ON tasks
FOR EACH ROW
WHEN NEW.domain IS NOT NULL AND NEW.domain NOT IN (
  'iOS', 'Backend', 'Question Service', 'Infrastructure', 'Docs', 'Data', 'Testing', 'Web'
)
BEGIN
  SELECT RAISE(ABORT, 'Invalid domain. Must be one of: iOS, Backend, Question Service, Infrastructure, Docs, Data, Testing, Web');
END;

CREATE TRIGGER validate_task_type_insert
BEFORE INSERT ON tasks
FOR EACH ROW
WHEN NEW.task_type IS NOT NULL AND NEW.task_type NOT IN (
  'bug', 'feature', 'refactor', 'test', 'docs', 'infrastructure'
)
BEGIN
  SELECT RAISE(ABORT, 'Invalid task_type. Must be one of: bug, feature, refactor, test, docs, infrastructure');
END;

CREATE TRIGGER validate_task_type_update
BEFORE UPDATE OF task_type ON tasks
FOR EACH ROW
WHEN NEW.task_type IS NOT NULL AND NEW.task_type NOT IN (
  'bug', 'feature', 'refactor', 'test', 'docs', 'infrastructure'
)
BEGIN
  SELECT RAISE(ABORT, 'Invalid task_type. Must be one of: bug, feature, refactor, test, docs, infrastructure');
END;

COMMIT;
