#!/usr/bin/env python3
"""
Unit tests for rule22_provider_model_validation in tusk-lint.py.

Usage: python3 tusk-lint-rule22-test.py
       python3 -m pytest tusk-lint-rule22-test.py -v
"""

import importlib.util
import os
import sys
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


def _make_config_tree(judges_yaml=None, generators_yaml=None):
    """Create a temporary directory tree with question-service/config/ files."""
    tmpdir = tempfile.mkdtemp()
    config_dir = os.path.join(tmpdir, "question-service", "config")
    os.makedirs(config_dir)
    if judges_yaml is not None:
        with open(os.path.join(config_dir, "judges.yaml"), "w") as f:
            f.write(judges_yaml)
    if generators_yaml is not None:
        with open(os.path.join(config_dir, "generators.yaml"), "w") as f:
            f.write(generators_yaml)
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
        root = _make_config_tree(judges_yaml=yaml)
        result = rule22(root)
        self.assertEqual(result, [], f"Expected no warnings, got: {result}")

    def test_generators_valid_model(self):
        yaml = textwrap.dedent("""\
            generators:
              spatial:
                model: gpt-4o
                provider: openai
        """)
        root = _make_config_tree(generators_yaml=yaml)
        result = rule22(root)
        self.assertEqual(result, [], f"Expected no warnings, got: {result}")

    def test_default_judge_valid_model(self):
        yaml = textwrap.dedent("""\
            default_judge:
              model: grok-4
              provider: xai
        """)
        root = _make_config_tree(judges_yaml=yaml)
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
        root = _make_config_tree(judges_yaml=yaml)
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
        root = _make_config_tree(judges_yaml=yaml)
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
        root = _make_config_tree(generators_yaml=yaml)
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
        root = _make_config_tree(generators_yaml=yaml)
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
        root = _make_config_tree(judges_yaml=yaml)
        result = rule22(root)
        self.assertEqual(len(result), 1)
        self.assertIn("unknown provider 'cohere'", result[0])

    def test_unknown_provider_in_default_generator(self):
        yaml = textwrap.dedent("""\
            default_generator:
              model: some-model
              provider: mystery_provider
        """)
        root = _make_config_tree(generators_yaml=yaml)
        result = rule22(root)
        self.assertEqual(len(result), 1)
        self.assertIn("unknown provider 'mystery_provider'", result[0])


class TestRule22MissingFile(unittest.TestCase):
    """Missing YAML files are silently skipped (no warnings, no errors)."""

    def test_missing_judges_yaml(self):
        root = _make_config_tree(generators_yaml=None)  # neither file written
        result = rule22(root)
        self.assertEqual(result, [])

    def test_missing_generators_yaml(self):
        root = _make_config_tree(judges_yaml=None)
        result = rule22(root)
        self.assertEqual(result, [])

    def test_both_files_missing(self):
        tmpdir = tempfile.mkdtemp()  # no config dir at all
        result = rule22(tmpdir)
        self.assertEqual(result, [])


class TestRule22MalformedYaml(unittest.TestCase):
    """Unparseable YAML is handled gracefully — one warning, no crash."""

    def test_malformed_yaml_judges(self):
        bad_yaml = "judges:\n  math:\n    - invalid: [unclosed\n"
        root = _make_config_tree(judges_yaml=bad_yaml)
        result = rule22(root)
        self.assertEqual(len(result), 1)
        self.assertIn("could not parse YAML", result[0])

    def test_malformed_yaml_generators(self):
        bad_yaml = ": :\n  bad: yaml: content:"
        root = _make_config_tree(generators_yaml=bad_yaml)
        result = rule22(root)
        self.assertEqual(len(result), 1)
        self.assertIn("could not parse YAML", result[0])

    def test_non_dict_root(self):
        # YAML that parses to a non-dict (e.g., a list) should be silently skipped.
        yaml = "- item1\n- item2\n"
        root = _make_config_tree(judges_yaml=yaml)
        result = rule22(root)
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
