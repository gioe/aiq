"""
Tests for OpenAPI schema transformation functions.

These tests verify that anyOf patterns with null types are correctly
transformed to the nullable: true format for better client compatibility.
"""

from app.core.openapi_transforms import (
    transform_anyof_to_nullable,
    transform_openapi_spec,
)


class TestTransformAnyofToNullable:
    """Tests for the transform_anyof_to_nullable function."""

    def test_simple_integer_nullable(self):
        """Transform anyOf with integer and null to nullable integer."""
        schema = {
            "anyOf": [{"type": "integer"}, {"type": "null"}],
            "title": "Score",
        }
        result = transform_anyof_to_nullable(schema)

        assert result == {
            "type": "integer",
            "nullable": True,
            "title": "Score",
        }

    def test_simple_string_nullable(self):
        """Transform anyOf with string and null to nullable string."""
        schema = {
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "description": "Optional name",
        }
        result = transform_anyof_to_nullable(schema)

        assert result == {
            "type": "string",
            "nullable": True,
            "description": "Optional name",
        }

    def test_null_first_in_anyof(self):
        """Handle null type appearing first in anyOf array."""
        schema = {
            "anyOf": [{"type": "null"}, {"type": "number"}],
        }
        result = transform_anyof_to_nullable(schema)

        assert result == {
            "type": "number",
            "nullable": True,
        }

    def test_string_with_constraints(self):
        """Preserve string constraints like maxLength when transforming."""
        schema = {
            "anyOf": [
                {"type": "string", "maxLength": 100},
                {"type": "null"},
            ],
            "title": "Device Id",
        }
        result = transform_anyof_to_nullable(schema)

        assert result == {
            "type": "string",
            "maxLength": 100,
            "nullable": True,
            "title": "Device Id",
        }

    def test_ref_type_nullable(self):
        """Transform $ref with null to allOf with nullable."""
        schema = {
            "anyOf": [
                {"$ref": "#/components/schemas/ABComparisonScore"},
                {"type": "null"},
            ],
            "description": "Optional score",
        }
        result = transform_anyof_to_nullable(schema)

        assert result == {
            "allOf": [{"$ref": "#/components/schemas/ABComparisonScore"}],
            "nullable": True,
            "description": "Optional score",
        }

    def test_object_type_nullable(self):
        """Transform object type with additionalProperties."""
        schema = {
            "anyOf": [
                {
                    "type": "object",
                    "additionalProperties": {"type": "number"},
                },
                {"type": "null"},
            ],
            "title": "Weights",
        }
        result = transform_anyof_to_nullable(schema)

        assert result == {
            "type": "object",
            "additionalProperties": {"type": "number"},
            "nullable": True,
            "title": "Weights",
        }

    def test_nested_properties(self):
        """Transform nullable fields nested in properties."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {
                    "anyOf": [{"type": "integer"}, {"type": "null"}],
                },
            },
        }
        result = transform_anyof_to_nullable(schema)

        assert result == {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {
                    "type": "integer",
                    "nullable": True,
                },
            },
        }

    def test_deeply_nested_anyof(self):
        """Transform anyOf in deeply nested schema structures."""
        schema = {
            "type": "object",
            "properties": {
                "data": {
                    "type": "object",
                    "properties": {
                        "value": {
                            "anyOf": [{"type": "number"}, {"type": "null"}],
                        },
                    },
                },
            },
        }
        result = transform_anyof_to_nullable(schema)

        assert result["properties"]["data"]["properties"]["value"] == {
            "type": "number",
            "nullable": True,
        }

    def test_anyof_in_array_items(self):
        """Transform anyOf within array items schema."""
        schema = {
            "type": "array",
            "items": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
            },
        }
        result = transform_anyof_to_nullable(schema)

        assert result == {
            "type": "array",
            "items": {
                "type": "string",
                "nullable": True,
            },
        }

    def test_non_nullable_anyof_unchanged(self):
        """Leave anyOf with more than 2 items unchanged."""
        schema = {
            "anyOf": [
                {"type": "string"},
                {"type": "integer"},
                {"type": "null"},
            ],
        }
        result = transform_anyof_to_nullable(schema)

        # Should remain unchanged since it has 3 items
        assert result == schema

    def test_anyof_without_null_unchanged(self):
        """Leave anyOf without null type unchanged."""
        schema = {
            "anyOf": [
                {"type": "string"},
                {"type": "integer"},
            ],
        }
        result = transform_anyof_to_nullable(schema)

        assert result == schema

    def test_empty_schema(self):
        """Handle empty schema dict."""
        assert transform_anyof_to_nullable({}) == {}

    def test_non_dict_input(self):
        """Handle non-dict input gracefully."""
        assert transform_anyof_to_nullable("string") == "string"
        assert transform_anyof_to_nullable(123) == 123
        assert transform_anyof_to_nullable(None) is None

    def test_schema_without_anyof(self):
        """Leave schemas without anyOf unchanged."""
        schema = {
            "type": "string",
            "minLength": 1,
            "maxLength": 255,
        }
        result = transform_anyof_to_nullable(schema)

        assert result == schema

    def test_preserves_description_and_title(self):
        """Preserve description and title metadata."""
        schema = {
            "anyOf": [{"type": "integer"}, {"type": "null"}],
            "title": "My Field",
            "description": "This is a description",
        }
        result = transform_anyof_to_nullable(schema)

        assert result["title"] == "My Field"
        assert result["description"] == "This is a description"
        assert result["nullable"] is True
        assert result["type"] == "integer"

    def test_does_not_mutate_input(self):
        """Verify that input schema is not mutated."""
        schema = {
            "anyOf": [{"type": "string"}, {"type": "null"}],
        }
        original = {
            "anyOf": [{"type": "string"}, {"type": "null"}],
        }
        transform_anyof_to_nullable(schema)

        assert schema == original


class TestTransformOpenAPISpec:
    """Tests for the transform_openapi_spec function."""

    def test_transforms_components_schemas(self):
        """Transform schemas in components/schemas section."""
        spec = {
            "openapi": "3.1.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "components": {
                "schemas": {
                    "User": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "name": {
                                "anyOf": [{"type": "string"}, {"type": "null"}],
                            },
                        },
                    },
                },
            },
        }
        result = transform_openapi_spec(spec)

        user_schema = result["components"]["schemas"]["User"]
        assert user_schema["properties"]["name"] == {
            "type": "string",
            "nullable": True,
        }

    def test_transforms_inline_schemas_in_paths(self):
        """Transform inline schemas in path definitions."""
        spec = {
            "openapi": "3.1.0",
            "paths": {
                "/users": {
                    "get": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "anyOf": [
                                                {"type": "object"},
                                                {"type": "null"},
                                            ],
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        }
        result = transform_openapi_spec(spec)

        response_schema = result["paths"]["/users"]["get"]["responses"]["200"][
            "content"
        ]["application/json"]["schema"]
        assert response_schema == {
            "type": "object",
            "nullable": True,
        }

    def test_preserves_other_spec_sections(self):
        """Preserve non-schema sections of the spec."""
        spec = {
            "openapi": "3.1.0",
            "info": {
                "title": "Test API",
                "version": "1.0.0",
                "description": "A test API",
            },
            "servers": [{"url": "https://api.example.com"}],
            "components": {
                "schemas": {},
                "securitySchemes": {
                    "bearerAuth": {
                        "type": "http",
                        "scheme": "bearer",
                    },
                },
            },
        }
        result = transform_openapi_spec(spec)

        assert result["openapi"] == "3.1.0"
        assert result["info"]["title"] == "Test API"
        assert result["servers"] == [{"url": "https://api.example.com"}]
        assert "bearerAuth" in result["components"]["securitySchemes"]

    def test_handles_missing_components(self):
        """Handle spec without components section."""
        spec = {
            "openapi": "3.1.0",
            "info": {"title": "Test", "version": "1.0.0"},
        }
        result = transform_openapi_spec(spec)

        assert result == spec

    def test_handles_missing_schemas(self):
        """Handle components without schemas section."""
        spec = {
            "openapi": "3.1.0",
            "components": {
                "securitySchemes": {},
            },
        }
        result = transform_openapi_spec(spec)

        assert result == spec

    def test_does_not_mutate_input_spec(self):
        """Verify that input spec is not mutated."""
        spec = {
            "openapi": "3.1.0",
            "components": {
                "schemas": {
                    "Test": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                    },
                },
            },
        }
        import copy

        original = copy.deepcopy(spec)
        transform_openapi_spec(spec)

        assert spec == original

    def test_non_dict_input(self):
        """Handle non-dict input gracefully."""
        assert transform_openapi_spec("string") == "string"
        assert transform_openapi_spec(None) is None

    def test_real_world_pattern(self):
        """Test transformation with a realistic schema pattern."""
        spec = {
            "openapi": "3.1.0",
            "components": {
                "schemas": {
                    "ABComparisonResult": {
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "integer"},
                            "score_difference": {
                                "anyOf": [
                                    {"type": "integer"},
                                    {"type": "null"},
                                ],
                                "description": "Difference between scores",
                                "title": "Score Difference",
                            },
                            "weighted_score": {
                                "anyOf": [
                                    {"$ref": "#/components/schemas/Score"},
                                    {"type": "null"},
                                ],
                                "description": "Weighted score if configured",
                            },
                        },
                    },
                },
            },
        }
        result = transform_openapi_spec(spec)

        props = result["components"]["schemas"]["ABComparisonResult"]["properties"]

        # Simple nullable integer
        assert props["score_difference"] == {
            "type": "integer",
            "nullable": True,
            "description": "Difference between scores",
            "title": "Score Difference",
        }

        # Nullable $ref
        assert props["weighted_score"] == {
            "allOf": [{"$ref": "#/components/schemas/Score"}],
            "nullable": True,
            "description": "Weighted score if configured",
        }
