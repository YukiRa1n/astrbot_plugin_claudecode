"""
Test Config Validator - Unit tests for ConfigValidator.
"""

from ...infrastructure.config.config_validator import ConfigValidator
from ...models import ClaudeConfig


class TestConfigValidator:
    """Tests for ConfigValidator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = ConfigValidator()

    def test_validate_valid_config_with_auth_token(self):
        """Test validation passes with auth token."""
        config = ClaudeConfig(
            auth_token="test-token",
            permission_mode="default",
            timeout_seconds=120,
        )

        result = self.validator.validate(config)

        assert result.is_ok()
        assert result.unwrap() == config

    def test_validate_valid_config_with_api_key(self):
        """Test validation passes with API key."""
        config = ClaudeConfig(
            api_key="sk-test-key",
            permission_mode="default",
            timeout_seconds=120,
        )

        result = self.validator.validate(config)

        assert result.is_ok()

    def test_validate_missing_auth_global_mode_allowed(self):
        """全局模式（无凭据）允许通过——依赖 claude CLI 本地登录。"""
        config = ClaudeConfig(
            auth_token="",
            api_key="",
            permission_mode="default",
            timeout_seconds=120,
        )

        result = self.validator.validate(config)

        assert result.is_ok()

    def test_validate_base_url_without_credential_rejected(self):
        """配置了 api_base_url 但无凭据应被拒绝（隔离模式需要密钥）。"""
        config = ClaudeConfig(
            auth_token="",
            api_key="",
            api_base_url="https://proxy.example.com",
            permission_mode="default",
            timeout_seconds=120,
        )

        result = self.validator.validate(config)

        assert result.is_err()
        error = result.unwrap_err()
        assert error.field == "auth"

    def test_validate_invalid_permission_mode(self):
        """Test validation fails with invalid permission mode."""
        config = ClaudeConfig(
            auth_token="test-token",
            permission_mode="invalid_mode",
            timeout_seconds=120,
        )

        result = self.validator.validate(config)

        assert result.is_err()
        error = result.unwrap_err()
        assert error.field == "permission_mode"

    def test_validate_safe_permission_modes(self):
        """Test interactive permission modes pass and dontAsk is rejected."""
        valid_modes = ["default", "acceptEdits", "plan"]

        for mode in valid_modes:
            config = ClaudeConfig(
                auth_token="test-token",
                permission_mode=mode,
                timeout_seconds=120,
            )
            result = self.validator.validate(config)
            assert result.is_ok(), f"Mode {mode} should be valid"

        unsafe = ClaudeConfig(
            auth_token="test-token",
            permission_mode="dontAsk",
            timeout_seconds=120,
        )
        assert self.validator.validate(unsafe).is_err()

    def test_validate_timeout_too_low(self):
        """Test validation fails with timeout too low."""
        config = ClaudeConfig(
            auth_token="test-token",
            permission_mode="default",
            timeout_seconds=5,  # Below minimum of 10
        )

        result = self.validator.validate(config)

        assert result.is_err()
        error = result.unwrap_err()
        assert error.field == "timeout_seconds"

    def test_validate_timeout_too_high(self):
        """Test validation fails with timeout too high."""
        config = ClaudeConfig(
            auth_token="test-token",
            permission_mode="default",
            timeout_seconds=1000,  # Above maximum of 600
        )

        result = self.validator.validate(config)

        assert result.is_err()
        error = result.unwrap_err()
        assert error.field == "timeout_seconds"

    def test_validate_timeout_at_boundaries(self):
        """Test validation passes at timeout boundaries."""
        # Minimum boundary
        config_min = ClaudeConfig(
            auth_token="test-token",
            permission_mode="default",
            timeout_seconds=10,
        )
        assert self.validator.validate(config_min).is_ok()

        # Maximum boundary
        config_max = ClaudeConfig(
            auth_token="test-token",
            permission_mode="default",
            timeout_seconds=600,
        )
        assert self.validator.validate(config_max).is_ok()
