"""
Read-only admin views for all database models.
"""

# mypy: disable-error-code="list-item,arg-type,dict-item"
from sqladmin import ModelView
from markupsafe import Markup

from app.core.psychometrics.question_analytics import (
    MIN_RESPONSES_FOR_CALIBRATION as RELIABLE_RESPONSE_COUNT,
    MIN_RESPONSES_FOR_SUFFICIENT_DATA as MIN_RESPONSES_FOR_QUALITY_ANALYSIS,
    POOR_DISCRIMINATION_THRESHOLD as ACCEPTABLE_DISCRIMINATION,
)
from app.models import (
    User,
    Question,
    UserQuestion,
    TestSession,
    Response,
    TestResult,
    DifficultyLevel,
)

# Discrimination display thresholds — view-local, no canonical source yet
GOOD_DISCRIMINATION = 0.3
EXCELLENT_DISCRIMINATION = 0.4

# Difficulty calibration thresholds (p-value = proportion correct)
# Used for coloring empirical difficulty display
EASY_P_VALUE_THRESHOLD = 0.7
MEDIUM_P_VALUE_THRESHOLD = 0.4

# Mismatch detection thresholds — flag when empirical difficulty diverges from assigned
EASY_TOO_HARD_THRESHOLD = 0.5
MEDIUM_TOO_HARD_THRESHOLD = 0.3
MEDIUM_TOO_EASY_THRESHOLD = 0.8
HARD_TOO_EASY_THRESHOLD = 0.6


class ReadOnlyModelView(ModelView):
    """
    Base class for read-only admin views.

    Disables all create, edit, and delete operations.
    """

    can_create = False
    can_edit = False
    can_delete = False
    can_export = True  # Allow data export
    page_size = 50  # Show 50 records per page
    page_size_options = [25, 50, 100, 200]


class UserAdmin(ReadOnlyModelView, model=User):
    """Admin view for User model."""

    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"

    # Columns to display in list view
    column_list = [
        User.id,
        User.email,
        User.first_name,
        User.last_name,
        User.created_at,
        User.last_login_at,
        User.notification_enabled,
    ]

    # Columns to show in detail view
    column_details_list = [
        User.id,
        User.email,
        User.first_name,
        User.last_name,
        User.created_at,
        User.last_login_at,
        User.notification_enabled,
        User.apns_device_token,
    ]

    # Searchable columns
    column_searchable_list = [User.email, User.first_name, User.last_name]

    # Sortable columns
    column_sortable_list = [User.id, User.email, User.created_at, User.last_login_at]

    # Default sort order
    column_default_sort = [(User.created_at, True)]  # Descending order


class QuestionAdmin(ReadOnlyModelView, model=Question):
    """
    Admin view for Question model with quality analytics.

    Displays question performance statistics and flags quality issues such as:
    - Difficulty mismatches (empirical vs. LLM-assigned)
    - Low discrimination (poor ability to distinguish high/low performers)
    - Insufficient response data
    """

    name = "Question"
    name_plural = "Questions"
    icon = "fa-solid fa-question"

    column_list = [
        Question.id,
        Question.question_type,
        Question.difficulty_level,
        "quality_status",  # Custom column
        Question.response_count,
        Question.empirical_difficulty,
        Question.discrimination,
        Question.judge_score,
        Question.source_llm,
        Question.source_model,
        Question.is_active,
    ]

    column_details_list = [
        Question.id,
        Question.question_text,
        Question.question_type,
        Question.difficulty_level,
        Question.correct_answer,
        Question.answer_options,
        Question.explanation,
        # Performance Statistics
        Question.response_count,
        Question.empirical_difficulty,
        Question.discrimination,
        # LLM Metadata
        Question.source_llm,
        Question.source_model,
        Question.judge_score,
        Question.question_metadata,
        # IRT Fields (future use)
        Question.irt_difficulty,
        Question.irt_discrimination,
        Question.irt_guessing,
        # Status
        Question.created_at,
        Question.is_active,
    ]

    column_searchable_list = [
        Question.question_text,
        Question.source_llm,
        Question.source_model,
    ]

    column_sortable_list = [
        Question.id,
        Question.question_type,
        Question.difficulty_level,
        Question.judge_score,
        Question.created_at,
        Question.response_count,
        Question.empirical_difficulty,
        Question.discrimination,
    ]

    column_default_sort = [
        (Question.response_count, True)
    ]  # Show most-used questions first

    # Add filters for quality monitoring
    column_filters = [
        Question.question_type,
        Question.difficulty_level,
        Question.is_active,
        Question.source_llm,
        Question.source_model,
        Question.response_count,
        Question.discrimination,
    ]

    # Custom column formatters for quality indicators
    column_formatters = {
        "quality_status": lambda m, a: QuestionAdmin._format_quality_status(m),
        Question.empirical_difficulty: lambda m, a: QuestionAdmin._format_empirical_difficulty(
            m
        ),
        Question.discrimination: lambda m, a: QuestionAdmin._format_discrimination(m),
        Question.response_count: lambda m, a: QuestionAdmin._format_response_count(m),
    }

    # Column labels
    column_labels = {
        "quality_status": "Quality",
        Question.empirical_difficulty: "P-Value (Empirical)",
        Question.discrimination: "Discrimination",
        Question.response_count: "Responses",
        Question.judge_score: "Judge Score",
        Question.irt_difficulty: "IRT: b (difficulty)",
        Question.irt_discrimination: "IRT: a (discrimination)",
        Question.irt_guessing: "IRT: c (guessing)",
    }

    @staticmethod
    def _format_quality_status(model: Question) -> Markup:
        """
        Display quality status badge based on multiple criteria:
        - Response count (sufficient data?)
        - Difficulty mismatch (empirical vs LLM-assigned)
        - Discrimination quality (ability to distinguish performers)
        """
        if (
            model.response_count is None
            or model.response_count < MIN_RESPONSES_FOR_QUALITY_ANALYSIS
        ):
            # Insufficient data - gray badge
            return Markup(
                '<span class="badge badge-secondary" title="Insufficient response data for analysis">'
                f"📊 Pending ({model.response_count or 0} responses)"
                "</span>"
            )

        issues = []

        # Check for difficulty mismatch
        if model.empirical_difficulty is not None:
            difficulty_mismatch = QuestionAdmin._check_difficulty_mismatch(
                model.difficulty_level, model.empirical_difficulty
            )
            if difficulty_mismatch:
                issues.append(f"Difficulty mismatch: {difficulty_mismatch}")

        # Check for low discrimination
        if (
            model.discrimination is not None
            and model.discrimination < ACCEPTABLE_DISCRIMINATION
        ):
            issues.append(f"Low discrimination: {model.discrimination:.2f}")

        # Return appropriate badge
        if not issues:
            # Good quality - green badge
            return Markup(
                '<span class="badge badge-success" title="Question performing well">✓ Good</span>'
            )
        else:
            # Issues detected - red badge with tooltip
            tooltip = "; ".join(issues)
            return Markup(
                f'<span class="badge badge-danger" title="{tooltip}">⚠ Review Needed</span>'
            )

    @staticmethod
    def _check_difficulty_mismatch(
        assigned_difficulty: DifficultyLevel, p_value: float
    ) -> str:
        """
        Check if empirical difficulty matches LLM-assigned difficulty.

        P-value interpretation (proportion correct):
        - Easy questions: p-value should be > 0.7
        - Medium questions: p-value should be 0.4-0.7
        - Hard questions: p-value should be < 0.4

        Returns:
            Empty string if match is good, otherwise description of mismatch
        """
        if assigned_difficulty == DifficultyLevel.EASY:
            expected = "easy (p > 0.7)"
            if p_value < EASY_TOO_HARD_THRESHOLD:
                return f"Too hard (p={p_value:.2f}, expected {expected})"
        elif assigned_difficulty == DifficultyLevel.MEDIUM:
            expected = "medium (0.4 < p < 0.7)"
            if p_value < MEDIUM_TOO_HARD_THRESHOLD:
                return f"Too hard (p={p_value:.2f}, expected {expected})"
            elif p_value > MEDIUM_TOO_EASY_THRESHOLD:
                return f"Too easy (p={p_value:.2f}, expected {expected})"
        elif assigned_difficulty == DifficultyLevel.HARD:
            expected = "hard (p < 0.4)"
            if p_value > HARD_TOO_EASY_THRESHOLD:
                return f"Too easy (p={p_value:.2f}, expected {expected})"

        return ""

    @staticmethod
    def _format_empirical_difficulty(model: Question) -> Markup:
        """Format empirical difficulty (p-value) with color coding."""
        if model.empirical_difficulty is None:
            return Markup('<span class="text-muted">N/A</span>')

        p_value = model.empirical_difficulty

        # Color code based on value (easier questions = higher p-value = green)
        if p_value > EASY_P_VALUE_THRESHOLD:
            color = "success"
            label = "Easy"
        elif p_value > MEDIUM_P_VALUE_THRESHOLD:
            color = "warning"
            label = "Medium"
        else:
            color = "danger"
            label = "Hard"

        return Markup(
            f'<span class="text-{color}" title="Proportion correct: {label}">'
            f"{p_value:.3f}"
            "</span>"
        )

    @staticmethod
    def _format_discrimination(model: Question) -> Markup:
        """Format discrimination value with color coding."""
        if model.discrimination is None:
            return Markup('<span class="text-muted">N/A</span>')

        disc = model.discrimination

        # Color code based on quality thresholds
        # Discrimination > 0.4 = excellent, > 0.3 = good, > 0.2 = acceptable, < 0.2 = poor
        if disc >= EXCELLENT_DISCRIMINATION:
            color = "success"
            label = "Excellent"
        elif disc >= GOOD_DISCRIMINATION:
            color = "info"
            label = "Good"
        elif disc >= ACCEPTABLE_DISCRIMINATION:
            color = "warning"
            label = "Acceptable"
        else:
            color = "danger"
            label = "Poor"

        return Markup(
            f'<span class="text-{color}" title="{label} discrimination">'
            f"{disc:.3f}"
            "</span>"
        )

    @staticmethod
    def _format_response_count(model: Question) -> Markup:
        """Format response count with indicator for statistical reliability."""
        if model.response_count is None or model.response_count == 0:
            return Markup('<span class="text-muted">0</span>')

        count = model.response_count

        # Color code based on statistical reliability
        # < 30 = insufficient, 30-100 = marginal, 100+ = reliable
        if count >= RELIABLE_RESPONSE_COUNT:
            color = "success"
            title = "Statistically reliable"
        elif count >= MIN_RESPONSES_FOR_QUALITY_ANALYSIS:
            color = "warning"
            title = "Marginally reliable"
        else:
            color = "secondary"
            title = "Insufficient data"

        return Markup(
            f'<span class="badge badge-{color}" title="{title}">{count}</span>'
        )


class UserQuestionAdmin(ReadOnlyModelView, model=UserQuestion):
    """Admin view for UserQuestion junction table."""

    name = "User Question"
    name_plural = "User Questions"
    icon = "fa-solid fa-link"

    column_list = [
        UserQuestion.id,
        UserQuestion.user_id,
        UserQuestion.question_id,
        UserQuestion.seen_at,
    ]

    column_sortable_list = [
        UserQuestion.id,
        UserQuestion.user_id,
        UserQuestion.question_id,
        UserQuestion.seen_at,
    ]

    column_default_sort = [(UserQuestion.seen_at, True)]

    column_filters = [UserQuestion.user_id, UserQuestion.question_id]


class TestSessionAdmin(ReadOnlyModelView, model=TestSession):
    """Admin view for TestSession model."""

    name = "Test Session"
    name_plural = "Test Sessions"
    icon = "fa-solid fa-clipboard"

    column_list = [
        TestSession.id,
        TestSession.user_id,
        TestSession.started_at,
        TestSession.completed_at,
        TestSession.status,
    ]

    column_sortable_list = [
        TestSession.id,
        TestSession.user_id,
        TestSession.started_at,
        TestSession.completed_at,
    ]

    column_default_sort = [(TestSession.started_at, True)]

    column_filters = [TestSession.user_id, TestSession.status]


class ResponseAdmin(ReadOnlyModelView, model=Response):
    """Admin view for Response model."""

    name = "Response"
    name_plural = "Responses"
    icon = "fa-solid fa-reply"

    column_list = [
        Response.id,
        Response.test_session_id,
        Response.user_id,
        Response.question_id,
        Response.is_correct,
        Response.answered_at,
    ]

    column_details_list = [
        Response.id,
        Response.test_session_id,
        Response.user_id,
        Response.question_id,
        Response.user_answer,
        Response.is_correct,
        Response.answered_at,
    ]

    column_sortable_list = [
        Response.id,
        Response.test_session_id,
        Response.user_id,
        Response.question_id,
        Response.answered_at,
    ]

    column_default_sort = [(Response.answered_at, True)]

    column_filters = [
        Response.test_session_id,
        Response.user_id,
        Response.question_id,
        Response.is_correct,
    ]


class TestResultAdmin(ReadOnlyModelView, model=TestResult):
    """Admin view for TestResult model."""

    name = "Test Result"
    name_plural = "Test Results"
    icon = "fa-solid fa-chart-line"

    column_list = [
        TestResult.id,
        TestResult.test_session_id,
        TestResult.user_id,
        TestResult.iq_score,
        TestResult.total_questions,
        TestResult.correct_answers,
        TestResult.completion_time_seconds,
        TestResult.completed_at,
    ]

    column_sortable_list = [
        TestResult.id,
        TestResult.user_id,
        TestResult.iq_score,
        TestResult.completed_at,
    ]

    column_default_sort = [(TestResult.completed_at, True)]

    column_filters = [TestResult.user_id, TestResult.iq_score]
