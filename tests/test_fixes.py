"""
Tests for P0/P1 fixes - test independent modules only.
"""

import sys
import types
import logging
import importlib.util
import asyncio
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

# Mock astrbot before any imports
if "astrbot" not in sys.modules:
    astrbot_mod = types.ModuleType("astrbot")
    api_mod = types.ModuleType("astrbot.api")
    event_mod = types.ModuleType("astrbot.api.event")
    star_mod = types.ModuleType("astrbot.api.star")
    api_mod.logger = logging.getLogger("astrbot")

    class _AstrBotConfig(dict):
        pass

    api_mod.AstrBotConfig = _AstrBotConfig

    class _Star:
        def __init__(self, context=None):
            pass

    class _Context:
        pass

    class _StarTools:
        @staticmethod
        def get_data_dir():
            import tempfile
            return Path(tempfile.gettempdir())

    def _register(*args, **kwargs):
        def decorator(cls):
            return cls
        return decorator

    class _filter:
        class llm_tool:
            def __init__(self, *args, **kwargs):
                pass
            def __call__(self, func):
                return func

    event_mod.filter = _filter
    event_mod.AstrMessageEvent = MagicMock
    star_mod.Star = _Star
    star_mod.Context = _Context
    star_mod.StarTools = _StarTools
    star_mod.register = _register
    astrbot_mod.api = api_mod
    sys.modules["astrbot"] = astrbot_mod
    sys.modules["astrbot.api"] = api_mod
    sys.modules["astrbot.api.event"] = event_mod
    sys.modules["astrbot.api.star"] = star_mod


def _load_module_from_file(module_name: str, file_path: Path):
    """Load a module directly from file path."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_plugin_root = Path(__file__).resolve().parent.parent

# Load models (independent, only depends on pydantic)
models = _load_module_from_file("claudecode_models", _plugin_root / "models.py")
ClaudeConfig = models.ClaudeConfig

# Load decorators (independent)
decorators = _load_module_from_file(
    "claudecode_decorators", _plugin_root / "utils" / "decorators.py"
)
_format_args = decorators._format_args


class TestClaudeConfigValidation:
    """Test ClaudeConfig handles None values correctly."""

    def test_none_timeout_does_not_crash_on_comparison(self):
        """None timeout_seconds should not raise TypeError when compared."""
        config = ClaudeConfig(
            auth_token="test-token",
            permission_mode="default",
            timeout_seconds=None,
        )
        # The fix ensures None is handled before comparison
        # Direct test: None should not crash when we check it
        assert config.timeout_seconds is None
        # Simulate the fixed validation logic
        if config.timeout_seconds is not None:
            _ = config.timeout_seconds < 10  # This would crash if None
        # If we get here, the fix works

    def test_none_permission_mode_handled(self):
        """None permission_mode should be handled correctly."""
        config = ClaudeConfig(
            auth_token="test-token",
            permission_mode=None,
            timeout_seconds=120,
        )
        assert config.permission_mode is None
        # Simulate the fixed validation logic
        valid_modes = ["default", "acceptEdits", "plan", "dontAsk"]
        if config.permission_mode is not None:
            assert config.permission_mode in valid_modes
        # None should pass validation

    def test_valid_config_values(self):
        """Valid config should have correct values."""
        config = ClaudeConfig(
            auth_token="test-token",
            api_key="sk-test",
            permission_mode="default",
            timeout_seconds=120,
        )
        assert config.auth_token == "test-token"
        assert config.api_key == "sk-test"
        assert config.permission_mode == "default"
        assert config.timeout_seconds == 120


class TestFormatArgs:
    """Tests for _format_args fix - should not skip first arg."""

    def test_does_not_skip_first_arg(self):
        result = _format_args(("hello", "world"), {})
        assert "hello" in result
        assert "world" in result

    def test_single_string_arg(self):
        result = _format_args(("some-task",), {})
        assert "some-task" in result

    def test_empty_args(self):
        result = _format_args((), {})
        assert result == ""

    def test_kwargs_included(self):
        result = _format_args((), {"key": "value"})
        assert "key=value" in result

    def test_long_arg_truncated(self):
        long_str = "x" * 100
        result = _format_args((long_str,), {})
        assert "..." in result

    def test_first_arg_with_class_not_skipped(self):
        """An object with __class__ as first arg should NOT be skipped."""

        class Dummy:
            def __repr__(self):
                return "Dummy()"

        dummy = Dummy()
        result = _format_args((dummy, "task"), {})
        assert "task" in result
        assert "Dummy()" in result

    def test_integer_first_arg(self):
        result = _format_args((42, "task"), {})
        assert "42" in result
        assert "task" in result

    def test_list_first_arg(self):
        result = _format_args(([1, 2, 3], "task"), {})
        assert "[1, 2, 3]" in result
        assert "task" in result


class TestVersionNumber:
    """Test that VERSION in main.py matches __init__.py."""

    def test_version_is_3_0_0(self):
        """main.py VERSION should be 3.0.0 to match __init__.py."""
        main_path = _plugin_root / "main.py"
        content = main_path.read_text(encoding="utf-8")
        assert 'VERSION = "3.0.0"' in content

    def test_version_matches_init(self):
        """main.py VERSION should match __init__.py __version__."""
        init_path = _plugin_root / "__init__.py"
        content = init_path.read_text(encoding="utf-8")
        assert '__version__ = "3.0.0"' in content


class TestClaudeMdWriteProtection:
    """Test that _write_claude_md only writes to workspace, not ~/.claude/."""

    def test_no_home_claude_write(self):
        """_write_claude_md should not write to ~/.claude/CLAUDE.md."""
        main_path = _plugin_root / "main.py"
        content = main_path.read_text(encoding="utf-8")
        assert 'Path.home() / ".claude"' not in content
        assert "~/.claude/CLAUDE.md" not in content

    def test_workspace_write_present(self):
        """_write_claude_md should write to workspace/CLAUDE.md."""
        main_path = _plugin_root / "main.py"
        content = main_path.read_text(encoding="utf-8")
        assert "self.workspace / \"CLAUDE.md\"" in content


class TestProcessRunnerTimeoutKill:
    """Test that ProcessRunner kills process on timeout."""

    def test_timeout_kills_process(self):
        """ProcessRunner.run should kill process on asyncio.TimeoutError."""
        runner_path = (
            _plugin_root
            / "infrastructure"
            / "process"
            / "process_runner.py"
        )
        content = runner_path.read_text(encoding="utf-8")
        assert "proc.kill()" in content
        assert "except asyncio.TimeoutError:" in content

    @pytest.mark.asyncio
    async def test_process_runner_kills_on_timeout_mock(self):
        """Verify process is killed when communicate() times out."""
        parent_dir = str(_plugin_root.parent)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)

        mock_proc = MagicMock()
        mock_proc.communicate = AsyncMock(
            side_effect=asyncio.TimeoutError()
        )
        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock()

        async def mock_create_subprocess_exec(*args, **kwargs):
            return mock_proc

        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=mock_create_subprocess_exec,
        ):
            from astrbot_plugin_claudecode.infrastructure.process.process_runner import (
                ProcessRunner,
            )

            runner = ProcessRunner()

            with pytest.raises(asyncio.TimeoutError):
                await runner.run(
                    cmd_args=["claude", "test"],
                    cwd=Path("."),
                    timeout=1,
                )

        mock_proc.kill.assert_called_once()
        mock_proc.wait.assert_called_once()


class TestMetadataVersion:
    """Test metadata.yaml version is in sync with plugin VERSION."""

    def test_metadata_yaml_version_is_3_0_0(self):
        """metadata.yaml should declare version 3.0.0."""
        metadata_path = _plugin_root / "metadata.yaml"
        content = metadata_path.read_text(encoding="utf-8")
        assert "version: 3.0.0" in content


class TestOwnerOnlyPermissions:
    """Test _set_owner_only_permissions helper in claude_config.py."""

    def test_function_exists(self):
        """_set_owner_only_permissions must be defined in claude_config module."""
        claude_config_path = _plugin_root / "claude_config.py"
        content = claude_config_path.read_text(encoding="utf-8")
        assert "_set_owner_only_permissions" in content
        assert "def _set_owner_only_permissions" in content

    def test_no_setfileattributesw_call(self):
        """Misleading SetFileAttributesW(0x02) call should be removed."""
        claude_config_path = _plugin_root / "claude_config.py"
        content = claude_config_path.read_text(encoding="utf-8")
        assert "SetFileAttributesW" not in content

    def test_uses_os_chmod_on_unix(self):
        """On non-Windows, _set_owner_only_permissions should call os.chmod(..., 0o600)."""
        import sys as _sys

        plat_mod = _load_module_from_file(
            "claudecode_claude_config_partial",
            _plugin_root / "claude_config.py",
        ) if False else None

        # Read source as a string check (independent of import-time deps)
        claude_config_path = _plugin_root / "claude_config.py"
        content = claude_config_path.read_text(encoding="utf-8")
        assert "os.chmod(file_path, 0o600)" in content

        # Behavioral check via mocking when on a Unix-like host
        if _sys.platform != "win32":
            chmod_calls = []

            def fake_chmod(path, mode):
                chmod_calls.append((str(path), mode))

            with patch("platform.system", return_value="Linux"), patch(
                "os.chmod", side_effect=fake_chmod
            ):
                # Re-import via direct exec to bypass relative-import requirement
                import importlib.util as _ilu

                # Build a minimal stub package so claude_config can resolve its
                # relative imports (.models, .infrastructure.config.path_resolver)
                pkg_name = "claudecode_pkg_stub"
                if pkg_name not in sys.modules:
                    pkg = types.ModuleType(pkg_name)
                    pkg.__path__ = [str(_plugin_root)]
                    sys.modules[pkg_name] = pkg

                    infra = types.ModuleType(f"{pkg_name}.infrastructure")
                    infra.__path__ = [str(_plugin_root / "infrastructure")]
                    sys.modules[f"{pkg_name}.infrastructure"] = infra

                    infra_cfg = types.ModuleType(
                        f"{pkg_name}.infrastructure.config"
                    )
                    infra_cfg.__path__ = [
                        str(_plugin_root / "infrastructure" / "config")
                    ]
                    sys.modules[f"{pkg_name}.infrastructure.config"] = infra_cfg

                    # Reuse already-loaded models module
                    sys.modules[f"{pkg_name}.models"] = models

                    pr_spec = _ilu.spec_from_file_location(
                        f"{pkg_name}.infrastructure.config.path_resolver",
                        _plugin_root
                        / "infrastructure"
                        / "config"
                        / "path_resolver.py",
                    )
                    pr_mod = _ilu.module_from_spec(pr_spec)
                    sys.modules[
                        f"{pkg_name}.infrastructure.config.path_resolver"
                    ] = pr_mod
                    pr_spec.loader.exec_module(pr_mod)

                cc_spec = _ilu.spec_from_file_location(
                    f"{pkg_name}.claude_config",
                    _plugin_root / "claude_config.py",
                )
                cc_mod = _ilu.module_from_spec(cc_spec)
                sys.modules[f"{pkg_name}.claude_config"] = cc_mod
                cc_spec.loader.exec_module(cc_mod)

                cc_mod._set_owner_only_permissions(Path("/tmp/fake-settings.json"))

            assert any(mode == 0o600 for _p, mode in chmod_calls), (
                f"os.chmod was not called with 0o600. Calls: {chmod_calls}"
            )


class TestDomainErrorsReExport:
    """Test that domain.errors re-exports from models.py."""

    def test_errors_file_is_reexport(self):
        """domain/errors.py should re-export from models.py (no duplicate defs)."""
        errors_path = _plugin_root / "domain" / "errors.py"
        content = errors_path.read_text(encoding="utf-8")
        assert "from ..models import" in content
        # No duplicate dataclass definitions
        assert "@dataclass" not in content
        assert "class ExecutionError" not in content
        assert "class ValidationError" not in content

    def test_reexported_names_are_identical(self):
        """Symbols re-exported by domain.errors must be the same objects as in models."""
        import importlib.util as _ilu

        pkg_name = "claudecode_pkg_reexport"
        if pkg_name not in sys.modules:
            pkg = types.ModuleType(pkg_name)
            pkg.__path__ = [str(_plugin_root)]
            sys.modules[pkg_name] = pkg

            sys.modules[f"{pkg_name}.models"] = models

            domain_pkg = types.ModuleType(f"{pkg_name}.domain")
            domain_pkg.__path__ = [str(_plugin_root / "domain")]
            sys.modules[f"{pkg_name}.domain"] = domain_pkg

        errors_spec = _ilu.spec_from_file_location(
            f"{pkg_name}.domain.errors",
            _plugin_root / "domain" / "errors.py",
        )
        errors_mod = _ilu.module_from_spec(errors_spec)
        sys.modules[f"{pkg_name}.domain.errors"] = errors_mod
        errors_spec.loader.exec_module(errors_mod)

        for name in [
            "DomainError",
            "ErrorCode",
            "ValidationError",
            "ExecutionError",
            "IOError",
            "DomainResult",
            "Result",
            "Ok",
            "Err",
            "ok",
            "err",
        ]:
            assert getattr(errors_mod, name) is getattr(models, name), (
                f"{name} is not the same object in domain.errors and models"
            )


class TestStreamProcessorProcCleanup:
    """Test that StreamProcessor.process kills proc on exception/cancellation."""

    def test_source_has_proc_kill_in_except(self):
        """Source should kill the subprocess from the except block."""
        sp_path = (
            _plugin_root
            / "infrastructure"
            / "stream"
            / "stream_processor.py"
        )
        content = sp_path.read_text(encoding="utf-8")
        assert "except (asyncio.CancelledError, Exception)" in content
        assert "proc.kill()" in content
        assert "await proc.wait()" in content

    @pytest.mark.asyncio
    async def test_proc_killed_on_exception(self):
        """When stdout reading raises, process should be killed and waited."""
        parent_dir = str(_plugin_root.parent)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)

        from astrbot_plugin_claudecode.infrastructure.stream.stream_processor import (
            StreamProcessor,
        )

        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stdout.readline = AsyncMock(side_effect=RuntimeError("boom"))
        mock_proc.stderr = None
        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock()

        processor = StreamProcessor()

        with pytest.raises(RuntimeError):
            await processor.process(
                proc=mock_proc, on_progress=None, start_time=0.0
            )

        mock_proc.kill.assert_called_once()
        mock_proc.wait.assert_called_once()

    @pytest.mark.asyncio
    async def test_proc_killed_on_cancellation(self):
        """When task is cancelled mid-read, process should still be cleaned up."""
        parent_dir = str(_plugin_root.parent)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)

        from astrbot_plugin_claudecode.infrastructure.stream.stream_processor import (
            StreamProcessor,
        )

        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stdout.readline = AsyncMock(side_effect=asyncio.CancelledError())
        mock_proc.stderr = None
        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock()

        processor = StreamProcessor()

        with pytest.raises(asyncio.CancelledError):
            await processor.process(
                proc=mock_proc, on_progress=None, start_time=0.0
            )

        mock_proc.kill.assert_called_once()
        mock_proc.wait.assert_called_once()


class TestCLIInstallerTimeoutKill:
    """Test that CLIInstaller kills process on timeout."""

    def test_source_has_proc_kill_on_timeout(self):
        """cli_installer.py should kill proc on asyncio.TimeoutError."""
        cli_path = (
            _plugin_root
            / "infrastructure"
            / "installer"
            / "cli_installer.py"
        )
        content = cli_path.read_text(encoding="utf-8")
        assert "except asyncio.TimeoutError:" in content
        assert "proc.kill()" in content
        assert "await proc.wait()" in content


class TestMarketplaceManagerTimeoutKill:
    """Test that MarketplaceManager kills process on timeout in all methods."""

    def _read_source(self):
        mp_path = (
            _plugin_root
            / "infrastructure"
            / "installer"
            / "marketplace_manager.py"
        )
        return mp_path.read_text(encoding="utf-8")

    def test_add_marketplace_kills_on_timeout(self):
        """add_marketplace should kill proc on timeout."""
        content = self._read_source()
        assert "proc.kill()" in content

    def test_has_marketplace_has_timeout(self):
        """has_marketplace should use asyncio.wait_for with timeout."""
        content = self._read_source()
        assert "asyncio.wait_for(proc.communicate(), timeout=" in content

    def test_get_version_has_timeout(self):
        """get_version in cli_installer should use asyncio.wait_for."""
        cli_path = (
            _plugin_root
            / "infrastructure"
            / "installer"
            / "cli_installer.py"
        )
        content = cli_path.read_text(encoding="utf-8")
        assert "asyncio.wait_for" in content

    def test_config_file_write_text_uses_utf8(self):
        """config_file.write_text should specify encoding='utf-8'."""
        content = self._read_source()
        assert 'write_text(json.dumps(config, indent=2), encoding="utf-8")' in content

    def test_all_timeout_handlers_kill_proc(self):
        """Every asyncio.TimeoutError handler should call proc.kill()."""
        content = self._read_source()
        import re
        timeout_blocks = re.findall(
            r"except asyncio\.TimeoutError:.*?(?=except |return |$)",
            content,
            re.DOTALL,
        )
        assert len(timeout_blocks) >= 4, (
            f"Expected at least 4 TimeoutError blocks, found {len(timeout_blocks)}"
        )
        for block in timeout_blocks:
            assert "proc.kill()" in block, (
                f"TimeoutError block missing proc.kill(): {block[:80]}"
            )


class TestProcessRunnerStreamTimeout:
    """Test that run_stream uses the timeout parameter."""

    def test_run_stream_uses_timeout(self):
        """run_stream should apply timeout around the readline loop."""
        runner_path = (
            _plugin_root
            / "infrastructure"
            / "process"
            / "process_runner.py"
        )
        content = runner_path.read_text(encoding="utf-8")
        assert "deadline" in content
        assert "asyncio.TimeoutError" in content
