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

    Pass --prod to query via the production backend API instead of a local
    database. Requires ADMIN_TOKEN in environment. BACKEND_URL defaults to
    the Railway production URL if not set.

Requires DATABASE_URL in environment (or backend/.env) for local mode.
"""

import argparse
import json
import os
import re
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import requests

# Ensure backend/ is on sys.path so app.models imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
)

# Database imports are deferred until needed (local mode only).
# This allows --prod mode to work without SQLAlchemy/models installed.
_db_imports_loaded = False


def _load_db_imports():
    global _db_imports_loaded
    if _db_imports_loaded:
        return
    global create_engine, text, sessionmaker, Question, QuestionGenerationRun
    global TestResult, TestSession, User
    from sqlalchemy import create_engine, text  # noqa: E402, F811
    from sqlalchemy.orm import sessionmaker  # noqa: E402, F811

    from app.models.models import (  # noqa: E402, F811
        Question,
        QuestionGenerationRun,
        TestResult,
        TestSession,
        User,
    )

    _db_imports_loaded = True


# ---------------------------------------------------------------------------
# Lightweight engine (pool_size=1) — NOT the pooled engine from base.py
# ---------------------------------------------------------------------------
_engine = None
_Session = None


@contextmanager
def _get_session():
    """Context manager yielding a lightweight DB session (created lazily)."""
    _load_db_imports()
    global _engine, _Session
    if _engine is None:
        db_url = os.getenv("DATABASE_URL", "postgresql://localhost:5432/aiq_dev")
        _engine = create_engine(db_url, pool_size=1, max_overflow=0, echo=False)
        _Session = sessionmaker(bind=_engine)
    db = _Session()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# SQL allowlist for the sql subcommand
# ---------------------------------------------------------------------------
_READ_ONLY_PATTERN = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)

# Tables that must never be queried via the sql subcommand.
_BLOCKED_TABLES = {"password_reset_tokens"}

# Columns that are stripped from query results to prevent accidental exposure.
_BLOCKED_COLUMNS = {"password_hash", "apns_device_token"}

# Pattern to extract table names from FROM and JOIN clauses.
_TABLE_REF_PATTERN = re.compile(r"\b(?:FROM|JOIN)\s+(\w+)", re.IGNORECASE)


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
# Production API helpers
# ---------------------------------------------------------------------------

_DEFAULT_BACKEND_URL = "https://aiq-backend-production.up.railway.app"


def _api_get(path, params=None):
    """GET a JSON list from the admin API."""
    base = os.getenv("BACKEND_URL", _DEFAULT_BACKEND_URL).rstrip("/")
    token = os.getenv("ADMIN_TOKEN")
    if not token:
        print("Error: ADMIN_TOKEN is required for --prod mode.", file=sys.stderr)
        sys.exit(1)
    url = f"{base}/v1/admin{path}"
    if params:
        url += "?" + urlencode({k: v for k, v in params.items() if v is not None})
    resp = requests.get(url, headers={"X-Admin-Token": token}, timeout=30)
    if resp.status_code != 200:
        print(f"Error: API returned {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)
    return resp.json()


def _api_post(path, body):
    """POST JSON to the admin API and return the response."""
    base = os.getenv("BACKEND_URL", _DEFAULT_BACKEND_URL).rstrip("/")
    token = os.getenv("ADMIN_TOKEN")
    if not token:
        print("Error: ADMIN_TOKEN is required for --prod mode.", file=sys.stderr)
        sys.exit(1)
    url = f"{base}/v1/admin{path}"
    resp = requests.post(url, json=body, headers={"X-Admin-Token": token}, timeout=30)
    if resp.status_code != 200:
        print(f"Error: API returned {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)
    return resp.json()


def _prod_list(path, headers, params, args):
    """Fetch a list endpoint and output it."""
    data = _api_get(path, params)
    rows = [tuple(row.get(h, "") for h in headers) for row in data]
    _output(headers, rows, args.json)


# ---------------------------------------------------------------------------
# Production subcommands
# ---------------------------------------------------------------------------


def cmd_users_prod(args):
    _prod_list(
        "/data/users",
        ["id", "email", "first_name", "created_at", "last_login_at"],
        None,
        args,
    )


def cmd_inventory_prod(args):
    params = {
        "type": getattr(args, "type", None),
        "difficulty": getattr(args, "difficulty", None),
    }
    _prod_list(
        "/data/inventory",
        ["question_type", "difficulty_level", "is_active", "count"],
        params,
        args,
    )


def cmd_sessions_prod(args):
    params = {"user": getattr(args, "user", None), "limit": args.limit}
    _prod_list(
        "/data/sessions",
        ["id", "user_id", "status", "started_at", "completed_at", "is_adaptive"],
        params,
        args,
    )


def cmd_scores_prod(args):
    params = {"user": getattr(args, "user", None), "limit": args.limit}
    _prod_list(
        "/data/scores",
        [
            "id",
            "user_id",
            "iq_score",
            "percentile_rank",
            "total_questions",
            "correct_answers",
            "completed_at",
            "validity_status",
        ],
        params,
        args,
    )


def cmd_generation_prod(args):
    params = {"limit": args.limit}
    _prod_list(
        "/data/generation",
        [
            "id",
            "started_at",
            "status",
            "questions_requested",
            "questions_generated",
            "questions_approved",
            "questions_inserted",
            "avg_judge_score",
            "duration_seconds",
        ],
        params,
        args,
    )


def cmd_activity_prod(args):
    params = {"days": args.days}
    _prod_list(
        "/data/activity",
        ["day", "sessions", "unique_users"],
        params,
        args,
    )


def cmd_sql_prod(args):
    data = _api_post("/data/sql", {"query": args.query})
    headers = data.get("columns", [])
    rows = [tuple(r) for r in data.get("rows", [])]
    _output(headers, rows, args.json)


# ---------------------------------------------------------------------------
# Local subcommands
# ---------------------------------------------------------------------------


def cmd_users(args):
    """List users with basic stats."""
    with _get_session() as db:
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


def cmd_inventory(args):
    """Show question inventory breakdown."""
    from sqlalchemy import func  # noqa: E402

    with _get_session() as db:
        query = db.query(
            Question.question_type,
            Question.difficulty_level,
            Question.is_active,
            func.count().label("count"),
        ).group_by(
            Question.question_type,
            Question.difficulty_level,
            Question.is_active,
        )
        if args.type:
            query = query.filter(Question.question_type == args.type)
        if args.difficulty:
            query = query.filter(Question.difficulty_level == args.difficulty)

        results = query.order_by(
            Question.question_type, Question.difficulty_level
        ).all()
        headers = ["question_type", "difficulty_level", "is_active", "count"]
        rows = [
            (r.question_type, str(r.difficulty_level), str(r.is_active), r.count)
            for r in results
        ]
        _output(headers, rows, args.json)


def cmd_sessions(args):
    """List test sessions."""
    with _get_session() as db:
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


def cmd_scores(args):
    """List test results / scores."""
    with _get_session() as db:
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


def cmd_generation(args):
    """Show question generation run history."""
    with _get_session() as db:
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


def cmd_activity(args):
    """Show recent user activity (test sessions started per day)."""
    with _get_session() as db:
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


def cmd_sql(args):
    """Run an arbitrary read-only SQL query."""
    query = args.query
    if not _READ_ONLY_PATTERN.match(query):
        print(
            "Error: only SELECT and WITH statements are allowed.",
            file=sys.stderr,
        )
        sys.exit(1)

    referenced_tables = {t.lower() for t in _TABLE_REF_PATTERN.findall(query)}
    blocked_hits = referenced_tables & _BLOCKED_TABLES
    if blocked_hits:
        print(
            f"Error: access to table(s) {', '.join(sorted(blocked_hits))} "
            "is not allowed.",
            file=sys.stderr,
        )
        sys.exit(1)

    with _get_session() as db:
        result = db.execute(text(query))
        if result.returns_rows:
            headers = list(result.keys())
            rows = [list(r) for r in result.fetchall()]

            blocked_indices = [
                i for i, c in enumerate(headers) if c.lower() in _BLOCKED_COLUMNS
            ]
            if blocked_indices:
                headers = [c for i, c in enumerate(headers) if i not in blocked_indices]
                rows = [
                    [v for i, v in enumerate(row) if i not in blocked_indices]
                    for row in rows
                ]
                rows = [tuple(r) for r in rows]
            else:
                rows = [tuple(r) for r in rows]

            _output(headers, rows, args.json)
        else:
            print("Query executed (no rows returned).")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        prog="aiq-data",
        description="Ad-hoc read-only query CLI for the AIQ database.",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--prod",
        action="store_true",
        help="Query via the production backend API (requires ADMIN_TOKEN env var)",
    )
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
    if args.prod:
        dispatch = {
            "users": cmd_users_prod,
            "inventory": cmd_inventory_prod,
            "sessions": cmd_sessions_prod,
            "scores": cmd_scores_prod,
            "generation": cmd_generation_prod,
            "activity": cmd_activity_prod,
            "sql": cmd_sql_prod,
        }
    else:
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
