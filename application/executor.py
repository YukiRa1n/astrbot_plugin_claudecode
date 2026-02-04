"""
Claude Executor - Application layer facade for Claude Code execution.

Orchestrates infrastructure components to execute Claude Code tasks.
Implements dependency injection for testability.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from ..types import (
    Result,
    ExecutionResult,
    ExecutionError,
    ErrorCode,
    ProgressCallback,
    ClaudeConfig,
    ok,
    err,
)
from ..infrastructure.process import CommandBuilder, ProcessRunner, OutputParser
from ..infrastructure.stream import StreamProcessor

if TYPE_CHECKING:
    from ..claude_config import ClaudeConfigManager

logger = logging.getLogger("astrbot")


class ClaudeExecutor:
    """
    Claude Code CLI executor facade.

    Orchestrates:
    - CommandBuilder: Build CLI arguments
    - ProcessRunner: Execute subprocess
    - OutputParser: Parse CLI output
    - StreamProcessor: Handle streaming output

    All dependencies are injectable for testing.
    """

    def __init__(
        self,
        workspace: Path,
        config_manager: "ClaudeConfigManager" = None,
        # Dependency injection
        command_builder: CommandBuilder = None,
        process_runner: ProcessRunner = None,
        output_parser: OutputParser = None,
        stream_processor: StreamProcessor = None,
    ):
        """
        Initialize executor with dependencies.

        Args:
            workspace: Working directory for execution
            config_manager: Configuration manager
            command_builder: Optional command builder (creates default if None)
            process_runner: Optional process runner (creates default if None)
            output_parser: Optional output parser (creates default if None)
            stream_processor: Optional stream processor (creates default if None)
        """
        self.workspace = workspace
        self.config_manager = config_manager
        self.workspace.mkdir(parents=True, exist_ok=True)

        # Inject or create dependencies
        self._command_builder = command_builder or CommandBuilder()
        self._process_runner = process_runner or ProcessRunner()
        self._output_parser = output_parser or OutputParser()
        self._stream_processor = stream_processor or StreamProcessor()

        logger.debug(f"[ClaudeExecutor] Initialized with workspace={workspace}")

    @property
    def config(self) -> ClaudeConfig:
        """Get current configuration."""
        if self.config_manager:
            return self.config_manager.config
        return ClaudeConfig()

    def _resolve_timeout(self, timeout: Optional[int]) -> int:
        """Resolve timeout from parameter or config."""
        if timeout is not None:
            return timeout
        return self.config.timeout_seconds or 120

    async def execute(self, task: str, timeout: int = None) -> dict:
        """
        Execute Claude Code task (legacy dict-based API).

        Maintains backward compatibility with original API.

        Args:
            task: Task description
            timeout: Execution timeout in seconds

        Returns:
            dict with keys: success, output, error, cost_usd, session_id
        """
        result = await self.execute_typed(task, timeout)

        if result.is_ok():
            exec_result = result.unwrap()
            return {
                "success": True,
                "output": exec_result.output,
                "cost_usd": exec_result.cost_usd,
                "session_id": exec_result.session_id,
            }
        else:
            error = result.unwrap_err()
            return {
                "success": False,
                "error": error.message,
                "output": error.details.get("stdout", ""),
            }

    async def execute_typed(
        self,
        task: str,
        timeout: Optional[int] = None,
    ) -> Result[ExecutionResult, ExecutionError]:
        """
        Execute Claude Code task with type-safe Result return.

        Args:
            task: Task description
            timeout: Execution timeout in seconds

        Returns:
            Result[ExecutionResult, ExecutionError]
        """
        task_preview = task[:50] + "..." if len(task) > 50 else task
        logger.info(f"[ClaudeExecutor] execute_typed task={task_preview}")
        start_time = time.time()

        timeout = self._resolve_timeout(timeout)

        # Build command
        cmd_args = self._command_builder.build(
            task=task,
            workspace=self.workspace,
            config=self.config,
            stream=False,
        )

        try:
            # Execute
            stdout, stderr, returncode = await self._process_runner.run(
                cmd_args=cmd_args,
                cwd=self.workspace,
                timeout=timeout,
            )

            duration_ms = (time.time() - start_time) * 1000

            # Parse output
            result = self._output_parser.parse(stdout, stderr, duration_ms)

            logger.info(
                f"[ClaudeExecutor] execute_typed completed success={result.is_ok()} duration_ms={duration_ms:.2f}"
            )
            return result

        except asyncio.TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            logger.warning(f"[ClaudeExecutor] TIMEOUT after {timeout}s")
            return err(
                ExecutionError(
                    code=ErrorCode.TIMEOUT,
                    message=f"Task execution exceeded {timeout}s timeout",
                    details={"task_preview": task_preview, "timeout": timeout},
                )
            )

        except FileNotFoundError:
            logger.error("[ClaudeExecutor] Claude CLI not found")
            return err(
                ExecutionError(
                    code=ErrorCode.NOT_INSTALLED,
                    message="Claude CLI is not installed or not in PATH",
                    details={"command": cmd_args[0]},
                )
            )

        except PermissionError as e:
            logger.error(f"[ClaudeExecutor] Permission denied: {e}")
            return err(
                ExecutionError(
                    code=ErrorCode.PERMISSION_DENIED,
                    message=f"Permission denied: {e}",
                    details={"workspace": str(self.workspace)},
                )
            )

        except Exception as e:
            logger.error(f"[ClaudeExecutor] Unexpected error: {e}")
            return err(
                ExecutionError(
                    code=ErrorCode.UNKNOWN,
                    message=f"Unexpected error: {e}",
                    details={"exception_type": type(e).__name__, "exception": str(e)},
                )
            )

    async def execute_stream(
        self,
        task: str,
        timeout: Optional[int] = None,
        on_progress: Optional[ProgressCallback] = None,
    ) -> Result[ExecutionResult, ExecutionError]:
        """
        Execute Claude Code task with streaming progress.

        Args:
            task: Task description
            timeout: Execution timeout in seconds
            on_progress: Optional callback for progress updates

        Returns:
            Result[ExecutionResult, ExecutionError]
        """
        task_preview = task[:50] + "..." if len(task) > 50 else task
        logger.info(f"[ClaudeExecutor] execute_stream task={task_preview}")
        start_time = time.time()

        timeout = self._resolve_timeout(timeout)

        # Build command with streaming
        cmd_args = self._command_builder.build(
            task=task,
            workspace=self.workspace,
            config=self.config,
            stream=True,
        )

        try:
            # Start process
            proc = await asyncio.create_subprocess_exec(
                *cmd_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace),
            )

            # Process stream with timeout
            result = await asyncio.wait_for(
                self._stream_processor.process(proc, on_progress, start_time),
                timeout=timeout,
            )

            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                f"[ClaudeExecutor] execute_stream completed success={result.is_ok()} duration_ms={duration_ms:.2f}"
            )
            return result

        except asyncio.TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            logger.warning(f"[ClaudeExecutor] Stream TIMEOUT after {timeout}s")
            if proc:
                proc.kill()
                await proc.wait()
            return err(
                ExecutionError(
                    code=ErrorCode.TIMEOUT,
                    message=f"Task execution exceeded {timeout}s timeout",
                    details={"task_preview": task_preview, "timeout": timeout},
                )
            )

        except FileNotFoundError:
            logger.error("[ClaudeExecutor] Claude CLI not found")
            return err(
                ExecutionError(
                    code=ErrorCode.NOT_INSTALLED,
                    message="Claude CLI is not installed or not in PATH",
                    details={"command": cmd_args[0]},
                )
            )

        except Exception as e:
            logger.error(f"[ClaudeExecutor] Stream error: {e}")
            return err(
                ExecutionError(
                    code=ErrorCode.UNKNOWN,
                    message=f"Unexpected error: {e}",
                    details={"exception_type": type(e).__name__, "exception": str(e)},
                )
            )


__all__ = ["ClaudeExecutor"]
