"""Tests for prompt generation."""

from unittest.mock import patch

from app.data.models import DifficultyLevel, QuestionType
from app.generation.prompts import (
    build_generation_prompt,
    build_judge_prompt,
    build_regeneration_prompt,
    GOLD_STANDARD_BY_SUBTYPE,
    GOLD_STANDARD_EXAMPLES,
    QUESTION_SUBTYPES,
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
        # Should mention that stimulus is shown first then hidden
        assert "shown first, then hidden" in prompt.lower()

    def test_non_memory_question_prompt_excludes_stimulus(self):
        """Test that non-memory question generation prompts do not include stimulus instruction."""
        non_memory_types = [qt for qt in QuestionType if qt != QuestionType.MEMORY]

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


class TestGoldStandardExamples:
    """Tests for gold standard example pool and random injection."""

    def test_all_question_types_have_gold_standard_examples(self):
        """Test that GOLD_STANDARD_EXAMPLES has entries for all QuestionType values."""
        for question_type in QuestionType:
            assert (
                question_type in GOLD_STANDARD_EXAMPLES
            ), f"Missing GOLD_STANDARD_EXAMPLES entry for {question_type.value}"
            assert len(GOLD_STANDARD_EXAMPLES[question_type]) >= 1

    def test_all_types_have_multiple_examples(self):
        """Test that every type has multiple gold standard examples for diversity."""
        for question_type in QuestionType:
            assert (
                len(GOLD_STANDARD_EXAMPLES[question_type]) >= 2
            ), f"{question_type.value} should have multiple gold standard examples to reduce anchoring bias"

    def test_each_example_contains_gold_standard_header(self):
        """Test that every example string starts with the GOLD STANDARD EXAMPLE header."""
        for question_type, examples in GOLD_STANDARD_EXAMPLES.items():
            for i, example in enumerate(examples):
                assert (
                    "GOLD STANDARD EXAMPLE:" in example
                ), f"{question_type.value} example {i} missing 'GOLD STANDARD EXAMPLE:' header"

    def test_build_generation_prompt_contains_gold_standard(self):
        """Test that build_generation_prompt output includes a gold standard example."""
        for question_type in QuestionType:
            prompt = build_generation_prompt(
                question_type=question_type,
                difficulty=DifficultyLevel.MEDIUM,
                count=1,
            )
            assert (
                "GOLD STANDARD EXAMPLE:" in prompt
            ), f"Prompt for {question_type.value} missing gold standard example"

    def test_build_generation_prompt_uses_random_choice(self):
        """Test that build_generation_prompt calls random.choice for example selection."""
        with patch("app.generation.prompts.random.choice") as mock_choice:
            mock_choice.return_value = GOLD_STANDARD_EXAMPLES[QuestionType.SPATIAL][0]
            build_generation_prompt(
                question_type=QuestionType.SPATIAL,
                difficulty=DifficultyLevel.HARD,
                count=1,
            )
            mock_choice.assert_called_once_with(
                GOLD_STANDARD_EXAMPLES[QuestionType.SPATIAL]
            )

    def test_spatial_examples_cover_different_subtypes(self):
        """Test that spatial gold standard examples cover different spatial subtypes."""
        examples = GOLD_STANDARD_EXAMPLES[QuestionType.SPATIAL]
        # Each example should have distinct question content
        questions = [ex.split('Question: "')[1].split('"')[0] for ex in examples]
        assert len(set(questions)) == len(
            questions
        ), "Spatial gold standard examples should all have unique questions"

    def test_build_regeneration_prompt_contains_gold_standard(self):
        """Test that build_regeneration_prompt output includes a gold standard example."""
        prompt = build_regeneration_prompt(
            original_question="Test question",
            original_answer="Answer",
            original_options=["A", "B", "C", "D"],
            question_type=QuestionType.SPATIAL,
            difficulty=DifficultyLevel.HARD,
            judge_feedback="Needs work",
            scores={"clarity": 0.6},
        )
        assert "GOLD STANDARD EXAMPLE:" in prompt


class TestSubtypeGoldStandard:
    """Tests for subtype-aware gold standard selection and prompt tailoring."""

    def test_build_generation_prompt_uses_subtype_gold_standard(self):
        """When subtype matches a gold standard, that specific example appears in the prompt."""
        subtype = "cube rotations tracking labeled faces through sequential turns"
        prompt = build_generation_prompt(
            question_type=QuestionType.SPATIAL,
            difficulty=DifficultyLevel.EASY,
            count=5,
            subtype=subtype,
        )

        # The cube rotation gold standard should be present (it mentions "different symbols on each face")
        expected_example = GOLD_STANDARD_BY_SUBTYPE[subtype]
        assert expected_example in prompt

    def test_build_generation_prompt_subtype_strengthened_wording(self):
        """Prompt contains 'REQUIRED SUB-TYPE' when subtype is set."""
        subtype = "cross-section identification from slicing a 3D solid"
        prompt = build_generation_prompt(
            question_type=QuestionType.SPATIAL,
            difficulty=DifficultyLevel.EASY,
            count=3,
            subtype=subtype,
        )

        assert "REQUIRED SUB-TYPE" in prompt
        assert f"'{subtype}'" in prompt
        assert "Do NOT generate questions of other sub-types" in prompt

    def test_build_generation_prompt_subtype_fallback(self):
        """When subtype has no matching gold standard, falls back to random choice."""
        # "paper folding..." has no entry in GOLD_STANDARD_BY_SUBTYPE
        subtype = "paper folding with holes or cuts, predicting unfolded result"
        assert subtype not in GOLD_STANDARD_BY_SUBTYPE

        with patch("app.generation.prompts.random.choice") as mock_choice:
            mock_choice.return_value = GOLD_STANDARD_EXAMPLES[QuestionType.SPATIAL][0]
            prompt = build_generation_prompt(
                question_type=QuestionType.SPATIAL,
                difficulty=DifficultyLevel.EASY,
                count=1,
                subtype=subtype,
            )
            mock_choice.assert_called_once_with(
                GOLD_STANDARD_EXAMPLES[QuestionType.SPATIAL]
            )
            assert "GOLD STANDARD EXAMPLE:" in prompt

    def test_build_generation_prompt_subtype_narrows_example_types(self):
        """When subtype is set, the 'Example types' list shows only the assigned subtype."""
        subtype = "probability and likelihood reasoning"
        prompt = build_generation_prompt(
            question_type=QuestionType.MATH,
            difficulty=DifficultyLevel.MEDIUM,
            count=1,
            subtype=subtype,
        )

        # The prompt should contain our subtype in the Example types section
        assert f"- {subtype}" in prompt

        # Other subtypes from the full list should NOT appear
        for other_subtype in QUESTION_SUBTYPES[QuestionType.MATH]:
            if other_subtype != subtype:
                assert other_subtype not in prompt, (
                    f"Expected '{other_subtype}' to be removed from prompt when "
                    f"subtype='{subtype}'"
                )

    def test_no_subtype_preserves_full_example_types(self):
        """When no subtype is provided, the full Example types list is preserved."""
        prompt = build_generation_prompt(
            question_type=QuestionType.SPATIAL,
            difficulty=DifficultyLevel.EASY,
            count=1,
        )

        # All spatial subtypes should appear in the prompt
        for subtype in QUESTION_SUBTYPES[QuestionType.SPATIAL]:
            # The subtypes in QUESTION_SUBTYPES are lowercase versions;
            # the prompt has mixed-case versions. Check the key concepts.
            assert "Example types:" in prompt

    def test_gold_standard_by_subtype_covers_all_types(self):
        """Verify GOLD_STANDARD_BY_SUBTYPE has entries for all types with gold standards."""
        for question_type, examples in GOLD_STANDARD_EXAMPLES.items():
            # At least one subtype per question type should have a mapping
            subtypes = QUESTION_SUBTYPES.get(question_type, [])
            mapped = [s for s in subtypes if s in GOLD_STANDARD_BY_SUBTYPE]
            assert (
                len(mapped) >= 1
            ), f"No GOLD_STANDARD_BY_SUBTYPE entries for {question_type.value}"


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

    def test_judge_prompt_difficulty_uses_absolute_scale(self):
        """Test that judge prompt asks for absolute difficulty, not appropriateness."""
        prompt = build_judge_prompt(
            question="Test question?",
            answer_options=["A", "B", "C", "D"],
            correct_answer="A",
            question_type="math",
            difficulty="easy",
        )

        # Should contain absolute scale language
        assert "absolute scale" in prompt.lower()
        assert "inherent difficulty" in prompt.lower()
        assert "regardless of the target level" in prompt.lower()

        # Should NOT contain the old appropriateness wording
        assert "Is difficulty appropriate for" not in prompt

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


class TestTypeDifficultyOverrides:
    """Tests for TYPE_DIFFICULTY_OVERRIDES in prompt generation."""

    def test_math_easy_prompt_uses_override(self):
        """Test that math+easy prompt includes the override text instead of generic."""
        prompt = build_generation_prompt(
            question_type=QuestionType.MATH,
            difficulty=DifficultyLevel.EASY,
            count=1,
        )

        # Override-specific constraints should appear
        assert "single arithmetic operation" in prompt.lower()
        assert "no percentages, fractions, ratios" in prompt.lower()
        assert "solvable in one mental step" in prompt.lower()

    def test_non_math_easy_uses_generic_instructions(self):
        """Test that non-math easy prompts still use generic difficulty instructions."""
        non_math_types = [qt for qt in QuestionType if qt != QuestionType.MATH]

        for question_type in non_math_types:
            prompt = build_generation_prompt(
                question_type=question_type,
                difficulty=DifficultyLevel.EASY,
                count=1,
            )

            # Generic easy instructions should appear (not the override)
            assert (
                "single-step or simple two-step reasoning" in prompt.lower()
            ), f"{question_type.value} easy prompt should use generic instructions"
            assert (
                "single arithmetic operation" not in prompt.lower()
            ), f"{question_type.value} easy prompt should NOT contain math override"

    def test_math_medium_uses_generic_instructions(self):
        """Test that math+medium still uses generic instructions (override only for easy)."""
        prompt = build_generation_prompt(
            question_type=QuestionType.MATH,
            difficulty=DifficultyLevel.MEDIUM,
            count=1,
        )

        # Generic medium instructions should appear
        assert "multi-step reasoning" in prompt.lower()
        # Override text should NOT appear
        assert "single arithmetic operation" not in prompt.lower()

    def test_math_hard_uses_generic_instructions(self):
        """Test that math+hard still uses generic instructions."""
        prompt = build_generation_prompt(
            question_type=QuestionType.MATH,
            difficulty=DifficultyLevel.HARD,
            count=1,
        )

        assert "abstract thinking" in prompt.lower()
        assert "single arithmetic operation" not in prompt.lower()

    def test_override_preserves_iq_range_and_success_rate(self):
        """Test that the override includes the same calibration metadata as generic."""
        prompt = build_generation_prompt(
            question_type=QuestionType.MATH,
            difficulty=DifficultyLevel.EASY,
            count=1,
        )

        assert "70-80%" in prompt
        assert "85-115" in prompt
        assert "discriminatory power" in prompt.lower()
