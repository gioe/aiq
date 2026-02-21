"""
Input validation and sanitization utilities.
"""

import re
import html
from typing import Optional


class PasswordValidator:
    """
    Password strength validator following OWASP guidelines.
    """

    MIN_LENGTH = 8
    MAX_LENGTH = 128

    # Common weak passwords to reject
    COMMON_PASSWORDS = {
        "password",
        "12345678",
        "password123",
        "qwerty123",
        "abc123456",
        "password1",
        "welcome123",
        "admin123",
        "letmein",
    }

    @classmethod
    def validate(cls, password: str) -> tuple[bool, Optional[str]]:
        """
        Validate password strength.

        Args:
            password: Password to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check length
        if len(password) < cls.MIN_LENGTH:
            return False, f"Password must be at least {cls.MIN_LENGTH} characters long"

        if len(password) > cls.MAX_LENGTH:
            return False, f"Password must not exceed {cls.MAX_LENGTH} characters"

        # Check for common weak passwords
        if password.lower() in cls.COMMON_PASSWORDS:
            return False, "Password is too common. Please choose a stronger password"

        # Check for at least one letter
        if not re.search(r"[a-zA-Z]", password):
            return False, "Password must contain at least one letter"

        # Check for at least one digit
        if not re.search(r"\d", password):
            return False, "Password must contain at least one digit"

        # Check for excessive repeated characters (4+ in a row)
        # This catches patterns like "aaaa" or "1111" which are weak
        if re.search(r"(.)\1{3,}", password):
            return False, "Password contains too many repeated characters"

        return True, None


class StringSanitizer:
    """
    String sanitization utilities for preventing XSS and injection attacks.
    """

    # Control characters to strip (except newlines, tabs, carriage returns)
    CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")

    # HTML entities pattern for detection
    HTML_ENTITIES_PATTERN = re.compile(r"&[a-zA-Z0-9#]+;")

    @classmethod
    def _base_sanitize(cls, value: str, escape_html: bool = True) -> str:
        """
        Base sanitization function with common steps shared by all sanitizers.

        Performs the following operations:
        1. Strips control characters (except newlines, tabs, carriage returns)
        2. Strips leading/trailing whitespace
        3. Optionally escapes HTML entities

        Args:
            value: String to sanitize
            escape_html: Whether to escape HTML entities (default: True)

        Returns:
            Sanitized string with common steps applied
        """
        # Strip control characters
        value = cls.CONTROL_CHARS_PATTERN.sub("", value)

        # Strip leading/trailing whitespace
        value = value.strip()

        # Escape HTML entities if requested
        if escape_html:
            value = html.escape(value)

        return value

    @classmethod
    def sanitize_string(cls, value: str, allow_html: bool = False) -> str:
        """
        Sanitize string input to prevent XSS attacks.

        Args:
            value: String to sanitize
            allow_html: Whether to allow HTML entities (default: False)

        Returns:
            Sanitized string
        """
        return cls._base_sanitize(value, escape_html=not allow_html)

    @classmethod
    def sanitize_name(cls, name: str) -> str:
        """
        Sanitize name fields (first_name, last_name).

        Args:
            name: Name to sanitize

        Returns:
            Sanitized name
        """
        # Apply base sanitization without HTML escaping (we'll escape after filtering)
        name = cls._base_sanitize(name, escape_html=False)

        # Allow only letters, spaces, hyphens, and apostrophes
        # This covers most names while preventing code injection
        name = re.sub(r"[^a-zA-ZÀ-ÿ\s\-']", "", name)

        # Remove multiple spaces
        name = re.sub(r"\s+", " ", name)

        # Escape HTML just in case
        name = html.escape(name)

        return name

    @classmethod
    def sanitize_answer(cls, answer: str) -> str:
        """
        Sanitize user answer input for test questions.

        Args:
            answer: User's answer

        Returns:
            Sanitized answer
        """
        # Apply base sanitization without HTML escaping (we'll escape after truncating)
        answer = cls._base_sanitize(answer, escape_html=False)

        # Limit length to prevent abuse
        max_length = 1000
        if len(answer) > max_length:
            answer = answer[:max_length]

        # Escape HTML entities
        answer = html.escape(answer)

        return answer


class EmailValidator:
    """
    Email validation and normalization utilities.
    """

    # Disposable email domains to block (subset for demonstration)
    DISPOSABLE_DOMAINS = {
        "tempmail.com",
        "throwaway.email",
        "guerrillamail.com",
        "mailinator.com",
        "10minutemail.com",
        "fakeinbox.com",
        "trashmail.com",
    }

    @classmethod
    def normalize_email(cls, email: str) -> str:
        """
        Normalize email address for consistency.

        Args:
            email: Email address to normalize

        Returns:
            Normalized email address
        """
        # Convert to lowercase
        email = email.lower().strip()

        # Remove any whitespace
        email = email.replace(" ", "")

        return email

    @classmethod
    def is_disposable_email(cls, email: str) -> bool:
        """
        Check if email is from a disposable email provider.

        Args:
            email: Email address to check

        Returns:
            True if disposable, False otherwise
        """
        domain = email.split("@")[-1].lower()
        return domain in cls.DISPOSABLE_DOMAINS


class IntegerValidator:
    """
    Integer validation utilities with bounds checking.
    """

    @staticmethod
    def validate_positive_int(
        value: int, max_value: Optional[int] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Validate that integer is positive and within bounds.

        Args:
            value: Integer to validate
            max_value: Optional maximum value

        Returns:
            Tuple of (is_valid, error_message)
        """
        if value < 1:
            return False, "Value must be a positive integer"

        if max_value is not None and value > max_value:
            return False, f"Value must not exceed {max_value}"

        return True, None


class TextValidator:
    """
    Text validation utilities for schema field validation.
    """

    @staticmethod
    def validate_non_empty_text(value: str, field_name: str = "Text") -> str:
        """
        Validate that text is not empty or whitespace-only.

        Args:
            value: Text to validate
            field_name: Name of the field for error messages

        Returns:
            The stripped value if valid

        Raises:
            ValueError: If the text is empty or whitespace-only
        """
        stripped = value.strip()
        if not stripped:
            raise ValueError(f"{field_name} cannot be empty or whitespace-only")
        return stripped

    @staticmethod
    def validate_non_negative_int(
        value: Optional[int], field_name: str = "Value"
    ) -> Optional[int]:
        """
        Validate that an optional integer is non-negative.

        Args:
            value: Integer to validate (can be None)
            field_name: Name of the field for error messages

        Returns:
            The value if valid (including None)

        Raises:
            ValueError: If the value is negative
        """
        if value is not None and value < 0:
            raise ValueError(f"{field_name} cannot be negative")
        return value

    @staticmethod
    def validate_positive_id(value: int, field_name: str = "ID") -> int:
        """
        Validate that an ID is a positive integer.

        Args:
            value: ID to validate
            field_name: Name of the field for error messages

        Returns:
            The value if valid

        Raises:
            ValueError: If the ID is not positive
        """
        if value <= 0:
            raise ValueError(f"{field_name} must be a positive integer")
        return value


def validate_no_sql_injection(value: str) -> bool:
    """
    Basic SQL injection pattern detection.

    Note: This is a defense-in-depth measure. The primary protection
    against SQL injection is the use of parameterized queries via SQLAlchemy ORM.

    Args:
        value: String to check for SQL injection patterns

    Returns:
        True if safe, False if suspicious patterns detected
    """
    # Common SQL injection patterns
    sql_patterns = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE)\b)",
        r"(--|\#|\/\*|\*\/)",  # SQL comments
        r"(\bOR\b.*[\'\"]\s*\d+\s*[\'\"]\s*=\s*[\'\"]\s*\d+)",  # OR '1'='1' patterns
        r"(\bAND\b.*[\'\"]\s*\d+\s*[\'\"]\s*=\s*[\'\"]\s*\d+)",  # AND '1'='1' patterns
        r"(\bUNION\b.*\bSELECT\b)",
        r"(;.*\b(SELECT|INSERT|UPDATE|DELETE|DROP)\b)",
        r"(\'\s*OR\s*[\'\"])",  # ' OR ' or ' OR "
    ]

    for pattern in sql_patterns:
        if re.search(pattern, value, re.IGNORECASE):
            return False

    return True
