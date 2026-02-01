"""
Claude Code CLI 执行器
"""
import asyncio
import json
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .claude_config import ClaudeConfigManager


class ClaudeExecutor:
    """Claude Code CLI 无头模式执行器"""

    def __init__(self, workspace: Path, config_manager: 'ClaudeConfigManager' = None):
        self.workspace = workspace
        self.config_manager = config_manager
        self.workspace.mkdir(parents=True, exist_ok=True)

    async def execute(self, task: str, timeout: int = None) -> dict:
        """执行Claude Code任务"""
        # 使用配置中的超时或默认值
        if timeout is None:
            if self.config_manager:
                timeout = self.config_manager.config.timeout_seconds
            else:
                timeout = 120

        cmd = self._build_command(task)

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace)
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout
            )

            output = stdout.decode('utf-8', errors='ignore')
            return self._parse_output(output, stderr.decode())

        except asyncio.TimeoutError:
            return {'success': False, 'error': 'Timeout', 'output': ''}
        except Exception as e:
            return {'success': False, 'error': str(e), 'output': ''}

    def _build_command(self, task: str) -> str:
        """构建执行命令"""
        # 转义双引号
        safe_task = task.replace('"', '\\"')

        cmd_parts = [
            'claude',
            '-p', f'"{safe_task}"',
            '--output-format', 'json'
        ]

        # 添加配置中的工具限制
        if self.config_manager:
            cfg = self.config_manager.config

            # 允许的工具
            if cfg.allowed_tools:
                tools = ','.join(cfg.allowed_tools)
                cmd_parts.extend(['--allowedTools', tools])

            # 禁用的工具
            if cfg.disallowed_tools:
                tools = ','.join(cfg.disallowed_tools)
                cmd_parts.extend(['--disallowedTools', tools])

            # 最大轮数
            if cfg.max_turns:
                cmd_parts.extend(['--max-turns', str(cfg.max_turns)])

        return ' '.join(cmd_parts)

    def _parse_output(self, stdout: str, stderr: str) -> dict:
        """解析输出"""
        try:
            data = json.loads(stdout)
            return {
                'success': not data.get('is_error', False),
                'output': data.get('result', ''),
                'cost_usd': data.get('total_cost_usd', 0),
                'session_id': data.get('session_id', '')
            }
        except json.JSONDecodeError:
            return {
                'success': bool(stdout),
                'output': stdout or stderr,
                'cost_usd': 0
            }
