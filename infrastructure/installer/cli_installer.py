"""
CLI Installer - Installs Claude Code CLI.

Single responsibility: Install and manage Claude CLI.
"""

import asyncio
import shutil
import logging
from typing import Tuple, Optional

logger = logging.getLogger("astrbot")


class CLIInstaller:
    """
    Claude Code CLI installer.

    Handles CLI installation via npm.
    """

    PACKAGE_NAME = "@anthropic-ai/claude-code"

    def __init__(self):
        self.claude_path: Optional[str] = None

    def is_installed(self) -> bool:
        """Check if Claude Code is installed."""
        self.claude_path = shutil.which("claude")
        return self.claude_path is not None

    async def get_version(self) -> Optional[str]:
        """Get installed version."""
        if not self.is_installed():
            return None
        if not self.claude_path:
            return None

        try:
            proc = await asyncio.create_subprocess_exec(
                self.claude_path,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            return stdout.decode().strip()
        except Exception as e:
            logger.warning(f"[CLIInstaller] Failed to get version: {e}")
            return None

    async def install(self) -> Tuple[bool, str]:
        """Install Claude Code CLI."""
        logger.info("[CLIInstaller] Starting installation...")

        # Check npm
        if not shutil.which("npm"):
            return False, "npm not found. Please install Node.js first."

        try:
            # Use taobao registry for faster installation in China
            proc = await asyncio.create_subprocess_exec(
                "npm",
                "install",
                "-g",
                self.PACKAGE_NAME,
                "--registry=https://registry.npmmirror.com",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)

            if proc.returncode == 0:
                version = await self.get_version()
                msg = f"Installed successfully: {version}"
                logger.info(f"[CLIInstaller] {msg}")
                return True, msg
            else:
                error = stderr.decode()
                logger.error(f"[CLIInstaller] Install failed: {error}")
                return False, f"Install failed: {error}"

        except asyncio.TimeoutError:
            return False, "Installation timeout (300s)"
        except Exception as e:
            return False, f"Install error: {str(e)}"

    async def ensure_installed(self, auto_install: bool = True) -> Tuple[bool, str]:
        """Ensure Claude Code is installed."""
        if self.is_installed():
            version = await self.get_version()
            return True, f"Already installed: {version}"

        if not auto_install:
            return False, "Claude Code not installed (auto_install disabled)"

        return await self.install()


__all__ = ["CLIInstaller"]
