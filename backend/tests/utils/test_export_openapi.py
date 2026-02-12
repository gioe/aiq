"""
Tests for the OpenAPI export script.

This module tests the export_openapi.py script including CLI argument parsing,
path validation, file writing, transform integration, and the --validate flag.
"""
import sys
from pathlib import Path

# Add project root to path for libs/ imports (matches CI PYTHONPATH config)
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import json  # noqa: E402
from unittest.mock import patch, MagicMock  # noqa: E402

import pytest  # noqa: E402

# Import the functions we're testing
from export_openapi import (  # noqa: E402
    validate_output_path,
    validate_openapi_spec,
    export_openapi,
    main,
    _collect_refs,
)


class TestValidateOutputPath:
    """Tests for the validate_output_path function."""

    def test_valid_path_within_project(self, tmp_path):
        """Accept paths within the project directory."""
        output_path = tmp_path / "docs" / "api" / "openapi.json"
        assert validate_output_path(output_path, tmp_path) is True

    def test_valid_path_nested_deeply(self, tmp_path):
        """Accept deeply nested paths within project."""
        output_path = tmp_path / "a" / "b" / "c" / "d" / "openapi.json"
        assert validate_output_path(output_path, tmp_path) is True

    def test_path_traversal_attempt(self, tmp_path):
        """Reject paths that attempt to escape the project directory."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        output_path = project_root / ".." / ".." / "etc" / "passwd"
        assert validate_output_path(output_path, project_root) is False

    def test_symlink_escape_attempt(self, tmp_path):
        """Reject paths using symlinks to escape project directory."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        escape_link = project_root / "escape"
        escape_link.symlink_to(tmp_path.parent)
        output_path = escape_link / "outside.json"
        assert validate_output_path(output_path, project_root) is False

    def test_absolute_path_outside_project(self, tmp_path):
        """Reject absolute paths outside the project."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        output_path = tmp_path / "outside" / "openapi.json"
        assert validate_output_path(output_path, project_root) is False


class TestValidateOpenAPISpec:
    """Tests for the validate_openapi_spec function."""

    def test_valid_spec(self):
        """Accept a valid OpenAPI spec."""
        spec = {
            "openapi": "3.1.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {"/test": {"get": {}}},
        }
        is_valid, msg = validate_openapi_spec(spec)
        assert is_valid is True
        assert msg == ""

    def test_missing_openapi_field(self):
        """Reject spec missing openapi field."""
        spec = {"info": {"title": "T", "version": "1"}, "paths": {}}
        is_valid, msg = validate_openapi_spec(spec)
        assert is_valid is False
        assert "openapi" in msg

    def test_missing_info_field(self):
        """Reject spec missing info field."""
        spec = {"openapi": "3.1.0", "paths": {}}
        is_valid, msg = validate_openapi_spec(spec)
        assert is_valid is False
        assert "info" in msg

    def test_missing_paths_field(self):
        """Reject spec missing paths field."""
        spec = {"openapi": "3.1.0", "info": {"title": "T", "version": "1"}}
        is_valid, msg = validate_openapi_spec(spec)
        assert is_valid is False
        assert "paths" in msg

    def test_missing_info_title(self):
        """Reject spec with missing info.title."""
        spec = {"openapi": "3.1.0", "info": {"version": "1"}, "paths": {}}
        is_valid, msg = validate_openapi_spec(spec)
        assert is_valid is False
        assert "title" in msg

    def test_missing_info_version(self):
        """Reject spec with missing info.version."""
        spec = {"openapi": "3.1.0", "info": {"title": "T"}, "paths": {}}
        is_valid, msg = validate_openapi_spec(spec)
        assert is_valid is False
        assert "version" in msg

    def test_unresolved_ref(self):
        """Reject spec with unresolved $ref."""
        spec = {
            "openapi": "3.1.0",
            "info": {"title": "T", "version": "1"},
            "paths": {},
            "components": {
                "schemas": {
                    "User": {
                        "type": "object",
                        "properties": {
                            "profile": {"$ref": "#/components/schemas/NonExistent"}
                        },
                    }
                }
            },
        }
        is_valid, msg = validate_openapi_spec(spec)
        assert is_valid is False
        assert "NonExistent" in msg

    def test_valid_ref_resolves(self):
        """Accept spec with valid $ref references."""
        spec = {
            "openapi": "3.1.0",
            "info": {"title": "T", "version": "1"},
            "paths": {},
            "components": {
                "schemas": {
                    "User": {
                        "type": "object",
                        "properties": {
                            "profile": {"$ref": "#/components/schemas/Profile"}
                        },
                    },
                    "Profile": {"type": "object"},
                }
            },
        }
        is_valid, msg = validate_openapi_spec(spec)
        assert is_valid is True


class TestCollectRefs:
    """Tests for the _collect_refs helper function."""

    def test_collects_simple_ref(self):
        """Collect a simple $ref."""
        obj = {"$ref": "#/components/schemas/User"}
        refs = _collect_refs(obj)
        assert refs == {"#/components/schemas/User"}

    def test_collects_nested_refs(self):
        """Collect refs nested in properties."""
        obj = {
            "type": "object",
            "properties": {
                "user": {"$ref": "#/components/schemas/User"},
                "items": {
                    "type": "array",
                    "items": {"$ref": "#/components/schemas/Item"},
                },
            },
        }
        refs = _collect_refs(obj)
        assert "#/components/schemas/User" in refs
        assert "#/components/schemas/Item" in refs

    def test_empty_object(self):
        """Return empty set for object with no refs."""
        refs = _collect_refs({"type": "string"})
        assert refs == set()


class TestExportOpenAPI:
    """Tests for the export_openapi function."""

    def test_invalid_output_path(self, tmp_path):
        """Return exit code 4 for invalid output path."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        output_path = tmp_path / "outside.json"

        # Mock Path(__file__).parent.parent to return our project_root
        with patch("export_openapi.Path") as mock_path_cls:
            mock_file_path = MagicMock()
            mock_file_path.parent.parent = project_root
            mock_path_cls.return_value = mock_file_path
            # Make sure the actual output_path still works as a Path
            mock_path_cls.side_effect = None

            # Simpler approach: patch validate_output_path directly
            with patch("export_openapi.validate_output_path", return_value=False):
                result = export_openapi(output_path)
                assert result == 4

    def test_app_import_failure(self, tmp_path):
        """Return exit code 1 when app import fails."""
        output_path = tmp_path / "openapi.json"

        with patch("export_openapi.validate_output_path", return_value=True):
            # The deferred import 'from app.main import app' will be mocked
            # by making the import raise an ImportError
            with patch.dict("sys.modules", {"app": None, "app.main": None}):
                result = export_openapi(output_path)
                assert result == 1

    def test_success_export(self, tmp_path):
        """Successfully export a spec."""
        output_path = tmp_path / "openapi.json"
        mock_spec = {
            "openapi": "3.1.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {},
        }

        mock_app = MagicMock()
        mock_app.openapi.return_value = mock_spec
        mock_app_module = MagicMock()
        mock_app_module.app = mock_app

        with patch("export_openapi.validate_output_path", return_value=True):
            # Mock the deferred import by injecting into sys.modules
            with patch.dict("sys.modules", {"app.main": mock_app_module}):
                result = export_openapi(output_path, apply_transforms=False)

                assert result == 0
                assert output_path.exists()
                with open(output_path) as f:
                    data = json.load(f)
                assert data["openapi"] == "3.1.0"

    def test_success_with_transforms(self, tmp_path):
        """Successfully export spec with transforms applied."""
        output_path = tmp_path / "openapi.json"
        mock_spec = {
            "openapi": "3.1.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {},
        }
        transformed_spec = {
            "openapi": "3.1.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {},
            "transformed": True,
        }

        mock_app = MagicMock()
        mock_app.openapi.return_value = mock_spec
        mock_app_module = MagicMock()
        mock_app_module.app = mock_app

        mock_transforms_module = MagicMock()
        mock_transforms_module.transform_openapi_spec.return_value = transformed_spec

        with patch("export_openapi.validate_output_path", return_value=True):
            with patch.dict(
                "sys.modules",
                {
                    "app.main": mock_app_module,
                    "app.core.openapi_transforms": mock_transforms_module,
                },
            ):
                result = export_openapi(output_path, apply_transforms=True)

                assert result == 0
                assert output_path.exists()
                with open(output_path) as f:
                    data = json.load(f)
                assert data.get("transformed") is True

    def test_openapi_generation_failure(self, tmp_path):
        """Return exit code 2 when OpenAPI generation fails."""
        output_path = tmp_path / "openapi.json"

        mock_app = MagicMock()
        mock_app.openapi.side_effect = RuntimeError("Generation failed")
        mock_app_module = MagicMock()
        mock_app_module.app = mock_app

        with patch("export_openapi.validate_output_path", return_value=True):
            with patch.dict("sys.modules", {"app.main": mock_app_module}):
                result = export_openapi(output_path)
                assert result == 2

    def test_file_write_failure(self, tmp_path):
        """Return exit code 3 when file write fails."""
        output_path = tmp_path / "openapi.json"
        mock_spec = {
            "openapi": "3.1.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {},
        }

        mock_app = MagicMock()
        mock_app.openapi.return_value = mock_spec
        mock_app_module = MagicMock()
        mock_app_module.app = mock_app

        with patch("export_openapi.validate_output_path", return_value=True):
            with patch.dict("sys.modules", {"app.main": mock_app_module}):
                with patch(
                    "builtins.open",
                    side_effect=PermissionError("No write access"),
                ):
                    result = export_openapi(output_path, apply_transforms=False)
                    assert result == 3

    def test_transform_failure_continues(self, tmp_path):
        """Continue export without transforms if transform fails."""
        output_path = tmp_path / "openapi.json"
        mock_spec = {
            "openapi": "3.1.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {},
        }

        mock_app = MagicMock()
        mock_app.openapi.return_value = mock_spec
        mock_app_module = MagicMock()
        mock_app_module.app = mock_app

        # Make the transform import raise
        mock_transforms = MagicMock()
        mock_transforms.transform_openapi_spec.side_effect = Exception(
            "Transform failed"
        )

        with patch("export_openapi.validate_output_path", return_value=True):
            with patch.dict(
                "sys.modules",
                {
                    "app.main": mock_app_module,
                    "app.core.openapi_transforms": mock_transforms,
                },
            ):
                result = export_openapi(output_path, apply_transforms=True)
                # Should succeed despite transform failure
                assert result == 0
                assert output_path.exists()

    def test_validate_failure(self, tmp_path):
        """Return exit code 5 when validation fails."""
        output_path = tmp_path / "openapi.json"
        # Spec missing required 'openapi' field
        mock_spec = {
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {},
        }

        mock_app = MagicMock()
        mock_app.openapi.return_value = mock_spec
        mock_app_module = MagicMock()
        mock_app_module.app = mock_app

        with patch("export_openapi.validate_output_path", return_value=True):
            with patch.dict("sys.modules", {"app.main": mock_app_module}):
                result = export_openapi(
                    output_path,
                    apply_transforms=False,
                    validate=True,
                )
                assert result == 5

    def test_validate_success(self, tmp_path):
        """Successfully validate and export a well-formed spec."""
        output_path = tmp_path / "openapi.json"
        mock_spec = {
            "openapi": "3.1.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {"/test": {}},
        }

        mock_app = MagicMock()
        mock_app.openapi.return_value = mock_spec
        mock_app_module = MagicMock()
        mock_app_module.app = mock_app

        with patch("export_openapi.validate_output_path", return_value=True):
            with patch.dict("sys.modules", {"app.main": mock_app_module}):
                result = export_openapi(
                    output_path,
                    apply_transforms=False,
                    validate=True,
                )
                assert result == 0
                assert output_path.exists()


class TestMain:
    """Tests for the main CLI entry point."""

    def test_no_transform_flag(self):
        """Disable transforms when --no-transform flag is provided."""
        with patch("sys.argv", ["export_openapi.py", "--no-transform"]):
            with patch("export_openapi.export_openapi") as mock_export:
                mock_export.return_value = 0

                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 0
                call_args = mock_export.call_args
                assert call_args[1]["apply_transforms"] is False

    def test_validate_flag(self):
        """Enable validation when --validate flag is provided."""
        with patch("sys.argv", ["export_openapi.py", "--validate"]):
            with patch("export_openapi.export_openapi") as mock_export:
                mock_export.return_value = 0

                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 0
                call_args = mock_export.call_args
                assert call_args[1]["validate"] is True

    def test_validate_with_no_transform(self):
        """Handle both --validate and --no-transform flags."""
        with patch(
            "sys.argv",
            ["export_openapi.py", "--validate", "--no-transform"],
        ):
            with patch("export_openapi.export_openapi") as mock_export:
                mock_export.return_value = 0

                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 0
                call_args = mock_export.call_args
                assert call_args[1]["validate"] is True
                assert call_args[1]["apply_transforms"] is False

    def test_custom_output_path(self, tmp_path):
        """Use custom output path when provided."""
        custom_path = str(tmp_path / "custom.json")
        with patch("sys.argv", ["export_openapi.py", custom_path]):
            with patch("export_openapi.export_openapi") as mock_export:
                mock_export.return_value = 0

                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 0
                call_args = mock_export.call_args
                assert str(call_args[0][0]) == custom_path

    def test_propagates_exit_code(self):
        """Propagate non-zero exit codes from export_openapi."""
        with patch("sys.argv", ["export_openapi.py"]):
            with patch("export_openapi.export_openapi") as mock_export:
                mock_export.return_value = 3

                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 3


class TestOpenAPIConfigPresence:
    """Integration tests for OpenAPI spec file presence and validity."""

    def test_openapi_spec_exists(self):
        """Verify that docs/api/openapi.json exists."""
        spec_path = project_root / "docs" / "api" / "openapi.json"
        assert spec_path.exists(), (
            f"OpenAPI spec not found at {spec_path}. "
            "Run 'cd backend && python export_openapi.py' to generate it."
        )

    def test_openapi_spec_is_valid_json(self):
        """Verify that the OpenAPI spec is valid JSON."""
        spec_path = project_root / "docs" / "api" / "openapi.json"
        if not spec_path.exists():
            pytest.skip("OpenAPI spec not found")

        with open(spec_path) as f:
            try:
                spec = json.load(f)
            except json.JSONDecodeError as e:
                pytest.fail(f"OpenAPI spec is not valid JSON: {e}")

        assert isinstance(spec, dict), "OpenAPI spec must be a JSON object"

    def test_openapi_spec_has_required_fields(self):
        """Verify that the OpenAPI spec has required top-level fields."""
        spec_path = project_root / "docs" / "api" / "openapi.json"
        if not spec_path.exists():
            pytest.skip("OpenAPI spec not found")

        with open(spec_path) as f:
            spec = json.load(f)

        for field in ["openapi", "info", "paths"]:
            assert field in spec, f"OpenAPI spec missing required field: {field}"

        assert "title" in spec["info"], "info.title is required"
        assert "version" in spec["info"], "info.version is required"

    def test_openapi_spec_has_paths_defined(self):
        """Verify that the OpenAPI spec has at least some paths."""
        spec_path = project_root / "docs" / "api" / "openapi.json"
        if not spec_path.exists():
            pytest.skip("OpenAPI spec not found")

        with open(spec_path) as f:
            spec = json.load(f)

        paths = spec.get("paths", {})
        assert len(paths) > 0, "OpenAPI spec should define at least one path"


class TestGeneratedOpenAPIClient:
    """Integration tests for the generated OpenAPI client schemas."""

    @pytest.fixture(autouse=True)
    def load_spec(self):
        """Load the OpenAPI spec for all tests in this class."""
        spec_path = project_root / "docs" / "api" / "openapi.json"
        if not spec_path.exists():
            pytest.skip("OpenAPI spec not found")

        with open(spec_path) as f:
            self.spec = json.load(f)

    def test_health_endpoint_exists(self):
        """Verify that the health check endpoint exists."""
        paths = self.spec.get("paths", {})
        assert "/v1/health" in paths, "Health check endpoint missing"
        assert "get" in paths["/v1/health"], "Health should support GET"

    def test_test_start_endpoint_exists(self):
        """Verify that the test start endpoint exists."""
        paths = self.spec.get("paths", {})
        assert "/v1/test/start" in paths, "Test start endpoint missing"
        assert "post" in paths["/v1/test/start"], "Test start should be POST"

    def test_auth_login_endpoint_exists(self):
        """Verify that the login endpoint exists."""
        paths = self.spec.get("paths", {})
        assert "/v1/auth/login" in paths, "Login endpoint missing"
        assert "post" in paths["/v1/auth/login"], "Login should be POST"

    def test_key_schemas_exist(self):
        """Verify that key schemas are defined."""
        schemas = self.spec.get("components", {}).get("schemas", {})
        for name in ["UserLogin", "UserResponse"]:
            assert name in schemas, f"Schema '{name}' not found"

    def test_user_login_schema_structure(self):
        """Verify UserLogin schema has expected required fields."""
        schemas = self.spec.get("components", {}).get("schemas", {})
        if "UserLogin" not in schemas:
            pytest.skip("UserLogin schema not found")

        login_schema = schemas["UserLogin"]
        properties = login_schema.get("properties", {})
        required = login_schema.get("required", [])

        assert "email" in properties, "UserLogin should have email"
        assert "password" in properties, "UserLogin should have password"
        assert "email" in required, "email should be required"
        assert "password" in required, "password should be required"

    def test_all_refs_resolve(self):
        """Verify that all $ref references in the spec resolve."""
        schemas = self.spec.get("components", {}).get("schemas", {})
        schema_names = set(schemas.keys())

        all_refs = set()
        for schema_def in schemas.values():
            all_refs.update(_collect_refs(schema_def))

        for ref in all_refs:
            if ref.startswith("#/components/schemas/"):
                ref_name = ref.split("/")[-1]
                assert ref_name in schema_names, f"Unresolved $ref: {ref}"
