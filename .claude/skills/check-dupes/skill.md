---
name: check-dupes
description: Check for duplicate tasks in the SQLite database before creating new tasks. Use before any INSERT into tasks.db.
allowed-tools: Bash
---

# Check Duplicates Skill

Canonical deduplication gate for `tasks.db`. Run this **before** inserting any task to avoid creating redundant work.

## Usage

```
/check-dupes check "<summary>" [--domain <domain>] [--threshold <float>] [--json]
/check-dupes scan [--domain <domain>] [--status <status>] [--threshold <float>] [--json]
/check-dupes similar <id> [--domain <domain>] [--threshold <float>] [--json]
```

## Commands

### `check "<summary>"`

Pre-insert gate. Checks if a summary is a duplicate of any open task.

```bash
python3 .claude/scripts/check_duplicates.py check "<summary>" --domain <domain>
```

**When to use:** Before every `INSERT INTO tasks` — in `/next-task`, `/analysis-to-tasks`, or any manual task creation.

### `scan`

Find all duplicate pairs among open tasks.

```bash
python3 .claude/scripts/check_duplicates.py scan --status "To Do"
```

**When to use:** During `/groom-backlog` to surface duplicates for cleanup.

### `similar <id>`

Find tasks related to a given task ID (uses a lower threshold of 0.6).

```bash
python3 .claude/scripts/check_duplicates.py similar <id>
```

**When to use:** Exploratory — when investigating whether a task overlaps with other work.

## Interpreting Results

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | No duplicates found — safe to create |
| 1 | Duplicates found — skip or review |
| 2 | Error (task not found, DB error) |

### Thresholds

| Score | Interpretation | Action |
|-------|---------------|--------|
| >= 0.82 | Duplicate | Skip the INSERT |
| 0.60 - 0.82 | Partial overlap | Present to user for decision |
| < 0.60 | New | Safe to create |

The default threshold (0.82) is calibrated so that:
- True duplicates (same task with/without `[Deferred]` prefix) score 1.0
- Generic-prefix false positives ("Add integration test for X" vs "...for Y") peak at ~0.72
- The gap between 0.72 and 0.82 provides a clean separation

### JSON Output

Use `--json` for programmatic consumption:

```json
{
  "duplicates": [
    {"id": 42, "summary": "...", "domain": "iOS", "similarity": 0.95}
  ]
}
```

## Integration Points

This skill is referenced by:
- **`/next-task`** — Steps 13c and 14a (before creating deferred tasks)
- **`/analysis-to-tasks`** — Step 4b (replacing manual LIKE queries)
- **`/groom-backlog`** — Step 2 (scanning for duplicate pairs)

## Examples

```bash
# Pre-insert check
python3 .claude/scripts/check_duplicates.py check "Add error handling for delete account" --domain iOS

# Scan backlog for duplicates
python3 .claude/scripts/check_duplicates.py scan --status "To Do"

# Find tasks related to #42
python3 .claude/scripts/check_duplicates.py similar 42

# JSON output for scripting
python3 .claude/scripts/check_duplicates.py check "unique task" --json
```
