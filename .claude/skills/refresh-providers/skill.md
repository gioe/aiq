---
name: refresh-providers
description: Research latest LLM benchmarks and update primary/fallback provider configurations if better models are available.
allowed-tools: Read, Edit, Write, Grep, Glob, WebSearch, WebFetch, Bash
---

# Refresh Providers Skill

Deterministic provider refresh: reads a stored benchmark baseline, fetches new scores, computes weighted composites per domain, and only recommends changes when the composite delta exceeds a configurable threshold.

## Usage

```
/refresh-providers [--dry-run]
```

## Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--dry-run` | No | false | Report findings without making any file changes (including benchmark_scores.yaml) |

## Execution Steps

### Step 1: Read Baseline

Read `question-service/config/benchmark_scores.yaml`. Extract:
- `change_threshold` (default 5.0)
- `source_hierarchy` (ordered list of trusted sources, index 0 = most trusted)
- `models` (list of provider + model ID pairs to evaluate)
- `rubric` (per-domain benchmark names and weights)
- `scores` (per-model, per-benchmark stored values with source and date)

If the file does not exist or fails to parse, **stop execution** and report the error.

### Step 2: Read Current Assignments

Read `question-service/config/generators.yaml` to get the current provider/model assignments per question type. For each of the 6 question types (`math`, `logic`, `pattern`, `spatial`, `verbal`, `memory`), extract:
- `provider`, `model` (primary)
- `fallback`, `fallback_model` (fallback)

### Step 3: Research New Scores

For each model in the `models` list, search for newer benchmark results. Use `WebSearch` with targeted queries:

**Search queries per benchmark:**
- AIME_2025: `"<model>" AIME 2025 score`
- FrontierMath: `"<model>" FrontierMath benchmark score`
- GSM8K: `"<model>" GSM8K score`
- GPQA_Diamond: `"<model>" GPQA Diamond score`
- SWE_bench_Verified: `"<model>" SWE-bench Verified score`
- HumanEval: `"<model>" HumanEval score`
- ARC_AGI_2: `"<model>" ARC-AGI-2 score`
- MMMU_Pro: `"<model>" MMMU-Pro score`
- Video_MMMU: `"<model>" Video-MMMU score`
- MMLU: `"<model>" MMLU score`
- MMLU_Pro: `"<model>" MMLU-Pro score`
- HellaSwag: `"<model>" HellaSwag score`
- context_window_norm: `"<model>" context window size tokens`
- RULER: `"<model>" RULER long-context benchmark`

For each search result that returns a score:

1. **Classify the source** against the `source_hierarchy`. Map the URL/publisher to the closest entry:
   - vals.ai domain → `"vals.ai"`
   - Official model announcement blog/paper from the provider → `"official-announcement"`
   - artificial-analysis.com → `"artificial-analysis"`
   - epochai.org → `"epoch-ai"`
   - arcprize.org → `"arc-prize"`
   - Everything else → `"third-party"`

2. **Decide whether to update** the stored score. An update is allowed only if:
   - The new source rank is **≤** (i.e., equal or more trusted than) the stored source rank in the hierarchy, **OR**
   - The new date is **> 6 months newer** than the stored date, regardless of source rank
   - If the stored value is `null`, any sourced value is accepted

3. **For `context_window_norm`**: Convert raw token count to normalized score: `min(tokens / 2_000_000 × 100, 100)`. Store the normalized value.

4. **Record** the new value, source classification, and date for any accepted updates.

### Step 4: Update Baseline File

Unless `--dry-run` is specified:
- Write all accepted score updates back to `question-service/config/benchmark_scores.yaml`
- Update the `last_updated` field to today's date
- Preserve the file's existing structure, comments, and formatting

Display a **diff summary** showing what changed:
```
Score updates:
  gpt-5.2 / GSM8K: null → 97.5 (source: artificial-analysis, 2026-01-20)
  grok-4 / SWE_bench_Verified: null → 72.0 (source: third-party, 2026-01-18)
```

If no scores changed, report: "No new benchmark data found. Baseline unchanged."

### Step 5: Compute Composites

For each domain in the rubric, for each model, compute a weighted composite score:

```
composite = Σ (weight_i × score_i) / Σ (weight_i where score_i is not null)
```

**Rules:**
- Null scores are **excluded** — their weight redistributes proportionally to benchmarks that have values
- If **> 50%** of a domain's total weight comes from null benchmarks for a model, mark that model as **"insufficient data"** for that domain — it cannot be recommended as primary or fallback

**Example:** For the `math` domain with weights `AIME_2025: 0.40, FrontierMath: 0.30, GSM8K: 0.30`:
- If a model has AIME=92.8 and GSM8K=96.4 but FrontierMath=null:
  - `composite = (0.40 × 92.8 + 0.30 × 96.4) / (0.40 + 0.30) = (37.12 + 28.92) / 0.70 = 94.3`
- The null FrontierMath (weight 0.30) is excluded, and the remaining weights (0.70) are used as the denominator

Present composites in a table per domain:
```
### math composites
| Model                        | AIME_2025 | FrontierMath | GSM8K | Composite |
|------------------------------|-----------|--------------|-------|-----------|
| gpt-5.2                      | 100.0     | 40.3         | —     | 76.1      |
| gemini-3-pro-preview          | 95.0      | —            | —     | 95.0      |
| grok-4                       | 93.0      | —            | 95.2  | 94.1      |
| claude-opus-4-5-20251101      | 92.8      | —            | 96.4  | 94.6      |
| claude-sonnet-4-5-20250929    | 87.0      | —            | —     | 87.0      |
```

### Step 6: Rank and Compare

For each domain:
1. **Rank** models by composite score (descending). Exclude "insufficient data" models.
2. **Recommended primary** = #1 ranked model
3. **Recommended fallback** = highest-ranked model from a **different provider** than the primary
4. **Compare** recommended vs. current assignments from Step 2
5. **Only flag a change** if the composite delta between the recommended model and the current model **exceeds `change_threshold`** (default 5.0 points)

Present a comparison table:
```
| Domain  | Current Primary        | Rec. Primary           | Δ    | Current Fallback       | Rec. Fallback          | Δ    | Change? |
|---------|------------------------|------------------------|------|------------------------|------------------------|------|---------|
| math    | openai/gpt-5.2         | gemini-3-pro-preview   | +3.2 | anthropic/opus-4.5     | grok-4                 | +1.1 | No      |
| logic   | openai/gpt-5.2         | openai/gpt-5.2         | 0.0  | anthropic/opus-4.5     | anthropic/opus-4.5     | 0.0  | No      |
```

A "Change?" of "No" means the delta is ≤ change_threshold OR the recommended model is the same as current.

### Step 7: Present Findings

Display a comprehensive summary:

1. **Score Updates** — Diff from Step 4 (what changed in the baseline)
2. **Composite Tables** — Per-domain tables from Step 5
3. **Change Recommendations** — Comparison table from Step 6, with deltas
4. **Data Gaps** — Models marked "insufficient data" for any domain

If `--dry-run` was specified, stop here and report: "Dry run complete. No files were modified."

### Step 8: Apply Changes (unless --dry-run)

If changes are recommended (delta > threshold), ask the user for confirmation before proceeding.

After confirmation, update files in this order:

#### 8a: Update `generators.yaml`

For each question type where a change is flagged:
- `provider` — New primary provider name
- `model` — New primary model identifier (must match provider's API exactly)
- `rationale` — Updated explanation citing composite score and delta
- `fallback` — New fallback provider name
- `fallback_model` — New fallback model identifier

**IMPORTANT**: Model identifiers must match the exact strings from each provider's API:
- Anthropic: `claude-opus-4-5-20251101`, `claude-sonnet-4-5-20250929`, etc.
- Google: `gemini-3-pro-preview`, `gemini-2.5-pro`, etc.
- OpenAI: `gpt-5.2`, `o4-mini`, etc.
- xAI: `grok-4`, `grok-3`, etc.

Check the "Available Models by Provider" section in `docs/MODEL_BENCHMARKS.md` or the `get_available_models()` method in each provider's implementation for valid identifiers.

#### 8b: Update `judges.yaml`

Apply the same provider/model changes as `generators.yaml`. The judges config must mirror generators per the "specialists-do-both" alignment policy (same model generates and judges each question type).

#### 8c: Update `MODEL_BENCHMARKS.md`

Update the following sections:
- **Supported Providers table** — Update "Current Default Model" and "Primary Use Case" columns
- **Benchmark data tables** — Update scores with latest data found
- **Model Selection Rationale table** — Update selected models and rationale for any changed types
- **Benchmark Sources** — Add any new benchmark sources discovered

### Step 9: Report Results

Provide a final summary:

```markdown
## Provider Refresh Complete

### Changes Applied
| Type | Previous Primary | New Primary | Previous Fallback | New Fallback | Δ Primary | Δ Fallback |
|------|-----------------|------------|------------------|-------------|-----------|------------|
| math | openai/gpt-5.2 | google/gemini-3-pro | openai/gpt-5.2 | xai/grok-4 | +7.2 | +5.8 |

### Files Modified
- `question-service/config/benchmark_scores.yaml` — Updated N score(s)
- `question-service/config/generators.yaml` — Updated N type(s)
- `question-service/config/judges.yaml` — Updated N type(s)
- `docs/MODEL_BENCHMARKS.md` — Updated benchmark data and rationale

### No Changes Needed
- Types where current assignments are still optimal (delta ≤ threshold)

### Notes
- Any caveats about data gaps or close races
```

If no changes were needed, report: "All current provider assignments are still optimal based on latest benchmarks (all deltas ≤ 5.0). No changes made."

## Important Guidelines

1. **Deterministic composites**: Always use the rubric weights and null-redistribution formula. Never invent ad-hoc scoring.
2. **Source hierarchy enforcement**: Never overwrite a higher-ranked source's value with a lower-ranked one (unless the new data is > 6 months newer).
3. **Threshold discipline**: Only flag a change when composite delta > `change_threshold`. Report close races but do not recommend action below threshold.
4. **Use exact model identifiers**: Never guess model IDs. Cross-reference with `MODEL_BENCHMARKS.md` available models lists or provider implementations.
5. **Specialists-do-both policy**: Generators and judges must use the same provider/model per question type. Always update both files together.
6. **Different providers for primary and fallback**: The fallback must be from a different provider than the primary, to provide actual redundancy.
7. **Cite sources**: When presenting benchmark data, note where each score came from and its trust rank.
8. **Preserve config structure**: When editing YAML files, maintain the existing comment headers, formatting, and field ordering.
9. **Ask before applying**: Unless `--dry-run` is specified, always present findings and ask for user confirmation before modifying files.

## Error Handling

- If `benchmark_scores.yaml` cannot be read or parsed, **stop execution** and report the error
- If `WebSearch` fails or returns no results for a benchmark, note the gap and continue with stored data
- If a config file cannot be read, report the error and stop execution
- If model identifiers have changed (e.g., preview suffix removed), flag this for manual verification

## Examples

```
/refresh-providers
```
Read baseline, research benchmarks, compute composites, and apply changes after user confirmation.

```
/refresh-providers --dry-run
```
Read baseline, research benchmarks, compute composites, report findings without modifying any files.
