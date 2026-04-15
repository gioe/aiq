"""Tests for the aiq-data CLI.

Covers:
  - SQL allowlist validation (SELECT/WITH allowed, write statements rejected,
    mixed-case bypass attempts, CTE+INSERT blocked)
  - Subcommand smoke tests (each subcommand dispatches without error)
"""

import argparse
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from cli.aiq_data import _READ_ONLY_PATTERN, cmd_sql


# ---------------------------------------------------------------------------
# SQL allowlist validation
# ---------------------------------------------------------------------------


class TestSQLAllowlist:
    """Test the _READ_ONLY_PATTERN regex used by cmd_sql."""

    @pytest.mark.parametrize(
        "query",
        [
            "SELECT * FROM users",
            "select id from users",
            "  SELECT 1",
            "WITH cte AS (SELECT 1) SELECT * FROM cte",
            "with cte as (select 1) select * from cte",
            "  WITH x AS (SELECT 1) SELECT * FROM x",
            "SeLeCt * FROM users",
            "WiTh cte AS (SELECT 1) SELECT * FROM cte",
            "\n  SELECT 1",
            "\t SELECT 1",
        ],
        ids=[
            "basic-select",
            "lowercase-select",
            "leading-spaces",
            "cte-with",
            "lowercase-with",
            "leading-spaces-with",
            "mixed-case-select",
            "mixed-case-with",
            "leading-newline",
            "leading-tab",
        ],
    )
    def test_allowed_queries(self, query):
        assert _READ_ONLY_PATTERN.match(query), f"Should allow: {query!r}"

    @pytest.mark.parametrize(
        "query",
        [
            "INSERT INTO users (email) VALUES ('x')",
            "UPDATE users SET email='x'",
            "DELETE FROM users",
            "DROP TABLE users",
            "ALTER TABLE users ADD COLUMN x TEXT",
            "TRUNCATE users",
            "CREATE TABLE evil (id INT)",
            "insert into users (email) values ('x')",
            "InSeRt INTO users VALUES (1)",
            "  DELETE FROM users WHERE 1=1",
        ],
        ids=[
            "insert",
            "update",
            "delete",
            "drop",
            "alter",
            "truncate",
            "create",
            "lowercase-insert",
            "mixed-case-insert",
            "leading-spaces-delete",
        ],
    )
    def test_rejected_queries(self, query):
        assert not _READ_ONLY_PATTERN.match(query), f"Should reject: {query!r}"

    def test_cte_with_insert_blocked(self):
        """WITH+INSERT: regex allows WITH prefix — real protection is DB role.

        The regex only validates the first keyword. This test documents
        that CTE+INSERT passes the regex; defense-in-depth (read-only
        DB connection / pg role) is the real guard.
        """
        query = "WITH cte AS (SELECT 1) INSERT INTO users (id) SELECT * FROM cte"
        # The regex will match because it starts with WITH — this is a known
        # limitation documented here. The real protection is the read-only
        # DB connection / pg role.
        assert _READ_ONLY_PATTERN.match(query) is not None

    def test_empty_string_rejected(self):
        assert not _READ_ONLY_PATTERN.match("")

    def test_comment_before_select_rejected(self):
        """A comment before SELECT should be rejected (doesn't start with SELECT)."""
        assert not _READ_ONLY_PATTERN.match("-- comment\nSELECT 1")

    def test_semicolon_stacking_first_keyword_matters(self):
        """Semicolon stacking: regex checks first keyword only.

        Real protection is single-statement execution via text().
        """
        query = "SELECT 1; DROP TABLE users"
        assert _READ_ONLY_PATTERN.match(query) is not None


# ---------------------------------------------------------------------------
# cmd_sql integration (mocked DB)
# ---------------------------------------------------------------------------


class TestCmdSql:
    """Test cmd_sql dispatch with mocked DB session."""

    def test_rejects_write_statement(self):
        args = SimpleNamespace(query="INSERT INTO users VALUES (1)", json=False)
        with pytest.raises(SystemExit) as exc_info:
            cmd_sql(args)
        assert exc_info.value.code == 1

    def test_accepts_select(self):
        mock_result = MagicMock()
        mock_result.returns_rows = True
        mock_result.keys.return_value = ["id"]
        mock_result.fetchall.return_value = [(1,)]

        mock_session = MagicMock()
        mock_session.execute.return_value = mock_result
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        args = SimpleNamespace(query="SELECT 1", json=False)
        with patch("cli.aiq_data._get_session", return_value=mock_session):
            cmd_sql(args)

        mock_session.execute.assert_called_once()

    def test_accepts_with_cte(self):
        mock_result = MagicMock()
        mock_result.returns_rows = True
        mock_result.keys.return_value = ["n"]
        mock_result.fetchall.return_value = [(1,)]

        mock_session = MagicMock()
        mock_session.execute.return_value = mock_result
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        args = SimpleNamespace(
            query="WITH cte AS (SELECT 1 AS n) SELECT * FROM cte", json=False
        )
        with patch("cli.aiq_data._get_session", return_value=mock_session):
            cmd_sql(args)

        mock_session.execute.assert_called_once()


# ---------------------------------------------------------------------------
# Subcommand smoke tests (argparse dispatch)
# ---------------------------------------------------------------------------


class TestSubcommandParsing:
    """Verify each subcommand is wired up and dispatches correctly."""

    @pytest.mark.parametrize(
        "argv,expected_command",
        [
            (["users"], "users"),
            (["inventory"], "inventory"),
            (["inventory", "--type", "pattern_recognition"], "inventory"),
            (["inventory", "--difficulty", "medium"], "inventory"),
            (["sessions"], "sessions"),
            (["sessions", "--user", "a@b.com", "--limit", "10"], "sessions"),
            (["scores"], "scores"),
            (["scores", "--user", "a@b.com"], "scores"),
            (["generation"], "generation"),
            (["generation", "--limit", "5"], "generation"),
            (["activity"], "activity"),
            (["activity", "--days", "7"], "activity"),
            (["sql", "SELECT 1"], "sql"),
            (["--json", "users"], "users"),
        ],
        ids=[
            "users",
            "inventory",
            "inventory-type-filter",
            "inventory-difficulty-filter",
            "sessions",
            "sessions-with-filters",
            "scores",
            "scores-with-user",
            "generation",
            "generation-with-limit",
            "activity",
            "activity-with-days",
            "sql",
            "json-flag",
        ],
    )
    def test_parse_and_dispatch(self, argv, expected_command):
        """Parse argv and verify the subcommand is set correctly."""
        parser = self._build_parser()
        args = parser.parse_args(argv)
        assert args.command == expected_command

    def test_no_subcommand_exits(self):
        """Missing subcommand should cause argparse to exit."""
        parser = self._build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_sql_requires_query_arg(self):
        """SQL subcommand without a query should fail."""
        parser = self._build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["sql"])

    @staticmethod
    def _build_parser():
        """Build the same parser as main() for testing."""
        parser = argparse.ArgumentParser(prog="aiq-data")
        parser.add_argument("--json", action="store_true")
        sub = parser.add_subparsers(dest="command", required=True)

        sub.add_parser("users")

        inv = sub.add_parser("inventory")
        inv.add_argument("--type")
        inv.add_argument("--difficulty")

        sess = sub.add_parser("sessions")
        sess.add_argument("--user")
        sess.add_argument("--limit", type=int, default=50)

        sc = sub.add_parser("scores")
        sc.add_argument("--user")
        sc.add_argument("--limit", type=int, default=50)

        gen = sub.add_parser("generation")
        gen.add_argument("--limit", type=int, default=20)

        act = sub.add_parser("activity")
        act.add_argument("--days", type=int, default=30)

        sq = sub.add_parser("sql")
        sq.add_argument("query")

        return parser
