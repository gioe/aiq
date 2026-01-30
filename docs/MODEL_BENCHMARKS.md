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
| **Anthropic** | claude-sonnet-4-5-20250929 | Logic, Verbal evaluation |
| **Google** | gemini-3-pro-preview | Memory evaluation; Spatial fallback |
| **OpenAI** | gpt-5.2 | Pattern, Spatial evaluation; Math/Logic fallback |
| **xAI** | grok-4 | Mathematical reasoning |

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
| gemini-3-pro-preview | Gemini 3 | Preview - best spatial/pattern |
| gemini-3-flash-preview | Gemini 3 | Preview - fast |
| gemini-2.5-pro | Gemini 2.5 | Current stable |
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
| **Math** | grok-4 | xAI | AIME 2024 | 100% |
| **Logic** | claude-sonnet-4-5 | Anthropic | SWE-bench | 77-82% |
| **Pattern** | gpt-5.2 | OpenAI | ARC-AGI-2 | 52.9% |
| **Spatial** | gpt-5.2 | OpenAI | ARC-AGI-2 | 52.9% |
| **Verbal** | claude-sonnet-4-5 | Anthropic | HellaSwag | ~95% |
| **Memory** | gemini-3-pro | Google | MMLU + 1M context | 91.8% |

## Detailed Benchmark Data

### Mathematical Reasoning

Mathematical reasoning is critical for evaluating IQ questions involving numerical patterns, algebraic problems, and quantitative logic.

| Model | GSM8K | AIME 2024 | AIME 2025 | USAMO 2025 | MATH | FrontierMath |
|-------|-------|-----------|-----------|------------|------|--------------|
| **grok-4** | 95.2% | **100%** | 93.0% | **61.9%** | - | 13.0% |
| **gpt-5.2** | 99.0% | - | **100%** | - | - | **40.3%** |
| claude-opus-4-5 | 96.4% | - | 92.8% | - | 96.4% | 21.0% |
| claude-sonnet-4-5 | 98.0% | - | 87.0% | - | - | - |
| gemini-3-pro-preview | - | - | 95% | - | - | 38.0% |
| gpt-4-turbo | 92.0% | - | - | - | 52.9% | - |

**Selected for Math Evaluation:** `grok-4` (xAI)

**Rationale:** Grok 4 demonstrates world-class mathematical reasoning with a perfect 100% score on AIME 2024 and exceptional 61.9% on USAMO 2025, outperforming competitors on advanced competition mathematics.

### Logical Reasoning

Logical reasoning benchmarks assess the ability to evaluate deductive reasoning, code logic, and structured problem-solving.

| Model | HumanEval | GPQA Diamond | SWE-bench Verified | SWE-bench Pro | LiveCodeBench |
|-------|-----------|--------------|-------------------|---------------|---------------|
| **claude-sonnet-4-5** | >95% | 83.4% | **77-82%** | - | - |
| claude-opus-4-5 | 97.6% | 83.3% | 80.9% | - | - |
| gpt-5.2 | - | **92.4-93.2%** | 80.0% | 55.6% | - |
| gemini-3-pro-preview | - | 91.9% | 76.2% | - | - |
| gpt-4-turbo | 87.1% | - | - | - | - |
| grok-4 | - | 88.0% | 72.0% | - | - |

**Selected for Logic Evaluation:** `claude-sonnet-4-5-20250929` (Anthropic)

**Rationale:** Claude Sonnet 4.5 combines exceptional coding benchmark performance (HumanEval >95%) with strong GPQA Diamond scores (83.4%) and leading SWE-bench results (77-82%), making it ideal for evaluating logical reasoning in IQ questions.

### Pattern Recognition

Pattern recognition benchmarks measure abstract reasoning and the ability to identify underlying structures.

| Model | ARC-AGI-2 | ARC-AGI-2 (Deep Think/Pro)* | MMMU-Pro | Visual Reasoning |
|-------|-----------|----------------------------|----------|------------------|
| **gpt-5.2** | **52.9%** | **54.2%** (Pro) | **86.5%** | - |
| gemini-3-pro-preview | 31.1% | 45.1% (Deep Think) | 81.0% | 62% |
| claude-opus-4-5 | 37.6% | - | 60.0% | - |
| claude-sonnet-4-5 | - | - | 55.0% | - |
| grok-4 | 16.0% | - | - | - |
| gpt-4-turbo | - | - | - | - |

*GPT-5.2 Pro and Gemini 3 Deep Think use extended reasoning modes not currently enabled in our pipeline.

**Selected for Pattern Evaluation:** `gpt-5.2` (OpenAI)

**Rationale:** GPT-5.2 achieves the highest ARC-AGI-2 score (52.9% Thinking, 54.2% Pro) among all models, the gold-standard benchmark for abstract pattern reasoning. This represents a 70% improvement over Gemini 3 Pro standard mode (31.1%) and surpasses Claude Opus 4.5 (37.6%). Fallback: Claude Opus 4.5 (ARC-AGI-2: 37.6%).

### Spatial Reasoning

Spatial reasoning benchmarks evaluate the ability to mentally manipulate objects and understand spatial relationships.

| Model | ARC-AGI-2 | MMMU-Pro | Visual Reasoning | Video-MMMU |
|-------|-----------|----------|------------------|------------|
| **gpt-5.2** | **52.9%** | **86.5%** | - | **90.5%** |
| claude-opus-4-5 | 37.6% | 60.0% | - | - |
| gemini-3-pro-preview | 31.1% | 81.0% | 62% | 87.6% |
| grok-4 | 16.0% | - | - | - |
| gpt-4-turbo | - | - | - | - |

**Selected for Spatial Evaluation:** `gpt-5.2` (OpenAI)

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

**Selected for Verbal Evaluation:** `claude-sonnet-4-5-20250929` (Anthropic)

**Rationale:** Claude Sonnet 4.5 achieves strong MMLU performance (89%) and excellent HellaSwag scores (~95%), demonstrating superior language understanding and commonsense reasoning essential for evaluating verbal IQ questions.

### Memory and Knowledge

Memory evaluation requires both broad knowledge and the ability to process long contexts.

| Model | MMLU | MMLU Pro | Context Window | Long-Context Retrieval |
|-------|------|----------|----------------|----------------------|
| **gemini-3-pro-preview** | **91.8%** | **90.1%** | **1,000,000 tokens** | - |
| gpt-5.2 | 88.0% | 83.0% | 400,000 tokens | - |
| grok-4 | 92.1% | 87.0% | 256,000 tokens | - |
| claude-sonnet-4-5 | 89.0% | 78.0% | 200,000 tokens | - |
| claude-opus-4-5 | 87.4% | 90.0% | 200,000 tokens | - |
| gpt-4-turbo | 86.4% | - | 128,000 tokens | - |

**Selected for Memory Evaluation:** `gemini-3-pro-preview` (Google)

**Rationale:** Gemini 3 Pro leads with composite score 72.3, combining top MMLU (91.8%) and MMLU-Pro (90.1%) scores with the largest usable context window (1M tokens, norm 50.0). This provides the strongest combination of knowledge breadth and context retention for memory-intensive evaluation.

## Model Selection Rationale

AIQ uses a "specialists-do-both" approach where the same model that excels at a cognitive task type is used for both:
1. **Generating** questions of that type
2. **Evaluating** (judging) questions of that type

This ensures domain expertise is applied consistently throughout the pipeline.

| Question Type | Generator | Judge | Provider | Fallback Provider |
|---------------|-----------|-------|----------|-------------------|
| Math | grok-4 | grok-4 | xAI | OpenAI |
| Logic | claude-sonnet-4-5 | claude-sonnet-4-5 | Anthropic | OpenAI |
| Pattern | gpt-5.2 | gpt-5.2 | OpenAI | Anthropic |
| Spatial | gpt-5.2 | gpt-5.2 | OpenAI | Google |
| Verbal | claude-sonnet-4-5 | claude-sonnet-4-5 | Anthropic | OpenAI |
| Memory | gemini-3-pro | gemini-3-pro | Google | OpenAI |
| Default | gpt-4-turbo | gpt-4-turbo | OpenAI | Anthropic |

## Benchmark Sources

All benchmark data is sourced from official provider announcements, research papers, and third-party evaluations. Last verified: January 2026.

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

*Last updated: 2026-01-29*
*See also: [question-service/docs/PERFORMANCE.md](../question-service/docs/PERFORMANCE.md) for operational performance metrics*
