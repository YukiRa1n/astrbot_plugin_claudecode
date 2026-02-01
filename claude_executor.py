"""
Claude Code CLI 执行器
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .claude_config import ClaudeConfigManager

logger = logging.getLogger('astrbot')


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

        cmd_args = self._build_command_args(task)

        try:
            # 使用 subprocess_exec 避免 shell 注入
            proc = await asyncio.create_subprocess_exec(
                *cmd_args,
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
            logger.warning(f'[ClaudeExecutor] Task timeout after {timeout}s: {task[:50]}...')
            return {'success': False, 'error': 'Timeout', 'output': ''}
        except Exception as e:
            logger.error(f'[ClaudeExecutor] Execution failed: {e}')
            return {'success': False, 'error': str(e), 'output': ''}

    def _build_command_args(self, task: str) -> list:
        """构建执行命令参数列表（避免 shell 注入）"""
        cmd_args = [
            'claude',
            '-p', task,  # 直接传递，不需要转义
            '--output-format', 'json'
        ]

        # 添加配置中的安全限制
        if self.config_manager:
            cfg = self.config_manager.config

            # 允许的工具（自动为 Bash 添加 workspace 路径限制）
            if cfg.allowed_tools:
                tools = self._process_allowed_tools(cfg.allowed_tools)
                cmd_args.extend(['--allowedTools', tools])

            # 禁用的工具
            if cfg.disallowed_tools:
                tools = ','.join(cfg.disallowed_tools)
                cmd_args.extend(['--disallowedTools', tools])

            # 权限模式
            if cfg.permission_mode and cfg.permission_mode != 'default':
                cmd_args.extend(['--permission-mode', cfg.permission_mode])

            # 额外目录
            if cfg.add_dirs:
                for d in cfg.add_dirs:
                    cmd_args.extend(['--add-dir', d])

            # 最大轮数
            if cfg.max_turns:
                cmd_args.extend(['--max-turns', str(cfg.max_turns)])

        return cmd_args

    def _process_allowed_tools(self, tools: list) -> str:
        """处理允许的工具列表，自动为 Bash 添加 workspace 路径限制"""
        processed = []
        for tool in tools:
            if tool == 'Bash':
                # 自动添加 workspace 路径限制
                workspace_path = str(self.workspace).replace('\\', '/')
                processed.append(f'Bash({workspace_path}/*)')
                logger.info(f'[ClaudeExecutor] Bash restricted to: {workspace_path}/*')
            else:
                processed.append(tool)
        return ','.join(processed)

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
        except json.JSONDecodeError as e:
            logger.warning(f'[ClaudeExecutor] Failed to parse JSON output: {e}')
            # 根据 stderr 判断是否成功
            has_error = stderr and ('error' in stderr.lower() or 'failed' in stderr.lower())
            return {
                'success': bool(stdout) and not has_error,
                'output': stdout or stderr,
                'cost_usd': 0
            }
