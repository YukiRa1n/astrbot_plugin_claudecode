
import json
import logging
import os
from pathlib import Path
from typing import Any

from .models import ClaudeConfig, IOError, Result, ValidationError, err, ok
from .infrastructure.config.path_resolver import PathResolver

logger = logging.getLogger("astrbot")

class ClaudeConfigManager:
    """Claude Code 配置管理器 (支持纯净隔离)"""

    def __init__(self, config: ClaudeConfig, workspace: Path = None):
        self.config = config
        self.workspace = workspace
        self.global_resolver = PathResolver()
        self.isolated_resolver = PathResolver(workspace) if workspace else self.global_resolver
        
        # 判定是否需要隔离 (仅当核心凭据或地址被填了才开启隔离)
        self.is_isolated = any([
            config.auth_token,
            config.api_key,
            config.api_base_url
        ])


    @classmethod
    def from_plugin_config(cls, plugin_config: dict[str, Any], workspace: Path = None) -> "ClaudeConfigManager":
        """从插件配置创建管理器。"""
        def get_val(key: str):
            val = plugin_config.get(key)
            return val if val and str(val).strip() else None

        config = ClaudeConfig(
            auth_token=get_val("auth_token"),
            api_key=get_val("api_key"),
            api_base_url=get_val("api_base_url"),
            model=get_val("model"),
            allowed_tools=[t.strip() for t in plugin_config.get("allowed_tools", "").split(",") if t.strip()] or None,
            disallowed_tools=[t.strip() for t in plugin_config.get("disallowed_tools", "").split(",") if t.strip()] or None,
            permission_mode=get_val("permission_mode"),
            add_dirs=[d.strip() for d in plugin_config.get("add_dirs", "").split(",") if d.strip()] or None,
            max_turns=plugin_config.get("max_turns") if plugin_config.get("max_turns") else None,
            timeout_seconds=plugin_config.get("timeout_seconds") if plugin_config.get("timeout_seconds") else None,
        )
        return cls(config, workspace)

    def get_execution_env(self) -> dict[str, str]:
        """获取执行环境。如果没开启隔离，返回空字典（使用系统默认环境）。"""
        import sys
        env_key = "USERPROFILE" if sys.platform == "win32" else "HOME"
        
        if self.is_isolated and self.workspace:
            return {env_key: str(self.workspace)}
        return {}

    def apply_config(self) -> Result[None, IOError]:
        """应用配置。隔离模式下直接生成纯净配置，绝不参考全局底稿。"""
        if not self.is_isolated:
            logger.info("[PROCESS] Mode: Global (Using system-wide Claude config)")
            return ok(None)

        logger.info(f"[ENTRY] apply_config (Fresh Isolation) target={self.workspace}")

        try:
            # 1. 确保私有目录存在
            self.isolated_resolver.claude_dir.mkdir(parents=True, exist_ok=True)

            # 2. 从零开始构建配置 (不再读取全局 settings.json)
            settings = {"env": {}}
            env = settings["env"]

            # 3. 仅填入插件中明确指定的项
            if self.config.timeout_seconds:
                env["API_TIMEOUT_MS"] = str(self.config.timeout_seconds * 1000)
            
            # 插件运行的建议项
            env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"

            if self.config.auth_token:
                env["ANTHROPIC_AUTH_TOKEN"] = self.config.auth_token
            elif self.config.api_key:
                env["ANTHROPIC_API_KEY"] = self.config.api_key

            if self.config.api_base_url:
                env["ANTHROPIC_BASE_URL"] = self.config.api_base_url
            
            if self.config.model:
                env["ANTHROPIC_MODEL"] = self.config.model

            # 4. 写入私有文件
            self.isolated_resolver.settings_file.write_text(json.dumps(settings, indent=2), encoding="utf-8")

            # 5. 生成纯净的 .claude.json 避免首屏欢迎词
            claude_json = {"hasCompletedOnboarding": True}
            self.isolated_resolver.claude_json.write_text(json.dumps(claude_json, indent=2), encoding="utf-8")

            logger.info(f"[EXIT] apply_config success. Fresh private config: {self.isolated_resolver.settings_file}")
            return ok(None)

        except Exception as e:
            error = IOError(str(self.workspace), "write", str(e))
            logger.error(f"[ERROR] apply_config: {error}")
            return err(error)

    def get_config_summary(self) -> str:
        """获取配置摘要"""
        mode = "隔离模式 (纯净)" if self.is_isolated else "全局模式"
        return f"运行模式: {mode}"
