"""
沙箱模块单元测试 - TDD Red Phase
"""
import pytest
from pathlib import Path

# 预期的沙箱验证器接口
class TestSandboxValidator:
    """测试路径安全验证"""
    
    def test_valid_path_in_sandbox(self):
        """沙箱内路径应该通过验证"""
        from sandbox import SandboxValidator
        validator = SandboxValidator('/workspace')
        assert validator.is_safe('/workspace/test.txt') == True
    
    def test_path_traversal_blocked(self):
        """路径穿越攻击应该被拦截"""
        from sandbox import SandboxValidator
        validator = SandboxValidator('/workspace')
        assert validator.is_safe('/workspace/../etc/passwd') == False
    
    def test_absolute_path_outside_blocked(self):
        """沙箱外绝对路径应该被拦截"""
        from sandbox import SandboxValidator
        validator = SandboxValidator('/workspace')
        assert validator.is_safe('/etc/passwd') == False

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
