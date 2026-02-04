"""
Test Output Parser - Unit tests for OutputParser.
"""

import pytest
import json

from ...infrastructure.process.output_parser import OutputParser
from ...types import ErrorCode


class TestOutputParser:
    """Tests for OutputParser."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = OutputParser()

    def test_parse_success_output(self):
        """Test parsing successful output."""
        stdout = json.dumps({
            "result": "Task completed",
            "is_error": False,
            "total_cost_usd": 0.005,
            "session_id": "sess-123",
        })

        result = self.parser.parse(stdout, "", 1000.0)

        assert result.is_ok()
        exec_result = result.unwrap()
        assert exec_result.output == "Task completed"
        assert exec_result.cost_usd == 0.005
        assert exec_result.session_id == "sess-123"
        assert exec_result.duration_ms == 1000.0

    def test_parse_error_output(self):
        """Test parsing error output."""
        stdout = json.dumps({
            "result": "Permission denied",
            "is_error": True,
            "total_cost_usd": 0.001,
            "session_id": "sess-456",
        })

        result = self.parser.parse(stdout, "", 500.0)

        assert result.is_err()
        error = result.unwrap_err()
        assert error.code == ErrorCode.CLI_ERROR
        assert "Permission denied" in error.message

    def test_parse_malformed_json_with_stderr_error(self):
        """Test parsing malformed JSON with error in stderr."""
        stdout = "Not valid JSON"
        stderr = "Error: something failed"

        result = self.parser.parse(stdout, stderr, 100.0)

        assert result.is_err()
        error = result.unwrap_err()
        assert error.code == ErrorCode.PARSE_ERROR

    def test_parse_malformed_json_fallback(self):
        """Test parsing malformed JSON falls back to raw output."""
        stdout = "Raw output without JSON"
        stderr = ""

        result = self.parser.parse(stdout, stderr, 100.0)

        assert result.is_ok()
        exec_result = result.unwrap()
        assert exec_result.output == "Raw output without JSON"
        assert exec_result.cost_usd == 0.0

    def test_parse_empty_output_with_error(self):
        """Test parsing empty output with error indicator."""
        stdout = ""
        stderr = "Error occurred"

        result = self.parser.parse(stdout, stderr, 100.0)

        assert result.is_err()
        error = result.unwrap_err()
        assert error.code == ErrorCode.PARSE_ERROR

    def test_parse_preserves_metadata(self):
        """Test that raw data is preserved in metadata."""
        data = {
            "result": "Done",
            "is_error": False,
            "total_cost_usd": 0.01,
            "session_id": "sess-789",
            "extra_field": "extra_value",
        }
        stdout = json.dumps(data)

        result = self.parser.parse(stdout, "", 200.0)

        assert result.is_ok()
        exec_result = result.unwrap()
        assert "raw_data" in exec_result.metadata
        assert exec_result.metadata["raw_data"]["extra_field"] == "extra_value"
