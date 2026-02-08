"""
Process Runner - Executes subprocess commands.

Single responsibility: Execute commands and return raw output.
No parsing, no business logic - pure I/O.
"""

import asyncio
import logging
from pathlib import Path
from typing import AsyncIterator

from ...utils import resolve_command

logger = logging.getLogger("astrbot")


def _resolve_cmd_args(cmd_args: list[str]) -> list[str]:
    if not cmd_args:
        return cmd_args
    resolved = resolve_command(cmd_args[0])
    if resolved == cmd_args[0]:
        return cmd_args
    return [resolved, *cmd_args[1:]]


class ProcessRunner:
    """
    Executes subprocess commands.

    Implements IProcessRunner interface.
    Handles only subprocess execution, no output parsing.
    """

    async def run(
        self,
        cmd_args: list[str],
        cwd: Path,
        timeout: int,
    ) -> tuple[str, str, int]:
        """
        Run command and return output.

        Args:
            cmd_args: Command arguments
            cwd: Working directory
            timeout: Timeout in seconds

        Returns:
            Tuple of (stdout, stderr, returncode)

        Raises:
            asyncio.TimeoutError: If execution exceeds timeout
            FileNotFoundError: If command not found
            PermissionError: If permission denied
        """
        cmd_args = _resolve_cmd_args(cmd_args)
        logger.debug(f"[ProcessRunner] Executing: {cmd_args[0]} in {cwd}")

        proc = await asyncio.create_subprocess_exec(
            *cmd_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd),
        )

        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout,
        )

        stdout = stdout_bytes.decode("utf-8", errors="ignore")
        stderr = stderr_bytes.decode("utf-8", errors="ignore")

        logger.debug(f"[ProcessRunner] Completed with returncode={proc.returncode}")
        return stdout, stderr, proc.returncode

    async def run_stream(
        self,
        cmd_args: list[str],
        cwd: Path,
        timeout: int,
    ) -> AsyncIterator[bytes]:
        """
        Run command with streaming output.

        Args:
            cmd_args: Command arguments
            cwd: Working directory
            timeout: Timeout in seconds (applied to entire execution)

        Yields:
            Output lines as bytes
        """
        cmd_args = _resolve_cmd_args(cmd_args)
        logger.debug(f"[ProcessRunner] Streaming: {cmd_args[0]} in {cwd}")

        cmd_args = _resolve_cmd_args(cmd_args)
        proc = await asyncio.create_subprocess_exec(
            *cmd_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd),
        )

        try:
            async def read_with_timeout():
                while True:
                    line = await proc.stdout.readline()
                    if not line:
                        break
                    yield line

            async for line in read_with_timeout():
                yield line

            await proc.wait()

        except asyncio.CancelledError:
            proc.kill()
            await proc.wait()
            raise

    async def run_stream_with_process(
        self,
        cmd_args: list[str],
        cwd: Path,
    ) -> tuple[asyncio.subprocess.Process, AsyncIterator[bytes]]:
        """
        Start streaming process and return process handle with iterator.

        This allows caller to manage timeout and process lifecycle.

        Args:
            cmd_args: Command arguments
            cwd: Working directory

        Returns:
            Tuple of (process, line_iterator)
        """
        proc = await asyncio.create_subprocess_exec(
            *cmd_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd),
        )

        async def line_iterator():
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                yield line

        return proc, line_iterator()


__all__ = ["ProcessRunner"]
