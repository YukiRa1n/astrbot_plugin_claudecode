"""
Mock Process Runner - Mock subprocess execution for testing.
"""

import asyncio
from pathlib import Path
from typing import AsyncIterator, Optional


class MockProcessRunner:
    """
    Mock process runner for testing.

    Implements IProcessRunner interface with configurable responses.
    """

    def __init__(
        self,
        stdout: str = "",
        stderr: str = "",
        returncode: int = 0,
        error: Optional[Exception] = None,
        stream_lines: list[str] = None,
    ):
        """
        Initialize mock runner.

        Args:
            stdout: Standard output to return
            stderr: Standard error to return
            returncode: Return code
            error: Optional exception to raise
            stream_lines: Lines to yield in streaming mode
        """
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.error = error
        self.stream_lines = stream_lines or []

        # Call tracking
        self.call_count = 0
        self.last_cmd_args: list[str] = []
        self.last_cwd: Optional[Path] = None
        self.last_timeout: Optional[int] = None

    async def run(
        self,
        cmd_args: list[str],
        cwd: Path,
        timeout: int,
    ) -> tuple[str, str, int]:
        """
        Mock run command.

        Records call and returns configured response.
        """
        self.call_count += 1
        self.last_cmd_args = cmd_args
        self.last_cwd = cwd
        self.last_timeout = timeout

        if self.error:
            raise self.error

        return self.stdout, self.stderr, self.returncode

    async def run_stream(
        self,
        cmd_args: list[str],
        cwd: Path,
        timeout: int,
    ) -> AsyncIterator[bytes]:
        """
        Mock streaming run.

        Yields configured stream lines.
        """
        self.call_count += 1
        self.last_cmd_args = cmd_args
        self.last_cwd = cwd
        self.last_timeout = timeout

        if self.error:
            raise self.error

        for line in self.stream_lines:
            yield (line + "\n").encode("utf-8")
            await asyncio.sleep(0)  # Yield control

    def reset(self):
        """Reset call tracking."""
        self.call_count = 0
        self.last_cmd_args = []
        self.last_cwd = None
        self.last_timeout = None


__all__ = ["MockProcessRunner"]
