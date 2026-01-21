# Analysis: IQ Test Question Categories Alignment

**Date:** 2026-01-20
**Scope:** Verification that AIQ question categories align with established IQ test cognitive domains, with particular focus on memory testing

## Executive Summary

AIQ's question category coverage is well-aligned with standard IQ tests. The codebase includes all six major cognitive domains: Pattern Recognition, Logical Reasoning, Spatial Reasoning, Mathematical Reasoning, Verbal Reasoning, and **Memory**. This matches the structure of established tests like WAIS-IV/WAIS-5 and Stanford-Binet SB5.

The memory category is fully implemented in the codebase - defined in the data models, included in question generation prompts with gold-standard examples, and integrated into test composition. However, the memory implementation in AIQ is a simplified "immediate recall" approach rather than the "presentation-delay-recall" paradigm used in clinical IQ tests like WAIS-IV Digit Span, which is appropriate given the mobile app format.

The analysis found no significant gaps in cognitive domain coverage. AIQ's categories map well to CHC theory's broad abilities and align with both WAIS and Stanford-Binet cognitive factors.

## Methodology

- Examined AIQ's question type definitions in `question-service/app/models.py`
- Reviewed generation prompts in `question-service/app/prompts.py`
- Analyzed methodology documentation in `docs/methodology/METHODOLOGY.md`
- Reviewed backend models in `backend/app/models/models.py`
- Checked test composition logic in `backend/app/core/test_composition.py`
- Researched standard IQ test structures (WAIS-IV, WAIS-5, Stanford-Binet SB5)
- Reviewed CHC (Cattell-Horn-Carroll) theory for comprehensive cognitive ability taxonomy

## Findings

### 1. AIQ Question Categories (Currently Implemented)

| AIQ Category | Enum Value | Full Implementation |
|--------------|------------|---------------------|
| Pattern Recognition | `pattern_recognition` / `pattern` | Yes |
| Logical Reasoning | `logical_reasoning` / `logic` | Yes |
| Spatial Reasoning | `spatial_reasoning` / `spatial` | Yes |
| Mathematical | `mathematical` / `math` | Yes |
| Verbal Reasoning | `verbal_reasoning` / `verbal` | Yes |
| **Memory** | `memory` | **Yes** |

#### Evidence: Memory Category Exists

**Question Service Models** (`question-service/app/models.py:21`):
```python
class QuestionType(str, Enum):
    """Types of IQ test questions."""
    PATTERN_RECOGNITION = "pattern_recognition"
    LOGICAL_REASONING = "logical_reasoning"
    SPATIAL_REASONING = "spatial_reasoning"
    MATHEMATICAL = "mathematical"
    VERBAL_REASONING = "verbal_reasoning"
    MEMORY = "memory"  # ← Memory is included
```

**Backend Models** (`backend/app/models/models.py:36`):
```python
class QuestionType(str, enum.Enum):
    MEMORY = "memory"  # ← Memory is included in backend
```

**Generation Prompts** (`question-service/app/prompts.py:175-201`):
Memory questions have a detailed prompt with:
- Clear requirements for recall-based questions
- Gold-standard example with dual memory + reasoning requirement
- Multiple example types (list recall, sequence memory, passage detail recall)

### 2. Comparison with Standard IQ Tests

#### WAIS-IV/WAIS-5 (Wechsler Adult Intelligence Scale)

| WAIS Index | WAIS Subtests | AIQ Mapping |
|------------|---------------|-------------|
| Verbal Comprehension | Similarities, Vocabulary, Information | Verbal Reasoning |
| Perceptual/Visual-Spatial Reasoning | Block Design, Matrix Reasoning, Visual Puzzles | Pattern Recognition, Spatial Reasoning |
| Working Memory | Digit Span, Arithmetic, Letter-Number Sequencing | **Memory**, Mathematical |
| Processing Speed | Symbol Search, Coding | (Implicit via timing) |
| Fluid Reasoning (WAIS-5) | Figure Weights, Matrix Reasoning | Logical Reasoning, Pattern Recognition |

**Key Finding:** WAIS includes Working Memory as a core index. AIQ's Memory category aligns with this.

#### Stanford-Binet SB5

| SB5 Factor | Description | AIQ Mapping |
|------------|-------------|-------------|
| Fluid Reasoning | Novel problem-solving | Logical Reasoning |
| Knowledge | Acquired information | Verbal Reasoning |
| Quantitative Reasoning | Mathematical operations | Mathematical |
| Visual-Spatial Processing | Mental imagery | Spatial Reasoning, Pattern Recognition |
| **Working Memory** | Hold and manipulate information | **Memory** |

**Key Finding:** Stanford-Binet explicitly includes Working Memory as one of five factors. AIQ covers this.

#### CHC Theory (Cattell-Horn-Carroll)

The CHC taxonomy identifies 16+ broad cognitive abilities. AIQ covers the most commonly assessed:

| CHC Broad Ability | Description | AIQ Coverage |
|------------------|-------------|--------------|
| Gf - Fluid Reasoning | Novel problem-solving | Logical Reasoning |
| Gc - Crystallized Intelligence | Acquired knowledge | Verbal Reasoning |
| Gv - Visual Processing | Visual patterns | Pattern Recognition, Spatial |
| **Gsm - Short-Term Memory** | Immediate awareness | **Memory** |
| Gs - Processing Speed | Cognitive speed | (Implicit via timing) |
| Gq - Quantitative Knowledge | Math knowledge | Mathematical |
| **Glr - Long-Term Storage & Retrieval** | Delayed recall | Partially (see gap analysis) |

### 3. Gap Analysis

#### What AIQ Covers Well

1. **Fluid Intelligence (Gf)** - Covered by Pattern Recognition, Logical Reasoning, Spatial Reasoning
2. **Crystallized Intelligence (Gc)** - Covered by Verbal Reasoning, Mathematical
3. **Working Memory (Gsm)** - Covered by Memory category
4. **Visual-Spatial (Gv)** - Covered by Pattern Recognition, Spatial Reasoning

#### Minor Gaps (Acceptable for Mobile Format)

| Gap | Standard IQ Approach | AIQ Approach | Justification |
|-----|---------------------|--------------|---------------|
| **Processing Speed (Gs)** | Timed tasks with speed emphasis | Implicit via response time tracking | Mobile format favors untimed assessment with timing analytics |
| **Long-Term Retrieval (Glr)** | Delayed recall (15+ minute gap) | Not implemented | Impractical for single-session mobile testing |
| **Auditory Processing (Ga)** | Audio stimuli | Not implemented | Mobile text-based format |

#### Memory Implementation Details

The current memory prompt (`question-service/app/prompts.py:175-201`) describes:

```
MEMORIZE THIS LIST: maple, oak, dolphin, cherry, whale, birch, salmon.
Which item from the list is a mammal that is NOT the fourth item?
```

This tests **working memory + reasoning**, not pure recall. This is appropriate because:
1. Pure recall without reasoning doesn't discriminate ability well
2. Mobile format doesn't support true "presentation-delay-recall" paradigm
3. Combining memory with reasoning load increases discriminatory power

**Note from prompt:** "For actual testing, there would be a delay between presentation and recall. For question generation, clearly separate the 'presentation' and 'question' parts."

The iOS app does not implement a special "memorize phase" UI - memory questions are displayed the same as other questions. This is a simplification but acceptable for the mobile format.

### 4. Methodology Documentation Alignment

The `METHODOLOGY.md` file explicitly documents the Memory category mapping:

```markdown
| AIQ Category | Cognitive Domain |
|--------------|------------------|
| Memory | Working Memory |
```

This confirms the intentional design decision to include memory testing.

## Recommendations

| Priority | Recommendation | Effort | Impact |
|----------|---------------|--------|--------|
| None Critical | Memory is already implemented | N/A | N/A |
| Low | Consider enhanced memory question UI | Medium | Low |
| Low | Add more memory question diversity | Low | Medium |
| Future | Consider processing speed subtests | High | Medium |

### Detailed Recommendations

#### 1. No Action Required for Memory Category

**Status:** Memory questions are already implemented in AIQ.

The category exists in:
- Question type enums (backend and question-service)
- Generation prompts with gold-standard examples
- Test composition (distributed evenly with other domains)
- Analytics tracking (response time by question type includes memory)

#### 2. (Optional) Enhanced Memory Question UI

**Problem:** Current iOS implementation displays memory questions identically to other questions. Users might scroll back and forth between the "memorize" content and the question.

**Solution:** Consider a two-phase UI for memory questions:
1. Show "Memorize this:" with the content
2. After user indicates ready, show only the question (hide the original content)

**Impact:** Would more closely replicate actual working memory testing paradigm.

**Files Affected:** iOS Views (QuestionView, TestActiveView)

#### 3. (Optional) Expand Memory Question Variety

**Current prompt example types:**
- List recall with logical constraint
- Sequence memory
- Detail recall from short passage
- Pattern memory
- Multi-step memory

**Potential additions:**
- Digit span (forward/backward) - classic WAIS subtest
- Letter-number sequencing - WAIS-5 addition
- Spatial memory (remember positions in a grid)

## Appendix

### Files Analyzed

| File | Relevance |
|------|-----------|
| `question-service/app/models.py` | QuestionType enum definition |
| `question-service/app/prompts.py` | Memory question generation prompts |
| `backend/app/models/models.py` | Backend QuestionType enum |
| `backend/app/core/test_composition.py` | Question selection includes all types |
| `docs/methodology/METHODOLOGY.md` | Category mapping documentation |
| `ios/AIQ/Models/Question.swift` | iOS QuestionType enum |

### Related Resources

- [WAIS-IV Overview](https://www.cogn-iq.org/learn/tests/wechsler-adult-intelligence-scale/)
- [Stanford-Binet Subtests](https://www.stanfordbinettest.com/all-about-stanford-binet-test/stanford-binet-subtests)
- [CHC Theory Guide](https://www.cogn-iq.org/learn/theory/chc-theory/)
- [Wikipedia: Cattell-Horn-Carroll Theory](https://en.wikipedia.org/wiki/Cattell–Horn–Carroll_theory)
- [WAIS-5 Comparison (Pearson)](https://www.pearsonassessments.com/content/dam/school/global/clinical/us/assets/wais-5/wais-5-comparison-flyer.pdf)

## Summary

**Answer to the original question:** Yes, AIQ is testing the correct categories that appear in standard IQ tests, including memory. The Memory category is fully implemented with:
- Enum definitions in both backend and question-service
- Detailed generation prompts with gold-standard examples
- Integration into stratified test composition
- Analytics tracking for memory question performance

The memory implementation uses a "working memory + reasoning" approach rather than pure recall with delay, which is appropriate for the mobile app format and aligns with modern IQ testing principles that emphasize working memory manipulation rather than simple memorization.
