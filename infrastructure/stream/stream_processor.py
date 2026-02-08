"""
Stream Processor - Processes streaming output with callbacks.

Single responsibility: Orchestrate streaming execution with progress callbacks.
Composes ChunkParser and ProcessRunner.
"""

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from ...models import (
    ChunkType,
    ErrorCode,
    ExecutionError,
    ExecutionResult,
    ProgressCallback,
    Result,
    err,
    ok,
)
from .chunk_parser import ChunkParser

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
        on_progress: ProgressCallback | None,
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
        error_chunk = None

        try:
            stderr_task = (
                asyncio.create_task(proc.stderr.read())
                if proc.stderr
                else None
            )

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
                    if chunk.chunk_type == ChunkType.ERROR:
                        error_chunk = chunk
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
            stderr_text = ""
            if stderr_task:
                stderr = await stderr_task
                stderr_text = stderr.decode("utf-8", errors="ignore")

            duration_ms = (time.time() - start_time) * 1000

            if proc.returncode not in (0, None):
                return err(
                    ExecutionError(
                        code=ErrorCode.CLI_ERROR,
                        message="Claude CLI exited with non-zero status",
                        details={
                            "returncode": proc.returncode,
                            "stderr": stderr_text,
                            "chunk_count": chunk_count,
                        },
                    )
                )

            if error_chunk:
                return err(
                    ExecutionError(
                        code=ErrorCode.CLI_ERROR,
                        message=error_chunk.content or "Stream returned error chunk",
                        details={
                            "chunk_type": error_chunk.chunk_type.value,
                            "metadata": error_chunk.metadata,
                            "stderr": stderr_text,
                            "chunk_count": chunk_count,
                        },
                    )
                )

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
            if "stderr_task" in locals() and stderr_task and not stderr_task.done():
                stderr_task.cancel()
                try:
                    await stderr_task
                except Exception:
                    pass
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
