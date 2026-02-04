"""
AstrBot Claude Code Plugin

Integrates Claude Code CLI as an LLM function tool.
Following Unix philosophy: explicit I/O, composable modules, single responsibility.

Architecture (v3.0 - Onion Architecture):
- domain/: Core interfaces and error types (no external dependencies)
- application/: Use case orchestration (executor facade)
- infrastructure/: Concrete implementations (process, stream, config, installer)
- utils/: Cross-cutting concerns (decorators, platform compatibility)
"""

__version__ = "3.0.0"

# Re-export plugin class
from .main import ClaudeCodePlugin

# Re-export types for backward compatibility
from .types import (
    # Result pattern
    Ok,
    Err,
    Result,
    ok,
    err,
    # Error types
    ErrorCode,
    ValidationError,
    ExecutionError,
    IOError,
    # Execution types
    ExecutionResult,
    ChunkType,
    StreamChunk,
    ProgressCallback,
    # Config types
    ClaudeConfig,
)

# Re-export application layer
from .application import ClaudeExecutor

# Re-export infrastructure components
from .infrastructure import (
    CommandBuilder,
    ProcessRunner,
    OutputParser,
    ChunkParser,
    StreamProcessor,
    PathResolver,
    ConfigValidator,
    ConfigWriter,
    validate_config,
)

# Re-export utils
from .utils import (
    log_entry_exit,
    with_timeout,
    retry,
    is_process_running,
    start_background_process,
)

__all__ = [
    # Version
    "__version__",
    # Plugin
    "ClaudeCodePlugin",
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
    # Application
    "ClaudeExecutor",
    # Infrastructure
    "CommandBuilder",
    "ProcessRunner",
    "OutputParser",
    "ChunkParser",
    "StreamProcessor",
    "PathResolver",
    "ConfigValidator",
    "ConfigWriter",
    "validate_config",
    # Utils
    "log_entry_exit",
    "with_timeout",
    "retry",
    "is_process_running",
    "start_background_process",
]
