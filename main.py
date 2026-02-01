"""
AstrBot Claude Code 插件
将Claude Code作为LLM函数工具
"""
from pathlib import Path
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api import AstrBotConfig

from .sandbox import SandboxValidator

# 动态获取插件目录
PLUGIN_DIR = Path(__file__).parent
WORKSPACE_DIR = PLUGIN_DIR / 'workspace'

@register(
    "astrbot_plugin_claudecode",
    "Claude",
    "将Claude Code作为LLM函数工具",
    "1.0.0"
)
class ClaudeCodePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.plugin_dir = PLUGIN_DIR
        
        # 使用配置或默认workspace
        workspace_name = config.get('workspace_name', 'workspace')
        self.workspace = self.plugin_dir / workspace_name
        self.workspace.mkdir(parents=True, exist_ok=True)
        
        self.sandbox = SandboxValidator(str(self.workspace))
        logger.info(f'[ClaudeCode] Plugin loaded, workspace: {self.workspace}')

    @filter.llm_tool(name="claude_exec")
    async def claude_exec(self, event: AstrMessageEvent, task: str) -> str:
        """【Claude Code执行工具】在安全沙箱中执行文件操作任务。
        
        可以创建、读取、修改文件。所有操作限制在workspace目录内。
        
        Args:
            task(string): Required. 要执行的任务描述，如"创建hello.txt写入Hello World"
        
        Returns:
            string: 执行结果
        """
        logger.info(f'[ClaudeCode] Received task: {task}')
        
        try:
            result = await self._execute_task(task)
            return result
        except Exception as e:
            logger.error(f'[ClaudeCode] Error: {e}')
            return f'执行失败: {str(e)}'

    async def _execute_task(self, task: str) -> str:
        """执行具体任务"""
        task_lower = task.lower()
        
        if '创建' in task_lower or '写入' in task_lower or 'write' in task_lower:
            return await self._handle_write(task)
        elif '读取' in task_lower or 'read' in task_lower:
            return await self._handle_read(task)
        elif '列出' in task_lower or 'list' in task_lower:
            return await self._handle_list()
        else:
            return '不支持的任务类型。支持: 创建/写入文件, 读取文件, 列出文件'

    async def _handle_write(self, task: str) -> str:
        """处理写入任务"""
        import re
        
        # 提取文件名（只匹配ASCII字符）
        match = re.search(r'([a-zA-Z0-9_]+\.[a-zA-Z0-9]+)', task)
        if not match:
            return '请指定文件名，如: 创建test.txt'
        
        filename = match.group(1)
        filepath = self.workspace / filename
        
        # 安全检查
        if not self.sandbox.is_safe(str(filepath)):
            return '安全错误: 路径不在沙箱内'
        
        # 提取内容
        content = 'Hello from Claude Code!'
        if '写入' in task:
            parts = task.split('写入')
            if len(parts) > 1:
                content = parts[1].strip()
        
        filepath.write_text(content, encoding='utf-8')
        logger.info(f'[ClaudeCode] Created file: {filepath}')
        return f'文件已创建: {filepath}'

    async def _handle_read(self, task: str) -> str:
        """处理读取任务"""
        import re
        
        match = re.search(r'([a-zA-Z0-9_]+\.[a-zA-Z0-9]+)', task)
        if not match:
            return '请指定文件名'
        
        filename = match.group(1)
        filepath = self.workspace / filename
        
        if not self.sandbox.is_safe(str(filepath)):
            return '安全错误: 路径不在沙箱内'
        
        if not filepath.exists():
            return f'文件不存在: {filename}'
        
        content = filepath.read_text(encoding='utf-8')
        return f'文件内容:\n{content}'

    async def _handle_list(self) -> str:
        """列出workspace中的文件"""
        files = list(self.workspace.iterdir())
        if not files:
            return 'workspace为空'
        names = [f.name for f in files if f.is_file()]
        return 'File list: ' + ', '.join(names)
