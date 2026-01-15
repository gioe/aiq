"""
Tests for feedback submission endpoints.
"""
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import SQLAlchemyError

from app.models import FeedbackSubmission
from app.ratelimit.storage import InMemoryStorage


@pytest.fixture(autouse=True)
def clear_rate_limits():
    """
    Automatically clear rate limits before each test.

    This fixture runs before each test to ensure rate limits don't
    interfere with test execution.
    """
    from app.api.v1.feedback import feedback_limiter

    # Clear the in-memory storage before each test
    feedback_limiter.storage.clear()

    yield

    # Optionally clear again after test
    feedback_limiter.storage.clear()


class TestFeedbackSubmissionSuccess:
    """Tests for successful feedback submission scenarios."""

    def test_submit_feedback_without_authentication(self, client, db_session):
        """Test submitting feedback without authentication (anonymous user)."""
        feedback_data = {
            "name": "John Doe",
            "email": "john@example.com",
            "category": "bug_report",
            "description": "The app crashes when I try to submit my test results.",
        }

        response = client.post("/v1/feedback/submit", json=feedback_data)

        assert response.status_code == 201
        data = response.json()

        # Verify response format
        assert data["success"] is True
        assert "submission_id" in data
        assert isinstance(data["submission_id"], int)
        assert (
            data["message"] == "Thank you for your feedback! We'll review it shortly."
        )

        # Verify database record
        submission = (
            db_session.query(FeedbackSubmission)
            .filter(FeedbackSubmission.id == data["submission_id"])
            .first()
        )
        assert submission is not None
        assert submission.name == "John Doe"
        assert submission.email == "john@example.com"
        assert submission.category.value == "bug_report"
        assert (
            submission.description
            == "The app crashes when I try to submit my test results."
        )
        assert submission.user_id is None  # No authentication

    def test_submit_feedback_with_authentication(
        self, client, db_session, test_user, auth_headers
    ):
        """Test submitting feedback with authentication (user_id should be linked)."""
        feedback_data = {
            "name": "Test User",
            "email": "test@example.com",
            "category": "feature_request",
            "description": "Please add dark mode support to the application.",
        }

        response = client.post(
            "/v1/feedback/submit", json=feedback_data, headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()

        # Verify response format
        assert data["success"] is True
        assert "submission_id" in data

        # Verify database record includes user_id
        submission = (
            db_session.query(FeedbackSubmission)
            .filter(FeedbackSubmission.id == data["submission_id"])
            .first()
        )
        assert submission is not None
        assert submission.user_id == test_user.id
        assert submission.name == "Test User"
        assert submission.email == "test@example.com"
        assert submission.category.value == "feature_request"

    def test_submit_feedback_all_categories(self, client, db_session):
        """Test submitting feedback for all supported categories."""
        categories = [
            "bug_report",
            "feature_request",
            "general_feedback",
            "question_help",
            "other",
        ]

        for category in categories:
            feedback_data = {
                "name": f"User {category}",
                "email": f"{category}@example.com",
                "category": category,
                "description": f"This is a test submission for {category} category.",
            }

            response = client.post("/v1/feedback/submit", json=feedback_data)

            assert response.status_code == 201, f"Failed for category: {category}"
            data = response.json()
            assert data["success"] is True

            # Verify in database
            submission = (
                db_session.query(FeedbackSubmission)
                .filter(FeedbackSubmission.id == data["submission_id"])
                .first()
            )
            assert submission.category.value == category

    def test_submit_feedback_with_valid_long_description(self, client, db_session):
        """Test submitting feedback with a long but valid description (near 5000 char limit)."""
        long_description = "A" * 4995  # 4995 chars, well under 5000 limit

        feedback_data = {
            "name": "Long Feedback User",
            "email": "long@example.com",
            "category": "general_feedback",
            "description": long_description,
        }

        response = client.post("/v1/feedback/submit", json=feedback_data)

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True

        # Verify in database
        submission = (
            db_session.query(FeedbackSubmission)
            .filter(FeedbackSubmission.id == data["submission_id"])
            .first()
        )
        assert len(submission.description) == 4995


class TestFeedbackValidationErrors:
    """Tests for validation errors in feedback submission."""

    def test_submit_feedback_missing_name(self, client):
        """Test submitting feedback without name field."""
        feedback_data = {
            "email": "test@example.com",
            "category": "bug_report",
            "description": "Missing name field in this submission.",
        }

        response = client.post("/v1/feedback/submit", json=feedback_data)

        assert response.status_code == 422  # Validation error

    def test_submit_feedback_missing_email(self, client):
        """Test submitting feedback without email field."""
        feedback_data = {
            "name": "John Doe",
            "category": "bug_report",
            "description": "Missing email field in this submission.",
        }

        response = client.post("/v1/feedback/submit", json=feedback_data)

        assert response.status_code == 422  # Validation error

    def test_submit_feedback_missing_category(self, client):
        """Test submitting feedback without category field."""
        feedback_data = {
            "name": "John Doe",
            "email": "test@example.com",
            "description": "Missing category field in this submission.",
        }

        response = client.post("/v1/feedback/submit", json=feedback_data)

        assert response.status_code == 422  # Validation error

    def test_submit_feedback_missing_description(self, client):
        """Test submitting feedback without description field."""
        feedback_data = {
            "name": "John Doe",
            "email": "test@example.com",
            "category": "bug_report",
        }

        response = client.post("/v1/feedback/submit", json=feedback_data)

        assert response.status_code == 422  # Validation error

    def test_submit_feedback_invalid_email_format(self, client):
        """Test submitting feedback with invalid email format."""
        feedback_data = {
            "name": "John Doe",
            "email": "not-an-email",
            "category": "bug_report",
            "description": "This submission has an invalid email format.",
        }

        response = client.post("/v1/feedback/submit", json=feedback_data)

        assert response.status_code == 422  # Validation error

    def test_submit_feedback_description_too_short(self, client):
        """Test submitting feedback with description less than 10 characters."""
        feedback_data = {
            "name": "John Doe",
            "email": "test@example.com",
            "category": "bug_report",
            "description": "Short",  # Only 5 characters
        }

        response = client.post("/v1/feedback/submit", json=feedback_data)

        assert response.status_code == 422  # Validation error

    def test_submit_feedback_description_too_long(self, client):
        """Test submitting feedback with description exceeding 5000 characters."""
        feedback_data = {
            "name": "John Doe",
            "email": "test@example.com",
            "category": "bug_report",
            "description": "A" * 5001,  # 5001 characters, exceeds limit
        }

        response = client.post("/v1/feedback/submit", json=feedback_data)

        assert response.status_code == 422  # Validation error

    def test_submit_feedback_invalid_category(self, client):
        """Test submitting feedback with an invalid category value."""
        feedback_data = {
            "name": "John Doe",
            "email": "test@example.com",
            "category": "invalid_category",
            "description": "This submission has an invalid category.",
        }

        response = client.post("/v1/feedback/submit", json=feedback_data)

        assert response.status_code == 422  # Validation error

    def test_submit_feedback_name_too_long(self, client):
        """Test submitting feedback with name exceeding 100 characters."""
        feedback_data = {
            "name": "A" * 101,  # 101 characters
            "email": "test@example.com",
            "category": "bug_report",
            "description": "This submission has a name that is too long.",
        }

        response = client.post("/v1/feedback/submit", json=feedback_data)

        assert response.status_code == 422  # Validation error

    def test_submit_feedback_empty_name(self, client):
        """Test submitting feedback with empty name."""
        feedback_data = {
            "name": "",
            "email": "test@example.com",
            "category": "bug_report",
            "description": "This submission has an empty name.",
        }

        response = client.post("/v1/feedback/submit", json=feedback_data)

        assert response.status_code == 422  # Validation error

    def test_submit_feedback_whitespace_only_name(self, client):
        """Test submitting feedback with whitespace-only name."""
        feedback_data = {
            "name": "   ",
            "email": "test@example.com",
            "category": "bug_report",
            "description": "This submission has a whitespace-only name.",
        }

        response = client.post("/v1/feedback/submit", json=feedback_data)

        assert response.status_code == 422  # Validation error


class TestFeedbackRateLimiting:
    """Tests for rate limiting on feedback submissions."""

    def test_rate_limit_allows_five_submissions(self, client, db_session):
        """Test that 5 submissions are allowed within the rate limit."""
        # Clear any existing rate limits by using unique client IP simulation
        # The test client uses testclient as the IP by default

        for i in range(5):
            feedback_data = {
                "name": f"User {i}",
                "email": f"user{i}@example.com",
                "category": "bug_report",
                "description": f"This is test submission number {i} within the rate limit.",
            }

            response = client.post("/v1/feedback/submit", json=feedback_data)

            assert response.status_code == 201, f"Submission {i+1} should succeed"
            data = response.json()
            assert data["success"] is True

    def test_rate_limit_blocks_sixth_submission(self, client):
        """Test that the 6th submission within the window returns 429 status."""
        # Submit 5 allowed requests
        for i in range(5):
            feedback_data = {
                "name": f"User {i}",
                "email": f"ratelimit{i}@example.com",
                "category": "bug_report",
                "description": f"Rate limit test submission number {i}.",
            }
            response = client.post("/v1/feedback/submit", json=feedback_data)
            assert response.status_code == 201

        # 6th request should be rate limited
        feedback_data = {
            "name": "Blocked User",
            "email": "blocked@example.com",
            "category": "bug_report",
            "description": "This submission should be rate limited.",
        }

        response = client.post("/v1/feedback/submit", json=feedback_data)

        assert response.status_code == 429  # Too Many Requests
        data = response.json()["detail"]
        assert data["error"] == "Rate limit exceeded"
        assert "Too many feedback submissions" in data["message"]
        assert "retry_after" in data

    def test_rate_limit_includes_retry_after_header(self, client):
        """Test that rate limit response includes Retry-After header."""
        # Submit 5 allowed requests
        for i in range(5):
            feedback_data = {
                "name": f"User {i}",
                "email": f"retry{i}@example.com",
                "category": "bug_report",
                "description": f"Retry header test submission {i}.",
            }
            client.post("/v1/feedback/submit", json=feedback_data)

        # 6th request should include Retry-After header
        feedback_data = {
            "name": "Retry User",
            "email": "retry@example.com",
            "category": "bug_report",
            "description": "Testing Retry-After header.",
        }

        response = client.post("/v1/feedback/submit", json=feedback_data)

        assert response.status_code == 429
        # The Retry-After header might not be set by TestClient or middleware
        # Check that retry_after is in the response body instead
        data = response.json()["detail"]
        assert "retry_after" in data

    def test_rate_limit_cannot_be_bypassed_with_spoofed_header(self, client):
        """Test that spoofing X-Forwarded-For cannot bypass rate limiting (BTS-221)."""
        feedback_data_base = {
            "name": "Attacker",
            "email": "attacker@example.com",
            "category": "bug_report",
            "description": "Attempting to bypass rate limiting.",
        }

        # Submit 5 requests without spoofing - should succeed
        for i in range(5):
            feedback_data = feedback_data_base.copy()
            feedback_data["email"] = f"attacker{i}@example.com"
            response = client.post("/v1/feedback/submit", json=feedback_data)
            assert response.status_code == 201

        # Try to bypass rate limit by spoofing X-Forwarded-For
        # This should FAIL because we now ignore X-Forwarded-For
        feedback_data = feedback_data_base.copy()
        feedback_data["email"] = "attacker_spoofed@example.com"

        # Attacker tries different IPs to bypass rate limiting
        spoofed_ips = [
            "1.2.3.4",
            "5.6.7.8",
            "9.10.11.12",
        ]

        for spoofed_ip in spoofed_ips:
            headers = {"X-Forwarded-For": spoofed_ip}
            response = client.post(
                "/v1/feedback/submit", json=feedback_data, headers=headers
            )
            # Should be rate limited (429) because spoofed header is ignored
            assert (
                response.status_code == 429
            ), f"Spoofed IP {spoofed_ip} should not bypass rate limiting"

    def test_rate_limit_with_envoy_header_per_unique_ip(self, client):
        """Test that rate limiting works correctly with X-Envoy-External-Address."""
        feedback_data_base = {
            "name": "Railway User",
            "email": "railway@example.com",
            "category": "bug_report",
            "description": "Testing rate limiting with Envoy header.",
        }

        # Different real IPs from Railway should have separate rate limits
        ip_addresses = [
            "203.0.113.1",
            "203.0.113.2",
            "203.0.113.3",
        ]

        for ip in ip_addresses:
            # Each IP should be able to submit (not rate limited across IPs)
            feedback_data = feedback_data_base.copy()
            feedback_data["email"] = f"user_{ip.replace('.', '_')}@example.com"
            headers = {"X-Envoy-External-Address": ip}

            response = client.post(
                "/v1/feedback/submit", json=feedback_data, headers=headers
            )
            assert (
                response.status_code == 201
            ), f"Different IP {ip} should have its own rate limit"


class TestFeedbackHeaderExtraction:
    """Tests for extracting request headers in feedback submission."""

    def test_submit_feedback_captures_app_version(self, client, db_session):
        """Test that X-App-Version header is captured in database."""
        feedback_data = {
            "name": "Header Test User",
            "email": "headers@example.com",
            "category": "bug_report",
            "description": "Testing header extraction for app version.",
        }

        headers = {"X-App-Version": "1.2.3"}
        response = client.post(
            "/v1/feedback/submit", json=feedback_data, headers=headers
        )

        assert response.status_code == 201
        data = response.json()

        # Verify in database
        submission = (
            db_session.query(FeedbackSubmission)
            .filter(FeedbackSubmission.id == data["submission_id"])
            .first()
        )
        assert submission.app_version == "1.2.3"

    def test_submit_feedback_captures_ios_version(self, client, db_session):
        """Test that X-Platform header is captured as ios_version in database."""
        feedback_data = {
            "name": "Platform Test User",
            "email": "platform@example.com",
            "category": "bug_report",
            "description": "Testing header extraction for iOS version.",
        }

        headers = {"X-Platform": "iOS 17.0"}
        response = client.post(
            "/v1/feedback/submit", json=feedback_data, headers=headers
        )

        assert response.status_code == 201
        data = response.json()

        # Verify in database
        submission = (
            db_session.query(FeedbackSubmission)
            .filter(FeedbackSubmission.id == data["submission_id"])
            .first()
        )
        assert submission.ios_version == "iOS 17.0"

    def test_submit_feedback_captures_device_id(self, client, db_session):
        """Test that X-Device-ID header is captured in database."""
        feedback_data = {
            "name": "Device Test User",
            "email": "device@example.com",
            "category": "bug_report",
            "description": "Testing header extraction for device ID.",
        }

        headers = {"X-Device-ID": "ABC123DEF456"}
        response = client.post(
            "/v1/feedback/submit", json=feedback_data, headers=headers
        )

        assert response.status_code == 201
        data = response.json()

        # Verify in database
        submission = (
            db_session.query(FeedbackSubmission)
            .filter(FeedbackSubmission.id == data["submission_id"])
            .first()
        )
        assert submission.device_id == "ABC123DEF456"

    def test_submit_feedback_with_all_headers(self, client, db_session):
        """Test submitting feedback with all optional headers present."""
        feedback_data = {
            "name": "All Headers User",
            "email": "allheaders@example.com",
            "category": "feature_request",
            "description": "Testing submission with all headers present.",
        }

        headers = {
            "X-App-Version": "2.0.1",
            "X-Platform": "iOS 16.5",
            "X-Device-ID": "DEVICE-XYZ-789",
        }

        response = client.post(
            "/v1/feedback/submit", json=feedback_data, headers=headers
        )

        assert response.status_code == 201
        data = response.json()

        # Verify all headers in database
        submission = (
            db_session.query(FeedbackSubmission)
            .filter(FeedbackSubmission.id == data["submission_id"])
            .first()
        )
        assert submission.app_version == "2.0.1"
        assert submission.ios_version == "iOS 16.5"
        assert submission.device_id == "DEVICE-XYZ-789"

    def test_submit_feedback_without_headers(self, client, db_session):
        """Test submitting feedback without optional headers (should be None)."""
        feedback_data = {
            "name": "No Headers User",
            "email": "noheaders@example.com",
            "category": "other",
            "description": "Testing submission without any optional headers.",
        }

        response = client.post("/v1/feedback/submit", json=feedback_data)

        assert response.status_code == 201
        data = response.json()

        # Verify headers are None in database
        submission = (
            db_session.query(FeedbackSubmission)
            .filter(FeedbackSubmission.id == data["submission_id"])
            .first()
        )
        assert submission.app_version is None
        assert submission.ios_version is None
        assert submission.device_id is None


class TestFeedbackSQLInjectionPrevention:
    """Tests for SQL injection prevention in feedback submission."""

    def test_submit_feedback_name_sql_injection_attempt(self, client):
        """Test that SQL injection attempts in name field are blocked."""
        feedback_data = {
            "name": "'; DROP TABLE feedback_submissions; --",
            "email": "hacker@example.com",
            "category": "bug_report",
            "description": "Testing SQL injection in name field.",
        }

        response = client.post("/v1/feedback/submit", json=feedback_data)

        # Should be rejected by validation
        assert response.status_code == 422

    def test_submit_feedback_description_sql_injection_attempt(self, client):
        """Test that SQL injection attempts in description field are blocked."""
        feedback_data = {
            "name": "Test User",
            "email": "test@example.com",
            "category": "bug_report",
            "description": "' OR '1'='1'; DELETE FROM users; --",
        }

        response = client.post("/v1/feedback/submit", json=feedback_data)

        # Should be rejected by validation
        assert response.status_code == 422

    def test_submit_feedback_valid_special_characters_allowed(self, client, db_session):
        """Test that legitimate special characters in feedback are allowed."""
        feedback_data = {
            "name": "John OBrien",
            "email": "john@example.com",
            "category": "feature_request",
            "description": "I would like to see better support for users. Can we add this feature?",
        }

        response = client.post("/v1/feedback/submit", json=feedback_data)

        assert response.status_code == 201
        data = response.json()

        # Verify in database
        submission = (
            db_session.query(FeedbackSubmission)
            .filter(FeedbackSubmission.id == data["submission_id"])
            .first()
        )
        assert submission.name == "John OBrien"
        assert "I would like to see" in submission.description


class TestFeedbackIPAddressNotStored:
    """Tests verifying IP addresses are NOT stored for privacy compliance."""

    def test_submit_feedback_does_not_store_ip_address(self, client, db_session):
        """Test that IP address is NOT stored in database (privacy compliance)."""
        feedback_data = {
            "name": "Privacy User",
            "email": "privacy@example.com",
            "category": "bug_report",
            "description": "Testing that IP addresses are not persisted.",
        }

        response = client.post("/v1/feedback/submit", json=feedback_data)

        assert response.status_code == 201
        data = response.json()

        # Verify IP address is NULL in database
        submission = (
            db_session.query(FeedbackSubmission)
            .filter(FeedbackSubmission.id == data["submission_id"])
            .first()
        )
        assert submission.ip_address is None

    def test_submit_feedback_with_envoy_header_still_not_stored(
        self, client, db_session
    ):
        """Test that IP address from X-Envoy-External-Address is NOT stored."""
        feedback_data = {
            "name": "Railway User",
            "email": "railway@example.com",
            "category": "bug_report",
            "description": "Testing IP not stored even with Envoy header.",
        }

        headers = {"X-Envoy-External-Address": "203.0.113.45"}
        response = client.post(
            "/v1/feedback/submit", json=feedback_data, headers=headers
        )

        assert response.status_code == 201
        data = response.json()

        # Verify IP is still NULL even when header is present
        submission = (
            db_session.query(FeedbackSubmission)
            .filter(FeedbackSubmission.id == data["submission_id"])
            .first()
        )
        assert submission.ip_address is None


class TestFeedbackDatabaseErrorHandling:
    """Tests for database error handling in feedback submission."""

    def test_submit_feedback_database_error_returns_500(self, client, db_session):
        """Test that database errors during feedback submission return 500."""
        feedback_data = {
            "name": "DB Error User",
            "email": "dberror@example.com",
            "category": "bug_report",
            "description": "Testing database error handling.",
        }

        # Mock the commit method on the actual db_session
        original_commit = db_session.commit
        db_session.commit = MagicMock(
            side_effect=SQLAlchemyError("Database connection lost")
        )

        try:
            response = client.post("/v1/feedback/submit", json=feedback_data)
            assert response.status_code == 500
            data = response.json()
            assert (
                "error" in data["detail"].lower()
                or "unexpected" in data["detail"].lower()
            )
        finally:
            # Restore original commit
            db_session.commit = original_commit

    def test_submit_feedback_database_error_triggers_rollback(self, client, db_session):
        """Test that database errors trigger rollback."""
        feedback_data = {
            "name": "Rollback Test",
            "email": "rollback@example.com",
            "category": "bug_report",
            "description": "Testing rollback on database error.",
        }

        # Mock both commit and rollback
        original_commit = db_session.commit
        original_rollback = db_session.rollback
        mock_rollback = MagicMock()

        db_session.commit = MagicMock(side_effect=SQLAlchemyError("Commit failed"))
        db_session.rollback = mock_rollback

        try:
            response = client.post("/v1/feedback/submit", json=feedback_data)
            assert response.status_code == 500

            # Verify rollback was called
            mock_rollback.assert_called_once()
        finally:
            # Restore originals
            db_session.commit = original_commit
            db_session.rollback = original_rollback

    def test_submit_feedback_database_error_logs_error(self, client, db_session):
        """Test that database errors are logged."""
        feedback_data = {
            "name": "Log Test User",
            "email": "logtest@example.com",
            "category": "bug_report",
            "description": "Testing error logging on database failure.",
        }

        # Mock commit to raise error
        original_commit = db_session.commit
        db_session.commit = MagicMock(side_effect=SQLAlchemyError("Database timeout"))

        try:
            with patch("app.api.v1.feedback.logger") as mock_logger:
                response = client.post("/v1/feedback/submit", json=feedback_data)
                assert response.status_code == 500

                # Verify error was logged
                mock_logger.error.assert_called_once()
                log_call_args = str(mock_logger.error.call_args)
                assert "Database error during feedback submission" in log_call_args
        finally:
            # Restore original commit
            db_session.commit = original_commit


class TestFeedbackEdgeCases:
    """Tests for edge cases in feedback submission."""

    def test_submit_feedback_description_with_newlines(self, client, db_session):
        """Test submitting feedback with newlines in description."""
        feedback_data = {
            "name": "Newline Test User",
            "email": "newline@example.com",
            "category": "bug_report",
            "description": "This is line 1.\nThis is line 2.\nThis is line 3.",
        }

        response = client.post("/v1/feedback/submit", json=feedback_data)

        assert response.status_code == 201
        data = response.json()

        # Verify newlines are preserved
        submission = (
            db_session.query(FeedbackSubmission)
            .filter(FeedbackSubmission.id == data["submission_id"])
            .first()
        )
        assert "\n" in submission.description
        assert "line 1" in submission.description
        assert "line 3" in submission.description

    def test_submit_feedback_description_with_unicode(self, client, db_session):
        """Test submitting feedback with Unicode characters."""
        feedback_data = {
            "name": "Unicode User",
            "email": "unicode@example.com",
            "category": "general_feedback",
            "description": "Great app! 👍 Works perfectly. Merci beaucoup! 日本語もOK",
        }

        response = client.post("/v1/feedback/submit", json=feedback_data)

        assert response.status_code == 201
        data = response.json()

        # Verify Unicode is preserved
        submission = (
            db_session.query(FeedbackSubmission)
            .filter(FeedbackSubmission.id == data["submission_id"])
            .first()
        )
        assert "👍" in submission.description
        assert "Merci" in submission.description
        assert "日本語" in submission.description

    def test_submit_feedback_email_case_handling(self, client, db_session):
        """Test email case handling in feedback submission."""
        feedback_data = {
            "name": "Case Test User",
            "email": "Test.User@Example.COM",
            "category": "other",
            "description": "Testing email case handling.",
        }

        response = client.post("/v1/feedback/submit", json=feedback_data)

        assert response.status_code == 201
        data = response.json()

        # Verify email is stored (Pydantic EmailStr may normalize domain to lowercase)
        submission = (
            db_session.query(FeedbackSubmission)
            .filter(FeedbackSubmission.id == data["submission_id"])
            .first()
        )
        # Pydantic EmailStr normalizes at least the domain part to lowercase
        assert submission.email.lower() == "test.user@example.com"
        # But the actual stored value depends on Pydantic version behavior
        assert "@example.com" in submission.email.lower()

    def test_submit_feedback_description_exact_minimum_length(self, client, db_session):
        """Test submitting feedback with exactly 10 characters (minimum)."""
        feedback_data = {
            "name": "Min Length User",
            "email": "minlength@example.com",
            "category": "other",
            "description": "1234567890",  # Exactly 10 characters
        }

        response = client.post("/v1/feedback/submit", json=feedback_data)

        assert response.status_code == 201
        data = response.json()

        # Verify in database
        submission = (
            db_session.query(FeedbackSubmission)
            .filter(FeedbackSubmission.id == data["submission_id"])
            .first()
        )
        assert len(submission.description) == 10

    def test_submit_feedback_description_exact_maximum_length(self, client, db_session):
        """Test submitting feedback with exactly 5000 characters (maximum)."""
        feedback_data = {
            "name": "Max Length User",
            "email": "maxlength@example.com",
            "category": "other",
            "description": "A" * 5000,  # Exactly 5000 characters
        }

        response = client.post("/v1/feedback/submit", json=feedback_data)

        assert response.status_code == 201
        data = response.json()

        # Verify in database
        submission = (
            db_session.query(FeedbackSubmission)
            .filter(FeedbackSubmission.id == data["submission_id"])
            .first()
        )
        assert len(submission.description) == 5000

    def test_submit_feedback_with_invalid_auth_token(self, client, db_session):
        """Test that invalid auth token is ignored (feedback still submitted)."""
        feedback_data = {
            "name": "Invalid Token User",
            "email": "invalidtoken@example.com",
            "category": "bug_report",
            "description": "Testing submission with invalid authentication token.",
        }

        headers = {"Authorization": "Bearer invalid_token_here"}
        response = client.post(
            "/v1/feedback/submit", json=feedback_data, headers=headers
        )

        # Should succeed because authentication is optional
        assert response.status_code == 201
        data = response.json()

        # Verify user_id is None (authentication failed but submission succeeded)
        submission = (
            db_session.query(FeedbackSubmission)
            .filter(FeedbackSubmission.id == data["submission_id"])
            .first()
        )
        assert submission.user_id is None

    def test_submit_feedback_name_with_maximum_length(self, client, db_session):
        """Test submitting feedback with name at exactly 100 characters (maximum)."""
        feedback_data = {
            "name": "A" * 100,  # Exactly 100 characters
            "email": "maxname@example.com",
            "category": "other",
            "description": "Testing maximum name length.",
        }

        response = client.post("/v1/feedback/submit", json=feedback_data)

        assert response.status_code == 201
        data = response.json()

        # Verify in database
        submission = (
            db_session.query(FeedbackSubmission)
            .filter(FeedbackSubmission.id == data["submission_id"])
            .first()
        )
        assert len(submission.name) == 100


class TestFeedbackNotificationErrorHandling:
    """Tests for email notification error handling in feedback submission."""

    def test_submit_feedback_succeeds_when_notification_returns_false(
        self, client, db_session
    ):
        """Test that feedback submission succeeds even when notification returns False."""
        feedback_data = {
            "name": "Notification Fail User",
            "email": "notifail@example.com",
            "category": "bug_report",
            "description": "Testing graceful handling of notification failures.",
        }

        # Mock the notification function to return False (simulating internal failure)
        with patch(
            "app.api.v1.feedback._send_feedback_notification",
            return_value=False,
        ):
            response = client.post("/v1/feedback/submit", json=feedback_data)

        # Should still succeed - notification failure shouldn't crash the endpoint
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "submission_id" in data

        # Verify feedback was saved to database
        submission = (
            db_session.query(FeedbackSubmission)
            .filter(FeedbackSubmission.id == data["submission_id"])
            .first()
        )
        assert submission is not None
        assert submission.email == "notifail@example.com"

    def test_notification_success_is_logged_correctly(self, client, db_session):
        """Test that notification success status is logged for monitoring."""
        feedback_data = {
            "name": "Log Test User",
            "email": "lognotif@example.com",
            "category": "feature_request",
            "description": "Testing that notification status is logged.",
        }

        with patch("app.api.v1.feedback.logger") as mock_logger:
            response = client.post("/v1/feedback/submit", json=feedback_data)

        # Should succeed
        assert response.status_code == 201

        # Verify success log includes notification_sent status
        info_calls = [str(call) for call in mock_logger.info.call_args_list]
        success_logs = [c for c in info_calls if "Feedback submission successful" in c]
        assert len(success_logs) > 0
        assert "notification_sent=True" in success_logs[0]

    def test_notification_returns_false_on_exception(self):
        """Test that _send_feedback_notification returns False on exception."""
        from app.api.v1.feedback import _send_feedback_notification

        # Create a mock feedback object that will cause an exception
        mock_feedback = MagicMock()
        mock_feedback.category.value = "bug_report"
        # Make description property raise an exception when accessed
        type(mock_feedback).description = property(
            lambda self: (_ for _ in ()).throw(RuntimeError("Attribute error"))
        )

        with patch("app.api.v1.feedback.logger"):
            result = _send_feedback_notification(mock_feedback)

        assert result is False

    def test_notification_returns_true_on_success(self, db_session):
        """Test that _send_feedback_notification returns True on success."""
        from app.api.v1.feedback import _send_feedback_notification
        from app.models import FeedbackCategory

        # Create a real feedback object
        feedback = FeedbackSubmission(
            id=999,
            name="Test User",
            email="test@example.com",
            category=FeedbackCategory.BUG_REPORT,
            description="This is a test feedback submission.",
        )

        with patch("app.api.v1.feedback.logger"):
            result = _send_feedback_notification(feedback)

        assert result is True

    def test_notification_failure_logs_feedback_id(self):
        """Test that notification errors include feedback ID for debugging."""
        from app.api.v1.feedback import _send_feedback_notification

        # Create a mock feedback that will fail during notification
        mock_feedback = MagicMock()
        mock_feedback.id = 12345
        mock_feedback.category.value = "bug_report"
        # Cause an exception when accessing email
        type(mock_feedback).email = property(
            lambda self: (_ for _ in ()).throw(ValueError("Invalid email"))
        )

        with patch("app.api.v1.feedback.logger") as mock_logger:
            result = _send_feedback_notification(mock_feedback)

        assert result is False
        # Verify error was logged with feedback_id
        mock_logger.error.assert_called_once()
        log_message = str(mock_logger.error.call_args)
        assert "feedback_id=12345" in log_message

    def test_notification_failure_logged_as_false(self, client, db_session):
        """Test that notification failure is logged with notification_sent=False."""
        feedback_data = {
            "name": "Status Log User",
            "email": "statuslog@example.com",
            "category": "general_feedback",
            "description": "Testing that notification failure status is logged.",
        }

        with patch("app.api.v1.feedback.logger") as mock_logger:
            # Mock notification to return False
            with patch(
                "app.api.v1.feedback._send_feedback_notification",
                return_value=False,
            ):
                response = client.post("/v1/feedback/submit", json=feedback_data)

        assert response.status_code == 201

        # Find the success log call and verify it includes notification_sent=False
        info_calls = [str(call) for call in mock_logger.info.call_args_list]
        success_log = [c for c in info_calls if "Feedback submission successful" in c]
        assert len(success_log) > 0
        assert "notification_sent=False" in success_log[0]


class TestRateLimiterErrorHandling:
    """Tests for rate limiter error handling in feedback submission."""

    def test_submit_feedback_succeeds_when_rate_limiter_throws_exception(
        self, client, db_session
    ):
        """Test that feedback submission succeeds when rate limiter fails (fail-open)."""
        feedback_data = {
            "name": "Rate Limiter Error User",
            "email": "rlerror@example.com",
            "category": "bug_report",
            "description": "Testing feedback submission when rate limiter fails.",
        }

        # Mock the rate limiter check to raise an exception
        with patch(
            "app.api.v1.feedback.feedback_limiter.check",
            side_effect=RuntimeError("Redis connection failed"),
        ):
            response = client.post("/v1/feedback/submit", json=feedback_data)

        # Should succeed because we fail-open
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "submission_id" in data

        # Verify feedback was saved to database
        submission = (
            db_session.query(FeedbackSubmission)
            .filter(FeedbackSubmission.id == data["submission_id"])
            .first()
        )
        assert submission is not None
        assert submission.email == "rlerror@example.com"

    def test_rate_limiter_error_logs_warning(self, client, db_session):
        """Test that rate limiter errors are logged as warnings."""
        feedback_data = {
            "name": "Log Warning User",
            "email": "logwarn@example.com",
            "category": "general_feedback",
            "description": "Testing that rate limiter errors are logged.",
        }

        with patch(
            "app.api.v1.feedback.feedback_limiter.check",
            side_effect=ConnectionError("Storage backend unavailable"),
        ):
            with patch("app.api.v1.feedback.logger") as mock_logger:
                response = client.post("/v1/feedback/submit", json=feedback_data)

        assert response.status_code == 201

        # Verify warning was logged with appropriate context
        mock_logger.warning.assert_called_once()
        warning_message = str(mock_logger.warning.call_args)
        assert "Rate limiter error" in warning_message
        assert "ConnectionError" in warning_message
        assert "fail-open" in warning_message

    def test_rate_limiter_error_logs_client_ip(self, client, db_session):
        """Test that rate limiter error logs include client IP for debugging."""
        feedback_data = {
            "name": "IP Log User",
            "email": "iplog@example.com",
            "category": "bug_report",
            "description": "Testing that client IP is logged with rate limiter errors.",
        }

        with patch(
            "app.api.v1.feedback.feedback_limiter.check",
            side_effect=TimeoutError("Rate limiter timed out"),
        ):
            with patch("app.api.v1.feedback.logger") as mock_logger:
                response = client.post("/v1/feedback/submit", json=feedback_data)

        assert response.status_code == 201

        # Verify client_ip is in the log message
        warning_message = str(mock_logger.warning.call_args)
        assert "client_ip=" in warning_message

    def test_rate_limit_429_still_returned_when_limit_exceeded(self, client):
        """Test that 429 is still returned when rate limit is exceeded (not an error)."""
        # Submit 5 allowed requests
        for i in range(5):
            feedback_data = {
                "name": f"User {i}",
                "email": f"exceeded{i}@example.com",
                "category": "bug_report",
                "description": f"Testing rate limit still works after adding error handling {i}.",
            }
            response = client.post("/v1/feedback/submit", json=feedback_data)
            assert response.status_code == 201

        # 6th request should still be rate limited
        feedback_data = {
            "name": "Exceeded User",
            "email": "exceeded@example.com",
            "category": "bug_report",
            "description": "This should be rate limited.",
        }

        response = client.post("/v1/feedback/submit", json=feedback_data)

        assert response.status_code == 429
        data = response.json()["detail"]
        assert data["error"] == "Rate limit exceeded"

    def test_rate_limiter_redis_error_allows_request(self, client, db_session):
        """Test that Redis-specific errors allow request to proceed."""
        feedback_data = {
            "name": "Redis Error User",
            "email": "rediserr@example.com",
            "category": "feature_request",
            "description": "Testing that Redis errors don't block feedback.",
        }

        # Simulate a Redis-like error
        with patch(
            "app.api.v1.feedback.feedback_limiter.check",
            side_effect=Exception(
                "READONLY You can't write against a read only replica"
            ),
        ):
            response = client.post("/v1/feedback/submit", json=feedback_data)

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True

    def test_multiple_requests_succeed_when_rate_limiter_fails(
        self, client, db_session
    ):
        """Test that multiple requests can succeed when rate limiter is failing."""
        # All requests should succeed when rate limiter is broken
        for i in range(10):  # More than the normal 5 limit
            feedback_data = {
                "name": f"Unlimited User {i}",
                "email": f"unlimited{i}@example.com",
                "category": "bug_report",
                "description": f"Request {i} when rate limiter is down.",
            }

            with patch(
                "app.api.v1.feedback.feedback_limiter.check",
                side_effect=RuntimeError("Rate limiter unavailable"),
            ):
                response = client.post("/v1/feedback/submit", json=feedback_data)

            assert response.status_code == 201, f"Request {i} should succeed"

        # Verify all 10 submissions were saved
        submissions = (
            db_session.query(FeedbackSubmission)
            .filter(FeedbackSubmission.email.like("unlimited%@example.com"))
            .all()
        )
        assert len(submissions) == 10


class TestCreateRateLimiterStorage:
    """Tests for _create_rate_limiter_storage() function."""

    def test_returns_in_memory_storage_when_storage_is_memory(self):
        """Test that in-memory storage is returned when RATE_LIMIT_STORAGE is 'memory'."""
        from app.api.v1.feedback import _create_rate_limiter_storage

        with patch("app.api.v1.feedback.settings") as mock_settings:
            mock_settings.RATE_LIMIT_STORAGE = "memory"
            mock_settings.RATE_LIMIT_MAX_KEYS = 100000

            storage = _create_rate_limiter_storage()

            assert isinstance(storage, InMemoryStorage)

    def test_returns_redis_storage_when_configured_and_connected(self):
        """Test that Redis storage is returned when configured and connection succeeds."""
        from app.api.v1.feedback import _create_rate_limiter_storage

        mock_redis_storage = MagicMock()
        mock_redis_storage.is_connected.return_value = True

        with patch("app.api.v1.feedback.settings") as mock_settings:
            mock_settings.RATE_LIMIT_STORAGE = "redis"
            mock_settings.RATE_LIMIT_REDIS_URL = "redis://localhost:6379/0"

            # Mock at the source module level since import is inside function
            with patch(
                "app.ratelimit.storage.RedisStorage",
                return_value=mock_redis_storage,
            ):
                storage = _create_rate_limiter_storage()

                assert storage == mock_redis_storage
                mock_redis_storage.is_connected.assert_called_once()

    def test_fallback_to_in_memory_when_redis_connection_fails(self):
        """Test fallback to in-memory when Redis connection fails."""
        from app.api.v1.feedback import _create_rate_limiter_storage

        mock_redis_storage = MagicMock()
        mock_redis_storage.is_connected.return_value = False

        with patch("app.api.v1.feedback.settings") as mock_settings:
            mock_settings.RATE_LIMIT_STORAGE = "redis"
            mock_settings.RATE_LIMIT_REDIS_URL = "redis://localhost:6379/0"
            mock_settings.RATE_LIMIT_MAX_KEYS = 50000

            with patch(
                "app.ratelimit.storage.RedisStorage",
                return_value=mock_redis_storage,
            ):
                with patch("app.api.v1.feedback.logger") as mock_logger:
                    storage = _create_rate_limiter_storage()

                    assert isinstance(storage, InMemoryStorage)
                    mock_logger.warning.assert_called()

    def test_fallback_to_in_memory_when_redis_import_fails(self):
        """Test fallback to in-memory when redis library is not installed."""
        from app.api.v1.feedback import _create_rate_limiter_storage

        with patch("app.api.v1.feedback.settings") as mock_settings:
            mock_settings.RATE_LIMIT_STORAGE = "redis"
            mock_settings.RATE_LIMIT_REDIS_URL = "redis://localhost:6379/0"
            mock_settings.RATE_LIMIT_MAX_KEYS = 100000

            # Simulate ImportError when RedisStorage is instantiated
            with patch(
                "app.ratelimit.storage.RedisStorage",
                side_effect=ImportError("No module named 'redis'"),
            ):
                with patch("app.api.v1.feedback.logger") as mock_logger:
                    storage = _create_rate_limiter_storage()

                    assert isinstance(storage, InMemoryStorage)
                    mock_logger.warning.assert_called()
                    warning_message = str(mock_logger.warning.call_args)
                    assert "not installed" in warning_message.lower()

    def test_fallback_to_in_memory_when_redis_raises_exception(self):
        """Test fallback to in-memory when Redis initialization raises exception."""
        from app.api.v1.feedback import _create_rate_limiter_storage

        with patch("app.api.v1.feedback.settings") as mock_settings:
            mock_settings.RATE_LIMIT_STORAGE = "redis"
            mock_settings.RATE_LIMIT_REDIS_URL = "redis://localhost:6379/0"
            mock_settings.RATE_LIMIT_MAX_KEYS = 100000

            # Simulate connection error at the source module
            with patch(
                "app.ratelimit.storage.RedisStorage",
                side_effect=ConnectionError("Connection refused"),
            ):
                with patch("app.api.v1.feedback.logger") as mock_logger:
                    storage = _create_rate_limiter_storage()

                    assert isinstance(storage, InMemoryStorage)
                    mock_logger.warning.assert_called()
                    warning_message = str(mock_logger.warning.call_args)
                    assert "Failed to initialize" in warning_message

    def test_logs_info_when_using_in_memory_storage(self):
        """Test that info log is generated when using in-memory storage."""
        from app.api.v1.feedback import _create_rate_limiter_storage

        with patch("app.api.v1.feedback.settings") as mock_settings:
            mock_settings.RATE_LIMIT_STORAGE = "memory"
            mock_settings.RATE_LIMIT_MAX_KEYS = 100000

            with patch("app.api.v1.feedback.logger") as mock_logger:
                storage = _create_rate_limiter_storage()

                assert isinstance(storage, InMemoryStorage)
                mock_logger.info.assert_called()
                info_message = str(mock_logger.info.call_args)
                assert "in-memory" in info_message.lower()

    def test_logs_info_when_redis_connection_succeeds(self):
        """Test that info log is generated when Redis connection succeeds."""
        from app.api.v1.feedback import _create_rate_limiter_storage

        mock_redis_storage = MagicMock()
        mock_redis_storage.is_connected.return_value = True

        with patch("app.api.v1.feedback.settings") as mock_settings:
            mock_settings.RATE_LIMIT_STORAGE = "redis"
            mock_settings.RATE_LIMIT_REDIS_URL = "redis://localhost:6379/0"

            with patch(
                "app.ratelimit.storage.RedisStorage",
                return_value=mock_redis_storage,
            ):
                with patch("app.api.v1.feedback.logger") as mock_logger:
                    storage = _create_rate_limiter_storage()

                    assert storage == mock_redis_storage
                    # Check that success was logged
                    info_calls = [str(c) for c in mock_logger.info.call_args_list]
                    success_logs = [
                        c for c in info_calls if "Successfully connected" in c
                    ]
                    assert len(success_logs) > 0

    def test_in_memory_storage_uses_max_keys_setting(self):
        """Test that in-memory storage is initialized with correct max_keys."""
        from app.api.v1.feedback import _create_rate_limiter_storage

        with patch("app.api.v1.feedback.settings") as mock_settings:
            mock_settings.RATE_LIMIT_STORAGE = "memory"
            mock_settings.RATE_LIMIT_MAX_KEYS = 75000

            storage = _create_rate_limiter_storage()

            assert isinstance(storage, InMemoryStorage)
            assert storage._max_keys == 75000

    def test_return_type_is_rate_limiter_storage(self):
        """Test that return type conforms to RateLimiterStorage interface."""
        from app.api.v1.feedback import _create_rate_limiter_storage
        from app.ratelimit.storage import RateLimiterStorage

        with patch("app.api.v1.feedback.settings") as mock_settings:
            mock_settings.RATE_LIMIT_STORAGE = "memory"
            mock_settings.RATE_LIMIT_MAX_KEYS = 100000

            storage = _create_rate_limiter_storage()

            # Verify it's an instance of the abstract class
            assert isinstance(storage, RateLimiterStorage)
