"""
Utility functions for working with Question models and schemas.
"""

from app.models.models import Question
from app.schemas.questions import QuestionResponse


def question_to_response(
    question: Question, include_explanation: bool = False
) -> QuestionResponse:
    """
    Convert a Question model to QuestionResponse schema.

    Handles conversion of answer_options from dict to list format if needed.
    This is necessary because the database stores answer_options as JSON (which can be dict),
    but the Pydantic schema expects a list for consistency with the iOS app.

    Args:
        question: The Question model instance to convert
        include_explanation: Whether to include the explanation field (default: False)

    Returns:
        QuestionResponse schema with properly formatted answer_options
    """
    # Convert answer_options dict to list if necessary
    answer_options = question.answer_options
    if answer_options and isinstance(answer_options, dict):
        # Convert dict format {"A": "option1", "B": "option2"} to list
        answer_options = [answer_options[key] for key in sorted(answer_options.keys())]

    return QuestionResponse.model_validate(
        {
            "id": question.id,
            "question_text": question.question_text,
            "question_type": question.question_type.value,
            "difficulty_level": question.difficulty_level.value,
            "answer_options": answer_options,
            "explanation": question.explanation if include_explanation else None,
            "stimulus": question.stimulus,
            "sub_type": question.sub_type,
            "inferred_sub_type": question.inferred_sub_type,
        }
    )
