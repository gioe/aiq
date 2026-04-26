# Model Benchmarks

This document records the model choices used by AIQ's question generation,
judging, fallback, pricing, and backend benchmark paths.

**Last reviewed:** 2026-04-26

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

## Follow-Up Benchmarking

This audit updates provider availability, pricing, and stale production IDs.
It does not claim that GPT-5.5 or Claude Opus 4.7 have been re-benchmarked on
AIQ's own cognitive question set. The next model-quality pass should run the
backend LLM benchmark for at least:

- `gpt-5.5`
- `claude-opus-4-7`
- current Google candidates if a Google model replacement is considered

## Sources

- OpenAI, [Introducing GPT-5.5](https://openai.com/index/introducing-gpt-5-5/)
- OpenAI, [API pricing](https://platform.openai.com/docs/pricing/)
- Anthropic, [Introducing Claude Opus 4.7](https://www.anthropic.com/news/claude-opus-4-7)
- Anthropic, [Claude Opus 4.7 product page](https://www.anthropic.com/claude/opus)
- Google, [Gemini models](https://ai.google.dev/gemini-api/docs/models/gemini)
- Google, [Gemini 3 developer guide](https://ai.google.dev/gemini-api/docs/gemini-3)
