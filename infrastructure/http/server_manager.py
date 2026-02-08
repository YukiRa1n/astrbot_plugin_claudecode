"""
Server Manager - Cross-platform HTTP server management.

Single responsibility: Start and manage HTTP server for web deployment.
Fixes pgrep compatibility issue in containers.
"""

import asyncio
import logging
import socket
import sys
from pathlib import Path
from typing import Optional

from ...utils.platform_compat import (
    is_process_running,
    start_background_process,
    terminate_process,
)

logger = logging.getLogger("astrbot")


class ServerManager:
    """
    Manages HTTP server for web deployment.

    Cross-platform compatible (Windows, Linux, containers).
    """

    def __init__(self, workspace: Path, port: int = 6200):
        """
        Initialize server manager.

        Args:
            workspace: Directory to serve
            port: HTTP server port
        """
        self.workspace = workspace
        self.port = port
        self._process: Optional[asyncio.subprocess.Process] = None
        self._pid: Optional[int] = None

    async def start(self) -> bool:
        """
        Start HTTP server if not already running.

        Returns:
            True if server is running (started or already running)
        """
        if not self.port:
            logger.debug("[ServerManager] Port not configured, skipping")
            return False

        if self._is_port_in_use():
            logger.info(f"[ServerManager] Port {self.port} already in use")
            return True

        # Check if already running (cross-platform)
        pattern = f"http.server {self.port}"
        if await is_process_running(pattern):
            logger.info(f"[ServerManager] Server already running on port {self.port}")
            return True

        # Start server
        return await self._start_server()

    async def _start_server(self) -> bool:
        """Start the HTTP server process."""
        try:
            cmd = [
                sys.executable or "python3",
                "-m",
                "http.server",
                str(self.port),
                "--bind",
                "0.0.0.0",
            ]

            pid = await start_background_process(cmd, self.workspace)

            if pid:
                self._pid = pid
                logger.info(
                    f"[ServerManager] Started on port {self.port}, serving: {self.workspace}"
                )
                return True
            else:
                logger.warning("[ServerManager] Failed to start server")
                return False

        except Exception as e:
            logger.warning(f"[ServerManager] Failed to start: {e}")
            return False

    async def stop(self) -> bool:
        """
        Stop the HTTP server.

        Returns:
            True if stopped successfully
        """
        if self._process:
            try:
                self._process.terminate()
                await self._process.wait()
                self._process = None
                logger.info("[ServerManager] Server stopped")
                return True
            except Exception as e:
                logger.warning(f"[ServerManager] Failed to stop: {e}")
                return False
        if self._pid:
            if terminate_process(self._pid):
                logger.info("[ServerManager] Server stopped via PID")
                self._pid = None
                return True
            logger.warning("[ServerManager] Failed to stop server via PID")
            return False
        return True

    def _is_port_in_use(self) -> bool:
        """Check if port is in use (local check)."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.5)
                return sock.connect_ex(("127.0.0.1", self.port)) == 0
        except Exception:
            return False


__all__ = ["ServerManager"]
