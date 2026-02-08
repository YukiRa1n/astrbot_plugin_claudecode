"""
Claude Code 配置管理器

This module manages Claude Code configuration with explicit validation
and Result-based error handling following functional programming principles.
"""

import json
import logging
from pathlib import Path
from typing import Any

from .types import ClaudeConfig, IOError, Result, ValidationError, err, ok

logger = logging.getLogger("astrbot")


# Validation Functions (Pure, Atomic)
def validate_config(config: ClaudeConfig) -> Result[ClaudeConfig, ValidationError]:
    """
    Validate Claude configuration.

    Args:
        config: Configuration to validate

    Returns:
        Result containing validated config or validation error
    """
    logger.info(
        f"[ENTRY] validate_config auth_present={bool(config.auth_token or config.api_key)}"
    )

    # Check authentication
    if not config.auth_token and not config.api_key:
        error = ValidationError("auth", "需要提供 auth_token 或 api_key")
        logger.warning(f"[ERROR] validate_config: {error}")
        return err(error)

    # Check permission mode
    valid_modes = ["default", "acceptEdits", "plan", "dontAsk"]
    if config.permission_mode not in valid_modes:
        error = ValidationError(
            "permission_mode",
            f"无效的权限模式: {config.permission_mode}, 有效值: {valid_modes}",
        )
        logger.warning(f"[ERROR] validate_config: {error}")
        return err(error)

    # Check timeout range
    if config.timeout_seconds < 10 or config.timeout_seconds > 600:
        error = ValidationError(
            "timeout_seconds",
            f"超时时间应在10-600秒之间, 当前值: {config.timeout_seconds}",
        )
        logger.warning(f"[ERROR] validate_config: {error}")
        return err(error)

    logger.info("[EXIT] validate_config return=success")
    return ok(config)


class ClaudeConfigManager:
    """Claude Code 配置管理器"""

    CLAUDE_DIR = Path.home() / ".claude"
    SETTINGS_FILE = CLAUDE_DIR / "settings.json"
    CLAUDE_JSON = Path.home() / ".claude.json"

    def __init__(self, config: ClaudeConfig):
        self.config = config

    @classmethod
    def from_plugin_config(cls, plugin_config: dict[str, Any]) -> "ClaudeConfigManager":
        """
        Create manager from plugin configuration.

        Args:
            plugin_config: Raw plugin configuration dictionary

        Returns:
            ClaudeConfigManager instance
        """
        # Parse configuration inline
        allowed = plugin_config.get("allowed_tools", "")
        disallowed = plugin_config.get("disallowed_tools", "")
        add_dirs = plugin_config.get("add_dirs", "")

        config = ClaudeConfig(
            auth_token=plugin_config.get("auth_token", ""),
            api_key=plugin_config.get("api_key", ""),
            api_base_url=plugin_config.get("api_base_url", ""),
            model=plugin_config.get("model", ""),
            allowed_tools=[t.strip() for t in allowed.split(",") if t.strip()],
            disallowed_tools=[t.strip() for t in disallowed.split(",") if t.strip()],
            permission_mode=plugin_config.get("permission_mode", "default"),
            add_dirs=[d.strip() for d in add_dirs.split(",") if d.strip()],
            max_turns=plugin_config.get("max_turns", 10),
            timeout_seconds=plugin_config.get("timeout_seconds", 300),
        )
        return cls(config)

    def apply_config(self) -> Result[None, IOError]:
        """
        Apply configuration to Claude Code.

        Returns:
            Result indicating success or I/O error
        """
        logger.info(f"[ENTRY] apply_config config={self.get_config_summary()}")

        try:
            # Create .claude directory
            self.CLAUDE_DIR.mkdir(parents=True, exist_ok=True)

            # Build settings inline
            env = {
                "API_TIMEOUT_MS": str(self.config.timeout_seconds * 1000),
                "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            }

            # Set authentication
            if self.config.auth_token:
                env["ANTHROPIC_AUTH_TOKEN"] = self.config.auth_token
            elif self.config.api_key:
                env["ANTHROPIC_API_KEY"] = self.config.api_key

            # Set Base URL
            if self.config.api_base_url:
                env["ANTHROPIC_BASE_URL"] = self.config.api_base_url

            # Write settings.json
            settings = {"env": env}
            self.SETTINGS_FILE.write_text(
                json.dumps(settings, indent=2), encoding="utf-8"
            )

            # Write .claude.json
            claude_json = {"hasCompletedOnboarding": True}
            self.CLAUDE_JSON.write_text(
                json.dumps(claude_json, indent=2), encoding="utf-8"
            )

            logger.info("[EXIT] apply_config return=success")
            return ok(None)

        except PermissionError as e:
            error = IOError(str(self.CLAUDE_DIR), "write", f"Permission denied: {e}")
            logger.error(f"[ERROR] apply_config: {error}")
            return err(error)

        except Exception as e:
            error = IOError(
                str(self.CLAUDE_DIR), "write", f"Failed to apply config: {e}"
            )
            logger.error(f"[ERROR] apply_config: {error}")
            return err(error)

    def get_config_summary(self) -> str:
        """获取配置摘要"""
        if self.config.auth_token:
            cred_status = "Auth Token: 已配置"
        elif self.config.api_key:
            cred_status = "API Key: 已配置"
        else:
            cred_status = "认证: 未配置"

        base_url = self.config.api_base_url or "官方"
        return f"{cred_status}, Base URL: {base_url}"
