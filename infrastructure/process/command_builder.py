"""
Command Builder - Builds CLI command arguments.

Single responsibility: Transform task + config into command arguments.
No subprocess execution, no I/O - pure transformation.
"""

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...models import ClaudeConfig


class CommandBuilder:
    """
    Builds Claude CLI command arguments.

    Implements ICommandBuilder interface.
    Pure function-like class: no side effects, deterministic output.
    """

    def build(
        self,
        task: str,
        workspace: Path,
        config: "ClaudeConfig",
        stream: bool = False,
    ) -> list[str]:
        """
        Build command arguments for Claude CLI.

        Args:
            task: Task description
            workspace: Working directory (used for Bash tool restriction)
            config: Claude configuration
            stream: Whether to use streaming output

        Returns:
            List of command arguments
        """
        output_format = "stream-json" if stream else "json"
        cmd_args = [
            "claude",
            "-p",
            task,
            "--output-format",
            output_format,
        ]

        # stream-json requires --verbose when using -p
        if stream:
            cmd_args.append("--verbose")

        # Add config-based arguments
        cmd_args.extend(self._build_tool_args(config, workspace))
        cmd_args.extend(self._build_permission_args(config))
        cmd_args.extend(self._build_dir_args(config))
        cmd_args.extend(self._build_model_args(config))

        return cmd_args

    def _build_tool_args(self, config: "ClaudeConfig", workspace: Path) -> list[str]:
        """Build tool restriction arguments."""
        args = []

        if config.allowed_tools:
            tools = self._process_allowed_tools(config.allowed_tools, workspace)
            args.extend(["--allowedTools", tools])

        if config.disallowed_tools:
            tools = ",".join(config.disallowed_tools)
            args.extend(["--disallowedTools", tools])

        return args

    def _build_permission_args(self, config: "ClaudeConfig") -> list[str]:
        """Build permission mode arguments."""
        if config.permission_mode and config.permission_mode != "default":
            return ["--permission-mode", config.permission_mode]
        return []

    def _build_dir_args(self, config: "ClaudeConfig") -> list[str]:
        """Build additional directory arguments."""
        args = []
        if config.add_dirs:
            for d in config.add_dirs:
                args.extend(["--add-dir", d])
        if config.max_turns:
            args.extend(["--max-turns", str(config.max_turns)])
        return args

    def _build_model_args(self, config: "ClaudeConfig") -> list[str]:
        """Build model selection arguments."""
        if config.model:
            return ["--model", config.model]
        return []

    def _process_allowed_tools(self, tools: list, workspace: Path) -> str:
        """
        Process allowed tools list, auto-add workspace path restriction for Bash.

        Args:
            tools: List of tool names
            workspace: Workspace path for Bash restriction

        Returns:
            Comma-separated tool list with restrictions
        """
        processed = []
        for tool in tools:
            if tool == "Bash":
                # Auto-add workspace path restriction
                workspace_path = str(workspace).replace("\\", "/")
                processed.append(f"Bash({workspace_path}/*)")
            else:
                processed.append(tool)
        return ",".join(processed)


__all__ = ["CommandBuilder"]
