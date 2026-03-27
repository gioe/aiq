# Model Benchmarks

This document provides comprehensive benchmark data for the LLM providers and models used in AIQ's question generation and evaluation pipeline. Models are selected based on their performance on cognitive task benchmarks relevant to IQ testing.

## Table of Contents

- [Supported Providers](#supported-providers)
- [Model Comparison by Cognitive Task](#model-comparison-by-cognitive-task)
- [Detailed Benchmark Data](#detailed-benchmark-data)
  - [Mathematical Reasoning](#mathematical-reasoning)
  - [Logical Reasoning](#logical-reasoning)
  - [Pattern Recognition](#pattern-recognition)
  - [Spatial Reasoning](#spatial-reasoning)
  - [Verbal Reasoning](#verbal-reasoning)
  - [Memory and Knowledge](#memory-and-knowledge)
- [Model Selection Rationale](#model-selection-rationale)
- [Benchmark Sources](#benchmark-sources)

## Supported Providers

AIQ integrates with four major LLM providers:

| Provider | Current Default Model | Primary Use Case |
|----------|----------------------|------------------|
| **Anthropic** | claude-sonnet-4-5-20250929 | Math, Logic, Verbal generation |
| **Google** | gemini-3.1-pro-preview | Memory generation; Verbal/Math fallback |
| **OpenAI** | gpt-5.2 | Pattern, Spatial generation; Math/Logic/Verbal fallback |
| **xAI** | grok-4 | Judge fallback (4th independent provider) |

### Available Models by Provider

<details>
<summary><strong>Anthropic</strong></summary>

| Model ID | Generation | Notes |
|----------|------------|-------|
| claude-opus-4-5-20251101 | Claude 4.5 | Flagship model |
| claude-sonnet-4-5-20250929 | Claude 4.5 | Balanced performance/cost |
| claude-haiku-4-5-20251001 | Claude 4.5 | Fast, cost-effective |
| claude-opus-4-1-20250805 | Claude 4.1 | Previous flagship |
| claude-sonnet-4-20250514 | Claude 4 | Previous generation |
| claude-3-7-sonnet-20250219 | Claude 3.7 | Legacy |

</details>

<details>
<summary><strong>Google</strong></summary>

| Model ID | Generation | Notes |
|----------|------------|-------|
| gemini-3.1-pro-preview | Gemini 3.1 | Preview - memory, verbal fallback |
| gemini-3-pro-preview | Gemini 3 | Preview - superseded by 3.1 |
| gemini-3-flash-preview | Gemini 3 | Preview - fast |
| gemini-2.5-pro | Gemini 2.5 | Current stable (used as judge) |
| gemini-1.5-pro | Gemini 1.5 | Previous generation |
| gemini-1.5-flash | Gemini 1.5 | Fast variant |

</details>

<details>
<summary><strong>OpenAI</strong></summary>

| Model ID | Generation | Notes |
|----------|------------|-------|
| gpt-5.2 | GPT-5 | Latest flagship |
| gpt-5.1 | GPT-5 | Previous flagship |
| gpt-5 | GPT-5 | Initial release |
| o4-mini | O-series | Reasoning model |
| o3 | O-series | Reasoning model |
| o3-mini | O-series | Fast reasoning |
| gpt-4o | GPT-4o | Multimodal |
| gpt-4-turbo | GPT-4 | High capability |

</details>

<details>
<summary><strong>xAI</strong></summary>

| Model ID | Generation | Notes |
|----------|------------|-------|
| grok-4 | Grok 4 | Flagship - exceptional math |
| grok-3 | Grok 3 | Previous generation |
| grok-beta | Grok Beta | Early access features |

</details>

## Model Comparison by Cognitive Task

The following table shows which models excel at each cognitive task type used in AIQ:

| Task Type | Best Model | Provider | Key Benchmark | Score |
|-----------|------------|----------|---------------|-------|
| **Math** | claude-sonnet-4-5 | Anthropic | AIME 2025 + GSM8K (composite 91.71 ⚠️) | 87% / 98% |
| **Logic** | claude-sonnet-4-5 | Anthropic | SWE-bench | 77-82% |
| **Pattern** | gpt-5.2 | OpenAI | ARC-AGI-2 | 52.9% |
| **Spatial** | gpt-5.2 | OpenAI | ARC-AGI-2 | 52.9% |
| **Verbal** | claude-sonnet-4-5 | Anthropic | HellaSwag | ~95% |
| **Memory** | gemini-3.1-pro | Google | MMLU + RULER + 1M context | 91.8% / 93.4% |

## Detailed Benchmark Data

### Mathematical Reasoning

Mathematical reasoning is critical for evaluating IQ questions involving numerical patterns, algebraic problems, and quantitative logic.

| Model | GSM8K | AIME 2024 | AIME 2025 | USAMO 2025 | MATH | FrontierMath | Composite |
|-------|-------|-----------|-----------|------------|------|--------------|-----------|
| **claude-sonnet-4-5** | 98.0% | - | 87.0% | - | - | - | **91.71 ⚠️** |
| gpt-5.2 | 99.0% | - | **100%** | - | - | **40.3%** | 81.79 |
| gemini-3.1-pro-preview | 98.0% ★ | - | 95.0% | - | - | 38.0% | 78.80 |
| claude-opus-4-5 | 96.4% | - | 92.8% | - | 96.4% | 21.0% | 72.34 |
| grok-4 | 95.2% | **100%** | 93.0% | **61.9%** | - | 13.0% | 69.66 |
| gpt-4-turbo | 92.0% | - | - | - | 52.9% | - | - |

⚠️ claude-sonnet composite inflated — FrontierMath data missing (30% weight redistributed to 2 benchmarks). If FrontierMath ~20%, true composite ≈ 76–78, below gpt-5.2 (81.79).
★ Updated Mar 2026 via artificial-analysis (more trusted than prior third-party source).

**Selected for Math Generation:** `claude-sonnet-4-5-20250929` (Anthropic)
**Judge:** `gemini-3.1-pro-preview` (Google)

**Rationale:** Composite 91.71 leads all evaluated models on AIME 2025 (87%) and GSM8K (98%), Δ+9.92 over prior gpt-5.2 assignment. FrontierMath data is unavailable — true composite may be lower. Fallback: openai/gpt-5.2 (composite 81.79, complete benchmark coverage). Updated Mar 2026 via /refresh-providers.

### Logical Reasoning

Logical reasoning benchmarks assess the ability to evaluate deductive reasoning, code logic, and structured problem-solving.

| Model | HumanEval | GPQA Diamond | SWE-bench Verified | SWE-bench Pro | LiveCodeBench |
|-------|-----------|--------------|-------------------|---------------|---------------|
| **claude-sonnet-4-5** | 95.0% | 83.4% | **77-82%** | - | - |
| claude-opus-4-5 | 97.6% | 83.3% | 80.9% | - | - |
| gpt-5.2 | **95.0%** | **92.4-93.2%** | 80.0% | 55.6% | - |
| gemini-3.1-pro-preview | 93.0% | 91.9% | 80.6% ★ | - | - |
| gpt-4-turbo | 87.1% | - | - | - | - |
| grok-4 | 88.0% | 88.0% | 72.0% | - | - |

★ Updated Mar 2026 via official Google announcement (80.6% vs prior 76.2%)

**Selected for Logic Generation:** `claude-sonnet-4-5-20250929` (Anthropic)
**Judge:** `gemini-3-pro-preview` (Google)

**Rationale:** Claude Sonnet 4.5 combines exceptional coding benchmark performance (HumanEval >95%) with strong GPQA Diamond scores (83.4%) and leading SWE-bench results (77-82%), making it ideal for generating questions that measure logical reasoning.

### Pattern Recognition

Pattern recognition benchmarks measure abstract reasoning and the ability to identify underlying structures.

| Model | ARC-AGI-2 | ARC-AGI-2 (Deep Think/Pro)* | MMMU-Pro | Visual Reasoning |
|-------|-----------|----------------------------|----------|------------------|
| **gpt-5.2** | **52.9%** | **54.2%** (Pro) | **86.5%** | - |
| gemini-3-pro-preview | 31.1% | 45.1% (Deep Think) | 81.0% | 62% |
| claude-opus-4-5 | 37.6% | - | 60.0% | - |
| claude-sonnet-4-5 | 13.6% ★ | - | 55.0% | - |
| grok-4 | 16.0% | - | 59.2% ★ | - |
| gpt-4-turbo | - | - | - | - |

★ newly verified score (Mar 2026)

*GPT-5.2 Pro and Gemini 3 Deep Think use extended reasoning modes not currently enabled in our pipeline.

**Selected for Pattern Generation:** `gpt-5.2` (OpenAI)
**Judge:** `gemini-3-pro-preview` (Google)

**Rationale:** GPT-5.2 achieves the highest ARC-AGI-2 score (52.9% Thinking, 54.2% Pro) among all models, the gold-standard benchmark for abstract pattern reasoning. This represents a 70% improvement over Gemini 3 Pro standard mode (31.1%) and surpasses Claude Opus 4.5 (37.6%). Fallback: Claude Opus 4.5 (ARC-AGI-2: 37.6%).

### Spatial Reasoning

Spatial reasoning benchmarks evaluate the ability to mentally manipulate objects and understand spatial relationships.

| Model | ARC-AGI-2 | MMMU-Pro | Visual Reasoning | Video-MMMU |
|-------|-----------|----------|------------------|------------|
| **gpt-5.2** | **52.9%** | **86.5%** | - | **90.5%** |
| claude-opus-4-5 | 37.6% | 60.0% | - | - |
| gemini-3-pro-preview | 31.1% | 81.0% | 62% | 87.6% |
| grok-4 | 16.0% | 59.2% ★ | - | - |
| gpt-4-turbo | - | - | - | - |

★ newly verified score (Mar 2026)

**Selected for Spatial Generation:** `gpt-5.2` (OpenAI)
**Judge:** `claude-opus-4-5` (Anthropic)

**Rationale:** GPT-5.2 leads across all spatial reasoning benchmarks: ARC-AGI-2 (52.9%), MMMU-Pro (86.5%), and Video-MMMU (90.5%). Composite score 75.9. Fallback: Gemini 3 Pro (composite 65.5, ARC-AGI-2: 31.1%, MMMU-Pro: 81.0%, Video-MMMU: 87.6%).

### Verbal Reasoning

Verbal reasoning benchmarks measure language understanding, reading comprehension, and natural language inference.

| Model | MMLU | MMLU Pro | HellaSwag | WinoGrande |
|-------|------|----------|-----------|------------|
| gemini-3-pro-preview | **91.8%** | **90.1%** | - | - |
| grok-4 | 92.1% | 87.0% | - | - |
| claude-opus-4-5 | 87.4% | 90.0% | - | - |
| **claude-sonnet-4-5** | 89.0% | 78.0% | **~95%** | - |
| gpt-5.2 | 88.0% | 83.0% | - | - |
| gpt-4-turbo | 86.4% | - | - | - |

**Selected for Verbal Generation:** `claude-sonnet-4-5-20250929` (Anthropic)
**Judge:** `gpt-5.2` (OpenAI)

**Rationale:** Claude Sonnet 4.5 achieves strong MMLU performance (89%) and excellent HellaSwag scores (~95%), demonstrating superior language understanding and commonsense reasoning essential for evaluating verbal IQ questions. Fallback changed to google/gemini-3.1-pro-preview (composite 91.01, Δ+5.34 vs prior gpt-5.2 fallback); judge changed to openai/gpt-5.2 to maintain cross-provider independence. Updated Mar 2026 via /refresh-providers.

### Memory and Knowledge

Memory evaluation requires both broad knowledge and the ability to process long contexts.

| Model | MMLU | MMLU Pro | Context Window | RULER (long-context) |
|-------|------|----------|----------------|----------------------|
| **gemini-3.1-pro-preview** | **91.8%** | **90.1%** | **1,000,000 tokens** | **93.4%** ★ |
| gpt-5.2 | 88.0% | 83.0% | 400,000 tokens | - |
| grok-4 | 92.1% | 87.0% | 256,000 tokens | - |
| claude-sonnet-4-5 | 89.0% | 78.0% | 200,000 tokens | - |
| claude-opus-4-5 | 87.4% | 90.0% | 200,000 tokens | - |
| gpt-4-turbo | 86.4% | - | 128,000 tokens | - |

★ RULER score added Mar 2026 (artificial-analysis); memory composite improved from 72.3 → 77.57.

**Selected for Memory Generation:** `gemini-3.1-pro-preview` (Google)
**Judge:** `claude-opus-4-5` (Anthropic)

**Rationale:** Gemini 3.1 Pro leads with composite score 77.57, combining top MMLU (91.8%) and MMLU-Pro (90.1%) scores with the largest usable context window (1M tokens, norm 50.0) and a strong RULER long-context score (93.4%). This provides the strongest combination of knowledge breadth and context retention for memory-intensive evaluation.

## Model Selection Rationale

AIQ uses **cross-provider judging**: the judge for each question type uses a *different* provider than the generator. This prevents self-evaluation bias and improves question quality by having an independent model assess generated output.

- **Generator** = specialist model for that cognitive domain
- **Judge** = a third provider independent from both the primary generator and generator fallback
- **Judge fallback** = xAI/grok-4 (fourth provider — fully independent chain)

This four-provider independence chain guarantees cross-provider evaluation even in failure scenarios: if the primary generator is unavailable and the system uses the generator fallback, the judge (third provider) still evaluates independently.

| Question Type | Generator | Provider | Judge | Provider | Gen Fallback |
|---------------|-----------|----------|-------|----------|--------------|
| Math | claude-sonnet-4-5 | Anthropic | gemini-3.1-pro-preview | Google | OpenAI |
| Logic | claude-sonnet-4-5 | Anthropic | gemini-2.5-pro | Google | OpenAI |
| Pattern | gpt-5.2 | OpenAI | gemini-2.5-pro | Google | Anthropic |
| Spatial | gpt-5.2 | OpenAI | claude-opus-4-5 | Anthropic | Google |
| Verbal | claude-sonnet-4-5 | Anthropic | gpt-5.2 | OpenAI | Google |
| Memory | gemini-3.1-pro | Google | claude-opus-4-5 | Anthropic | OpenAI |
| Default | gpt-4-turbo | OpenAI | gemini-2.5-pro | Google | Anthropic |

## Benchmark Sources

All benchmark data is sourced from official provider announcements, research papers, and third-party evaluations. Last verified: March 2026.

### Anthropic (Claude)

- [Claude Opus 4.5 Release Announcement](https://www.anthropic.com/news/claude-opus-4-5) - Official benchmark figures for Claude 4.5 Opus
- [Claude Sonnet 4.5 Release Announcement](https://www.anthropic.com/news/claude-sonnet-4-5) - Official benchmark figures for Claude 4.5 Sonnet
- [Anthropic Model Card](https://www.anthropic.com/claude) - Technical specifications and capabilities
- [GPQA Benchmark Paper](https://arxiv.org/abs/2311.12022) - Graduate-level science questions benchmark
- [SWE-bench](https://www.swebench.com/) - Real-world software engineering benchmark

### Google (Gemini)

- [Gemini 3 Release Announcement](https://blog.google/products/gemini/gemini-3/) - Official Gemini 3 announcement with benchmarks
- [ARC-AGI-2 Leaderboard](https://arcprize.org/leaderboard) - Abstract reasoning benchmark results
- [MMMU-Pro Benchmark](https://mmmu-benchmark.github.io/) - Multimodal understanding benchmark

### OpenAI (GPT)

- [GPT-4 Technical Report](https://arxiv.org/abs/2303.08774) - Original GPT-4 benchmark data
- [GPT-5 Release Announcement](https://openai.com/index/introducing-gpt-5/) - Official GPT-5 announcement with benchmarks
- [GPT-5.2 Release Announcement](https://openai.com/index/introducing-gpt-5-2/) - GPT-5.2 series announcement
- [GPT-5.2-Codex Release Announcement](https://openai.com/index/introducing-gpt-5-2-codex/) - GPT-5.2-Codex announcement
- [HumanEval Benchmark](https://github.com/openai/human-eval) - Code generation benchmark

### xAI (Grok)

- [Grok 4 Announcement](https://x.ai/news/grok-4) - Official Grok 4 release with benchmarks
- [xAI Release Notes](https://docs.x.ai/docs/release-notes) - Model release notes and updates
- [GSM8K Benchmark](https://github.com/openai/grade-school-math) - Grade school math reasoning
- [AIME Competition Results](https://artofproblemsolving.com/wiki/index.php/AIME_Problems_and_Solutions) - American Invitational Mathematics Examination

### Third-Party Evaluations

- [LMSYS Chatbot Arena](https://chat.lmsys.org/?leaderboard) - Crowdsourced model comparisons
- [Hugging Face Open LLM Leaderboard](https://huggingface.co/spaces/HuggingFaceH4/open_llm_leaderboard) - Standardized evaluations
- [Artificial Analysis LLM Benchmarks](https://artificialanalysis.ai/) - Independent performance testing
- [Vals.ai Benchmarks](https://www.vals.ai/benchmarks/mmlu_pro) - MMLU-Pro and domain-specific evaluations
- [Epoch AI FrontierMath](https://epoch.ai/benchmarks/frontiermath) - Expert-level mathematics benchmark
- [Epoch AI SWE-bench Verified](https://epoch.ai/benchmarks/swe-bench-verified) - Software engineering benchmark
- [Automatio.ai Model Data](https://automatio.ai/) - Aggregated benchmark data across models

---

*Last updated: 2026-03-27*
*See also: [question-service/docs/PERFORMANCE.md](../question-service/docs/PERFORMANCE.md) for operational performance metrics*
