#!/usr/bin/env python3
"""Sync the README.md project structure tree and validate all markdown links.

Compares the actual directory layout against the tree block in README.md,
reports drift, and optionally updates the README in place.

Usage:
    python scripts/sync_readme_structure.py          # Check only (exit 1 if drift)
    python scripts/sync_readme_structure.py --fix    # Update README.md in place
"""

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"

# Directories to include in the tree (order matters for display).
# Map of directory name -> description comment.
# Set to None to auto-detect directories not listed here.
KNOWN_DIRS: dict[str, str] = {
    "ios/": "SwiftUI iOS application",
    "backend/": "Backend API server",
    "question-service/": "AI-powered question generation service",
    "libs/": "Shared Python packages (domain types, observability)",
    "scripts/": "Pre-commit hooks (float checks, magic numbers)",
    "docs/": "Project documentation",
    "deployment/": "AWS Terraform configs (legacy)",
    "website/": "Privacy policy, terms of service",
    ".claude/": "Claude Code config, skills, and scripts",
    ".github/": "CI/CD workflows, PR template, Dependabot",
}

# Directories to always exclude from the tree.
EXCLUDED = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    "tusk",
    "logs",
}

# Top-level files to include in the tree.
KNOWN_FILES: dict[str, str] = {
    "README.md": "This file",
}


def get_actual_dirs() -> list[str]:
    """Return top-level directories in display order.

    Known directories appear in the order defined in KNOWN_DIRS.
    Any new directories not in KNOWN_DIRS are appended alphabetically.
    """
    on_disk = set()
    for entry in ROOT.iterdir():
        if not entry.is_dir():
            continue
        name = entry.name
        if name in EXCLUDED:
            continue
        if name + "/" in KNOWN_DIRS or not name.startswith("."):
            on_disk.add(name + "/")

    # Preserve KNOWN_DIRS order for directories that exist on disk.
    ordered = [d for d in KNOWN_DIRS if d in on_disk]
    # Append any new directories not in KNOWN_DIRS.
    new_dirs = sorted(on_disk - set(KNOWN_DIRS))
    return ordered + new_dirs


def build_tree(dirs: list[str]) -> str:
    """Build the ASCII tree block content."""
    lines = ["aiq/"]
    entries = list(dirs) + list(KNOWN_FILES.keys())
    col_width = max(len(e) for e in entries) + 4  # padding for alignment

    for i, entry in enumerate(entries):
        is_last = i == len(entries) - 1
        prefix = "\u2514\u2500\u2500" if is_last else "\u251c\u2500\u2500"

        # Look up description
        if entry in KNOWN_DIRS:
            desc = KNOWN_DIRS[entry]
        elif entry in KNOWN_FILES:
            desc = KNOWN_FILES[entry]
        else:
            desc = "(new - needs description)"

        padded = f"{entry:<{col_width}}"
        lines.append(f"{prefix} {padded}# {desc}")

    return "\n".join(lines)


def parse_readme_tree(content: str) -> str | None:
    """Extract the tree block from README content."""
    match = re.search(
        r"```\n(aiq/\n(?:.*\n)*?.*\u2514.*)\n```", content
    )
    if match:
        return match.group(1)
    return None


def find_markdown_links(content: str) -> list[tuple[int, str, str]]:
    """Find all markdown links and return (line_number, text, path) tuples."""
    links = []
    for i, line in enumerate(content.splitlines(), 1):
        for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", line):
            text, path = match.group(1), match.group(2)
            # Skip external URLs
            if path.startswith(("http://", "https://", "#", "mailto:")):
                continue
            links.append((i, text, path))
    return links


def validate_links(content: str) -> list[str]:
    """Check all relative markdown links point to existing files."""
    issues = []
    for line_num, text, path in find_markdown_links(content):
        target = ROOT / path
        if not target.exists():
            issues.append(f"  Line {line_num}: [{text}]({path}) -> file not found")
    return issues


def main() -> int:
    fix_mode = "--fix" in sys.argv
    content = README.read_text()
    issues: list[str] = []

    # --- Check tree block ---
    actual_dirs = get_actual_dirs()
    expected_tree = build_tree(actual_dirs)
    current_tree = parse_readme_tree(content)

    if current_tree is None:
        issues.append("Could not find project structure tree block in README.md")
    elif current_tree != expected_tree:
        issues.append("Project structure tree is out of date:")

        current_entries = set(re.findall(r"[.\w-]+/", current_tree))
        expected_entries = set(re.findall(r"[.\w-]+/", expected_tree))

        added = expected_entries - current_entries
        removed = current_entries - expected_entries

        for d in sorted(added):
            issues.append(f"  + {d} (directory exists but missing from README)")
        for d in sorted(removed):
            issues.append(f"  - {d} (listed in README but does not exist)")

    # --- Check links ---
    link_issues = validate_links(content)
    if link_issues:
        issues.append("Broken markdown links:")
        issues.extend(link_issues)

    # --- Report or fix ---
    if not issues:
        print("README.md is in sync with project structure.")
        return 0

    for issue in issues:
        print(issue)

    if fix_mode and current_tree is not None:
        updated = content.replace(current_tree, expected_tree)
        README.write_text(updated)
        print(f"\nUpdated README.md tree block.")
        # Re-check links after tree update (links need manual fixes)
        if link_issues:
            print("Broken links require manual fixes.")
            return 1
        return 0

    if not fix_mode:
        print(f"\nRun with --fix to update the tree block automatically.")

    return 1


if __name__ == "__main__":
    sys.exit(main())
