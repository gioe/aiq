#!/usr/bin/env python3
"""Pre-commit hook to detect direct float comparisons in test files.

This script finds assert statements that compare values directly to float literals
without using pytest.approx(). Direct float comparisons can cause flaky tests due
to floating-point precision issues.

Examples of patterns detected:
    assert result == 0.5          # FLAGGED - missing pytest.approx()
    assert data["value"] == 1.23  # FLAGGED - missing pytest.approx()

Examples of acceptable patterns:
    assert result == pytest.approx(0.5)      # OK - uses pytest.approx()
    assert result == pytest.approx(0.5, rel=1e-3)  # OK - uses pytest.approx()
    assert count == 5                        # OK - integer comparison
    assert flag is True                      # OK - not a numeric comparison

Usage:
    python .pre-commit-hooks/check_float_comparisons.py [files...]

    If no files are provided, checks all test_*.py files in the repository.
"""

import re
import sys
from pathlib import Path
from typing import Optional


# Pattern to detect: assert <expression> == <float_literal>
# This catches patterns like:
#   assert result == 0.5
#   assert data["key"] == 1.23
#   assert obj.attr == 99.9
#
# The float literal pattern matches: digits, decimal point, more digits
# Optionally followed by exponent notation (e.g., 1.5e-3)
FLOAT_LITERAL_PATTERN = r"\d+\.\d+(?:[eE][+-]?\d+)?"

# Full pattern for assert equality with float literal
# Captures the full assert statement for reporting
FLOAT_COMPARISON_PATTERN = re.compile(
    rf"assert\s+.+\s*==\s*({FLOAT_LITERAL_PATTERN})(?!\s*,|\s*\))",
    re.MULTILINE,
)

# Pattern to check if pytest.approx is used in the same line
APPROX_PATTERN = re.compile(r"pytest\.approx\s*\(")


def check_line(line: str, line_number: int, file_path: Path) -> Optional[str]:
    """Check a single line for direct float comparison.

    Args:
        line: The line content to check.
        line_number: 1-indexed line number.
        file_path: Path to the file being checked.

    Returns:
        Error message if issue found, None otherwise.
    """
    # Skip if line already uses pytest.approx
    if APPROX_PATTERN.search(line):
        return None

    # Skip if line is a comment
    stripped = line.strip()
    if stripped.startswith("#"):
        return None

    # Check for direct float comparison
    match = FLOAT_COMPARISON_PATTERN.search(line)
    if match:
        float_value = match.group(1)
        return (
            f"{file_path}:{line_number}: Direct float comparison found "
            f"(== {float_value}). Use pytest.approx({float_value}) instead."
        )

    return None


def check_file(file_path: Path) -> list[str]:
    """Check a file for direct float comparisons.

    Args:
        file_path: Path to the test file to check.

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


def find_test_files(paths: list[str]) -> list[Path]:
    """Find test files to check.

    Args:
        paths: List of file paths or directories to check.
                If empty, searches for all test_*.py files.

    Returns:
        List of Path objects for test files to check.
    """
    if paths:
        # Check only the specified files
        test_files = []
        for path_str in paths:
            path = Path(path_str)
            if path.is_file() and path.name.startswith("test_") and path.suffix == ".py":
                test_files.append(path)
        return test_files

    # No files specified - find all test files
    return list(Path(".").rglob("test_*.py"))


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

    test_files = find_test_files(args)

    if not test_files:
        # No test files to check
        return 0

    all_issues: list[str] = []

    for file_path in test_files:
        issues = check_file(file_path)
        all_issues.extend(issues)

    if all_issues:
        print("Float comparison issues found:")
        print()
        for issue in all_issues:
            print(f"  {issue}")
        print()
        print(
            "Hint: Replace direct float comparisons with pytest.approx() to avoid "
            "flaky tests due to floating-point precision issues."
        )
        print()
        print("Example fix:")
        print("  # Before:")
        print('  assert result["value"] == 0.5')
        print()
        print("  # After:")
        print('  assert result["value"] == pytest.approx(0.5)')
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
