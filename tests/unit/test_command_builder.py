"""
Test Command Builder - Unit tests for CommandBuilder.
"""

import pytest
from pathlib import Path

from ...infrastructure.process.command_builder import CommandBuilder
from ...types import ClaudeConfig


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
        """Test command with allowed tools."""
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
        assert cmd[idx + 1] == "Read,Write"

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

    def test_build_default_permission_mode_not_added(self):
        """Test default permission mode is not added."""
        config = ClaudeConfig(
            auth_token="test",
            permission_mode="default",
        )
        cmd = self.builder.build(
            task="Test",
            workspace=self.workspace,
            config=config,
        )

        assert "--permission-mode" not in cmd

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
