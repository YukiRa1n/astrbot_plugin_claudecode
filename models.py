"""
Claude Code Plugin - Type System

Provides Result pattern for functional error handling and domain-specific types.
Following Unix philosophy: explicit I/O, composable types, zero side effects.

Usage:
    from .models import ok, err, Result, ExecutionResult, ExecutionError

    def execute_task(task: str) -> Result[ExecutionResult, ExecutionError]:
        if not task:
            return err(ExecutionError(ErrorCode.INVALID_CONFIG, "Empty task"))
        return ok(ExecutionResult(output="Done"))
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Generic, TypeVar, Union

# Type variables for generic Result pattern
T = TypeVar("T")
E = TypeVar("E")


# =============================================================================
# Result Pattern - Functional Error Handling
# =============================================================================


@dataclass(frozen=True)
class Ok(Generic[T]):
    """
    Represents a successful result containing a value.

    Attributes:
        value: The successful result value

    Example:
        result = Ok(42)
        if result.is_ok():
            print(result.unwrap())  # 42
    """

    value: T

    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False

    def unwrap(self) -> T:
        return self.value

    def unwrap_or(self, default: T) -> T:
        return self.value


@dataclass(frozen=True)
class Err(Generic[E]):
    """
    Represents a failed result containing an error.

    Attributes:
        error: The error value

    Example:
        result = Err(ValidationError("field", "invalid"))
        if result.is_err():
            print(result.unwrap_err())
    """

    error: E

    def is_ok(self) -> bool:
        return False

    def is_err(self) -> bool:
        return True

    def unwrap(self) -> None:
        raise ValueError(f"Called unwrap on Err: {self.error}")

    def unwrap_or(self, default: T) -> T:
        return default

    def unwrap_err(self) -> E:
        return self.error


# Result type alias
Result = Union[Ok[T], Err[E]]


def ok(value: T) -> Ok[T]:
    """Create a successful Result."""
    return Ok(value)


def err(error: E) -> Err[E]:
    """Create a failed Result."""
    return Err(error)


# =============================================================================
# Error Types
# =============================================================================


class ErrorCode(str, Enum):
    """Structured error codes for programmatic handling."""

    TIMEOUT = "TIMEOUT"
    PARSE_ERROR = "PARSE_ERROR"
    CLI_ERROR = "CLI_ERROR"
    NOT_INSTALLED = "NOT_INSTALLED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    INVALID_CONFIG = "INVALID_CONFIG"
    IO_ERROR = "IO_ERROR"
    UNKNOWN = "UNKNOWN"


@dataclass
class ValidationError:
    """Configuration validation error."""

    field: str
    message: str

    def __str__(self) -> str:
        return f"[{self.field}] {self.message}"


@dataclass
class ExecutionError:
    """
    Structured execution error.

    Attributes:
        code: Error code for programmatic handling
        message: Human-readable error message
        details: Additional context (stdout, stderr, etc.)
    """

    code: ErrorCode
    message: str
    details: dict = field(default_factory=dict)

    def __str__(self) -> str:
        return f"[{self.code.value}] {self.message}"


@dataclass
class IOError:
    """File I/O operation error."""

    path: str
    operation: str
    reason: str

    def __str__(self) -> str:
        return f"[{self.operation}] {self.path}: {self.reason}"


# =============================================================================
# Execution Types
# =============================================================================


@dataclass
class ExecutionResult:
    """
    Successful execution result.

    Attributes:
        output: The main output text from Claude
        cost_usd: Execution cost in USD
        session_id: Claude session identifier
        duration_ms: Execution time in milliseconds
        metadata: Additional execution metadata
    """

    output: str
    cost_usd: float = 0.0
    session_id: str = ""
    duration_ms: float = 0.0
    metadata: dict = field(default_factory=dict)


class ChunkType(str, Enum):
    """Types of streaming chunks."""

    THINKING = "thinking"
    TOOL_USE = "tool_use"
    RESULT = "result"
    ERROR = "error"
    STATUS = "status"


@dataclass
class StreamChunk:
    """
    A chunk of streaming output.

    Attributes:
        chunk_type: Type of this chunk
        content: The chunk content
        timestamp: Unix timestamp when chunk was received
        metadata: Additional chunk metadata
    """

    chunk_type: ChunkType
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


# Type alias for progress callback
ProgressCallback = Callable[[StreamChunk], None]


# =============================================================================
# Configuration Types
# =============================================================================


@dataclass
class ClaudeConfig:
    """
    Claude Code configuration.

    Attributes:
        auth_token: Anthropic authentication token
        api_key: Anthropic API key (alternative to auth_token)
        api_base_url: Custom API base URL
        model: Model identifier
        allowed_tools: List of allowed tool names
        disallowed_tools: List of disallowed tool names
        permission_mode: Permission mode (default/acceptEdits/plan/dontAsk)
        add_dirs: Additional directories to include
        max_turns: Maximum conversation turns
        timeout_seconds: Execution timeout in seconds
    """

    auth_token: str = ""
    api_key: str = ""
    api_base_url: str = ""
    model: str = ""
    allowed_tools: list = field(default_factory=list)
    disallowed_tools: list = field(default_factory=list)
    permission_mode: str = "default"
    add_dirs: list = field(default_factory=list)
    max_turns: int = 10
    timeout_seconds: int = 300


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Result pattern
    "Ok",
    "Err",
    "Result",
    "ok",
    "err",
    # Error types
    "ErrorCode",
    "ValidationError",
    "ExecutionError",
    "IOError",
    # Execution types
    "ExecutionResult",
    "ChunkType",
    "StreamChunk",
    "ProgressCallback",
    # Config types
    "ClaudeConfig",
]
