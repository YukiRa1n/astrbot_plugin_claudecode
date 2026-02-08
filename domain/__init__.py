"""
Domain Layer - Core business types and interfaces.

This layer has NO external dependencies and defines the core contracts.
"""

from .errors import (
    DomainError,
    ErrorCode,
    ExecutionError,
    IOError,
    ValidationError,
)
from .interfaces import (
    IChunkParser,
    ICommandBuilder,
    IConfigValidator,
    IConfigWriter,
    IOutputParser,
    IPathResolver,
    IProcessRunner,
)

__all__ = [
    # Interfaces
    "ICommandBuilder",
    "IProcessRunner",
    "IOutputParser",
    "IChunkParser",
    "IPathResolver",
    "IConfigWriter",
    "IConfigValidator",
    # Errors
    "DomainError",
    "ValidationError",
    "ExecutionError",
    "IOError",
    "ErrorCode",
]
