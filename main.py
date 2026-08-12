"""
AstrBot Claude Code Plugin

Integrates Claude Code CLI as an LLM function tool.
Following Unix philosophy: explicit I/O, composable modules, single responsibility.

v3.0 - Refactored to Onion Architecture with dependency injection.
"""

import asyncio
import time
from pathlib import Path

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, StarTools, register

# Use new modular architecture
from .application import ClaudeExecutor
from .claude_config import ClaudeConfigManager
from .infrastructure.config import validate_config
from .infrastructure.config.path_resolver import PathResolver
from .infrastructure.http import ServerManager
from .infrastructure.installer import CLIInstaller, MarketplaceManager

PLUGIN_DIR = Path(__file__).parent
VERSION = "3.0.0"


@register("astrbot_plugin_claudecode", "Claude", "Claude Code as LLM Tool", VERSION)
class ClaudeCodePlugin(Star):
    """
    Claude Code Plugin - Integrates Claude Code CLI as LLM function tool.

    Features:
    - Code generation, debugging, refactoring
    - File operations and shell commands
    - Instant web deployment
    - Streaming progress feedback
    """

    def __init__(self, context: Context, config: AstrBotConfig):
        """Initialize plugin with configuration."""
        super().__init__(context)
        start_time = time.time()
        logger.info(f"[ENTRY] ClaudeCodePlugin.__init__ version={VERSION}")

        self.config = config
        self._restrict_to_admin = bool(config.get("restrict_to_admin", True))
        self._config_ready = False
        self._init_task = None
        self._validation_error = None

        # Initialize workspace. workspace_name 是配置项，可能被低权限用户
        # 或恶意配置修改；必须拒绝绝对路径、.. 和符号链接，避免越出数据目录
        # 写任意位置（随后 mkdir/CLAUDE.md/配置/cwd/dist 都会作用其上）。
        workspace_name = config.get("workspace_name", "workspace")
        workspace_name = str(workspace_name or "").strip().replace("\\", "/")
        if (
            not workspace_name
            or workspace_name.startswith("/")
            or workspace_name.startswith("~")
            or ":" in workspace_name  # Windows 盘符
            or ".." in workspace_name.split("/")
        ):
            logger.warning(
                f"[PROCESS] Invalid workspace_name {workspace_name!r}, "
                "falling back to 'workspace'"
            )
            workspace_name = "workspace"

        try:
            data_dir = Path(StarTools.get_data_dir())
        except Exception:
            data_dir = PLUGIN_DIR
        self.workspace = data_dir / workspace_name
        try:
            # 拒绝符号链接：解析后必须仍在数据目录内。
            resolved = self.workspace.resolve()
            if not str(resolved).startswith(str(data_dir.resolve())):
                raise ValueError("workspace resolves outside data dir")
        except (OSError, ValueError) as exc:
            logger.warning(
                f"[PROCESS] Workspace {self.workspace} resolves outside data dir: {exc}, "
                "falling back to data/workspace"
            )
            self.workspace = data_dir / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        logger.info(f"[PROCESS] Workspace initialized: {self.workspace}")

        # Initialize components (using new modular architecture)
        self.config_manager = ClaudeConfigManager.from_plugin_config(
            config, self.workspace
        )
        self.cli_installer = CLIInstaller()
        self.marketplace_manager = MarketplaceManager(
            path_resolver=PathResolver(self.workspace)
        )
        self.claude_executor = ClaudeExecutor(
            workspace=self.workspace, config_manager=self.config_manager
        )
        self.server_manager = ServerManager(
            workspace=self.workspace,
            port=config.get("http_server_port", 6200),
        )

        # Validate configuration
        validation_result = validate_config(self.config_manager.config)
        if validation_result.is_err():
            self._validation_error = validation_result.unwrap_err()
            logger.warning(
                f"[PROCESS] Config validation failed: {self._validation_error}"
            )

        # Start async initialization
        self._init_task = None

        duration_ms = (time.time() - start_time) * 1000
        logger.info(f"[EXIT] ClaudeCodePlugin.__init__ duration_ms={duration_ms:.2f}")
        logger.info(f"[PROCESS] {self.config_manager.get_config_summary()}")

    async def initialize(self):
        """Async initialization called by AstrBot framework"""
        self._init_task = asyncio.create_task(self._async_init())
        self._init_task.add_done_callback(self._handle_init_done)

    async def terminate(self):
        """Cleanup on plugin unload"""
        if self._init_task and not self._init_task.done():
            self._init_task.cancel()
            try:
                await self._init_task
            except asyncio.CancelledError:
                pass
        await self.server_manager.stop()
        logger.info("[EXIT] ClaudeCodePlugin terminated")

    def _handle_init_done(self, task):
        """Handle async initialization completion."""
        try:
            task.result()
        except asyncio.CancelledError:
            logger.warning("[PROCESS] Async init was cancelled")
        except Exception as e:
            logger.error(f"[ERROR] Async init failed: {e}")

    async def _async_init(self):
        """Async initialization: install CLI, apply config, setup skills."""
        start_time = time.time()
        logger.info("[ENTRY] _async_init")

        auto_install = self.config.get("auto_install_claude", True)

        # Check and install Claude CLI
        success, msg = await self.cli_installer.ensure_installed(auto_install)
        logger.info(f"[PROCESS] Install check: {msg}")

        if not success:
            logger.warning(f"[EXIT] _async_init: CLI not available: {msg}")
            return

        # Apply configuration
        apply_result = self.config_manager.apply_config()
        if apply_result.is_ok():
            logger.info("[PROCESS] Configuration applied successfully")
            self._config_ready = True
        else:
            error = apply_result.unwrap_err()
            logger.error(f"[ERROR] Failed to apply config: {error}")
            self._config_ready = False
            return

        # Write CLAUDE.md (project instructions)
        await self._write_claude_md()

        # Install Skills
        await self._install_skills()

        # Start HTTP server for web deployment
        await self._start_http_server()

        duration_ms = (time.time() - start_time) * 1000
        logger.info(f"[EXIT] _async_init duration_ms={duration_ms:.2f}")

    async def _write_claude_md(self):
        """Write CLAUDE.md project instructions to workspace only."""
        claude_md = self.config.get("claude_md", "")
        if not claude_md:
            return

        try:
            workspace_claude_md = self.workspace / "CLAUDE.md"
            workspace_claude_md.write_text(claude_md, encoding="utf-8")
            logger.info("[PROCESS] CLAUDE.md updated in workspace/")
        except Exception as e:
            logger.warning(f"[ERROR] Failed to write CLAUDE.md: {e}")

    async def _install_skills(self):
        """Install configured skills."""
        skills_str = self.config.get("skills_to_install", "")
        if not skills_str:
            return

        for skill in [s.strip() for s in skills_str.split(",") if s.strip()]:
            success, result = await self.marketplace_manager.install_skill(skill)
            logger.info(f"[PROCESS] Skill {skill}: {result}")

    async def _start_http_server(self):
        """Start HTTP server for web deployment (cross-platform)."""
        # Use ServerManager for cross-platform compatibility
        # Fixes pgrep issue in containers
        await self.server_manager.start()

    def _check_config_ready(self) -> str | None:
        """Check if configuration is ready. Returns error message if not ready."""
        if self._validation_error:
            return f"Configuration error: {self._validation_error}"
        if not self._config_ready:
            return "Claude Code not ready, check plugin logs"
        return None

    @staticmethod
    def _truncate_task(task: str, max_len: int = 50) -> str:
        """Truncate task description for logging."""
        return task[:max_len] + "..." if len(task) > max_len else task

    @staticmethod
    def _is_admin(event: AstrMessageEvent) -> bool:
        is_admin = getattr(event, "is_admin", None)
        try:
            return bool(is_admin()) if callable(is_admin) else False
        except Exception:
            return False

    @filter.llm_tool(name="claude_code")
    async def claude_code(self, event: AstrMessageEvent, task: str) -> str:
        """
        在隔离的 Claude Code 工作区中执行编程任务(写代码/调试/重构/分析/部署)。

        能力:
        - 编写/修改/调试代码、项目分析、重构
        - 读写工作区文件、执行 shell 命令(仅工作区内)
        - 生成网页并部署到临时 HTTP 服务
        - 技术研究、文档撰写

        使用说明:
        - task 传用户的原始需求(中文/英文均可),保持完整上下文
        - 代码任务请说明: 语言/框架、期望行为、文件位置(如有)
        - 输出为执行结果文本(文件路径、输出、网页 URL 等),可能较长
        - 任务在工作区中执行,工作区外的文件不可访问
        - 默认权限模式为 acceptEdits(可写文件);Bash 默认禁用

        注意:
        - 仅管理员可调用(restrict_to_admin 默认开启)
        - 任务有超时(默认 180s)和并发限制(2)
        - 失败信息会说明原因,可据此修正任务描述后重试

        Args:
            task(string): Required. 要执行的任务描述,传用户原始请求

        Returns:
            string: 执行结果(输出/文件路径/URL)或失败原因
        """
        if self._restrict_to_admin and not self._is_admin(event):
            return "Claude Code 工具仅允许 AstrBot 管理员调用。"

        start_time = time.time()
        logger.info(f"[ENTRY] claude_code task={self._truncate_task(task)}")

        # Check configuration
        error = self._check_config_ready()
        if error:
            return error

        # Execute task
        result = await self.claude_executor.execute(task)

        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"[EXIT] claude_code success={result['success']} duration_ms={duration_ms:.2f}"
        )

        if result["success"]:
            cost = result.get("cost_usd", 0)
            output = result["output"]
            return f"{output}\n\n[Cost: ${cost:.4f} | Time: {duration_ms / 1000:.1f}s]"

        # 失败信息可操作化: 映射常见错误为 LLM 可修正的提示
        error = result.get("error", "unknown")
        if "TIMEOUT" in str(error) or "exceeded" in str(error):
            return (
                f"任务执行超时: {error}。提示: 请将任务拆分为更小的步骤,"
                "或减少要求(如限定文件范围/简化目标)后重试。"
            )
        if "NOT_INSTALLED" in str(error) or "not installed" in str(error):
            return (
                f"Claude Code CLI 不可用: {error}。提示: 请告知用户安装"
                "或启用 auto_install_claude 配置。"
            )
        if "permission" in str(error).lower() or "denied" in str(error).lower():
            return (
                f"权限不足: {error}。提示: 任务可能涉及工作区外操作,"
                "请调整任务描述限定在工作区内。"
            )
        return f"任务执行失败: {error}。请修正任务描述后重试。"

    # NOTE: 流式工具暂时禁用，stream-json输出过于冗长
    # @filter.llm_tool(name="claude_code_stream")
    # async def claude_code_stream(
    #     self, event: AstrMessageEvent, task: str
    # ) -> str:
    #     """
    #     Claude Code (Streaming) - AI assistant with real-time progress.
    #     """
    #     start_time = time.time()
    #     logger.info(f"[ENTRY] claude_code_stream task={self._truncate_task(task)}")
    #
    #     error = self._check_config_ready()
    #     if error:
    #         return error
    #
    #     progress_log = []
    #     type_icons = {
    #         "thinking": "[Thinking]",
    #         "tool_use": "[Tool]",
    #         "result": "[Result]",
    #         "error": "[Error]",
    #         "status": "[Status]",
    #     }
    #
    #     def on_progress(chunk: StreamChunk):
    #         icon = type_icons.get(chunk.chunk_type.value, "[Info]")
    #         progress_log.append(f"{icon} {chunk.content[:100]}...")
    #
    #     result = await self.claude_executor.execute_stream(
    #         task, on_progress=on_progress
    #     )
    #
    #     duration_ms = (time.time() - start_time) * 1000
    #     logger.info(
    #         f"[EXIT] claude_code_stream success={result.is_ok()} duration_ms={duration_ms:.2f}"
    #     )
    #
    #     if result.is_ok():
    #         exec_result = result.unwrap()
    #         progress_str = "\n".join(progress_log[-5:])
    #         return (
    #             f"{exec_result.output}\n\n"
    #             f"--- Progress ---\n{progress_str}\n"
    #             f"[Cost: ${exec_result.cost_usd:.4f} | Time: {duration_ms/1000:.1f}s]"
    #         )
    #
    #     error = result.unwrap_err()
    #     return f"Execution failed [{error.code}]: {error.message}"
