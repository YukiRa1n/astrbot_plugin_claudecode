"""
Test Runner - Run unit tests without astrbot dependency.
"""

import json
import sys
from pathlib import Path

# Add parent directory to path
plugin_dir = Path(__file__).parent.parent
sys.path.insert(0, str(plugin_dir.parent))

# Mock astrbot module to prevent import errors
class MockAstrbot:
    class api:
        class event:
            class filter:
                @staticmethod
                def llm_tool(name):
                    def decorator(func):
                        return func
                    return decorator
            class AstrMessageEvent:
                pass
        class star:
            class Context:
                pass
            class Star:
                def __init__(self, context):
                    pass
            @staticmethod
            def register(*args, **kwargs):
                def decorator(cls):
                    return cls
                return decorator
            class StarTools:
                @staticmethod
                def get_data_dir():
                    return Path.cwd()
        @staticmethod
        def logger():
            import logging
            return logging.getLogger("test")
        class AstrBotConfig(dict):
            pass

# Install mock
sys.modules["astrbot"] = MockAstrbot
sys.modules["astrbot.api"] = MockAstrbot.api
sys.modules["astrbot.api.event"] = MockAstrbot.api.event
sys.modules["astrbot.api.star"] = MockAstrbot.api.star

# Now import the actual modules
from astrbot_plugin_claudecode.infrastructure.config.config_validator import (
    ConfigValidator,
)
from astrbot_plugin_claudecode.infrastructure.process.command_builder import (
    CommandBuilder,
)
from astrbot_plugin_claudecode.infrastructure.process.output_parser import OutputParser
from astrbot_plugin_claudecode.infrastructure.stream.chunk_parser import ChunkParser
from astrbot_plugin_claudecode.models import ChunkType, ClaudeConfig, ErrorCode


def test_config_validator():
    print("=" * 60)
    print("Testing ConfigValidator")
    print("=" * 60)

    validator = ConfigValidator()

    # Test 1: Valid config with auth token
    config = ClaudeConfig(auth_token="test-token", permission_mode="default", timeout_seconds=120)
    result = validator.validate(config)
    assert result.is_ok(), "Should pass with auth token"
    print("  [PASS] Valid config with auth token")

    # Test 2: Valid config with API key
    config = ClaudeConfig(api_key="sk-test", permission_mode="default", timeout_seconds=120)
    result = validator.validate(config)
    assert result.is_ok(), "Should pass with API key"
    print("  [PASS] Valid config with API key")

    # Test 3: Missing auth
    config = ClaudeConfig(auth_token="", api_key="", permission_mode="default", timeout_seconds=120)
    result = validator.validate(config)
    assert result.is_err(), "Should fail without auth"
    assert result.unwrap_err().field == "auth"
    print("  [PASS] Missing auth rejected")

    # Test 4: Invalid permission mode
    config = ClaudeConfig(auth_token="test", permission_mode="invalid", timeout_seconds=120)
    result = validator.validate(config)
    assert result.is_err(), "Should fail with invalid mode"
    print("  [PASS] Invalid permission mode rejected")

    # Test 5: Timeout too low
    config = ClaudeConfig(auth_token="test", permission_mode="default", timeout_seconds=5)
    result = validator.validate(config)
    assert result.is_err(), "Should fail with low timeout"
    print("  [PASS] Timeout too low rejected")

    # Test 6: Timeout too high
    config = ClaudeConfig(auth_token="test", permission_mode="default", timeout_seconds=1000)
    result = validator.validate(config)
    assert result.is_err(), "Should fail with high timeout"
    print("  [PASS] Timeout too high rejected")


def test_output_parser():
    print("")
    print("=" * 60)
    print("Testing OutputParser")
    print("=" * 60)

    parser = OutputParser()

    # Test 1: Success output
    stdout = json.dumps({"result": "Task done", "is_error": False, "total_cost_usd": 0.005, "session_id": "sess-123"})
    result = parser.parse(stdout, "", 1000.0)
    assert result.is_ok()
    exec_result = result.unwrap()
    assert exec_result.output == "Task done"
    assert exec_result.cost_usd == 0.005
    print("  [PASS] Success output parsed")

    # Test 2: Error output
    stdout = json.dumps({"result": "Permission denied", "is_error": True})
    result = parser.parse(stdout, "", 500.0)
    assert result.is_err()
    assert result.unwrap_err().code == ErrorCode.CLI_ERROR
    print("  [PASS] Error output parsed")

    # Test 3: Malformed JSON fallback
    result = parser.parse("Raw output", "", 100.0)
    assert result.is_ok()
    assert result.unwrap().output == "Raw output"
    print("  [PASS] Malformed JSON fallback works")


def test_command_builder():
    print("")
    print("=" * 60)
    print("Testing CommandBuilder")
    print("=" * 60)

    builder = CommandBuilder()
    workspace = Path("/test/workspace")

    # Test 1: Basic command
    config = ClaudeConfig(auth_token="test")
    cmd = builder.build("Hello", workspace, config, stream=False)
    assert cmd[0] == "claude"
    assert "-p" in cmd
    assert "Hello" in cmd
    assert "json" in cmd
    print("  [PASS] Basic command built")

    # Test 2: Stream command
    cmd = builder.build("Hello", workspace, config, stream=True)
    assert "stream-json" in cmd
    assert "--verbose" in cmd
    print("  [PASS] Stream command built")

    # Test 3: With allowed tools
    config = ClaudeConfig(auth_token="test", allowed_tools=["Read", "Write"])
    cmd = builder.build("Test", workspace, config)
    assert "--allowedTools" in cmd
    idx = cmd.index("--allowedTools")
    assert cmd[idx + 1] == "Read,Write"
    print("  [PASS] Allowed tools added")

    # Test 4: Bash tool restriction
    config = ClaudeConfig(auth_token="test", allowed_tools=["Bash"])
    cmd = builder.build("Test", Path("/my/workspace"), config)
    idx = cmd.index("--allowedTools")
    assert "Bash(/my/workspace/*)" in cmd[idx + 1]
    print("  [PASS] Bash tool restricted to workspace")


def test_chunk_parser():
    print("")
    print("=" * 60)
    print("Testing ChunkParser")
    print("=" * 60)

    chunk_parser = ChunkParser()

    # Test 1: Thinking chunk
    chunk = chunk_parser.parse_line(json.dumps({"type": "thinking", "content": "Analyzing..."}))
    assert chunk is not None
    assert chunk.chunk_type == ChunkType.THINKING
    assert chunk.content == "Analyzing..."
    print("  [PASS] Thinking chunk parsed")

    # Test 2: Tool use chunk
    chunk = chunk_parser.parse_line(json.dumps({"type": "tool_use", "content": "Reading file"}))
    assert chunk.chunk_type == ChunkType.TOOL_USE
    print("  [PASS] Tool use chunk parsed")

    # Test 3: Raw text
    chunk = chunk_parser.parse_line("Raw text output")
    assert chunk.chunk_type == ChunkType.STATUS
    assert chunk.content == "Raw text output"
    print("  [PASS] Raw text parsed")

    # Test 4: Empty line
    chunk = chunk_parser.parse_line("")
    assert chunk is None
    print("  [PASS] Empty line returns None")


if __name__ == "__main__":
    test_config_validator()
    test_output_parser()
    test_command_builder()
    test_chunk_parser()

    print("")
    print("=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)
