# Model Benchmarks

This document records the model choices used by AIQ's question generation,
judging, fallback, pricing, and backend benchmark paths.

**Last reviewed:** 2026-04-26

The current production models, judge assignments, provider audit, and pricing
sections below are the authoritative April 2026 audit. Historical benchmark
tables later in this document are retained as external evidence, not as current
production routing.

## Current Production Models

| Area | Provider | Model ID | Notes |
|------|----------|----------|-------|
| Math generator | Anthropic | `claude-sonnet-4-5-20250929` | Kept as primary from the March 2026 domain routing update. |
| Math generator fallback | OpenAI | `gpt-5.5` | Upgraded from `gpt-5.2`; OpenAI announced API availability on 2026-04-24. |
| Logic generator | Anthropic | `claude-sonnet-4-5-20250929` | Kept as primary from the March 2026 domain routing update. |
| Logic generator fallback | OpenAI | `gpt-5.5` | Upgraded from `gpt-5.2`. |
| Pattern generator | OpenAI | `gpt-5.5` | Upgraded from `gpt-5.2`; keep OpenAI primary pending an AIQ bakeoff. |
| Pattern generator fallback | Anthropic | `claude-opus-4-7` | Upgraded from `claude-opus-4-6`. |
| Spatial generator | OpenAI | `gpt-5.5` | Upgraded from `gpt-5.2`; keep OpenAI primary pending an AIQ bakeoff. |
| Spatial generator fallback | Google | `gemini-2.5-pro` | Unchanged. |
| Verbal generator | Anthropic | `claude-sonnet-4-5-20250929` | Unchanged. |
| Verbal generator fallback | Google | `gemini-3.1-pro-preview` | Unchanged; no Google replacement was applied without live validation. |
| Memory generator | Google | `gemini-3.1-pro-preview` | Unchanged; no Google replacement was applied without live validation. |
| Memory generator fallback | OpenAI | `gpt-5.5` | Upgraded from `gpt-5.2`. |
| Default generator | OpenAI | `gpt-5.5` | Upgraded from legacy `gpt-4-turbo`. |
| Default generator fallback | Anthropic | `claude-sonnet-4-5-20250929` | Unchanged. |

## Judge Models

AIQ uses cross-provider judging: each judge should use a different provider
from both the primary generator and the generator fallback whenever the active
provider set allows it.

| Question Type | Judge Provider | Judge Model | Judge Fallback |
|---------------|----------------|-------------|----------------|
| Math | Google | `gemini-3.1-pro-preview` | Anthropic / `claude-opus-4-7` |
| Logic | Google | `gemini-2.5-pro` | Anthropic / `claude-opus-4-7` |
| Pattern | Google | `gemini-2.5-pro` | Anthropic / `claude-opus-4-7` |
| Spatial | Anthropic | `claude-opus-4-7` | Google / `gemini-2.5-pro` |
| Verbal | OpenAI | `gpt-5.5` | Anthropic / `claude-opus-4-7` |
| Memory | Anthropic | `claude-opus-4-7` | Google / `gemini-2.5-pro` |
| Default | Google | `gemini-2.5-pro` | Anthropic / `claude-opus-4-7` |

## Provider Audit

### OpenAI

OpenAI published GPT-5.5 on 2026-04-23 and updated the announcement on
2026-04-24 to say `gpt-5.5` and `gpt-5.5-pro` are available in the API.
The same page lists `gpt-5.5` at $5 per 1M input tokens and $30 per 1M
output tokens, and `gpt-5.5-pro` at $30 / $180. GPT-5.5 improves GPT-5.4
on Terminal-Bench 2.0, GDPval, OSWorld-Verified, BrowseComp, FrontierMath,
and CyberGym in OpenAI's published comparison table.

Config impact:

- `gpt-5.2` OpenAI production generator, judge, and fallback assignments were
  upgraded to `gpt-5.5`.
- The default generator was upgraded from legacy `gpt-4-turbo` to `gpt-5.5`.
- `question-service/config/models.yaml` now includes `gpt-5.5`,
  `gpt-5.5-pro`, `gpt-5.2-pro`, and current OpenAI pricing rows.
- Backend LLM benchmark defaults now use `gpt-5.5`.

### Anthropic

Anthropic announced Claude Opus 4.7 on 2026-04-16 and states that developers
can use `claude-opus-4-7` via the Claude API. The product page lists Opus 4.7
pricing at $5 per 1M input tokens and $25 per 1M output tokens. Anthropic
describes Opus 4.7 as an improvement over Opus 4.6 for advanced software
engineering, vision, and complex multi-step tasks.

Config impact:

- Active Opus judge assignments and Opus fallback assignments were upgraded
  from `claude-opus-4-6` to `claude-opus-4-7`.
- `question-service/config/models.yaml` now includes `claude-opus-4-7` and
  its current pricing.
- Backend benchmark cost/display mappings include `claude-opus-4-7`.
- Backend Anthropic benchmark calls avoid assistant-message prefill for
  `claude-opus-4-7`, matching the existing Opus no-prefill behavior.

### Google

Google's Gemini documentation currently documents Gemini 3 Pro Preview as
`gemini-3-pro-preview` and Gemini 3 Flash Preview as `gemini-3-flash-preview`,
with preview models described as usable for production but subject to stricter
limits and deprecation notice. AIQ's active Google routing currently uses
`gemini-3.1-pro-preview` from a prior provider refresh. No Google model ID was
changed in this audit because the task explicitly requires live availability
validation or benchmark evidence before changing Google usage.

Config impact:

- Google active model IDs remain unchanged.
- The docs intentionally record that no Google replacement was applied in this
  review.

## Current Pricing Rows

Pricing is tracked in `question-service/config/models.yaml` and mirrored in
the backend LLM benchmark cost cap table where needed.

| Provider | Model | Input / 1M | Output / 1M |
|----------|-------|------------|-------------|
| OpenAI | `gpt-5.5` | $5.00 | $30.00 |
| OpenAI | `gpt-5.5-pro` | $30.00 | $180.00 |
| OpenAI | `gpt-5.2` | $1.75 | $14.00 |
| OpenAI | `gpt-5.2-pro` | $21.00 | $168.00 |
| OpenAI | `gpt-5.1` | $1.25 | $10.00 |
| OpenAI | `gpt-5` | $1.25 | $10.00 |
| Anthropic | `claude-opus-4-7` | $5.00 | $25.00 |
| Anthropic | `claude-sonnet-4-5-20250929` | $3.00 | $15.00 |
| Google | `gemini-3.1-pro-preview` | $1.25 | $10.00 |
| Google | `gemini-2.5-pro` | $1.25 | $10.00 |

## External Provider Benchmark Evidence

This section restores the detailed public/provider benchmark evidence used by
prior model-selection reviews. These tables are not AIQ backend benchmark
runner output. They combine official provider announcements, public research
benchmarks, and third-party benchmark aggregators, last reviewed in March 2026
unless a row says otherwise.

Some model IDs and selected production routes changed in the April 2026 audit
above. Treat this section as historical evidence for domain fit, not as the
source of truth for current production routing.

### Provider Coverage in Restored Historical Evidence

| Provider | Historical Default Model | Primary Use Case in March 2026 Evidence |
|----------|--------------------------|-----------------------------------------|
| **Anthropic** | `claude-sonnet-4-5-20250929` | Math, logic, verbal generation |
| **Google** | `gemini-3.1-pro-preview` | Memory generation, verbal/math fallback |
| **OpenAI** | `gpt-5.2` | Pattern and spatial generation, math/logic/verbal fallback |
| **xAI** | `grok-4` | Judge fallback before xAI credits were exhausted |

### Historical Model Comparison by Cognitive Task

| Task Type | Best Model in Restored Evidence | Provider | Key Benchmark | Score |
|-----------|---------------------------------|----------|---------------|-------|
| **Math** | `claude-sonnet-4-5` | Anthropic | AIME 2025 + GSM8K, incomplete composite | 87% / 98% |
| **Logic** | `claude-sonnet-4-5` | Anthropic | SWE-bench | 77-82% |
| **Pattern** | `gpt-5.2` | OpenAI | ARC-AGI-2 | 52.9% |
| **Spatial** | `gpt-5.2` | OpenAI | ARC-AGI-2 | 52.9% |
| **Verbal** | `claude-sonnet-4-5` | Anthropic | HellaSwag | ~95% |
| **Memory** | `gemini-3.1-pro-preview` | Google | MMLU + RULER + 1M context | 91.8% / 93.4% |

### Mathematical Reasoning

Mathematical reasoning is critical for evaluating IQ questions involving
numerical patterns, algebraic problems, and quantitative logic.

| Model | GSM8K | AIME 2024 | AIME 2025 | USAMO 2025 | MATH | FrontierMath | Composite |
|-------|-------|-----------|-----------|------------|------|--------------|-----------|
| **claude-sonnet-4-5** | 98.0% | - | 87.0% | - | - | - | **91.71 incomplete** |
| `gpt-5.2` | 99.0% | - | **100%** | - | - | **40.3%** | 81.79 |
| `gemini-3.1-pro-preview` | 98.0% | - | 95.0% | - | - | 38.0% | 78.80 |
| `claude-opus-4-5` | 96.4% | - | 92.8% | - | 96.4% | 21.0% | 72.34 |
| `grok-4` | 95.2% | **100%** | 93.0% | **61.9%** | - | 13.0% | 69.66 |
| `gpt-4-turbo` | 92.0% | - | - | - | 52.9% | - | - |

The Claude Sonnet composite was marked as inflated in the March 2026 review
because FrontierMath data was missing and its 30% weight was redistributed
across two benchmarks. If FrontierMath were approximately 20%, the true
composite would be about 76-78, below `gpt-5.2`.

**Historical selected generator:** `claude-sonnet-4-5-20250929` (Anthropic)
**Historical judge:** `gemini-3.1-pro-preview` (Google)

**Historical rationale:** Claude Sonnet 4.5 led the available March 2026
provider evidence on AIME 2025 and GSM8K, with the caveat above that incomplete
FrontierMath coverage could materially lower its true composite. `gpt-5.2`
remained the fallback because it had complete benchmark coverage.

### Logical Reasoning

Logical reasoning benchmarks assess the ability to evaluate deductive
reasoning, code logic, and structured problem-solving.

| Model | HumanEval | GPQA Diamond | SWE-bench Verified | SWE-bench Pro | LiveCodeBench |
|-------|-----------|--------------|--------------------|---------------|---------------|
| **claude-sonnet-4-5** | 95.0% | 83.4% | **77-82%** | - | - |
| `claude-opus-4-5` | 97.6% | 83.3% | 80.9% | - | - |
| `gpt-5.2` | **95.0%** | **92.4-93.2%** | 80.0% | 55.6% | - |
| `gemini-3.1-pro-preview` | 93.0% | 91.9% | 80.6% | - | - |
| `gpt-4-turbo` | 87.1% | - | - | - | - |
| `grok-4` | 88.0% | 88.0% | 72.0% | - | - |

The Gemini SWE-bench Verified score was updated in March 2026 from Google's
official announcement.

**Historical selected generator:** `claude-sonnet-4-5-20250929` (Anthropic)
**Historical judge:** `gemini-3-pro-preview` (Google)

**Historical rationale:** Claude Sonnet 4.5 combined strong coding benchmark
performance with GPQA Diamond and leading SWE-bench results, making it a good
fit for generating questions that measure logical reasoning.

### Pattern Recognition

Pattern recognition benchmarks measure abstract reasoning and the ability to
identify underlying structures.

| Model | ARC-AGI-2 | ARC-AGI-2 extended mode | MMMU-Pro | Visual Reasoning |
|-------|-----------|-------------------------|----------|------------------|
| **`gpt-5.2`** | **52.9%** | **54.2%** (Pro) | **86.5%** | - |
| `gemini-3-pro-preview` | 31.1% | 45.1% (Deep Think) | 81.0% | 62% |
| `claude-opus-4-5` | 37.6% | - | 60.0% | - |
| `claude-sonnet-4-5` | 13.6% | - | 55.0% | - |
| `grok-4` | 16.0% | - | 59.2% | - |
| `gpt-4-turbo` | - | - | - | - |

`gpt-5.2` Pro and Gemini 3 Deep Think use extended reasoning modes that were
not enabled in the AIQ pipeline when this evidence was reviewed.

**Historical selected generator:** `gpt-5.2` (OpenAI)
**Historical judge:** `gemini-3-pro-preview` (Google)

**Historical rationale:** `gpt-5.2` had the highest ARC-AGI-2 score among the
reviewed models, plus strong MMMU-Pro evidence. Claude Opus 4.5 was the
historical fallback because it was the next strongest provider candidate on
ARC-AGI-2.

### Spatial Reasoning

Spatial reasoning benchmarks evaluate the ability to mentally manipulate
objects and understand spatial relationships.

| Model | ARC-AGI-2 | MMMU-Pro | Visual Reasoning | Video-MMMU |
|-------|-----------|----------|------------------|------------|
| **`gpt-5.2`** | **52.9%** | **86.5%** | - | **90.5%** |
| `claude-opus-4-5` | 37.6% | 60.0% | - | - |
| `gemini-3-pro-preview` | 31.1% | 81.0% | 62% | 87.6% |
| `grok-4` | 16.0% | 59.2% | - | - |
| `gpt-4-turbo` | - | - | - | - |

**Historical selected generator:** `gpt-5.2` (OpenAI)
**Historical judge:** `claude-opus-4-5` (Anthropic)

**Historical rationale:** `gpt-5.2` led the March 2026 spatial evidence across
ARC-AGI-2, MMMU-Pro, and Video-MMMU. Gemini 3 Pro remained the historical
fallback on the strength of MMMU-Pro and Video-MMMU.

### Verbal Reasoning

Verbal reasoning benchmarks measure language understanding, reading
comprehension, and natural language inference.

| Model | MMLU | MMLU Pro | HellaSwag | WinoGrande |
|-------|------|----------|-----------|------------|
| `gemini-3-pro-preview` | **91.8%** | **90.1%** | - | - |
| `grok-4` | 92.1% | 87.0% | - | - |
| `claude-opus-4-5` | 87.4% | 90.0% | - | - |
| **`claude-sonnet-4-5`** | 89.0% | 78.0% | **~95%** | - |
| `gpt-5.2` | 88.0% | 83.0% | - | - |
| `gpt-4-turbo` | 86.4% | - | - | - |

**Historical selected generator:** `claude-sonnet-4-5-20250929` (Anthropic)
**Historical judge:** `gpt-5.2` (OpenAI)

**Historical rationale:** Claude Sonnet 4.5 had strong MMLU performance and
excellent HellaSwag evidence, while the March 2026 update changed verbal
fallback to Google/Gemini and the judge to OpenAI to preserve cross-provider
independence.

### Memory and Knowledge

Memory evaluation requires both broad knowledge and the ability to process long
contexts.

| Model | MMLU | MMLU Pro | Context Window | RULER long-context |
|-------|------|----------|----------------|--------------------|
| **`gemini-3.1-pro-preview`** | **91.8%** | **90.1%** | **1,000,000 tokens** | **93.4%** |
| `gpt-5.2` | 88.0% | 83.0% | 400,000 tokens | - |
| `grok-4` | 92.1% | 87.0% | 256,000 tokens | - |
| `claude-sonnet-4-5` | 89.0% | 78.0% | 200,000 tokens | - |
| `claude-opus-4-5` | 87.4% | 90.0% | 200,000 tokens | - |
| `gpt-4-turbo` | 86.4% | - | 128,000 tokens | - |

The RULER score was added in March 2026 from Artificial Analysis, improving
the memory composite from 72.3 to 77.57 in the historical review.

**Historical selected generator:** `gemini-3.1-pro-preview` (Google)
**Historical judge:** `claude-opus-4-5` (Anthropic)

**Historical rationale:** Gemini 3.1 Pro combined top MMLU/MMLU-Pro scores
with a 1M-token context window and strong RULER evidence, giving it the best
combination of knowledge breadth and context retention in the restored review.

### Historical Cross-Provider Selection Rationale

The March 2026 review used cross-provider judging: the judge for each question
type used a different provider than the generator, and the judge fallback was
intended to remain independent from both the primary generator and generator
fallback when the active provider set allowed it.

| Question Type | Historical Generator | Provider | Historical Judge | Provider | Historical Generator Fallback |
|---------------|----------------------|----------|------------------|----------|-------------------------------|
| Math | `claude-sonnet-4-5` | Anthropic | `gemini-3.1-pro-preview` | Google | OpenAI |
| Logic | `claude-sonnet-4-5` | Anthropic | `gemini-2.5-pro` | Google | OpenAI |
| Pattern | `gpt-5.2` | OpenAI | `gemini-2.5-pro` | Google | Anthropic |
| Spatial | `gpt-5.2` | OpenAI | `claude-opus-4-5` | Anthropic | Google |
| Verbal | `claude-sonnet-4-5` | Anthropic | `gpt-5.2` | OpenAI | Google |
| Memory | `gemini-3.1-pro-preview` | Google | `claude-opus-4-5` | Anthropic | OpenAI |
| Default | `gpt-4-turbo` | OpenAI | `gemini-2.5-pro` | Google | Anthropic |

## AIQ Internal Benchmark Runs

AIQ internal benchmark runs are results produced by the backend LLM benchmark
runner (`POST /v1/admin/llm-benchmark/run`) against AIQ-owned benchmark
question sets. They are distinct from the external provider evidence above.

The April 26, 2026 production benchmark pass used the backend LLM benchmark
runner against the production benchmark tables. The admin API path still
returned `401 Invalid admin token`, so these runs were executed through the
backend runner with production database credentials and provider API keys.

| Run Date (UTC) | Benchmark Set | Session ID(s) | Provider | Model | Result Summary | Notes |
|----------------|---------------|---------------|----------|-------|----------------|-------|
| 2026-04-26 | Stratified production set, 25 questions per run | 96, 97, 98 | OpenAI | `gpt-5.5` | 3 zero-error runs; mean IQ 113.67; 71/75 correct (94.7%); latest run 24/25, IQ 114. | Runner omits `temperature` for GPT-5.5 because the API only accepts the model default. Earlier compatibility-failure sessions 93 and 94 had 25 provider errors each and are excluded. |
| 2026-04-26 | Stratified production set, 25 questions per run | 102, 103, 104 | Anthropic | `claude-opus-4-7` | 3 zero-error runs; mean IQ 115.00; 75/75 correct (100.0%); all runs IQ 115. | Runner omits `temperature` for Claude Opus 4.7 because the API marks it deprecated. Earlier compatibility-failure sessions 99-101 had 25 provider errors each and are excluded. |
| 2026-04-26 | Stratified production set, 25 questions per run | 106 | Google | `gemini-2.5-pro` | 1 zero-error run; 24/25 correct (96.0%); IQ 114. | Clean production rerun after the benchmark runner fix. Earlier partial Google sessions remain excluded from clean coverage metrics. |
| 2026-04-26 | Stratified production set, 25 questions per run | 107 | Google | `gemini-3.1-pro-preview` | 1 zero-error run; 24/25 correct (96.0%); IQ 114. | Clean production rerun after the benchmark runner fix. Earlier partial Google sessions remain excluded from clean coverage metrics. |

Current active-model coverage checked during the same pass:

| Checked Date (UTC) | Provider | Model | Existing Coverage | Result Summary | Notes |
|--------------------|----------|-------|-------------------|----------------|-------|
| 2026-04-26 | Anthropic | `claude-sonnet-4-5-20250929` | 9 completed runs through 2026-04-09; 8 zero-error runs. | Zero-error mean IQ 113.38; 173/186 correct (93.0%). | Coverage exists and is visible in production benchmark tables. |
| 2026-04-26 | Google | `gemini-2.5-pro` | Clean production session 106, plus earlier partial sessions through 2026-04-09. | Clean run scored IQ 114 with 24/25 correct (96.0%). | The clean rerun persisted with zero provider errors after the benchmark runner fix; earlier partial sessions are retained historically but excluded from clean coverage metrics. |
| 2026-04-26 | Google | `gemini-3.1-pro-preview` | Clean production session 107, plus earlier partial sessions through 2026-04-09. | Clean run scored IQ 114 with 24/25 correct (96.0%). | The clean rerun persisted with zero provider errors after the benchmark runner fix; earlier partial sessions are retained historically but excluded from clean coverage metrics. |

April 26 follow-up investigation found the Google errors were not caused by
prompt format, JSON MIME mode, safety filtering, model availability, or quota.
Stored failures were either transient Google 503 high-demand responses or
benchmark-runner read timeouts on reasoning-heavy prompts. The local patched
runner reproduced the slow `gemini-2.5-pro` and `gemini-3.1-pro-preview` cases
without provider errors by using a longer Google timeout, transient retries,
and low Gemini 3 thinking. After deployment, production sessions 106 and 107
confirmed clean persisted Google coverage with zero provider errors.

## Follow-Up Benchmarking

This audit updates provider availability, pricing, stale production IDs, and
AIQ internal benchmark coverage for GPT-5.5 and Claude Opus 4.7. The next
model-quality pass should rerun the current Google candidates after addressing
their response-error rate if a Google model replacement is considered.

## Sources

### April 2026 Current Model Audit Sources

- OpenAI, [Introducing GPT-5.5](https://openai.com/index/introducing-gpt-5-5/)
- OpenAI, [API pricing](https://platform.openai.com/docs/pricing/)
- Anthropic, [Introducing Claude Opus 4.7](https://www.anthropic.com/news/claude-opus-4-7)
- Anthropic, [Claude Opus 4.7 product page](https://www.anthropic.com/claude/opus)
- Google, [Gemini models](https://ai.google.dev/gemini-api/docs/models/gemini)
- Google, [Gemini 3 developer guide](https://ai.google.dev/gemini-api/docs/gemini-3)

### Restored Historical Public Benchmark Sources

Historical benchmark evidence restored from the March 2026 version of this
document. Last reviewed for that evidence set: March 2026.

- Anthropic, [Claude Opus 4.5 Release Announcement](https://www.anthropic.com/news/claude-opus-4-5)
- Anthropic, [Claude Sonnet 4.5 Release Announcement](https://www.anthropic.com/news/claude-sonnet-4-5)
- Anthropic, [Claude model/product page](https://www.anthropic.com/claude)
- Google, [Gemini 3 Release Announcement](https://blog.google/products/gemini/gemini-3/)
- OpenAI, [GPT-4 Technical Report](https://arxiv.org/abs/2303.08774)
- OpenAI, [GPT-5 Release Announcement](https://openai.com/index/introducing-gpt-5/)
- OpenAI, [GPT-5.2 Release Announcement](https://openai.com/index/introducing-gpt-5-2/)
- OpenAI, [GPT-5.2-Codex Release Announcement](https://openai.com/index/introducing-gpt-5-2-codex/)
- xAI, [Grok 4 Announcement](https://x.ai/news/grok-4)
- xAI, [Release notes](https://docs.x.ai/docs/release-notes)
- [GPQA Benchmark Paper](https://arxiv.org/abs/2311.12022)
- [SWE-bench](https://www.swebench.com/)
- [HumanEval Benchmark](https://github.com/openai/human-eval)
- [GSM8K Benchmark](https://github.com/openai/grade-school-math)
- [AIME Problems and Solutions](https://artofproblemsolving.com/wiki/index.php/AIME_Problems_and_Solutions)
- [ARC-AGI-2 Leaderboard](https://arcprize.org/leaderboard)
- [MMMU-Pro Benchmark](https://mmmu-benchmark.github.io/)
- [Artificial Analysis LLM Benchmarks](https://artificialanalysis.ai/)
- [Vals.ai Benchmarks](https://www.vals.ai/benchmarks/mmlu_pro)
- [Epoch AI FrontierMath](https://epoch.ai/benchmarks/frontiermath)
- [Epoch AI SWE-bench Verified](https://epoch.ai/benchmarks/swe-bench-verified)
- [LMSYS Chatbot Arena](https://chat.lmsys.org/?leaderboard)
- [Hugging Face Open LLM Leaderboard](https://huggingface.co/spaces/HuggingFaceH4/open_llm_leaderboard)
- [Automatio.ai Model Data](https://automatio.ai/)
