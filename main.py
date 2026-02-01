"""
AstrBot Claude Code 插件
将Claude Code作为LLM函数工具
"""
import asyncio
from pathlib import Path
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register, StarTools
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
        self._config_ready = False
        self._init_task = None

        # 初始化工作目录 (使用框架数据目录)
        workspace_name = config.get('workspace_name', 'workspace')
        try:
            self.workspace = StarTools.get_data_dir() / workspace_name
        except Exception:
            # 回退到插件目录
            self.workspace = PLUGIN_DIR / workspace_name
        self.workspace.mkdir(parents=True, exist_ok=True)

        # 初始化组件
        self.config_manager = ClaudeConfigManager.from_plugin_config(config)
        self.installer = ClaudeInstaller()
        self.claude_executor = ClaudeExecutor(
            workspace=self.workspace,
            config_manager=self.config_manager
        )

        # 异步初始化 (追踪任务)
        self._init_task = asyncio.create_task(self._async_init())
        self._init_task.add_done_callback(self._handle_init_done)

        logger.info('[ClaudeCode] Plugin v2.0.0 loaded')
        logger.info(f'[ClaudeCode] Workspace: {self.workspace}')
        logger.info(f'[ClaudeCode] {self.config_manager.get_config_summary()}')

    def _handle_init_done(self, task):
        """处理初始化任务完成"""
        try:
            task.result()
        except asyncio.CancelledError:
            logger.warning('[ClaudeCode] Async init was cancelled')
        except Exception as e:
            logger.error(f'[ClaudeCode] Async init failed: {e}')

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
            self._config_ready = True
        else:
            logger.error('[ClaudeCode] Failed to apply configuration')
            self._config_ready = False
            return

        # 写入 CLAUDE.md (项目指令)
        claude_md = self.config.get('claude_md', '')
        if claude_md:
            try:
                # CLAUDE.md 放在 ~/.claude/ 目录下
                claude_dir = Path.home() / '.claude'
                claude_dir.mkdir(parents=True, exist_ok=True)
                claude_md_path = claude_dir / 'CLAUDE.md'
                claude_md_path.write_text(claude_md, encoding='utf-8')
                logger.info('[ClaudeCode] CLAUDE.md updated')
            except Exception as e:
                logger.warning(f'[ClaudeCode] Failed to write CLAUDE.md: {e}')

        # 安装 Skills
        skills_str = self.config.get('skills_to_install', '')
        if skills_str:
            for skill in [s.strip() for s in skills_str.split(',') if s.strip()]:
                ok, result = await self.installer.install_skill(skill)
                logger.info(f'[ClaudeCode] Skill {skill}: {result}')

    @filter.llm_tool(name="claude_code")
    async def claude_code(self, event: AstrMessageEvent, task: str) -> str:
        """【Claude Code】强大的AI编程助手，可执行几乎任何计算机任务。

        Claude Code 是一个独立的AI Agent，拥有完整的工具集：
        - 代码编写、调试、重构
        - 文件读写、项目分析
        - 执行Shell命令、安装依赖
        - 网络搜索、信息调研
        - 生成文档、报告等

        当用户请求涉及编程、写代码、文件操作等稍复杂的任务时，
        可使用此工具，将任务描述直接传递给Claude Code执行。

        Args:
            task(string): Required. 任务描述，直接传递用户的原始请求即可

        Returns:
            string: 执行结果
        """
        # 检查配置是否就绪
        if not self._config_ready:
            return "Claude Code 配置未就绪，请检查插件日志"

        logger.info(f'[ClaudeCode] Task: {task[:50]}...')
        result = await self.claude_executor.execute(task)

        if result['success']:
            cost = result.get('cost_usd', 0)
            return f"{result['output']}\n[Cost: ${cost:.4f}]"
        return f"执行失败: {result.get('error', 'unknown')}"
