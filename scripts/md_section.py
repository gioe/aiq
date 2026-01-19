#!/usr/bin/env python3
"""Extract a section from a Markdown file by heading."""
import sys
import re

def extract_section(filepath: str, heading: str) -> str:
    """Extract content from heading to next same/higher level heading."""
    with open(filepath) as f:
        content = f.read()

    # Find the heading (case-insensitive)
    pattern = rf'^(#+)\s+{re.escape(heading)}\s*$'
    match = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)
    if not match:
        return ""

    level = len(match.group(1))
    start = match.end()

    # Find next heading of same or higher level
    next_heading = re.compile(rf'^#{{1,{level}}}\s', re.MULTILINE)
    end_match = next_heading.search(content, start)

    end = end_match.start() if end_match else len(content)
    return content[start:end].strip()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: md_section.py <file> <heading>", file=sys.stderr)
        sys.exit(1)
    print(extract_section(sys.argv[1], sys.argv[2]))
