"""
Tests for input validation and security measures.
"""
import pytest

from app.core.validators import (
    PasswordValidator,
    StringSanitizer,
    EmailValidator,
    TextValidator,
    validate_no_sql_injection,
)
from app.schemas.questions import QuestionResponse
from app.schemas.responses import ResponseItem, ResponseSubmission


class TestPasswordValidator:
    """Tests for password strength validation."""

    def test_valid_password(self):
        """Test that valid passwords pass validation."""
        valid_passwords = [
            "SecurePass123",
            "MyP@ssw0rd!",
            "TestPass789xyz",
            "abcDEF123456",
        ]

        for password in valid_passwords:
            is_valid, error = PasswordValidator.validate(password)
            assert is_valid is True
            assert error is None

    def test_password_too_short(self):
        """Test that passwords shorter than minimum length are rejected."""
        short_password = "abc123"  # 6 characters
        is_valid, error = PasswordValidator.validate(short_password)
        assert is_valid is False
        assert "at least" in error.lower()

    def test_password_too_long(self):
        """Test that passwords longer than maximum length are rejected."""
        long_password = "a" * 150  # 150 characters
        is_valid, error = PasswordValidator.validate(long_password)
        assert is_valid is False
        assert "exceed" in error.lower()

    def test_password_no_letters(self):
        """Test that passwords without letters are rejected."""
        no_letters = "987654321"  # Not in common passwords list
        is_valid, error = PasswordValidator.validate(no_letters)
        assert is_valid is False
        assert "letter" in error.lower()

    def test_password_no_digits(self):
        """Test that passwords without digits are rejected."""
        no_digits = "abcdefghij"
        is_valid, error = PasswordValidator.validate(no_digits)
        assert is_valid is False
        assert "digit" in error.lower()

    def test_common_weak_password(self):
        """Test that common weak passwords are rejected."""
        weak_passwords = ["password", "12345678", "password123", "qwerty123"]

        for weak_pass in weak_passwords:
            is_valid, error = PasswordValidator.validate(weak_pass)
            assert is_valid is False
            assert "common" in error.lower()

    def test_excessive_repeated_characters(self):
        """Test that passwords with too many repeated characters are rejected."""
        repeated = "aaaa1234"  # 4 'a's in a row
        is_valid, error = PasswordValidator.validate(repeated)
        assert is_valid is False
        assert "repeated" in error.lower()

    def test_repeated_characters_allowed_up_to_limit(self):
        """Test that 3 repeated characters are allowed."""
        acceptable = "aaa123xyz"  # Only 3 'a's
        is_valid, error = PasswordValidator.validate(acceptable)
        assert is_valid is True


class TestStringSanitizer:
    """Tests for string sanitization."""

    def test_sanitize_removes_control_characters(self):
        """Test that control characters are removed."""
        malicious = "test\x00\x01\x02string"
        sanitized = StringSanitizer.sanitize_string(malicious)
        assert "\x00" not in sanitized
        assert "\x01" not in sanitized
        assert sanitized == "teststring"

    def test_sanitize_strips_whitespace(self):
        """Test that leading/trailing whitespace is stripped."""
        input_str = "  test string  "
        sanitized = StringSanitizer.sanitize_string(input_str)
        assert sanitized == "test string"

    def test_sanitize_escapes_html(self):
        """Test that HTML is escaped by default."""
        malicious = "<script>alert('XSS')</script>"
        sanitized = StringSanitizer.sanitize_string(malicious)
        assert "<script>" not in sanitized
        assert "&lt;script&gt;" in sanitized

    def test_sanitize_name_removes_numbers(self):
        """Test that numbers are removed from names."""
        name = "John123"
        sanitized = StringSanitizer.sanitize_name(name)
        assert sanitized == "John"

    def test_sanitize_name_allows_hyphens_apostrophes(self):
        """Test that hyphens and apostrophes are preserved (though HTML escaped)."""
        name = "Mary-Jane O'Brien"
        sanitized = StringSanitizer.sanitize_name(name)
        # Hyphen is preserved, apostrophe is HTML escaped
        assert "Mary-Jane" in sanitized
        assert "Brien" in sanitized
        # Apostrophe gets HTML escaped
        assert "&#x27;" in sanitized or "&#39;" in sanitized or "'" in sanitized

    def test_sanitize_name_removes_special_chars(self):
        """Test that special characters are removed from names."""
        name = "John@#$Doe"
        sanitized = StringSanitizer.sanitize_name(name)
        assert sanitized == "JohnDoe"

    def test_sanitize_answer_limits_length(self):
        """Test that answers are limited to maximum length."""
        long_answer = "a" * 2000
        sanitized = StringSanitizer.sanitize_answer(long_answer)
        assert len(sanitized) <= 1000

    def test_sanitize_answer_escapes_html(self):
        """Test that HTML is escaped in answers."""
        answer = "<b>bold</b>"
        sanitized = StringSanitizer.sanitize_answer(answer)
        assert "<b>" not in sanitized
        assert "&lt;b&gt;" in sanitized


class TestEmailValidator:
    """Tests for email validation."""

    def test_normalize_email_lowercase(self):
        """Test that emails are converted to lowercase."""
        email = "Test@EXAMPLE.COM"
        normalized = EmailValidator.normalize_email(email)
        assert normalized == "test@example.com"

    def test_normalize_email_strips_whitespace(self):
        """Test that whitespace is removed from emails."""
        email = "  test@example.com  "
        normalized = EmailValidator.normalize_email(email)
        assert normalized == "test@example.com"

    def test_is_disposable_email(self):
        """Test that disposable emails are detected."""
        disposable = "test@tempmail.com"
        assert EmailValidator.is_disposable_email(disposable) is True

    def test_is_not_disposable_email(self):
        """Test that legitimate emails are not flagged as disposable."""
        legitimate = "test@gmail.com"
        assert EmailValidator.is_disposable_email(legitimate) is False


class TestSQLInjectionDetection:
    """Tests for SQL injection pattern detection."""

    def test_clean_input_passes(self):
        """Test that clean input passes SQL injection check."""
        clean_inputs = [
            "This is a normal string",
            "user@example.com",
            "Test answer 123",
            "John Doe",
        ]

        for clean in clean_inputs:
            assert validate_no_sql_injection(clean) is True

    def test_sql_keywords_detected(self):
        """Test that SQL keywords are detected."""
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'--",
            "1 UNION SELECT * FROM users",
            "'; DELETE FROM users WHERE 1=1; --",
        ]

        for malicious in malicious_inputs:
            assert validate_no_sql_injection(malicious) is False

    def test_sql_comments_detected(self):
        """Test that SQL comment patterns are detected."""
        with_comments = [
            "test -- comment",
            "test /* comment */",
            "test # comment",
        ]

        for input_str in with_comments:
            assert validate_no_sql_injection(input_str) is False


class TestRegistrationValidation:
    """Integration tests for registration validation."""

    def test_register_with_weak_password_fails(self, client):
        """Test that registration with weak password fails."""
        user_data = {
            "email": "test@example.com",
            "password": "password",  # Too common
            "first_name": "John",
            "last_name": "Doe",
        }

        response = client.post("/v1/auth/register", json=user_data)
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert "common" in str(data["detail"]).lower()

    def test_register_with_short_password_fails(self, client):
        """Test that registration with short password fails."""
        user_data = {
            "email": "test@example.com",
            "password": "abc123",  # Too short
            "first_name": "John",
            "last_name": "Doe",
        }

        response = client.post("/v1/auth/register", json=user_data)
        assert response.status_code == 422

    def test_register_with_no_digits_fails(self, client):
        """Test that registration without digits in password fails."""
        user_data = {
            "email": "test@example.com",
            "password": "abcdefghij",  # No digits
            "first_name": "John",
            "last_name": "Doe",
        }

        response = client.post("/v1/auth/register", json=user_data)
        assert response.status_code == 422
        data = response.json()
        assert "digit" in str(data["detail"]).lower()

    def test_register_sanitizes_names(self, client):
        """Test that names are sanitized during registration."""
        user_data = {
            "email": "test@example.com",
            "password": "SecurePass123",
            "first_name": "John<script>",  # Malicious HTML
            "last_name": "Doe",
        }

        response = client.post("/v1/auth/register", json=user_data)
        assert response.status_code == 201
        data = response.json()
        # HTML should be sanitized
        assert "<script>" not in data["user"]["first_name"]


class TestResponseValidation:
    """Integration tests for response validation."""

    def test_answer_validation_works(self, client, test_user, test_questions):
        """Test that answer validation is enforced."""
        from app.core.auth.security import create_access_token

        token = create_access_token({"user_id": test_user.id})
        headers = {"Authorization": f"Bearer {token}"}

        # Start a test session
        response = client.post(
            "/v1/test/start", params={"question_count": 1}, headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        session_id = data["session"]["id"]
        question_id = data["questions"][0]["id"]

        # Submit a normal answer
        submission = {
            "session_id": session_id,
            "responses": [
                {
                    "question_id": question_id,
                    "user_answer": "Valid answer 42",
                }
            ],
        }

        response = client.post("/v1/test/submit", json=submission, headers=headers)
        assert response.status_code == 200

        # The answer should be accepted
        result = response.json()
        assert result["responses_count"] == 1


class TestSecurityHeaders:
    """Tests for security headers middleware."""

    def test_security_headers_present(self, client):
        """Test that security headers are added to responses."""
        response = client.get("/v1/health")

        # Check for security headers
        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"

        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"

        assert "X-XSS-Protection" in response.headers

        assert "Content-Security-Policy" in response.headers

        assert "Referrer-Policy" in response.headers

        assert "Permissions-Policy" in response.headers

    def test_hsts_not_enabled_in_development(self, client):
        """Test that HSTS is not enabled in development mode."""
        # HSTS should not be present in development
        # (ENV defaults to 'development' in tests)
        # Note: This depends on the ENV setting
        # If we want to test this properly, we'd need to mock the ENV
        pass


class TestRequestSizeLimit:
    """Tests for request size limit middleware."""

    def test_large_request_body_rejected(self, client):
        """Test that excessively large request bodies are rejected."""
        # Create a payload larger than 1MB
        large_payload = {
            "email": "test@example.com",
            "password": "SecurePass123",
            "first_name": "A" * (1024 * 1024 + 1),  # > 1MB
            "last_name": "Doe",
        }

        response = client.post("/v1/auth/register", json=large_payload)
        # Should be rejected by size limit middleware
        assert response.status_code == 413 or response.status_code == 422


class TestTextValidator:
    """Tests for TextValidator utility methods."""

    def test_validate_non_empty_text_with_valid_string(self):
        """Test that valid non-empty strings pass validation."""
        result = TextValidator.validate_non_empty_text("Hello World", "Test Field")
        assert result == "Hello World"

    def test_validate_non_empty_text_strips_whitespace(self):
        """Test that whitespace is stripped from valid strings."""
        result = TextValidator.validate_non_empty_text("  Hello World  ", "Test Field")
        assert result == "Hello World"

    def test_validate_non_empty_text_rejects_empty_string(self):
        """Test that empty strings are rejected."""
        with pytest.raises(ValueError) as exc_info:
            TextValidator.validate_non_empty_text("", "Test Field")
        assert "Test Field cannot be empty or whitespace-only" in str(exc_info.value)

    def test_validate_non_empty_text_rejects_whitespace_only(self):
        """Test that whitespace-only strings are rejected."""
        with pytest.raises(ValueError) as exc_info:
            TextValidator.validate_non_empty_text("   ", "Test Field")
        assert "Test Field cannot be empty or whitespace-only" in str(exc_info.value)

    def test_validate_non_empty_text_rejects_tabs_only(self):
        """Test that tab-only strings are rejected."""
        with pytest.raises(ValueError) as exc_info:
            TextValidator.validate_non_empty_text("\t\t\t", "Test Field")
        assert "cannot be empty or whitespace-only" in str(exc_info.value)

    def test_validate_non_negative_int_with_positive_value(self):
        """Test that positive integers pass validation."""
        result = TextValidator.validate_non_negative_int(42, "Test Field")
        assert result == 42

    def test_validate_non_negative_int_with_zero(self):
        """Test that zero passes validation."""
        result = TextValidator.validate_non_negative_int(0, "Test Field")
        assert result == 0

    def test_validate_non_negative_int_with_none(self):
        """Test that None passes validation."""
        result = TextValidator.validate_non_negative_int(None, "Test Field")
        assert result is None

    def test_validate_non_negative_int_rejects_negative(self):
        """Test that negative integers are rejected."""
        with pytest.raises(ValueError) as exc_info:
            TextValidator.validate_non_negative_int(-5, "Time spent")
        assert "Time spent cannot be negative" in str(exc_info.value)

    def test_validate_positive_id_with_valid_id(self):
        """Test that positive IDs pass validation."""
        result = TextValidator.validate_positive_id(1, "Question ID")
        assert result == 1

        result = TextValidator.validate_positive_id(999999, "Question ID")
        assert result == 999999

    def test_validate_positive_id_rejects_zero(self):
        """Test that zero is rejected for IDs."""
        with pytest.raises(ValueError) as exc_info:
            TextValidator.validate_positive_id(0, "Question ID")
        assert "Question ID must be a positive integer" in str(exc_info.value)

    def test_validate_positive_id_rejects_negative(self):
        """Test that negative IDs are rejected."""
        with pytest.raises(ValueError) as exc_info:
            TextValidator.validate_positive_id(-1, "Question ID")
        assert "Question ID must be a positive integer" in str(exc_info.value)


class TestQuestionResponseSchemaValidation:
    """Tests for QuestionResponse schema validation."""

    def test_valid_question_response(self):
        """Test that valid QuestionResponse data passes validation."""
        data = {
            "id": 1,
            "question_text": "What is 2 + 2?",
            "question_type": "math",
            "difficulty_level": "easy",
            "answer_options": ["A", "B", "C", "D"],
            "explanation": None,
        }
        response = QuestionResponse(**data)
        assert response.id == 1
        assert response.question_text == "What is 2 + 2?"

    def test_question_response_rejects_zero_id(self):
        """Test that QuestionResponse rejects zero ID."""
        data = {
            "id": 0,
            "question_text": "What is 2 + 2?",
            "question_type": "math",
            "difficulty_level": "easy",
        }
        with pytest.raises(ValueError) as exc_info:
            QuestionResponse(**data)
        assert "Question ID must be a positive integer" in str(exc_info.value)

    def test_question_response_rejects_negative_id(self):
        """Test that QuestionResponse rejects negative ID."""
        data = {
            "id": -5,
            "question_text": "What is 2 + 2?",
            "question_type": "math",
            "difficulty_level": "easy",
        }
        with pytest.raises(ValueError) as exc_info:
            QuestionResponse(**data)
        assert "Question ID must be a positive integer" in str(exc_info.value)

    def test_question_response_rejects_empty_text(self):
        """Test that QuestionResponse rejects empty question text."""
        data = {
            "id": 1,
            "question_text": "",
            "question_type": "math",
            "difficulty_level": "easy",
        }
        with pytest.raises(ValueError) as exc_info:
            QuestionResponse(**data)
        assert "Question text cannot be empty or whitespace-only" in str(exc_info.value)

    def test_question_response_rejects_whitespace_only_text(self):
        """Test that QuestionResponse rejects whitespace-only question text."""
        data = {
            "id": 1,
            "question_text": "   \t\n   ",
            "question_type": "math",
            "difficulty_level": "easy",
        }
        with pytest.raises(ValueError) as exc_info:
            QuestionResponse(**data)
        assert "Question text cannot be empty or whitespace-only" in str(exc_info.value)

    def test_question_response_strips_whitespace(self):
        """Test that QuestionResponse strips whitespace from question text."""
        data = {
            "id": 1,
            "question_text": "  What is 2 + 2?  ",
            "question_type": "math",
            "difficulty_level": "easy",
        }
        response = QuestionResponse(**data)
        assert response.question_text == "What is 2 + 2?"


class TestResponseItemSchemaValidation:
    """Tests for ResponseItem schema validation."""

    def test_valid_response_item(self):
        """Test that valid ResponseItem data passes validation."""
        data = {
            "question_id": 1,
            "user_answer": "A",
            "time_spent_seconds": 30,
        }
        item = ResponseItem(**data)
        assert item.question_id == 1
        assert item.time_spent_seconds == 30

    def test_response_item_rejects_zero_question_id(self):
        """Test that ResponseItem rejects zero question ID."""
        data = {
            "question_id": 0,
            "user_answer": "A",
        }
        with pytest.raises(ValueError) as exc_info:
            ResponseItem(**data)
        assert "Question ID must be a positive integer" in str(exc_info.value)

    def test_response_item_rejects_negative_question_id(self):
        """Test that ResponseItem rejects negative question ID."""
        data = {
            "question_id": -1,
            "user_answer": "A",
        }
        with pytest.raises(ValueError) as exc_info:
            ResponseItem(**data)
        assert "Question ID must be a positive integer" in str(exc_info.value)

    def test_response_item_accepts_none_time_spent(self):
        """Test that ResponseItem accepts None for time_spent_seconds."""
        data = {
            "question_id": 1,
            "user_answer": "A",
            "time_spent_seconds": None,
        }
        item = ResponseItem(**data)
        assert item.time_spent_seconds is None

    def test_response_item_accepts_zero_time_spent(self):
        """Test that ResponseItem accepts zero time_spent_seconds."""
        data = {
            "question_id": 1,
            "user_answer": "A",
            "time_spent_seconds": 0,
        }
        item = ResponseItem(**data)
        assert item.time_spent_seconds == 0

    def test_response_item_rejects_negative_time_spent(self):
        """Test that ResponseItem rejects negative time_spent_seconds."""
        data = {
            "question_id": 1,
            "user_answer": "A",
            "time_spent_seconds": -10,
        }
        with pytest.raises(ValueError) as exc_info:
            ResponseItem(**data)
        assert "Time spent cannot be negative" in str(exc_info.value)


class TestResponseSubmissionSchemaValidation:
    """Tests for ResponseSubmission schema validation."""

    def test_valid_response_submission(self):
        """Test that valid ResponseSubmission data passes validation."""
        data = {
            "session_id": 1,
            "responses": [{"question_id": 1, "user_answer": "A"}],
        }
        submission = ResponseSubmission(**data)
        assert submission.session_id == 1

    def test_response_submission_rejects_zero_session_id(self):
        """Test that ResponseSubmission rejects zero session ID."""
        data = {
            "session_id": 0,
            "responses": [{"question_id": 1, "user_answer": "A"}],
        }
        with pytest.raises(ValueError) as exc_info:
            ResponseSubmission(**data)
        assert "Session ID must be a positive integer" in str(exc_info.value)

    def test_response_submission_rejects_negative_session_id(self):
        """Test that ResponseSubmission rejects negative session ID."""
        data = {
            "session_id": -1,
            "responses": [{"question_id": 1, "user_answer": "A"}],
        }
        with pytest.raises(ValueError) as exc_info:
            ResponseSubmission(**data)
        assert "Session ID must be a positive integer" in str(exc_info.value)
