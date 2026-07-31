"""
Test ServerManager - dist-only serving boundary.
"""

from pathlib import Path

import pytest

from ...infrastructure.http.server_manager import ServerManager


class TestServerManager:
    """Tests for ServerManager security boundary."""

    def test_serve_dir_is_dist_subdirectory(self):
        """HTTP 服务只暴露 workspace/dist/，绝不暴露含密钥的整个 workspace。"""
        ws = Path("/tmp/workspace")
        mgr = ServerManager(ws, port=6200)
        assert mgr.serve_dir == ws / "dist"
        # workspace 根目录绝不能作为服务目录
        assert mgr.serve_dir != ws

    @pytest.mark.asyncio
    async def test_start_skips_when_dist_missing(self):
        """dist 目录不存在时不应启动服务器。"""
        mgr = ServerManager(Path("/nonexistent/ws"), port=6200)
        result = await mgr.start()
        assert result is False
