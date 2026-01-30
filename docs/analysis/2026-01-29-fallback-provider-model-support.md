# Analysis: Primary and Fallback Provider/Model Configuration

**Date:** 2026-01-29
**Scope:** How to extend the generator configuration to support explicit fallback provider+model pairs, and allow CLI selection of primary vs fallback tier.

## Executive Summary

The current generator configuration (`generators.yaml`) stores a `fallback` field as a bare provider name (e.g., `"openai"`). When the fallback triggers, the code in `generator_config.py:245` returns `(fallback_provider, None)` — meaning no model override, so the provider's hardcoded default is used (e.g., `gpt-4-turbo-preview` for OpenAI). This is inadequate because the best fallback model for a given question type is not necessarily the provider's default model.

The fix requires three coordinated changes:
1. **Config schema** — Extend `generators.yaml` to accept `fallback_model` alongside `fallback`
2. **Config loader** — Update `GeneratorAssignment` and `get_provider_and_model_for_question_type()` to return the fallback model
3. **CLI** — Add a `--provider-tier` argument to `run_generation.py` (and the `/run-generation` skill) that forces primary or fallback selection

## Methodology

- Examined `config/generators.yaml` for current schema
- Examined `app/generator_config.py` for Pydantic models and routing logic
- Examined `app/generator.py` for specialist routing (`_get_specialist_provider`, `_try_fallback_provider`, `generate_batch_async`)
- Examined `app/pipeline.py` for how generation invokes the generator
- Examined `run_generation.py` for CLI argument parsing and main loop
- Examined `config/judges.yaml` for consistency considerations

## Findings

### 1. Config Schema Gap

**File:** `config/generators.yaml`

The current schema for each question type:

```yaml
spatial:
  provider: "google"
  model: "gemini-3-pro-preview"
  rationale: "..."
  fallback: "openai"        # <-- provider only, no model
```

When fallback triggers, the code at `generator_config.py:245` returns:

```python
return (assignment.fallback, None)  # None = provider default model
```

This means spatial's fallback uses `gpt-4-turbo-preview` (OpenAI's hardcoded default) instead of `gpt-5.2` (the actual second-best spatial reasoning model per ARC-AGI-2 benchmarks).

#### Evidence
- `generator_config.py:18-33` — `GeneratorAssignment` Pydantic model has `fallback: Optional[str]` (provider name only)
- `generator_config.py:238-245` — Fallback path explicitly logs "model override not applied" and returns `None` for model
- `app/providers/openai_provider.py:19` — Default model is `gpt-4-turbo-preview`

### 2. Routing Logic

**File:** `app/generator_config.py`

The `get_provider_and_model_for_question_type()` method (lines 204-257) has three tiers:

| Priority | Condition | Returns |
|----------|-----------|---------|
| 1 | Primary provider available | `(provider, model)` |
| 2 | Fallback provider available | `(fallback, None)` ← **gap** |
| 3 | Any available provider | `(any_provider, None)` |

Only tier 1 passes a model override. Tiers 2 and 3 always return `None` for the model.

### 3. Generator Specialist Routing

**File:** `app/generator.py`

The `_get_specialist_provider()` method (lines 267-308) calls `get_provider_and_model_for_question_type()` and passes the result through to `generate_batch_async()` as `(specialist_provider, specialist_model)`. The model override flows correctly through the single-call and parallel generation paths — the plumbing is already there, it just receives `None` for fallback.

The `_try_fallback_provider()` method (lines 310-329) re-calls `_get_specialist_provider()` when a provider fails, which would naturally return the fallback provider+model if the primary's circuit breaker is open.

### 4. CLI Has No Provider Tier Selection

**File:** `run_generation.py`

The CLI has no mechanism to explicitly choose primary vs fallback. The only provider-related parameter is `--types` which filters question types but not provider selection. There is no way to say "generate spatial questions using the fallback provider."

### 5. Judges Config Lacks Fallback Entirely

**File:** `config/judges.yaml`

The judge configuration has no fallback concept at all — each question type has exactly one judge provider+model. This is a separate concern but worth noting for consistency.

## Recommendations

| Priority | Recommendation | Effort | Impact |
|----------|---------------|--------|--------|
| High | Add `fallback_model` to config schema and loader | Small | Fixes the core gap — fallback uses correct model |
| High | Add `--provider-tier` CLI argument | Small | Enables explicit primary/fallback selection for testing |
| Medium | Update `/run-generation` skill definition | Small | Skill stays in sync with CLI capabilities |
| Low | Add fallback to judges.yaml schema | Small | Consistency across generator and judge configs |

### Detailed Recommendations

#### 1. Extend Config Schema

**Problem:** `fallback` is a bare provider name with no associated model.

**Solution:** Add `fallback_model` field to `generators.yaml` and `GeneratorAssignment`.

**Config change (`generators.yaml`):**

```yaml
spatial:
  provider: "google"
  model: "gemini-3-pro-preview"
  rationale: "..."
  fallback: "openai"
  fallback_model: "gpt-5.2"    # NEW
```

**Pydantic model change (`generator_config.py`):**

```python
class GeneratorAssignment(BaseModel):
    provider: str = Field(..., pattern="^(openai|anthropic|google|xai)$")
    model: Optional[str] = Field(None, description="Specific model for this question type")
    rationale: str = Field(..., min_length=1)
    fallback: Optional[str] = Field(None, pattern="^(openai|anthropic|google|xai)$")
    fallback_model: Optional[str] = Field(
        None, description="Specific model to use with the fallback provider"
    )
```

**Routing change (`generator_config.py:238-245`):**

```python
# Try fallback provider with its configured model
if assignment.fallback and assignment.fallback in available_providers:
    logger.warning(
        f"Primary provider '{assignment.provider}' unavailable for "
        f"'{question_type}', using fallback '{assignment.fallback}'"
        + (f" with model '{assignment.fallback_model}'" if assignment.fallback_model else "")
    )
    return (assignment.fallback, assignment.fallback_model)
```

**Files affected:**
- `config/generators.yaml` — Add `fallback_model` to each question type
- `app/generator_config.py` — Add field to `GeneratorAssignment`, update `get_provider_and_model_for_question_type()`
- `tests/test_generator_config.py` — Update tests for new field

#### 2. Add `--provider-tier` CLI Argument

**Problem:** No way to explicitly run generation using the fallback provider for testing or when the primary is known to perform poorly.

**Solution:** Add `--provider-tier` argument to `run_generation.py` that accepts `primary` (default) or `fallback`.

**CLI change (`run_generation.py`):**

```python
parser.add_argument(
    "--provider-tier",
    choices=["primary", "fallback"],
    default="primary",
    help="Which provider tier to use: 'primary' (default) or 'fallback'. "
         "When 'fallback' is selected, uses the fallback provider+model "
         "from generators.yaml instead of the primary.",
)
```

**Implementation approach:**

The cleanest way to implement this is to add a `provider_tier` parameter to `GeneratorConfigLoader.get_provider_and_model_for_question_type()`:

```python
def get_provider_and_model_for_question_type(
    self,
    question_type: str,
    available_providers: list[str],
    provider_tier: str = "primary",    # NEW
) -> tuple[Optional[str], Optional[str]]:
```

When `provider_tier="fallback"`:
- Return `(assignment.fallback, assignment.fallback_model)` if fallback is configured and available
- Fall through to primary if fallback is not configured
- Log which tier is being used

This parameter would be threaded through:
1. `run_generation.py` — Parse `args.provider_tier`, pass to pipeline
2. `app/pipeline.py` — Accept `provider_tier` in generation methods, pass to generator
3. `app/generator.py` — Accept `provider_tier` in `_get_specialist_provider()`, pass to config loader
4. `app/generator_config.py` — Use `provider_tier` to select primary or fallback

**Files affected:**
- `run_generation.py` — Add argument, pass through
- `app/pipeline.py` — Thread parameter through `generate_questions_async()` and `run_generation_job_async()`
- `app/generator.py` — Thread parameter through `_get_specialist_provider()`, `generate_batch_async()`, `generate_batch_single_call_async()`
- `app/generator_config.py` — Accept tier parameter in `get_provider_and_model_for_question_type()`

#### 3. Update `/run-generation` Skill

**Problem:** The skill definition won't know about the new `--provider-tier` argument.

**Solution:** Add the argument to the skill's argument table and command construction.

**Files affected:**
- `.claude/skills/run-generation` — Add `--provider-tier` to arguments table and command examples

#### 4. Update All Fallback Models in Config

**Problem:** Once the schema supports `fallback_model`, each question type needs its fallback model populated.

**Solution:** Update `generators.yaml` with benchmark-informed fallback models:

```yaml
generators:
  math:
    provider: "xai"
    model: "grok-4"
    fallback: "anthropic"
    fallback_model: "claude-sonnet-4-5-20250929"

  logic:
    provider: "anthropic"
    model: "claude-sonnet-4-5-20250929"
    fallback: "openai"
    fallback_model: "gpt-5.2"

  pattern:
    provider: "google"
    model: "gemini-3-pro-preview"
    fallback: "anthropic"
    fallback_model: "claude-opus-4-5-20251101"

  spatial:
    provider: "google"
    model: "gemini-3-pro-preview"
    fallback: "openai"
    fallback_model: "gpt-5.2"

  verbal:
    provider: "anthropic"
    model: "claude-sonnet-4-5-20250929"
    fallback: "openai"
    fallback_model: "gpt-5.2"

  memory:
    provider: "anthropic"
    model: "claude-sonnet-4-5-20250929"
    fallback: "openai"
    fallback_model: "gpt-5.2"
```

## Appendix

### Files Analyzed

| File | Purpose |
|------|---------|
| `config/generators.yaml` | Generator provider/model configuration |
| `config/judges.yaml` | Judge provider/model configuration |
| `app/generator_config.py` | Config loader, Pydantic models, routing logic |
| `app/generator.py` | Question generator with specialist routing |
| `app/pipeline.py` | Generation pipeline orchestration |
| `run_generation.py` | CLI entry point and argument parsing |
| `app/providers/openai_provider.py` | OpenAI provider default model |

### Data Flow: Provider Selection

```
run_generation.py (CLI args)
  → pipeline.run_generation_job_async()
    → pipeline.generate_questions_async()
      → generator.generate_batch_async()
        → generator._get_specialist_provider(question_type)
          → generator_config.get_provider_and_model_for_question_type()
            → Returns (provider, model) or (fallback, None) ← gap
        → generator.generate_batch_single_call_async(provider, model_override)
          → provider.generate_structured_completion_with_usage_async(model_override=model)
```

### Data Flow: With Proposed Changes

```
run_generation.py (--provider-tier=fallback)
  → pipeline.run_generation_job_async(provider_tier="fallback")
    → pipeline.generate_questions_async(provider_tier="fallback")
      → generator.generate_batch_async(provider_tier="fallback")
        → generator._get_specialist_provider(question_type, provider_tier="fallback")
          → generator_config.get_provider_and_model_for_question_type(tier="fallback")
            → Returns (fallback, fallback_model) ← fixed
        → generator.generate_batch_single_call_async(provider, model_override)
          → provider.generate_structured_completion_with_usage_async(model_override=model)
```
