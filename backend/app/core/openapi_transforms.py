"""
OpenAPI schema transformations for better client compatibility.

This module provides functions to transform OpenAPI 3.1 schema patterns
into formats that are more compatible with code generators and clients.

The primary transformation is converting anyOf patterns with null types
(common in Python Optional fields) to the nullable: true format.

Examples:
    Transform a simple nullable type:
    >>> schema = {"anyOf": [{"type": "integer"}, {"type": "null"}]}
    >>> transform_anyof_to_nullable(schema)
    {"type": "integer", "nullable": True}

    Transform a $ref nullable type:
    >>> schema = {"anyOf": [{"$ref": "#/components/schemas/Foo"}, {"type": "null"}]}
    >>> transform_anyof_to_nullable(schema)
    {"allOf": [{"$ref": "#/components/schemas/Foo"}], "nullable": True}
"""

from copy import deepcopy
from typing import Any


def _is_null_type(schema: dict[str, Any]) -> bool:
    """Check if a schema represents a null type."""
    return schema.get("type") == "null"


def _is_nullable_anyof(schema: dict[str, Any]) -> bool:
    """
    Check if a schema is an anyOf pattern representing a nullable type.

    A nullable anyOf has exactly 2 items where one is {type: "null"}.

    Args:
        schema: The schema to check

    Returns:
        True if this is a nullable anyOf pattern
    """
    if "anyOf" not in schema:
        return False

    any_of = schema["anyOf"]
    if not isinstance(any_of, list) or len(any_of) != 2:
        return False

    null_count = sum(1 for item in any_of if _is_null_type(item))
    return null_count == 1


def _extract_non_null_type(any_of: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract the non-null type from an anyOf list."""
    for item in any_of:
        if not _is_null_type(item):
            return item
    raise ValueError("No non-null type found in anyOf")


def transform_anyof_to_nullable(schema: dict[str, Any]) -> dict[str, Any]:
    """
    Transform anyOf null patterns to nullable format.

    Converts patterns like:
        {"anyOf": [{"type": "integer"}, {"type": "null"}]}
    To:
        {"type": "integer", "nullable": true}

    For $ref types, uses allOf to preserve the reference:
        {"anyOf": [{"$ref": "..."}, {"type": "null"}]}
    Becomes:
        {"allOf": [{"$ref": "..."}], "nullable": true}

    Args:
        schema: A schema dict that may contain anyOf patterns

    Returns:
        Transformed schema with anyOf null patterns converted to nullable
    """
    if not isinstance(schema, dict):
        return schema

    # Check if this schema itself is a nullable anyOf
    if _is_nullable_anyof(schema):
        non_null_type = _extract_non_null_type(schema["anyOf"])

        # Build the transformed schema
        if "$ref" in non_null_type:
            # For $ref, wrap in allOf to preserve the reference
            transformed: dict[str, Any] = {
                "allOf": [{"$ref": non_null_type["$ref"]}],
                "nullable": True,
            }
        else:
            # For other types, merge the non-null type and add nullable
            transformed = deepcopy(non_null_type)
            transformed["nullable"] = True

        # Preserve other properties from the original schema (description, title, etc.)
        for key, value in schema.items():
            if key != "anyOf" and key not in transformed:
                transformed[key] = deepcopy(value)

        # Recursively transform any nested schemas in the result
        return transform_anyof_to_nullable(transformed)

    # Otherwise, recursively process all values (make a copy to avoid mutation)
    result: dict[str, Any] = {}
    for key, value in schema.items():
        if isinstance(value, dict):
            result[key] = transform_anyof_to_nullable(value)
        elif isinstance(value, list):
            result[key] = [
                transform_anyof_to_nullable(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value

    return result


def transform_openapi_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """
    Transform an entire OpenAPI specification.

    This is the main entry point for transforming a complete OpenAPI spec.
    It applies all transformations to the components/schemas section and
    any inline schemas in paths.

    Args:
        spec: The complete OpenAPI specification dict

    Returns:
        Transformed OpenAPI specification
    """
    if not isinstance(spec, dict):
        return spec

    result = deepcopy(spec)

    # Transform components/schemas
    if "components" in result and "schemas" in result["components"]:
        schemas = result["components"]["schemas"]
        for name in schemas:
            schemas[name] = transform_anyof_to_nullable(schemas[name])

    # Transform paths (for inline schemas in request/response bodies)
    if "paths" in result:
        result["paths"] = transform_anyof_to_nullable(result["paths"])

    return result
