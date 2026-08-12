"""
Test Command Builder - Unit tests for CommandBuilder.
"""

from pathlib import Path

from ...infrastructure.process.command_builder import CommandBuilder
from ...models import ClaudeConfig


class TestCommandBuilder:
    """Tests for CommandBuilder."""

    def setup_method(self):
        """Set up test fixtures."""
        self.builder = CommandBuilder()
        self.workspace = Path("/test/workspace")

    def test_build_basic_command(self):
        """Test basic command building."""
        config = ClaudeConfig(auth_token="test")
        cmd = self.builder.build(
            task="Hello world",
            workspace=self.workspace,
            config=config,
            stream=False,
        )

        assert cmd[0] == "claude"
        assert "-p" in cmd
        assert "Hello world" in cmd
        assert "--output-format" in cmd
        assert "json" in cmd

    def test_build_task_starting_with_dash_uses_separator(self):
        """以 '-' 开头的任务需加 '--' 分隔，避免被解析为选项。"""
        config = ClaudeConfig(auth_token="test")
        cmd = self.builder.build(
            task="--help",
            workspace=self.workspace,
            config=config,
        )
        idx = cmd.index("-p")
        # -p 后的参数必须是 ["--", "--help"]
        assert cmd[idx + 1] == "--"
        assert cmd[idx + 2] == "--help"

    def test_build_normal_task_no_separator(self):
        """普通任务不加 '--' 分隔。"""
        config = ClaudeConfig(auth_token="test")
        cmd = self.builder.build(
            task="refactor this",
            workspace=self.workspace,
            config=config,
        )
        idx = cmd.index("-p")
        assert cmd[idx + 1] == "refactor this"

    def test_build_stream_command(self):
        """Test streaming command building."""
        config = ClaudeConfig(auth_token="test")
        cmd = self.builder.build(
            task="Hello world",
            workspace=self.workspace,
            config=config,
            stream=True,
        )

        assert "stream-json" in cmd
        assert "--verbose" in cmd

    def test_build_with_allowed_tools(self):
        """Test file tools get workspace path restriction (security boundary)."""
        config = ClaudeConfig(
            auth_token="test",
            allowed_tools=["Read", "Write"],
        )
        cmd = self.builder.build(
            task="Test",
            workspace=self.workspace,
            config=config,
        )

        assert "--allowedTools" in cmd
        idx = cmd.index("--allowedTools")
        tools = cmd[idx + 1]
        # Read/Write 被限制在 workspace 内，不再是无参全盘工具
        assert "Read(/test/workspace)" in tools
        assert "Write(/test/workspace)" in tools

    def test_build_with_bash_tool_restriction(self):
        """Test Bash tool gets workspace restriction."""
        config = ClaudeConfig(
            auth_token="test",
            allowed_tools=["Bash"],
        )
        cmd = self.builder.build(
            task="Test",
            workspace=Path("/my/workspace"),
            config=config,
        )

        assert "--allowedTools" in cmd
        idx = cmd.index("--allowedTools")
        assert "Bash(/my/workspace/*)" in cmd[idx + 1]

    def test_all_file_tools_are_workspace_restricted(self):
        """All path-based tools must be workspace-restricted, not unrestricted."""
        config = ClaudeConfig(
            auth_token="test",
            allowed_tools=["Read", "Write", "Edit", "Glob", "Grep", "Bash"],
        )
        cmd = self.builder.build(
            task="Test",
            workspace=self.workspace,
            config=config,
        )
        idx = cmd.index("--allowedTools")
        tools = cmd[idx + 1]
        assert "Read(/test/workspace)" in tools
        assert "Write(/test/workspace)" in tools
        assert "Edit(/test/workspace)" in tools
        assert "Glob(/test/workspace)" in tools
        assert "Grep(/test/workspace)" in tools
        assert "Bash(/test/workspace/*)" in tools
        # 绝不能出现裸工具名（无路径限制）
        assert "Read," not in tools
        assert tools != "Read,Write,Edit,Glob,Grep,Bash"

    def test_add_dirs_expand_allowlist(self):
        """add_dirs 显式声明的目录也会被加入工具白名单。"""
        config = ClaudeConfig(
            auth_token="test",
            allowed_tools=["Read", "Bash"],
            add_dirs=["/data/extra"],
        )
        cmd = self.builder.build(
            task="Test",
            workspace=self.workspace,
            config=config,
        )
        idx = cmd.index("--allowedTools")
        tools = cmd[idx + 1]
        assert "Read(/test/workspace)" in tools
        assert "Read(/data/extra)" in tools
        assert "Bash(/test/workspace/*)" in tools
        assert "Bash(/data/extra/*)" in tools

    def test_windows_paths_normalized_to_forward_slashes(self):
        """Windows 路径反斜杠应规范化为正斜杠，避免权限规则匹配失败。"""
        config = ClaudeConfig(
            auth_token="test",
            allowed_tools=["Read"],
        )
        cmd = self.builder.build(
            task="Test",
            workspace=Path("C:/Users/me/workspace"),
            config=config,
        )
        idx = cmd.index("--allowedTools")
        assert "Read(C:/Users/me/workspace)" in cmd[idx + 1]

    def test_build_with_disallowed_tools(self):
        """Test command with disallowed tools."""
        config = ClaudeConfig(
            auth_token="test",
            disallowed_tools=["Bash", "Edit"],
        )
        cmd = self.builder.build(
            task="Test",
            workspace=self.workspace,
            config=config,
        )

        assert "--disallowedTools" in cmd
        idx = cmd.index("--disallowedTools")
        assert cmd[idx + 1] == "Bash,Edit"

    def test_build_with_permission_mode(self):
        """Test command with permission mode."""
        config = ClaudeConfig(
            auth_token="test",
            permission_mode="acceptEdits",
        )
        cmd = self.builder.build(
            task="Test",
            workspace=self.workspace,
            config=config,
        )

        assert "--permission-mode" in cmd
        idx = cmd.index("--permission-mode")
        assert cmd[idx + 1] == "acceptEdits"

    def test_build_default_permission_mode_maps_to_accept_edits(self):
        """默认权限模式在非交互模式下映射为 acceptEdits，确保能写文件。

        插件在非交互模式(-p)下运行 claude CLI。默认权限模式(default)在
        非交互模式下无法写文件（端到端测试确认），会削弱工具的文件操作能力。
        因此 default 映射为 acceptEdits：允许编辑/写文件，但危险命令仍需确认。
        """
        config = ClaudeConfig(
            auth_token="test",
            permission_mode="default",
        )
        cmd = self.builder.build(
            task="Test",
            workspace=self.workspace,
            config=config,
        )

        idx = cmd.index("--permission-mode")
        assert cmd[idx + 1] == "acceptEdits"

    def test_build_explicit_permission_mode_respected(self):
        """显式指定的权限模式原样传递。"""
        config = ClaudeConfig(
            auth_token="test",
            permission_mode="acceptEdits",
        )
        cmd = self.builder.build(
            task="Test",
            workspace=self.workspace,
            config=config,
        )
        idx = cmd.index("--permission-mode")
        assert cmd[idx + 1] == "acceptEdits"

    def test_build_with_model(self):
        """Test command with model selection."""
        config = ClaudeConfig(
            auth_token="test",
            model="claude-opus-4-20250514",
        )
        cmd = self.builder.build(
            task="Test",
            workspace=self.workspace,
            config=config,
        )

        assert "--model" in cmd
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "claude-opus-4-20250514"

    def test_build_with_max_turns(self):
        """Test command with max turns."""
        config = ClaudeConfig(
            auth_token="test",
            max_turns=5,
        )
        cmd = self.builder.build(
            task="Test",
            workspace=self.workspace,
            config=config,
        )

        assert "--max-turns" in cmd
        idx = cmd.index("--max-turns")
        assert cmd[idx + 1] == "5"

    def test_build_with_add_dirs(self):
        """Test command with additional directories."""
        config = ClaudeConfig(
            auth_token="test",
            add_dirs=["/dir1", "/dir2"],
        )
        cmd = self.builder.build(
            task="Test",
            workspace=self.workspace,
            config=config,
        )

        assert cmd.count("--add-dir") == 2
        assert "/dir1" in cmd
        assert "/dir2" in cmd
