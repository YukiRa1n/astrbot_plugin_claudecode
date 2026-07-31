"""
Test ClaudeConfigManager - isolation mode decision.
"""

from pathlib import Path

from ...claude_config import ClaudeConfigManager
from ...models import ClaudeConfig


class TestClaudeConfigManager:
    """Tests for ClaudeConfigManager isolation decisions."""

    def setup_method(self):
        self.workspace = Path("/tmp/test-workspace")

    def test_not_isolated_when_no_credentials(self):
        """无凭据时进入全局模式（依赖 claude CLI 本机登录）。"""
        config = ClaudeConfig(auth_token="", api_key="")
        mgr = ClaudeConfigManager(config, self.workspace)
        assert mgr.is_isolated is False

    def test_isolated_with_auth_token(self):
        """配置 auth_token 进入隔离模式。"""
        config = ClaudeConfig(auth_token="tok-123")
        mgr = ClaudeConfigManager(config, self.workspace)
        assert mgr.is_isolated is True

    def test_isolated_with_api_key(self):
        """配置 api_key 进入隔离模式。"""
        config = ClaudeConfig(api_key="sk-123")
        mgr = ClaudeConfigManager(config, self.workspace)
        assert mgr.is_isolated is True

    def test_base_url_alone_does_not_isolate(self):
        """仅配置 api_base_url 不应进入隔离模式（无密钥隔离必然认证失败）。"""
        config = ClaudeConfig(api_base_url="https://proxy.example.com")
        mgr = ClaudeConfigManager(config, self.workspace)
        assert mgr.is_isolated is False

    def test_execution_env_global_is_empty(self):
        """全局模式返回空环境（使用系统默认）。"""
        config = ClaudeConfig()
        mgr = ClaudeConfigManager(config, self.workspace)
        assert mgr.get_execution_env() == {}
