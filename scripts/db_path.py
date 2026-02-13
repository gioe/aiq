#!/usr/bin/env python3
"""Resolve the project task database path.

Uses the ``tusk path`` CLI command when available, falling back to
``<repo_root>/tusk/tasks.db`` by walking up from this file's directory.
"""

import os
import subprocess


def resolve_db_path() -> str:
    """Return the absolute path to the project task database."""
    try:
        result = subprocess.run(
            ["tusk", "path"], capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        d = os.path.dirname(os.path.abspath(__file__))
        while d != os.path.dirname(d):
            if os.path.isdir(os.path.join(d, ".git")):
                return os.path.join(d, "tusk", "tasks.db")
            d = os.path.dirname(d)
        return "tusk/tasks.db"


DB_PATH = resolve_db_path()
