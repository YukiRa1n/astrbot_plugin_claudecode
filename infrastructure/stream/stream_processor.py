"""
Stream Processor - Processes streaming output with callbacks.

Single responsibility: Orchestrate streaming execution with progress callbacks.
Composes ChunkParser and ProcessRunner.
"""

import asyncio
import time
import logging
from typing import Optional, TYPE_CHECKING

from .chunk_parser import ChunkParser
from ...types import (
    Result,
    ExecutionResult,
    ExecutionError,
    ErrorCode,
    ProgressCallback,
    ok,
    err,
)

if TYPE_CHECKING:
    from ..process.process_runner import ProcessRunner

logger = logging.getLogger("astrbot")


class StreamProcessor:
    """
    Processes streaming output with progress callbacks.

    Orchestrates:
    - ProcessRunner for subprocess execution
    - ChunkParser for line parsing
    - Progress callbacks for real-time updates
    """

    def __init__(
        self,
        process_runner: "ProcessRunner" = None,
        chunk_parser: ChunkParser = None,
    ):
        """
        Initialize stream processor.

        Args:
            process_runner: Optional process runner (creates default if None)
            chunk_parser: Optional chunk parser (creates default if None)
        """
        from ..process.process_runner import ProcessRunner as DefaultRunner

        self._process_runner = process_runner or DefaultRunner()
        self._chunk_parser = chunk_parser or ChunkParser()

    async def process(
        self,
        proc: asyncio.subprocess.Process,
        on_progress: Optional[ProgressCallback],
        start_time: float,
    ) -> Result[ExecutionResult, ExecutionError]:
        """
        Process streaming output from subprocess.

        Args:
            proc: Running subprocess with stdout pipe
            on_progress: Optional callback for progress updates
            start_time: Start time for duration calculation

        Returns:
            Result containing ExecutionResult or ExecutionError
        """
        accumulated_output = []
        chunk_count = 0

        try:
            # Read stdout line by line
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break

                line_text = line.decode("utf-8", errors="ignore").strip()
                if not line_text:
                    continue

                chunk_count += 1

                # Parse line into chunk
                chunk = self._chunk_parser.parse_line(line_text)

                if chunk:
                    # Invoke callback if provided
                    if on_progress:
                        try:
                            on_progress(chunk)
                        except Exception as e:
                            logger.warning(f"[StreamProcessor] Callback failed: {e}")

                    # Accumulate content
                    if chunk.content:
                        accumulated_output.append(chunk.content)

            # Wait for process to complete
            await proc.wait()
            stderr = await proc.stderr.read()
            stderr_text = stderr.decode("utf-8", errors="ignore")

            duration_ms = (time.time() - start_time) * 1000

            # Build final result
            final_output = "\n".join(accumulated_output)
            result = ExecutionResult(
                output=final_output,
                cost_usd=0.0,  # Cost info not available in stream mode
                session_id="",
                duration_ms=duration_ms,
                metadata={"chunk_count": chunk_count, "stderr": stderr_text},
            )

            logger.debug(
                f"[StreamProcessor] Completed: chunks={chunk_count}, duration_ms={duration_ms:.2f}"
            )
            return ok(result)

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"[StreamProcessor] Failed: {e}")
            return err(
                ExecutionError(
                    code=ErrorCode.UNKNOWN,
                    message=f"Stream processing error: {e}",
                    details={
                        "exception_type": type(e).__name__,
                        "accumulated_output": "\n".join(accumulated_output),
                        "chunk_count": chunk_count,
                    },
                )
            )


__all__ = ["StreamProcessor"]
