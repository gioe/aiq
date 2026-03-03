"""
Tests for admin session deletion endpoints.
"""

from app.core.auth.security import hash_password
from app.models import TestSession, User, UserQuestion
from app.models.models import Response, TestResult, TestStatus


class TestDeleteSession:
    """Tests for DELETE /v1/admin/sessions/{session_id}."""

    def _make_user(self, db_session, email="sess@example.com"):
        user = User(email=email, password_hash=hash_password("pw123"))
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    def _make_session(self, db_session, user):
        session = TestSession(user_id=user.id, status=TestStatus.COMPLETED)
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)
        return session

    def test_delete_session_204(self, client, admin_headers, db_session):
        """Returns 204 and removes the session."""
        user = self._make_user(db_session)
        session = self._make_session(db_session, user)

        response = client.delete(
            f"/v1/admin/sessions/{session.id}",
            headers=admin_headers,
        )

        assert response.status_code == 204
        session_id = session.id
        db_session.expunge(session)
        assert db_session.get(TestSession, session_id) is None

    def test_delete_session_not_found(self, client, admin_headers):
        """Returns 404 for a non-existent session_id."""
        response = client.delete(
            "/v1/admin/sessions/999999",
            headers=admin_headers,
        )
        assert response.status_code == 404

    def test_delete_session_requires_admin_token(self, client, db_session):
        """Returns 401/422 when X-Admin-Token header is missing."""
        user = self._make_user(db_session, email="sess_noauth@example.com")
        session = self._make_session(db_session, user)

        response = client.delete(f"/v1/admin/sessions/{session.id}")
        assert response.status_code in (401, 422)

    def test_delete_session_invalid_admin_token(self, client, db_session):
        """Returns 401 for an invalid admin token."""
        user = self._make_user(db_session, email="sess_badauth@example.com")
        session = self._make_session(db_session, user)

        response = client.delete(
            f"/v1/admin/sessions/{session.id}",
            headers={"X-Admin-Token": "wrong-token"},
        )
        assert response.status_code == 401

    def test_delete_session_dry_run_returns_preview(
        self, client, admin_headers, db_session
    ):
        """?dry_run=true returns preview without deleting."""
        user = self._make_user(db_session, email="sess_dry@example.com")
        session = self._make_session(db_session, user)

        response = client.delete(
            f"/v1/admin/sessions/{session.id}?dry_run=true",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session.id
        assert data["dry_run"] is True
        # Session should still exist
        assert db_session.get(TestSession, session.id) is not None

    def test_delete_session_dry_run_counts_responses(
        self, client, admin_headers, db_session, test_questions
    ):
        """Dry-run preview accurately counts associated responses."""
        user = self._make_user(db_session, email="sess_dry_count@example.com")
        session = self._make_session(db_session, user)
        question = test_questions[0]

        resp = Response(
            test_session_id=session.id,
            user_id=user.id,
            question_id=question.id,
            user_answer="A",
            is_correct=True,
        )
        db_session.add(resp)
        db_session.commit()

        response = client.delete(
            f"/v1/admin/sessions/{session.id}?dry_run=true",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["responses_count"] == 1
        assert data["has_test_result"] is False

    def test_delete_session_dry_run_detects_test_result(
        self, client, admin_headers, db_session
    ):
        """Dry-run preview reports has_test_result=True when a TestResult exists."""
        user = self._make_user(db_session, email="sess_result@example.com")
        session = self._make_session(db_session, user)

        result = TestResult(
            test_session_id=session.id,
            user_id=user.id,
            iq_score=100,
            total_questions=10,
            correct_answers=7,
        )
        db_session.add(result)
        db_session.commit()

        response = client.delete(
            f"/v1/admin/sessions/{session.id}?dry_run=true",
            headers=admin_headers,
        )

        assert response.status_code == 200
        assert response.json()["has_test_result"] is True

    def test_delete_session_dry_run_not_found(self, client, admin_headers):
        """?dry_run=true on a non-existent session still returns 404."""
        response = client.delete(
            "/v1/admin/sessions/999999?dry_run=true",
            headers=admin_headers,
        )
        assert response.status_code == 404

    def test_delete_session_cascades_child_records(
        self, client, admin_headers, db_session, test_questions
    ):
        """Deletion cascades to child Responses, TestResult, and UserQuestions."""
        user = self._make_user(db_session, email="sess_cascade@example.com")
        session = self._make_session(db_session, user)
        question = test_questions[0]

        resp = Response(
            test_session_id=session.id,
            user_id=user.id,
            question_id=question.id,
            user_answer="A",
            is_correct=True,
        )
        result = TestResult(
            test_session_id=session.id,
            user_id=user.id,
            iq_score=100,
            total_questions=1,
            correct_answers=1,
        )
        db_session.add_all([resp, result])
        db_session.commit()
        resp_id = resp.id
        result_id = result.id

        http_response = client.delete(
            f"/v1/admin/sessions/{session.id}",
            headers=admin_headers,
        )

        assert http_response.status_code == 204
        db_session.expunge_all()
        assert db_session.get(Response, resp_id) is None
        assert db_session.get(TestResult, result_id) is None

    def test_delete_session_dry_run_counts_user_questions(
        self, client, admin_headers, db_session, test_questions
    ):
        """Dry-run preview accurately counts associated user_questions."""
        user = self._make_user(db_session, email="sess_uq@example.com")
        session = self._make_session(db_session, user)
        question = test_questions[0]

        uq = UserQuestion(
            user_id=user.id,
            question_id=question.id,
            test_session_id=session.id,
        )
        db_session.add(uq)
        db_session.commit()

        response = client.delete(
            f"/v1/admin/sessions/{session.id}?dry_run=true",
            headers=admin_headers,
        )

        assert response.status_code == 200
        assert response.json()["user_questions_count"] == 1
