# Sub-Type System & Gold-Standard Examples

## 1. Overview

The sub-type system prevents **mode collapse** during question generation. Without it, LLMs tend to anchor on their favorite variant of each question type (e.g., always generating simple A:B::C:? analogies for verbal reasoning, or always picking cube rotations for spatial).

**High-level flow:**

```
Sub-type selected  →  Prompt narrowed to that sub-type  →  Gold-standard example injected  →  LLM generates  →  sub_type stamped on question  →  Stored in DB
```

Each question type has a set of sub-types extracted from the "Example types" lists in the type-specific prompts. When a question is generated, a sub-type is selected (randomly or via rotation), and the prompt is tailored so the LLM sees only that sub-type as the target.

**Source file:** `app/generation/prompts.py` — `QUESTION_SUBTYPES`, `GOLD_STANDARD_BY_SUBTYPE`, `GOLD_STANDARD_EXAMPLES`, `build_generation_prompt()`

---

## 2. Sub-Type Catalog

65 sub-types across 6 question types.

### Pattern Recognition (10 sub-types)

| # | Sub-Type | Gold Standard |
|---|----------|:---:|
| 1 | number sequences with arithmetic progressions | Mapped |
| 2 | number sequences with geometric or multiplicative rules | — |
| 3 | letter patterns using alphabetic positions or skip patterns | Mapped |
| 4 | alternating or interleaved dual sequences | — |
| 5 | recursive patterns where each term depends on previous terms | — |
| 6 | matrix patterns describing a 3x3 grid with one missing cell | Mapped |
| 7 | shape or symbol transformation sequences | — |
| 8 | modular arithmetic or cyclic patterns | — |
| 9 | difference-of-differences (second-order) sequences | — |
| 10 | combined operation sequences (e.g., +2, x3, +2, x3) | Mapped |

### Logical Reasoning (10 sub-types)

| # | Sub-Type | Gold Standard |
|---|----------|:---:|
| 1 | syllogisms (All A are B, Some B are C, therefore...) | Mapped |
| 2 | if-then conditional reasoning with valid and invalid inferences | — |
| 3 | set theory and Venn diagram logic | — |
| 4 | ordering and ranking puzzles from comparative clues | Mapped |
| 5 | truth-teller and liar puzzles | — |
| 6 | necessary vs. sufficient condition identification | — |
| 7 | elimination puzzles using process of elimination | Mapped |
| 8 | logical equivalence and contrapositive reasoning | Mapped |
| 9 | multi-constraint deductive puzzles (Einstein-style, simplified) | — |
| 10 | categorical classification with overlapping properties | — |

### Spatial Reasoning (12 sub-types)

| # | Sub-Type | Gold Standard |
|---|----------|:---:|
| 1 | cube rotations tracking labeled faces through sequential turns | Mapped |
| 2 | paper folding with holes or cuts, predicting unfolded result | — |
| 3 | 2D net folding into 3D cubes or boxes | — |
| 4 | mirror and reflection of 2D shapes across an axis | — |
| 5 | cross-section identification from slicing a 3D solid | Mapped |
| 6 | mental rotation of 2D shapes (which rotated shape matches?) | — |
| 7 | map or compass navigation (follow directions, determine final position) | Mapped |
| 8 | shape fitting or tangram-style assembly into a target outline | — |
| 9 | perspective taking (what does a 3D object look like from another angle?) | Mapped |
| 10 | symmetry identification (line/rotational symmetry of a figure) | — |
| 11 | coordinate grid transformations (translate, rotate, reflect a shape on a grid) | — |
| 12 | counting faces, edges, or vertices of described 3D objects | — |

### Mathematical (10 sub-types)

| # | Sub-Type | Gold Standard |
|---|----------|:---:|
| 1 | word problems with practical everyday contexts | — |
| 2 | number theory involving LCM, GCD, or divisibility | Mapped |
| 3 | proportional reasoning with ratios, rates, or scaling | Mapped |
| 4 | algebraic thinking with unknown quantities or pattern generalization | — |
| 5 | logical-mathematical puzzles with digit or arithmetic constraints | — |
| 6 | combinatorics and counting problems | Mapped |
| 7 | probability and likelihood reasoning | Mapped |
| 8 | fraction, percentage, or unit conversion reasoning | — |
| 9 | age, distance, or work-rate relationship problems | — |
| 10 | estimation and number sense problems | — |

### Verbal Reasoning (15 sub-types)

| # | Sub-Type | Gold Standard |
|---|----------|:---:|
| 1 | analogies with part-whole relationships | Mapped |
| 2 | analogies with cause-effect or function relationships | Mapped |
| 3 | analogies with tool-user or creator-creation relationships | — |
| 4 | odd one out identifying the item that doesn't share a category or property | Mapped |
| 5 | word classification grouping words by shared semantic feature | — |
| 6 | sentence completion where context determines the correct word | Mapped |
| 7 | synonym or antonym selection | — |
| 8 | semantic reasoning about described relationships | — |
| 9 | sequence completion with conceptually ordered words | — |
| 10 | verbal inference drawing a conclusion from a short statement | — |
| 11 | multi-layered analogies requiring recognition of two simultaneous relationship types | Mapped* |
| 12 | verbal inference chains combining 2-3 premises to reach a non-obvious conclusion | Mapped |
| 13 | abstract cross-domain analogies connecting unrelated fields via a shared principle | Mapped* |
| 14 | multi-clause sentence completion with complex rhetorical structure | Mapped** |
| 15 | embedded verbal constraint satisfaction requiring 3+ semantic conditions | Mapped** |

\* Sub-types 11 and 13 share the same gold-standard example (multi-layered analogy, example index [4]).
\** Sub-types 14 and 15 share the same gold-standard example (rhetorical completion, example index [6]).

### Memory (8 sub-types)

| # | Sub-Type | Gold Standard |
|---|----------|:---:|
| 1 | list recall with logical constraint | Mapped |
| 2 | sequence memory with position-based recall | Mapped |
| 3 | detail recall from a short passage of 2-3 sentences | Mapped |
| 4 | pattern memory with number or letter sequences to recall and identify | — |
| 5 | multi-step memory requiring remember, transform, and recall | — |
| 6 | spatial memory recalling positions or arrangements | — |
| 7 | associative memory recalling paired items or attributes | — |
| 8 | temporal order memory recalling the sequence of events | Mapped |

---

## 3. Selection Mechanism

Sub-type selection happens in the generator (`app/generation/generator.py`) and varies by generation path.

### Single question (sync or async)

```python
# generator.py:171-173, 661-663
subtypes = QUESTION_SUBTYPES.get(question_type, [])
subtype = random.choice(subtypes) if subtypes else None
```

A single sub-type is chosen uniformly at random and passed to the prompt builder.

### Chunked batches (`_generate_chunked_batch_async`)

For large batches that exceed `max_batch_size`, the batch is split into sub-batches (e.g., 25 questions with `max_batch_size=10` becomes `[10, 10, 5]`). Each sub-batch gets a different sub-type via sequential rotation from a random start index:

```python
# generator.py:1196-1207
subtypes = QUESTION_SUBTYPES.get(question_type, [])
start_idx = random.randint(0, len(subtypes) - 1)

for i, sub_count in enumerate(sub_batch_sizes):
    subtype = subtypes[(start_idx + i) % len(subtypes)]
```

This cycling ensures diversity across sub-batches without repeating a sub-type until all have been used. Sub-batches run in parallel via `asyncio.gather()`.

### Non-chunked single-call batches

When the batch fits in a single API call (count <= `max_batch_size`), a single random sub-type is picked for the entire batch:

```python
# generator.py:935-936
subtypes = QUESTION_SUBTYPES.get(question_type, [])
subtype = random.choice(subtypes) if subtypes else None
```

---

## 4. Gold-Standard Examples

### What they are

Gold-standard examples are hand-crafted ideal questions included in the LLM prompt as few-shot demonstrations. Each example contains:

- **Question text** with answer options
- **Correct answer**
- **Detailed explanation** of the reasoning
- **Quality notes** describing what makes it a good question

### Example pool per type

| Type | Examples | Index Range |
|------|:--------:|:-----------:|
| Pattern | 4 | [0]–[3] |
| Logic | 4 | [0]–[3] |
| Spatial | 4 | [0]–[3] |
| Math | 4 | [0]–[3] |
| Verbal | 7 | [0]–[6] |
| Memory | 4 | [0]–[3] |
| **Total** | **27** | |

These live in `GOLD_STANDARD_EXAMPLES` in `app/generation/prompts.py` (lines 210–448).

### The `GOLD_STANDARD_BY_SUBTYPE` mapping

The mapping (`app/generation/prompts.py`, lines 625–741) has **29 entries** covering **29 of 65 sub-types**. It maps sub-type strings to their best-matching gold-standard example so the few-shot demonstration reinforces (rather than contradicts) the assigned sub-type.

**Shared mappings:** Two pairs of verbal sub-types share the same example:
- `multi-layered analogies` and `abstract cross-domain analogies` → both use example [4] (Fossil:Paleontologist)
- `multi-clause sentence completion` and `embedded verbal constraint satisfaction` → both use example [6] (precision...pedantic)

### Fallback behavior

When a sub-type has no entry in `GOLD_STANDARD_BY_SUBTYPE`, the prompt builder falls back to `random.choice()` from the full example pool for that question type:

```python
# prompts.py:806-811
if subtype and subtype in GOLD_STANDARD_BY_SUBTYPE:
    gold_standard = GOLD_STANDARD_BY_SUBTYPE[subtype]
else:
    gold_standard = random.choice(GOLD_STANDARD_EXAMPLES[question_type])
```

---

## 5. Prompt Assembly

`build_generation_prompt()` (`app/generation/prompts.py`, lines 770–860) assembles the final LLM prompt in five steps:

### Step 1: Load base prompt + difficulty instructions

```python
type_prompt = QUESTION_TYPE_PROMPTS[question_type]
diff_instructions = TYPE_DIFFICULTY_OVERRIDES.get(
    (question_type, difficulty), DIFFICULTY_INSTRUCTIONS[difficulty]
)
```

`TYPE_DIFFICULTY_OVERRIDES` provides custom difficulty instructions for specific type-difficulty combinations. Currently two overrides exist:
- **MATH / EASY** — Restricts to single arithmetic operations, whole numbers under 100, no multi-step problems
- **VERBAL / HARD** — Requires multi-step verbal reasoning with structural complexity (multi-layered analogies, inference chains, cross-domain mapping, etc.)

All other combinations use the generic `DIFFICULTY_INSTRUCTIONS` for their difficulty level.

### Step 2: Narrow "Example types" list

When a sub-type is provided, the full menu of example types in the base prompt is replaced with just the assigned sub-type:

```python
type_prompt = re.sub(
    r"Example types:\n(?:- .*\n)+",
    f"Example types:\n- {subtype}\n",
    type_prompt,
)
```

This prevents the LLM from seeing all options and defaulting to its favorite.

### Step 3: Select gold-standard example

The matched example is looked up in `GOLD_STANDARD_BY_SUBTYPE`; if unmapped, a random example from the type's pool is used (see Section 4).

### Step 4: Add "REQUIRED SUB-TYPE" directive

```
REQUIRED SUB-TYPE: You MUST generate '{subtype}' questions for this batch.
Do NOT generate questions of other sub-types (e.g., do not generate cube rotation
questions if the required sub-type is mirror/reflection).
Vary the specific scenarios, objects, and transformations within this sub-type.
```

### Step 5: Assemble final prompt

The components are concatenated:

```
{SYSTEM_PROMPT}
{type_prompt}          ← with narrowed Example types
{gold_standard}        ← matched or random fallback
{diff_instructions}    ← with type-difficulty override if applicable
{diversity_instruction} ← REQUIRED SUB-TYPE directive
Generate {count} unique, high-quality question(s) of type '{type}' at '{difficulty}' difficulty.
...response format instructions...
```

For memory questions, an additional `stimulus` field instruction is included in the response format.

---

## 6. Data Flow Through Pipeline

### Generation → Storage

```
Generator selects sub-type
    ↓
build_generation_prompt(subtype=...) assembles prompt
    ↓
LLM generates question(s)
    ↓
Parser returns GeneratedQuestion
    ↓
Generator stamps question.sub_type = subtype
    ↓
Judge evaluates → approved questions pass through
    ↓
Deduplication
    ↓
question.to_dict() → stored in DB (sub_type included)
```

### Sub-type stamping locations

| Path | File | Line | Code |
|------|------|:----:|------|
| Single sync | `generator.py` | 248 | `question.sub_type = subtype` |
| Single async | `generator.py` | 746 | `question.sub_type = subtype` |
| Batch single-call | `generator.py` | 1521–1523 | `for q in questions: q.sub_type = subtype` |
| Regeneration | `generator.py` | 1721 | `question.sub_type = original_question.sub_type` |

### Regeneration

When a question fails judge evaluation and is regenerated with feedback, the **original sub_type is preserved** on the new question. The regeneration prompt builder (`build_regeneration_prompt()`) does NOT use the sub-type to re-narrow the prompt — it rebuilds context from the original question and judge feedback.

### Salvage paths

Rejected questions go through up to three recovery attempts before full regeneration. In both salvage strategies, sub_type is explicitly preserved:

1. **Answer repair** (`run_generation.py:338`) — `sub_type=question.sub_type` passed to the new `GeneratedQuestion` constructor
2. **Difficulty reclassification** (`run_generation.py:443`) — `sub_type=question.sub_type` passed to the new `GeneratedQuestion` constructor
3. **Regeneration with feedback** — Sub-type preserved via `question.sub_type = original_question.sub_type` (see table above)

---

## 7. Coverage Summary

### Per-type coverage

| Type | Total Sub-Types | Mapped | Unmapped | Coverage |
|------|:-:|:-:|:-:|:-:|
| Pattern | 10 | 4 | 6 | 40% |
| Logic | 10 | 4 | 6 | 40% |
| Spatial | 12 | 4 | 8 | 33% |
| Math | 10 | 4 | 6 | 40% |
| Verbal | 15 | 9 | 6 | 60% |
| Memory | 8 | 4 | 4 | 50% |
| **Total** | **65** | **29** | **36** | **45%** |

### Unmapped sub-types by type

**Pattern (6):**
- number sequences with geometric or multiplicative rules
- alternating or interleaved dual sequences
- recursive patterns where each term depends on previous terms
- shape or symbol transformation sequences
- modular arithmetic or cyclic patterns
- difference-of-differences (second-order) sequences

**Logic (6):**
- if-then conditional reasoning with valid and invalid inferences
- set theory and Venn diagram logic
- truth-teller and liar puzzles
- necessary vs. sufficient condition identification
- multi-constraint deductive puzzles (Einstein-style, simplified)
- categorical classification with overlapping properties

**Spatial (8):**
- paper folding with holes or cuts, predicting unfolded result
- 2D net folding into 3D cubes or boxes
- mirror and reflection of 2D shapes across an axis
- mental rotation of 2D shapes (which rotated shape matches?)
- shape fitting or tangram-style assembly into a target outline
- symmetry identification (line/rotational symmetry of a figure)
- coordinate grid transformations (translate, rotate, reflect a shape on a grid)
- counting faces, edges, or vertices of described 3D objects

**Math (6):**
- word problems with practical everyday contexts
- algebraic thinking with unknown quantities or pattern generalization
- logical-mathematical puzzles with digit or arithmetic constraints
- fraction, percentage, or unit conversion reasoning
- age, distance, or work-rate relationship problems
- estimation and number sense problems

**Verbal (6):**
- analogies with tool-user or creator-creation relationships
- word classification grouping words by shared semantic feature
- synonym or antonym selection
- semantic reasoning about described relationships
- sequence completion with conceptually ordered words
- verbal inference drawing a conclusion from a short statement

**Memory (4):**
- pattern memory with number or letter sequences to recall and identify
- multi-step memory requiring remember, transform, and recall
- spatial memory recalling positions or arrangements
- associative memory recalling paired items or attributes
