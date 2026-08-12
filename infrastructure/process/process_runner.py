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


# 传给 Claude CLI 子进程时剥离的敏感环境变量前缀/名称。
# Claude Code 的 Bash 子进程会继承这些变量，提示注入的 task 可
# printenv/curl 外传；宿主其他服务的密钥（数据库、代理、云厂商等）
# 也不应暴露给 agent。
_SENSITIVE_ENV_PREFIXES = (
    "ANTHROPIC_",
    "AWS_",
    "AZURE_",
    "GOOGLE_",
    "GCP_",
    "OPENAI_",
    "DATABASE_",
    "DB_",
    "MYSQL_",
    "POSTGRES_",
    "REDIS_",
    "MONGO_",
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "PASSWD",
    "API_KEY",
    "APIKEY",
    "ACCESS_KEY",
    "PRIVATE_KEY",
)
# 传子进程时需剥离的敏感变量名（精确匹配）。
_SENSITIVE_ENV_EXACT = frozenset(
    {"USER", "USERNAME", "LOGNAME", "MAIL", "SSH_AUTH_SOCK", "PGPASSWORD"}
)


def sanitize_env_for_subprocess(env: dict[str, str]) -> dict[str, str]:
    """Copy env and drop secrets that the Claude agent must not inherit.

    ``run``/``run_stream`` 从 ``os.environ.copy()`` 构造子进程环境。此函数
    移除含密钥的变量（凭据、令牌、密钥前缀）。HOME/USERPROFILE 是隔离模式
    的键（指向 workspace），必须保留；PATH 等必要变量也保留。
    """
    cleaned = {}
    for key, value in env.items():
        upper = key.upper()
        if upper in _SENSITIVE_ENV_EXACT:
            continue
        if any(prefix in upper for prefix in _SENSITIVE_ENV_PREFIXES):
            continue
        cleaned[key] = value
    return cleaned


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

    async def _create_proc(self, cmd_args: list[str], cwd: Path):
        """启动子进程（不传 env，run 方法单独传）。"""
        return await asyncio.create_subprocess_exec(
            *cmd_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd),
            **_subprocess_kwargs(),
        )

    async def _iter_stdout_lines(self, proc) -> AsyncIterator[bytes]:
        """逐行读取子进程 stdout。"""
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            yield line

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

        # Merge with current environment, then drop secrets the agent
        # must not inherit (API keys, tokens, database credentials).
        full_env = os.environ.copy()
        if env:
            full_env.update(env)
        full_env = sanitize_env_for_subprocess(full_env)

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

        proc = await self._create_proc(cmd_args, cwd)

        try:
            deadline = asyncio.get_event_loop().time() + timeout

            async for line in self._iter_stdout_lines(proc):
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
        proc = await self._create_proc(cmd_args, cwd)
        return proc, self._iter_stdout_lines(proc)


__all__ = ["ProcessRunner"]
