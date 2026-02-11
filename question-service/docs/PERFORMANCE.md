# Performance Baseline Documentation

This document establishes baseline performance metrics for the question generation service, including throughput, latency, and cost measurements for each provider and pipeline stage.

## Table of Contents

- [Overview](#overview)
- [Pipeline Stages](#pipeline-stages)
- [Provider Performance](#provider-performance)
- [Latency by Pipeline Stage](#latency-by-pipeline-stage)
- [Cost Analysis](#cost-analysis)
- [Performance Tracking](#performance-tracking)
- [Optimization Recommendations](#optimization-recommendations)

## Overview

The question generation pipeline processes questions through four main stages:

1. **Generation** - LLM creates raw question content
2. **Evaluation** - Judge model assesses question quality
3. **Deduplication** - Embedding-based similarity check
4. **Storage** - Database insertion with embedding persistence

### Current Configuration

| Parameter | Value | Source |
|-----------|-------|--------|
| Questions per run | 50 | `config.py:questions_per_run` |
| Min judge score | 0.7 | `config.py:min_judge_score` |
| Similarity threshold | 0.85 | `config.py:dedup_similarity_threshold` |
| Embedding model | text-embedding-3-small | `config.py:dedup_embedding_model` |
| Retry max attempts | 3 | `config.py:provider_max_retries` |
| Retry base delay | 1.0s | `config.py:provider_retry_base_delay` |
| Retry max delay | 60.0s | `config.py:provider_retry_max_delay` |

## Pipeline Stages

### Stage 1: Generation

Questions are generated across multiple LLM providers in round-robin distribution.

**Parameters:**
- Temperature: 0.8
- Max tokens: 1,500
- Question types: pattern, logic, spatial, math, verbal, memory
- Difficulty distribution: easy (30%), medium (45%), hard (25%)

**Default Models:**

| Provider | Model | Purpose |
|----------|-------|---------|
| OpenAI | gpt-4-turbo-preview | Question generation |
| Anthropic | claude-3-5-sonnet-20241022 | Question generation |
| Google | gemini-1.5-pro | Question generation |
| xAI | grok-4 | Question generation |

### Stage 2: Evaluation (Judge)

Type-specific judge models evaluate questions against five weighted criteria:

| Criterion | Weight | Description |
|-----------|--------|-------------|
| Validity | 0.30 | Valid as an IQ test question |
| Clarity | 0.25 | Clear and unambiguous |
| Difficulty | 0.20 | Appropriate for IQ testing |
| Formatting | 0.15 | Properly formatted with correct answer |
| Creativity | 0.10 | Novel and interesting |

**Judge Model Assignments:**

| Question Type | Provider | Model | Rationale |
|---------------|----------|-------|-----------|
| Math | xAI | grok-4 | GSM8K 95.2%, AIME 2024 100%, USAMO 2025 61.9% |
| Logic | Anthropic | claude-sonnet-4-5-20250929 | HumanEval >95%, GPQA Diamond 83.4%, SWE-bench 77-82% |
| Pattern | Google | gemini-3-pro-preview | ARC-AGI-2 31.1%, GPQA Diamond 91.9%, MMMU-Pro 81.0% |
| Spatial | Google | gemini-3-pro-preview | ARC-AGI-2 31.1% standard mode (Deep Think 45.1% not enabled), MMMU-Pro 81.0% |
| Verbal | Anthropic | claude-sonnet-4-5-20250929 | MMLU 89%, HellaSwag ~95% |
| Memory | Anthropic | claude-sonnet-4-5-20250929 | MMLU 89%, 200K context window |

> **Note:** For comprehensive benchmark data and model selection rationale, see [MODEL_BENCHMARKS.md](../../docs/MODEL_BENCHMARKS.md). That document serves as the authoritative source of truth for all model benchmarks used in AIQ.

**Evaluation Parameters:**
- Temperature: 0.3 (lower for consistency)
- Max tokens: 500

### Stage 3: Deduplication

Two-phase duplicate detection:

1. **Exact Match Check**: SHA-256 hash comparison (case-insensitive)
2. **Semantic Similarity**: Cosine similarity of OpenAI embeddings

**Optimizations:**
- In-memory `EmbeddingCache` with SHA-256 hash keys
- Pre-computed embeddings from database for existing questions
- Cache statistics tracking (hits/misses)

### Stage 4: Storage

PostgreSQL insertion via SQLAlchemy with:
- Full question metadata
- Pre-computed embedding vectors (ARRAY(Float))
- Source LLM tracking

## Provider Performance

### Throughput (Questions per Minute)

Based on observed API response times and rate limits:

| Provider | Model | Est. TPM* | Questions/Min | Notes |
|----------|-------|-----------|---------------|-------|
| OpenAI | gpt-4-turbo-preview | 30,000 | ~15-20 | Higher rate limits on paid tiers |
| Anthropic | claude-3-5-sonnet | 25,000 | ~12-18 | 200K context window |
| Google | gemini-1.5-pro | 32,000 | ~15-20 | Generous free tier |
| xAI | grok-4 | 20,000 | ~10-15 | Newer API, variable limits |

*TPM = Tokens Per Minute (input + output)

### Observed Latency by Provider

Average response times for structured completions:

| Provider | Model | P50 Latency | P95 Latency | P99 Latency |
|----------|-------|-------------|-------------|-------------|
| OpenAI | gpt-4-turbo-preview | 3-5s | 8-12s | 15-20s |
| Anthropic | claude-3-5-sonnet | 4-6s | 10-15s | 20-25s |
| Google | gemini-1.5-pro | 3-5s | 8-12s | 15-20s |
| xAI | grok-4 | 4-7s | 12-18s | 25-30s |

**Note:** Latencies vary significantly based on prompt complexity, output length, and API load.

## Latency by Pipeline Stage

### Per-Question Processing Time

| Stage | Min | Typical | Max | Notes |
|-------|-----|---------|-----|-------|
| Generation | 3s | 5s | 25s | Depends on provider/model |
| Evaluation | 2s | 4s | 15s | Lower max_tokens (500) |
| Deduplication | 0.5s | 1s | 3s | With cache hits |
| Database Insert | 0.05s | 0.1s | 0.5s | Includes embedding storage |
| **Total per question** | 5.5s | 10s | 43s | End-to-end |

### Full Run Duration

For a typical 50-question run:

| Metric | Value | Notes |
|--------|-------|-------|
| Observed duration | ~100-120s | From heartbeat.json |
| Questions generated | 15-25 | Before evaluation |
| Questions approved | 8-15 | After judge filtering |
| Questions inserted | 5-12 | After deduplication |
| Effective throughput | 3-7 q/min | Net new questions to DB |

## Cost Analysis

### Provider Pricing (as of January 2026)

| Provider | Model | Input ($/1M tokens) | Output ($/1M tokens) |
|----------|-------|---------------------|----------------------|
| OpenAI | gpt-4-turbo-preview | $10.00 | $30.00 |
| Anthropic | claude-3-5-sonnet | $3.00 | $15.00 |
| Google | gemini-1.5-pro | $1.25 | $5.00 |
| xAI | grok-4 | $2.00 | $10.00 |
| OpenAI | text-embedding-3-small | $0.02 | N/A |

**Note:** Prices are estimates and may vary. Check provider documentation for current pricing.

### Estimated Token Usage per Question

| Stage | Input Tokens | Output Tokens | Total |
|-------|--------------|---------------|-------|
| Generation | ~500 | ~1,000 | 1,500 |
| Evaluation | ~800 | ~300 | 1,100 |
| Embedding | ~200 | N/A | 200 |

### Cost per Successfully Inserted Question

Assuming 50% approval rate and 20% deduplication rate:

| Provider | Generation Cost | Evaluation Cost | Total per Question |
|----------|-----------------|-----------------|-------------------|
| OpenAI | ~$0.035 | ~$0.017 | ~$0.052 |
| Anthropic | ~$0.017 | ~$0.007 | ~$0.024 |
| Google | ~$0.008 | ~$0.004 | ~$0.012 |
| xAI | ~$0.012 | ~$0.005 | ~$0.017 |
| Embedding | ~$0.000004 | N/A | ~$0.000004 |

**Blended cost per inserted question:** ~$0.03-0.05 (varies by provider mix)

### Monthly Cost Projection

| Run Frequency | Questions/Month | Est. Monthly Cost |
|---------------|-----------------|-------------------|
| 1x daily | ~150-350 | $5-15 |
| 2x daily | ~300-700 | $10-30 |
| 4x daily | ~600-1,400 | $20-60 |

## Performance Tracking

### Metrics Currently Tracked

The `RunSummary` class (`app/run_summary.py`) and observability facade capture:

**Generation Metrics:**
- `questions_requested` - Target count
- `questions_generated` - Successfully generated
- `generation_failures` - Failed generations
- `questions_by_provider` - Per-provider breakdown
- `questions_by_type` - Per-question-type breakdown
- `questions_by_difficulty` - Per-difficulty breakdown

**Evaluation Metrics:**
- `questions_evaluated` - Sent to judge
- `questions_approved` - Passed threshold
- `questions_rejected` - Below threshold
- `evaluation_scores` - Score distribution (min/max/avg)

**Deduplication Metrics:**
- `questions_checked_for_duplicates` - Total checked
- `duplicates_found` - Total removed
- `exact_duplicates` - Hash matches
- `semantic_duplicates` - Embedding similarity matches

**Database Metrics:**
- `questions_inserted` - Successfully stored
- `insertion_failures` - Storage errors

**API Metrics:**
- `total_api_calls` - All provider calls
- `api_calls_by_provider` - Per-provider breakdown

**Retry Metrics:**
- `total_retries` - Retry attempts
- `successful_retries` - Succeeded after retry
- `exhausted_retries` - Max retries exceeded
- `retries_by_provider` - Per-provider breakdown

**Error Classification:**
- `errors_by_category` - network, rate_limit, auth, etc.
- `errors_by_severity` - transient, permanent, critical

### Reporting Destinations

1. **Observability facade**: OpenTelemetry metrics and Sentry error capture
2. **Backend API**: `RunReporter` posts `RunSummary` data to `/v1/admin/generation-runs`
4. **Heartbeat file**: `logs/heartbeat.json` for scheduler monitoring

### Recommended Additional Tracking

To enable more granular performance analysis, consider adding:

1. **Per-stage timing**
   ```python
   stage_durations = {
       "generation": duration_seconds,
       "evaluation": duration_seconds,
       "deduplication": duration_seconds,
       "storage": duration_seconds
   }
   ```

2. **Token counting per request**
   ```python
   token_usage = {
       "provider": "openai",
       "input_tokens": 500,
       "output_tokens": 1000,
       "cost_estimate": 0.035
   }
   ```

3. **Embedding cache performance**
   ```python
   cache_stats = {
       "hits": 150,
       "misses": 10,
       "hit_rate": 0.94
   }
   ```

## Optimization Recommendations

### Short-term (Operational)

1. **Increase cache utilization**: Pre-load embeddings for all existing questions on startup
2. **Batch embedding requests**: Group new questions for batch embedding API calls
3. **Provider failover**: Automatically switch to backup provider on rate limits

### Medium-term (Architectural)

1. **Async generation**: Parallelize question generation across providers
2. **Streaming responses**: Use streaming API where available to reduce TTFB
3. **Smart scheduling**: Run during off-peak hours for better API response times

### Long-term (Strategic)

1. **Model fine-tuning**: Train custom models for question generation
2. **Local embeddings**: Use local embedding models to reduce API costs
3. **Caching layer**: Redis cache for frequently accessed question patterns

## Appendix: Benchmark Methodology

### How to Run Benchmarks

```bash
# Single provider benchmark
python -m app.benchmark --provider openai --questions 10

# All providers benchmark
python -m app.benchmark --all --questions 50

# Custom configuration
python -m app.benchmark \
    --providers openai,anthropic \
    --questions 25 \
    --output benchmarks/$(date +%Y%m%d).json
```

### Benchmark Output Format

```json
{
  "timestamp": "2026-01-21T12:00:00Z",
  "configuration": {
    "questions_per_provider": 10,
    "providers": ["openai", "anthropic", "google", "xai"]
  },
  "results": {
    "openai": {
      "questions_generated": 10,
      "avg_latency_ms": 4500,
      "p95_latency_ms": 8200,
      "total_tokens": 15000,
      "estimated_cost": 0.35
    }
  }
}
```

**Note:** The benchmark script referenced above is a suggested implementation for future development.

---

*Last updated: 2026-01-24*
*Document version: 1.1*
