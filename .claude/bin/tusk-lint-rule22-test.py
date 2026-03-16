#!/usr/bin/env python3
"""
Unit tests for rule22_provider_model_validation in tusk-lint.py.

Usage: python3 tusk-lint-rule22-test.py
       python3 -m pytest tusk-lint-rule22-test.py -v
"""

import importlib.util
import os
import shutil
import tempfile
import textwrap
import unittest


def _load_lint_module():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "tusk-lint.py")
    spec = importlib.util.spec_from_file_location("tusk_lint", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_lint = _load_lint_module()
rule22 = _lint.rule22_provider_model_validation


def _make_config_tree(test_case, judges_yaml=None, generators_yaml=None, extra_files=None):
    """Create a temporary directory tree with question-service/config/ files.

    Registers cleanup on test_case so the directory is removed after the test.
    extra_files: dict of {filename: content} for additional files in config/.
    """
    tmpdir = tempfile.mkdtemp()
    test_case.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)
    config_dir = os.path.join(tmpdir, "question-service", "config")
    os.makedirs(config_dir)
    if judges_yaml is not None:
        with open(os.path.join(config_dir, "judges.yaml"), "w") as f:
            f.write(judges_yaml)
    if generators_yaml is not None:
        with open(os.path.join(config_dir, "generators.yaml"), "w") as f:
            f.write(generators_yaml)
    for fname, content in (extra_files or {}).items():
        with open(os.path.join(config_dir, fname), "w") as f:
            f.write(content)
    return tmpdir


class TestRule22ValidModel(unittest.TestCase):
    """A model that is in the provider's known list produces no warnings."""

    def test_judges_valid_model(self):
        yaml = textwrap.dedent("""\
            judges:
              math:
                model: claude-sonnet-4-5-20250929
                provider: anthropic
        """)
        root = _make_config_tree(self, judges_yaml=yaml)
        result = rule22(root)
        self.assertEqual(result, [], f"Expected no warnings, got: {result}")

    def test_generators_valid_model(self):
        yaml = textwrap.dedent("""\
            generators:
              spatial:
                model: gpt-4o
                provider: openai
        """)
        root = _make_config_tree(self, generators_yaml=yaml)
        result = rule22(root)
        self.assertEqual(result, [], f"Expected no warnings, got: {result}")

    def test_default_judge_valid_model(self):
        yaml = textwrap.dedent("""\
            default_judge:
              model: grok-4
              provider: xai
        """)
        root = _make_config_tree(self, judges_yaml=yaml)
        result = rule22(root)
        self.assertEqual(result, [], f"Expected no warnings, got: {result}")

    def test_fallback_valid_model(self):
        yaml = textwrap.dedent("""\
            judges:
              math:
                model: claude-sonnet-4-5-20250929
                provider: anthropic
                fallback_model: grok-4
                fallback: xai
        """)
        root = _make_config_tree(self, judges_yaml=yaml)
        result = rule22(root)
        self.assertEqual(result, [], f"Expected no warnings, got: {result}")


class TestRule22UnknownModel(unittest.TestCase):
    """A model not in the provider's known list produces a warning."""

    def test_unknown_model_in_judges(self):
        yaml = textwrap.dedent("""\
            judges:
              math:
                model: claude-3-opus-stale-preview
                provider: anthropic
        """)
        root = _make_config_tree(self, judges_yaml=yaml)
        result = rule22(root)
        self.assertEqual(len(result), 1)
        self.assertIn("claude-3-opus-stale-preview", result[0])
        self.assertIn("not in anthropic's known list", result[0])

    def test_unknown_model_in_generators(self):
        yaml = textwrap.dedent("""\
            generators:
              verbal:
                model: gemini-3-pro-preview-old
                provider: google
        """)
        root = _make_config_tree(self, generators_yaml=yaml)
        result = rule22(root)
        self.assertEqual(len(result), 1)
        self.assertIn("gemini-3-pro-preview-old", result[0])

    def test_unknown_fallback_model(self):
        yaml = textwrap.dedent("""\
            generators:
              math:
                model: gpt-4o
                provider: openai
                fallback_model: gpt-99-nonexistent
                fallback: openai
        """)
        root = _make_config_tree(self, generators_yaml=yaml)
        result = rule22(root)
        self.assertEqual(len(result), 1)
        self.assertIn("gpt-99-nonexistent", result[0])
        self.assertIn("[fallback]", result[0])


class TestRule22UnknownProvider(unittest.TestCase):
    """A provider not in _PROVIDER_MODELS produces a warning."""

    def test_unknown_provider_in_judges(self):
        yaml = textwrap.dedent("""\
            judges:
              logic:
                model: cohere-command-r
                provider: cohere
        """)
        root = _make_config_tree(self, judges_yaml=yaml)
        result = rule22(root)
        self.assertEqual(len(result), 1)
        self.assertIn("unknown provider 'cohere'", result[0])

    def test_unknown_provider_in_default_generator(self):
        yaml = textwrap.dedent("""\
            default_generator:
              model: some-model
              provider: mystery_provider
        """)
        root = _make_config_tree(self, generators_yaml=yaml)
        result = rule22(root)
        self.assertEqual(len(result), 1)
        self.assertIn("unknown provider 'mystery_provider'", result[0])


class TestRule22MissingFile(unittest.TestCase):
    """Missing YAML files are silently skipped (no warnings, no errors)."""

    def test_only_generators_present_judges_missing(self):
        valid_yaml = textwrap.dedent("""\
            generators:
              math:
                model: gpt-4o
                provider: openai
        """)
        root = _make_config_tree(self, generators_yaml=valid_yaml)
        result = rule22(root)
        self.assertEqual(result, [])

    def test_only_judges_present_generators_missing(self):
        valid_yaml = textwrap.dedent("""\
            judges:
              math:
                model: claude-sonnet-4-5-20250929
                provider: anthropic
        """)
        root = _make_config_tree(self, judges_yaml=valid_yaml)
        result = rule22(root)
        self.assertEqual(result, [])

    def test_both_files_missing(self):
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)
        result = rule22(tmpdir)
        self.assertEqual(result, [])


class TestRule22MalformedYaml(unittest.TestCase):
    """Unparseable YAML is handled gracefully — one warning, no crash."""

    def test_malformed_yaml_judges(self):
        bad_yaml = "judges:\n  math:\n    - invalid: [unclosed\n"
        root = _make_config_tree(self, judges_yaml=bad_yaml)
        result = rule22(root)
        self.assertEqual(len(result), 1)
        self.assertIn("could not parse YAML", result[0])

    def test_malformed_yaml_generators(self):
        bad_yaml = ": :\n  bad: yaml: content:"
        root = _make_config_tree(self, generators_yaml=bad_yaml)
        result = rule22(root)
        self.assertEqual(len(result), 1)
        self.assertIn("could not parse YAML", result[0])

    def test_non_dict_root(self):
        # YAML that parses to a non-dict (e.g., a list) should be silently skipped.
        yaml = "- item1\n- item2\n"
        root = _make_config_tree(self, judges_yaml=yaml)
        result = rule22(root)
        self.assertEqual(result, [])


class TestRule22StructuralFilter(unittest.TestCase):
    """Structural filter: only YAML files with model-mapping section keys are validated."""

    def test_non_model_yaml_is_skipped(self):
        # A config file with no judges/generators/default_judge/default_generator keys
        # should be silently skipped even if it contains 'model' fields.
        alerting_yaml = textwrap.dedent("""\
            inventory:
              thresholds:
                healthy_min: 50
                warning_min: 20
              model: some-value
              provider: some-provider
        """)
        root = _make_config_tree(self, extra_files={"alerting.yaml": alerting_yaml})
        result = rule22(root)
        self.assertEqual(result, [], f"Non-model config should be skipped, got: {result}")

    def test_new_model_yaml_is_caught(self):
        # A new config file (not judges.yaml or generators.yaml) that has a judges
        # top-level key should be validated automatically.
        new_config_yaml = textwrap.dedent("""\
            judges:
              logic:
                model: claude-stale-model
                provider: anthropic
        """)
        root = _make_config_tree(self, extra_files={"new-model-config.yaml": new_config_yaml})
        result = rule22(root)
        self.assertEqual(len(result), 1)
        self.assertIn("claude-stale-model", result[0])
        self.assertIn("new-model-config.yaml", result[0])

    def test_new_model_yaml_valid_model_passes(self):
        # A new config file with a valid model+provider should produce no warnings.
        new_config_yaml = textwrap.dedent("""\
            generators:
              custom:
                model: gpt-4o
                provider: openai
        """)
        root = _make_config_tree(self, extra_files={"custom-generators.yaml": new_config_yaml})
        result = rule22(root)
        self.assertEqual(result, [], f"Valid model in new config file should pass, got: {result}")

    def test_non_model_yaml_alongside_model_yaml(self):
        # Non-model files should be skipped while model files are still validated.
        valid_yaml = textwrap.dedent("""\
            judges:
              math:
                model: claude-sonnet-4-5-20250929
                provider: anthropic
        """)
        non_model_yaml = textwrap.dedent("""\
            sentry:
              enabled: true
              dsn: https://example.sentry.io
        """)
        root = _make_config_tree(
            self,
            judges_yaml=valid_yaml,
            extra_files={"observability.yaml": non_model_yaml},
        )
        result = rule22(root)
        self.assertEqual(result, [], f"Only model files should be validated, got: {result}")

    def test_structural_key_present_but_null_section(self):
        # A glob-discovered file with a structural key (e.g. judges) that maps to null
        # should be handled gracefully — no crash, no spurious warnings.
        yaml = "judges:\n"  # key exists but value is null
        root = _make_config_tree(self, extra_files={"null-section.yaml": yaml})
        result = rule22(root)
        self.assertEqual(result, [], f"Null section value should produce no warnings, got: {result}")


class TestRule22MultiFileAggregation(unittest.TestCase):
    """Warnings from judges.yaml and generators.yaml are concatenated into one result list."""

    def test_bad_models_in_both_files_produces_two_warnings(self):
        judges_yaml = textwrap.dedent("""\
            judges:
              math:
                model: claude-3-opus-stale-preview
                provider: anthropic
        """)
        generators_yaml = textwrap.dedent("""\
            generators:
              verbal:
                model: gemini-3-pro-preview-old
                provider: google
        """)
        root = _make_config_tree(self, judges_yaml=judges_yaml, generators_yaml=generators_yaml)
        result = rule22(root)
        self.assertEqual(len(result), 2, f"Expected 2 warnings (one per file), got: {result}")
        combined = "\n".join(result)
        self.assertIn("claude-3-opus-stale-preview", combined)
        self.assertIn("gemini-3-pro-preview-old", combined)


if __name__ == "__main__":
    unittest.main(verbosity=2)
