"""
API客户端模块单元测试 - TDD Red Phase
"""
import pytest

class TestGLMApiClient:
    """测试GLM API调用"""
    
    def test_client_init_with_config(self):
        """客户端应该正确初始化"""
        from api_client import GLMApiClient
        client = GLMApiClient(
            api_key='test_key',
            api_base='https://open.bigmodel.cn/api/paas/v4'
        )
        assert client.api_key == 'test_key'
    
    def test_execute_task_returns_result(self):
        """执行任务应该返回结果"""
        from api_client import GLMApiClient
        client = GLMApiClient(api_key='test', api_base='test')
        # Mock测试
        result = client.execute('写一个hello.txt')
        assert 'output' in result

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
