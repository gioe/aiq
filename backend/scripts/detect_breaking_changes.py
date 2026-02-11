#!/usr/bin/env python3
"""
Detect breaking changes between two OpenAPI specifications.

This script compares an old and new OpenAPI spec to identify breaking changes
that would require client code updates.

Usage:
    python detect_breaking_changes.py <old_spec.json> <new_spec.json>

Exit codes:
    0 - No breaking changes detected
    1 - Breaking changes detected
    2 - Error reading or parsing spec files
"""

import json
import sys
from pathlib import Path
from typing import Any


HTTP_METHODS = {"get", "post", "put", "delete", "patch", "options", "head", "trace"}


class BreakingChange:
    """Represents a breaking change detected in the API."""

    def __init__(self, category: str, path: str, description: str):
        """Initialize a breaking change with category, path, and description."""
        self.category = category
        self.path = path
        self.description = description

    def __str__(self) -> str:
        return f"[{self.category}] {self.path}: {self.description}"


def load_spec(file_path: Path) -> dict[str, Any]:
    """Load and parse an OpenAPI spec file."""
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found: {file_path}")
        sys.exit(2)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {file_path}: {e}")
        sys.exit(2)


def detect_removed_endpoints(
    old_spec: dict[str, Any], new_spec: dict[str, Any]
) -> list[BreakingChange]:
    """Detect endpoints that were removed."""
    changes = []
    old_paths = old_spec.get("paths", {})
    new_paths = new_spec.get("paths", {})

    for path in old_paths:
        if path not in new_paths:
            changes.append(
                BreakingChange("REMOVED_ENDPOINT", path, "Entire endpoint was removed")
            )
            continue

        # Check for removed HTTP methods
        old_methods = old_paths[path]
        new_methods = new_paths[path]
        for method in old_methods:
            if method.lower() not in HTTP_METHODS:
                continue
            if method not in new_methods:
                changes.append(
                    BreakingChange(
                        "REMOVED_METHOD",
                        f"{method.upper()} {path}",
                        "HTTP method was removed",
                    )
                )

    return changes


def detect_removed_required_fields(
    old_spec: dict[str, Any], new_spec: dict[str, Any]
) -> list[BreakingChange]:
    """Detect required request/response fields that were removed."""
    changes = []
    old_schemas = old_spec.get("components", {}).get("schemas", {})
    new_schemas = new_spec.get("components", {}).get("schemas", {})

    for schema_name, old_schema in old_schemas.items():
        if schema_name not in new_schemas:
            # Schema removed entirely - this is significant
            changes.append(
                BreakingChange(
                    "REMOVED_SCHEMA",
                    f"components/schemas/{schema_name}",
                    "Schema definition was removed",
                )
            )
            continue

        new_schema = new_schemas[schema_name]

        # Check if required fields were removed from properties
        old_props = old_schema.get("properties", {})
        new_props = new_schema.get("properties", {})

        for prop_name in old_props:
            if prop_name not in new_props:
                # Check if it was required
                if prop_name in old_schema.get("required", []):
                    changes.append(
                        BreakingChange(
                            "REMOVED_REQUIRED_FIELD",
                            f"components/schemas/{schema_name}.{prop_name}",
                            "Required field was removed",
                        )
                    )

        # Check if fields became required (also breaking)
        old_required = set(old_schema.get("required", []))
        new_required = set(new_schema.get("required", []))
        newly_required = new_required - old_required

        for field in newly_required:
            if field in new_props:
                changes.append(
                    BreakingChange(
                        "FIELD_NOW_REQUIRED",
                        f"components/schemas/{schema_name}.{field}",
                        "Previously optional field is now required",
                    )
                )

    return changes


def detect_changed_response_types(
    old_spec: dict[str, Any], new_spec: dict[str, Any]
) -> list[BreakingChange]:
    """Detect changes in response schema types."""
    changes = []
    old_schemas = old_spec.get("components", {}).get("schemas", {})
    new_schemas = new_spec.get("components", {}).get("schemas", {})

    for schema_name in old_schemas:
        if schema_name not in new_schemas:
            continue  # Already handled in removed_required_fields

        old_schema = old_schemas[schema_name]
        new_schema = new_schemas[schema_name]

        # Check for type changes in properties
        old_props = old_schema.get("properties", {})
        new_props = new_schema.get("properties", {})

        for prop_name in old_props:
            if prop_name not in new_props:
                continue  # Already handled in removed_required_fields

            old_prop = old_props[prop_name]
            new_prop = new_props[prop_name]

            # Compare types
            old_type = _get_type(old_prop)
            new_type = _get_type(new_prop)

            if old_type and new_type and old_type != new_type:
                changes.append(
                    BreakingChange(
                        "CHANGED_TYPE",
                        f"components/schemas/{schema_name}.{prop_name}",
                        f"Type changed from {old_type} to {new_type}",
                    )
                )

    return changes


def _get_type(prop: dict[str, Any]) -> str | None:
    """Extract the type from a property definition."""
    if "type" in prop:
        return prop["type"]
    if "$ref" in prop:
        return prop["$ref"]
    if "allOf" in prop:
        # For nullable refs like {"allOf": [{"$ref": "..."}], "nullable": true}
        if len(prop["allOf"]) > 0 and "$ref" in prop["allOf"][0]:
            return prop["allOf"][0]["$ref"]
    if "anyOf" in prop:
        # Extract non-null types from anyOf
        types = []
        for item in prop["anyOf"]:
            if item.get("type") != "null":
                types.append(item.get("type", item.get("$ref", "unknown")))
        return types[0] if types else None
    return None


def detect_changed_http_methods(
    old_spec: dict[str, Any], new_spec: dict[str, Any]
) -> list[BreakingChange]:
    """
    Detect endpoints where the HTTP method semantics changed.

    Note: Method removal is already covered by detect_removed_endpoints.
    This function is a placeholder for future detection of method renames
    or semantic changes (e.g., POST becoming PUT).
    """
    # Covered by detect_removed_endpoints for now
    _ = old_spec, new_spec
    return []


def generate_report(breaking_changes: list[BreakingChange]) -> None:
    """Generate a human-readable report of breaking changes."""
    if not breaking_changes:
        print("✓ No breaking changes detected")
        return

    print(f"✗ {len(breaking_changes)} breaking change(s) detected:\n")

    # Group by category
    by_category: dict[str, list[BreakingChange]] = {}
    for change in breaking_changes:
        if change.category not in by_category:
            by_category[change.category] = []
        by_category[change.category].append(change)

    for category, changes in sorted(by_category.items()):
        print(f"{category}:")
        for change in changes:
            print(f"  - {change.path}")
            print(f"    {change.description}")
        print()


def main() -> None:
    """Main entry point."""
    if len(sys.argv) != 3:
        print(
            "Usage: python detect_breaking_changes.py <old_spec.json> <new_spec.json>"
        )
        sys.exit(2)

    old_path = Path(sys.argv[1])
    new_path = Path(sys.argv[2])

    print("Comparing OpenAPI specs:")
    print(f"  Old: {old_path}")
    print(f"  New: {new_path}")
    print()

    old_spec = load_spec(old_path)
    new_spec = load_spec(new_path)

    # Run all detection functions
    breaking_changes: list[BreakingChange] = []
    breaking_changes.extend(detect_removed_endpoints(old_spec, new_spec))
    breaking_changes.extend(detect_removed_required_fields(old_spec, new_spec))
    breaking_changes.extend(detect_changed_response_types(old_spec, new_spec))
    breaking_changes.extend(detect_changed_http_methods(old_spec, new_spec))

    generate_report(breaking_changes)

    # Exit with code 1 if breaking changes found
    sys.exit(1 if breaking_changes else 0)


if __name__ == "__main__":
    main()
