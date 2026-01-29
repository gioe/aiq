"""Tests for prompt generation."""

from app.models import DifficultyLevel, QuestionType
from app.prompts import (
    build_generation_prompt,
    build_judge_prompt,
    build_regeneration_prompt,
    QUESTION_TYPE_PROMPTS,
    DIFFICULTY_INSTRUCTIONS,
)


class TestBuildGenerationPrompt:
    """Tests for build_generation_prompt function."""

    def test_build_single_question_prompt(self):
        """Test building a prompt for a single question."""
        prompt = build_generation_prompt(
            question_type=QuestionType.MATH,
            difficulty=DifficultyLevel.EASY,
            count=1,
        )

        assert "mathematical" in prompt.lower()
        assert "easy" in prompt.lower()
        assert "Generate 1 unique" in prompt
        assert "psychometrician" in prompt.lower()
        assert "JSON" in prompt

    def test_build_multiple_questions_prompt(self):
        """Test building a prompt for multiple questions."""
        prompt = build_generation_prompt(
            question_type=QuestionType.LOGIC,
            difficulty=DifficultyLevel.HARD,
            count=5,
        )

        assert "logic" in prompt.lower()
        assert "hard" in prompt.lower()
        assert "Generate 5 unique" in prompt
        assert "array of question objects" in prompt.lower()

    def test_prompt_contains_type_specific_instructions(self):
        """Test that prompt contains type-specific instructions."""
        for question_type in QuestionType:
            prompt = build_generation_prompt(
                question_type=question_type,
                difficulty=DifficultyLevel.MEDIUM,
                count=1,
            )

            # Should contain the type-specific prompt
            assert question_type.value in prompt.lower()

    def test_prompt_contains_difficulty_instructions(self):
        """Test that prompt contains difficulty-specific instructions."""
        for difficulty in DifficultyLevel:
            prompt = build_generation_prompt(
                question_type=QuestionType.MATH,
                difficulty=difficulty,
                count=1,
            )

            # Should contain the difficulty level
            assert difficulty.value in prompt.lower()

    def test_all_question_types_have_prompts(self):
        """Test that all question types have prompt templates."""
        for question_type in QuestionType:
            assert question_type in QUESTION_TYPE_PROMPTS
            assert len(QUESTION_TYPE_PROMPTS[question_type]) > 0

    def test_all_difficulties_have_instructions(self):
        """Test that all difficulty levels have instructions."""
        for difficulty in DifficultyLevel:
            assert difficulty in DIFFICULTY_INSTRUCTIONS
            assert len(DIFFICULTY_INSTRUCTIONS[difficulty]) > 0

    def test_memory_question_prompt_includes_stimulus_requirement(self):
        """Test that memory question generation prompt includes stimulus field requirement."""
        prompt = build_generation_prompt(
            question_type=QuestionType.MEMORY,
            difficulty=DifficultyLevel.MEDIUM,
            count=1,
        )

        # The prompt should mention the stimulus field as required for memory questions
        assert "stimulus" in prompt.lower()
        # Should include the type-specific prompt which has CRITICAL stimulus instructions
        assert "CRITICAL" in prompt
        assert "stimulus" in prompt
        # Should mention that stimulus is shown first then hidden
        assert "shown first, then hidden" in prompt.lower()
        # The numbered instruction list should include stimulus
        assert "stimulus" in prompt

    def test_non_memory_question_prompt_excludes_stimulus(self):
        """Test that non-memory question generation prompts do not include stimulus instruction."""
        non_memory_types = [
            QuestionType.PATTERN,
            QuestionType.LOGIC,
            QuestionType.SPATIAL,
            QuestionType.MATH,
            QuestionType.VERBAL,
        ]

        for question_type in non_memory_types:
            prompt = build_generation_prompt(
                question_type=question_type,
                difficulty=DifficultyLevel.MEDIUM,
                count=1,
            )

            # Non-memory prompts should not include the stimulus instruction line
            assert (
                "stimulus" not in prompt.lower()
            ), f"{question_type.value} prompt should not mention stimulus"


class TestBuildJudgePrompt:
    """Tests for build_judge_prompt function."""

    def test_build_judge_prompt(self):
        """Test building an judge evaluation prompt."""
        prompt = build_judge_prompt(
            question="What is 2 + 2?",
            answer_options=["2", "3", "4", "5"],
            correct_answer="4",
            question_type="mathematical",
            difficulty="easy",
        )

        assert "What is 2 + 2?" in prompt
        assert "4" in prompt
        assert "mathematical" in prompt
        assert "easy" in prompt
        assert "clarity" in prompt.lower()
        assert "validity" in prompt.lower()
        assert "JSON" in prompt

    def test_judge_prompt_includes_all_options(self):
        """Test that judge prompt includes all answer options."""
        options = ["Option A", "Option B", "Option C", "Option D"]
        prompt = build_judge_prompt(
            question="Test question?",
            answer_options=options,
            correct_answer="Option C",
            question_type="logical_reasoning",
            difficulty="medium",
        )

        for option in options:
            assert option in prompt

    def test_judge_prompt_includes_evaluation_criteria(self):
        """Test that judge prompt includes all evaluation criteria."""
        prompt = build_judge_prompt(
            question="Test question?",
            answer_options=["A", "B", "C", "D"],
            correct_answer="A",
            question_type="verbal_reasoning",
            difficulty="hard",
        )

        criteria = ["clarity", "difficulty", "validity", "formatting", "creativity"]
        for criterion in criteria:
            assert criterion.lower() in prompt.lower()

    def test_judge_prompt_specifies_score_range(self):
        """Test that judge prompt specifies valid score range."""
        prompt = build_judge_prompt(
            question="Test question?",
            answer_options=["A", "B"],
            correct_answer="A",
            question_type="pattern_recognition",
            difficulty="easy",
        )

        assert "0.0-1.0" in prompt or "0.0 to 1.0" in prompt

    def test_judge_prompt_memory_question_includes_stimulus(self):
        """Test that memory question judge prompt includes stimulus content."""
        stimulus = "maple, oak, dolphin, cherry, whale, birch, salmon"
        prompt = build_judge_prompt(
            question="Which item from the list is a mammal that is NOT the fourth item?",
            answer_options=["dolphin", "whale", "salmon", "cherry", "oak"],
            correct_answer="whale",
            question_type="memory",
            difficulty="medium",
            stimulus=stimulus,
        )

        assert stimulus in prompt
        assert "Stimulus (shown first, then hidden before question appears)" in prompt

    def test_judge_prompt_memory_question_includes_guidance(self):
        """Test that memory question judge prompt includes memory-specific guidance."""
        prompt = build_judge_prompt(
            question="Which color was mentioned second?",
            answer_options=["red", "blue", "green", "yellow"],
            correct_answer="blue",
            question_type="memory",
            difficulty="easy",
            stimulus="red, blue, green, yellow",
        )

        assert "MEMORY QUESTION EVALUATION GUIDELINES" in prompt
        assert "two-phase delivery" in prompt
        assert "stimulus is shown first, then hidden" in prompt

    def test_judge_prompt_non_memory_question_no_memory_guidance(self):
        """Test that non-memory questions do not include memory-specific guidance."""
        prompt = build_judge_prompt(
            question="What comes next: 2, 4, 6, ?",
            answer_options=["7", "8", "9", "10"],
            correct_answer="8",
            question_type="pattern",
            difficulty="easy",
        )

        assert "MEMORY QUESTION EVALUATION GUIDELINES" not in prompt
        assert "two-phase delivery" not in prompt

    def test_judge_prompt_without_stimulus_no_stimulus_section(self):
        """Test that prompt without stimulus does not include stimulus section."""
        prompt = build_judge_prompt(
            question="What is 2 + 2?",
            answer_options=["2", "3", "4", "5"],
            correct_answer="4",
            question_type="math",
            difficulty="easy",
        )

        assert "Stimulus (shown first, then hidden" not in prompt


class TestBuildRegenerationPrompt:
    """Tests for build_regeneration_prompt function."""

    def test_build_regeneration_prompt_basic(self):
        """Test building a basic regeneration prompt."""
        prompt = build_regeneration_prompt(
            original_question="What is 2 + 2?",
            original_answer="4",
            original_options=["2", "3", "4", "5"],
            question_type=QuestionType.MATH,
            difficulty=DifficultyLevel.EASY,
            judge_feedback="The question is too simple and tests calculation, not reasoning.",
            scores={"clarity": 0.9, "difficulty": 0.5, "validity": 0.8},
        )

        assert "What is 2 + 2?" in prompt
        assert "4" in prompt
        assert "REGENERATION TASK" in prompt
        assert "too simple" in prompt
        assert "DIFFICULTY" in prompt  # Weak score should be highlighted

    def test_regeneration_prompt_contains_type_and_difficulty(self):
        """Test that regeneration prompt contains type and difficulty instructions."""
        prompt = build_regeneration_prompt(
            original_question="Test question",
            original_answer="Answer",
            original_options=["A", "B", "C", "D"],
            question_type=QuestionType.LOGIC,
            difficulty=DifficultyLevel.HARD,
            judge_feedback="Needs improvement",
            scores={"clarity": 0.5},
        )

        assert "logic" in prompt.lower()
        assert "hard" in prompt.lower()
        assert QuestionType.LOGIC.value in prompt.lower()

    def test_regeneration_prompt_highlights_weak_scores(self):
        """Test that weak scores (below 0.7) are highlighted."""
        prompt = build_regeneration_prompt(
            original_question="Test question",
            original_answer="Answer",
            original_options=["A", "B", "C", "D"],
            question_type=QuestionType.PATTERN,
            difficulty=DifficultyLevel.MEDIUM,
            judge_feedback="Multiple issues found",
            scores={
                "clarity": 0.5,
                "difficulty": 0.4,
                "validity": 0.9,
                "formatting": 0.8,
                "creativity": 0.3,
            },
        )

        # Weak scores should be highlighted
        assert "CLARITY" in prompt
        assert "DIFFICULTY" in prompt
        assert "CREATIVITY" in prompt
        # Strong scores should not be in weak areas section
        assert "VALIDITY" not in prompt.split("WEAK SCORES")[1].split("REGENERATION")[0]
        assert (
            "FORMATTING" not in prompt.split("WEAK SCORES")[1].split("REGENERATION")[0]
        )

    def test_regeneration_prompt_memory_question_without_stimulus(self):
        """Test regeneration prompt for memory question without original stimulus."""
        prompt = build_regeneration_prompt(
            original_question="What color was mentioned first?",
            original_answer="red",
            original_options=["red", "blue", "green", "yellow"],
            question_type=QuestionType.MEMORY,
            difficulty=DifficultyLevel.EASY,
            judge_feedback="Question cannot be answered without stimulus",
            scores={"validity": 0.3},
        )

        # Should include memory-specific requirements
        assert "MEMORY QUESTION SPECIFIC" in prompt
        assert '"stimulus"' in prompt
        assert "shown first, then hidden" in prompt.lower()
        # Should not have stimulus section since none was provided
        assert "Stimulus (content to memorize):" not in prompt

    def test_regeneration_prompt_memory_question_with_stimulus(self):
        """Test regeneration prompt for memory question with original stimulus."""
        stimulus = "maple, oak, dolphin, cherry, whale, birch, salmon"
        prompt = build_regeneration_prompt(
            original_question="Which item was a mammal?",
            original_answer="whale",
            original_options=["whale", "maple", "oak", "birch"],
            question_type=QuestionType.MEMORY,
            difficulty=DifficultyLevel.MEDIUM,
            judge_feedback="Question too easy, doesn't test enough recall",
            scores={"difficulty": 0.4, "validity": 0.8},
            original_stimulus=stimulus,
        )

        # Should include the original stimulus
        assert stimulus in prompt
        assert "Stimulus (content to memorize):" in prompt
        # Should include memory-specific requirements
        assert "MEMORY QUESTION SPECIFIC" in prompt
        assert '"stimulus"' in prompt

    def test_regeneration_prompt_non_memory_no_memory_requirements(self):
        """Test that non-memory questions don't include memory-specific requirements."""
        prompt = build_regeneration_prompt(
            original_question="What comes next: 2, 4, 6, ?",
            original_answer="8",
            original_options=["7", "8", "9", "10"],
            question_type=QuestionType.PATTERN,
            difficulty=DifficultyLevel.EASY,
            judge_feedback="Pattern too obvious",
            scores={"creativity": 0.4},
        )

        assert "MEMORY QUESTION SPECIFIC" not in prompt
        assert "Stimulus (content to memorize):" not in prompt

    def test_regeneration_prompt_includes_original_options(self):
        """Test that original options are included in the prompt."""
        options = ["Option 1", "Option 2", "Option 3", "Option 4"]
        prompt = build_regeneration_prompt(
            original_question="Test question",
            original_answer="Option 2",
            original_options=options,
            question_type=QuestionType.VERBAL,
            difficulty=DifficultyLevel.MEDIUM,
            judge_feedback="Distractors not plausible",
            scores={"formatting": 0.5},
        )

        # Options should be in the prompt (as a list representation)
        for option in options:
            assert option in prompt

    def test_regeneration_prompt_json_format(self):
        """Test that regeneration prompt specifies JSON output format."""
        prompt = build_regeneration_prompt(
            original_question="Test",
            original_answer="Answer",
            original_options=["A", "B"],
            question_type=QuestionType.SPATIAL,
            difficulty=DifficultyLevel.HARD,
            judge_feedback="Needs work",
            scores={"clarity": 0.6},
        )

        assert "JSON" in prompt
        assert '"question_text"' in prompt
        assert '"correct_answer"' in prompt
        assert '"answer_options"' in prompt
        assert '"explanation"' in prompt

    def test_regeneration_prompt_all_scores_above_threshold(self):
        """Test prompt when all scores are above threshold shows default message."""
        prompt = build_regeneration_prompt(
            original_question="Test",
            original_answer="Answer",
            original_options=["A", "B", "C"],
            question_type=QuestionType.MATH,
            difficulty=DifficultyLevel.EASY,
            judge_feedback="Minor issues only",
            scores={
                "clarity": 0.8,
                "difficulty": 0.75,
                "validity": 0.9,
                "formatting": 0.85,
                "creativity": 0.7,
            },
        )

        assert "Multiple areas need improvement" in prompt
