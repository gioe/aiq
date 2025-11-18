"""Prompt templates for question generation.

This module contains the prompts used to generate different types of
IQ test questions from various LLM providers.
"""

from typing import Dict

from .models import DifficultyLevel, QuestionType

# Base system prompt for all question generation
SYSTEM_PROMPT = """You are an expert psychometrician and IQ test designer with deep knowledge of cognitive assessment.
Your task is to generate high-quality, scientifically valid IQ test questions that accurately measure cognitive abilities.

CONTEXT: These questions are for a mobile IQ tracking app where users take tests periodically (every 3 months)
to monitor their cognitive performance over time. Questions must be:
- Suitable for repeated testing (highly original, not memorizable)
- Optimized for mobile display (concise, clear formatting)
- Aligned with established IQ testing principles (Wechsler, Stanford-Binet, Raven's Progressive Matrices)

IQ TESTING PRINCIPLES:
- Measure fluid intelligence (problem-solving, pattern recognition) and crystallized intelligence (knowledge, reasoning)
- Questions should have good discriminatory power (distinguish between different ability levels)
- Distractors (wrong answers) should be plausible but definitively incorrect
- Avoid floor/ceiling effects (questions too easy or too hard for target population)
- Cultural fairness: avoid region-specific knowledge, idioms, or culturally-biased content

KEY REQUIREMENTS:
✓ Clear, unambiguous wording with a single objectively correct answer
✓ Original and creative (avoid well-known puzzles like Monty Hall, Tower of Hanoi, common riddles)
✓ Appropriate difficulty calibration for specified level
✓ Culturally neutral and globally accessible
✓ Concise question text (ideally under 300 characters for mobile readability)
✓ High-quality distractors that test understanding, not just guessing
✓ Clear, pedagogical explanations

ANTI-PATTERNS TO AVOID:
✗ Ambiguous wording or multiple valid interpretations
✗ Questions requiring specialized knowledge (advanced mathematics, obscure vocabulary, cultural references)
✗ Trick questions or gotchas that test attention rather than reasoning
✗ Overly verbose or complex sentence structures
✗ Distractors that are obviously wrong or random numbers/letters
✗ Questions found in common IQ test prep materials
✗ Content that could be easily memorized and recognized on retesting
"""

# Question type-specific generation prompts
QUESTION_TYPE_PROMPTS: Dict[QuestionType, str] = {
    QuestionType.PATTERN_RECOGNITION: """Generate a pattern recognition question that tests the ability to identify visual or logical patterns.

Requirements:
- Present a sequence or pattern (can be numbers, letters, shapes, or symbols)
- The test-taker must identify the next item in the sequence or the missing item
- The pattern should have a clear logical rule
- Provide 4-6 answer options including distractors
- Include an explanation of the pattern rule

GOLD STANDARD EXAMPLE:
Question: "What comes next in the sequence? 3, 6, 11, 18, 27, ?"
Options: ["36", "38", "40", "42", "44"]
Answer: "38"
Explanation: "Each number increases by consecutive odd numbers: +3, +5, +7, +9, +11. So 27 + 11 = 38."

Quality notes: Clear progression rule, plausible distractors (other arithmetic progressions), concise wording.

Example types:
- Number sequences with arithmetic/geometric progressions
- Letter patterns (alphabetic positions, skip patterns)
- Visual pattern descriptions (rotating shapes, size progressions)
- Matrix patterns (describe a 3x3 grid with one missing cell)
- Alternating or recursive patterns
""",
    QuestionType.LOGICAL_REASONING: """Generate a logical reasoning question that tests deductive or inductive reasoning abilities.

Requirements:
- Present a logical scenario, syllogism, or reasoning puzzle
- The test-taker must draw a valid logical conclusion
- Avoid trick questions; focus on valid logical inference
- Provide 4-6 answer options including plausible distractors
- Include an explanation of the logical reasoning process

GOLD STANDARD EXAMPLE:
Question: "All musicians can read sheet music. Some musicians are teachers. Which statement must be true?"
Options: [
  "All teachers can read sheet music",
  "Some teachers can read sheet music",
  "All people who read sheet music are musicians",
  "Some musicians who teach cannot read sheet music"
]
Answer: "Some teachers can read sheet music"
Explanation: "Since some musicians are teachers, and all musicians can read sheet music, it follows that at least some teachers (those who are musicians) can read sheet music. We cannot conclude that ALL teachers can read music since only some are musicians."

Quality notes: Tests syllogistic reasoning, distractors exploit common logical fallacies, clear and unambiguous.

Example types:
- Syllogisms (All A are B, Some B are C, therefore...)
- If-then reasoning with valid/invalid inferences
- Set theory problems (Venn diagram logic)
- Deductive puzzles from given facts
- Necessary vs. sufficient conditions
""",
    QuestionType.SPATIAL_REASONING: """Generate a spatial reasoning question that tests the ability to visualize and manipulate objects in space.

Requirements:
- Present a spatial transformation problem (rotations, folding, 3D visualization)
- The test-taker must mentally manipulate shapes or objects
- Describe shapes and transformations clearly in text
- Provide 4-6 answer options including similar but incorrect options
- Include an explanation of the spatial transformation

GOLD STANDARD EXAMPLE:
Question: "A cube has different symbols on each face: ★ on top, ● on bottom, ■ on front, ▲ on back, ◆ on left, and ✦ on right. If you rotate the cube 90° forward (top face moves to front), then 90° clockwise (when viewed from above), which symbol is now on top?"
Options: ["★", "●", "■", "▲", "◆"]
Answer: "◆"
Explanation: "After rotating forward 90°: ● moves to front, ★ moves to back, ■ moves to top, ▲ moves to bottom. Then rotating 90° clockwise from above: ◆ (left) moves to top."

Quality notes: Tests sequential 3D visualization, requires mental manipulation, clear face labeling.

Example types:
- Cube rotations with labeled faces
- Paper folding sequences with holes/marks
- 3D object assembly from 2D nets
- Mirror/reflection problems
- Cross-section identification (what shape results from slicing a 3D object)
""",
    QuestionType.MATHEMATICAL: """Generate a mathematical reasoning question that tests quantitative and numerical reasoning.

Requirements:
- Present a mathematical problem requiring reasoning, not just calculation
- Focus on problem-solving rather than arithmetic
- The difficulty should be appropriate for the specified level
- Provide 4-6 answer options with numerical answers
- Include a step-by-step explanation of the solution

GOLD STANDARD EXAMPLE:
Question: "A store sells apples in bags of 6 and oranges in bags of 8. If you buy the same number of apples and oranges, what is the minimum number of each fruit you must buy?"
Options: ["12", "16", "24", "32", "48"]
Answer: "24"
Explanation: "We need the least common multiple (LCM) of 6 and 8. Factors: 6 = 2 × 3, 8 = 2³. LCM = 2³ × 3 = 24. You need 4 bags of apples (4 × 6 = 24) and 3 bags of oranges (3 × 8 = 24)."

Quality notes: Tests LCM concept through practical context, requires reasoning not just calculation, appropriate distractors.

Example types:
- Word problems with practical contexts (avoiding culturally-specific scenarios)
- Number theory (LCM, GCD, divisibility patterns)
- Proportional reasoning (ratios, rates, scaling)
- Algebraic thinking (pattern generalization, unknown quantities)
- Logical-mathematical puzzles (digit problems, arithmetic constraints)
""",
    QuestionType.VERBAL_REASONING: """Generate a verbal reasoning question that tests language comprehension and reasoning.

Requirements:
- Present analogies, word relationships, or vocabulary problems
- Test understanding of meaning and relationships, not just vocabulary knowledge
- Questions should require reasoning about conceptual connections
- Provide 4-6 answer options
- Include an explanation of the relationship or reasoning
- Use common vocabulary (avoid obscure or highly technical terms)

GOLD STANDARD EXAMPLE:
Question: "Book is to Chapter as Building is to ____"
Options: ["Floor", "Brick", "Foundation", "Architect", "City"]
Answer: "Floor"
Explanation: "A book is divided into chapters; similarly, a building is divided into floors. The relationship is 'whole to major subdivision.' Brick is too small (a component), Foundation is a specific part, Architect is the creator, and City is a larger container."

Quality notes: Tests hierarchical relationship reasoning, uses common words, distractors test different relationship types.

Example types:
- Analogies (testing various relationship types: part-whole, cause-effect, function, category)
- Odd one out (identify item that doesn't share a property)
- Word relationships (synonyms, antonyms, category membership)
- Inference from context (complete a sentence where meaning determines the answer)
- Semantic reasoning (which word fits a described relationship)
""",
    QuestionType.MEMORY: """Generate a memory-based question that tests working memory and recall.

Requirements:
- Present information to be remembered (list, sequence, or passage)
- Ask a question that requires recalling specific details
- The memory load should be appropriate for the difficulty level
- Provide 4-6 answer options
- Include an explanation referencing the original information

GOLD STANDARD EXAMPLE:
Question: "MEMORIZE THIS LIST: maple, oak, dolphin, cherry, whale, birch, salmon. Which item from the list is a mammal that is NOT the fourth item?"
Options: ["dolphin", "whale", "salmon", "cherry", "oak"]
Answer: "whale"
Explanation: "The mammals in the list are dolphin and whale. The fourth item is cherry (not a mammal). Therefore, whale is the mammal that is not the fourth item."

Quality notes: Tests both memory retention and logical reasoning, clear structure, appropriate cognitive load.

Example types:
- List recall with logical constraint (remember items, then answer question requiring reasoning)
- Sequence memory (position-based recall)
- Detail recall from short passage (2-3 sentences)
- Pattern memory (number/letter sequences to recall and identify)
- Multi-step memory (remember, transform, recall)

Note: For actual testing, there would be a delay between presentation and recall.
For question generation, clearly separate the "presentation" and "question" parts.
""",
}

# Difficulty-specific instructions
DIFFICULTY_INSTRUCTIONS: Dict[DifficultyLevel, str] = {
    DifficultyLevel.EASY: """Difficulty: EASY
- Suitable for most adults with average cognitive ability
- Pattern or logic should be straightforward and recognizable
- Single-step or simple two-step reasoning
- Common knowledge sufficient (no specialized expertise needed)
- Distractors should be clearly wrong to someone who understands the concept
- Target success rate: ~70-80% of general population
- IQ range: Effectively measures differences in the 85-115 range
- Discriminatory power: Should still differentiate between average and above-average
""",
    DifficultyLevel.MEDIUM: """Difficulty: MEDIUM
- Suitable for above-average problem solvers
- Pattern or logic requires careful analysis and thought
- Multi-step reasoning or non-obvious pattern identification
- May involve integration of multiple concepts
- Distractors should be plausible and test partial understanding
- Target success rate: ~40-60% of general population
- IQ range: Effectively measures differences in the 100-130 range
- Discriminatory power: Should clearly separate average from high performers
""",
    DifficultyLevel.HARD: """Difficulty: HARD
- Suitable for high-performing individuals (top 10-15%)
- Complex patterns requiring abstract thinking or creative insight
- Multi-step logic with non-obvious intermediate steps
- May require working memory to hold multiple constraints
- Distractors should be sophisticated and appeal to incomplete reasoning
- Target success rate: ~10-30% of general population
- IQ range: Effectively measures differences in the 115-145+ range
- Discriminatory power: Should identify genuinely exceptional reasoning ability
- Avoid making questions hard through obscurity; difficulty should come from cognitive demand
""",
}

# JSON response format specification
JSON_RESPONSE_FORMAT = {
    "type": "object",
    "properties": {
        "question_text": {
            "type": "string",
            "description": "The complete question text",
        },
        "correct_answer": {"type": "string", "description": "The correct answer"},
        "answer_options": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Array of 4-6 answer options including the correct answer",
        },
        "explanation": {
            "type": "string",
            "description": "Detailed explanation of why the answer is correct",
        },
    },
    "required": ["question_text", "correct_answer", "answer_options", "explanation"],
}


def build_generation_prompt(
    question_type: QuestionType, difficulty: DifficultyLevel, count: int = 1
) -> str:
    """Build a complete generation prompt for a specific question type and difficulty.

    Args:
        question_type: Type of question to generate
        difficulty: Difficulty level
        count: Number of questions to generate (default: 1)

    Returns:
        Complete prompt string for the LLM
    """
    type_prompt = QUESTION_TYPE_PROMPTS[question_type]
    diff_instructions = DIFFICULTY_INSTRUCTIONS[difficulty]

    prompt = f"""{SYSTEM_PROMPT}

{type_prompt}

{diff_instructions}

Generate {count} unique, high-quality {"question" if count == 1 else "questions"} of type '{question_type.value}' at '{difficulty.value}' difficulty.

IMPORTANT: Respond with valid JSON only. Do not include any text outside the JSON structure.

For each question, provide:
1. question_text: The complete question statement
2. correct_answer: The correct answer (must be one of the answer_options)
3. answer_options: An array of 4-6 options (must include correct_answer)
4. explanation: A clear explanation of why the answer is correct

{"If generating multiple questions, return an array of question objects." if count > 1 else "Return a single question object."}
"""

    return prompt.strip()


def build_arbiter_prompt(
    question: str,
    answer_options: list[str],
    correct_answer: str,
    question_type: str,
    difficulty: str,
) -> str:
    """Build an evaluation prompt for the arbiter to score a question.

    Args:
        question: The question text
        answer_options: List of answer options
        correct_answer: The correct answer
        question_type: Type of question
        difficulty: Difficulty level

    Returns:
        Prompt string for arbiter evaluation
    """
    return f"""You are an expert psychometrician evaluating IQ test questions for a mobile app used for longitudinal cognitive tracking.

CONTEXT: These questions will be used for repeated testing every 3 months. They must be highly original, suitable for mobile display, and aligned with established IQ testing principles (Wechsler, Stanford-Binet, Raven's).

Evaluate the following question across these criteria:

1. CLARITY (0.0-1.0):
   - Is wording unambiguous and clear?
   - Is the question concise enough for mobile display (ideally <300 characters)?
   - Can it be understood without multiple readings?

2. DIFFICULTY (0.0-1.0):
   - Is difficulty appropriate for {difficulty} level?
   - EASY: ~70-80% success rate, tests basic understanding
   - MEDIUM: ~40-60% success rate, requires multi-step reasoning
   - HARD: ~10-30% success rate, requires abstract/creative thinking
   - Does cognitive demand match the target, not just obscure knowledge?

3. VALIDITY (0.0-1.0):
   - Does it genuinely measure {question_type} cognitive ability?
   - Is there ONE objectively correct answer?
   - Is it culturally neutral (no region-specific knowledge, idioms, or bias)?
   - Does it align with psychometric best practices?

4. FORMATTING (0.0-1.0):
   - Are there 4-6 answer options?
   - Is the correct answer included in the options?
   - Are distractors plausible and well-designed (not obviously wrong)?
   - Do distractors test understanding rather than random guessing?

5. CREATIVITY (0.0-1.0):
   - Is the question original and unlikely to be recognized on retesting?
   - Avoids well-known puzzles (Monty Hall, Tower of Hanoi, common riddles)?
   - Would it feel fresh even to someone who took an IQ test recently?
   - Does it show innovative problem design?

Question to evaluate:
---
Type: {question_type}
Difficulty: {difficulty}

Question: {question}

Answer Options:
{chr(10).join(f"  {i+1}. {opt}" for i, opt in enumerate(answer_options))}

Correct Answer: {correct_answer}
---

Respond with valid JSON matching this exact structure:
{{
    "clarity_score": <float 0.0-1.0>,
    "difficulty_score": <float 0.0-1.0>,
    "validity_score": <float 0.0-1.0>,
    "formatting_score": <float 0.0-1.0>,
    "creativity_score": <float 0.0-1.0>,
    "feedback": "<brief explanation of scores and any issues>"
}}

Be rigorous in your evaluation. Questions must score above 0.7 in ALL categories to be acceptable.
A question with even one weak dimension should be rejected.
"""
