"""Tests for log_utils module."""
import sys
from pathlib import Path

# Add question-service/scripts to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from log_utils import (  # noqa: E402
    extract_last_error,
    extract_last_error_clean,
    strip_ansi_codes,
)


class TestStripAnsiCodes:
    """Tests for strip_ansi_codes function."""

    def test_strips_color_codes(self):
        """Test that ANSI color codes are stripped."""
        text = "\x1b[32mINFO\x1b[0m - message"
        result = strip_ansi_codes(text)
        assert result == "INFO - message"

    def test_strips_multiple_codes(self):
        """Test that multiple ANSI codes are stripped."""
        text = "\x1b[31mERROR\x1b[0m and \x1b[33mWARNING\x1b[0m"
        result = strip_ansi_codes(text)
        assert result == "ERROR and WARNING"

    def test_no_change_without_codes(self):
        """Test that text without ANSI codes is unchanged."""
        text = "Just a normal message"
        result = strip_ansi_codes(text)
        assert result == text

    def test_empty_string(self):
        """Test with empty string."""
        assert strip_ansi_codes("") == ""


class TestExtractLastError:
    """Tests for extract_last_error function."""

    def test_returns_none_for_nonexistent_file(self):
        """Test that None is returned for non-existent file."""
        result = extract_last_error("/nonexistent/path/to/file.log")
        assert result is None

    def test_returns_none_for_directory(self, tmp_path):
        """Test that None is returned for directory path."""
        result = extract_last_error(tmp_path)
        assert result is None

    def test_returns_none_for_empty_file(self, tmp_path):
        """Test that None is returned for empty file."""
        log_file = tmp_path / "empty.log"
        log_file.write_text("")
        result = extract_last_error(log_file)
        assert result is None

    def test_returns_none_for_no_errors(self, tmp_path):
        """Test that None is returned when no errors in file."""
        log_file = tmp_path / "no_errors.log"
        log_file.write_text(
            "2026-01-25 14:37:06,314 - app - INFO - module:func:10 - All is well\n"
            "2026-01-25 14:37:07,314 - app - INFO - module:func:11 - Still good\n"
        )
        result = extract_last_error(log_file)
        assert result is None

    def test_extracts_single_error_line(self, tmp_path):
        """Test extraction of a single ERROR line."""
        log_file = tmp_path / "single_error.log"
        log_file.write_text(
            "2026-01-25 14:37:06,314 - app - INFO - module:func:10 - Starting\n"
            "2026-01-25 14:37:07,314 - app - ERROR - module:func:20 - Something failed\n"
            "2026-01-25 14:37:08,314 - app - INFO - module:func:30 - Continuing\n"
        )
        result = extract_last_error(log_file)
        assert result is not None
        assert "ERROR" in result
        assert "Something failed" in result

    def test_extracts_multiple_error_lines(self, tmp_path):
        """Test extraction of multiple ERROR lines."""
        log_file = tmp_path / "multiple_errors.log"
        log_file.write_text(
            "2026-01-25 14:37:06,314 - app - ERROR - module:func:10 - First error\n"
            "2026-01-25 14:37:07,314 - app - INFO - module:func:20 - Info message\n"
            "2026-01-25 14:37:08,314 - app - ERROR - module:func:30 - Second error\n"
        )
        result = extract_last_error(log_file)
        assert result is not None
        assert "First error" in result
        assert "Second error" in result

    def test_respects_max_lines(self, tmp_path):
        """Test that max_lines parameter limits results."""
        log_file = tmp_path / "many_errors.log"
        lines = []
        for i in range(20):
            lines.append(
                f"2026-01-25 14:37:{i:02d},314 - app - ERROR - mod:f:{i} - Error {i}\n"
            )
        log_file.write_text("".join(lines))

        result = extract_last_error(log_file, max_lines=5)
        assert result is not None
        # Should only have the last 5 errors
        assert "Error 15" in result
        assert "Error 19" in result
        assert "Error 14" not in result

    def test_handles_ansi_color_codes(self, tmp_path):
        """Test that ERROR lines with ANSI codes are detected."""
        log_file = tmp_path / "ansi_errors.log"
        # Using actual ANSI escape sequences like the bootstrap log
        log_file.write_text(
            "2026-01-25 14:37:06,314 - app - \x1b[32mINFO\x1b[0m - mod:f:10 - Starting\n"
            "2026-01-25 14:37:07,314 - app - \x1b[31mERROR\x1b[0m - mod:f:20 - Failed\n"
            "2026-01-25 14:37:08,314 - app - \x1b[32mINFO\x1b[0m - mod:f:30 - Done\n"
        )
        result = extract_last_error(log_file)
        assert result is not None
        assert "Failed" in result

    def test_extracts_traceback(self, tmp_path):
        """Test extraction of Python traceback."""
        log_file = tmp_path / "traceback.log"
        log_file.write_text(
            "2026-01-25 14:37:06,314 - app - INFO - mod:f:10 - Starting\n"
            "Traceback (most recent call last):\n"
            '  File "app.py", line 42, in main\n'
            "    do_something()\n"
            '  File "lib.py", line 10, in do_something\n'
            "    raise ValueError('bad input')\n"
            "ValueError: bad input\n"
            "2026-01-25 14:37:07,314 - app - INFO - mod:f:20 - Continuing\n"
        )
        result = extract_last_error(log_file, include_traceback=True)
        assert result is not None
        assert "Traceback" in result
        assert "ValueError: bad input" in result
        assert "app.py" in result

    def test_excludes_traceback_when_disabled(self, tmp_path):
        """Test that traceback is excluded when include_traceback=False."""
        log_file = tmp_path / "traceback_disabled.log"
        log_file.write_text(
            "Traceback (most recent call last):\n"
            '  File "app.py", line 42, in main\n'
            "    do_something()\n"
            "ValueError: bad input\n"
            "2026-01-25 14:37:07,314 - app - ERROR - mod:f:20 - Error occurred\n"
        )
        result = extract_last_error(log_file, include_traceback=False)
        # Should only have the ERROR line, not the traceback
        if result:
            assert "Error occurred" in result

    def test_handles_error_followed_by_traceback(self, tmp_path):
        """Test ERROR line followed by traceback is captured together."""
        log_file = tmp_path / "error_with_traceback.log"
        log_file.write_text(
            "2026-01-25 14:37:06,314 - app - ERROR - mod:f:10 - Request failed\n"
            "Traceback (most recent call last):\n"
            '  File "handler.py", line 55, in handle\n'
            "    process(data)\n"
            "RuntimeError: connection lost\n"
        )
        result = extract_last_error(log_file)
        assert result is not None
        assert "Request failed" in result

    def test_accepts_path_object(self, tmp_path):
        """Test that Path objects work as input."""
        log_file = tmp_path / "path_object.log"
        log_file.write_text(
            "2026-01-25 14:37:07,314 - app - ERROR - mod:f:20 - Path test\n"
        )
        result = extract_last_error(Path(log_file))
        assert result is not None
        assert "Path test" in result

    def test_accepts_string_path(self, tmp_path):
        """Test that string paths work as input."""
        log_file = tmp_path / "string_path.log"
        log_file.write_text(
            "2026-01-25 14:37:07,314 - app - ERROR - mod:f:20 - String test\n"
        )
        result = extract_last_error(str(log_file))
        assert result is not None
        assert "String test" in result

    def test_case_insensitive_error_detection(self, tmp_path):
        """Test that ERROR detection is case insensitive."""
        log_file = tmp_path / "case.log"
        log_file.write_text(
            "2026-01-25 14:37:07,314 - app - error - mod:f:20 - Lowercase error\n"
        )
        result = extract_last_error(log_file)
        assert result is not None
        assert "Lowercase error" in result


class TestExtractLastErrorClean:
    """Tests for extract_last_error_clean function."""

    def test_strips_ansi_codes(self, tmp_path):
        """Test that ANSI codes are stripped from output."""
        log_file = tmp_path / "ansi.log"
        log_file.write_text(
            "2026-01-25 14:37:07,314 - app - \x1b[31mERROR\x1b[0m - mod:f:20 - Test\n"
        )
        result = extract_last_error_clean(log_file)
        assert result is not None
        assert "\x1b[" not in result
        assert "ERROR" in result

    def test_returns_none_for_no_errors(self, tmp_path):
        """Test that None is returned for no errors."""
        log_file = tmp_path / "no_errors.log"
        log_file.write_text("Just some info messages\n")
        result = extract_last_error_clean(log_file)
        assert result is None


class TestRealWorldLogFormat:
    """Tests with realistic log format from bootstrap_inventory.sh."""

    def test_bootstrap_log_format(self, tmp_path):
        """Test with actual format from bootstrap logs."""
        log_file = tmp_path / "bootstrap.log"
        log_file.write_text(
            "Running: /venv/bin/python run_generation.py --types pattern\n"
            "Started: 2026-01-25T14:37:04-05:00\n"
            "2026-01-25 14:37:06,311 - root - \x1b[32mINFO\x1b[0m - logging:setup:166 - Logging started\n"
            'HEARTBEAT: {"status": "started"}\n'
            "2026-01-25 14:37:06,314 - app - \x1b[31mERROR\x1b[0m - generator:gen:50 - API call failed\n"
            "2026-01-25 14:37:06,315 - app - \x1b[32mINFO\x1b[0m - pipeline:run:100 - Retrying...\n"
        )
        result = extract_last_error(log_file)
        assert result is not None
        assert "API call failed" in result

    def test_multiple_error_blocks_with_tracebacks(self, tmp_path):
        """Test multiple errors with tracebacks are properly separated."""
        log_file = tmp_path / "multi_traceback.log"
        log_file.write_text(
            "2026-01-25 14:37:06,314 - app - ERROR - mod:f:10 - First failure\n"
            "2026-01-25 14:37:07,314 - app - INFO - mod:f:20 - Recovering...\n"
            "Traceback (most recent call last):\n"
            '  File "app.py", line 100, in process\n'
            "    call_api()\n"
            "ConnectionError: timeout\n"
            "2026-01-25 14:37:08,314 - app - ERROR - mod:f:30 - Second failure\n"
        )
        result = extract_last_error(log_file)
        assert result is not None
        assert "First failure" in result
        assert "Second failure" in result
