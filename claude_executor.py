"""
Claude Code CLI 执行器

This module provides both blocking and streaming execution modes for Claude Code CLI.
Follows Unix philosophy: single responsibility, explicit I/O, composable functions.
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from .types import (
    Result,
    ExecutionResult,
    ExecutionError,
    ErrorCode,
    StreamChunk,
    ChunkType,
    ProgressCallback,
    ok,
    err,
)

if TYPE_CHECKING:
    from .claude_config import ClaudeConfigManager

logger = logging.getLogger("astrbot")


class ClaudeExecutor:
    """
    Claude Code CLI executor with streaming support.

    Provides both blocking and streaming execution modes following Unix philosophy:
    - Single responsibility: Execute Claude Code tasks
    - Explicit I/O: All inputs as parameters, all outputs as return values
    - Composable: Can be used in pipelines with Result type
    """

    def __init__(self, workspace: Path, config_manager: "ClaudeConfigManager" = None):
        """
        Initialize executor.

        Args:
            workspace: Working directory for Claude Code execution
            config_manager: Optional configuration manager for execution settings
        """
        self.workspace = workspace
        self.config_manager = config_manager
        self.workspace.mkdir(parents=True, exist_ok=True)
        logger.info(f"[ENTRY] ClaudeExecutor.__init__ workspace={workspace}")

    def _resolve_timeout(self, timeout: Optional[int]) -> int:
        """
        Resolve timeout from parameter or config.

        Args:
            timeout: Optional timeout in seconds

        Returns:
            int: Resolved timeout value
        """
        if timeout is None:
            timeout = (
                self.config_manager.config.timeout_seconds
                if self.config_manager
                else 120
            )
        return timeout

    async def execute(self, task: str, timeout: int = None) -> dict:
        """
        Execute Claude Code task (legacy blocking mode).

        This method maintains backward compatibility with the original dict-based API.
        For new code, prefer execute_typed() which returns Result type.

        Args:
            task: Task description for Claude
            timeout: Execution timeout in seconds (uses config default if None)

        Returns:
            dict: Legacy format with keys: success, output, error, cost_usd, session_id
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
        self, task: str, timeout: Optional[int] = None
    ) -> Result[ExecutionResult, ExecutionError]:
        """
        Execute Claude Code task with type-safe Result return.

        Args:
            task: Task description for Claude
            timeout: Execution timeout in seconds (uses config default if None)

        Returns:
            Result[ExecutionResult, ExecutionError]: Type-safe execution result
        """
        task_preview = task[:50] + "..." if len(task) > 50 else task
        logger.info(
            f"[ENTRY] execute_typed inputs={{task={task_preview}, timeout={timeout}}}"
        )
        start_time = time.time()

        timeout = self._resolve_timeout(timeout)
        cmd_args = self._build_command_args(task, stream=False)

        try:
            # Use subprocess_exec to avoid shell injection
            proc = await asyncio.create_subprocess_exec(
                *cmd_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace),
            )
            logger.info(f"[PROCESS] Started subprocess pid={proc.pid}")

            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            duration_ms = (time.time() - start_time) * 1000

            output = stdout.decode("utf-8", errors="ignore")
            stderr_text = stderr.decode("utf-8", errors="ignore")

            result = self._parse_json_output(output, stderr_text, duration_ms)
            logger.info(
                f"[EXIT] execute_typed return={{success={result.is_ok()}, duration_ms={duration_ms:.2f}}}"
            )
            return result

        except asyncio.TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            logger.warning(
                f"[ERROR] TIMEOUT: Task exceeded {timeout}s timeout duration_ms={duration_ms:.2f}"
            )
            return err(
                ExecutionError(
                    code=ErrorCode.TIMEOUT,
                    message=f"Task execution exceeded {timeout}s timeout",
                    details={"task_preview": task_preview, "timeout": timeout},
                )
            )
        except FileNotFoundError:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"[ERROR] NOT_INSTALLED: Claude CLI not found duration_ms={duration_ms:.2f}"
            )
            return err(
                ExecutionError(
                    code=ErrorCode.NOT_INSTALLED,
                    message="Claude CLI is not installed or not in PATH",
                    details={"command": cmd_args[0]},
                )
            )
        except PermissionError as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"[ERROR] PERMISSION_DENIED: {e} duration_ms={duration_ms:.2f}"
            )
            return err(
                ExecutionError(
                    code=ErrorCode.PERMISSION_DENIED,
                    message=f"Permission denied: {e}",
                    details={"workspace": str(self.workspace)},
                )
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"[ERROR] UNKNOWN: {type(e).__name__}: {e} duration_ms={duration_ms:.2f}"
            )
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
        Execute Claude Code task with streaming progress updates.

        Args:
            task: Task description for Claude
            timeout: Execution timeout in seconds (uses config default if None)
            on_progress: Optional callback for progress updates

        Returns:
            Result[ExecutionResult, ExecutionError]: Type-safe execution result
        """
        task_preview = task[:50] + "..." if len(task) > 50 else task
        logger.info(
            f"[ENTRY] execute_stream inputs={{task={task_preview}, timeout={timeout}, has_callback={on_progress is not None}}}"
        )
        start_time = time.time()

        timeout = self._resolve_timeout(timeout)
        cmd_args = self._build_command_args(task, stream=True)

        try:
            # Use subprocess_exec to avoid shell injection
            proc = await asyncio.create_subprocess_exec(
                *cmd_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace),
            )
            logger.info(f"[PROCESS] Started streaming subprocess pid={proc.pid}")

            # Stream output with timeout
            result = await asyncio.wait_for(
                self._stream_output(proc, on_progress, start_time),
                timeout=timeout,
            )

            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                f"[EXIT] execute_stream return={{success={result.is_ok()}, duration_ms={duration_ms:.2f}}}"
            )
            return result

        except asyncio.TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            logger.warning(
                f"[ERROR] TIMEOUT: Streaming task exceeded {timeout}s timeout duration_ms={duration_ms:.2f}"
            )
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
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"[ERROR] NOT_INSTALLED: Claude CLI not found duration_ms={duration_ms:.2f}"
            )
            return err(
                ExecutionError(
                    code=ErrorCode.NOT_INSTALLED,
                    message="Claude CLI is not installed or not in PATH",
                    details={"command": cmd_args[0]},
                )
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"[ERROR] UNKNOWN: {type(e).__name__}: {e} duration_ms={duration_ms:.2f}"
            )
            return err(
                ExecutionError(
                    code=ErrorCode.UNKNOWN,
                    message=f"Unexpected error: {e}",
                    details={"exception_type": type(e).__name__, "exception": str(e)},
                )
            )

    def _build_command_args(self, task: str, stream: bool = False) -> list:
        """
        Build command arguments list (prevents shell injection).

        Args:
            task: Task description for Claude
            stream: Whether to use stream-json output format

        Returns:
            list: Command arguments for subprocess execution
        """
        output_format = "stream-json" if stream else "json"
        cmd_args = [
            "claude",
            "-p",
            task,  # Passed directly, no escaping needed
            "--output-format",
            output_format,
        ]

        # stream-json requires --verbose when using -p
        if stream:
            cmd_args.append("--verbose")

        # Add security restrictions from config
        if self.config_manager:
            cfg = self.config_manager.config

            # Allowed tools (auto-add workspace path restriction for Bash)
            if cfg.allowed_tools:
                tools = self._process_allowed_tools(cfg.allowed_tools)
                cmd_args.extend(["--allowedTools", tools])

            # Disallowed tools
            if cfg.disallowed_tools:
                tools = ",".join(cfg.disallowed_tools)
                cmd_args.extend(["--disallowedTools", tools])

            # Permission mode
            if cfg.permission_mode and cfg.permission_mode != "default":
                cmd_args.extend(["--permission-mode", cfg.permission_mode])

            # Additional directories
            if cfg.add_dirs:
                for d in cfg.add_dirs:
                    cmd_args.extend(["--add-dir", d])

            # Max turns
            if cfg.max_turns:
                cmd_args.extend(["--max-turns", str(cfg.max_turns)])

            # Model
            if cfg.model:
                cmd_args.extend(["--model", cfg.model])

        return cmd_args

    def _process_allowed_tools(self, tools: list) -> str:
        """
        Process allowed tools list, auto-add workspace path restriction for Bash.

        Args:
            tools: List of tool names

        Returns:
            str: Comma-separated tool list with restrictions
        """
        processed = []
        for tool in tools:
            if tool == "Bash":
                # Auto-add workspace path restriction
                workspace_path = str(self.workspace).replace("\\", "/")
                processed.append(f"Bash({workspace_path}/*)")
            else:
                processed.append(tool)
        return ",".join(processed)

    def _parse_json_output(
        self, stdout: str, stderr: str, duration_ms: float
    ) -> Result[ExecutionResult, ExecutionError]:
        """
        Parse JSON output from Claude CLI.

        Args:
            stdout: Standard output from CLI
            stderr: Standard error from CLI
            duration_ms: Execution duration in milliseconds

        Returns:
            Result[ExecutionResult, ExecutionError]: Parsed result
        """
        try:
            data = json.loads(stdout)
            is_error = data.get("is_error", False)

            if is_error:
                logger.warning(
                    f"[ERROR] CLI returned error: {data.get('result', 'Unknown error')}"
                )
                return err(
                    ExecutionError(
                        code=ErrorCode.CLI_ERROR,
                        message=data.get("result", "Unknown CLI error"),
                        details={"stdout": stdout, "stderr": stderr, "data": data},
                    )
                )

            result = ExecutionResult(
                output=data.get("result", ""),
                cost_usd=data.get("total_cost_usd", 0.0),
                session_id=data.get("session_id", ""),
                duration_ms=duration_ms,
                metadata={"raw_data": data},
            )
            return ok(result)

        except json.JSONDecodeError as e:
            logger.warning(f"[ERROR] Failed to parse JSON: {e}")
            # Check stderr for error indicators
            has_error = stderr and (
                "error" in stderr.lower() or "failed" in stderr.lower()
            )

            if has_error or not stdout:
                return err(
                    ExecutionError(
                        code=ErrorCode.PARSE_ERROR,
                        message=f"Failed to parse CLI output: {e}",
                        details={"stdout": stdout, "stderr": stderr},
                    )
                )

            # Fallback: treat as success with raw output
            result = ExecutionResult(
                output=stdout or stderr,
                cost_usd=0.0,
                session_id="",
                duration_ms=duration_ms,
                metadata={"parse_error": str(e)},
            )
            return ok(result)

    async def _stream_output(
        self,
        proc: asyncio.subprocess.Process,
        on_progress: Optional[ProgressCallback],
        start_time: float,
    ) -> Result[ExecutionResult, ExecutionError]:
        """
        Stream output from subprocess and invoke progress callbacks.

        Args:
            proc: The subprocess to read from
            on_progress: Optional callback for progress updates
            start_time: Start time for duration calculation

        Returns:
            Result[ExecutionResult, ExecutionError]: Final execution result
        """
        accumulated_output = []
        chunk_count = 0

        try:
            # Read stdout line by line
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break

                line_text = line.decode("utf-8", errors="ignore").strip()
                if not line_text:
                    continue

                chunk_count += 1

                # Try to parse as stream-json chunk
                try:
                    chunk_data = json.loads(line_text)
                    chunk_type = self._determine_chunk_type(chunk_data)
                    content = self._extract_chunk_content(chunk_data)

                    # Create stream chunk (simplified metadata)
                    chunk = StreamChunk(
                        chunk_type=chunk_type,
                        content=content,
                        timestamp=time.time(),
                        metadata={"type": chunk_data.get("type", "unknown")},
                    )

                    # Invoke callback if provided
                    if on_progress:
                        try:
                            on_progress(chunk)
                        except Exception as e:
                            logger.warning(f"[ERROR] Progress callback failed: {e}")

                    # Accumulate output
                    if content:
                        accumulated_output.append(content)

                except json.JSONDecodeError:
                    # Not JSON, treat as raw output
                    accumulated_output.append(line_text)

            # Wait for process to complete
            await proc.wait()
            stderr = await proc.stderr.read()
            stderr_text = stderr.decode("utf-8", errors="ignore")

            duration_ms = (time.time() - start_time) * 1000

            # Build final result
            final_output = "\n".join(accumulated_output)
            result = ExecutionResult(
                output=final_output,
                cost_usd=0.0,  # Cost info not available in stream mode
                session_id="",
                duration_ms=duration_ms,
                metadata={"chunk_count": chunk_count, "stderr": stderr_text},
            )

            logger.info(
                f"[EXIT] _stream_output return={{success=True, chunks={chunk_count}, duration_ms={duration_ms:.2f}}}"
            )
            return ok(result)

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"[ERROR] Stream processing failed: {e} duration_ms={duration_ms:.2f}"
            )
            return err(
                ExecutionError(
                    code=ErrorCode.UNKNOWN,
                    message=f"Stream processing error: {e}",
                    details={
                        "exception_type": type(e).__name__,
                        "accumulated_output": "\n".join(accumulated_output),
                        "chunk_count": chunk_count,
                    },
                )
            )

    def _determine_chunk_type(self, chunk_data: dict) -> ChunkType:
        """
        Determine the type of a stream chunk.

        Args:
            chunk_data: Parsed JSON chunk data

        Returns:
            ChunkType: The determined chunk type
        """
        # Check for common stream-json fields
        if "type" in chunk_data:
            chunk_type_str = chunk_data["type"].lower()
            if "think" in chunk_type_str:
                return ChunkType.THINKING
            elif "tool" in chunk_type_str:
                return ChunkType.TOOL_USE
            elif "error" in chunk_type_str:
                return ChunkType.ERROR
            elif "result" in chunk_type_str:
                return ChunkType.RESULT

        # Check for error indicators
        if chunk_data.get("is_error") or "error" in chunk_data:
            return ChunkType.ERROR

        # Check for result indicators
        if "result" in chunk_data or "output" in chunk_data:
            return ChunkType.RESULT

        # Default to status
        return ChunkType.STATUS

    def _extract_chunk_content(self, chunk_data: dict) -> str:
        """
        Extract content from a stream chunk.

        Args:
            chunk_data: Parsed JSON chunk data

        Returns:
            str: Extracted content
        """
        # Try common content fields
        for field in ["content", "text", "message", "result", "output"]:
            if field in chunk_data and chunk_data[field]:
                return str(chunk_data[field])

        # Fallback to JSON string
        return json.dumps(chunk_data)
