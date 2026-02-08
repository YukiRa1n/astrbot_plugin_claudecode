"""
Pytest Configuration - Fixtures and configuration for tests.
"""

import tempfile
from pathlib import Path

import pytest

from ..models import ClaudeConfig
from .fixtures.mock_process import MockProcessRunner
from .fixtures.sample_outputs import SAMPLE_OUTPUTS


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_config():
    """Create a sample ClaudeConfig for testing."""
    return ClaudeConfig(
        auth_token="test-token-123",
        api_key="",
        api_base_url="",
        model="claude-sonnet-4-20250514",
        allowed_tools=["Read", "Write", "Bash"],
        disallowed_tools=[],
        permission_mode="default",
        add_dirs=[],
        max_turns=10,
        timeout_seconds=120,
    )


@pytest.fixture
def mock_runner_success():
    """Create a mock runner that returns success."""
    return MockProcessRunner(
        stdout=SAMPLE_OUTPUTS["success"],
        stderr="",
        returncode=0,
    )


@pytest.fixture
def mock_runner_error():
    """Create a mock runner that returns error."""
    return MockProcessRunner(
        stdout=SAMPLE_OUTPUTS["error"],
        stderr="",
        returncode=0,
    )


@pytest.fixture
def mock_runner_timeout():
    """Create a mock runner that raises timeout."""
    import asyncio
    return MockProcessRunner(
        error=asyncio.TimeoutError(),
    )


@pytest.fixture
def mock_runner_not_found():
    """Create a mock runner that raises FileNotFoundError."""
    return MockProcessRunner(
        error=FileNotFoundError("claude not found"),
    )
