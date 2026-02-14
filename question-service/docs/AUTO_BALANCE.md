# Auto-Balance Feature

The auto-balance feature (`run_generation.py --auto-balance`) uses inventory analysis to prioritize question generation for underrepresented strata, ensuring even coverage across all 18 strata (6 question types x 3 difficulty levels).

## Flow

### 1. Inventory Analysis

**Source**: `app/inventory/inventory_analyzer.py` -- `InventoryAnalyzer.analyze_inventory()`

The analyzer queries the database for active question counts (`is_active == True`) grouped by `question_type` and `difficulty_level`. It produces a `StratumInventory` for each of the 18 strata with:

| Field | Description |
|-------|-------------|
| `current_count` | Number of active questions in the stratum |
| `target_count` | Target inventory level (default: 50) |
| `deficit` | `max(0, target_count - current_count)` |
| `fill_priority` | `min(1.0, deficit / target_count)` -- higher means more urgent |

The result is an `InventoryAnalysis` containing all strata, total question count, total deficit, and convenience accessors for `strata_below_target`, `critical_strata`, and `strata_by_priority`.

### 2. Generation Plan

**Source**: `app/inventory/inventory_analyzer.py` -- `InventoryAnalyzer.compute_generation_plan()`

The plan allocates a `target_total` number of questions across strata using a three-phase distribution algorithm:

| Phase | Logic |
|-------|-------|
| **Phase 1: Proportional** | Each stratum with a deficit receives `floor(target_total * (stratum_deficit / total_deficit))` questions, capped at its deficit. Strata are processed in priority order (highest `fill_priority` first). |
| **Phase 2: Remaining deficit** | Any unallocated questions are distributed to strata that still have unfilled deficit, in priority order. |
| **Phase 3: Round-robin** | If questions remain after all deficits are filled, they are distributed one-at-a-time across all strata in priority order. |

If `total_deficit == 0` (all strata at or above target), questions are distributed evenly: each stratum gets `floor(target_total / 18)` with the remainder spread across the first N strata.

The output is a `GenerationPlan` with:
- `allocations`: `Dict[Tuple[QuestionType, DifficultyLevel], int]` -- per-stratum counts
- `total_questions`: total allocated
- `get_types_to_generate()`: aggregated per-type totals

### 3. Inventory Alerting

**Source**: `app/observability/alerting.py` -- `InventoryAlertManager.check_and_alert()`

After analysis, the system checks strata against configurable thresholds and sends email alerts for low-inventory strata. Alerting is skipped if `--skip-inventory-alerts` is passed.

| Level | Threshold | Default |
|-------|-----------|---------|
| Healthy | `>= healthy_min` | 50 |
| Warning | `>= critical_min` and `< warning_min` | 20 |
| Critical | `< critical_min` | 5 |

Alerting configuration is loaded from `config/alerting.yaml` (override with `--alerting-config`).

**Cooldown protection** prevents alert spam:

| Mechanism | Default |
|-----------|---------|
| Per-stratum cooldown | 60 minutes |
| Global cooldown | 15 minutes |
| Max alerts per hour | 10 |

### 4. Early Exit

If `generation_plan.total_questions == 0`, the script logs verbose diagnostics and exits with code 0:

```
Auto-balance early exit: all strata at or above target
  Thresholds: healthy=50, warning=20, target_per_stratum=50
  Analyzed 18 strata, N total active questions
  Below target: 0, Critical: 0
```

### 5. Generation Execution

The generation plan's `allocations` dict is passed to the pipeline's balanced generation method. The pipeline iterates over each `(QuestionType, DifficultyLevel) -> count` allocation.

Three execution modes are supported:

| Mode | Flag | Method |
|------|------|--------|
| Sync | (default) | `pipeline.run_balanced_generation_job()` |
| Async | `--async` | `pipeline.run_balanced_generation_job_async()` |
| Batch (Google) | Internal | Used within async when Google provider is active |

After generation, questions proceed through the standard pipeline phases: judge evaluation, salvage (answer repair, difficulty reclassification, regeneration), deduplication, and database insertion.

## Thresholds

| Constant | Default | Description |
|----------|---------|-------------|
| `DEFAULT_HEALTHY_THRESHOLD` | 50 | Minimum count for healthy stratum status |
| `DEFAULT_WARNING_THRESHOLD` | 20 | Below this is critical (alerting) |
| `DEFAULT_TARGET_QUESTIONS_PER_STRATUM` | 50 | Target inventory level per stratum |

## CLI Usage

```
python run_generation.py --auto-balance \
    [--target-per-stratum 100] \
    [--healthy-threshold 50] \
    [--warning-threshold 20] \
    [--skip-inventory-alerts] \
    [--alerting-config ./config/alerting.yaml] \
    [--count 200] \
    [--async] \
    [--provider-tier primary|fallback]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--auto-balance` | off | Enable inventory-aware balanced generation |
| `--target-per-stratum` | 50 | Target questions per stratum |
| `--healthy-threshold` | 50 | Minimum count for healthy status |
| `--warning-threshold` | 20 | Minimum count for warning status |
| `--skip-inventory-alerts` | off | Disable inventory alerting |
| `--alerting-config` | `./config/alerting.yaml` | Path to alerting YAML config |
| `--count` | from config | Total questions to generate (overrides `questions_per_run` setting) |
| `--async` | off | Enable async parallel generation |

**Note**: `--auto-balance` requires a database connection and cannot be used with `--dry-run`.
