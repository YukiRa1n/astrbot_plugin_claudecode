"""
Process Runner - Executes subprocess commands.

Single responsibility: Execute commands and return raw output.
No parsing, no business logic - pure I/O.
"""

import asyncio
import logging
import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

from ...utils import resolve_command

logger = logging.getLogger("astrbot")


def _resolve_cmd_args(cmd_args: list[str]) -> list[str]:
    if not cmd_args:
        return cmd_args
    resolved = resolve_command(cmd_args[0])
    if resolved == cmd_args[0]:
        return cmd_args
    return [resolved, *cmd_args[1:]]


def _subprocess_kwargs() -> dict:
    """Return extra kwargs for asyncio.create_subprocess_exec.

    On Windows, CREATE_NO_WINDOW prevents a console window from flashing
    when AstrBot runs as a service / pythonw.
    """
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}


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
        env: dict[str, str] = None,
    ) -> tuple[str, str, int]:
        """
        Run command and return output.

        Args:
            cmd_args: Command arguments
            cwd: Working directory
            timeout: Timeout in seconds
            env: Optional environment variables

        Returns:
            Tuple of (stdout, stderr, returncode)
        """
        cmd_args = _resolve_cmd_args(cmd_args)
        logger.debug(f"[ProcessRunner] Executing: {cmd_args[0]} in {cwd}")

        # Merge with current environment
        full_env = os.environ.copy()
        if env:
            full_env.update(env)

        proc = await asyncio.create_subprocess_exec(
            *cmd_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd),
            env=full_env,
            **_subprocess_kwargs(),
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
            raise

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

        proc = await asyncio.create_subprocess_exec(
            *cmd_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd),
            **_subprocess_kwargs(),
        )

        try:

            async def read_with_timeout():
                while True:
                    line = await proc.stdout.readline()
                    if not line:
                        break
                    yield line

            deadline = asyncio.get_event_loop().time() + timeout

            async for line in read_with_timeout():
                if asyncio.get_event_loop().time() > deadline:
                    raise asyncio.TimeoutError()
                yield line

            await proc.wait()

        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            try:
                await proc.wait()
            except Exception:
                pass
            raise
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
        cmd_args = _resolve_cmd_args(cmd_args)
        proc = await asyncio.create_subprocess_exec(
            *cmd_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd),
            **_subprocess_kwargs(),
        )

        async def line_iterator():
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                yield line

        return proc, line_iterator()


__all__ = ["ProcessRunner"]
