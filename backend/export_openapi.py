#!/usr/bin/env python3
"""
Export the FastAPI OpenAPI spec to a JSON file.

This script generates the OpenAPI specification from the FastAPI application
without requiring a running server. It's used in CI to keep the spec in sync.

Usage:
    python export_openapi.py [output_path] [--no-transform]

If no output path is provided, defaults to ../docs/api/openapi.json

The --no-transform flag skips the anyOf-to-nullable transformation, which
converts OpenAPI 3.1 anyOf patterns (used by Python Optional types) to
nullable: true format for better client generator compatibility.

Exit codes:
    0 - Success
    1 - Failed to import app
    2 - Failed to generate OpenAPI spec
    3 - Failed to write file
    4 - Invalid output path (path traversal attempt)
    5 - Validation failed (--validate flag)
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


def validate_openapi_spec(spec: dict) -> tuple[bool, str]:
    """
    Validate the OpenAPI specification structure.

    Performs basic structural validation to ensure the spec is well-formed.

    Args:
        spec: The OpenAPI specification dictionary to validate

    Returns:
        Tuple of (is_valid, error_message). error_message is empty string if valid.
    """
    # Check required top-level fields
    required_fields = ["openapi", "info", "paths"]
    for field in required_fields:
        if field not in spec:
            return False, f"Missing required field: {field}"

    # Validate openapi version format
    if not isinstance(spec["openapi"], str):
        return False, "Field 'openapi' must be a string"

    # Validate info structure
    info = spec["info"]
    if not isinstance(info, dict):
        return False, "Field 'info' must be an object"
    if "title" not in info:
        return False, "Field 'info.title' is required"
    if "version" not in info:
        return False, "Field 'info.version' is required"

    # Validate paths structure
    paths = spec["paths"]
    if not isinstance(paths, dict):
        return False, "Field 'paths' must be an object"

    # Validate $ref resolution in components/schemas if present
    if "components" in spec and "schemas" in spec["components"]:
        schemas = spec["components"]["schemas"]
        if not isinstance(schemas, dict):
            return False, "Field 'components.schemas' must be an object"

        # Collect all $ref references and check they resolve
        schema_names = set(schemas.keys())
        for schema_name, schema_def in schemas.items():
            refs = _collect_refs(schema_def)
            for ref in refs:
                # Parse ref like "#/components/schemas/SchemaName"
                if ref.startswith("#/components/schemas/"):
                    ref_name = ref.split("/")[-1]
                    if ref_name not in schema_names:
                        return (
                            False,
                            f"Unresolved $ref in schema '{schema_name}': {ref}",
                        )

    return True, ""


def _collect_refs(obj, refs=None) -> set[str]:
    """Recursively collect all $ref values from a schema object."""
    if refs is None:
        refs = set()

    if isinstance(obj, dict):
        if "$ref" in obj:
            refs.add(obj["$ref"])
        for value in obj.values():
            _collect_refs(value, refs)
    elif isinstance(obj, list):
        for item in obj:
            _collect_refs(item, refs)

    return refs


def export_openapi(
    output_path: Path, *, apply_transforms: bool = True, validate: bool = False
) -> int:
    """
    Export the OpenAPI spec to the specified path.

    Args:
        output_path: Path to write the OpenAPI spec JSON file
        apply_transforms: If True, apply anyOf-to-nullable transformations
        validate: If True, validate the spec structure before writing

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

    if apply_transforms:
        try:
            from app.core.openapi_transforms import transform_openapi_spec

            openapi_spec = transform_openapi_spec(openapi_spec)
            print("Applied anyOf-to-nullable transformations")
        except Exception as e:
            print(f"Warning: Failed to apply transforms: {e}")
            # Continue without transforms rather than failing

    if validate:
        is_valid, error_msg = validate_openapi_spec(openapi_spec)
        if not is_valid:
            print(f"Error: OpenAPI spec validation failed: {error_msg}")
            return 5

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
    args = sys.argv[1:]
    apply_transforms = "--no-transform" not in args
    validate = "--validate" in args
    args = [a for a in args if a not in ("--no-transform", "--validate")]

    if args:
        output_path = Path(args[0])
    else:
        output_path = Path(__file__).parent.parent / "docs" / "api" / "openapi.json"

    exit_code = export_openapi(
        output_path, apply_transforms=apply_transforms, validate=validate
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
