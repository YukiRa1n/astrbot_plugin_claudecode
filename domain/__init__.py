"""
Domain Layer - Core business types and interfaces.

This layer has NO external dependencies and defines the core contracts.
"""

from .interfaces import (
    ICommandBuilder,
    IProcessRunner,
    IOutputParser,
    IChunkParser,
    IPathResolver,
    IConfigWriter,
    IConfigValidator,
)
from .errors import (
    DomainError,
    ValidationError,
    ExecutionError,
    IOError,
    ErrorCode,
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
