"""
Config Writer - Writes configuration files.

Single responsibility: Write configuration to files.
Pure I/O operations with Result-based error handling.
"""

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from ...domain.errors import IOError
from .models import Result, err, ok

if TYPE_CHECKING:
    pass

logger = logging.getLogger("astrbot")


class ConfigWriter:
    """
    Writes Claude configuration files.

    Implements IConfigWriter interface.
    Handles file I/O with proper error handling.
    """

    def write_settings(self, settings: dict, path: Path) -> Result[None, IOError]:
        """
        Write settings to JSON file.

        Args:
            settings: Settings dictionary
            path: Target file path

        Returns:
            Result indicating success or IOError
        """
        return self._write_json(settings, path, "settings")

    def write_claude_json(self, data: dict, path: Path) -> Result[None, IOError]:
        """
        Write .claude.json file.

        Args:
            data: Data dictionary
            path: Target file path

        Returns:
            Result indicating success or IOError
        """
        return self._write_json(data, path, "claude.json")

    def _write_json(self, data: dict, path: Path, name: str) -> Result[None, IOError]:
        """
        Write JSON data to file.

        Args:
            data: Data to write
            path: Target file path
            name: File name for logging

        Returns:
            Result indicating success or IOError
        """
        try:
            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            logger.debug(f"[ConfigWriter] Wrote {name} to {path}")
            return ok(None)

        except PermissionError as e:
            error = IOError(str(path), "write", f"Permission denied: {e}")
            logger.error(f"[ConfigWriter] {error}")
            return err(error)

        except Exception as e:
            error = IOError(str(path), "write", f"Failed to write: {e}")
            logger.error(f"[ConfigWriter] {error}")
            return err(error)


__all__ = ["ConfigWriter"]
