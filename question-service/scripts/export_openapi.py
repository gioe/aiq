#!/usr/bin/env python3
"""Export OpenAPI specification from FastAPI applications.

Usage:
    python export_openapi.py [--output PATH]

This script generates the OpenAPI specification from the trigger_server FastAPI
application and saves it as a JSON file.
"""
import argparse
import json
from pathlib import Path

from trigger_server import app


def export_openapi(output_path: Path) -> None:
    """Export the OpenAPI spec to the specified path."""
    openapi_schema = app.openapi()

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(openapi_schema, f, indent=2)

    print(f"OpenAPI spec exported to: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export OpenAPI specification from trigger_server"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/api/trigger-server.json"),
        help="Output path for the OpenAPI spec (default: docs/api/trigger-server.json)",
    )
    args = parser.parse_args()

    export_openapi(args.output)


if __name__ == "__main__":
    main()
