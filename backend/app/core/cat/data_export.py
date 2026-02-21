r"""
IRT calibration data export utilities.

Exports response data for IRT calibration. Phase 1 of CAT implementation.

CLI Usage:
    python -m app.core.cat.data_export \
        --start-date 2026-01-01 \
        --output calibration_data.csv \
        [--question-ids 1,2,3] \
        [--min-responses 10] \
        [--format csv|jsonl] \
        [--export-type responses|matrix|details|ctt-summary]
"""

import argparse
import csv
import io
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, TypedDict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import Question, Response, TestSession, TestStatus

logger = logging.getLogger(__name__)

# Constants for minimum response thresholds
MIN_RESPONSES_DEFAULT = 10  # Default minimum responses per question


class DataExportError(Exception):
    """Custom exception for data export errors."""

    def __init__(
        self,
        message: str,
        original_error: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Initialize with message, optional cause, and structured context."""
        self.message = message
        self.original_error = original_error
        self.context = context or {}
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format error message with context."""
        msg = self.message
        if self.context:
            ctx_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            msg = f"{msg} (context: {ctx_str})"
        if self.original_error:
            msg = f"{msg} - caused by: {str(self.original_error)}"
        return msg


class ResponseExportData(TypedDict):
    """Response data structure for calibration export."""

    user_id: int
    question_id: int
    is_correct: int  # 0 or 1
    response_time: Optional[int]  # seconds, nullable
    test_session_id: int
    completed_at: str  # ISO timestamp


class ResponseMatrixRow(TypedDict):
    """Row structure for response matrix export."""

    user_id: int
    # Dynamic keys for question_id columns with values: 1, 0, or None


class ResponseDetailData(TypedDict):
    """Detailed response data with question statistics."""

    user_id: int
    question_id: int
    is_correct: int
    time_spent_seconds: Optional[int]
    question_type: str
    difficulty_level: str
    empirical_difficulty: Optional[float]
    discrimination: Optional[float]


class CTTSummaryData(TypedDict):
    """CTT summary statistics per question."""

    question_id: int
    question_type: str
    difficulty_level: str
    empirical_difficulty: Optional[float]
    discrimination: Optional[float]
    response_count: int


def export_responses_for_calibration(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    question_ids: Optional[List[int]] = None,
    min_responses: int = MIN_RESPONSES_DEFAULT,
    output_format: str = "csv",
) -> str:
    """
    Export response data for IRT calibration.

    This function exports detailed response data from completed, fixed-form tests
    in a format suitable for IRT calibration tools.

    Args:
        db: SQLAlchemy session
        start_date: Filter by date range start (optional)
        end_date: Filter by date range end (optional)
        question_ids: Optional list of question IDs to filter
        min_responses: Minimum response count per question (default: 10)
        output_format: Output format - "csv" or "jsonl"

    Returns:
        String containing the exported data in the requested format

    Raises:
        DataExportError: If export fails
    """
    try:
        logger.info(
            f"Starting calibration data export: format={output_format}, "
            f"min_responses={min_responses}, "
            f"start_date={start_date}, end_date={end_date}"
        )

        # Build base query for responses from completed, fixed-form sessions
        query = (
            db.query(
                Response.user_id,
                Response.question_id,
                Response.is_correct,
                Response.time_spent_seconds,
                Response.test_session_id,
                TestSession.completed_at,
            )
            .join(TestSession, Response.test_session_id == TestSession.id)
            .filter(TestSession.status == TestStatus.COMPLETED)
            .filter(TestSession.is_adaptive == False)  # noqa: E712
        )

        # Apply date filters
        if start_date:
            query = query.filter(TestSession.completed_at >= start_date)
            logger.debug(f"Filtering responses after {start_date}")

        if end_date:
            query = query.filter(TestSession.completed_at <= end_date)
            logger.debug(f"Filtering responses before {end_date}")

        # Get all responses
        responses = query.all()
        logger.debug(f"Retrieved {len(responses)} total responses")

        # Count responses per question
        question_response_counts: Dict[int, int] = {}
        for response in responses:
            qid = response.question_id
            question_response_counts[qid] = question_response_counts.get(qid, 0) + 1

        # Filter questions by min_responses threshold
        eligible_questions = {
            qid
            for qid, count in question_response_counts.items()
            if count >= min_responses
        }

        if question_ids:
            # Further filter by requested question IDs
            eligible_questions = eligible_questions.intersection(set(question_ids))
            logger.debug(
                f"Filtered to {len(eligible_questions)} requested question IDs"
            )

        logger.debug(
            f"Filtered to {len(eligible_questions)} questions with >= {min_responses} responses"
        )

        # Filter responses to only include eligible questions
        filtered_responses = [
            r for r in responses if r.question_id in eligible_questions
        ]

        logger.info(
            f"Exporting {len(filtered_responses)} responses for "
            f"{len(eligible_questions)} questions"
        )

        if not filtered_responses:
            logger.warning("No responses match the filter criteria")
            return "" if output_format == "csv" else ""

        # Convert to export format
        export_data: List[ResponseExportData] = [
            {
                "user_id": r.user_id,
                "question_id": r.question_id,
                "is_correct": 1 if r.is_correct else 0,
                "response_time": r.time_spent_seconds,
                "test_session_id": r.test_session_id,
                "completed_at": r.completed_at.isoformat(),
            }
            for r in filtered_responses
        ]

        # Generate output
        if output_format == "csv":
            return _generate_csv(export_data)
        elif output_format == "jsonl":
            return _generate_jsonl(export_data)
        else:
            raise DataExportError(
                f"Invalid output format: {output_format}",
                context={"valid_formats": ["csv", "jsonl"]},
            )

    except DataExportError:
        raise
    except Exception as e:
        logger.exception("Failed to export calibration data")
        raise DataExportError(
            "Failed to export calibration data",
            original_error=e,
            context={
                "format": output_format,
                "min_responses": min_responses,
            },
        ) from e


def export_response_matrix(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    question_ids: Optional[List[int]] = None,
    min_responses: int = MIN_RESPONSES_DEFAULT,
) -> str:
    """
    Export response matrix (users x items binary matrix).

    Rows = users, Columns = question IDs
    Values: 1 (correct), 0 (incorrect), empty (not attempted)

    Args:
        db: SQLAlchemy session
        start_date: Filter by date range start (optional)
        end_date: Filter by date range end (optional)
        question_ids: Optional list of question IDs to filter
        min_responses: Minimum response count per question (default: 10)

    Returns:
        CSV string with user_id as first column, question IDs as headers

    Raises:
        DataExportError: If export fails
    """
    try:
        logger.info("Starting response matrix export")

        # Build base query for responses from completed, fixed-form sessions
        query = (
            db.query(
                Response.user_id,
                Response.question_id,
                Response.is_correct,
            )
            .join(TestSession, Response.test_session_id == TestSession.id)
            .filter(TestSession.status == TestStatus.COMPLETED)
            .filter(TestSession.is_adaptive == False)  # noqa: E712
        )

        if start_date:
            query = query.filter(TestSession.completed_at >= start_date)
        if end_date:
            query = query.filter(TestSession.completed_at <= end_date)

        responses = query.all()

        # Count responses per question and filter by min_responses
        question_response_counts: Dict[int, int] = {}
        for response in responses:
            qid = response.question_id
            question_response_counts[qid] = question_response_counts.get(qid, 0) + 1

        eligible_questions = {
            qid
            for qid, count in question_response_counts.items()
            if count >= min_responses
        }

        if question_ids:
            eligible_questions = eligible_questions.intersection(set(question_ids))

        # Filter responses
        filtered_responses = [
            r for r in responses if r.question_id in eligible_questions
        ]

        if not filtered_responses:
            logger.warning("No responses match the filter criteria")
            return ""

        # Build matrix data structure
        # user_id -> question_id -> is_correct (1 or 0)
        matrix: Dict[int, Dict[int, int]] = {}
        for r in filtered_responses:
            if r.user_id not in matrix:
                matrix[r.user_id] = {}
            matrix[r.user_id][r.question_id] = 1 if r.is_correct else 0

        # Sort question IDs for consistent output
        sorted_question_ids = sorted(eligible_questions)
        user_ids = sorted(matrix.keys())

        logger.info(
            f"Exporting matrix: {len(user_ids)} users x {len(sorted_question_ids)} questions"
        )

        # Generate CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # Header row: user_id, then question IDs
        writer.writerow(["user_id"] + sorted_question_ids)

        # Data rows
        for user_id in user_ids:
            row: List[Any] = [user_id]
            for qid in sorted_question_ids:
                # Use empty string for not attempted (NaN equivalent)
                value = matrix[user_id].get(qid, "")
                row.append(value)
            writer.writerow(row)

        return output.getvalue()

    except Exception as e:
        logger.exception("Failed to export response matrix")
        raise DataExportError(
            "Failed to export response matrix",
            original_error=e,
            context={"min_responses": min_responses},
        ) from e


def export_response_details(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    question_ids: Optional[List[int]] = None,
    min_responses: int = MIN_RESPONSES_DEFAULT,
    output_format: str = "csv",
) -> str:
    """
    Export detailed per-response data with question statistics.

    Includes: user_id, question_id, is_correct, time_spent_seconds, question_type,
    difficulty_level, empirical_difficulty, discrimination

    Args:
        db: SQLAlchemy session
        start_date: Filter by date range start (optional)
        end_date: Filter by date range end (optional)
        question_ids: Optional list of question IDs to filter
        min_responses: Minimum response count per question (default: 10)
        output_format: Output format - "csv" or "jsonl"

    Returns:
        String containing the exported data in the requested format

    Raises:
        DataExportError: If export fails
    """
    try:
        logger.info(f"Starting response details export: format={output_format}")

        # Build query with question data from completed, fixed-form sessions
        query = (
            db.query(
                Response.user_id,
                Response.question_id,
                Response.is_correct,
                Response.time_spent_seconds,
                Question.question_type,
                Question.difficulty_level,
                Question.empirical_difficulty,
                Question.discrimination,
            )
            .join(TestSession, Response.test_session_id == TestSession.id)
            .join(Question, Response.question_id == Question.id)
            .filter(TestSession.status == TestStatus.COMPLETED)
            .filter(TestSession.is_adaptive == False)  # noqa: E712
        )

        if start_date:
            query = query.filter(TestSession.completed_at >= start_date)
        if end_date:
            query = query.filter(TestSession.completed_at <= end_date)

        responses = query.all()

        # Count responses per question and filter
        question_response_counts: Dict[int, int] = {}
        for response in responses:
            qid = response.question_id
            question_response_counts[qid] = question_response_counts.get(qid, 0) + 1

        eligible_questions = {
            qid
            for qid, count in question_response_counts.items()
            if count >= min_responses
        }

        if question_ids:
            eligible_questions = eligible_questions.intersection(set(question_ids))

        filtered_responses = [
            r for r in responses if r.question_id in eligible_questions
        ]

        logger.info(f"Exporting {len(filtered_responses)} detailed response records")

        if not filtered_responses:
            logger.warning("No responses match the filter criteria")
            return "" if output_format == "csv" else ""

        # Convert to export format
        export_data: List[ResponseDetailData] = [
            {
                "user_id": r.user_id,
                "question_id": r.question_id,
                "is_correct": 1 if r.is_correct else 0,
                "time_spent_seconds": r.time_spent_seconds,
                "question_type": (
                    r.question_type.value
                    if hasattr(r.question_type, "value")
                    else str(r.question_type)
                ),
                "difficulty_level": (
                    r.difficulty_level.value
                    if hasattr(r.difficulty_level, "value")
                    else str(r.difficulty_level)
                ),
                "empirical_difficulty": r.empirical_difficulty,
                "discrimination": r.discrimination,
            }
            for r in filtered_responses
        ]

        # Generate output
        if output_format == "csv":
            return _generate_csv(export_data)
        elif output_format == "jsonl":
            return _generate_jsonl(export_data)
        else:
            raise DataExportError(
                f"Invalid output format: {output_format}",
                context={"valid_formats": ["csv", "jsonl"]},
            )

    except DataExportError:
        raise
    except Exception as e:
        logger.exception("Failed to export response details")
        raise DataExportError(
            "Failed to export response details",
            original_error=e,
            context={"format": output_format, "min_responses": min_responses},
        ) from e


def export_ctt_summary(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    question_ids: Optional[List[int]] = None,
    min_responses: int = MIN_RESPONSES_DEFAULT,
) -> str:
    """
    Export CTT (Classical Test Theory) summary statistics per question.

    Includes: question_id, question_type, difficulty_level, empirical_difficulty,
    discrimination, response_count

    Args:
        db: SQLAlchemy session
        start_date: Filter by date range start (optional)
        end_date: Filter by date range end (optional)
        question_ids: Optional list of question IDs to filter
        min_responses: Minimum response count per question (default: 10)

    Returns:
        CSV string with CTT summary data

    Raises:
        DataExportError: If export fails
    """
    try:
        logger.info("Starting CTT summary export")

        # Count responses per question from completed, fixed-form sessions
        count_query = (
            db.query(
                Response.question_id,
                func.count(Response.id).label("response_count"),
            )
            .join(TestSession, Response.test_session_id == TestSession.id)
            .filter(TestSession.status == TestStatus.COMPLETED)
            .filter(TestSession.is_adaptive == False)  # noqa: E712
        )

        if start_date:
            count_query = count_query.filter(TestSession.completed_at >= start_date)
        if end_date:
            count_query = count_query.filter(TestSession.completed_at <= end_date)

        count_query = count_query.group_by(Response.question_id)
        response_counts = count_query.all()

        # Filter by min_responses
        eligible_question_ids = {
            r.question_id for r in response_counts if r.response_count >= min_responses
        }

        if question_ids:
            eligible_question_ids = eligible_question_ids.intersection(
                set(question_ids)
            )

        logger.debug(f"Found {len(eligible_question_ids)} eligible questions")

        if not eligible_question_ids:
            logger.warning("No questions match the filter criteria")
            return ""

        # Get question details
        questions_query = db.query(
            Question.id,
            Question.question_type,
            Question.difficulty_level,
            Question.empirical_difficulty,
            Question.discrimination,
            Question.response_count,
        ).filter(Question.id.in_(list(eligible_question_ids)))

        questions = questions_query.all()

        # Build count lookup
        count_lookup = {r.question_id: r.response_count for r in response_counts}

        logger.info(f"Exporting CTT summary for {len(questions)} questions")

        # Convert to export format
        export_data: List[CTTSummaryData] = [
            {
                "question_id": q.id,
                "question_type": (
                    q.question_type.value
                    if hasattr(q.question_type, "value")
                    else str(q.question_type)
                ),
                "difficulty_level": (
                    q.difficulty_level.value
                    if hasattr(q.difficulty_level, "value")
                    else str(q.difficulty_level)
                ),
                "empirical_difficulty": q.empirical_difficulty,
                "discrimination": q.discrimination,
                "response_count": count_lookup[q.id],
            }
            for q in questions
        ]

        # Sort by question_id for consistent output
        export_data.sort(key=lambda x: x["question_id"])

        return _generate_csv(export_data)

    except Exception as e:
        logger.exception("Failed to export CTT summary")
        raise DataExportError(
            "Failed to export CTT summary",
            original_error=e,
            context={"min_responses": min_responses},
        ) from e


def _generate_csv(data: Sequence[Mapping[str, Any]]) -> str:
    """Generate CSV string from list of dictionaries."""
    if not data:
        return ""

    output = io.StringIO()
    fieldnames = list(data[0].keys())
    writer = csv.DictWriter(output, fieldnames=fieldnames)

    writer.writeheader()
    writer.writerows(data)  # type: ignore[arg-type]

    return output.getvalue()


def _generate_jsonl(data: Sequence[Mapping[str, Any]]) -> str:
    """Generate JSONL string (one JSON object per line)."""
    if not data:
        return ""

    output = io.StringIO()
    for record in data:
        json.dump(record, output)
        output.write("\n")

    return output.getvalue()


def main():
    """CLI entry point for data export."""
    parser = argparse.ArgumentParser(
        description="Export IRT calibration data from AIQ database"
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date filter (ISO format: YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date filter (ISO format: YYYY-MM-DD)",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output file path",
    )
    parser.add_argument(
        "--question-ids",
        type=str,
        help="Comma-separated list of question IDs to include",
    )
    parser.add_argument(
        "--min-responses",
        type=int,
        default=MIN_RESPONSES_DEFAULT,
        help=f"Minimum responses per question (default: {MIN_RESPONSES_DEFAULT})",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["csv", "jsonl"],
        default="csv",
        help="Output format (default: csv)",
    )
    parser.add_argument(
        "--export-type",
        type=str,
        choices=["responses", "matrix", "details", "ctt-summary"],
        default="responses",
        help="Type of export (default: responses)",
    )

    args = parser.parse_args()

    # Parse dates
    start_date = None
    end_date = None
    if args.start_date:
        start_date = datetime.fromisoformat(args.start_date)
    if args.end_date:
        end_date = datetime.fromisoformat(args.end_date)

    # Parse question IDs
    question_ids = None
    if args.question_ids:
        question_ids = [int(qid.strip()) for qid in args.question_ids.split(",")]

    # Get database session
    from app.models.base import SessionLocal

    db = SessionLocal()

    try:
        # Select export function based on type
        if args.export_type == "responses":
            output = export_responses_for_calibration(
                db=db,
                start_date=start_date,
                end_date=end_date,
                question_ids=question_ids,
                min_responses=args.min_responses,
                output_format=args.format,
            )
        elif args.export_type == "matrix":
            if args.format != "csv":
                raise ValueError("Matrix export only supports CSV format")
            output = export_response_matrix(
                db=db,
                start_date=start_date,
                end_date=end_date,
                question_ids=question_ids,
                min_responses=args.min_responses,
            )
        elif args.export_type == "details":
            output = export_response_details(
                db=db,
                start_date=start_date,
                end_date=end_date,
                question_ids=question_ids,
                min_responses=args.min_responses,
                output_format=args.format,
            )
        elif args.export_type == "ctt-summary":
            if args.format != "csv":
                raise ValueError("CTT summary export only supports CSV format")
            output = export_ctt_summary(
                db=db,
                start_date=start_date,
                end_date=end_date,
                question_ids=question_ids,
                min_responses=args.min_responses,
            )
        else:
            raise ValueError(f"Unknown export type: {args.export_type}")

        # Write to file
        with open(args.output, "w") as f:
            f.write(output)

        print(f"Successfully exported data to {args.output}")
        print(f"Export type: {args.export_type}")
        print(f"Format: {args.format}")
        if start_date:
            print(f"Start date: {start_date}")
        if end_date:
            print(f"End date: {end_date}")
        if question_ids:
            print(f"Question IDs: {len(question_ids)} questions")
        print(f"Minimum responses per question: {args.min_responses}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
