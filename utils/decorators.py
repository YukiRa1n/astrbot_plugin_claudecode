"""
AOP Decorators - Cross-cutting concerns as decorators.

Provides logging, timeout, and retry functionality without polluting business logic.
"""

import asyncio
import functools
import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger("astrbot")

F = TypeVar("F", bound=Callable[..., Any])


def log_entry_exit(func: F) -> F:
    """
    Decorator to log function entry and exit.

    Supports both sync and async functions.
    Logs function name, arguments (truncated), and duration.
    """
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        func_name = func.__qualname__
        args_preview = _format_args(args, kwargs)
        logger.info(f"[ENTRY] {func_name} {args_preview}")
        start_time = time.time()

        try:
            result = await func(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000
            logger.info(f"[EXIT] {func_name} duration_ms={duration_ms:.2f}")
            return result
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"[ERROR] {func_name} {type(e).__name__}: {e} duration_ms={duration_ms:.2f}")
            raise

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        func_name = func.__qualname__
        args_preview = _format_args(args, kwargs)
        logger.info(f"[ENTRY] {func_name} {args_preview}")
        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000
            logger.info(f"[EXIT] {func_name} duration_ms={duration_ms:.2f}")
            return result
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"[ERROR] {func_name} {type(e).__name__}: {e} duration_ms={duration_ms:.2f}")
            raise

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


def with_timeout(default_timeout: int = 300):
    """
    Decorator to add timeout to async functions.

    Args:
        default_timeout: Default timeout in seconds

    Usage:
        @with_timeout(60)
        async def my_func():
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, timeout: int = None, **kwargs):
            actual_timeout = timeout or default_timeout
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=actual_timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(f"[TIMEOUT] {func.__qualname__} exceeded {actual_timeout}s")
                raise

        return wrapper
    return decorator


def retry(max_attempts: int = 3, delay: float = 1.0, exceptions: tuple = (Exception,)):
    """
    Decorator to retry function on failure.

    Args:
        max_attempts: Maximum number of attempts
        delay: Delay between attempts in seconds
        exceptions: Tuple of exceptions to catch

    Usage:
        @retry(max_attempts=3, delay=1.0)
        async def my_func():
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        logger.warning(
                            f"[RETRY] {func.__qualname__} attempt {attempt}/{max_attempts} failed: {e}"
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"[RETRY] {func.__qualname__} all {max_attempts} attempts failed"
                        )
            raise last_exception

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        logger.warning(
                            f"[RETRY] {func.__qualname__} attempt {attempt}/{max_attempts} failed: {e}"
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"[RETRY] {func.__qualname__} all {max_attempts} attempts failed"
                        )
            raise last_exception

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


def _format_args(args: tuple, kwargs: dict, max_len: int = 50) -> str:
    """Format function arguments for logging."""
    parts = []

    # Skip 'self' argument
    display_args = args[1:] if args and hasattr(args[0], "__class__") else args

    for arg in display_args:
        s = str(arg)
        if len(s) > max_len:
            s = s[:max_len] + "..."
        parts.append(s)

    for k, v in kwargs.items():
        s = str(v)
        if len(s) > max_len:
            s = s[:max_len] + "..."
        parts.append(f"{k}={s}")

    if not parts:
        return ""
    return f"inputs={{{', '.join(parts)}}}"


__all__ = ["log_entry_exit", "with_timeout", "retry"]
