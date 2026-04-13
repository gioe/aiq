---
name: railway-logs
description: Fetch Railway logs for the backend or question-service, optionally for a specific deployment ID.
allowed-tools: Bash
---

# Railway Logs Skill

Fetches logs from Railway for an AIQ service. Supports optional deployment ID, line count, log type (deploy/build), and log level filtering.

## Usage

```
/railway-logs [deployment_id] [--service <name>] [--lines <n>] [--build] [--level <level>] [--filter <text>]
```

## Arguments

Parse the user's args string for:
- A deployment ID: a UUID-like string (e.g. `7422c95b-c604-46bc-9de4-b7a43e1fd53d`) appearing without a flag
- `--service <name>` — service name (default: linked service — omit flag)
- `--lines <n>` — number of lines to fetch (default: 2000; when `--level` is used, default remains 2000)
- `--build` — show build logs instead of deploy logs
- `--level <level>` — filter by log level using `grep` after fetching (e.g. `error`, `warn`, `info`, `debug`). This is a deterministic string match against the JSON `"level"` field — NOT passed to Railway's search API.
- `--filter <text>` — additional text to grep for after level filtering (plain string match, case-insensitive)

## Implementation

Build and run the `railway logs` command, then apply any post-fetch filtering with `grep`.

```bash
# Base flags always used
FLAGS="--environment production --lines <n>"

# If --build was passed: FLAGS="$FLAGS --build"
# else (default):        FLAGS="$FLAGS --deployment"
# If --service was passed, add: --service <name>
# If a deployment ID was passed (positional), append it at the end

railway logs $FLAGS [| grep -E '"level":"<LEVEL_REGEX>"|- <LEVEL> -|\[<ANSI_CODE>m<LEVEL>'] [| grep -i "<filter>"]
```

### Why grep instead of Railway's --filter

Railway's `--filter` flag routes through their search API which may apply fuzzy/semantic matching. Use grep for reliable, deterministic level filtering.

### Log format variation

Different services use different log formats:

- **backend**: `JSONFormatter` — structured JSON: `{"level": "ERROR", "message": "...", "timestamp": "..."}`
- **question-service / question-generation-cron**: plain-text Python logging with ANSI color codes: `2026-03-28 02:09:05,358 - app.foo - [31mERROR[0m - ...`

Use an extended grep pattern that matches **both** formats:

### Post-fetch grep patterns

The pattern must match the **log level field only**, not the word in message text. Both formats use a fixed position for the level:
- JSON: `"level":"ERROR"`
- Plain-text ANSI: `- [31mERROR[0m -` (the `[` is a literal bracket from the ANSI escape sequence)

| `--level` value | grep pattern |
|-----------------|--------------|
| `error` | `"level":"[Ee][Rr][Rr][Oo][Rr]"\|\- ERROR \-\|\[31mERROR` |
| `warn` | `"level":"[Ww][Aa][Rr][Nn]"\|\- WARNING \-\|\[33mWARNING` |
| `info` | `"level":"[Ii][Nn][Ff][Oo]"\|\- INFO \-\|\[32mINFO` |
| `debug` | `"level":"[Dd][Ee][Bb][Uu][Gg]"\|\- DEBUG \-\|\[36mDEBUG` |

Use `grep -E` (not `-i`) since the ANSI color codes and level names are case-sensitive in these log formats:

```bash
grep -E '"level":"[Ee][Rr][Rr][Oo][Rr]"|- ERROR -|\[31mERROR'
grep -E '"level":"[Ww][Aa][Rr][Nn]"|- WARNING -|\[33mWARNING'
grep -E '"level":"[Ii][Nn][Ff][Oo]"|- INFO -|\[32mINFO'
grep -E '"level":"[Dd][Ee][Bb][Uu][Gg]"|- DEBUG -|\[36mDEBUG'
```

### Defaults

| Option | Default |
|--------|---------|
| service | *(linked service — omit flag)* |
| environment | `production` |
| lines | `2000` |
| log type | deploy (`--deployment`) |
| deployment ID | *(most recent successful)* |

### Examples

```bash
# Latest 2000 deploy logs from production
railway logs --deployment --environment production --lines 2000

# Error logs only (matches both JSON and plain-text formats, level field only)
railway logs --deployment --environment production --lines 2000 | grep -E '"level":"[Ee][Rr][Rr][Oo][Rr]"|- ERROR -|\[31mERROR'

# Warning logs only
railway logs --deployment --environment production --lines 2000 | grep -E '"level":"[Ww][Aa][Rr][Nn]"|- WARNING -|\[33mWARNING'

# Error logs also containing a specific message
railway logs --deployment --environment production --lines 2000 | grep -E '"level":"[Ee][Rr][Rr][Oo][Rr]"|- ERROR -|\[31mERROR' | grep -i "rate limit"

# Build logs for a specific deployment
railway logs --build --environment production --lines 2000 7422c95b-c604-46bc-9de4-b7a43e1fd53d

# Logs from question-service
railway logs --deployment --environment production --lines 2000 --service question-service
```

## Error Handling

- If `railway` CLI is not authenticated, print: `Run: railway login` and stop.
- If the command fails, print the raw error output.
