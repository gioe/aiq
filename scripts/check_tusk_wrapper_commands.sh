#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TUSK_EXECUTABLE="${TUSK_EXECUTABLE:-tusk}"

if ! command -v "$TUSK_EXECUTABLE" >/dev/null 2>&1; then
  echo "Error: documented tusk executable '$TUSK_EXECUTABLE' is not on PATH." >&2
  exit 1
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

db_path="$tmp_dir/tasks.db"

python3 - "$db_path" <<'PY'
import sqlite3
import sys

db_path = sys.argv[1]
conn = sqlite3.connect(db_path)
conn.executescript(
    """
    CREATE TABLE tasks (
        id INTEGER PRIMARY KEY,
        status TEXT NOT NULL
    );

    CREATE TABLE task_progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER NOT NULL,
        commit_hash TEXT,
        commit_message TEXT,
        files_changed TEXT,
        next_steps TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE skill_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        skill_name TEXT NOT NULL,
        task_id INTEGER,
        started_at TEXT DEFAULT CURRENT_TIMESTAMP,
        ended_at TEXT,
        cost_dollars REAL,
        tokens_in INTEGER,
        tokens_out INTEGER,
        model TEXT,
        metadata TEXT,
        request_count INTEGER
    );

    INSERT INTO tasks (id, status) VALUES (1, 'In Progress');
    """
)
conn.commit()
conn.close()
PY

export TUSK_PROJECT="$REPO_ROOT"
export TUSK_DB="$db_path"

"$TUSK_EXECUTABLE" progress 1 --next-steps wrapper-regression >/dev/null

run_json="$("$TUSK_EXECUTABLE" skill-run start wrapper-regression --task-id 1)"
run_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["run_id"])' <<<"$run_json")"
"$TUSK_EXECUTABLE" skill-run cancel "$run_id" >/dev/null

python3 - "$db_path" "$run_id" <<'PY'
import sqlite3
import sys

db_path = sys.argv[1]
run_id = int(sys.argv[2])
conn = sqlite3.connect(db_path)
progress_count = conn.execute(
    "SELECT COUNT(*) FROM task_progress WHERE task_id = 1 AND next_steps = ?",
    ("wrapper-regression",),
).fetchone()[0]
run = conn.execute(
    "SELECT skill_name, task_id, ended_at FROM skill_runs WHERE id = ?",
    (run_id,),
).fetchone()
conn.close()

if progress_count != 1:
    raise SystemExit("progress command did not record the expected checkpoint")
if run is None:
    raise SystemExit("skill-run start did not record a row")
if not (run[0] == "wrapper-regression" and run[1] == 1 and run[2] is not None):
    raise SystemExit("skill-run start/cancel did not record and close the expected row")
PY

echo "OK: $TUSK_EXECUTABLE supports progress --next-steps and skill-run start/cancel"
