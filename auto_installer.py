"""
Claude Code 自动安装器
负责检测和安装 Claude Code CLI
"""
import asyncio
import shutil
from pathlib import Path
from typing import Tuple, List, Optional
from astrbot.api import logger


class ClaudeInstaller:
    """Claude Code CLI 安装器"""

    PACKAGE_NAME = '@anthropic-ai/claude-code'

    def __init__(self):
        self.claude_path: Optional[str] = None

    def is_installed(self) -> bool:
        """检查 Claude Code 是否已安装"""
        self.claude_path = shutil.which('claude')
        return self.claude_path is not None

    async def get_version(self) -> Optional[str]:
        """获取已安装的版本"""
        if not self.is_installed():
            return None

        try:
            proc = await asyncio.create_subprocess_exec(
                'claude', '--version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            return stdout.decode().strip()
        except Exception:
            return None

    async def install(self) -> Tuple[bool, str]:
        """安装 Claude Code CLI"""
        logger.info('[ClaudeInstaller] Starting installation...')

        # 检查 npm
        if not shutil.which('npm'):
            return False, 'npm not found. Please install Node.js first.'

        try:
            proc = await asyncio.create_subprocess_exec(
                'npm', 'install', '-g', self.PACKAGE_NAME,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=180
            )

            if proc.returncode == 0:
                version = await self.get_version()
                msg = f'Installed successfully: {version}'
                logger.info(f'[ClaudeInstaller] {msg}')
                return True, msg
            else:
                error = stderr.decode()
                logger.error(f'[ClaudeInstaller] Install failed: {error}')
                return False, f'Install failed: {error}'

        except asyncio.TimeoutError:
            return False, 'Installation timeout (180s)'
        except Exception as e:
            return False, f'Install error: {str(e)}'

    async def install_skill(self, skill_name: str) -> Tuple[bool, str]:
        """安装 Claude Code Skill"""
        if not self.is_installed():
            return False, 'Claude Code not installed'

        try:
            proc = await asyncio.create_subprocess_exec(
                'claude', 'mcp', 'add', skill_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=60
            )

            if proc.returncode == 0:
                return True, f'Skill {skill_name} installed'
            return False, stderr.decode()

        except Exception as e:
            return False, str(e)

    async def ensure_installed(self, auto_install: bool = True) -> Tuple[bool, str]:
        """确保 Claude Code 已安装"""
        if self.is_installed():
            version = await self.get_version()
            return True, f'Already installed: {version}'

        if not auto_install:
            return False, 'Claude Code not installed (auto_install disabled)'

        return await self.install()
