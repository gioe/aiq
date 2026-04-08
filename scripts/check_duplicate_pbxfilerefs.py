#!/usr/bin/env python3
"""Pre-commit hook to detect duplicate PBXFileReference entries in project.pbxproj.

When both add_files_to_xcode.rb and an iOS agent modify the Xcode project file,
the same file can end up with multiple PBXFileReference entries. This causes
'Multiple commands produce' build errors.

This script parses PBXFileReference lines and flags any filename that appears
more than once.

Usage:
    python scripts/check_duplicate_pbxfilerefs.py [project.pbxproj path]

    If no path is provided, checks ios/AIQ.xcodeproj/project.pbxproj.
"""

import re
import sys
from pathlib import Path

# Matches: HASH /* Name */ = {isa = PBXFileReference; ... path = SomeName; ...};
# Captures the path value (the actual filename/path referenced).
PATH_PATTERN = re.compile(
    r"isa\s*=\s*PBXFileReference;.*?path\s*=\s*(?:\"([^\"]+)\"|(\S+?));",
)

DEFAULT_PBXPROJ = Path("ios/AIQ.xcodeproj/project.pbxproj")


def find_duplicates(pbxproj_path: Path) -> list[tuple[str, int, list[int]]]:
    """Find duplicate PBXFileReference paths in a pbxproj file.

    Returns:
        List of (filename, count, line_numbers) for each duplicate.
    """
    try:
        lines = pbxproj_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as e:
        print(f"Error reading {pbxproj_path}: {e}", file=sys.stderr)
        sys.exit(2)

    in_section = False
    path_occurrences: dict[str, list[int]] = {}

    for line_number, line in enumerate(lines, start=1):
        if "/* Begin PBXFileReference section */" in line:
            in_section = True
            continue
        if "/* End PBXFileReference section */" in line:
            break
        if not in_section:
            continue

        match = PATH_PATTERN.search(line)
        if match:
            path_value = match.group(1) or match.group(2)
            path_occurrences.setdefault(path_value, []).append(line_number)

    return [
        (path, len(line_nums), line_nums)
        for path, line_nums in path_occurrences.items()
        if len(line_nums) > 1
    ]


def main() -> int:
    args = sys.argv[1:]
    pbxproj_path = Path(args[0]) if args else DEFAULT_PBXPROJ

    if not pbxproj_path.exists():
        return 0

    duplicates = find_duplicates(pbxproj_path)

    if not duplicates:
        return 0

    print("Duplicate PBXFileReference entries found in project.pbxproj:")
    print()
    for path, count, line_nums in sorted(duplicates):
        lines_str = ", ".join(str(n) for n in line_nums)
        print(f"  {path}: {count} references (lines {lines_str})")
    print()
    print(
        "Fix: Remove the duplicate entries from project.pbxproj, keeping only one "
        "PBXFileReference per file. This typically happens when both a script and "
        "an agent add the same file to the Xcode project."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
