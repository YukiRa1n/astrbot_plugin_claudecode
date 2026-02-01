"""
Claude Code 配置管理器
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ClaudeConfig:
    """Claude Code 配置数据类"""
    auth_token: str = ''
    api_key: str = ''
    api_base_url: str = ''
    allowed_tools: list = None
    disallowed_tools: list = None
    max_turns: int = 10
    timeout_seconds: int = 300

    def __post_init__(self):
        if self.allowed_tools is None:
            self.allowed_tools = []
        if self.disallowed_tools is None:
            self.disallowed_tools = []


class ClaudeConfigManager:
    """Claude Code 配置管理器"""

    CLAUDE_DIR = Path.home() / '.claude'
    SETTINGS_FILE = CLAUDE_DIR / 'settings.json'
    CLAUDE_JSON = Path.home() / '.claude.json'

    def __init__(self, config: ClaudeConfig):
        self.config = config

    @classmethod
    def from_plugin_config(cls, plugin_config: Dict[str, Any]) -> 'ClaudeConfigManager':
        """从插件配置创建管理器"""
        allowed = plugin_config.get('allowed_tools', '')
        disallowed = plugin_config.get('disallowed_tools', '')

        config = ClaudeConfig(
            auth_token=plugin_config.get('auth_token', ''),
            api_key=plugin_config.get('api_key', ''),
            api_base_url=plugin_config.get('api_base_url', ''),
            allowed_tools=[t.strip() for t in allowed.split(',') if t.strip()],
            disallowed_tools=[t.strip() for t in disallowed.split(',') if t.strip()],
            max_turns=plugin_config.get('max_turns', 10),
            timeout_seconds=plugin_config.get('timeout_seconds', 300)
        )
        return cls(config)

    def get_credential(self) -> tuple:
        """获取认证信息，返回 (type, value)"""
        if self.config.auth_token:
            return ('ANTHROPIC_AUTH_TOKEN', self.config.auth_token)
        if self.config.api_key:
            return ('ANTHROPIC_API_KEY', self.config.api_key)
        return (None, None)

    def build_settings(self) -> Dict[str, Any]:
        """构建 settings.json 内容"""
        env = {
            'API_TIMEOUT_MS': str(self.config.timeout_seconds * 1000),
            'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1'
        }

        # 设置认证
        cred_type, cred_value = self.get_credential()
        if cred_type and cred_value:
            env[cred_type] = cred_value

        # 设置 Base URL
        if self.config.api_base_url:
            env['ANTHROPIC_BASE_URL'] = self.config.api_base_url

        return {'env': env}

    def apply_config(self) -> bool:
        """应用配置到 Claude Code"""
        try:
            self.CLAUDE_DIR.mkdir(parents=True, exist_ok=True)

            settings = self.build_settings()
            self.SETTINGS_FILE.write_text(
                json.dumps(settings, indent=2),
                encoding='utf-8'
            )

            claude_json = {'hasCompletedOnboarding': True}
            self.CLAUDE_JSON.write_text(
                json.dumps(claude_json, indent=2),
                encoding='utf-8'
            )
            return True
        except Exception:
            return False

    def get_config_summary(self) -> str:
        """获取配置摘要"""
        cred_type, cred_value = self.get_credential()
        has_cred = bool(cred_value)
        cred_name = 'Auth Token' if cred_type == 'ANTHROPIC_AUTH_TOKEN' else 'API Key'
        base_url = self.config.api_base_url or '官方'
        return f"{cred_name}: {'已配置' if has_cred else '未配置'}, Base URL: {base_url}"
