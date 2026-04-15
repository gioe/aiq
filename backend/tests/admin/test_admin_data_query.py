"""
Tests for admin data-query endpoints (GET /v1/admin/data/* and POST /v1/admin/data/sql).
"""

from app.core.auth.security import hash_password
from app.models.models import Question, QuestionType, DifficultyLevel, User


class TestDataUsersEndpoint:
    """Tests for GET /v1/admin/data/users."""

    def test_returns_users(self, client, admin_headers, db_session):
        """Returns user list with expected fields."""
        user = User(
            email="datauser@example.com",
            password_hash=hash_password("pw123"),
            first_name="Alice",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.get("/v1/admin/data/users", headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        row = next(r for r in data if r["email"] == "datauser@example.com")
        assert row["id"] == user.id
        assert row["first_name"] == "Alice"
        assert "created_at" in row

    def test_requires_admin_token(self, client):
        """Returns 401/422 when X-Admin-Token header is missing."""
        response = client.get("/v1/admin/data/users")
        assert response.status_code in (401, 422)

    def test_invalid_admin_token(self, client):
        """Returns 401 for an invalid admin token."""
        response = client.get(
            "/v1/admin/data/users",
            headers={"X-Admin-Token": "wrong-token"},
        )
        assert response.status_code == 401


class TestDataInventoryEndpoint:
    """Tests for GET /v1/admin/data/inventory."""

    def test_returns_inventory(self, client, admin_headers, db_session):
        """Returns inventory rows with expected shape."""
        q = Question(
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.MEDIUM,
            question_text="Test Q",
            correct_answer="A",
            is_active=True,
        )
        db_session.add(q)
        db_session.commit()

        response = client.get("/v1/admin/data/inventory", headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        row = data[0]
        assert "question_type" in row
        assert "difficulty_level" in row
        assert "is_active" in row
        assert "count" in row

    def test_requires_admin_token(self, client):
        response = client.get("/v1/admin/data/inventory")
        assert response.status_code in (401, 422)


class TestDataSqlEndpoint:
    """Tests for POST /v1/admin/data/sql."""

    def test_valid_select(self, client, admin_headers, db_session):
        """Valid SELECT query returns columns and rows."""
        user = User(
            email="sqltest@example.com",
            password_hash=hash_password("pw123"),
        )
        db_session.add(user)
        db_session.commit()

        response = client.post(
            "/v1/admin/data/sql",
            json={"query": "SELECT id, email FROM users"},
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "columns" in data
        assert "rows" in data
        assert "id" in data["columns"]
        assert "email" in data["columns"]
        assert len(data["rows"]) >= 1

    def test_valid_with_statement(self, client, admin_headers, db_session):
        """WITH (CTE) queries are allowed."""
        response = client.post(
            "/v1/admin/data/sql",
            json={"query": "WITH cte AS (SELECT 1 AS n) SELECT n FROM cte"},
            headers=admin_headers,
        )
        assert response.status_code == 200

    def test_trailing_semicolon_allowed(self, client, admin_headers, db_session):
        """A single trailing semicolon is allowed."""
        response = client.post(
            "/v1/admin/data/sql",
            json={"query": "SELECT 1;"},
            headers=admin_headers,
        )
        assert response.status_code == 200

    def test_rejects_insert(self, client, admin_headers):
        """INSERT statements are rejected with 400."""
        response = client.post(
            "/v1/admin/data/sql",
            json={"query": "INSERT INTO users (email) VALUES ('hack@x.com')"},
            headers=admin_headers,
        )
        assert response.status_code == 400
        assert "SELECT" in response.json()["detail"]

    def test_rejects_update(self, client, admin_headers):
        """UPDATE statements are rejected with 400."""
        response = client.post(
            "/v1/admin/data/sql",
            json={"query": "UPDATE users SET email='hack@x.com'"},
            headers=admin_headers,
        )
        assert response.status_code == 400

    def test_rejects_delete(self, client, admin_headers):
        """DELETE statements are rejected with 400."""
        response = client.post(
            "/v1/admin/data/sql",
            json={"query": "DELETE FROM users"},
            headers=admin_headers,
        )
        assert response.status_code == 400

    def test_rejects_drop(self, client, admin_headers):
        """DROP statements are rejected with 400."""
        response = client.post(
            "/v1/admin/data/sql",
            json={"query": "DROP TABLE users"},
            headers=admin_headers,
        )
        assert response.status_code == 400

    def test_rejects_multi_statement(self, client, admin_headers):
        """Multi-statement queries (semicolon between statements) are rejected with 400."""
        response = client.post(
            "/v1/admin/data/sql",
            json={"query": "SELECT 1; SELECT 2"},
            headers=admin_headers,
        )
        assert response.status_code == 400
        assert "Multi-statement" in response.json()["detail"]

    def test_rejects_multi_statement_with_trailing(self, client, admin_headers):
        """Multi-statement with trailing semicolon is still rejected."""
        response = client.post(
            "/v1/admin/data/sql",
            json={"query": "SELECT 1; SELECT 2;"},
            headers=admin_headers,
        )
        assert response.status_code == 400

    def test_requires_admin_token(self, client):
        """Returns 401/422 when X-Admin-Token header is missing."""
        response = client.post(
            "/v1/admin/data/sql",
            json={"query": "SELECT 1"},
        )
        assert response.status_code in (401, 422)

    def test_invalid_admin_token(self, client):
        """Returns 401 for an invalid admin token."""
        response = client.post(
            "/v1/admin/data/sql",
            json={"query": "SELECT 1"},
            headers={"X-Admin-Token": "wrong-token"},
        )
        assert response.status_code == 401

    def test_rejects_blocked_table(self, client, admin_headers):
        """Queries referencing blocked tables are rejected with 400."""
        response = client.post(
            "/v1/admin/data/sql",
            json={"query": "SELECT * FROM password_reset_tokens"},
            headers=admin_headers,
        )
        assert response.status_code == 400
        assert "password_reset_tokens" in response.json()["detail"]

    def test_rejects_blocked_table_in_join(self, client, admin_headers):
        """Blocked tables in JOIN clauses are also rejected."""
        response = client.post(
            "/v1/admin/data/sql",
            json={
                "query": (
                    "SELECT u.email FROM users u "
                    "JOIN password_reset_tokens p ON u.id = p.user_id"
                )
            },
            headers=admin_headers,
        )
        assert response.status_code == 400
        assert "password_reset_tokens" in response.json()["detail"]

    def test_strips_blocked_columns(self, client, admin_headers, db_session):
        """Blocked columns (e.g. password_hash) are stripped from results."""
        user = User(
            email="blocklist@example.com",
            password_hash=hash_password("pw123"),
        )
        db_session.add(user)
        db_session.commit()

        response = client.post(
            "/v1/admin/data/sql",
            json={"query": "SELECT email, password_hash FROM users"},
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "email" in data["columns"]
        assert "password_hash" not in data["columns"]
        # Rows should only have the non-blocked column values
        for row in data["rows"]:
            assert len(row) == 1

    def test_strips_blocked_column_star_query(self, client, admin_headers, db_session):
        """SELECT * results also have blocked columns stripped."""
        user = User(
            email="starquery@example.com",
            password_hash=hash_password("pw123"),
        )
        db_session.add(user)
        db_session.commit()

        response = client.post(
            "/v1/admin/data/sql",
            json={"query": "SELECT * FROM users"},
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "password_hash" not in data["columns"]
        assert "apns_device_token" not in data["columns"]
        assert "email" in data["columns"]
