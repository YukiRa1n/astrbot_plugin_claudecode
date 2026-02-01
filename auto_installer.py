"""
Claude Code 自动安装器
负责检测和安装 Claude Code CLI
"""
import asyncio
import json
import shutil
from pathlib import Path
from typing import Tuple, List, Optional
from datetime import datetime
from astrbot.api import logger


class ClaudeInstaller:
    """Claude Code CLI 安装器"""

    PACKAGE_NAME = '@anthropic-ai/claude-code'
    OFFICIAL_MARKETPLACE = 'anthropics/claude-plugins-official'
    MARKETPLACE_HTTPS_URL = 'https://github.com/anthropics/claude-plugins-official.git'
    CLAUDE_DIR = Path.home() / '.claude'

    def __init__(self):
        self.claude_path: Optional[str] = None
        self._marketplace_ready = False

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

    async def has_marketplace(self) -> bool:
        """检查是否已配置 marketplace"""
        try:
            proc = await asyncio.create_subprocess_exec(
                'claude', 'plugin', 'marketplace', 'list',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            output = stdout.decode()
            return 'claude-plugins-official' in output
        except Exception:
            return False

    async def add_marketplace(self) -> Tuple[bool, str]:
        """添加官方 marketplace（带备用方案）"""
        logger.info('[ClaudeInstaller] Adding official marketplace...')

        # 先尝试使用 claude 命令
        try:
            proc = await asyncio.create_subprocess_exec(
                'claude', 'plugin', 'marketplace', 'add',
                self.OFFICIAL_MARKETPLACE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=120
            )
            if proc.returncode == 0:
                return True, 'Marketplace added via claude command'
        except Exception as e:
            logger.warning(f'[ClaudeInstaller] Claude command failed: {e}')

        # 备用方案：手动克隆并配置
        return await self._manual_add_marketplace()

    async def _manual_add_marketplace(self) -> Tuple[bool, str]:
        """手动克隆并配置 marketplace（备用方案）"""
        logger.info('[ClaudeInstaller] Using manual marketplace setup...')

        plugins_dir = self.CLAUDE_DIR / 'plugins'
        marketplaces_dir = plugins_dir / 'marketplaces'
        target_dir = marketplaces_dir / 'claude-plugins-official'
        config_file = plugins_dir / 'known_marketplaces.json'

        # 创建目录
        marketplaces_dir.mkdir(parents=True, exist_ok=True)

        # 如果目录已存在，跳过克隆
        if not target_dir.exists():
            try:
                proc = await asyncio.create_subprocess_exec(
                    'git', 'clone', '--depth', '1',
                    self.MARKETPLACE_HTTPS_URL, str(target_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await asyncio.wait_for(proc.communicate(), timeout=120)
                if proc.returncode != 0:
                    return False, 'Git clone failed'
            except Exception as e:
                return False, f'Git clone error: {e}'

        # 创建配置文件
        config = {
            'claude-plugins-official': {
                'source': {'source': 'github', 'repo': self.OFFICIAL_MARKETPLACE},
                'installLocation': str(target_dir),
                'lastUpdated': datetime.utcnow().isoformat() + 'Z'
            }
        }
        config_file.write_text(json.dumps(config, indent=2))
        logger.info('[ClaudeInstaller] Marketplace configured manually')
        return True, 'Marketplace added manually'

    async def update_marketplace(self) -> Tuple[bool, str]:
        """更新 marketplace"""
        try:
            proc = await asyncio.create_subprocess_exec(
                'claude', 'plugin', 'marketplace', 'update',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=60
            )
            if proc.returncode == 0:
                return True, 'Marketplace updated'
            return False, stderr.decode()
        except Exception as e:
            return False, str(e)

    async def ensure_marketplace(self) -> Tuple[bool, str]:
        """确保 marketplace 已配置并更新"""
        if self._marketplace_ready:
            return True, 'Marketplace ready (cached)'

        if not await self.has_marketplace():
            ok, msg = await self.add_marketplace()
            if not ok:
                return False, f'Failed to add marketplace: {msg}'
            logger.info(f'[ClaudeInstaller] {msg}')

        ok, msg = await self.update_marketplace()
        if ok:
            self._marketplace_ready = True
            logger.info(f'[ClaudeInstaller] {msg}')
        return ok, msg

    async def install_skill(self, skill_name: str) -> Tuple[bool, str]:
        """安装 Claude Code Skill/Plugin"""
        if not self.is_installed():
            return False, 'Claude Code not installed'

        # 确保 marketplace 已配置
        ok, msg = await self.ensure_marketplace()
        if not ok:
            return False, f'Marketplace not ready: {msg}'

        try:
            proc = await asyncio.create_subprocess_exec(
                'claude', 'plugin', 'install', skill_name,
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
