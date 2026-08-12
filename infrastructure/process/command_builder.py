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
        # 任务以 '-' 开头时用 '--' 分隔，避免被 claude 解析为选项
        task_arg = ["--", task] if task.startswith("-") else [task]
        cmd_args = [
            "claude",
            "-p",
            *task_arg,
            "--output-format",
            output_format,
        ]

        # stream-json requires --verbose when using -p
        if stream:
            cmd_args.append("--verbose")

        # 非交互模式默认会持久化会话/提示/工具输出到磁盘（workspace 内），
        # 敏感聊天内容可能被后续会话或备份恢复。显式关闭会话持久化。
        cmd_args.append("--no-session-persistence")

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
            allowed, disallowed = self._process_allowed_tools(
                config.allowed_tools, workspace, config.add_dirs or []
            )
            args.extend(["--allowedTools", allowed])

            # 安全边界：Claude Code 的权限匹配基于命令字符串前缀（如
            # Bash(<workspace>/*)），不解析 OS 路径。路径穿越（../../）可
            # 绕过前缀匹配，因此 Bash 不能作为文件系统隔离手段。
            # 默认禁用 Bash，仅当配置显式允许时才保留。
            if "Bash" not in config.allowed_tools:
                disallowed.append("Bash")
            if disallowed:
                args.extend(["--disallowedTools", ",".join(dict.fromkeys(disallowed))])

        if config.disallowed_tools:
            tools = ",".join(config.disallowed_tools)
            args.extend(["--disallowedTools", tools])

        return args

    def _build_permission_args(self, config: "ClaudeConfig") -> list[str]:
        """Build permission mode arguments.

        插件在非交互模式(-p)下运行 claude CLI。默认权限模式(default)在
        非交互模式下无法写文件（端到端测试确认），会削弱工具的文件操作能力。
        因此 default 映射为 acceptEdits：允许编辑/写文件，但危险命令仍需确认。
        """
        mode = config.permission_mode
        if not mode or mode == "default":
            mode = "acceptEdits"
        return ["--permission-mode", mode]

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

    def _process_allowed_tools(
        self, tools: list, workspace: Path, add_dirs: list | None = None
    ) -> tuple[str, list[str]]:
        """
        Process allowed tools list, auto-add path restrictions.

        Only the workspace and explicitly configured add_dirs are reachable by
        file tools. This is a security boundary: chat messages are untrusted
        input that drives the Claude Code agent, and unrestricted
        Read/Write/Edit/Glob/Grep would allow reading/writing arbitrary files
        on the host.

        Args:
            tools: List of tool names
            workspace: Workspace path for tool restriction
            add_dirs: Additional directories explicitly allowed by config

        Returns:
            ``(allowed_tools_csv, disallowed_rules)`` — the comma-separated
            allowed tool list plus path rules that must be disallowed to keep
            secrets out of the agent's reach.
        """
        # Paths the agent is allowed to touch: workspace + configured add_dirs
        allowed_paths = [str(workspace)]
        if add_dirs:
            allowed_paths.extend(str(d) for d in add_dirs if str(d).strip())
        # 规范化斜杠，并追加目录前缀规则
        path_rules = [p.replace("\\", "/") for p in allowed_paths]

        # 受路径限制的工具：目录参数为 workspace（Bash 使用子目录通配）
        dir_restricted = {
            "Bash": [f"Bash({p}/*)" for p in path_rules],
            "Read": [f"Read({p})" for p in path_rules],
            "Write": [f"Write({p})" for p in path_rules],
            "Edit": [f"Edit({p})" for p in path_rules],
            "Glob": [f"Glob({p})" for p in path_rules],
            "Grep": [f"Grep({p})" for p in path_rules],
        }

        # 敏感文件排除：隔离配置（.claude/settings.json）包含明文密钥，
        # 即使 agent 可访问 workspace 也不应读到这些文件。
        # Claude Code 权限匹配基于前缀，`Read(<workspace>)` 覆盖整个目录，
        # 必须显式加入 disallowed 规则才能拦截。
        processed = []
        disallowed: list[str] = []
        for tool in tools:
            processed.extend(dir_restricted.get(tool, [tool]))
            if tool in {"Read", "Glob", "Grep"}:
                for p in path_rules:
                    if tool == "Read":
                        disallowed.append(f"Read({p}/.claude/settings.json)")
                        disallowed.append(f"Read({p}/.claude.json)")
                    else:
                        disallowed.append(f"{tool}({p}/.claude/**)")
        return ",".join(processed), disallowed


__all__ = ["CommandBuilder"]
