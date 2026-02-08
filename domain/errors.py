"""
Domain Errors - Structured error types for the domain layer.

These are extracted from types.py to maintain separation of concerns.
The original types.py is preserved for backward compatibility.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


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


class DomainError(Exception):
    """Base class for all domain errors."""

    def __init__(self, message: str, code: ErrorCode = ErrorCode.UNKNOWN):
        super().__init__(message)
        self.code = code
        self.message = message


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
    details: dict[str, Any] = field(default_factory=dict)

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


__all__ = [
    "ErrorCode",
    "DomainError",
    "ValidationError",
    "ExecutionError",
    "IOError",
]
