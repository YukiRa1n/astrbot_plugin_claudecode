"""
Marketplace Manager - Manages Claude plugin marketplace.

Single responsibility: Manage marketplace configuration and plugins.
"""

import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Tuple

from ..config.path_resolver import PathResolver

logger = logging.getLogger("astrbot")


class MarketplaceManager:
    """
    Manages Claude plugin marketplace.

    Handles marketplace configuration, updates, and plugin installation.
    """

    OFFICIAL_MARKETPLACE = "anthropics/claude-plugins-official"
    MARKETPLACE_HTTPS_URL = "https://github.com/anthropics/claude-plugins-official.git"

    def __init__(self, path_resolver: PathResolver = None):
        """
        Initialize marketplace manager.

        Args:
            path_resolver: Optional path resolver (creates default if None)
        """
        self._path_resolver = path_resolver or PathResolver()
        self._marketplace_ready = False

    async def has_marketplace(self) -> bool:
        """Check if marketplace is configured."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "claude",
                "plugin",
                "marketplace",
                "list",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            output = stdout.decode()
            return "claude-plugins-official" in output
        except Exception as e:
            logger.warning(f"[MarketplaceManager] Failed to check marketplace: {e}")
            return False

    async def add_marketplace(self) -> Tuple[bool, str]:
        """Add official marketplace (with fallback)."""
        logger.info("[MarketplaceManager] Adding official marketplace...")

        # Try using claude command first
        try:
            proc = await asyncio.create_subprocess_exec(
                "claude",
                "plugin",
                "marketplace",
                "add",
                self.OFFICIAL_MARKETPLACE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            if proc.returncode == 0:
                return True, "Marketplace added via claude command"
        except Exception as e:
            logger.warning(f"[MarketplaceManager] Claude command failed: {e}")

        # Fallback: manual setup
        return await self._manual_add_marketplace()

    async def _manual_add_marketplace(self) -> Tuple[bool, str]:
        """Manually clone and configure marketplace (fallback)."""
        logger.info("[MarketplaceManager] Using manual marketplace setup...")

        marketplaces_dir = self._path_resolver.marketplaces_dir
        target_dir = marketplaces_dir / "claude-plugins-official"
        config_file = self._path_resolver.known_marketplaces_file

        # Create directory
        marketplaces_dir.mkdir(parents=True, exist_ok=True)

        # Clone if not exists
        if not target_dir.exists():
            try:
                proc = await asyncio.create_subprocess_exec(
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    self.MARKETPLACE_HTTPS_URL,
                    str(target_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(proc.communicate(), timeout=120)
                if proc.returncode != 0:
                    return False, "Git clone failed"
            except Exception as e:
                return False, f"Git clone error: {e}"

        # Create config file
        config = {
            "claude-plugins-official": {
                "source": {"source": "github", "repo": self.OFFICIAL_MARKETPLACE},
                "installLocation": str(target_dir),
                "lastUpdated": datetime.utcnow().isoformat() + "Z",
            }
        }
        config_file.write_text(json.dumps(config, indent=2))
        logger.info("[MarketplaceManager] Marketplace configured manually")
        return True, "Marketplace added manually"

    async def update_marketplace(self) -> Tuple[bool, str]:
        """Update marketplace."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "claude",
                "plugin",
                "marketplace",
                "update",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            if proc.returncode == 0:
                return True, "Marketplace updated"
            return False, stderr.decode()
        except asyncio.TimeoutError:
            logger.warning("[MarketplaceManager] Marketplace update timeout")
            return False, "Update timeout (60s)"
        except Exception as e:
            logger.warning(f"[MarketplaceManager] Marketplace update failed: {e}")
            return False, str(e)

    async def ensure_marketplace(self) -> Tuple[bool, str]:
        """Ensure marketplace is configured and updated."""
        if self._marketplace_ready:
            return True, "Marketplace ready (cached)"

        if not await self.has_marketplace():
            ok, msg = await self.add_marketplace()
            if not ok:
                return False, f"Failed to add marketplace: {msg}"
            logger.info(f"[MarketplaceManager] {msg}")

        ok, msg = await self.update_marketplace()
        if ok:
            self._marketplace_ready = True
            logger.info(f"[MarketplaceManager] {msg}")
        return ok, msg

    async def install_skill(self, skill_name: str) -> Tuple[bool, str]:
        """Install a Claude Code skill/plugin."""
        # Ensure marketplace is configured
        ok, msg = await self.ensure_marketplace()
        if not ok:
            return False, f"Marketplace not ready: {msg}"

        try:
            proc = await asyncio.create_subprocess_exec(
                "claude",
                "plugin",
                "install",
                skill_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)

            if proc.returncode == 0:
                return True, f"Skill {skill_name} installed"
            return False, stderr.decode()

        except asyncio.TimeoutError:
            logger.warning(f"[MarketplaceManager] Skill install timeout: {skill_name}")
            return False, "Install timeout (60s)"
        except Exception as e:
            logger.warning(f"[MarketplaceManager] Skill install failed: {e}")
            return False, str(e)


__all__ = ["MarketplaceManager"]
