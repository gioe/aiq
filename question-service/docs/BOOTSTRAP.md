# Initial Inventory Bootstrap

Before production launch, use the bootstrap script to generate initial question inventory across all strata (question type x difficulty combinations).

## Quick Start

Two implementations are available:

**Python Script (Recommended):**
```bash
cd question-service

# Generate full inventory (900 questions target)
python scripts/bootstrap_inventory.py

# Dry run to test without database writes
python scripts/bootstrap_inventory.py --dry-run --count 15 --types math

# Generate specific types only
python scripts/bootstrap_inventory.py --types math,logic,pattern

# Parallel generation (faster, 2 types at once)
python scripts/bootstrap_inventory.py --parallel

# High-throughput parallel with batch API (4 types at once)
python scripts/bootstrap_inventory.py --parallel --max-parallel 4

# Quiet mode for CI/scripts (suppresses terminal output, logs to JSONL)
python scripts/bootstrap_inventory.py --quiet
```

**Bash Script (Legacy):**
```bash
# From project root
./scripts/bootstrap_inventory.sh
./scripts/bootstrap_inventory.sh --dry-run --count 15 --types math
```

## Python vs Bash Script Comparison

| Feature | Python Script | Bash Script |
|---------|--------------|-------------|
| Parallel generation | Yes (`--parallel`) | No |
| Batch API support | Yes (`--no-batch` to disable) | No |
| Progress reporting | Rich terminal UI | Basic output |
| Quiet mode | Yes (`--quiet`) | No |
| JSONL events | Yes | Yes |
| Critical failure alerts | Yes | Yes |

## Options

| Option | Description |
|--------|-------------|
| `--count N` | Questions per type (default: 150, distributed across 3 difficulties) |
| `--types TYPE,...` | Comma-separated types: pattern, logic, spatial, math, verbal, memory |
| `--dry-run` | Generate without database insertion |
| `--no-async` | Disable async mode for troubleshooting |
| `--no-batch` | Disable batch API generation (Python only) |
| `--max-retries N` | Max retries per type (default: 3) |
| `--parallel` | Enable parallel type generation (Python only) |
| `--max-parallel N` | Max concurrent types when parallel (default: 2, Python only) |
| `--quiet` / `-q` | Suppress terminal output, log to JSONL only (Python only) |
| `--verbose` / `-v` | Enable DEBUG logging |

## Target Inventory

The script targets 50 questions per stratum (type x difficulty):

| Dimension | Values | Count |
|-----------|--------|-------|
| Types | pattern, logic, spatial, math, verbal, memory | 6 |
| Difficulties | easy, medium, hard | 3 |
| **Strata** | 6 x 3 | **18** |
| **Target per stratum** | | 50 |
| **Total target** | 18 x 50 | **900** |

Actual inserted questions will be lower than target due to judge evaluation filtering (min score: 0.7) and deduplication against existing questions.

## JSONL Event Logging

Both scripts emit structured events to `logs/bootstrap_events.jsonl` for monitoring:

```json
{"timestamp":"2026-01-26T12:00:00Z","event_type":"script_start","status":"started","total_types":6}
{"timestamp":"2026-01-26T12:00:30Z","event_type":"type_start","status":"started","type":"math"}
{"timestamp":"2026-01-26T12:02:30Z","event_type":"type_end","status":"success","type":"math","generated":150}
{"timestamp":"2026-01-26T12:15:00Z","event_type":"script_end","status":"success","successful_types":6}
```

Event types: `script_start`, `type_start`, `type_end`, `batch_generation_start`, `batch_generation_complete`, `multi_type_failure`, `script_end`

## Critical Failure Alerting

When 3 or more question types fail after retries, both scripts:
1. Emit a `multi_type_failure` event to JSONL
2. Write a sentinel file to `logs/bootstrap_failure.flag`
3. Send an email alert if AlertManager is configured

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All types completed successfully |
| 1 | Some types failed after retries |
| 2 | Configuration or setup error |

## Idempotency

The script is safe to re-run:
- Deduplication prevents duplicate questions from being inserted
- Progress is logged to `logs/bootstrap_YYYYMMDD_HHMMSS.log`
- Events logged to `logs/bootstrap_events.jsonl`
- Check inventory health via `GET /v1/admin/inventory-health`
