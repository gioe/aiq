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
| **Anthropic** | claude-sonnet-4-5-20250929 | Logic, Verbal, Memory evaluation |
| **Google** | gemini-2.5-pro | Pattern, Spatial evaluation |
| **OpenAI** | gpt-4-turbo-preview | General-purpose fallback |
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
| **Pattern** | gemini-3-pro-preview | Google | ARC-AGI-2 | 31.1% |
| **Spatial** | gemini-3-pro-preview | Google | ARC-AGI-2 | 31.1%* |
| **Verbal** | claude-sonnet-4-5 | Anthropic | HellaSwag | ~95% |
| **Memory** | claude-sonnet-4-5 | Anthropic | MMLU | 89% |

*Uses standard mode. Deep Think mode (45.1%) is not currently enabled.

## Detailed Benchmark Data

### Mathematical Reasoning

Mathematical reasoning is critical for evaluating IQ questions involving numerical patterns, algebraic problems, and quantitative logic.

| Model | GSM8K | AIME 2024 | USAMO 2025 | MATH | MMLU-Math |
|-------|-------|-----------|------------|------|-----------|
| **grok-4** | 95.2% | **100%** | **61.9%** | - | 92.1% |
| claude-opus-4-5 | 96.4% | - | - | 96.4% | - |
| claude-sonnet-4-5 | - | - | - | - | 89% |
| gemini-3-pro-preview | - | - | - | - | - |
| gpt-4-turbo | 92.0% | - | - | 52.9% | - |

**Selected for Math Evaluation:** `grok-4` (xAI)

**Rationale:** Grok 4 demonstrates world-class mathematical reasoning with a perfect 100% score on AIME 2024 and exceptional 61.9% on USAMO 2025, outperforming competitors on advanced competition mathematics.

### Logical Reasoning

Logical reasoning benchmarks assess the ability to evaluate deductive reasoning, code logic, and structured problem-solving.

| Model | HumanEval | GPQA Diamond | SWE-bench | LiveCodeBench |
|-------|-----------|--------------|-----------|---------------|
| **claude-sonnet-4-5** | >95% | 83.4% | **77-82%** | - |
| claude-opus-4-5 | 97.6% | 83.3% | 72.5% | - |
| gemini-3-pro-preview | - | 91.9% | - | - |
| gpt-4-turbo | 87.1% | - | - | - |
| grok-4 | - | - | - | - |

**Selected for Logic Evaluation:** `claude-sonnet-4-5-20250929` (Anthropic)

**Rationale:** Claude Sonnet 4.5 combines exceptional coding benchmark performance (HumanEval >95%) with strong GPQA Diamond scores (83.4%) and leading SWE-bench results (77-82%), making it ideal for evaluating logical reasoning in IQ questions.

### Pattern Recognition

Pattern recognition benchmarks measure abstract reasoning and the ability to identify underlying structures.

| Model | ARC-AGI-2 | ARC-AGI-2 (Deep Think)* | MMMU-Pro | Visual Reasoning |
|-------|-----------|-------------------------|----------|------------------|
| **gemini-3-pro-preview** | **31.1%** | 45.1% | 81.0% | 62% |
| claude-sonnet-4-5 | - | - | - | - |
| gpt-4-turbo | - | - | - | - |
| grok-4 | - | - | - | - |

*Deep Think mode is not currently enabled in our implementation.

**Selected for Pattern Evaluation:** `gemini-3-pro-preview` (Google)

**Rationale:** Gemini 3 Pro achieves breakthrough performance on ARC-AGI-2 (31.1% standard mode), the gold-standard benchmark for abstract pattern reasoning. This represents a 6x improvement over previous models and makes it the clear choice for evaluating pattern recognition questions.

### Spatial Reasoning

Spatial reasoning benchmarks evaluate the ability to mentally manipulate objects and understand spatial relationships.

| Model | ARC-AGI-2 | MMMU-Pro | Visual Reasoning | 3D Understanding |
|-------|-----------|----------|------------------|------------------|
| **gemini-3-pro-preview** | 31.1% | **81.0%** | **62%** | - |
| claude-sonnet-4-5 | - | - | - | - |
| gpt-4-turbo | - | - | - | - |

**Selected for Spatial Evaluation:** `gemini-3-pro-preview` (Google)

**Rationale:** Gemini 3 Pro's MMMU-Pro score (81.0%) and visual reasoning capabilities (62%) demonstrate strong spatial understanding. The ARC-AGI-2 benchmark, which tests abstract spatial manipulation, shows exceptional performance (31.1% standard mode). Deep Think mode (45.1%) is not currently enabled but could be a future enhancement.

### Verbal Reasoning

Verbal reasoning benchmarks measure language understanding, reading comprehension, and natural language inference.

| Model | MMLU | HellaSwag | WinoGrande | Reading Comprehension |
|-------|------|-----------|------------|----------------------|
| **claude-sonnet-4-5** | **89%** | **~95%** | - | - |
| claude-opus-4-5 | 87.4% | - | - | - |
| gpt-4-turbo | 86.4% | - | - | - |
| gemini-3-pro-preview | - | - | - | - |

**Selected for Verbal Evaluation:** `claude-sonnet-4-5-20250929` (Anthropic)

**Rationale:** Claude Sonnet 4.5 achieves strong MMLU performance (89%) and excellent HellaSwag scores (~95%), demonstrating superior language understanding and commonsense reasoning essential for evaluating verbal IQ questions.

### Memory and Knowledge

Memory evaluation requires both broad knowledge and the ability to process long contexts.

| Model | MMLU | Context Window | Long-Context Retrieval |
|-------|------|----------------|----------------------|
| **claude-sonnet-4-5** | **89%** | **200,000 tokens** | - |
| claude-opus-4-5 | 87.4% | 200,000 tokens | - |
| gemini-3-pro-preview | - | 1,000,000+ tokens | - |
| gpt-4-turbo | 86.4% | 128,000 tokens | - |

**Selected for Memory Evaluation:** `claude-sonnet-4-5-20250929` (Anthropic)

**Rationale:** Claude Sonnet 4.5 combines strong knowledge benchmarks (MMLU 89%) with a massive 200K token context window, making it ideal for evaluating memory-intensive questions that require both factual knowledge and context retention.

## Model Selection Rationale

AIQ uses a "specialists-do-both" approach where the same model that excels at a cognitive task type is used for both:
1. **Generating** questions of that type
2. **Evaluating** (judging) questions of that type

This ensures domain expertise is applied consistently throughout the pipeline.

| Question Type | Generator | Judge | Provider |
|---------------|-----------|-------|----------|
| Math | grok-4 | grok-4 | xAI |
| Logic | claude-sonnet-4-5 | claude-sonnet-4-5 | Anthropic |
| Pattern | gemini-3-pro-preview | gemini-3-pro-preview | Google |
| Spatial | gemini-3-pro-preview | gemini-3-pro-preview | Google |
| Verbal | claude-sonnet-4-5 | claude-sonnet-4-5 | Anthropic |
| Memory | claude-sonnet-4-5 | claude-sonnet-4-5 | Anthropic |
| Default | gpt-4-turbo | gpt-4-turbo | OpenAI |

## Benchmark Sources

All benchmark data is sourced from official provider announcements, research papers, and third-party evaluations. Last verified: January 2026.

### Anthropic (Claude)

- [Claude 4.5 Release Announcement](https://www.anthropic.com/news/claude-4-5) - Official benchmark figures for Claude 4.5 Opus and Sonnet
- [Anthropic Model Card](https://www.anthropic.com/claude) - Technical specifications and capabilities
- [GPQA Benchmark Paper](https://arxiv.org/abs/2311.12022) - Graduate-level science questions benchmark
- [SWE-bench](https://www.swebench.com/) - Real-world software engineering benchmark

### Google (Gemini)

- [Gemini 3.0 Technical Report](https://blog.google/technology/ai/google-gemini-ai/) - Official Gemini 3 announcement with benchmarks
- [ARC-AGI-2 Leaderboard](https://arcprize.org/leaderboard) - Abstract reasoning benchmark results
- [MMMU-Pro Benchmark](https://mmmu-benchmark.github.io/) - Multimodal understanding benchmark

### OpenAI (GPT)

- [GPT-4 Technical Report](https://arxiv.org/abs/2303.08774) - Original GPT-4 benchmark data
- [GPT-5 Release Blog](https://openai.com/blog) - Latest model announcements
- [HumanEval Benchmark](https://github.com/openai/human-eval) - Code generation benchmark

### xAI (Grok)

- [Grok 4 Announcement](https://x.ai/blog) - Official Grok 4 release with AIME/USAMO scores
- [GSM8K Benchmark](https://github.com/openai/grade-school-math) - Grade school math reasoning
- [AIME Competition Results](https://artofproblemsolving.com/wiki/index.php/AIME_Problems_and_Solutions) - American Invitational Mathematics Examination

### Third-Party Evaluations

- [LMSYS Chatbot Arena](https://chat.lmsys.org/?leaderboard) - Crowdsourced model comparisons
- [Hugging Face Open LLM Leaderboard](https://huggingface.co/spaces/HuggingFaceH4/open_llm_leaderboard) - Standardized evaluations
- [Artificial Analysis LLM Benchmarks](https://artificialanalysis.ai/) - Independent performance testing

---

*Last updated: 2026-01-24*
*See also: [question-service/docs/PERFORMANCE.md](../question-service/docs/PERFORMANCE.md) for operational performance metrics*
