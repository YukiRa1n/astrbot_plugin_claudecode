"""
Domain Interfaces - Core contracts for dependency inversion.

All infrastructure implementations MUST implement these interfaces.
This enables testing with mocks and swapping implementations.
"""

from abc import abstractmethod
from pathlib import Path
from typing import Protocol, AsyncIterator, Optional, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import Result, ExecutionResult, ExecutionError, StreamChunk, ClaudeConfig


@runtime_checkable
class ICommandBuilder(Protocol):
    """Builds CLI command arguments from task and config."""

    @abstractmethod
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
            workspace: Working directory
            config: Claude configuration
            stream: Whether to use streaming output

        Returns:
            List of command arguments
        """
        ...


@runtime_checkable
class IProcessRunner(Protocol):
    """Executes subprocess commands."""

    @abstractmethod
    async def run(
        self,
        cmd_args: list[str],
        cwd: Path,
        timeout: int,
    ) -> tuple[str, str, int]:
        """
        Run command and return output.

        Args:
            cmd_args: Command arguments
            cwd: Working directory
            timeout: Timeout in seconds

        Returns:
            Tuple of (stdout, stderr, returncode)
        """
        ...

    @abstractmethod
    async def run_stream(
        self,
        cmd_args: list[str],
        cwd: Path,
        timeout: int,
    ) -> AsyncIterator[bytes]:
        """
        Run command with streaming output.

        Args:
            cmd_args: Command arguments
            cwd: Working directory
            timeout: Timeout in seconds

        Yields:
            Output bytes as they arrive
        """
        ...


@runtime_checkable
class IOutputParser(Protocol):
    """Parses CLI output into structured results."""

    @abstractmethod
    def parse(
        self,
        stdout: str,
        stderr: str,
        duration_ms: float,
    ) -> "Result[ExecutionResult, ExecutionError]":
        """
        Parse CLI output into ExecutionResult.

        Args:
            stdout: Standard output
            stderr: Standard error
            duration_ms: Execution duration

        Returns:
            Result containing ExecutionResult or ExecutionError
        """
        ...


@runtime_checkable
class IChunkParser(Protocol):
    """Parses streaming output chunks."""

    @abstractmethod
    def parse_line(self, line: str) -> Optional["StreamChunk"]:
        """
        Parse a single line of streaming output.

        Args:
            line: Raw line from stdout

        Returns:
            StreamChunk if parseable, None otherwise
        """
        ...


@runtime_checkable
class IPathResolver(Protocol):
    """Resolves Claude configuration paths."""

    @property
    @abstractmethod
    def claude_dir(self) -> Path:
        """Path to ~/.claude directory."""
        ...

    @property
    @abstractmethod
    def settings_file(self) -> Path:
        """Path to settings.json."""
        ...

    @property
    @abstractmethod
    def claude_json(self) -> Path:
        """Path to ~/.claude.json."""
        ...


@runtime_checkable
class IConfigWriter(Protocol):
    """Writes configuration files."""

    @abstractmethod
    def write_settings(self, settings: dict, path: Path) -> "Result[None, IOError]":
        """Write settings to file."""
        ...

    @abstractmethod
    def write_claude_json(self, data: dict, path: Path) -> "Result[None, IOError]":
        """Write .claude.json file."""
        ...


@runtime_checkable
class IConfigValidator(Protocol):
    """Validates configuration."""

    @abstractmethod
    def validate(self, config: "ClaudeConfig") -> "Result[ClaudeConfig, ValidationError]":
        """Validate configuration and return result."""
        ...


# Import error types for type hints
from .errors import IOError, ValidationError
