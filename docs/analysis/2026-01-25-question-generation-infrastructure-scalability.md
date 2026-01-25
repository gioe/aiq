# Analysis: Question Generation Infrastructure Scalability for Production Release

**Date:** 2026-01-25
**Scope:** Comprehensive analysis of question-service architecture, production readiness, question inventory requirements, type-specific generation capabilities, and integration processes.

## Executive Summary

The question generation infrastructure is architecturally sound and production-ready with robust error handling, circuit breakers, and multi-provider failover. However, there are critical gaps in **question inventory management** and **targeted generation capabilities** that should be addressed before release.

**Key Findings:**
1. **Inventory Gap**: The current daily cron job generates 50 questions uniformly across all 6 types and 3 difficulty levels, producing ~5-12 net new questions per run. This approach lacks precision for building up specific categories that may be underrepresented.
2. **Missing Type-Specific Commands**: While the `--types` flag exists in `run_generation.py`, there is no skill/command wrapper for easily generating questions of specific types. Operations staff must manually run CLI commands.
3. **Scalability is Adequate**: The async generation mode (4-10x speedup) and multi-provider architecture can handle production loads. Estimated throughput: 15-20 questions/minute with full async enabled.
4. **Integration is Mature**: Backend receives generation metrics via `RunReporter`, tracks runs in database, and the Railway deployment is well-configured.

**Primary Recommendation:** Create targeted generation commands and implement an inventory dashboard before release to ensure question pool balance across all strata (6 types x 3 difficulties = 18 strata, each needing sufficient depth).

## Methodology

### Tools and Techniques Used
- Codebase exploration using Glob, Grep, and Read tools
- Analysis of configuration files (YAML, JSON, Python settings)
- Review of deployment configurations (Railway, Docker)
- Examination of test composition logic to understand inventory requirements
- Documentation review (OPERATIONS.md, PERFORMANCE.md, README files)

### Files and Directories Examined
- `question-service/` - Core generation pipeline code
- `backend/app/core/test_composition.py` - Question selection algorithm
- `backend/app/core/config.py` - Test configuration settings
- `.claude/skills/` - Existing skill definitions
- `railway-cron.json` - Scheduled generation configuration
- Configuration files in `question-service/config/`

## Findings

### 1. Current Question Generation Capabilities

#### Architecture Overview
The question-service implements a 4-stage pipeline:
1. **Generation**: Multi-provider LLM question creation (OpenAI, Anthropic, Google, xAI)
2. **Evaluation**: Type-specific judge models assess quality (0.7 minimum score threshold)
3. **Deduplication**: Exact hash + semantic similarity (0.85 threshold) checking
4. **Storage**: PostgreSQL with pre-computed embeddings

#### Evidence
- Pipeline implementation: `question-service/app/pipeline.py:23-460`
- Generator: `question-service/app/generator.py:42-250`
- Judge: `question-service/app/judge.py:38-200`
- Type-specific routing: `question-service/config/generators.yaml` and `judges.yaml`

#### Type-Specific Generation Already Supported
The CLI **already supports** targeted type generation via the `--types` flag:

```bash
# Generate only math and logic questions
python run_generation.py --types math logic --count 50

# Generate all questions of one type
python run_generation.py --types spatial --count 100
```

**File reference:** `question-service/run_generation.py:183-189`

However, there is **no skill wrapper** or convenient command for operations teams to use this capability without direct CLI access.

### 2. Question Inventory Requirements

#### Test Composition Requirements
Based on `backend/app/core/test_composition.py` and `backend/app/core/config.py`:

| Parameter | Value | Source |
|-----------|-------|--------|
| Questions per test | 20 | `TEST_TOTAL_QUESTIONS` (config.py:69) |
| Difficulty distribution | Easy 30%, Medium 40%, Hard 30% | `TEST_DIFFICULTY_DISTRIBUTION` (config.py:70-74) |
| Cognitive domains | 6 types | pattern, logic, spatial, math, verbal, memory |
| Target per domain | ~3-4 questions | Evenly distributed across types |

#### Minimum Inventory Calculation

For a single user taking multiple tests without seeing repeated questions:

| Scenario | Tests | Questions Needed | Per Stratum (18 strata)* |
|----------|-------|------------------|--------------------------|
| 1 test | 1 | 20 | ~1-2 |
| 4 tests (1 year, quarterly) | 4 | 80 | ~4-5 |
| 12 tests (3 years) | 12 | 240 | ~13-14 |
| Buffer for growth (3x) | - | 720 | ~40 |

*18 strata = 6 question types x 3 difficulty levels

#### Critical Insight: Stratified Selection Fallback

The `select_stratified_questions` function (`test_composition.py:22-264`) has a **three-tier fallback** strategy:

1. First: Try to get questions from specific type + difficulty combination
2. If insufficient: Fall back to any question of that difficulty level (logging warning)
3. If still insufficient: Fall back to any available question (logging warning)

This means the system will **degrade gracefully** but may serve imbalanced tests if inventory is sparse in certain strata.

### 3. Current Production Generation Configuration

#### Railway Cron Configuration
**File:** `railway-cron.json`
```json
{
  "deploy": {
    "startCommand": "cd question-service && python run_generation.py --count 50 --verbose",
    "cronSchedule": "0 2 * * *",
    "restartPolicyType": "NEVER"
  }
}
```

**Analysis:**
- Runs **daily at 2:00 AM UTC**
- Generates **50 questions** per run
- Uniform distribution across all types (round-robin)
- No type-specific targeting

#### Expected Output per Run

Based on `question-service/docs/PERFORMANCE.md`:

| Metric | Value |
|--------|-------|
| Questions generated | 15-25 (before evaluation) |
| Questions approved | 8-15 (after judge filtering) |
| Questions inserted | 5-12 (after deduplication) |
| Effective throughput | 3-7 questions/minute net |

With uniform distribution, each run contributes approximately:
- ~1-2 questions per type (6 types)
- ~2-4 questions per difficulty level (3 levels)
- **~0.3-0.7 questions per stratum** (18 strata)

### 4. Scalability Assessment

#### Current Capabilities

| Aspect | Status | Notes |
|--------|--------|-------|
| Async generation | Supported | `--async` flag, 10 concurrent default |
| Async judging | Supported | `--async-judge` flag |
| Multi-provider | Yes | 4 providers with circuit breakers |
| Rate limiting | Per-provider semaphores | Configurable via CLI |
| Retry logic | Exponential backoff | 3 retries, 60s max delay |
| Circuit breakers | Yes | Failure threshold: 5, 60s recovery |
| Cost tracking | Yes | Per-question cost calculation |
| Backend reporting | Yes | `RunReporter` posts to API |

#### Scaling Capacity

**Maximum throughput with full async:**
- 15-20 questions/minute per provider
- 4 providers = 60-80 questions/minute theoretical
- Practical (with rate limits): ~30-40 questions/minute

**To generate 720 questions (target inventory):**
- Current rate (5-12/day): **60-144 days**
- With 2x daily runs: **30-72 days**
- With bulk generation (200 questions, async): **~2-3 days**

### 5. Integration Process Assessment

#### Strengths

1. **Comprehensive metrics tracking**: The `MetricsTracker` captures generation, evaluation, deduplication, and insertion metrics
2. **Backend integration**: `RunReporter` (`question-service/app/reporter.py`) posts execution results to `/v1/admin/generation-runs`
3. **Health monitoring**: Heartbeat file (`logs/heartbeat.json`) for scheduler tracking
4. **Exit codes**: 7 distinct exit codes for different failure modes
5. **Alerting**: Email + file-based alerts for critical errors

#### Evidence
- Reporter: `question-service/app/reporter.py`
- Metrics: `question-service/app/metrics.py`
- Admin endpoint: `backend/app/api/v1/admin/generation.py:509-611`
- Exit codes: `run_generation.py:47-54`

### 6. Gap Analysis: Missing Capabilities

#### Gap 1: No Type-Specific Generation Commands

**Current state:** Must SSH into server or modify Railway config to run type-specific generation.

**Evidence:** No skill files exist in `.claude/skills/` for question generation. The `/generate-questions` and `/start-question-service` skills mentioned in CLAUDE.md are referenced but not implemented as skills.

#### Gap 2: No Inventory Monitoring Dashboard

**Current state:** Must run raw SQL queries to check inventory levels:
```sql
SELECT question_type, difficulty_level, COUNT(*)
FROM questions
WHERE is_active = true AND quality_flag = 'normal'
GROUP BY question_type, difficulty_level;
```

**Missing:** Admin endpoint for inventory health check with threshold alerts.

#### Gap 3: No Automated Inventory Balancing

**Current state:** Generation is uniform across all types.

**Missing:** Logic to automatically prioritize underrepresented strata.

## Recommendations

| Priority | Recommendation | Effort | Impact |
|----------|---------------|--------|--------|
| **Critical** | Create `/generate-questions-by-type` skill | Low | High |
| **High** | Add inventory health endpoint to admin API | Medium | High |
| **High** | Pre-release bulk generation script | Low | Critical |
| **Medium** | Auto-balancing generation mode | Medium | Medium |
| **Medium** | Inventory alerting on low strata | Low | Medium |
| **Low** | Redis caching for embedding lookups | Medium | Low |

### Detailed Recommendations

#### 1. Create `/generate-questions-by-type` Skill (Critical)

**Problem:** Operations cannot easily generate questions of specific types without CLI access.

**Solution:** Create a new skill at `.claude/skills/generate-questions-by-type/`:

```markdown
# Generate Questions by Type Skill

Generates questions of specific types to balance inventory.

## Arguments
- `type`: Question type (math, logic, pattern, spatial, verbal, memory)
- `count`: Number to generate (default: 50)
- `difficulty`: Optional difficulty filter (easy, medium, hard)

## Usage
/generate-questions-by-type math 100
/generate-questions-by-type spatial 50 hard
```

**Implementation:** Wrapper that constructs and executes:
```bash
python run_generation.py --types <type> --count <count> --async --async-judge
```

#### 2. Pre-Release Bulk Generation Script (High)

**Problem:** Starting with insufficient inventory risks poor user experience.

**Solution:** Create `scripts/bootstrap_inventory.sh`:

```bash
#!/bin/bash
# Generate initial question inventory across all strata

QUESTIONS_PER_STRATUM=50  # Target: 50 questions per type/difficulty combo

for type in math logic pattern spatial verbal memory; do
    for difficulty in easy medium hard; do
        echo "Generating $type/$difficulty..."
        python run_generation.py \
            --types $type \
            --count $QUESTIONS_PER_STRATUM \
            --async --async-judge \
            --triggered-by bootstrap
    done
done
```

**Timeline:** Run this 1-2 weeks before release to build inventory.

#### 3. Add Inventory Health Endpoint (High)

**Problem:** No programmatic way to check inventory levels.

**Solution:** Add `GET /v1/admin/inventory-health` endpoint:

**Response:**
```json
{
  "total_active_questions": 523,
  "strata": [
    {
      "type": "math",
      "difficulty": "easy",
      "count": 42,
      "status": "healthy"
    },
    {
      "type": "spatial",
      "difficulty": "hard",
      "count": 8,
      "status": "critical"
    }
  ],
  "alerts": [
    "spatial/hard below minimum threshold (10)"
  ]
}
```

**Files affected:**
- `backend/app/api/v1/admin/inventory.py` (new)
- `backend/app/schemas/inventory.py` (new)

#### 4. Auto-Balancing Generation Mode (Medium)

**Problem:** Uniform generation doesn't address inventory gaps.

**Solution:** Add `--auto-balance` flag to `run_generation.py`:

1. Query current inventory levels
2. Identify strata below threshold
3. Prioritize generation for underrepresented strata
4. Generate proportionally to fill gaps

**Implementation location:** `question-service/run_generation.py` and `question-service/app/inventory_analyzer.py` (new)

## Appendix

### Files Analyzed

| Category | Files |
|----------|-------|
| Question Service Core | `run_generation.py`, `app/pipeline.py`, `app/generator.py`, `app/judge.py`, `app/deduplicator.py`, `app/database.py` |
| Configuration | `config/judges.yaml`, `config/generators.yaml`, `app/config.py` |
| Backend | `app/core/test_composition.py`, `app/core/config.py`, `app/api/v1/admin/generation.py` |
| Deployment | `railway-cron.json`, `Dockerfile`, `docker-compose.yml` |
| Documentation | `docs/OPERATIONS.md`, `docs/PERFORMANCE.md`, `README.md` |

### Related Resources

- [Question Service README](../../question-service/README.md)
- [Operations Guide](../../question-service/docs/OPERATIONS.md)
- [Performance Baseline](../../question-service/docs/PERFORMANCE.md)
- [Test Composition Logic](../../backend/app/core/test_composition.py)
- [Railway Deployment](../../backend/DEPLOYMENT.md)

### Question Type Definitions

**File:** `question-service/app/models.py:13-25`

```python
class QuestionType(str, Enum):
    PATTERN = "pattern"      # Pattern and sequence recognition
    LOGIC = "logic"          # Logical reasoning and deduction
    SPATIAL = "spatial"      # 3D visualization and spatial
    MATH = "math"            # Mathematical and numerical problems
    VERBAL = "verbal"        # Language comprehension and analogies
    MEMORY = "memory"        # Working memory and recall tasks
```

### CLI Reference for Type-Specific Generation

```bash
# Generate specific type
python run_generation.py --types math --count 100

# Generate multiple types
python run_generation.py --types math logic --count 50

# Generate with async (faster)
python run_generation.py --types spatial --count 100 --async --async-judge

# Dry run to test
python run_generation.py --types verbal --count 10 --dry-run --verbose

# All available types
python run_generation.py --types pattern logic spatial math verbal memory
```
