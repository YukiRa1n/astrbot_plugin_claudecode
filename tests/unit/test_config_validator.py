"""
Test Config Validator - Unit tests for ConfigValidator.
"""


from ...infrastructure.config.config_validator import ConfigValidator
from ...types import ClaudeConfig


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

    def test_validate_missing_auth(self):
        """Test validation fails without auth."""
        config = ClaudeConfig(
            auth_token="",
            api_key="",
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

    def test_validate_all_permission_modes(self):
        """Test all valid permission modes pass."""
        valid_modes = ["default", "acceptEdits", "plan", "dontAsk"]

        for mode in valid_modes:
            config = ClaudeConfig(
                auth_token="test-token",
                permission_mode=mode,
                timeout_seconds=120,
            )
            result = self.validator.validate(config)
            assert result.is_ok(), f"Mode {mode} should be valid"

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
