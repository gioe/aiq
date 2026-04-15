#!/usr/bin/env python3
"""aiq-data: Ad-hoc read-only query CLI for the AIQ database.

Usage:
    python cli/aiq_data.py users [--json]
    python cli/aiq_data.py inventory [--json] [--type TYPE] [--difficulty DIFF]
    python cli/aiq_data.py sessions [--json] [--user EMAIL] [--limit N]
    python cli/aiq_data.py scores [--json] [--user EMAIL] [--limit N]
    python cli/aiq_data.py generation [--json] [--limit N]
    python cli/aiq_data.py activity [--json] [--days N]
    python cli/aiq_data.py sql "SELECT ..." [--json]

Requires DATABASE_URL in environment (or backend/.env).
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

# Ensure backend/ is on sys.path so app.models imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
)

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.models.models import (  # noqa: E402
    Question,
    QuestionGenerationRun,
    TestResult,
    TestSession,
    User,
)

# ---------------------------------------------------------------------------
# Lightweight engine (pool_size=1) — NOT the pooled engine from base.py
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/aiq_dev")
engine = create_engine(DATABASE_URL, pool_size=1, max_overflow=0, echo=False)
Session = sessionmaker(bind=engine)

# ---------------------------------------------------------------------------
# Write-statement blocklist for the sql subcommand
# ---------------------------------------------------------------------------
_WRITE_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE)\b", re.IGNORECASE
)


def _serialize(obj):
    """JSON serializer for types json.dumps doesn't handle natively."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "__dict__"):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _print_table(headers, rows):
    """Print a simple aligned ASCII table."""
    if not rows:
        print("(no rows)")
        return
    col_widths = [len(h) for h in headers]
    str_rows = []
    for row in rows:
        str_row = [str(v) if v is not None else "" for v in row]
        str_rows.append(str_row)
        for i, v in enumerate(str_row):
            col_widths[i] = max(col_widths[i], len(v))
    fmt = "  ".join(f"{{:<{w}}}" for w in col_widths)
    print(fmt.format(*headers))
    print("  ".join("-" * w for w in col_widths))
    for r in str_rows:
        print(fmt.format(*r))
    print(f"\n({len(str_rows)} rows)")


def _output(headers, rows, as_json):
    """Output rows as JSON array or ASCII table."""
    if as_json:
        data = [dict(zip(headers, row)) for row in rows]
        print(json.dumps(data, indent=2, default=_serialize))
    else:
        _print_table(headers, rows)


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_users(args):
    """List users with basic stats."""
    db = Session()
    try:
        users = (
            db.query(
                User.id,
                User.email,
                User.first_name,
                User.created_at,
                User.last_login_at,
            )
            .order_by(User.created_at.desc())
            .all()
        )
        headers = ["id", "email", "first_name", "created_at", "last_login_at"]
        rows = [tuple(u) for u in users]
        _output(headers, rows, args.json)
    finally:
        db.close()


def cmd_inventory(args):
    """Show question inventory breakdown."""
    db = Session()
    try:
        query = db.query(
            Question.question_type,
            Question.difficulty_level,
            Question.is_active,
        )
        if args.type:
            query = query.filter(Question.question_type == args.type)
        if args.difficulty:
            query = query.filter(Question.difficulty_level == args.difficulty)

        questions = query.all()
        # Aggregate counts
        counts = {}
        for q in questions:
            key = (q.question_type, str(q.difficulty_level), str(q.is_active))
            counts[key] = counts.get(key, 0) + 1

        headers = ["question_type", "difficulty_level", "is_active", "count"]
        rows = sorted(
            [(k[0], k[1], k[2], v) for k, v in counts.items()],
            key=lambda r: (r[0], r[1]),
        )
        _output(headers, rows, args.json)
    finally:
        db.close()


def cmd_sessions(args):
    """List test sessions."""
    db = Session()
    try:
        query = db.query(
            TestSession.id,
            TestSession.user_id,
            TestSession.status,
            TestSession.started_at,
            TestSession.completed_at,
            TestSession.is_adaptive,
        )
        if args.user:
            user = db.query(User.id).filter(User.email == args.user).first()
            if not user:
                print(f"User not found: {args.user}", file=sys.stderr)
                sys.exit(1)
            query = query.filter(TestSession.user_id == user.id)
        sessions = query.order_by(TestSession.started_at.desc()).limit(args.limit).all()
        headers = [
            "id",
            "user_id",
            "status",
            "started_at",
            "completed_at",
            "is_adaptive",
        ]
        rows = [tuple(s) for s in sessions]
        _output(headers, rows, args.json)
    finally:
        db.close()


def cmd_scores(args):
    """List test results / scores."""
    db = Session()
    try:
        query = db.query(
            TestResult.id,
            TestResult.user_id,
            TestResult.iq_score,
            TestResult.percentile_rank,
            TestResult.total_questions,
            TestResult.correct_answers,
            TestResult.completed_at,
            TestResult.validity_status,
        )
        if args.user:
            user = db.query(User.id).filter(User.email == args.user).first()
            if not user:
                print(f"User not found: {args.user}", file=sys.stderr)
                sys.exit(1)
            query = query.filter(TestResult.user_id == user.id)
        results = query.order_by(TestResult.completed_at.desc()).limit(args.limit).all()
        headers = [
            "id",
            "user_id",
            "iq_score",
            "percentile_rank",
            "total_questions",
            "correct_answers",
            "completed_at",
            "validity_status",
        ]
        rows = [tuple(r) for r in results]
        _output(headers, rows, args.json)
    finally:
        db.close()


def cmd_generation(args):
    """Show question generation run history."""
    db = Session()
    try:
        runs = (
            db.query(
                QuestionGenerationRun.id,
                QuestionGenerationRun.started_at,
                QuestionGenerationRun.status,
                QuestionGenerationRun.questions_requested,
                QuestionGenerationRun.questions_generated,
                QuestionGenerationRun.questions_approved,
                QuestionGenerationRun.questions_inserted,
                QuestionGenerationRun.avg_judge_score,
                QuestionGenerationRun.duration_seconds,
            )
            .order_by(QuestionGenerationRun.started_at.desc())
            .limit(args.limit)
            .all()
        )
        headers = [
            "id",
            "started_at",
            "status",
            "questions_requested",
            "questions_generated",
            "questions_approved",
            "questions_inserted",
            "avg_judge_score",
            "duration_seconds",
        ]
        rows = [tuple(r) for r in runs]
        _output(headers, rows, args.json)
    finally:
        db.close()


def cmd_activity(args):
    """Show recent user activity (test sessions started per day)."""
    db = Session()
    try:
        since = datetime.now(timezone.utc) - timedelta(days=args.days)
        result = db.execute(
            text(
                "SELECT DATE(started_at) as day, COUNT(*) as sessions, "
                "COUNT(DISTINCT user_id) as unique_users "
                "FROM test_sessions "
                "WHERE started_at >= :since "
                "GROUP BY DATE(started_at) "
                "ORDER BY day DESC"
            ),
            {"since": since},
        )
        rows_raw = result.fetchall()
        headers = ["day", "sessions", "unique_users"]
        rows = [(str(r[0]), r[1], r[2]) for r in rows_raw]
        _output(headers, rows, args.json)
    finally:
        db.close()


def cmd_sql(args):
    """Run an arbitrary read-only SQL query."""
    query = args.query
    if _WRITE_PATTERN.search(query):
        print(
            "Error: write statements (INSERT, UPDATE, DELETE, DROP, ALTER, "
            "TRUNCATE, CREATE) are not allowed.",
            file=sys.stderr,
        )
        sys.exit(1)

    db = Session()
    try:
        result = db.execute(text(query))
        if result.returns_rows:
            headers = list(result.keys())
            rows = [tuple(r) for r in result.fetchall()]
            _output(headers, rows, args.json)
        else:
            print("Query executed (no rows returned).")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        prog="aiq-data",
        description="Ad-hoc read-only query CLI for the AIQ database.",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    # users
    sub.add_parser("users", help="List all users")

    # inventory
    inv = sub.add_parser("inventory", help="Question inventory breakdown")
    inv.add_argument("--type", help="Filter by question_type")
    inv.add_argument("--difficulty", help="Filter by difficulty_level")

    # sessions
    sess = sub.add_parser("sessions", help="List test sessions")
    sess.add_argument("--user", help="Filter by user email")
    sess.add_argument("--limit", type=int, default=50, help="Max rows (default 50)")

    # scores
    sc = sub.add_parser("scores", help="List test scores")
    sc.add_argument("--user", help="Filter by user email")
    sc.add_argument("--limit", type=int, default=50, help="Max rows (default 50)")

    # generation
    gen = sub.add_parser("generation", help="Question generation run history")
    gen.add_argument("--limit", type=int, default=20, help="Max rows (default 20)")

    # activity
    act = sub.add_parser("activity", help="Recent user activity (sessions per day)")
    act.add_argument("--days", type=int, default=30, help="Lookback days (default 30)")

    # sql
    sq = sub.add_parser("sql", help="Run arbitrary read-only SQL")
    sq.add_argument("query", help="SQL SELECT statement")

    args = parser.parse_args()
    dispatch = {
        "users": cmd_users,
        "inventory": cmd_inventory,
        "sessions": cmd_sessions,
        "scores": cmd_scores,
        "generation": cmd_generation,
        "activity": cmd_activity,
        "sql": cmd_sql,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
