#!/usr/bin/env python3
"""
Export the FastAPI OpenAPI spec to a JSON file.

This script generates the OpenAPI specification from the FastAPI application
without requiring a running server. It's used in CI to keep the spec in sync.

Usage:
    python export_openapi.py [output_path]

If no output path is provided, defaults to ../docs/api/openapi.json
"""

import json
import sys
from pathlib import Path


def export_openapi(output_path: Path) -> None:
    """Export the OpenAPI spec to the specified path."""
    from app.main import app

    openapi_spec = app.openapi()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(openapi_spec, f, indent=2)

    print(f"OpenAPI spec exported to {output_path}")


def main() -> None:
    if len(sys.argv) > 1:
        output_path = Path(sys.argv[1])
    else:
        output_path = Path(__file__).parent.parent / "docs" / "api" / "openapi.json"

    export_openapi(output_path)


if __name__ == "__main__":
    main()
