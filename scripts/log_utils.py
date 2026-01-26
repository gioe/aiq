#!/usr/bin/env python3
"""Utilities for parsing and extracting information from log files."""

import re
from pathlib import Path

# Maximum lines to include as context after an error line
MAX_ERROR_CONTEXT_LINES = 20

# Pattern to detect exception lines (e.g., "ValueError: bad input")
EXCEPTION_LINE_PATTERN = re.compile(r"^\w+(?:Error|Exception):")


def extract_last_error(
    log_path: str | Path,
    max_lines: int = 10,
    include_traceback: bool = True,
) -> str | None:
    """Extract the last error(s) from a log file.

    Scans a log file for ERROR lines and Python tracebacks, returning the last
    few errors found. Useful for surfacing actual failure reasons from bootstrap
    or generation logs.

    Args:
        log_path: Path to the log file to parse.
        max_lines: Maximum number of ERROR lines to return (default: 10).
        include_traceback: If True, include full tracebacks with ERROR lines.

    Returns:
        A string containing the last errors found, or None if no errors.

    Example:
        >>> errors = extract_last_error("logs/bootstrap_20260125.log")
        >>> if errors:
        ...     print("Found errors:", errors)
    """
    log_path = Path(log_path)

    if not log_path.exists():
        return None

    if not log_path.is_file():
        return None

    # Pattern to match ERROR lines in Python logging format
    # Example: 2026-01-25 14:37:06,314 - logger - ERROR - module:func:line - message
    # Also handles ANSI color codes like \x1b[31mERROR\x1b[0m
    # The ANSI pattern is: ESC [ <params> m where ESC is \x1b
    ansi_code = r"(?:\x1b\[[0-9;]*m)?"
    error_pattern = re.compile(
        r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d+\s+-\s+[\w.]+"
        rf"\s+-\s+{ansi_code}ERROR{ansi_code}\s+-",
        re.IGNORECASE,
    )

    # Pattern to detect start of a traceback
    traceback_start_pattern = re.compile(r"^Traceback \(most recent call last\):")

    # Pattern to detect traceback continuation lines (indented with spaces or
    # lines starting with common traceback elements)
    traceback_continuation_pattern = re.compile(
        r"^(?:\s{2,}|\s*File\s+\"|.*Error:|.*Exception:)"
    )

    try:
        with open(log_path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return None

    if not lines:
        return None

    error_blocks: list[list[str]] = []
    current_block: list[str] = []
    in_traceback = False

    for line in lines:
        line_stripped = line.rstrip("\n\r")

        # Check for ERROR line
        if error_pattern.match(line_stripped):
            # Save previous block if it exists
            if current_block:
                error_blocks.append(current_block)
            current_block = [line_stripped]
            in_traceback = False

        # Check for traceback start
        elif traceback_start_pattern.match(line_stripped):
            if include_traceback:
                # Start new block or extend current
                if not current_block:
                    current_block = []
                current_block.append(line_stripped)
                in_traceback = True

        # Continue collecting traceback lines
        elif in_traceback and include_traceback:
            if traceback_continuation_pattern.match(line_stripped) or line_stripped.startswith(" "):
                current_block.append(line_stripped)
            elif line_stripped:
                # Check if this is the final exception line (e.g., "ValueError: bad input")
                if EXCEPTION_LINE_PATTERN.match(line_stripped):
                    current_block.append(line_stripped)
                # Either way, we're done with this traceback
                in_traceback = False

        # Also capture standalone exception lines that might follow ERROR logs
        elif current_block and line_stripped:
            # Continue adding context if we're still near an error
            if len(current_block) < MAX_ERROR_CONTEXT_LINES:
                # Add lines that look like exception details
                if EXCEPTION_LINE_PATTERN.match(line_stripped):
                    current_block.append(line_stripped)

    # Don't forget the last block
    if current_block:
        error_blocks.append(current_block)

    if not error_blocks:
        return None

    # Take the last N error blocks
    last_blocks = error_blocks[-max_lines:]

    # Format output
    result_lines = []
    for block in last_blocks:
        result_lines.extend(block)
        if block != last_blocks[-1]:
            result_lines.append("")  # Blank line between blocks

    return "\n".join(result_lines) if result_lines else None


def strip_ansi_codes(text: str) -> str:
    """Remove ANSI color codes from text.

    Args:
        text: Text potentially containing ANSI escape sequences.

    Returns:
        Text with ANSI codes removed.
    """
    ansi_pattern = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_pattern.sub("", text)


def extract_last_error_clean(
    log_path: str | Path,
    max_lines: int = 10,
    include_traceback: bool = True,
) -> str | None:
    """Extract errors with ANSI codes removed for cleaner output.

    Same as extract_last_error but strips ANSI color codes from the result.

    Args:
        log_path: Path to the log file to parse.
        max_lines: Maximum number of ERROR lines to return.
        include_traceback: If True, include full tracebacks with ERROR lines.

    Returns:
        A string containing the last errors found (without ANSI codes), or None.
    """
    result = extract_last_error(log_path, max_lines, include_traceback)
    if result:
        return strip_ansi_codes(result)
    return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract last errors from a log file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s logs/bootstrap_20260125.log
  %(prog)s --max-lines 5 logs/question_service.log
  %(prog)s --no-traceback logs/bootstrap.log
  %(prog)s --clean logs/bootstrap.log  # Strip ANSI codes
        """,
    )
    parser.add_argument("log_file", help="Path to the log file to parse")
    parser.add_argument(
        "--max-lines",
        "-n",
        type=int,
        default=10,
        help="Maximum number of error blocks to show (default: 10)",
    )
    parser.add_argument(
        "--no-traceback",
        action="store_true",
        help="Exclude tracebacks from output",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Strip ANSI color codes from output",
    )

    args = parser.parse_args()

    if args.clean:
        errors = extract_last_error_clean(
            args.log_file,
            max_lines=args.max_lines,
            include_traceback=not args.no_traceback,
        )
    else:
        errors = extract_last_error(
            args.log_file,
            max_lines=args.max_lines,
            include_traceback=not args.no_traceback,
        )

    if errors:
        print(errors)
    else:
        print("No errors found in log file.")
