"""
Output Parser - Parses CLI output into structured results.

Single responsibility: Transform raw CLI output into ExecutionResult.
No subprocess execution, no I/O - pure transformation.
"""

import json
import logging
from typing import TYPE_CHECKING

from ...types import (
    Result,
    ExecutionResult,
    ExecutionError,
    ErrorCode,
    ok,
    err,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger("astrbot")


class OutputParser:
    """
    Parses Claude CLI JSON output.

    Implements IOutputParser interface.
    Pure function-like class: no side effects, deterministic output.
    """

    def parse(
        self,
        stdout: str,
        stderr: str,
        duration_ms: float,
        returncode: int | None = None,
    ) -> Result[ExecutionResult, ExecutionError]:
        """
        Parse CLI output into ExecutionResult.

        Args:
            stdout: Standard output from CLI
            stderr: Standard error from CLI
            duration_ms: Execution duration in milliseconds

        Returns:
            Result containing ExecutionResult or ExecutionError
        """
        try:
            data = json.loads(stdout)
            return self._parse_json_data(
                data, stdout, stderr, duration_ms, returncode
            )

        except json.JSONDecodeError as e:
            return self._handle_parse_error(
                e, stdout, stderr, duration_ms, returncode
            )

    def _parse_json_data(
        self,
        data: dict,
        stdout: str,
        stderr: str,
        duration_ms: float,
        returncode: int | None,
    ) -> Result[ExecutionResult, ExecutionError]:
        """Parse valid JSON data into result."""
        is_error = data.get("is_error", False)

        if is_error:
            logger.warning(
                f"[OutputParser] CLI returned error: {data.get('result', 'Unknown error')}"
            )
            return err(
                ExecutionError(
                    code=ErrorCode.CLI_ERROR,
                    message=data.get("result", "Unknown CLI error"),
                    details={"stdout": stdout, "stderr": stderr, "data": data},
                )
            )

        if returncode is not None and returncode != 0:
            return err(
                ExecutionError(
                    code=ErrorCode.CLI_ERROR,
                    message="Claude CLI exited with non-zero status",
                    details={
                        "stdout": stdout,
                        "stderr": stderr,
                        "returncode": returncode,
                        "data": data,
                    },
                )
            )

        result = ExecutionResult(
            output=data.get("result", ""),
            cost_usd=data.get("total_cost_usd", 0.0),
            session_id=data.get("session_id", ""),
            duration_ms=duration_ms,
            metadata={"raw_data": data},
        )
        return ok(result)

    def _handle_parse_error(
        self,
        error: json.JSONDecodeError,
        stdout: str,
        stderr: str,
        duration_ms: float,
        returncode: int | None,
    ) -> Result[ExecutionResult, ExecutionError]:
        """Handle JSON parse errors with fallback logic."""
        logger.warning(f"[OutputParser] Failed to parse JSON: {error}")

        if returncode is not None and returncode != 0:
            return err(
                ExecutionError(
                    code=ErrorCode.PARSE_ERROR,
                    message=f"Failed to parse CLI output: {error}",
                    details={
                        "stdout": stdout,
                        "stderr": stderr,
                        "returncode": returncode,
                    },
                )
            )

        # Check stderr for error indicators
        has_error = stderr and (
            "error" in stderr.lower() or "failed" in stderr.lower()
        )

        if has_error or not stdout:
            return err(
                ExecutionError(
                    code=ErrorCode.PARSE_ERROR,
                    message=f"Failed to parse CLI output: {error}",
                    details={"stdout": stdout, "stderr": stderr},
                )
            )

        # Fallback: treat as success with raw output
        result = ExecutionResult(
            output=stdout or stderr,
            cost_usd=0.0,
            session_id="",
            duration_ms=duration_ms,
            metadata={"parse_error": str(error)},
        )
        return ok(result)


__all__ = ["OutputParser"]
