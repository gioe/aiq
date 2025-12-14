# Distractor Analysis

## Problem Statement

For multiple-choice questions, AIQ tracks whether answers are correct or incorrect but doesn't analyze the performance of individual wrong answer options (distractors). A well-designed distractor should be plausible enough that some test-takers choose it, but not so attractive that it misleads high-ability examinees.

Non-functioning distractors—those that virtually no one selects—effectively reduce the question to fewer options, changing guessing probability and potentially affecting item difficulty and discrimination.

## What is Distractor Analysis?

Distractor analysis examines the selection frequency and quality of incorrect answer options:

### Key Metrics

1. **Selection Frequency**: What percentage of respondents chose each option?
2. **Distractor Discrimination**: Do high or low scorers preferentially choose each distractor?
3. **Functioning Status**: Is each distractor plausible enough to attract responses?

### Ideal Distractor Properties

| Property | Description |
|----------|-------------|
| Plausible | Chosen by some respondents (>5% selection rate) |
| Discriminating | Chosen more by low scorers than high scorers |
| Non-overlapping | Each distractor attracts different types of errors |

### Red Flags

| Issue | Indicator | Impact |
|-------|-----------|--------|
| Non-functioning | Selected by <5% | Reduces effective options |
| Correct-competitor | Chosen by high scorers | May indicate ambiguity |
| Universal attractor | Chosen by >40% (wrong answer) | May indicate key error or misleading stem |

## Current State

### What Exists

1. **Answer options stored** (`backend/app/models/models.py:130`)
   ```python
   answer_options = Column(JSON)  # JSON array for multiple choice
   ```

2. **User answers recorded** (`backend/app/models/models.py:289`)
   ```python
   user_answer = Column(String(500), nullable=False)
   ```

3. **Correctness tracked** (`backend/app/models/models.py:290`)
   ```python
   is_correct = Column(Boolean, nullable=False)
   ```

### What's Missing

1. **No distractor frequency tracking**
   - Cannot see how often each option is chosen
   - No aggregate statistics per option

2. **No distractor discrimination analysis**
   - Don't know if distractors preferentially attract low scorers
   - Cannot identify "correct-competitor" distractors

3. **No non-functioning distractor detection**
   - Questions may have options no one ever selects
   - Effectively 3-option questions masquerading as 4-option

4. **No reporting or action**
   - Admins cannot see distractor quality
   - No mechanism to improve or replace poor distractors

## Why This Matters

### Measurement Precision

A 4-option question has:
- 25% guessing probability (if all options function)
- 33% guessing probability (if only 3 options function)
- 50% guessing probability (if only 2 options function)

This affects:
- Item difficulty (p-value)
- Reliability
- Score precision

### Question Quality

Distractor analysis reveals:
- **Content issues**: If a distractor is never chosen, it may be obviously wrong
- **Key errors**: If wrong answer attracts high scorers, the key may be wrong
- **Ambiguity**: Multiple highly-selected options suggest unclear question

### AI Generation Insight

For AI-generated questions, distractor analysis provides feedback:
- Which types of distractors work well?
- Are AI-generated distractors too obviously wrong?
- Can we improve generation prompts based on distractor patterns?

## Solution Requirements

### 1. Distractor Frequency Tracking

**Storage Options:**

**Option A: Aggregate on Question model**
```python
# Add to Question model
distractor_stats = Column(JSON, nullable=True)
# Example: {"A": 45, "B": 120, "C": 30, "D": 85}  # selection counts
```

**Option B: Separate tracking table**
```python
class DistractorStat(Base):
    __tablename__ = "distractor_stats"

    id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey("questions.id"))
    option_value = Column(String(500))  # The answer option text or identifier
    selection_count = Column(Integer, default=0)
    selection_by_top_quartile = Column(Integer, default=0)  # High scorers
    selection_by_bottom_quartile = Column(Integer, default=0)  # Low scorers
    last_updated = Column(DateTime)
```

**Recommendation:** Option A for simplicity initially. Option B for detailed discrimination analysis later.

**Update Logic:**
```python
def update_distractor_stats(db: Session, question_id: int, selected_answer: str):
    """
    Increment selection count for the chosen answer option.

    Called after each response is recorded.
    """
    question = db.query(Question).filter(Question.id == question_id).first()

    if not question.distractor_stats:
        # Initialize with zeros for all options
        question.distractor_stats = {opt: 0 for opt in question.answer_options}

    if selected_answer in question.distractor_stats:
        question.distractor_stats[selected_answer] += 1

    db.commit()
```

### 2. Distractor Effectiveness Analysis

**Function:**
```python
def analyze_distractor_effectiveness(
    db: Session,
    question_id: int,
    min_responses: int = 50
) -> Dict:
    """
    Analyze effectiveness of each distractor for a question.

    Returns:
        {
            "question_id": int,
            "total_responses": int,
            "options": [
                {
                    "option": str,
                    "is_correct": bool,
                    "selection_count": int,
                    "selection_rate": float,  # 0.0-1.0
                    "status": str,  # "functioning", "weak", "non-functioning"
                    "top_quartile_rate": float,  # Selection rate among high scorers
                    "bottom_quartile_rate": float,  # Selection rate among low scorers
                    "discrimination": str  # "good", "neutral", "inverted"
                }
            ],
            "non_functioning_count": int,
            "effective_options": int,
            "recommendations": [str]
        }
    """
```

**Status Definitions:**
- **Functioning**: Selected by ≥5% of respondents
- **Weak**: Selected by 2-5% of respondents
- **Non-functioning**: Selected by <2% of respondents

**Discrimination Categories:**
- **Good**: Bottom quartile selects more than top quartile (desired for distractors)
- **Neutral**: Similar selection rates across ability levels
- **Inverted**: Top quartile selects more than bottom quartile (problematic)

### 3. Distractor Quality Endpoint

**Endpoint:** `GET /v1/admin/questions/{id}/distractor-analysis`

**Response:**
```json
{
    "question_id": 123,
    "question_text": "What comes next in the sequence: 2, 4, 8, 16, ?",
    "total_responses": 234,
    "options": [
        {
            "option": "32",
            "is_correct": true,
            "selection_count": 187,
            "selection_rate": 0.80,
            "status": "correct_answer",
            "notes": null
        },
        {
            "option": "24",
            "is_correct": false,
            "selection_count": 28,
            "selection_rate": 0.12,
            "status": "functioning",
            "top_quartile_rate": 0.05,
            "bottom_quartile_rate": 0.18,
            "discrimination": "good"
        },
        {
            "option": "18",
            "is_correct": false,
            "selection_count": 15,
            "selection_rate": 0.06,
            "status": "functioning",
            "top_quartile_rate": 0.04,
            "bottom_quartile_rate": 0.09,
            "discrimination": "good"
        },
        {
            "option": "64",
            "is_correct": false,
            "selection_count": 4,
            "selection_rate": 0.02,
            "status": "non-functioning",
            "top_quartile_rate": 0.01,
            "bottom_quartile_rate": 0.02,
            "discrimination": "neutral",
            "notes": "Too obviously wrong"
        }
    ],
    "summary": {
        "functioning_distractors": 2,
        "non_functioning_distractors": 1,
        "effective_option_count": 3,
        "guessing_probability": 0.33
    },
    "recommendations": [
        "Replace '64' with a more plausible distractor",
        "Consider: 30, 20, or another arithmetic progression error"
    ]
}
```

### 4. Bulk Distractor Report

**Endpoint:** `GET /v1/admin/questions/distractor-summary`

**Response:**
```json
{
    "total_questions_analyzed": 450,
    "questions_with_non_functioning_distractors": 67,
    "questions_with_inverted_distractors": 12,
    "by_non_functioning_count": {
        "0": 320,
        "1": 85,
        "2": 40,
        "3": 5
    },
    "worst_offenders": [
        {
            "question_id": 456,
            "non_functioning_count": 3,
            "effective_options": 1,
            "response_count": 89
        }
    ],
    "by_question_type": {
        "pattern": {"avg_functioning": 3.2, "problematic_pct": 8},
        "logic": {"avg_functioning": 3.5, "problematic_pct": 5},
        "spatial": {"avg_functioning": 3.0, "problematic_pct": 12}
    }
}
```

### 5. Distractor Discrimination Calculation

To calculate distractor discrimination, need to track responses by ability level:

```python
def calculate_distractor_discrimination(
    db: Session,
    question_id: int
) -> Dict[str, Dict]:
    """
    Calculate selection rates by ability quartile for each option.

    Process:
    1. Get all responses for this question with their test session
    2. Get total score for each session
    3. Divide into quartiles by total score
    4. Calculate selection rate per option per quartile
    """
    # Get responses with total scores
    responses = db.query(
        Response.user_answer,
        TestResult.correct_answers
    ).join(
        TestResult,
        Response.test_session_id == TestResult.test_session_id
    ).filter(
        Response.question_id == question_id
    ).all()

    if len(responses) < 40:  # Need enough for quartile analysis
        return {"insufficient_data": True}

    # Sort by total score
    sorted_responses = sorted(responses, key=lambda r: r.correct_answers)

    # Split into quartiles
    n = len(sorted_responses)
    bottom_quartile = sorted_responses[:n//4]
    top_quartile = sorted_responses[3*n//4:]

    # Calculate selection rates per option
    # ... implementation details ...
```

## Implementation Dependencies

### Prerequisites
- Response data exists ✓
- Answer options stored as JSON ✓
- Need ~50 responses per question for meaningful analysis

### Database Changes

**Option A (simpler):** Add to Question model:
```python
distractor_stats = Column(JSON, nullable=True)
# Format: {"option_text": {"count": 50, "top_q": 10, "bottom_q": 25}, ...}
```

**Option B (more flexible):** New table as shown above

### Update Points

1. **After each response**: Increment distractor counts
2. **After each test completion**: Update quartile-based stats (requires total score)

### Related Code Locations
- `backend/app/models/models.py:130` - answer_options field
- `backend/app/models/models.py:289` - user_answer field
- Response creation code - Add distractor stat update
- `backend/app/core/question_analytics.py` - Similar analytics pattern

## Distractor Design Principles

When flagging poor distractors, provide guidance for replacement:

### Good Distractor Types

1. **Common misconception**: Answer that reflects typical error patterns
2. **Partial solution**: Correct approach but calculation error
3. **Related concept**: Plausible but wrong domain
4. **Inverse/opposite**: Reverses the correct relationship

### Poor Distractor Types

1. **Obviously wrong**: No one would choose it
2. **Correct-ish**: Too close to correct, ambiguous
3. **Trick answer**: Only confuses careful thinkers
4. **Random**: No logical connection to question

## Edge Cases

1. **Free-response questions**
   - No distractors to analyze
   - Skip these questions entirely

2. **Variable option counts**
   - Some questions may have 4 options, others 5 or 6
   - Handle dynamically based on answer_options array length

3. **Option format variations**
   - Some options may be text, others numbers, others images
   - Normalize for comparison and storage

4. **Very new questions**
   - Insufficient data for analysis
   - Return "insufficient_data" status

## Success Criteria

1. **Tracking**: Selection frequency recorded for all options on all questions
2. **Detection**: Non-functioning distractors (<5% selection) are flagged
3. **Discrimination**: Inverted distractors (high scorers prefer them) are flagged
4. **Visibility**: Admin can see distractor quality for any question
5. **Actionability**: Report includes recommendations for improvement
6. **Threshold**: <15% of questions have non-functioning distractors

## Testing Strategy

1. **Unit Tests:**
   - Test selection count incrementing
   - Test quartile calculation
   - Test status categorization at boundaries

2. **Integration Tests:**
   - Create question with known options
   - Simulate responses with controlled patterns
   - Verify analysis returns expected results

3. **Edge Cases:**
   - All responses to same option
   - Exactly equal distribution
   - Missing option data

## AI Generation Feedback Loop

Use distractor analysis to improve question generation:

1. **Track by source LLM**: Which LLMs produce better distractors?
2. **Track by question type**: Are some types harder to write distractors for?
3. **Prompt improvement**: Feed back patterns of non-functioning distractors

**Example insight:**
> "GPT-4 spatial reasoning questions have 23% non-functioning distractor rate vs. 8% for Claude. Consider adjusting spatial distractor prompts."

## References

- IQ_METHODOLOGY.md - Question generation quality control
- Classical Test Theory: Distractor analysis
- `backend/app/models/models.py:130` - answer_options field
- `backend/app/models/models.py:289` - user_answer field
