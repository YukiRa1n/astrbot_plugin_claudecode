"""
AstrBot Claude Code Plugin

Integrates Claude Code CLI as an LLM function tool.
Following Unix philosophy: explicit I/O, composable modules, single responsibility.

v3.0 - Refactored to Onion Architecture with dependency injection.
"""

import asyncio
import time
from pathlib import Path
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import logger
from astrbot.api import AstrBotConfig

# Use new modular architecture
from .application import ClaudeExecutor
from .claude_config import ClaudeConfigManager
from .infrastructure.config import validate_config
from .infrastructure.installer import CLIInstaller, MarketplaceManager
from .infrastructure.http import ServerManager
from .types import StreamChunk

PLUGIN_DIR = Path(__file__).parent
VERSION = "3.0.0"


@register(
    "astrbot_plugin_claudecode", "Claude", "Claude Code as LLM Tool", VERSION
)
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
        self._config_ready = False
        self._init_task = None
        self._validation_error = None

        # Initialize workspace
        workspace_name = config.get("workspace_name", "workspace")
        try:
            self.workspace = StarTools.get_data_dir() / workspace_name
        except Exception:
            self.workspace = PLUGIN_DIR / workspace_name
        self.workspace.mkdir(parents=True, exist_ok=True)
        logger.info(f"[PROCESS] Workspace initialized: {self.workspace}")

        # Initialize components (using new modular architecture)
        self.config_manager = ClaudeConfigManager.from_plugin_config(config)
        self.cli_installer = CLIInstaller()
        self.marketplace_manager = MarketplaceManager()
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
        self._init_task = asyncio.create_task(self._async_init())
        self._init_task.add_done_callback(self._handle_init_done)

        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"[EXIT] ClaudeCodePlugin.__init__ duration_ms={duration_ms:.2f}"
        )
        logger.info(f"[PROCESS] {self.config_manager.get_config_summary()}")

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
        """Write CLAUDE.md project instructions to both ~/.claude and workspace."""
        claude_md = self.config.get("claude_md", "")
        if not claude_md:
            return

        try:
            # Write to ~/.claude/CLAUDE.md (global config)
            claude_dir = Path.home() / ".claude"
            claude_dir.mkdir(parents=True, exist_ok=True)
            claude_md_path = claude_dir / "CLAUDE.md"
            claude_md_path.write_text(claude_md, encoding="utf-8")
            logger.info("[PROCESS] CLAUDE.md updated in ~/.claude/")

            # Write to workspace/CLAUDE.md (for -p mode execution)
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

    @filter.llm_tool(name="claude_code")
    async def claude_code(self, event: AstrMessageEvent, task: str) -> str:
        """
        Claude Code - Powerful AI programming assistant.

        Capabilities:
        - Code writing, debugging, refactoring, project analysis
        - File read/write, shell command execution
        - Instant web deployment to temporary server
        - Web search, research, documentation

        Use cases:
        - User requests code, web pages, deployments
        - Tasks requiring file operations or commands
        - Technical research, code analysis

        Args:
            task(string): Required. Task description, pass user's original request

        Returns:
            string: Execution result (file paths, web URLs, etc.)
        """
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
            return f"{output}\n\n[Cost: ${cost:.4f} | Time: {duration_ms/1000:.1f}s]"

        return f"Execution failed: {result.get('error', 'unknown')}"

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
