"""
GLM API客户端模块 - 调用Claude API
"""
import httpx
import json
from typing import Dict, Any

class GLMApiClient:
    """GLM API客户端"""
    
    def __init__(self, api_key: str, api_base: str):
        self.api_key = api_key
        self.api_base = api_base.rstrip('/')
    
    async def execute(self, task: str, working_dir: str = '.') -> Dict[str, Any]:
        """执行Claude任务"""
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': 'claude-3-5-sonnet',
            'messages': [
                {'role': 'user', 'content': f'在目录 {working_dir} 中执行: {task}'}
            ]
        }
        
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f'{self.api_base}/chat/completions',
                headers=headers,
                json=payload
            )
            return {'output': resp.json(), 'success': resp.status_code == 200}
