"""
Platform Compatibility - Cross-platform utilities.

Fixes pgrep compatibility issue in containers and Windows.
"""

import asyncio
import logging
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("astrbot")


async def is_process_running(pattern: str) -> bool:
    """
    Check if a process matching pattern is running.

    Cross-platform: Uses tasklist on Windows, pgrep/ps on Unix.
    Container-safe: Falls back to ps if pgrep unavailable.

    Args:
        pattern: Process pattern to search for

    Returns:
        True if process is running
    """
    if sys.platform == "win32":
        return await _is_process_running_windows(pattern)
    else:
        return await _is_process_running_unix(pattern)


async def _is_process_running_windows(pattern: str) -> bool:
    """Check process on Windows using tasklist."""
    pattern_lower = pattern.lower()
    try:
        proc = await asyncio.create_subprocess_exec(
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-CimInstance Win32_Process -Filter \"Name='python.exe' or Name='pythonw.exe'\" | Select-Object -ExpandProperty CommandLine",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode("utf-8", errors="ignore").lower()
        if pattern_lower in output:
            return True
    except FileNotFoundError:
        logger.debug("[PlatformCompat] powershell not available, falling back")
    except Exception as e:
        logger.debug(f"[PlatformCompat] powershell failed: {e}")

    try:
        proc = await asyncio.create_subprocess_exec(
            "tasklist",
            "/FI",
            "IMAGENAME eq python*",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode("utf-8", errors="ignore").lower()

        # Check if pattern appears in command line (limited on Windows)
        # This is a best-effort check
        return pattern_lower.split()[0] in output
    except Exception as e:
        logger.debug(f"[PlatformCompat] Windows process check failed: {e}")
        return False


async def _is_process_running_unix(pattern: str) -> bool:
    """Check process on Unix using pgrep or ps."""
    # Try pgrep first
    try:
        proc = await asyncio.create_subprocess_exec(
            "pgrep",
            "-f",
            pattern,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0 and stdout.strip():
            return True
    except FileNotFoundError:
        logger.debug("[PlatformCompat] pgrep not available, trying ps")
    except Exception as e:
        logger.debug(f"[PlatformCompat] pgrep failed: {e}")

    # Fallback to ps
    try:
        proc = await asyncio.create_subprocess_exec(
            "ps",
            "aux",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode()
        return pattern in output
    except Exception as e:
        logger.debug(f"[PlatformCompat] ps failed: {e}")
        return False


async def start_background_process(cmd: list[str], cwd: Path) -> int | None:
    """
    Start a background process.

    Cross-platform: Uses appropriate method for Windows/Unix.

    Args:
        cmd: Command and arguments
        cwd: Working directory

    Returns:
        Process ID if started, None on failure
    """
    try:
        if sys.platform == "win32":
            # Windows: Use CREATE_NEW_PROCESS_GROUP
            proc = subprocess.Popen(
                cmd,
                cwd=str(cwd),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        else:
            # Unix: Use start_new_session
            proc = subprocess.Popen(
                cmd,
                cwd=str(cwd),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

        logger.debug(f"[PlatformCompat] Started background process: pid={proc.pid}")
        return proc.pid

    except Exception as e:
        logger.warning(f"[PlatformCompat] Failed to start background process: {e}")
        return None


def terminate_process(pid: int) -> bool:
    """
    Terminate a process by PID (cross-platform).

    Args:
        pid: Process ID to terminate

    Returns:
        True if termination command succeeded
    """
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            return result.returncode == 0
        os.kill(pid, signal.SIGTERM)
        return True
    except Exception as e:
        logger.warning(f"[PlatformCompat] Failed to terminate pid={pid}: {e}")
        return False


def resolve_command(command: str) -> str:
    """
    Resolve command path using PATH (cross-platform).

    On Windows, this resolves .cmd/.exe paths so subprocess can execute.
    """
    resolved = shutil.which(command)
    return resolved or command


__all__ = [
    "is_process_running",
    "start_background_process",
    "terminate_process",
    "resolve_command",
]
