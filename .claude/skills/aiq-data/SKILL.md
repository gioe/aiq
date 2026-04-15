---
name: aiq-data
description: Run ad-hoc read-only database queries against the AIQ backend database using the aiq-data CLI.
allowed-tools: Bash
---

# aiq-data Skill

Query the AIQ database directly without a running server or auth tokens.

## Usage

```
/aiq-data <subcommand> [options]
```

## Subcommands

| Command | Description | Key Options |
|---------|-------------|-------------|
| `users` | List all users | |
| `inventory` | Question inventory breakdown | `--type`, `--difficulty` |
| `sessions` | List test sessions | `--user EMAIL`, `--limit N` |
| `scores` | List test scores | `--user EMAIL`, `--limit N` |
| `generation` | Question generation run history | `--limit N` |
| `activity` | Sessions per day (recent activity) | `--days N` |
| `sql` | Run arbitrary read-only SQL | `"SELECT ..."` |

All subcommands accept `--json` for JSON output (placed before the subcommand).

Pass `--prod` to query via the production backend API instead of a local database.
Requires `ADMIN_TOKEN` in environment. `BACKEND_URL` defaults to the Railway production URL.

## Invocation

### Local mode (default)

Run from the repo root. The skill activates the backend venv and loads `.env` automatically:

```bash
cd /Users/mattgioe/Desktop/projects/aiq/backend && source venv/bin/activate && set -a && source .env && set +a && python cli/aiq_data.py <subcommand> [options]
```

### Production mode

```bash
cd /Users/mattgioe/Desktop/projects/aiq/backend && source venv/bin/activate && set -a && source .env && set +a && python cli/aiq_data.py --prod <subcommand> [options]
```

## Examples

```bash
# List all users
python cli/aiq_data.py users

# Question inventory filtered by type
python cli/aiq_data.py inventory --type verbal_reasoning

# Recent scores as JSON
python cli/aiq_data.py --json scores --limit 10

# Sessions for a specific user
python cli/aiq_data.py sessions --user user@example.com

# Arbitrary SQL
python cli/aiq_data.py sql "SELECT COUNT(*) FROM questions WHERE is_active = true"

# Activity over last 7 days
python cli/aiq_data.py activity --days 7
```

## Notes

- **Read-only**: The `sql` subcommand rejects write statements (INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE).
- **Lightweight**: Local mode uses its own `pool_size=1` engine, not the pooled app engine.
- Local mode requires `DATABASE_URL` in environment or `backend/.env`.
- **`--prod` mode** requires `ADMIN_TOKEN` in environment. `BACKEND_URL` defaults to `https://aiq-backend-production.up.railway.app`.
