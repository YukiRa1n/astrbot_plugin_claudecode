"""
Chunk Parser - Parses streaming output chunks.

Single responsibility: Parse individual stream-json lines into StreamChunk.
No I/O, no accumulation - pure line-by-line transformation.
"""

import json
import logging
import time

from ...models import ChunkType, StreamChunk

logger = logging.getLogger("astrbot")


class ChunkParser:
    """
    Parses streaming output chunks.

    Implements IChunkParser interface.
    Pure function-like class: no side effects, deterministic output.
    """

    def parse_line(self, line: str) -> StreamChunk | None:
        """
        Parse a single line of streaming output.

        Args:
            line: Raw line from stdout (already stripped)

        Returns:
            StreamChunk if parseable, None if empty/invalid
        """
        if not line:
            return None

        try:
            chunk_data = json.loads(line)
            chunk_type = self._determine_chunk_type(chunk_data)
            content = self._extract_content(chunk_data)

            return StreamChunk(
                chunk_type=chunk_type,
                content=content,
                timestamp=time.time(),
                metadata={"type": chunk_data.get("type", "unknown")},
            )

        except json.JSONDecodeError:
            # Not JSON, treat as raw text chunk
            return StreamChunk(
                chunk_type=ChunkType.STATUS,
                content=line,
                timestamp=time.time(),
                metadata={"raw": True},
            )

    def _determine_chunk_type(self, chunk_data: dict) -> ChunkType:
        """
        Determine the type of a stream chunk.

        Args:
            chunk_data: Parsed JSON chunk data

        Returns:
            ChunkType enum value
        """
        # Check for type field
        if "type" in chunk_data:
            chunk_type_str = chunk_data["type"].lower()
            if "think" in chunk_type_str:
                return ChunkType.THINKING
            elif "tool" in chunk_type_str:
                return ChunkType.TOOL_USE
            elif "error" in chunk_type_str:
                return ChunkType.ERROR
            elif "result" in chunk_type_str:
                return ChunkType.RESULT

        # Check for error indicators
        if chunk_data.get("is_error") or "error" in chunk_data:
            return ChunkType.ERROR

        # Check for result indicators
        if "result" in chunk_data or "output" in chunk_data:
            return ChunkType.RESULT

        # Default to status
        return ChunkType.STATUS

    def _extract_content(self, chunk_data: dict) -> str:
        """
        Extract content from a stream chunk.

        Args:
            chunk_data: Parsed JSON chunk data

        Returns:
            Extracted content string
        """
        # Try common content fields in priority order
        for field in ["content", "text", "message", "result", "output"]:
            if field in chunk_data and chunk_data[field]:
                return str(chunk_data[field])

        # Fallback to JSON string
        return json.dumps(chunk_data)


__all__ = ["ChunkParser"]
