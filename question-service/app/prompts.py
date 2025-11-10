"""Prompt templates for question generation.

This module contains the prompts used to generate different types of
IQ test questions from various LLM providers.
"""

from typing import Dict

from .models import DifficultyLevel, QuestionType

# Base system prompt for all question generation
SYSTEM_PROMPT = """You are an expert psychometrician and IQ test designer with deep knowledge of cognitive assessment.
Your task is to generate high-quality, scientifically valid IQ test questions that accurately measure cognitive abilities.

Key requirements:
- Questions must be clear, unambiguous, and have a single correct answer
- Questions should be original and creative (avoid common or well-known puzzles)
- Difficulty should be appropriate for the specified level
- Questions must be culturally neutral and accessible
- Include clear explanations for why the answer is correct
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

Example types:
- Number sequences (e.g., 2, 4, 8, 16, ?)
- Letter patterns (e.g., A, C, F, J, ?)
- Visual pattern descriptions (e.g., rotating shapes, size progressions)
- Matrix patterns (describe a 3x3 grid with one missing cell)
""",
    QuestionType.LOGICAL_REASONING: """Generate a logical reasoning question that tests deductive or inductive reasoning abilities.

Requirements:
- Present a logical scenario, syllogism, or reasoning puzzle
- The test-taker must draw a valid logical conclusion
- Avoid trick questions; focus on valid logical inference
- Provide 4-6 answer options including plausible distractors
- Include an explanation of the logical reasoning process

Example types:
- Syllogisms (All A are B, All B are C, therefore...)
- If-then reasoning (If X, then Y. X is true, therefore...)
- Set theory problems (Venn diagram logic)
- Deductive puzzles (Given facts, what must be true?)
""",
    QuestionType.SPATIAL_REASONING: """Generate a spatial reasoning question that tests the ability to visualize and manipulate objects in space.

Requirements:
- Present a spatial transformation problem (rotations, folding, 3D visualization)
- The test-taker must mentally manipulate shapes or objects
- Describe shapes and transformations clearly in text
- Provide 4-6 answer options including similar but incorrect options
- Include an explanation of the spatial transformation

Example types:
- Paper folding (describe folding sequence, ask what it looks like unfolded)
- 3D object rotation (describe a shape and its rotation, ask for resulting view)
- Shape assembly (which pieces combine to form a target shape?)
- Mirror images (which option is the mirror image of the given shape?)
""",
    QuestionType.MATHEMATICAL: """Generate a mathematical reasoning question that tests quantitative and numerical reasoning.

Requirements:
- Present a mathematical problem requiring reasoning, not just calculation
- Focus on problem-solving rather than arithmetic
- The difficulty should be appropriate for the specified level
- Provide 4-6 answer options with numerical answers
- Include a step-by-step explanation of the solution

Example types:
- Word problems (age problems, distance/rate/time, mixture problems)
- Number theory (prime numbers, divisibility, factors)
- Algebra (solve for x, system of equations)
- Probability or combinatorics (simple counting problems)
""",
    QuestionType.VERBAL_REASONING: """Generate a verbal reasoning question that tests language comprehension and reasoning.

Requirements:
- Present an analogies, word relationships, or vocabulary problem
- Test understanding of meaning, not just vocabulary knowledge
- Questions should require reasoning about word relationships
- Provide 4-6 answer options
- Include an explanation of the relationship or reasoning

Example types:
- Analogies (A is to B as C is to ?)
- Word relationships (odd one out, categorization)
- Sentence completion (choose word that best completes meaning)
- Logical reading (brief passage with an inference question)
""",
    QuestionType.MEMORY: """Generate a memory-based question that tests working memory and recall.

Requirements:
- Present information to be remembered (list, sequence, or passage)
- Ask a question that requires recalling specific details
- The memory load should be appropriate for the difficulty level
- Provide 4-6 answer options
- Include an explanation referencing the original information

Example types:
- List recall (provide a list, ask which item was included)
- Sequence memory (provide a sequence, ask for a specific position)
- Detail recall (provide a short passage, ask about a specific detail)
- Pattern memory (show a pattern, ask to identify it from options)

Note: For actual testing, there would be a delay between presentation and recall.
For question generation, clearly separate the "presentation" and "question" parts.
""",
}

# Difficulty-specific instructions
DIFFICULTY_INSTRUCTIONS: Dict[DifficultyLevel, str] = {
    DifficultyLevel.EASY: """Difficulty: EASY
- Suitable for most adults
- Pattern or logic should be straightforward
- Minimal steps to solution
- Common knowledge sufficient
- Target: ~70-80% of test-takers should answer correctly
""",
    DifficultyLevel.MEDIUM: """Difficulty: MEDIUM
- Suitable for above-average problem solvers
- Pattern or logic requires more thought
- Multiple-step reasoning may be needed
- Some specialized knowledge may help
- Target: ~40-60% of test-takers should answer correctly
""",
    DifficultyLevel.HARD: """Difficulty: HARD
- Suitable for high-performing individuals
- Complex patterns or multi-step logic
- Abstract or non-obvious relationships
- May require creative insight
- Target: ~10-30% of test-takers should answer correctly
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
    return f"""You are an expert psychometrician evaluating the quality of an IQ test question.

Evaluate the following question across these criteria:

1. CLARITY (0.0-1.0): Is the question clear, unambiguous, and well-written?
2. DIFFICULTY (0.0-1.0): Is the difficulty appropriate for the specified level ({difficulty})?
3. VALIDITY (0.0-1.0): Is this a valid IQ test question for measuring {question_type} ability?
4. FORMATTING (0.0-1.0): Are the answer options properly formatted? Is the correct answer valid?
5. CREATIVITY (0.0-1.0): Is the question original and interesting (not a well-known puzzle)?

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

Be rigorous in your evaluation. Only high-quality questions should score above 0.7 overall.
"""
