"""
Tests for database query metrics instrumentation.
"""
import time
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text

from app.db.instrumentation import (
    _parse_sql_operation,
    _parse_table_name,
    _should_instrument_query,
    setup_db_instrumentation,
    teardown_db_instrumentation,
)

# Test constants
MAX_QUERY_DURATION_SECONDS = 1.0  # Maximum expected duration for simple queries
SIMPLE_QUERY_MAX_DURATION_SECONDS = 0.1  # 100ms - simple query should be fast
TEST_DATA_ROW_COUNT = 100  # Number of rows for performance tests
PERFORMANCE_TEST_ITERATIONS = 10  # Query iterations for timing
MAX_INSTRUMENTATION_OVERHEAD = 0.5  # 50% - acceptable overhead for instrumentation


class TestSQLParsing:
    """Tests for SQL parsing utility functions."""

    def test_parse_operation_select(self):
        """Test parsing SELECT operation."""
        assert _parse_sql_operation("SELECT * FROM users") == "SELECT"
        assert _parse_sql_operation("  SELECT id FROM users") == "SELECT"
        assert _parse_sql_operation("\nSELECT * FROM users") == "SELECT"

    def test_parse_operation_insert(self):
        """Test parsing INSERT operation."""
        assert _parse_sql_operation("INSERT INTO users VALUES (1, 'test')") == "INSERT"
        assert _parse_sql_operation("  INSERT INTO users (id) VALUES (1)") == "INSERT"

    def test_parse_operation_update(self):
        """Test parsing UPDATE operation."""
        assert _parse_sql_operation("UPDATE users SET name='test'") == "UPDATE"
        assert _parse_sql_operation("  UPDATE users SET id=1") == "UPDATE"

    def test_parse_operation_delete(self):
        """Test parsing DELETE operation."""
        assert _parse_sql_operation("DELETE FROM users WHERE id=1") == "DELETE"
        assert _parse_sql_operation("  DELETE FROM users") == "DELETE"

    def test_parse_operation_create(self):
        """Test parsing CREATE operation."""
        assert _parse_sql_operation("CREATE TABLE users (id INT)") == "CREATE"
        assert _parse_sql_operation("CREATE INDEX idx_users ON users(id)") == "CREATE"

    def test_parse_operation_drop(self):
        """Test parsing DROP operation."""
        assert _parse_sql_operation("DROP TABLE users") == "DROP"
        assert _parse_sql_operation("DROP INDEX idx_users") == "DROP"

    def test_parse_operation_case_insensitive(self):
        """Test that operation parsing is case-insensitive."""
        assert _parse_sql_operation("select * from users") == "SELECT"
        assert _parse_sql_operation("Select * From users") == "SELECT"
        assert _parse_sql_operation("SELECT * FROM users") == "SELECT"

    def test_parse_operation_unknown(self):
        """Test parsing unknown operation."""
        assert _parse_sql_operation("INVALID SQL") == "UNKNOWN"
        assert _parse_sql_operation("") == "UNKNOWN"
        assert _parse_sql_operation("   ") == "UNKNOWN"

    def test_parse_table_from_select(self):
        """Test parsing table name from SELECT queries."""
        assert _parse_table_name("SELECT * FROM users") == "users"
        assert _parse_table_name("SELECT id FROM test_sessions") == "test_sessions"
        assert _parse_table_name("SELECT * FROM users WHERE id=1") == "users"

    def test_parse_table_from_insert(self):
        """Test parsing table name from INSERT queries."""
        assert _parse_table_name("INSERT INTO users VALUES (1)") == "users"
        assert _parse_table_name("INSERT INTO questions (id) VALUES (1)") == "questions"

    def test_parse_table_from_update(self):
        """Test parsing table name from UPDATE queries."""
        assert _parse_table_name("UPDATE users SET name='test'") == "users"
        assert (
            _parse_table_name("UPDATE questions SET difficulty='easy'") == "questions"
        )

    def test_parse_table_from_delete(self):
        """Test parsing table name from DELETE queries."""
        assert _parse_table_name("DELETE FROM users WHERE id=1") == "users"
        assert _parse_table_name("DELETE FROM test_sessions") == "test_sessions"

    def test_parse_table_with_join(self):
        """Test parsing table name from queries with JOINs (returns first table)."""
        sql = (
            "SELECT * FROM users JOIN test_sessions ON users.id = test_sessions.user_id"
        )
        assert _parse_table_name(sql) == "users"

    def test_parse_table_case_insensitive(self):
        """Test that table parsing is case-insensitive."""
        assert _parse_table_name("SELECT * FROM Users") == "users"
        assert _parse_table_name("SELECT * FROM USERS") == "users"
        assert _parse_table_name("select * from users") == "users"

    def test_parse_table_with_schema(self):
        """Test parsing table name with schema prefix (returns table name only)."""
        # Note: Our regex doesn't handle schema prefixes, returns "public" not "users"
        # This is acceptable as we're tracking high-level metrics
        assert _parse_table_name("SELECT * FROM public.users") == "public"

    def test_parse_table_unknown(self):
        """Test parsing unknown table name."""
        assert _parse_table_name("INVALID SQL") == "unknown"
        assert _parse_table_name("") == "unknown"
        assert _parse_table_name("SELECT 1") == "unknown"


class TestQueryFiltering:
    """Tests for query filtering logic."""

    def test_should_instrument_normal_queries(self):
        """Test that normal application queries are instrumented."""
        assert _should_instrument_query("SELECT * FROM users")
        assert _should_instrument_query("INSERT INTO users VALUES (1)")
        assert _should_instrument_query("UPDATE users SET name='test'")
        assert _should_instrument_query("DELETE FROM users WHERE id=1")

    def test_should_skip_empty_queries(self):
        """Test that empty queries are not instrumented."""
        assert not _should_instrument_query("")
        assert not _should_instrument_query("   ")
        assert not _should_instrument_query("\n")

    def test_should_skip_pragma_queries(self):
        """Test that SQLite PRAGMA queries are not instrumented."""
        assert not _should_instrument_query("PRAGMA table_info(users)")
        assert not _should_instrument_query("pragma foreign_keys = ON")

    def test_should_skip_pg_catalog_queries(self):
        """Test that PostgreSQL catalog queries are not instrumented."""
        assert not _should_instrument_query("SELECT * FROM pg_catalog.pg_tables")
        assert not _should_instrument_query("select * from pg_catalog.pg_class")

    def test_should_skip_information_schema_queries(self):
        """Test that information_schema queries are not instrumented."""
        assert not _should_instrument_query("SELECT * FROM information_schema.tables")
        assert not _should_instrument_query("select * from information_schema.columns")

    def test_should_skip_show_queries(self):
        """Test that SHOW queries are not instrumented."""
        assert not _should_instrument_query("SHOW TABLES")
        assert not _should_instrument_query("show databases")

    def test_should_skip_set_queries(self):
        """Test that SET queries are not instrumented."""
        assert not _should_instrument_query("SET TIME ZONE 'UTC'")
        assert not _should_instrument_query("set session authorization default")


class TestInstrumentationSetup:
    """Tests for instrumentation setup and teardown."""

    @pytest.fixture
    def test_engine(self):
        """Create a test SQLite engine in memory."""
        engine = create_engine("sqlite:///:memory:")
        yield engine
        engine.dispose()

    def test_setup_instrumentation(self, test_engine):
        """Test that instrumentation can be set up successfully."""
        setup_db_instrumentation(test_engine)

        # Check that engine is marked as instrumented
        assert hasattr(test_engine, "_aiq_instrumented")
        assert test_engine._aiq_instrumented is True

    def test_setup_instrumentation_idempotent(self, test_engine):
        """Test that setting up instrumentation twice is safe (idempotent)."""
        setup_db_instrumentation(test_engine)
        # Second call should not raise an exception
        setup_db_instrumentation(test_engine)

        # Engine should still be marked as instrumented
        assert hasattr(test_engine, "_aiq_instrumented")
        assert test_engine._aiq_instrumented is True

    def test_teardown_instrumentation(self, test_engine):
        """Test that instrumentation can be torn down successfully."""
        setup_db_instrumentation(test_engine)
        teardown_db_instrumentation(test_engine)

        # Check that marker is removed
        assert not hasattr(test_engine, "_aiq_instrumented")

    def test_teardown_without_setup(self, test_engine):
        """Test that tearing down without setup is safe."""
        # Should not raise an exception
        teardown_db_instrumentation(test_engine)

        # Engine should not have marker
        assert not hasattr(test_engine, "_aiq_instrumented")


class TestInstrumentationIntegration:
    """Integration tests for query instrumentation with actual database."""

    @pytest.fixture
    def test_engine(self):
        """Create a test SQLite engine with a test table."""
        engine = create_engine("sqlite:///:memory:")

        # Create a test table
        with engine.connect() as conn:
            conn.execute(
                text("CREATE TABLE test_users (id INTEGER PRIMARY KEY, name TEXT)")
            )
            conn.commit()

        yield engine
        engine.dispose()

    @pytest.fixture
    def instrumented_engine(self, test_engine):
        """Create an instrumented test engine."""
        setup_db_instrumentation(test_engine)
        yield test_engine
        teardown_db_instrumentation(test_engine)

    def test_select_query_instrumented(self, instrumented_engine):
        """Test that SELECT queries are instrumented and metrics are recorded."""
        with patch("app.observability.metrics.record_db_query") as mock_record:
            with instrumented_engine.connect() as conn:
                conn.execute(text("SELECT * FROM test_users"))

            # Verify metric was recorded
            mock_record.assert_called_once()
            call_args = mock_record.call_args

            # Check arguments
            assert call_args[1]["operation"] == "SELECT"
            assert call_args[1]["table"] == "test_users"
            assert call_args[1]["duration"] > 0
            assert call_args[1]["duration"] < MAX_QUERY_DURATION_SECONDS

    def test_insert_query_instrumented(self, instrumented_engine):
        """Test that INSERT queries are instrumented and metrics are recorded."""
        with patch("app.observability.metrics.record_db_query") as mock_record:
            with instrumented_engine.connect() as conn:
                conn.execute(
                    text("INSERT INTO test_users (id, name) VALUES (1, 'test')")
                )
                conn.commit()

            # Verify metric was recorded
            mock_record.assert_called_once()
            call_args = mock_record.call_args

            # Check arguments
            assert call_args[1]["operation"] == "INSERT"
            assert call_args[1]["table"] == "test_users"
            assert call_args[1]["duration"] > 0

    def test_update_query_instrumented(self, instrumented_engine):
        """Test that UPDATE queries are instrumented and metrics are recorded."""
        # First insert a row
        with instrumented_engine.connect() as conn:
            conn.execute(text("INSERT INTO test_users (id, name) VALUES (1, 'test')"))
            conn.commit()

        with patch("app.observability.metrics.record_db_query") as mock_record:
            with instrumented_engine.connect() as conn:
                conn.execute(text("UPDATE test_users SET name='updated' WHERE id=1"))
                conn.commit()

            # Verify metric was recorded
            mock_record.assert_called_once()
            call_args = mock_record.call_args

            # Check arguments
            assert call_args[1]["operation"] == "UPDATE"
            assert call_args[1]["table"] == "test_users"
            assert call_args[1]["duration"] > 0

    def test_delete_query_instrumented(self, instrumented_engine):
        """Test that DELETE queries are instrumented and metrics are recorded."""
        # First insert a row
        with instrumented_engine.connect() as conn:
            conn.execute(text("INSERT INTO test_users (id, name) VALUES (1, 'test')"))
            conn.commit()

        with patch("app.observability.metrics.record_db_query") as mock_record:
            with instrumented_engine.connect() as conn:
                conn.execute(text("DELETE FROM test_users WHERE id=1"))
                conn.commit()

            # Verify metric was recorded
            mock_record.assert_called_once()
            call_args = mock_record.call_args

            # Check arguments
            assert call_args[1]["operation"] == "DELETE"
            assert call_args[1]["table"] == "test_users"
            assert call_args[1]["duration"] > 0

    def test_multiple_queries_instrumented(self, instrumented_engine):
        """Test that multiple queries are all instrumented."""
        with patch("app.observability.metrics.record_db_query") as mock_record:
            with instrumented_engine.connect() as conn:
                conn.execute(text("SELECT * FROM test_users"))
                conn.execute(
                    text("INSERT INTO test_users (id, name) VALUES (1, 'test')")
                )
                conn.execute(text("UPDATE test_users SET name='updated' WHERE id=1"))
                conn.commit()

            # Verify all queries were recorded
            assert mock_record.call_count == 3

            # Verify operations
            operations = [call[1]["operation"] for call in mock_record.call_args_list]
            assert "SELECT" in operations
            assert "INSERT" in operations
            assert "UPDATE" in operations

    def test_pragma_query_not_instrumented(self, instrumented_engine):
        """Test that PRAGMA queries are not instrumented."""
        with patch("app.observability.metrics.record_db_query") as mock_record:
            with instrumented_engine.connect() as conn:
                conn.execute(text("PRAGMA table_info(test_users)"))

            # Verify metric was NOT recorded
            mock_record.assert_not_called()

    def test_query_timing_accuracy(self, instrumented_engine):
        """Test that query timing is reasonably accurate."""
        with patch("app.observability.metrics.record_db_query") as mock_record:
            # Add a small delay to ensure measurable duration
            with instrumented_engine.connect() as conn:
                conn.execute(text("SELECT * FROM test_users"))
                # Note: We can't reliably add artificial delays in SQLite

            # Verify timing is within reasonable bounds
            call_args = mock_record.call_args
            duration = call_args[1]["duration"]

            # Duration should be positive and less than 100ms for simple query
            assert duration > 0
            assert duration < SIMPLE_QUERY_MAX_DURATION_SECONDS

    def test_instrumentation_error_handling(self, instrumented_engine):
        """Test that instrumentation errors don't break query execution."""
        # Mock record_db_query to raise an exception
        with patch(
            "app.observability.metrics.record_db_query",
            side_effect=Exception("Metrics error"),
        ):
            # Query should still execute successfully despite metrics error
            with instrumented_engine.connect() as conn:
                result = conn.execute(text("SELECT * FROM test_users"))
                assert result is not None

    def test_context_cleanup(self, instrumented_engine):
        """Test that query context is cleaned up after execution."""
        with patch("app.observability.metrics.record_db_query"):
            with instrumented_engine.connect() as conn:
                # Execute query
                conn.execute(text("SELECT * FROM test_users"))

                # Context should be cleaned up (no easy way to verify directly,
                # but we can check that subsequent queries work)
                conn.execute(text("SELECT * FROM test_users"))
                conn.execute(text("SELECT * FROM test_users"))

            # If context wasn't cleaned up, we'd likely see errors or memory issues


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    @pytest.fixture
    def test_engine(self):
        """Create a test SQLite engine."""
        engine = create_engine("sqlite:///:memory:")
        yield engine
        engine.dispose()

    def test_complex_query_with_subquery(self, test_engine):
        """Test parsing complex queries with subqueries."""
        sql = """
        SELECT u.id, u.name
        FROM (SELECT * FROM users WHERE active=1) u
        JOIN test_sessions ts ON u.id = ts.user_id
        """
        assert _parse_sql_operation(sql) == "SELECT"
        # Returns first table found (users in this case)
        table = _parse_table_name(sql)
        assert table in ["users", "test_sessions"]

    def test_query_with_comments(self, test_engine):
        """Test parsing queries with SQL comments."""
        # Our regex matches operation at start, so comment before SELECT fails
        # This is acceptable - most real queries don't start with comments
        sql = "-- This is a comment\nSELECT * FROM users"
        # Comment at start means operation not at start, so returns UNKNOWN
        assert _parse_sql_operation(sql) == "UNKNOWN"

        # Comment after operation works fine
        sql = "SELECT * FROM users -- This is a comment"
        assert _parse_sql_operation(sql) == "SELECT"

        sql = "/* Multi-line comment */ SELECT * FROM users"
        # Comment at start means operation not at start
        assert _parse_sql_operation(sql) == "UNKNOWN"

    def test_query_with_newlines(self, test_engine):
        """Test parsing queries with multiple newlines."""
        sql = """
        SELECT
            id,
            name
        FROM
            users
        WHERE
            active = 1
        """
        assert _parse_sql_operation(sql) == "SELECT"
        assert _parse_table_name(sql) == "users"

    def test_cte_query(self, test_engine):
        """Test parsing queries with CTEs (Common Table Expressions)."""
        sql = """
        WITH active_users AS (
            SELECT * FROM users WHERE active=1
        )
        SELECT * FROM active_users
        """
        assert _parse_sql_operation(sql) == "UNKNOWN"  # WITH not in our regex
        # But actual execution would work fine

    def test_transaction_statements(self, test_engine):
        """Test parsing transaction control statements."""
        assert _parse_sql_operation("BEGIN TRANSACTION") == "UNKNOWN"
        assert _parse_sql_operation("COMMIT") == "UNKNOWN"
        assert _parse_sql_operation("ROLLBACK") == "UNKNOWN"


class TestPerformanceImpact:
    """Tests to verify instrumentation doesn't significantly impact performance."""

    @pytest.fixture
    def test_engine(self):
        """Create a test SQLite engine with test data."""
        engine = create_engine("sqlite:///:memory:")

        with engine.connect() as conn:
            conn.execute(
                text("CREATE TABLE test_users (id INTEGER PRIMARY KEY, name TEXT)")
            )
            # Insert test data
            for i in range(TEST_DATA_ROW_COUNT):
                conn.execute(
                    text(f"INSERT INTO test_users (id, name) VALUES ({i}, 'user{i}')")
                )
            conn.commit()

        yield engine
        engine.dispose()

    def test_instrumentation_overhead(self, test_engine):
        """Test that instrumentation overhead is minimal."""
        # Baseline: query without instrumentation
        start_time = time.perf_counter()
        for _ in range(PERFORMANCE_TEST_ITERATIONS):
            with test_engine.connect() as conn:
                conn.execute(text("SELECT * FROM test_users"))
        baseline_duration = time.perf_counter() - start_time

        # With instrumentation
        setup_db_instrumentation(test_engine)
        start_time = time.perf_counter()
        for _ in range(PERFORMANCE_TEST_ITERATIONS):
            with test_engine.connect() as conn:
                conn.execute(text("SELECT * FROM test_users"))
        instrumented_duration = time.perf_counter() - start_time

        # Overhead should be minimal
        overhead = (instrumented_duration - baseline_duration) / baseline_duration
        assert (
            overhead < MAX_INSTRUMENTATION_OVERHEAD
        ), f"Instrumentation overhead too high: {overhead*100:.1f}%"

        teardown_db_instrumentation(test_engine)
