---
name: run-production-script
description: Run a backend Python script against the Railway production environment via SSH. Use when you need to execute scripts in backend/scripts/ against production data.
allowed-tools: Bash
---

# Run Production Script

Executes a backend script against the Railway production environment using `railway ssh`.

## Usage

```
/run-production-script <script-name.py> [args...]
```

## Critical: Correct Invocation Pattern

**Do NOT use `--` before the command.** Using `--` opens an interactive Python REPL instead of running the script.

```bash
railway ssh --service aiq-backend env PYTHONPATH=/home/appuser/.local/lib/python3.11/site-packages:/app python3 /app/backend/scripts/<script>.py [args...]
```

The `env PYTHONPATH=...` prefix is required so Python can locate both installed packages and the app's modules.

## Required PYTHONPATH

```
PYTHONPATH=/home/appuser/.local/lib/python3.11/site-packages:/app
```

This ensures:
- `/home/appuser/.local/lib/python3.11/site-packages` — pip-installed packages
- `/app` — the app root (needed for `from backend.xxx import ...` and `from libs.xxx import ...`)

## Examples

### Audit answer leakage

```bash
railway ssh --service aiq-backend env PYTHONPATH=/home/appuser/.local/lib/python3.11/site-packages:/app python3 /app/backend/scripts/audit_answer_leakage.py
```

### Run IRT calibration

```bash
railway ssh --service aiq-backend env PYTHONPATH=/home/appuser/.local/lib/python3.11/site-packages:/app python3 /app/backend/scripts/run_irt_calibration.py
```

### Run CAT readiness check

```bash
railway ssh --service aiq-backend env PYTHONPATH=/home/appuser/.local/lib/python3.11/site-packages:/app python3 /app/backend/scripts/run_cat_readiness.py
```

## Available Scripts

Located at `backend/scripts/` in the repo:

| Script | Purpose |
|--------|---------|
| `audit_answer_leakage.py` | Check for questions where answer text appears in question body |
| `run_irt_calibration.py` | Run IRT calibration on anchor items |
| `run_cat_readiness.py` | Check CAT readiness metrics |
| `backfill_question_embeddings.py` | Backfill embeddings for existing questions |
| `create_demo_account.py` | Create a demo user account |

## Instructions

When invoked with a script name and optional arguments:

1. Construct the full `railway ssh` command using the pattern above, substituting the script name and any arguments.
2. Run the command with the Bash tool.
3. Display the output to the user.

If the script name is omitted, list available scripts from `backend/scripts/` and ask the user which one to run.
