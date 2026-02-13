#!/usr/bin/env python3
"""Sync a README.md project-structure tree with the actual directory layout.

Scans a target directory, compares its contents against the ASCII tree block
in its README.md, reports drift, and optionally updates the README in place.

Usage:
    python scripts/sync_readme_structure.py [directory] [--fix]

Arguments:
    directory   Path to check (default: repo root). Must contain a README.md
                with a fenced code block whose first line ends with '/'.

Options:
    --fix       Update the README.md tree block in place.

Examples:
    python scripts/sync_readme_structure.py              # Check repo root
    python scripts/sync_readme_structure.py --fix        # Fix repo root
    python scripts/sync_readme_structure.py backend      # Check backend/
    python scripts/sync_readme_structure.py ios --fix    # Fix ios/
"""

import re
import sys
from pathlib import Path

# Directories/files to always exclude from tree comparison.
EXCLUDED = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    ".DS_Store",
    ".coverage",
    ".build",
    "DerivedData",
    "Build",
    "xcuserdata",
    "tusk",
    "logs",
    "venv",
    ".venv",
}

# Patterns to exclude by suffix (e.g., build artifacts).
EXCLUDED_SUFFIXES = {".xcresult"}


def find_tree_block(content: str) -> tuple[str, int, int] | None:
    """Find an ASCII directory-tree fenced code block in markdown content.

    Looks for a ``` block whose first line ends with '/' (a directory root)
    and contains box-drawing characters (├── or └──).

    Returns (block_text, start_pos, end_pos) or None.
    """
    for match in re.finditer(r"```\n(.*?)\n```", content, re.DOTALL):
        block = match.group(1)
        lines = block.splitlines()
        if not lines:
            continue
        # First line should be a directory name ending with /
        if not lines[0].rstrip().endswith("/"):
            continue
        # Must contain tree-drawing characters
        if not any("\u251c" in line or "\u2514" in line for line in lines):
            continue
        return block, match.start(1), match.end(1)
    return None


def parse_tree_entries(tree_block: str) -> dict[str, str]:
    """Parse directory/file entries and their comments from a tree block.

    Returns {name: description} preserving the original descriptions.
    """
    entries: dict[str, str] = {}
    for line in tree_block.splitlines()[1:]:  # skip root line
        # Match: ├── name  # description  OR  └── name  # description
        m = re.match(r"[│├└─\s]+\s+(\S+)\s+#\s*(.*)", line)
        if m:
            entries[m.group(1)] = m.group(2).strip()
        else:
            # Entry without a description comment
            m = re.match(r"[│├└─\s]+\s+(\S+)", line)
            if m:
                entries[m.group(1)] = ""
    return entries


def get_dir_contents(target: Path) -> tuple[list[str], list[str]]:
    """Return (directories, files) in target, excluding noise."""
    dirs = []
    files = []
    for entry in sorted(target.iterdir()):
        name = entry.name
        if name in EXCLUDED:
            continue
        if any(name.endswith(s) for s in EXCLUDED_SUFFIXES):
            continue
        if name.startswith(".") and entry.is_dir():
            # Only include select hidden dirs
            if name not in {".claude", ".github"}:
                continue
        if entry.is_dir():
            dirs.append(name + "/")
        elif entry.is_file() and not name.startswith("."):
            files.append(name)
    return dirs, files


def build_tree(
    root_name: str,
    dirs: list[str],
    files: list[str],
    existing_entries: dict[str, str],
    readme_entries: list[str],
) -> str:
    """Build an updated ASCII tree block.

    Preserves order and descriptions from the existing tree for entries that
    still exist. Appends new entries at the end. Drops removed entries.
    """
    on_disk = set(dirs + files)

    # Start with existing entries that still exist (preserves order).
    ordered: list[str] = [e for e in readme_entries if e in on_disk]
    # Append new entries not in the existing tree.
    new_entries = sorted(on_disk - set(readme_entries))
    ordered.extend(new_entries)

    if not ordered:
        return root_name

    col_width = max(len(e) for e in ordered) + 4
    lines = [root_name]

    for i, entry in enumerate(ordered):
        is_last = i == len(ordered) - 1
        prefix = "\u2514\u2500\u2500" if is_last else "\u251c\u2500\u2500"

        desc = existing_entries.get(entry, "")
        if not desc and entry in new_entries:
            desc = "(new - needs description)"

        padded = f"{entry:<{col_width}}"
        if desc:
            lines.append(f"{prefix} {padded}# {desc}")
        else:
            lines.append(f"{prefix} {padded.rstrip()}")

    return "\n".join(lines)


def validate_links(content: str, base: Path) -> list[str]:
    """Check all relative markdown links point to existing files."""
    issues = []
    for i, line in enumerate(content.splitlines(), 1):
        for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", line):
            text, path = match.group(1), match.group(2)
            if path.startswith(("http://", "https://", "#", "mailto:")):
                continue
            # Strip anchor fragments (e.g., "file.md#section" -> "file.md")
            file_path = path.split("#")[0]
            if not file_path:
                continue
            target = base / file_path
            if not target.exists():
                issues.append(
                    f"  Line {i}: [{text}]({path}) -> file not found"
                )
    return issues


def main() -> int:
    fix_mode = "--fix" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--fix"]

    # Resolve target directory.
    if args:
        target = Path(args[0]).resolve()
    else:
        target = Path(__file__).resolve().parent.parent

    readme = target / "README.md"
    if not readme.exists():
        print(f"No README.md found in {target}")
        return 1

    content = readme.read_text()
    issues: list[str] = []

    # --- Check tree block ---
    result = find_tree_block(content)
    tree_drifted = False

    if result is None:
        issues.append(
            f"No directory-tree code block found in {readme.name}. "
            f"(Expected a ``` block starting with a line ending in '/')"
        )
    else:
        current_tree, start_pos, end_pos = result
        root_name = current_tree.splitlines()[0].rstrip()
        existing_entries = parse_tree_entries(current_tree)
        readme_entry_order = list(existing_entries.keys())

        actual_dirs, actual_files = get_dir_contents(target)

        # Only check files that are already listed in the tree. New files
        # are not auto-discovered (too noisy). New directories ARE flagged.
        tree_files = [e for e in existing_entries if not e.endswith("/")]
        include_files = [f for f in actual_files if f in tree_files]

        expected_tree = build_tree(
            root_name,
            actual_dirs,
            include_files,
            existing_entries,
            readme_entry_order,
        )

        if current_tree != expected_tree:
            tree_drifted = True
            issues.append("Project structure tree is out of date:")

            current_dirs = {e for e in existing_entries if e.endswith("/")}
            actual_dir_set = set(actual_dirs)
            actual_file_set = set(actual_files)
            current_set = set(existing_entries.keys())
            actual_set = actual_dir_set | set(include_files)

            for d in sorted(actual_set - current_set):
                issues.append(
                    f"  + {d} (exists on disk but missing from README)"
                )
            for d in sorted(current_set - actual_set):
                # Only flag removal if the entry no longer exists on disk.
                if d.endswith("/") and d not in actual_dir_set:
                    issues.append(
                        f"  - {d} (listed in README but not found on disk)"
                    )
                elif not d.endswith("/") and d not in actual_file_set:
                    issues.append(
                        f"  - {d} (listed in README but not found on disk)"
                    )

            # If only whitespace/ordering changed, still flag it.
            if not (actual_set - current_set) and not (
                current_set - actual_set
            ):
                issues.append("  (whitespace or ordering difference)")

    # --- Check links ---
    link_issues = validate_links(content, target)
    if link_issues:
        issues.append("Broken markdown links:")
        issues.extend(link_issues)

    # --- Report or fix ---
    if not issues:
        print(f"{readme.name} is in sync with {target.name}/ structure.")
        return 0

    for issue in issues:
        print(issue)

    if fix_mode and tree_drifted:
        updated = content[:start_pos] + expected_tree + content[end_pos:]
        readme.write_text(updated)
        print(f"\nUpdated {readme.name} tree block.")
        if link_issues:
            print("Broken links require manual fixes.")
            return 1
        return 0

    if not fix_mode:
        print(f"\nRun with --fix to update the tree block automatically.")

    return 1


if __name__ == "__main__":
    sys.exit(main())
