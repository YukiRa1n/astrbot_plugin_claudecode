"""
AstrBot Claude Code 插件
将Claude Code作为LLM函数工具
"""
import asyncio
from pathlib import Path
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api import AstrBotConfig

from .claude_executor import ClaudeExecutor
from .claude_config import ClaudeConfigManager
from .auto_installer import ClaudeInstaller

PLUGIN_DIR = Path(__file__).parent


@register(
    "astrbot_plugin_claudecode",
    "Claude",
    "将Claude Code作为LLM函数工具",
    "2.0.0"
)
class ClaudeCodePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        # 初始化工作目录
        workspace_name = config.get('workspace_name', 'workspace')
        self.workspace = PLUGIN_DIR / workspace_name
        self.workspace.mkdir(parents=True, exist_ok=True)

        # 初始化组件
        self.config_manager = ClaudeConfigManager.from_plugin_config(config)
        self.installer = ClaudeInstaller()
        self.claude_executor = ClaudeExecutor(
            workspace=self.workspace,
            config_manager=self.config_manager
        )

        # 异步初始化
        asyncio.create_task(self._async_init())

        logger.info('[ClaudeCode] Plugin v2.0.0 loaded')
        logger.info(f'[ClaudeCode] Workspace: {self.workspace}')
        logger.info(f'[ClaudeCode] {self.config_manager.get_config_summary()}')

    async def _async_init(self):
        """异步初始化"""
        auto_install = self.config.get('auto_install_claude', True)

        # 检查并安装
        success, msg = await self.installer.ensure_installed(auto_install)
        logger.info(f'[ClaudeCode] Install check: {msg}')

        if not success:
            logger.warning(f'[ClaudeCode] Claude Code not available: {msg}')
            return

        # 应用配置
        if self.config_manager.apply_config():
            logger.info('[ClaudeCode] Configuration applied')
        else:
            logger.error('[ClaudeCode] Failed to apply configuration')

        # 安装 Skills
        skills_str = self.config.get('skills_to_install', '')
        if skills_str:
            for skill in [s.strip() for s in skills_str.split(',') if s.strip()]:
                ok, result = await self.installer.install_skill(skill)
                logger.info(f'[ClaudeCode] Skill {skill}: {result}')

    @filter.llm_tool(name="claude_code")
    async def claude_code(self, event: AstrMessageEvent, task: str) -> str:
        """【Claude Code】调用Claude Code执行编程任务。

        可执行代码编写、文件操作、项目分析等任务。

        Args:
            task(string): Required. 任务描述

        Returns:
            string: 执行结果
        """
        logger.info(f'[ClaudeCode] Task: {task[:50]}...')
        result = await self.claude_executor.execute(task)

        if result['success']:
            cost = result.get('cost_usd', 0)
            return f"{result['output']}\n[Cost: ${cost:.4f}]"
        return f"执行失败: {result.get('error', 'unknown')}"
