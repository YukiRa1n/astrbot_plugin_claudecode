"""
Config Validator - Validates Claude configuration.

Single responsibility: Validate configuration and return Result.
No I/O, no side effects - pure validation logic.
"""

import logging

from ...domain.errors import ValidationError
from ...models import ClaudeConfig, Result, err, ok

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

    def _error(self, field: str, message: str) -> ValidationError:
        """构造错误并记录警告日志。"""
        error = ValidationError(field, message)
        logger.warning(f"[ConfigValidator] {error}")
        return error

    def _validate_auth(self, config: ClaudeConfig) -> ValidationError | None:
        """Validate authentication configuration.

        已配置凭据则视为隔离模式并放行；未配置则依赖本地登录（全局模式）。
        仅当配置了 api_base_url 但无凭据时拒绝——隔离模式需要密钥。
        """
        if config.auth_token or config.api_key:
            return None
        if config.api_base_url:
            return self._error(
                "auth", "配置了 api_base_url 但缺少 auth_token/api_key"
            )
        return None

    def _validate_permission_mode(self, config: ClaudeConfig) -> ValidationError | None:
        """Validate permission mode."""
        if (
            config.permission_mode is not None
            and config.permission_mode not in self.VALID_PERMISSION_MODES
        ):
            return self._error(
                "permission_mode",
                f"无效的权限模式: {config.permission_mode}, 有效值: {self.VALID_PERMISSION_MODES}",
            )
        return None

    def _validate_timeout(self, config: ClaudeConfig) -> ValidationError | None:
        """Validate timeout range."""
        if config.timeout_seconds is None:
            return None
        if (
            config.timeout_seconds < self.MIN_TIMEOUT
            or config.timeout_seconds > self.MAX_TIMEOUT
        ):
            return self._error(
                "timeout_seconds",
                f"超时时间应在{self.MIN_TIMEOUT}-{self.MAX_TIMEOUT}秒之间, 当前值: {config.timeout_seconds}",
            )
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
