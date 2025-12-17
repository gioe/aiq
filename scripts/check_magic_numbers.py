#!/usr/bin/env python3
"""Pre-commit hook to detect magic numbers in Python files.

This script finds numeric literals used in comparisons that should be extracted
to named constants for better maintainability and readability.

Examples of patterns detected:
    if count >= 50:           # FLAGGED - 50 should be a constant
    if score < 0.7:           # FLAGGED - 0.7 should be a constant
    while retries <= 3:       # FLAGGED - 3 should be a constant

Examples of acceptable patterns:
    if count >= MIN_COUNT:    # OK - uses named constant
    if index == 0:            # OK - 0 is commonly acceptable
    if len(items) > 1:        # OK - 1 is commonly acceptable
    result[0]                 # OK - array index
    x * 100                   # OK - percentage conversion
    x / 2                     # OK - common math operation

Usage:
    python scripts/check_magic_numbers.py [files...]

    If no files are provided, checks all non-test .py files in backend/app
    and question-service/app directories.
"""

import re
import sys
from pathlib import Path
from typing import Optional


# Numbers that are commonly acceptable and not flagged
# These are used in idioms like "if not items" → "if len(items) == 0"
# or simple binary checks, percentage conversions, etc.
ACCEPTABLE_NUMBERS = frozenset({
    # Zero and one - common in boolean-like checks
    "0", "0.0", "1", "1.0", "-1", "-1.0",
    # Common percentage/scaling bases
    "100", "100.0", "1000",
    # Common powers of 2 (often used in computing)
    "2", "4", "8", "16", "32", "64", "128", "256", "512", "1024",
    # HTTP status code boundaries (well-known conventions)
    "200", "400", "500",
})

# Comparison operators to check for
COMPARISON_OPS = r"(?:==|!=|>=|<=|>|<)"

# Pattern for numeric literals (integers and floats, with optional negative sign)
# Matches: 50, 0.7, -3, 1.5e-3, etc.
NUMBER_PATTERN = r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?"

# Full pattern for comparisons with numeric literals
# Captures lines like: if count >= 50:  or  elif score < 0.7:  or  and x > 10:
MAGIC_NUMBER_PATTERN = re.compile(
    rf"(?:if|elif|while|and|or)\s+.*?\s*{COMPARISON_OPS}\s*({NUMBER_PATTERN})\b",
    re.MULTILINE,
)

# Pattern to detect if line is assignment to a constant (SCREAMING_SNAKE_CASE)
CONSTANT_ASSIGNMENT_PATTERN = re.compile(r"^\s*[A-Z][A-Z0-9_]*\s*=")

# Pattern to detect if the number is used with a named constant comparison
# e.g., "if count >= MIN_COUNT" - the constant name suggests it's intentional
NAMED_CONSTANT_PATTERN = re.compile(r"[A-Z][A-Z0-9_]+\s*" + COMPARISON_OPS)


def is_in_comment_or_string(line: str, match_start: int) -> bool:
    """Check if a match position is inside a comment or string literal.

    Args:
        line: The full line content.
        match_start: The position where the match starts.

    Returns:
        True if the position is inside a comment or string.
    """
    in_string = False
    string_char = None
    i = 0

    while i < len(line):
        char = line[i]

        # Handle escape sequences
        if char == "\\" and in_string and i + 1 < len(line):
            i += 2  # Skip escaped character
            continue

        # Handle string boundaries
        if char in ('"', "'"):
            # Check for triple quotes
            triple = line[i : i + 3]
            if triple in ('"""', "'''"):
                if not in_string:
                    in_string = True
                    string_char = triple
                    i += 3
                    continue
                elif string_char == triple:
                    in_string = False
                    string_char = None
                    i += 3
                    continue

            # Single quotes
            if not in_string:
                in_string = True
                string_char = char
            elif string_char == char:
                in_string = False
                string_char = None

        # Handle comments (only when not in string)
        elif char == "#" and not in_string:
            # Everything after # is a comment
            if match_start >= i:
                return True

        # Check if match_start is within a string
        if i == match_start and in_string:
            return True

        i += 1

    # If we reached match_start while in_string, it's in a string
    return in_string and match_start < len(line)


def check_line(line: str, line_number: int, file_path: Path) -> Optional[str]:
    """Check a single line for magic numbers in comparisons.

    Args:
        line: The line content to check.
        line_number: 1-indexed line number.
        file_path: Path to the file being checked.

    Returns:
        Error message if issue found, None otherwise.
    """
    stripped = line.strip()

    # Skip comment-only lines
    if stripped.startswith("#"):
        return None

    # Skip constant assignments (we're defining constants, not using magic numbers)
    if CONSTANT_ASSIGNMENT_PATTERN.match(stripped):
        return None

    # Skip docstrings
    if stripped.startswith('"""') or stripped.startswith("'''"):
        return None

    # Find magic number comparisons
    for match in MAGIC_NUMBER_PATTERN.finditer(line):
        number = match.group(1)

        # Skip if it's an acceptable number
        if number in ACCEPTABLE_NUMBERS:
            continue

        # Check if match is in a comment
        if is_in_comment_or_string(line, match.start()):
            continue

        # Check if there's already a named constant being compared
        # This catches cases like "count >= MIN_COUNT * 2" where a constant exists
        match_text = match.group(0)
        if NAMED_CONSTANT_PATTERN.search(match_text):
            continue

        return (
            f"{file_path}:{line_number}: Magic number {number} found in comparison. "
            f"Consider extracting to a named constant."
        )

    return None


def check_file(file_path: Path) -> list[str]:
    """Check a file for magic numbers.

    Args:
        file_path: Path to the Python file to check.

    Returns:
        List of error messages for issues found.
    """
    issues = []

    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return [f"{file_path}: Error reading file: {e}"]

    for line_number, line in enumerate(content.split("\n"), start=1):
        issue = check_line(line, line_number, file_path)
        if issue:
            issues.append(issue)

    return issues


def find_python_files(paths: list[str]) -> list[Path]:
    """Find Python files to check.

    Args:
        paths: List of file paths to check.
                If empty, searches for all non-test .py files in app directories.

    Returns:
        List of Path objects for Python files to check.
    """
    if paths:
        # Check only the specified files, excluding test files
        python_files = []
        for path_str in paths:
            path = Path(path_str)
            if path.is_file() and path.suffix == ".py":
                # Skip test files - magic numbers in tests are often acceptable
                if not path.name.startswith("test_"):
                    python_files.append(path)
        return python_files

    # No files specified - find all non-test Python files
    files = []
    for directory in ["backend/app", "question-service/app"]:
        dir_path = Path(directory)
        if dir_path.exists():
            for f in dir_path.rglob("*.py"):
                if not f.name.startswith("test_"):
                    files.append(f)
    return files


def main(args: Optional[list[str]] = None) -> int:
    """Main entry point for the pre-commit hook.

    Args:
        args: Command line arguments (file paths to check).
              If None, uses sys.argv[1:].

    Returns:
        Exit code: 0 if no issues, 1 if issues found.
    """
    if args is None:
        args = sys.argv[1:]

    python_files = find_python_files(args)

    if not python_files:
        # No Python files to check
        return 0

    all_issues: list[str] = []

    for file_path in python_files:
        issues = check_file(file_path)
        all_issues.extend(issues)

    if all_issues:
        print("Magic number issues found:")
        print()
        for issue in all_issues:
            print(f"  {issue}")
        print()
        print("Hint: Extract numeric literals to named constants for better")
        print("maintainability. Constants should use SCREAMING_SNAKE_CASE and")
        print("include a comment explaining the value's meaning or source.")
        print()
        print("Example fix:")
        print("  # Before:")
        print("  if response_count >= 50:")
        print()
        print("  # After:")
        print("  # Minimum responses for reliable discrimination estimates")
        print("  MIN_RESPONSES_FOR_DISCRIMINATION = 50")
        print()
        print("  if response_count >= MIN_RESPONSES_FOR_DISCRIMINATION:")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
