"""
Test Chunk Parser - Unit tests for ChunkParser.
"""

import pytest
import json

from ...infrastructure.stream.chunk_parser import ChunkParser
from ...types import ChunkType


class TestChunkParser:
    """Tests for ChunkParser."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = ChunkParser()

    def test_parse_thinking_chunk(self):
        """Test parsing thinking chunk."""
        line = json.dumps({"type": "thinking", "content": "Analyzing..."})

        chunk = self.parser.parse_line(line)

        assert chunk is not None
        assert chunk.chunk_type == ChunkType.THINKING
        assert chunk.content == "Analyzing..."

    def test_parse_tool_use_chunk(self):
        """Test parsing tool use chunk."""
        line = json.dumps({"type": "tool_use", "content": "Reading file.py"})

        chunk = self.parser.parse_line(line)

        assert chunk is not None
        assert chunk.chunk_type == ChunkType.TOOL_USE
        assert chunk.content == "Reading file.py"

    def test_parse_result_chunk(self):
        """Test parsing result chunk."""
        line = json.dumps({"type": "result", "content": "Task completed"})

        chunk = self.parser.parse_line(line)

        assert chunk is not None
        assert chunk.chunk_type == ChunkType.RESULT
        assert chunk.content == "Task completed"

    def test_parse_error_chunk(self):
        """Test parsing error chunk."""
        line = json.dumps({"type": "error", "content": "Something failed"})

        chunk = self.parser.parse_line(line)

        assert chunk is not None
        assert chunk.chunk_type == ChunkType.ERROR
        assert chunk.content == "Something failed"

    def test_parse_error_by_is_error_field(self):
        """Test parsing error by is_error field."""
        line = json.dumps({"is_error": True, "message": "Error occurred"})

        chunk = self.parser.parse_line(line)

        assert chunk is not None
        assert chunk.chunk_type == ChunkType.ERROR

    def test_parse_result_by_result_field(self):
        """Test parsing result by result field."""
        line = json.dumps({"result": "Done"})

        chunk = self.parser.parse_line(line)

        assert chunk is not None
        assert chunk.chunk_type == ChunkType.RESULT
        assert chunk.content == "Done"

    def test_parse_status_default(self):
        """Test default to status type."""
        line = json.dumps({"some_field": "some_value"})

        chunk = self.parser.parse_line(line)

        assert chunk is not None
        assert chunk.chunk_type == ChunkType.STATUS

    def test_parse_raw_text(self):
        """Test parsing non-JSON text."""
        line = "This is raw text output"

        chunk = self.parser.parse_line(line)

        assert chunk is not None
        assert chunk.chunk_type == ChunkType.STATUS
        assert chunk.content == "This is raw text output"
        assert chunk.metadata.get("raw") is True

    def test_parse_empty_line(self):
        """Test parsing empty line returns None."""
        chunk = self.parser.parse_line("")

        assert chunk is None

    def test_parse_content_extraction_priority(self):
        """Test content extraction field priority."""
        # 'content' has highest priority
        line = json.dumps({
            "content": "from_content",
            "text": "from_text",
            "message": "from_message",
        })

        chunk = self.parser.parse_line(line)

        assert chunk.content == "from_content"

    def test_parse_text_field_extraction(self):
        """Test text field extraction when content missing."""
        line = json.dumps({
            "text": "from_text",
            "message": "from_message",
        })

        chunk = self.parser.parse_line(line)

        assert chunk.content == "from_text"

    def test_parse_timestamp_set(self):
        """Test timestamp is set on chunk."""
        line = json.dumps({"type": "status", "content": "test"})

        chunk = self.parser.parse_line(line)

        assert chunk.timestamp > 0
