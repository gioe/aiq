# Analysis: Question Service - Pipeline Performance & First-Class System Assessment

**Date:** 2026-01-20
**Scope:** Comprehensive analysis of the question-service as a performant pipeline and first-class system, examining maintainability, documentation, and cross-component consistency.

## Executive Summary

The question-service is a **well-architected, production-grade microservice** that generates AI-powered IQ test questions through a sophisticated multi-stage pipeline. It demonstrates strong software engineering principles with clear separation of concerns, comprehensive error handling, and excellent documentation.

**Strengths:**
- Exceptional documentation quality (850+ lines of operations guide alone)
- Benchmark-driven arbiter model selection with research backing
- Multi-provider redundancy with graceful degradation
- Comprehensive metrics and alerting infrastructure

**Areas for Improvement:**
- Critical enum value mismatch with backend service requires explicit mapping layer
- Sequential (non-parallel) LLM API calls limit throughput
- No embedding caching causes redundant API calls during deduplication
- Test coverage gaps in integration scenarios

**Overall Assessment:** The question-service rates as a **strong first-class system** in terms of architecture and documentation, but requires attention to cross-service consistency and performance optimization for scale.

---

## Methodology

### Tools and Techniques Used
- Codebase exploration via specialized agents
- Source code analysis of all Python modules
- Cross-service domain model comparison (question-service, backend, iOS)
- Documentation review and completeness assessment
- Industry best practices research via web search

### Files and Directories Examined
- `question-service/app/` - All 14 Python modules
- `question-service/tests/` - 13 test files
- `question-service/docs/` - 5 documentation files
- `question-service/config/` - Configuration files and README
- `backend/app/models/` - Backend domain models
- `ios/AIQ/Models/` - iOS domain models

### External Resources Consulted
- [ZenML LLMOps Case Studies](https://www.zenml.io/blog/llmops-in-production-457-case-studies-of-what-actually-works)
- [Multi-LLM Orchestration Patterns](https://orchestre.dev/blog/multi-llm-orchestration-patterns)
- [LLM Orchestration Frameworks 2025](https://orq.ai/blog/llm-orchestration)
- [Mercado Libre Multi-LLM Architecture](https://www.zenml.io/llmops-database/multi-llm-orchestration-for-product-matching-at-scale)

---

## Findings

### 1. Pipeline Architecture Analysis

#### Architecture Overview

The question-service implements a **4-stage sequential pipeline**:

```
Generation → Evaluation → Deduplication → Storage
    ↓            ↓             ↓            ↓
Multi-LLM    Type-specific  Semantic     PostgreSQL
Providers    Arbiters       Embeddings   Persistence
```

#### Evidence: Pipeline Flow (`run_generation.py:458-678`)

```python
# PHASE 1: Generation - Multi-provider question creation
job_result = pipeline.run_generation_job(...)

# PHASE 2: Arbiter Evaluation - Quality scoring
evaluated_question = arbiter.evaluate_question(question)

# PHASE 3: Deduplication - Semantic similarity check
result = deduplicator.check_duplicate(evaluated_question.question, existing_questions)

# PHASE 4: Storage - Database persistence
question_id = db.insert_evaluated_question(evaluated_question)
```

#### Strengths

**Multi-Provider Redundancy:** The system supports 4 LLM providers (OpenAI, Anthropic, Google, xAI) with round-robin distribution and graceful degradation.

```python
# generator.py:194-214 - Round-robin distribution
if distribute_across_providers and len(self.providers) > 1:
    providers = list(self.providers.keys())
    for i in range(count):
        provider_name = providers[i % len(providers)]
        try:
            question = self.generate_question(...)
        except Exception as e:
            # Continue with next provider on failure
            continue
```

**Type-Specific Arbiters:** Different question types are evaluated by models proven best for that domain via benchmark research.

```yaml
# config/arbiters.yaml - Benchmark-driven assignments
mathematical:
  model: "grok-4"
  provider: "xai"
  rationale: "GSM8K (95.2%), AIME 2024 (100%)"

logical_reasoning:
  model: "claude-sonnet-4-5"
  provider: "anthropic"
  rationale: "HumanEval (93.7%), GPQA (67.2%)"
```

#### Weaknesses

**Sequential Processing:** Each question is processed one at a time with synchronous API calls, limiting throughput.

```python
# generator.py:196-214 - Sequential iteration
for i in range(count):
    provider_name = providers[i % len(providers)]
    question = self.generate_question(...)  # Blocking call
```

**No Embedding Cache:** The deduplicator generates new embeddings for each existing question on every comparison.

```python
# deduplicator.py:202-207 - Uncached embedding generation
for existing in existing_questions:
    existing_embedding = self._get_embedding(existing_text)  # API call per question
    similarity = self._cosine_similarity(new_embedding, existing_embedding)
```

**Impact:** For a pool of 1,000 existing questions, checking 50 new questions requires 50,000 embedding API calls.

---

### 2. Maintainability Assessment

#### Code Quality Metrics

| Aspect | Rating | Evidence |
|--------|--------|----------|
| **Separation of Concerns** | Excellent | Each module has single responsibility (14 focused modules) |
| **Type Safety** | Strong | Pydantic models with field validators (`models.py:57-71`) |
| **Error Handling** | Comprehensive | Error classification with severity levels (`error_classifier.py`) |
| **Logging** | Thorough | Structured logging throughout with appropriate levels |
| **Configuration** | Well-designed | YAML + environment variables with validation |

#### Evidence: Strong Type Safety

```python
# models.py:57-71 - Pydantic validation
@field_validator("answer_options")
@classmethod
def validate_answer_options(cls, v: Optional[List[str]], info) -> Optional[List[str]]:
    if v is not None:
        if len(v) < 2:
            raise ValueError("Must have at least 2 answer options if provided")
        correct = info.data.get("correct_answer")
        if correct and correct not in v:
            raise ValueError(f"correct_answer '{correct}' must be in answer_options")
    return v
```

#### Evidence: Comprehensive Error Classification

```python
# error_classifier.py - Severity-based error categorization
class ErrorCategory(str, Enum):
    BILLING_QUOTA = "billing_quota"     # Critical
    RATE_LIMIT = "rate_limit"           # High
    AUTHENTICATION = "authentication"   # Critical
    INVALID_REQUEST = "invalid_request" # Medium
    SERVER_ERROR = "server_error"       # High
    NETWORK_ERROR = "network_error"     # Low
```

#### Maintainability Issues

**Magic Numbers:** Some hardcoded values should be configurable.

```python
# deduplicator.py:69-71
def __init__(
    self,
    similarity_threshold: float = 0.85,  # Hardcoded default
    embedding_model: str = "text-embedding-3-small",  # Hardcoded model
):
```

**Provider Model Switching Side Effect:** The arbiter temporarily modifies provider model state.

```python
# arbiter.py:127-128 - Mutable state modification
original_model = provider.model
provider.model = arbiter_model.model  # Side effect
```

---

### 3. Documentation Quality

#### Documentation Inventory

| Document | Lines | Purpose | Quality |
|----------|-------|---------|---------|
| `README.md` | 349 | Service overview | Excellent |
| `docs/OPERATIONS.md` | 850 | Operations guide | Outstanding |
| `docs/ARBITER_SELECTION.md` | 488 | Model selection rationale | Exceptional |
| `docs/SCHEDULING.md` | ~200 | Scheduling options | Good |
| `docs/ALERTING.md` | ~150 | Alert configuration | Good |
| `config/README.md` | ~100 | Config reference | Good |

**Total Documentation:** ~2,100+ lines

#### Evidence: Outstanding Operations Guide

The OPERATIONS.md file includes:
- 5-minute setup guide
- Configuration reference with examples
- Exit code documentation
- Troubleshooting workflows
- Maintenance checklists (weekly, monthly, quarterly, annual)
- Command reference

```markdown
# From OPERATIONS.md - Comprehensive troubleshooting
#### 4. Partial Failure (Exit Code 1)
**Symptoms**: Some questions generated, but errors occurred
**Diagnosis**:
# Check logs for specific errors
grep "ERROR" logs/question_service.log | tail -20
# Check LLM API rate limits
grep "rate limit" logs/question_service.log
```

#### Evidence: Research-Backed Arbiter Selection

The ARBITER_SELECTION.md provides:
- Benchmark-to-question-type mapping rationale
- Specific benchmark scores for each model
- Update process with quarterly review schedule
- Decision criteria with switching thresholds

```markdown
# From ARBITER_SELECTION.md
### Switching Checklist
- [ ] New model shows >5% improvement on primary benchmark
- [ ] Cost increase is acceptable (<20%) OR performance gain (>10%)
- [ ] Latency is acceptable (<2x current model)
```

#### Documentation Gaps

1. **API Contract Documentation:** No OpenAPI/Swagger spec for trigger server
2. **Architecture Diagrams:** Text descriptions only, no visual diagrams
3. **Performance Benchmarks:** No documented baseline performance metrics

---

### 4. Cross-Component Consistency (Critical Issue)

#### Enum Value Mismatch

**The question-service and backend use incompatible enum values.**

| Component | Pattern Type | Logic Type | Math Type |
|-----------|-------------|------------|-----------|
| **Question-Service** | `PATTERN_RECOGNITION` | `LOGICAL_REASONING` | `MATHEMATICAL` |
| **Backend** | `PATTERN` | `LOGIC` | `MATH` |
| **iOS** | `"pattern"` | `"logic"` | `"math"` |

#### Evidence: Question-Service Enums (`models.py:14-21`)

```python
class QuestionType(str, Enum):
    PATTERN_RECOGNITION = "pattern_recognition"
    LOGICAL_REASONING = "logical_reasoning"
    SPATIAL_REASONING = "spatial_reasoning"
    MATHEMATICAL = "mathematical"
    VERBAL_REASONING = "verbal_reasoning"
    MEMORY = "memory"
```

#### Evidence: Backend Enums (`backend/app/models/models.py`)

```python
class QuestionType(str, Enum):
    PATTERN = "pattern"
    LOGIC = "logic"
    SPATIAL = "spatial"
    MATH = "math"
    VERBAL = "verbal"
    MEMORY = "memory"
```

#### Evidence: Database Mapping Layer (`database.py:148-155`)

The question-service includes a manual mapping to bridge this gap:

```python
question_type_map = {
    "pattern_recognition": "pattern",
    "logical_reasoning": "logic",
    "spatial_reasoning": "spatial",
    "mathematical": "math",
    "verbal_reasoning": "verbal",
    "memory": "memory",
}
```

**Risk:** This mapping exists in the database module but not in the reporter module, creating potential inconsistencies when reporting to the backend API.

#### Additional Inconsistencies

| Field | Question-Service | Backend | iOS |
|-------|-----------------|---------|-----|
| Metadata field name | `metadata` | `question_metadata` | N/A |
| `source_model` | Present | Missing | N/A |
| `answer_options` | `List[str]` | `JSON (list or dict)` | Not generated |

---

### 5. Test Coverage Analysis

#### Test Inventory

| Test File | Lines | Focus Area |
|-----------|-------|------------|
| `test_generator.py` | 252 | Question generation |
| `test_arbiter.py` | ~200 | Evaluation logic |
| `test_arbiter_config.py` | ~150 | Configuration loading |
| `test_models.py` | ~100 | Data model validation |
| `test_deduplicator.py` | ~150 | Duplicate detection |
| `test_database.py` | ~100 | Database operations |
| `test_pipeline.py` | ~100 | Pipeline orchestration |
| `test_metrics.py` | ~80 | Metrics tracking |
| `test_prompts.py` | ~50 | Prompt templates |

#### Strengths

**Good Unit Test Coverage:** Core modules have dedicated test files with mocking.

```python
# test_generator.py:115-144 - Tests error resilience
def test_generate_batch_with_failures(self, generator_with_openai):
    provider.generate_structured_completion.side_effect = [
        {"question_text": "Q1?", ...},
        Exception("API Error"),  # Simulated failure
        {"question_text": "Q3?", ...},
    ]
    batch = generator_with_openai.generate_batch(count=3)
    assert len(batch.questions) == 2  # Continues despite failure
```

#### Gaps

1. **No Integration Tests:** Missing end-to-end pipeline tests with real API calls (even mocked)
2. **No Provider Tests:** `tests/providers/` directory exists but appears empty
3. **No Performance Tests:** No benchmarks for throughput or latency

---

### 6. Industry Best Practices Comparison

#### Alignment with Best Practices

| Practice | Question-Service | Industry Standard |
|----------|-----------------|-------------------|
| **Modular Pipeline** | 4-stage pipeline | Multi-stage recommended |
| **Provider Redundancy** | 4 providers | Risk mitigation via redundancy |
| **Error Classification** | 6 categories | Severity-based handling |
| **Metrics Tracking** | Comprehensive | Essential for LLMOps |
| **Configuration-Driven** | YAML + env vars | Externalized config |

#### Gaps vs. Best Practices

| Practice | Question-Service | Industry Standard |
|----------|-----------------|-------------------|
| **Parallel Processing** | Sequential | Async/concurrent calls |
| **Caching** | None | Embedding/response caching |
| **A/B Testing** | None | Model comparison capability |
| **Observability** | Basic logging | Distributed tracing |
| **RAG Evaluation** | N/A | RAGAS or similar frameworks |

#### Reference: Mercado Libre's Multi-LLM System

> "The final production system deployed a sophisticated 7-node architecture with... collaborative consensus mechanisms between nodes where multiple LLM components could validate each other's outputs."

The question-service's dual-phase approach (generation + evaluation) follows this pattern but could benefit from consensus mechanisms for borderline cases.

---

## Recommendations

### Summary Table

| Priority | ID | Recommendation | Effort | Impact | Category |
|----------|-----|---------------|--------|--------|----------|
| **Critical** | R01 | Standardize enum values across services | Medium | High | Consistency |
| **Critical** | R02 | Add enum mapping to reporter.py | Low | High | Consistency |
| **Critical** | R03 | Store `source_model` in backend database | Low | Medium | Consistency |
| **High** | R04 | Add embedding cache to deduplicator | Low | High | Performance |
| **High** | R05 | Implement async/parallel LLM calls for generation | Medium | High | Performance |
| **High** | R06 | Implement async/parallel arbiter evaluation | Medium | High | Performance |
| **High** | R07 | Pre-compute and store embeddings in database | Medium | High | Performance |
| **High** | R08 | Add provider-level unit tests | Low | Medium | Testing |
| **High** | R09 | Add end-to-end integration tests | Medium | High | Testing |
| **High** | R10 | Fix iOS `answerOptions` generation issue | Medium | High | Consistency |
| **Medium** | R11 | Eliminate arbiter provider model mutation | Low | Medium | Code Quality |
| **Medium** | R12 | Extract deduplication config to settings | Low | Medium | Maintainability |
| **Medium** | R13 | Create architecture diagrams | Low | Medium | Documentation |
| **Medium** | R14 | Document baseline performance metrics | Medium | Medium | Documentation |
| **Medium** | R15 | Add OpenAPI spec for trigger server | Low | Medium | Documentation |
| **Medium** | R16 | Add distributed tracing (OpenTelemetry) | Medium | Medium | Observability |
| **Medium** | R17 | Implement cost tracking per provider | Low | Medium | Observability |
| **Medium** | R18 | Add retry logic with exponential backoff | Low | Medium | Reliability |
| **Medium** | R19 | Implement circuit breaker for providers | Medium | Medium | Reliability |
| **Medium** | R20 | Standardize metadata field naming | Low | Low | Consistency |
| **Low** | R21 | Add A/B testing capability for arbiters | High | Medium | Features |
| **Low** | R22 | Add consensus mechanism for borderline scores | Medium | Low | Features |
| **Low** | R23 | Create shared domain types package | High | Medium | Architecture |
| **Low** | R24 | Add performance/load tests | Medium | Low | Testing |
| **Low** | R25 | Implement response caching for identical prompts | Low | Low | Performance |

---

### Critical Priority

#### R01: Standardize Enum Values Across Services

**Problem:** The question-service uses `PATTERN_RECOGNITION` while the backend uses `PATTERN`. This creates brittle mapping code and potential data inconsistencies.

**Evidence:** `question-service/app/models.py:14-21` vs `backend/app/models/models.py`

**Solution Options:**
- **Option A (Recommended):** Align question-service enums to match backend (breaking change, but simplifies system)
- **Option B:** Create a shared enum package used by both services
- **Option C:** Formalize the mapping layer with comprehensive tests

**Files Affected:**
- `question-service/app/models.py`
- `question-service/app/database.py`
- `question-service/app/reporter.py`
- `question-service/app/prompts.py` (if enum values used in prompts)

---

#### R02: Add Enum Mapping to Reporter Module

**Problem:** The `reporter.py` module sends metrics to the backend API but doesn't include the same enum mapping that exists in `database.py`. This could cause inconsistent question type values in reports.

**Evidence:** `database.py:148-155` has mapping, but `reporter.py` does not.

**Solution:** Extract the mapping to a shared utility and use it in both modules.

**Files Affected:**
- `question-service/app/reporter.py`
- Create `question-service/app/type_mapping.py` (new file)

---

#### R03: Store `source_model` in Backend Database

**Problem:** The question-service tracks both `source_llm` (provider) and `source_model` (specific model like "gpt-4-turbo"), but the backend database only stores `source_llm`. This loses valuable traceability data.

**Evidence:** `question-service/app/models.py:54-55` has both fields; backend only has `source_llm`.

**Solution:** Add `source_model` column to backend's questions table.

**Files Affected:**
- `backend/app/models/models.py`
- Backend database migration
- `question-service/app/database.py` (update insert)

---

### High Priority

#### R04: Add Embedding Cache to Deduplicator

**Problem:** Each deduplication check generates embeddings for all existing questions, causing O(n*m) API calls.

**Evidence:** `deduplicator.py:202-207` - uncached embedding generation in loop.

**Solution:**
```python
class QuestionDeduplicator:
    def __init__(self, ..., cache_embeddings: bool = True):
        self._embedding_cache: Dict[str, np.ndarray] = {}

    def _get_embedding(self, text: str) -> np.ndarray:
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key]
        embedding = self._fetch_embedding(text)
        self._embedding_cache[cache_key] = embedding
        return embedding
```

**Impact:** Reduces embedding API calls from O(n*m) to O(n+m).

**Files Affected:**
- `question-service/app/deduplicator.py`

---

#### R05: Implement Async/Parallel LLM Calls for Generation

**Problem:** Sequential API calls limit throughput. Generating 50 questions takes ~50 sequential LLM calls.

**Evidence:** `generator.py:196-214` - sequential for loop with blocking calls.

**Solution:** Use `asyncio` with provider-specific async clients.

```python
async def generate_batch_async(self, count: int) -> List[GeneratedQuestion]:
    tasks = [
        self._generate_question_async(provider)
        for provider in self._round_robin_providers(count)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if isinstance(r, GeneratedQuestion)]
```

**Impact:** Could reduce generation time by 4-10x.

**Files Affected:**
- `question-service/app/generator.py`
- `question-service/app/providers/*.py` (add async methods)
- `question-service/app/pipeline.py`
- `question-service/run_generation.py`

---

#### R06: Implement Async/Parallel Arbiter Evaluation

**Problem:** Arbiter evaluations are also sequential - each question waits for the previous evaluation.

**Evidence:** `run_generation.py:521-552` - sequential for loop over generated questions.

**Solution:** Parallelize arbiter calls similar to generation.

**Files Affected:**
- `question-service/app/arbiter.py`
- `question-service/run_generation.py`

---

#### R07: Pre-compute and Store Embeddings in Database

**Problem:** Embeddings are computed on-the-fly every run. For a growing question pool, this becomes increasingly expensive.

**Solution:** Store embeddings in a vector column or separate table, compute once at insertion time.

**Files Affected:**
- `backend/app/models/models.py` (add embedding column)
- `question-service/app/database.py` (store embedding on insert)
- `question-service/app/deduplicator.py` (load pre-computed embeddings)

---

#### R08: Add Provider-Level Unit Tests

**Problem:** The `tests/providers/` directory exists but contains no tests. Provider implementations are untested.

**Evidence:** `tests/providers/__init__.py` exists but no test files.

**Solution:** Add unit tests for each provider with mocked HTTP responses.

**Files Affected:**
- `question-service/tests/providers/test_openai_provider.py` (new)
- `question-service/tests/providers/test_anthropic_provider.py` (new)
- `question-service/tests/providers/test_google_provider.py` (new)
- `question-service/tests/providers/test_xai_provider.py` (new)

---

#### R09: Add End-to-End Integration Tests

**Problem:** No tests exercise the full pipeline flow from generation through storage.

**Solution:** Create integration tests with mocked external APIs but real internal flow.

**Files Affected:**
- `question-service/tests/test_integration.py` (new)

---

#### R10: Fix iOS `answerOptions` Generation Issue

**Problem:** iOS's generated Question type is missing `answerOptions` and `explanation` fields due to OpenAPI generator limitations with nullable types.

**Evidence:** `ios/AIQ/Models/Question+Extensions.swift` has deprecated stubs returning `false`.

**Solution Options:**
- Update OpenAPI spec to make fields required (not nullable)
- Use a different OpenAPI generator
- Manually extend the generated type

**Files Affected:**
- `backend/openapi.yaml` or schema generation
- iOS generated models

---

### Medium Priority

#### R11: Eliminate Arbiter Provider Model Mutation

**Problem:** The arbiter temporarily mutates the provider's model attribute, which is a side effect that could cause issues in concurrent scenarios.

**Evidence:** `arbiter.py:127-128` - modifies `provider.model`, restores in `finally`.

**Solution:** Create a new provider instance or pass model as parameter to completion method.

**Files Affected:**
- `question-service/app/arbiter.py`
- `question-service/app/providers/base.py` (accept model override)

---

#### R12: Extract Deduplication Config to Settings

**Problem:** Similarity threshold (0.85) and embedding model are hardcoded defaults.

**Evidence:** `deduplicator.py:69-71`

**Solution:** Add to `config.py` Settings class.

**Files Affected:**
- `question-service/app/config.py`
- `question-service/app/deduplicator.py`
- `question-service/.env.example`

---

#### R13: Create Architecture Diagrams

**Problem:** Documentation uses only text descriptions; no visual diagrams.

**Solution:** Add Mermaid or PNG diagrams showing:
- Pipeline flow
- Component interactions
- Deployment architecture

**Files Affected:**
- `question-service/docs/ARCHITECTURE.md` (new)
- `question-service/README.md` (embed diagram)

---

#### R14: Document Baseline Performance Metrics

**Problem:** No documented baseline for expected throughput, latency, or cost per question.

**Solution:** Run benchmarks and document:
- Questions per minute per provider
- Average latency per stage
- Cost per question by provider

**Files Affected:**
- `question-service/docs/PERFORMANCE.md` (new)

---

#### R15: Add OpenAPI Spec for Trigger Server

**Problem:** The `trigger_server.py` FastAPI app has no documented API contract.

**Solution:** Export OpenAPI spec, add to docs.

**Files Affected:**
- `question-service/docs/api/trigger-server.yaml` (new)
- `question-service/trigger_server.py` (add metadata)

---

#### R16: Add Distributed Tracing

**Problem:** Only basic logging exists; no request correlation or distributed tracing.

**Solution:** Integrate OpenTelemetry for tracing across pipeline stages.

**Files Affected:**
- `question-service/app/tracing.py` (new)
- All pipeline modules (add spans)
- `question-service/requirements.txt`

---

#### R17: Implement Cost Tracking per Provider

**Problem:** No visibility into LLM API costs per run or per provider.

**Solution:** Add token counting and cost calculation to metrics.

**Files Affected:**
- `question-service/app/metrics.py`
- `question-service/app/providers/base.py`

---

#### R18: Add Retry Logic with Exponential Backoff

**Problem:** Provider failures are caught but not retried. Transient errors cause lost questions.

**Evidence:** `generator.py:208-214` - catches exception and continues.

**Solution:** Add configurable retry with exponential backoff.

**Files Affected:**
- `question-service/app/providers/base.py`
- `question-service/app/config.py`

---

#### R19: Implement Circuit Breaker for Providers

**Problem:** A failing provider will keep receiving requests until all fail.

**Solution:** Add circuit breaker pattern to temporarily disable failing providers.

**Files Affected:**
- `question-service/app/circuit_breaker.py` (new)
- `question-service/app/generator.py`

---

#### R20: Standardize Metadata Field Naming

**Problem:** Question-service uses `metadata`, backend uses `question_metadata`.

**Evidence:** Cross-component comparison findings.

**Solution:** Align naming (prefer `metadata` for simplicity).

**Files Affected:**
- `backend/app/models/models.py`
- Backend migration

---

### Low Priority

#### R21: Add A/B Testing Capability for Arbiters

**Problem:** Cannot easily compare arbiter model performance in production.

**Solution:** Add configuration to split traffic between arbiter models and compare approval rates.

**Files Affected:**
- `question-service/app/arbiter.py`
- `question-service/config/arbiters.yaml`
- `question-service/app/metrics.py`

---

#### R22: Add Consensus Mechanism for Borderline Scores

**Problem:** Questions near the approval threshold (e.g., 0.68-0.72) are binary approved/rejected without additional review.

**Solution:** For borderline cases, query multiple arbiters and use consensus.

**Files Affected:**
- `question-service/app/arbiter.py`
- `question-service/app/config.py`

---

#### R23: Create Shared Domain Types Package

**Problem:** Each service defines its own enums and types, leading to drift.

**Solution:** Create a shared Python/Swift package for domain types.

**Files Affected:**
- New shared package
- All services

---

#### R24: Add Performance/Load Tests

**Problem:** No tests verify behavior under load or measure throughput.

**Solution:** Add locust or pytest-benchmark tests.

**Files Affected:**
- `question-service/tests/performance/` (new directory)

---

#### R25: Implement Response Caching for Identical Prompts

**Problem:** If the same prompt is sent twice (e.g., retry scenario), it generates a new API call.

**Solution:** Add optional response cache with TTL.

**Files Affected:**
- `question-service/app/providers/base.py`
- `question-service/app/config.py`

---

## Appendix

### Files Analyzed

**Core Application (`app/`):**
- `__init__.py` - Package exports
- `pipeline.py` - Pipeline orchestration (305 lines)
- `generator.py` - Question generation (379 lines)
- `arbiter.py` - Quality evaluation (394 lines)
- `deduplicator.py` - Duplicate detection (328 lines)
- `database.py` - Database operations (385 lines)
- `config.py` - Settings management (60 lines)
- `arbiter_config.py` - YAML config loader (~200 lines)
- `models.py` - Pydantic data models (151 lines)
- `prompts.py` - LLM prompt templates
- `metrics.py` - Metrics tracking
- `error_classifier.py` - Error categorization
- `logging_config.py` - Logging setup
- `alerting.py` - Alert management
- `reporter.py` - Backend API reporting

**Providers (`app/providers/`):**
- `base.py` - Abstract base class
- `openai_provider.py` - OpenAI integration
- `anthropic_provider.py` - Anthropic integration
- `google_provider.py` - Google integration
- `xai_provider.py` - xAI/Grok integration

**Tests (`tests/`):**
- 13 test files covering all major modules

**Documentation (`docs/`):**
- 5 comprehensive markdown guides

### Related Resources

- [ZenML LLMOps in Production](https://www.zenml.io/blog/llmops-in-production-457-case-studies-of-what-actually-works)
- [Multi-LLM Orchestration Patterns](https://orchestre.dev/blog/multi-llm-orchestration-patterns)
- [LLM Orchestration Best Practices 2025](https://orq.ai/blog/llm-orchestration)
- [Databricks LLMOps Guide](https://www.databricks.com/glossary/llmops)

---

**Analysis completed:** 2026-01-20
**Analyst:** Claude Code Analysis Agent
