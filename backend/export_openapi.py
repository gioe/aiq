#!/usr/bin/env python3
"""
Export the FastAPI OpenAPI spec to a JSON file.

This script generates the OpenAPI specification from the FastAPI application
without requiring a running server. It's used in CI to keep the spec in sync.

Usage:
    python export_openapi.py [output_path]

If no output path is provided, defaults to ../docs/api/openapi.json

Exit codes:
    0 - Success
    1 - Failed to import app
    2 - Failed to generate OpenAPI spec
    3 - Failed to write file
    4 - Invalid output path (path traversal attempt)
"""

import json
import sys
from pathlib import Path


def validate_output_path(output_path: Path, project_root: Path) -> bool:
    """Validate that the output path is within the project directory."""
    try:
        resolved = output_path.resolve()
        return resolved.is_relative_to(project_root.resolve())
    except (ValueError, RuntimeError):
        return False


def export_openapi(output_path: Path) -> int:
    """
    Export the OpenAPI spec to the specified path.

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    project_root = Path(__file__).parent.parent

    if not validate_output_path(output_path, project_root):
        print(f"Error: Output path must be within project: {project_root}")
        return 4

    try:
        from app.main import app
    except Exception as e:
        print(f"Error: Failed to import FastAPI app: {e}")
        return 1

    try:
        openapi_spec = app.openapi()
    except Exception as e:
        print(f"Error: Failed to generate OpenAPI spec: {e}")
        return 2

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(openapi_spec, f, indent=2, sort_keys=True)
    except Exception as e:
        print(f"Error: Failed to write OpenAPI spec: {e}")
        return 3

    print(f"OpenAPI spec exported to {output_path}")
    return 0


def main() -> None:
    if len(sys.argv) > 1:
        output_path = Path(sys.argv[1])
    else:
        output_path = Path(__file__).parent.parent / "docs" / "api" / "openapi.json"

    exit_code = export_openapi(output_path)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
