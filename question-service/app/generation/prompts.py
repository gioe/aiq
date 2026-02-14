"""Prompt templates for question generation.

This module contains the prompts used to generate different types of
IQ test questions from various LLM providers.
"""

import logging
import random
import re
from typing import Dict, List, Optional

from app.data.models import DifficultyLevel, QuestionType

logger = logging.getLogger(__name__)

# Threshold below which a score is considered weak and needs improvement
WEAK_SCORE_THRESHOLD = 0.7

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
✓ EXACTLY ONE correct answer in the answer_options - all other options must be definitively wrong
✓ The correct_answer must appear exactly once in answer_options

ANTI-PATTERNS TO AVOID:
✗ Ambiguous wording or multiple valid interpretations
✗ Questions requiring specialized knowledge (advanced mathematics, obscure vocabulary, cultural references)
✗ Trick questions or gotchas that test attention rather than reasoning
✗ Overly verbose or complex sentence structures
✗ Distractors that are obviously wrong or random numbers/letters
✗ Questions found in common IQ test prep materials
✗ Content that could be easily memorized and recognized on retesting
✗ Multiple correct or arguably correct answers in the options
✗ Answer options where more than one could be defended as correct
"""

# Question type-specific generation prompts
QUESTION_TYPE_PROMPTS: Dict[QuestionType, str] = {
    QuestionType.PATTERN: """Generate a pattern recognition question that tests the ability to identify visual or logical patterns.

Requirements:
- Present a sequence or pattern (can be numbers, letters, shapes, or symbols)
- The test-taker must identify the next item in the sequence or the missing item
- The pattern should have a clear logical rule
- Provide 4-6 answer options including distractors
- Include an explanation of the pattern rule

Example types:
- Number sequences with arithmetic progressions
- Number sequences with geometric or multiplicative rules
- Letter patterns using alphabetic positions or skip patterns
- Alternating or interleaved dual sequences
- Recursive patterns where each term depends on previous terms
- Matrix patterns describing a 3x3 grid with one missing cell
- Shape or symbol transformation sequences
- Modular arithmetic or cyclic patterns
- Difference-of-differences (second-order) sequences
- Combined operation sequences (e.g., +2, ×3, +2, ×3)
""",
    QuestionType.LOGIC: """Generate a logical reasoning question that tests deductive or inductive reasoning abilities.

Requirements:
- Present a logical scenario, syllogism, or reasoning puzzle
- The test-taker must draw a valid logical conclusion
- Avoid trick questions; focus on valid logical inference
- Provide 4-6 answer options including plausible distractors
- Include an explanation of the logical reasoning process

Example types:
- Syllogisms (All A are B, Some B are C, therefore...)
- If-then conditional reasoning with valid and invalid inferences
- Set theory and Venn diagram logic
- Ordering and ranking puzzles from comparative clues
- Truth-teller and liar puzzles
- Necessary vs. sufficient condition identification
- Elimination puzzles using process of elimination
- Logical equivalence and contrapositive reasoning
- Multi-constraint deductive puzzles (Einstein-style, simplified)
- Categorical classification with overlapping properties
""",
    QuestionType.SPATIAL: """Generate a spatial reasoning question that tests the ability to visualize and manipulate objects in space.

Requirements:
- Present a spatial transformation problem (rotations, folding, 3D visualization)
- The test-taker must mentally manipulate shapes or objects
- Describe shapes and transformations clearly in text
- Provide 4-6 answer options including similar but incorrect options
- Include an explanation of the spatial transformation

Example types:
- Cube rotations tracking labeled faces through sequential turns
- Paper folding with holes or cuts, predicting unfolded result
- 2D net folding into 3D cubes or boxes
- Mirror and reflection of 2D shapes across an axis
- Cross-section identification from slicing a 3D solid
- Mental rotation of 2D shapes (which rotated shape matches?)
- Map or compass navigation (follow directions, determine final position)
- Shape fitting or tangram-style assembly into a target outline
- Perspective taking (what does a 3D object look like from another angle?)
- Symmetry identification (line/rotational symmetry of a figure)
- Coordinate grid transformations (translate, rotate, reflect a shape on a grid)
- Counting faces, edges, or vertices of described 3D objects
""",
    QuestionType.MATH: """Generate a mathematical reasoning question that tests quantitative and numerical reasoning.

Requirements:
- Present a mathematical problem requiring reasoning, not just calculation
- Focus on problem-solving rather than arithmetic
- The difficulty should be appropriate for the specified level
- Provide 4-6 answer options with numerical answers
- Include a step-by-step explanation of the solution

Example types:
- Word problems with practical everyday contexts
- Number theory involving LCM, GCD, or divisibility
- Proportional reasoning with ratios, rates, or scaling
- Algebraic thinking with unknown quantities or pattern generalization
- Logical-mathematical puzzles with digit or arithmetic constraints
- Combinatorics and counting problems
- Probability and likelihood reasoning
- Fraction, percentage, or unit conversion reasoning
- Age, distance, or work-rate relationship problems
- Estimation and number sense problems
""",
    QuestionType.VERBAL: """Generate a verbal reasoning question that tests language comprehension and reasoning.

Requirements:
- Present analogies, word relationships, or vocabulary problems
- Test understanding of meaning and relationships, not just vocabulary knowledge
- Questions should require reasoning about conceptual connections
- Provide 4-6 answer options
- Include an explanation of the relationship or reasoning
- Use common vocabulary (avoid obscure or highly technical terms)

Example types:
- Analogies with part-whole relationships
- Analogies with cause-effect or function relationships
- Analogies with tool-user or creator-creation relationships
- Odd one out identifying the item that doesn't share a category or property
- Word classification grouping words by shared semantic feature
- Sentence completion where context determines the correct word
- Synonym or antonym selection
- Semantic reasoning about described relationships
- Sequence completion with conceptually ordered words
- Verbal inference drawing a conclusion from a short statement
- Multi-layered analogies requiring recognition of two simultaneous relationship types
- Verbal inference chains combining 2-3 premises to reach a non-obvious conclusion
- Abstract cross-domain analogies connecting unrelated fields via a shared principle
- Multi-clause sentence completion with complex rhetorical structure
- Embedded verbal constraint satisfaction requiring 3+ semantic conditions
""",
    QuestionType.MEMORY: """Generate a memory-based question that tests working memory and recall.

CRITICAL: Memory questions MUST include a separate "stimulus" field containing the content to memorize.
The app will display the stimulus first, then hide it before showing the question.

Requirements:
- Provide a "stimulus" field with the content to memorize (list, sequence, passage, or pattern)
- Provide a "question_text" field with the question to answer AFTER the stimulus is hidden
- The question_text should NOT repeat the stimulus content
- The memory load should be appropriate for the difficulty level
- Provide 4-6 answer options
- Include an explanation referencing the original stimulus

STRUCTURED FORMAT:
- stimulus: The content the user must memorize (will be shown first, then hidden)
- question_text: The question to answer after the stimulus is hidden (should NOT contain the stimulus)

Example types:
- List recall with logical constraint (remember items, then answer question requiring reasoning)
- Sequence memory with position-based recall
- Detail recall from a short passage of 2-3 sentences
- Pattern memory with number or letter sequences to recall and identify
- Multi-step memory requiring remember, transform, and recall
- Spatial memory recalling positions or arrangements
- Associative memory recalling paired items or attributes
- Temporal order memory recalling the sequence of events

IMPORTANT: The stimulus field must contain ONLY the content to memorize.
The question_text must be answerable only by someone who has memorized the stimulus.
Do NOT embed the stimulus within the question_text.
""",
}

# Pool of gold standard examples per question type, randomly selected at prompt
# build time. Each call to build_generation_prompt() picks one example from the
# pool, reducing anchoring bias toward any single question style.
GOLD_STANDARD_EXAMPLES: Dict[QuestionType, List[str]] = {
    QuestionType.PATTERN: [
        # Example 1: Arithmetic progression (existing)
        """GOLD STANDARD EXAMPLE:
Question: "What comes next in the sequence? 3, 6, 11, 18, 27, ?"
Options: ["36", "38", "40", "42", "44"]
Answer: "38"
Explanation: "Each number increases by consecutive odd numbers: +3, +5, +7, +9, +11. So 27 + 11 = 38."

Quality notes: Clear progression rule, plausible distractors (other arithmetic progressions), concise wording.""",
        # Example 2: Letter pattern
        """GOLD STANDARD EXAMPLE:
Question: "What letter comes next? B, D, G, K, P, ?"
Options: ["T", "U", "V", "W", "X"]
Answer: "V"
Explanation: "The gaps between alphabetic positions increase by 1 each time: B→D (+2), D→G (+3), G→K (+4), K→P (+5), P→? (+6). P + 6 = V."

Quality notes: Tests alphabetic position reasoning with increasing gaps, requires translating letters to ordinal positions.""",
        # Example 3: Matrix pattern
        """GOLD STANDARD EXAMPLE:
Question: "In a 3×3 grid, the top row shows 2, 4, 6; the middle row shows 3, 6, 9; and the bottom row shows 5, 10, ?. What number replaces the question mark?"
Options: ["12", "15", "20", "14", "25"]
Answer: "15"
Explanation: "Each row multiplies its first number by 1, 2, and 3. The bottom row: 5×1=5, 5×2=10, 5×3=15."

Quality notes: Tests matrix pattern recognition, requires identifying row-level rules, plausible distractors from other operations.""",
        # Example 4: Combined operation sequence
        """GOLD STANDARD EXAMPLE:
Question: "What comes next? 2, 6, 4, 12, 10, 30, ?"
Options: ["28", "32", "26", "60", "90"]
Answer: "28"
Explanation: "The pattern alternates two operations: ×3, then −2. So 2×3=6, 6−2=4, 4×3=12, 12−2=10, 10×3=30, 30−2=28."

Quality notes: Tests alternating dual-operation recognition, requires tracking two interleaved rules.""",
    ],
    QuestionType.LOGIC: [
        # Example 1: Syllogism (existing)
        """GOLD STANDARD EXAMPLE:
Question: "All musicians can read sheet music. Some musicians are teachers. Which statement must be true?"
Options: [
  "All teachers can read sheet music",
  "Some teachers can read sheet music",
  "All people who read sheet music are musicians",
  "Some musicians who teach cannot read sheet music"
]
Answer: "Some teachers can read sheet music"
Explanation: "Since some musicians are teachers, and all musicians can read sheet music, it follows that at least some teachers (those who are musicians) can read sheet music. We cannot conclude that ALL teachers can read music since only some are musicians."

Quality notes: Tests syllogistic reasoning, distractors exploit common logical fallacies, clear and unambiguous.""",
        # Example 2: Conditional / contrapositive reasoning
        """GOLD STANDARD EXAMPLE:
Question: "If it rains, the ground gets wet. The ground is not wet. Which conclusion is valid?"
Options: ["It rained", "It did not rain", "The ground is dry because of the sun", "It might have rained"]
Answer: "It did not rain"
Explanation: "This is modus tollens: If P then Q; Not Q; therefore Not P. Since the ground is not wet (not Q), it did not rain (not P). The other options either affirm the consequent or introduce unsupported causes."

Quality notes: Tests contrapositive reasoning, distractors include affirming the consequent and irrelevant causal explanations.""",
        # Example 3: Ordering / ranking puzzle
        """GOLD STANDARD EXAMPLE:
Question: "Four runners finished a race. Amy finished before Ben. Carlos finished after Diana. Ben finished before Diana. Who finished first?"
Options: ["Amy", "Ben", "Diana", "Carlos"]
Answer: "Amy"
Explanation: "From the clues: Amy before Ben, Ben before Diana, Carlos after Diana. Combined order: Amy, Ben, Diana, Carlos. Amy finished first."

Quality notes: Tests transitive ordering from comparative clues, requires combining multiple constraints into a single sequence.""",
        # Example 4: Elimination puzzle
        """GOLD STANDARD EXAMPLE:
Question: "A prize is in one of three boxes: red, blue, or green. You're told: (1) The prize is not in the red box. (2) If the prize is in the blue box, then the note inside says 'Try again.' The blue box's note says 'Congratulations!' Which box has the prize?"
Options: ["Red box", "Blue box", "Green box", "Cannot be determined"]
Answer: "Green box"
Explanation: "Clue 1 eliminates red. Clue 2 says if the prize were in blue, the note would say 'Try again,' but blue's note says 'Congratulations!' — a contradiction. So the prize is not in blue either. It must be in the green box."

Quality notes: Tests process of elimination with conditional reasoning, requires identifying contradictions to narrow possibilities.""",
    ],
    QuestionType.SPATIAL: [
        # Example 1: Cube rotation (existing)
        """GOLD STANDARD EXAMPLE:
Question: "A cube has different symbols on each face: ★ on top, ● on bottom, ■ on front, ▲ on back, ◆ on left, and ✦ on right. If you rotate the cube 90° forward (top face moves to front), then 90° clockwise (when viewed from above), which symbol is now on top?"
Options: ["★", "●", "■", "▲", "◆"]
Answer: "◆"
Explanation: "After rotating forward 90°: ● moves to front, ★ moves to back, ■ moves to top, ▲ moves to bottom. Then rotating 90° clockwise from above: ◆ (left) moves to top."

Quality notes: Tests sequential 3D visualization, requires mental manipulation, clear face labeling.""",
        # Example 2: Cross-section
        """GOLD STANDARD EXAMPLE:
Question: "A right circular cone with height 12 cm and base radius 6 cm is sliced by a horizontal plane 4 cm above the base. What is the shape and radius of the cross-section?"
Options: ["Circle, radius 4 cm", "Circle, radius 2 cm", "Ellipse, 4 cm wide", "Circle, radius 3 cm"]
Answer: "Circle, radius 4 cm"
Explanation: "A horizontal slice of a cone parallel to the base produces a circle. At height 4 from the base (8 from the apex), the radius scales linearly: r = 6 × (8/12) = 4 cm."

Quality notes: Tests cross-section visualization and proportional spatial reasoning.""",
        # Example 3: Map/compass navigation
        """GOLD STANDARD EXAMPLE:
Question: "Starting at point X, you walk 3 blocks North, turn right and walk 4 blocks, turn right and walk 1 block, then turn left and walk 2 blocks. What direction and approximate distance are you from point X in a straight line?"
Options: ["Northeast, 5 blocks", "East, 6 blocks", "Southeast, 7 blocks", "Northeast, 6.3 blocks"]
Answer: "Northeast, 6.3 blocks"
Explanation: "Net displacement: East = 4 + 2 = 6 blocks, North = 3 − 1 = 2 blocks. Distance = √(6² + 2²) = √40 ≈ 6.3. Direction is Northeast (positive East and North)."

Quality notes: Tests path integration and spatial orientation, requires tracking cumulative displacement.""",
        # Example 4: Perspective taking
        """GOLD STANDARD EXAMPLE:
Question: "Three blocks are stacked: a large cube on the bottom, a medium cylinder on top of it, and a small sphere on top of the cylinder. What shape do you see when looking at this arrangement directly from the side (eye level with the middle object)?"
Options: ["A square with a circle on top and a smaller circle above that", "A square with a rectangle on top and a circle above that", "A square topped by a rectangle topped by a semicircle", "A square topped by a rectangle topped by a circle"]
Answer: "A square topped by a rectangle topped by a circle"
Explanation: "From the side: the cube appears as a square, the cylinder appears as a rectangle (side profile), and the sphere appears as a circle. The shapes stack vertically."

Quality notes: Tests 3D-to-2D projection reasoning, requires understanding of how solids project from different viewpoints.""",
    ],
    QuestionType.MATH: [
        # Example 1: Number theory / LCM (existing)
        """GOLD STANDARD EXAMPLE:
Question: "A store sells apples in bags of 6 and oranges in bags of 8. If you buy the same number of apples and oranges, what is the minimum number of each fruit you must buy?"
Options: ["12", "16", "24", "32", "48"]
Answer: "24"
Explanation: "We need the least common multiple (LCM) of 6 and 8. Factors: 6 = 2 × 3, 8 = 2³. LCM = 2³ × 3 = 24. You need 4 bags of apples (4 × 6 = 24) and 3 bags of oranges (3 × 8 = 24)."

Quality notes: Tests LCM concept through practical context, requires reasoning not just calculation, appropriate distractors.""",
        # Example 2: Probability
        """GOLD STANDARD EXAMPLE:
Question: "A bag contains 3 red marbles, 4 blue marbles, and 5 green marbles. If you draw two marbles without replacement, what is the probability that both are blue?"
Options: ["1/11", "1/6", "4/33", "1/9", "2/12"]
Answer: "1/11"
Explanation: "P(first blue) = 4/12 = 1/3. P(second blue | first blue) = 3/11. P(both blue) = (4/12) × (3/11) = 12/132 = 1/11."

Quality notes: Tests probability reasoning with dependent events, requires understanding sampling without replacement.""",
        # Example 3: Proportional reasoning
        """GOLD STANDARD EXAMPLE:
Question: "A recipe serves 4 people and requires 2/3 cup of flour. How much flour is needed to serve 10 people?"
Options: ["5/3 cups", "10/3 cups", "5/6 cup", "2 cups", "4/3 cups"]
Answer: "5/3 cups"
Explanation: "Scaling factor = 10/4 = 5/2. Flour needed = (2/3) × (5/2) = 10/6 = 5/3 cups."

Quality notes: Tests proportional scaling with fractions, practical everyday context, requires fraction multiplication.""",
        # Example 4: Combinatorics
        """GOLD STANDARD EXAMPLE:
Question: "How many different 3-letter arrangements can be made from the letters A, B, C, D if no letter may be repeated?"
Options: ["12", "24", "64", "6", "27"]
Answer: "24"
Explanation: "This is a permutation: 4 choices for the first letter, 3 for the second, 2 for the third. 4 × 3 × 2 = 24."

Quality notes: Tests combinatorial thinking, requires understanding ordered selection without replacement.""",
    ],
    QuestionType.VERBAL: [
        # Example 1: Part-whole analogy (existing)
        """GOLD STANDARD EXAMPLE:
Question: "Book is to Chapter as Building is to ____"
Options: ["Floor", "Brick", "Foundation", "Architect", "City"]
Answer: "Floor"
Explanation: "A book is divided into chapters; similarly, a building is divided into floors. The relationship is 'whole to major subdivision.' Brick is too small (a component), Foundation is a specific part, Architect is the creator, and City is a larger container."

Quality notes: Tests hierarchical relationship reasoning, uses common words, distractors test different relationship types.""",
        # Example 2: Odd one out
        """GOLD STANDARD EXAMPLE:
Question: "Which word does NOT belong with the others? Whisper, Shout, Mumble, Write, Murmur"
Options: ["Whisper", "Shout", "Mumble", "Write", "Murmur"]
Answer: "Write"
Explanation: "Whisper, Shout, Mumble, and Murmur are all ways of producing vocal sound. Write is a form of communication but does not involve vocalization."

Quality notes: Tests categorical classification by shared semantic property, uses common vocabulary with a subtle but clear distinction.""",
        # Example 3: Sentence completion
        """GOLD STANDARD EXAMPLE:
Question: "Despite the team's early setbacks, their ____ determination led them to an unexpected victory."
Options: ["wavering", "unwavering", "halfhearted", "token", "questionable"]
Answer: "unwavering"
Explanation: "'Despite early setbacks' signals a contrast — the team overcame obstacles. 'Unwavering' (steady, firm) fits because their steady determination contrasts with setbacks. The other options would agree with setbacks rather than contrasting them."

Quality notes: Tests contextual vocabulary and contrast-signal comprehension, requires understanding sentence-level logical structure.""",
        # Example 4: Function analogy
        """GOLD STANDARD EXAMPLE:
Question: "Telescope is to Distant as Microscope is to ____"
Options: ["Small", "Large", "Near", "Scientific", "Glass"]
Answer: "Small"
Explanation: "A telescope is used to see distant objects; a microscope is used to see small objects. The relationship is 'instrument to the quality of what it reveals.' Large is the opposite, Near confuses physical distance with scale, and Scientific and Glass describe attributes of the tool itself."

Quality notes: Tests functional analogy reasoning with instruments, distractors target different relationship interpretations.""",
        # Example 5: Multi-layered analogy (hard)
        """GOLD STANDARD EXAMPLE:
Question: "Fossil is to Paleontologist as Dream is to ____"
Options: ["Psychoanalyst", "Sleeper", "Neurologist", "Philosopher", "Artist"]
Answer: "Psychoanalyst"
Explanation: "This analogy operates on two levels simultaneously. Surface level: both fossils and dreams are artifacts of past activity (biological history / unconscious thought). Deeper level: both paleontologists and psychoanalysts reconstruct a hidden narrative by interpreting fragmentary evidence. 'Neurologist' studies the brain mechanism but doesn't interpret dream content narratively. 'Sleeper' produces dreams but doesn't analyze them. 'Philosopher' and 'Artist' engage with dreams but not through systematic evidence-based interpretation."

Quality notes: HARD — requires recognizing a dual-layer relationship (artifact + interpretive reconstruction), not just a single functional link. Distractors each match one layer but not both.""",
        # Example 6: Verbal inference chain (hard)
        """GOLD STANDARD EXAMPLE:
Question: "All effective communicators adapt their message to their audience. Some scientists struggle to explain their work to non-specialists. No one who fails to adapt their message is persuasive to a general audience. Which conclusion follows?"
Options: ["All scientists are poor communicators", "Some scientists may not be persuasive to a general audience", "Non-specialists cannot understand science", "Effective communicators are always scientists", "Scientists who adapt their message are always persuasive"]
Answer: "Some scientists may not be persuasive to a general audience"
Explanation: "Premise 1: Effective communicators adapt to their audience. Premise 2: Some scientists struggle to explain to non-specialists (i.e., struggle to adapt). Premise 3: Failing to adapt → not persuasive to general audiences. Chaining premises 2 and 3: some scientists struggle to adapt → those scientists are not persuasive to general audiences. The answer uses 'may not be' because premise 2 says 'some,' not 'all.' The other options overgeneralize or reverse the logic."

Quality notes: HARD — requires chaining three premises and tracking quantifiers ('some' vs 'all'). Distractors exploit common logical errors (overgeneralization, reversal).""",
        # Example 7: Multi-clause rhetorical completion (hard)
        """GOLD STANDARD EXAMPLE:
Question: "While the novelist's early works were praised for their ____, critics noted that this same quality, when taken to excess in her later novels, made the prose feel ____ rather than refined."
Options: ["brevity ... sparse", "complexity ... convoluted", "originality ... derivative", "precision ... pedantic", "warmth ... sentimental"]
Answer: "precision ... pedantic"
Explanation: "The sentence requires a quality that is positive in moderation but negative in excess. 'Precision' is valued in early work, but excessive precision becomes 'pedantic' (overly focused on minor details). The pair must satisfy three constraints: (1) the first word is a positive trait, (2) the second is its negative extreme, and (3) the second contrasts with 'refined.' 'Brevity/sparse' nearly works but 'sparse' doesn't contrast with 'refined.' 'Complexity/convoluted' fails because complexity isn't typically praised as a virtue. 'Originality/derivative' contradicts itself (derivative is the opposite, not the excess)."

Quality notes: HARD — requires satisfying three simultaneous constraints across two blanks. Each distractor pair fails on exactly one constraint, testing thorough reasoning rather than pattern matching.""",
    ],
    QuestionType.MEMORY: [
        # Example 1: List recall with logical constraint (existing)
        """GOLD STANDARD EXAMPLE:
stimulus: "maple, oak, dolphin, cherry, whale, birch, salmon"
question_text: "Which item from the list is a mammal that is NOT the fourth item?"
Options: ["dolphin", "whale", "salmon", "cherry", "oak"]
Answer: "whale"
Explanation: "The mammals in the list are dolphin and whale. The fourth item is cherry (not a mammal). Therefore, whale is the mammal that is not the fourth item."

Quality notes: Tests both memory retention and logical reasoning, stimulus is separate from question, appropriate cognitive load.""",
        # Example 2: Detail recall from a short passage (existing)
        """GOLD STANDARD EXAMPLE:
stimulus: "The red house is next to the blue house. The green house is across from the yellow house. A doctor lives in the blue house."
question_text: "Which house is next to the one where the doctor lives?"
Options: ["red house", "green house", "yellow house", "blue house"]
Answer: "red house"
Explanation: "The doctor lives in the blue house, and the red house is next to the blue house."

Quality notes: Tests relational memory and spatial inference from memorized statements.""",
        # Example 3: Sequence memory with position-based recall
        """GOLD STANDARD EXAMPLE:
stimulus: "7, K, 3, P, 9, A, 5, M"
question_text: "What is the fifth item in the sequence, and what type is it (letter or number)?"
Options: ["9, number", "P, letter", "A, letter", "5, number"]
Answer: "9, number"
Explanation: "The sequence is: 7(1st), K(2nd), 3(3rd), P(4th), 9(5th), A(6th), 5(7th), M(8th). The fifth item is 9, which is a number."

Quality notes: Tests sequential position recall with mixed-type items, requires precise ordinal memory.""",
        # Example 4: Temporal order memory
        """GOLD STANDARD EXAMPLE:
stimulus: "First, the bell rang. Then, the lights flickered. Next, a door slammed shut. After that, someone laughed. Finally, music began playing."
question_text: "Which event occurred immediately before the door slammed shut?"
Options: ["The bell rang", "The lights flickered", "Someone laughed", "Music began playing"]
Answer: "The lights flickered"
Explanation: "The sequence of events: bell rang, lights flickered, door slammed, someone laughed, music began. The event immediately before the door slammed was the lights flickering."

Quality notes: Tests temporal sequence memory, requires recall of event order from a narrative passage.""",
    ],
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

# Type+difficulty-specific overrides that replace the generic DIFFICULTY_INSTRUCTIONS
# when the combination matches. This allows fine-tuning difficulty constraints for
# question types where the generic instructions produce misaligned difficulty (e.g.,
# easy math questions that are actually medium-difficulty word problems).
TYPE_DIFFICULTY_OVERRIDES: Dict[tuple[QuestionType, DifficultyLevel], str] = {
    (
        QuestionType.MATH,
        DifficultyLevel.EASY,
    ): """Difficulty: EASY
- Single arithmetic operation only — NO chaining multiple steps
- Use whole numbers with small values (under 100)
- NO percentages, fractions, ratios, or unit conversions
- NO multi-step word problems
- Basic addition, subtraction, multiplication, or division only
- The question should be solvable in one mental step
- Target success rate: ~70-80% of general population
- IQ range: Effectively measures differences in the 85-115 range
- Discriminatory power: Should still differentiate between average and above-average
""",
    (
        QuestionType.VERBAL,
        DifficultyLevel.HARD,
    ): """Difficulty: HARD
- Target success rate: ~10-30% of general population
- IQ range: Effectively measures differences in the 115-145+ range
- Discriminatory power: Should identify genuinely exceptional verbal reasoning ability

WHAT MAKES A VERBAL QUESTION HARD (follow these rules strictly):
- The question MUST require MULTI-STEP verbal reasoning — single-step recognition (e.g., simple A:B::C:? analogies, basic odd-one-out) is NOT hard
- Difficulty must come from STRUCTURAL COMPLEXITY, not just advanced vocabulary
- Hard verbal questions require the solver to hold multiple relationships in working memory simultaneously

REQUIRED structural characteristics (use at least one):
1. Multi-layered analogies: relationships that operate on two levels (e.g., functional AND metaphorical)
2. Verbal inference chains: 2-3 premises in natural language that require combining to reach a non-obvious conclusion
3. Abstract cross-domain mapping: analogies connecting concepts from unrelated domains via a shared abstract principle
4. Rhetorical structure reasoning: sentence completions requiring understanding of complex contrasts, concessions, or paradoxes across multiple clauses
5. Embedded constraint satisfaction: verbal puzzles where 3+ semantic constraints must be satisfied simultaneously

ANTI-PATTERNS (these produce medium-difficulty questions, NOT hard):
✗ Simple A:B::C:? analogies with a single clear relationship — ALWAYS medium or easy
✗ "Which word does NOT belong?" with a single shared category — ALWAYS medium
✗ Synonym/antonym selection even with advanced vocabulary — ALWAYS medium
✗ Single-clause sentence completions — ALWAYS medium
✗ Making questions hard solely through obscure vocabulary without structural complexity

VOCABULARY GUIDELINES FOR HARD:
- You MAY use moderately advanced vocabulary (e.g., "pragmatic", "tenuous", "ameliorate")
- Avoid highly obscure words that only test vocabulary knowledge (e.g., "defenestrate", "sesquipedalian")
- Difficulty must PRIMARILY come from reasoning complexity, not word rarity
""",
}

# Sub-types for each question type, extracted from the "Example types" lists
# in QUESTION_TYPE_PROMPTS. Used by the batch chunking system to assign each
# sub-batch a different focus area, reducing mode collapse in large batches.
QUESTION_SUBTYPES: Dict[QuestionType, List[str]] = {
    QuestionType.PATTERN: [
        "number sequences with arithmetic progressions",
        "number sequences with geometric or multiplicative rules",
        "letter patterns using alphabetic positions or skip patterns",
        "alternating or interleaved dual sequences",
        "recursive patterns where each term depends on previous terms",
        "matrix patterns describing a 3x3 grid with one missing cell",
        "shape or symbol transformation sequences",
        "modular arithmetic or cyclic patterns",
        "difference-of-differences (second-order) sequences",
        "combined operation sequences (e.g., +2, ×3, +2, ×3)",
    ],
    QuestionType.LOGIC: [
        "syllogisms (All A are B, Some B are C, therefore...)",
        "if-then conditional reasoning with valid and invalid inferences",
        "set theory and Venn diagram logic",
        "ordering and ranking puzzles from comparative clues",
        "truth-teller and liar puzzles",
        "necessary vs. sufficient condition identification",
        "elimination puzzles using process of elimination",
        "logical equivalence and contrapositive reasoning",
        "multi-constraint deductive puzzles (Einstein-style, simplified)",
        "categorical classification with overlapping properties",
    ],
    QuestionType.SPATIAL: [
        "cube rotations tracking labeled faces through sequential turns",
        "paper folding with holes or cuts, predicting unfolded result",
        "2D net folding into 3D cubes or boxes",
        "mirror and reflection of 2D shapes across an axis",
        "cross-section identification from slicing a 3D solid",
        "mental rotation of 2D shapes (which rotated shape matches?)",
        "map or compass navigation (follow directions, determine final position)",
        "shape fitting or tangram-style assembly into a target outline",
        "perspective taking (what does a 3D object look like from another angle?)",
        "symmetry identification (line/rotational symmetry of a figure)",
        "coordinate grid transformations (translate, rotate, reflect a shape on a grid)",
        "counting faces, edges, or vertices of described 3D objects",
    ],
    QuestionType.MATH: [
        "word problems with practical everyday contexts",
        "number theory involving LCM, GCD, or divisibility",
        "proportional reasoning with ratios, rates, or scaling",
        "algebraic thinking with unknown quantities or pattern generalization",
        "logical-mathematical puzzles with digit or arithmetic constraints",
        "combinatorics and counting problems",
        "probability and likelihood reasoning",
        "fraction, percentage, or unit conversion reasoning",
        "age, distance, or work-rate relationship problems",
        "estimation and number sense problems",
    ],
    QuestionType.VERBAL: [
        "analogies with part-whole relationships",
        "analogies with cause-effect or function relationships",
        "analogies with tool-user or creator-creation relationships",
        "odd one out identifying the item that doesn't share a category or property",
        "word classification grouping words by shared semantic feature",
        "sentence completion where context determines the correct word",
        "synonym or antonym selection",
        "semantic reasoning about described relationships",
        "sequence completion with conceptually ordered words",
        "verbal inference drawing a conclusion from a short statement",
        "multi-layered analogies requiring recognition of two simultaneous relationship types",
        "verbal inference chains combining 2-3 premises to reach a non-obvious conclusion",
        "abstract cross-domain analogies connecting unrelated fields via a shared principle",
        "multi-clause sentence completion with complex rhetorical structure",
        "embedded verbal constraint satisfaction requiring 3+ semantic conditions",
    ],
    QuestionType.MEMORY: [
        "list recall with logical constraint",
        "sequence memory with position-based recall",
        "detail recall from a short passage of 2-3 sentences",
        "pattern memory with number or letter sequences to recall and identify",
        "multi-step memory requiring remember, transform, and recall",
        "spatial memory recalling positions or arrangements",
        "associative memory recalling paired items or attributes",
        "temporal order memory recalling the sequence of events",
    ],
}

# Mapping from sub-type strings (as found in QUESTION_SUBTYPES) to their
# matching gold standard example.  When build_generation_prompt() is called
# with a specific subtype, this mapping is consulted so the single example
# shown to the LLM reinforces—rather than contradicts—the assigned sub-type.
GOLD_STANDARD_BY_SUBTYPE: Dict[str, str] = {
    # Pattern
    "number sequences with arithmetic progressions": GOLD_STANDARD_EXAMPLES[
        QuestionType.PATTERN
    ][0],
    "letter patterns using alphabetic positions or skip patterns": GOLD_STANDARD_EXAMPLES[
        QuestionType.PATTERN
    ][
        1
    ],
    "matrix patterns describing a 3x3 grid with one missing cell": GOLD_STANDARD_EXAMPLES[
        QuestionType.PATTERN
    ][
        2
    ],
    "combined operation sequences (e.g., +2, ×3, +2, ×3)": GOLD_STANDARD_EXAMPLES[
        QuestionType.PATTERN
    ][3],
    # Logic
    "syllogisms (All A are B, Some B are C, therefore...)": GOLD_STANDARD_EXAMPLES[
        QuestionType.LOGIC
    ][0],
    "logical equivalence and contrapositive reasoning": GOLD_STANDARD_EXAMPLES[
        QuestionType.LOGIC
    ][1],
    "ordering and ranking puzzles from comparative clues": GOLD_STANDARD_EXAMPLES[
        QuestionType.LOGIC
    ][2],
    "elimination puzzles using process of elimination": GOLD_STANDARD_EXAMPLES[
        QuestionType.LOGIC
    ][3],
    # Spatial
    "cube rotations tracking labeled faces through sequential turns": GOLD_STANDARD_EXAMPLES[
        QuestionType.SPATIAL
    ][
        0
    ],
    "cross-section identification from slicing a 3D solid": GOLD_STANDARD_EXAMPLES[
        QuestionType.SPATIAL
    ][1],
    "map or compass navigation (follow directions, determine final position)": GOLD_STANDARD_EXAMPLES[
        QuestionType.SPATIAL
    ][
        2
    ],
    "perspective taking (what does a 3D object look like from another angle?)": GOLD_STANDARD_EXAMPLES[
        QuestionType.SPATIAL
    ][
        3
    ],
    # Math
    "number theory involving LCM, GCD, or divisibility": GOLD_STANDARD_EXAMPLES[
        QuestionType.MATH
    ][0],
    "probability and likelihood reasoning": GOLD_STANDARD_EXAMPLES[QuestionType.MATH][
        1
    ],
    "proportional reasoning with ratios, rates, or scaling": GOLD_STANDARD_EXAMPLES[
        QuestionType.MATH
    ][2],
    "combinatorics and counting problems": GOLD_STANDARD_EXAMPLES[QuestionType.MATH][3],
    # Verbal
    "analogies with part-whole relationships": GOLD_STANDARD_EXAMPLES[
        QuestionType.VERBAL
    ][0],
    "odd one out identifying the item that doesn't share a category or property": GOLD_STANDARD_EXAMPLES[
        QuestionType.VERBAL
    ][
        1
    ],
    "sentence completion where context determines the correct word": GOLD_STANDARD_EXAMPLES[
        QuestionType.VERBAL
    ][
        2
    ],
    "analogies with cause-effect or function relationships": GOLD_STANDARD_EXAMPLES[
        QuestionType.VERBAL
    ][3],
    "multi-layered analogies requiring recognition of two simultaneous relationship types": GOLD_STANDARD_EXAMPLES[
        QuestionType.VERBAL
    ][
        4
    ],
    "verbal inference chains combining 2-3 premises to reach a non-obvious conclusion": GOLD_STANDARD_EXAMPLES[
        QuestionType.VERBAL
    ][
        5
    ],
    "abstract cross-domain analogies connecting unrelated fields via a shared principle": GOLD_STANDARD_EXAMPLES[
        QuestionType.VERBAL
    ][
        4
    ],
    "multi-clause sentence completion with complex rhetorical structure": GOLD_STANDARD_EXAMPLES[
        QuestionType.VERBAL
    ][
        6
    ],
    "embedded verbal constraint satisfaction requiring 3+ semantic conditions": GOLD_STANDARD_EXAMPLES[
        QuestionType.VERBAL
    ][
        6
    ],
    # Memory
    "list recall with logical constraint": GOLD_STANDARD_EXAMPLES[QuestionType.MEMORY][
        0
    ],
    "detail recall from a short passage of 2-3 sentences": GOLD_STANDARD_EXAMPLES[
        QuestionType.MEMORY
    ][1],
    "sequence memory with position-based recall": GOLD_STANDARD_EXAMPLES[
        QuestionType.MEMORY
    ][2],
    "temporal order memory recalling the sequence of events": GOLD_STANDARD_EXAMPLES[
        QuestionType.MEMORY
    ][3],
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
        "stimulus": {
            "type": "string",
            "description": "Optional. Content to memorize before answering. Required for memory questions only - the app will display this first, then hide it before showing the question.",
        },
    },
    "required": ["question_text", "correct_answer", "answer_options", "explanation"],
}


def build_generation_prompt(
    question_type: QuestionType,
    difficulty: DifficultyLevel,
    count: int = 1,
    subtype: Optional[str] = None,
) -> str:
    """Build a complete generation prompt for a specific question type and difficulty.

    Args:
        question_type: Type of question to generate
        difficulty: Difficulty level
        count: Number of questions to generate (default: 1)
        subtype: Optional sub-type focus for diversity (e.g., "cube rotations").
            When provided, the prompt is tailored to generate only that sub-type:
            the gold standard example is matched, the "Example types" list is
            narrowed, and a mandatory sub-type directive is included.

    Returns:
        Complete prompt string for the LLM
    """
    type_prompt = QUESTION_TYPE_PROMPTS[question_type]
    diff_instructions = TYPE_DIFFICULTY_OVERRIDES.get(
        (question_type, difficulty), DIFFICULTY_INSTRUCTIONS[difficulty]
    )

    # When a subtype is specified, narrow the "Example types" list to just that
    # subtype so the LLM doesn't see the full menu and pick its favorite.
    if subtype:
        type_prompt = re.sub(
            r"Example types:\n(?:- .*\n)+",
            f"Example types:\n- {subtype}\n",
            type_prompt,
        )

    # Select gold standard example: prefer subtype-specific match to reduce
    # anchoring on an unrelated example that contradicts the assigned subtype.
    if subtype and subtype in GOLD_STANDARD_BY_SUBTYPE:
        gold_standard = GOLD_STANDARD_BY_SUBTYPE[subtype]
        gold_source = "subtype-matched"
    else:
        gold_standard = random.choice(GOLD_STANDARD_EXAMPLES[question_type])
        gold_source = "random"

    # Extract a short label from the gold standard for logging (first Question line)
    gold_label = (
        gold_standard.split('Question: "')[1].split('"')[0][:60]
        if 'Question: "' in gold_standard
        else "unknown"
    )
    logger.info(
        f"Prompt config: type={question_type.value}, subtype={subtype!r}, "
        f"gold_standard={gold_source} ({gold_label}...)"
    )

    # Build optional diversity instruction for sub-batch focus
    diversity_instruction = ""
    if subtype:
        diversity_instruction = f"""
REQUIRED SUB-TYPE: You MUST generate '{subtype}' questions for this batch.
Do NOT generate questions of other sub-types (e.g., do not generate cube rotation questions if the required sub-type is mirror/reflection).
Vary the specific scenarios, objects, and transformations within this sub-type.
"""

    # Memory questions use a two-phase UX: the stimulus is shown first, then hidden
    # before the question appears. The inline conditional below adds a "stimulus"
    # field instruction only for memory questions so the LLM includes it in its
    # JSON response. For all other question types, the conditional evaluates to an
    # empty string and the field is omitted.
    prompt = f"""{SYSTEM_PROMPT}

{type_prompt}

{gold_standard}

{diff_instructions}
{diversity_instruction}
Generate {count} unique, high-quality {"question" if count == 1 else "questions"} of type '{question_type.value}' at '{difficulty.value}' difficulty.

IMPORTANT: Respond with valid JSON only. Do not include any text outside the JSON structure.

For each question, provide:
1. question_text: The complete question statement
2. correct_answer: The correct answer (must be one of the answer_options)
3. answer_options: An array of 4-6 options (must include correct_answer)
4. explanation: A clear explanation of why the answer is correct
{"5. stimulus: The content to memorize (REQUIRED for memory questions - this is shown first, then hidden before the question)" if question_type == QuestionType.MEMORY else ""}

{"If generating multiple questions, return an array of question objects." if count > 1 else "Return a single question object."}
"""

    return prompt.strip()


def build_judge_prompt(
    question: str,
    answer_options: list[str],
    correct_answer: str,
    question_type: str,
    difficulty: str,
    stimulus: str | None = None,
) -> str:
    """Build an evaluation prompt for the judge to score a question.

    Args:
        question: The question text
        answer_options: List of answer options
        correct_answer: The correct answer
        question_type: Type of question
        difficulty: Difficulty level
        stimulus: Content to memorize before answering (for memory questions)

    Returns:
        Prompt string for judge evaluation
    """
    # Determine if this is a memory question for specialized guidance
    is_memory_question = question_type.lower() == "memory"

    memory_guidance = ""
    if is_memory_question:
        # Add critical warning if stimulus is missing
        missing_stimulus_warning = ""
        if not stimulus:
            missing_stimulus_warning = """
CRITICAL ERROR: This memory question is MISSING the required stimulus field!
Memory questions MUST have a stimulus field containing content for the user to memorize.
Without a stimulus, this question is INVALID and should receive a validity_score of 0.0.

"""
        memory_guidance = f"""{missing_stimulus_warning}MEMORY QUESTION EVALUATION GUIDELINES:
Memory questions use a two-phase delivery: the stimulus is shown first, then hidden before the question appears.
- The "stimulus" field contains content the user must memorize (shown first, then hidden)
- The "question_text" is what the user sees AFTER the stimulus is hidden
- CRITICAL: If no stimulus is provided above, the question MUST be rejected (validity_score = 0.0)
- Do NOT penalize for:
  * The question being "too easy" if they could see the stimulus (they can't when answering)
  * UX concerns about cheating, screenshots, or stimulus visibility
  * The stimulus not being repeated in the question (this is intentional)
- DO evaluate whether:
  * The stimulus field EXISTS and contains meaningful content
  * The stimulus contains appropriate content for the difficulty level
  * The question genuinely tests memory of the stimulus
  * The cognitive load matches the target difficulty
  * The question is answerable ONLY by someone who memorized the stimulus

"""

    return f"""You are an expert psychometrician evaluating IQ test questions for a mobile app used for longitudinal cognitive tracking.

CONTEXT: These questions will be used for repeated testing every 3 months. They must be highly original, suitable for mobile display, and aligned with established IQ testing principles (Wechsler, Stanford-Binet, Raven's).

IMPORTANT: Evaluate QUESTION CONTENT QUALITY only. Delivery mechanism concerns (e.g., screenshots, hiding sequences before recall, preventing cheating) are handled by the app UX - do NOT penalize validity for these concerns.
{memory_guidance}
Evaluate the following question across these criteria:

1. CLARITY (0.0-1.0):
   - Is wording unambiguous and clear?
   - Is the question concise enough for mobile display (ideally <300 characters)?
   - Can it be understood without multiple readings?

2. DIFFICULTY (0.0-1.0):
   - Rate the ACTUAL cognitive difficulty of this question on an absolute scale:
     0.0-0.3 = Easy (single-step, basic recall/recognition, ~70-80% success rate)
     0.4-0.6 = Medium (multi-step reasoning, integration of concepts, ~40-60% success rate)
     0.7-1.0 = Hard (abstract/creative thinking, complex working memory, ~10-30% success rate)
   - Score the question's inherent difficulty, regardless of the target level ({difficulty})
   - Base your rating on cognitive demand, not obscure knowledge

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
{"" if not stimulus else f'''
Stimulus (shown first, then hidden before question appears):
{stimulus}
'''}
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


def build_regeneration_prompt(
    original_question: str,
    original_answer: str,
    original_options: list[str],
    question_type: QuestionType,
    difficulty: DifficultyLevel,
    judge_feedback: str,
    scores: dict[str, float],
    original_stimulus: str | None = None,
) -> str:
    """Build a prompt for regenerating a rejected question with judge feedback.

    This prompt instructs the LLM to create an improved version of a question
    that addresses the specific issues identified by the judge.

    Args:
        original_question: The original question text that was rejected
        original_answer: The original correct answer
        original_options: The original answer options
        question_type: Type of question
        difficulty: Difficulty level
        judge_feedback: Detailed feedback from the judge explaining why it was rejected
        scores: Dictionary of scores (clarity, difficulty, validity, formatting, creativity)
        original_stimulus: The original stimulus content for memory questions (optional)

    Returns:
        Complete prompt string for regeneration
    """
    type_prompt = QUESTION_TYPE_PROMPTS[question_type]
    diff_instructions = DIFFICULTY_INSTRUCTIONS[difficulty]

    # Randomly select a gold standard example to reduce anchoring bias
    gold_standard = random.choice(GOLD_STANDARD_EXAMPLES[question_type])

    # Identify the weakest areas to focus improvement
    weak_areas = []
    for score_name, score_value in scores.items():
        if score_value < WEAK_SCORE_THRESHOLD:
            weak_areas.append(f"- {score_name.upper()}: {score_value:.2f}")

    weak_areas_text = (
        "\n".join(weak_areas) if weak_areas else "- Multiple areas need improvement"
    )

    # Build stimulus section for memory questions
    stimulus_section = ""
    if original_stimulus:
        stimulus_section = f"\nStimulus (content to memorize): {original_stimulus}"

    # Build memory-specific requirements if this is a memory question
    memory_requirements = ""
    if question_type == QuestionType.MEMORY:
        memory_requirements = """
9. MEMORY QUESTION SPECIFIC: Include a "stimulus" field with content to memorize
   - The stimulus is shown first, then hidden before the question appears
   - The question_text should NOT repeat the stimulus content
   - Ensure the question is only answerable by someone who memorized the stimulus"""

    # The JSON template below uses an inline conditional to append a "stimulus"
    # field for memory questions only. This mirrors the two-phase UX where
    # stimulus content is shown first, then hidden before the question appears.
    # See also: build_generation_prompt() which uses the same pattern.
    prompt = f"""{SYSTEM_PROMPT}

{type_prompt}

{gold_standard}

{diff_instructions}

---

REGENERATION TASK: A previous question was rejected by our quality judge. Your task is to create a NEW, IMPROVED question that addresses the identified issues while maintaining the same type and difficulty.

ORIGINAL QUESTION (REJECTED):
Question: {original_question}{stimulus_section}
Correct Answer: {original_answer}
Options: {original_options}

JUDGE'S FEEDBACK:
{judge_feedback}

WEAK SCORES (below 0.7 threshold):
{weak_areas_text}

REGENERATION REQUIREMENTS:
1. Create a COMPLETELY NEW question - do not simply rephrase the original
2. Address ALL issues mentioned in the judge's feedback
3. If the issue was "ambiguous answers" or "multiple valid answers", ensure your new question has ONE definitively correct answer
4. If the issue was "low creativity", use a novel question format or content area
5. If the issue was "too easy" or "wrong difficulty", calibrate appropriately for {difficulty.value} level
6. If the issue was "tests knowledge not reasoning", focus on cognitive reasoning rather than factual recall
7. Maintain the question type: {question_type.value}
8. Ensure cultural neutrality and mobile-friendliness{memory_requirements}

IMPORTANT: Generate a fresh, high-quality question that would pass rigorous evaluation. Do NOT attempt to "fix" the original - create something better.

Respond with valid JSON only:
{{
    "question_text": "<your new question>",
    "correct_answer": "<the one correct answer>",
    "answer_options": ["<4-6 options including correct answer>"],
    "explanation": "<clear explanation of why the answer is correct>"{', "stimulus": "<content to memorize - REQUIRED for memory questions>"' if question_type == QuestionType.MEMORY else ""}
}}
"""

    return prompt.strip()
