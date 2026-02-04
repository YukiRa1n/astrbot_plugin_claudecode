"""
Path Resolver - Resolves Claude configuration paths.

Single responsibility: Provide consistent path resolution.
No I/O operations - pure path computation.
"""

from pathlib import Path


class PathResolver:
    """
    Resolves Claude configuration paths.

    Implements IPathResolver interface.
    All paths are computed lazily and cached.
    """

    def __init__(self, home_dir: Path = None):
        """
        Initialize path resolver.

        Args:
            home_dir: Optional home directory override (for testing)
        """
        self._home = home_dir or Path.home()

    @property
    def claude_dir(self) -> Path:
        """Path to ~/.claude directory."""
        return self._home / ".claude"

    @property
    def settings_file(self) -> Path:
        """Path to settings.json."""
        return self.claude_dir / "settings.json"

    @property
    def claude_json(self) -> Path:
        """Path to ~/.claude.json."""
        return self._home / ".claude.json"

    @property
    def plugins_dir(self) -> Path:
        """Path to plugins directory."""
        return self.claude_dir / "plugins"

    @property
    def marketplaces_dir(self) -> Path:
        """Path to marketplaces directory."""
        return self.plugins_dir / "marketplaces"

    @property
    def known_marketplaces_file(self) -> Path:
        """Path to known_marketplaces.json."""
        return self.plugins_dir / "known_marketplaces.json"


__all__ = ["PathResolver"]
