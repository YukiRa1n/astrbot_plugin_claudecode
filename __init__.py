"""
AstrBot Claude Code Plugin

Integrates Claude Code CLI as an LLM function tool.
"""

from .main import ClaudeCodePlugin
from .types import (
    Result,
    Ok,
    Err,
    ok,
    err,
    ErrorCode,
    ExecutionResult,
    ExecutionError,
    StreamChunk,
    ChunkType,
)

__all__ = [
    "ClaudeCodePlugin",
    "Result",
    "Ok",
    "Err",
    "ok",
    "err",
    "ErrorCode",
    "ExecutionResult",
    "ExecutionError",
    "StreamChunk",
    "ChunkType",
]

__version__ = "2.1.0"
