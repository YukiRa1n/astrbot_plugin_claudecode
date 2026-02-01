"""
沙箱验证模块 - 路径安全控制
"""
from pathlib import Path
import os

class SandboxValidator:
    """路径安全验证器"""
    
    def __init__(self, sandbox_root: str):
        self.sandbox_root = Path(sandbox_root).resolve()
    
    def is_safe(self, path: str) -> bool:
        """验证路径是否在沙箱内"""
        try:
            target = Path(path).resolve()
            return str(target).startswith(str(self.sandbox_root))
        except Exception:
            return False
