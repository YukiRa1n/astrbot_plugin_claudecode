"""
Config Validator - Validates Claude configuration.

Single responsibility: Validate configuration and return Result.
No I/O, no side effects - pure validation logic.
"""

import logging
from typing import TYPE_CHECKING

from ...domain.errors import ValidationError
from ...models import ClaudeConfig, Result, err, ok

if TYPE_CHECKING:
    pass

logger = logging.getLogger("astrbot")


class ConfigValidator:
    """
    Validates Claude configuration.

    Implements IConfigValidator interface.
    Pure validation logic with no side effects.
    """

    VALID_PERMISSION_MODES = ["default", "acceptEdits", "plan"]
    MIN_TIMEOUT = 10
    MAX_TIMEOUT = 600

    def validate(self, config: ClaudeConfig) -> Result[ClaudeConfig, ValidationError]:
        """
        Validate configuration and return result.

        Args:
            config: Configuration to validate

        Returns:
            Result containing validated config or ValidationError
        """
        logger.debug(
            f"[ConfigValidator] Validating: auth_present={bool(config.auth_token or config.api_key)}"
        )

        # Check authentication
        auth_error = self._validate_auth(config)
        if auth_error:
            return err(auth_error)

        # Check permission mode
        mode_error = self._validate_permission_mode(config)
        if mode_error:
            return err(mode_error)

        # Check timeout range
        timeout_error = self._validate_timeout(config)
        if timeout_error:
            return err(timeout_error)

        logger.debug("[ConfigValidator] Validation passed")
        return ok(config)

    def _validate_auth(self, config: ClaudeConfig) -> ValidationError | None:
        """Validate authentication configuration.

        隔离模式（配置了 auth_token 或 api_key）必须提供凭据；
        全局模式（未配置任何凭据）依赖 claude CLI 本地登录，无需校验。
        """
        has_credential = bool(config.auth_token or config.api_key)
        if has_credential:
            return None
        # 无凭据：视为全局模式，允许使用本机已登录的 Claude CLI。
        # 仅当配置了 api_base_url（但无凭据）时提示——隔离模式需要密钥。
        if config.api_base_url:
            error = ValidationError(
                "auth", "配置了 api_base_url 但缺少 auth_token/api_key"
            )
            logger.warning(f"[ConfigValidator] {error}")
            return error
        return None

    def _validate_permission_mode(self, config: ClaudeConfig) -> ValidationError | None:
        """Validate permission mode."""
        if config.permission_mode is not None and config.permission_mode not in self.VALID_PERMISSION_MODES:
            error = ValidationError(
                "permission_mode",
                f"无效的权限模式: {config.permission_mode}, 有效值: {self.VALID_PERMISSION_MODES}",
            )
            logger.warning(f"[ConfigValidator] {error}")
            return error
        return None

    def _validate_timeout(self, config: ClaudeConfig) -> ValidationError | None:
        """Validate timeout range."""
        if config.timeout_seconds is None:
            return None
        if (
            config.timeout_seconds < self.MIN_TIMEOUT
            or config.timeout_seconds > self.MAX_TIMEOUT
        ):
            error = ValidationError(
                "timeout_seconds",
                f"超时时间应在{self.MIN_TIMEOUT}-{self.MAX_TIMEOUT}秒之间, 当前值: {config.timeout_seconds}",
            )
            logger.warning(f"[ConfigValidator] {error}")
            return error
        return None


# Standalone function for backward compatibility
def validate_config(config: ClaudeConfig) -> Result[ClaudeConfig, ValidationError]:
    """
    Validate Claude configuration (standalone function).

    This function is provided for backward compatibility with existing code.
    New code should use ConfigValidator class directly.
    """
    return ConfigValidator().validate(config)


__all__ = ["ConfigValidator", "validate_config"]
