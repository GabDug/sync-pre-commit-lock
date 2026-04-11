import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest
from pytest_mock import MockerFixture

from sync_pre_commit_lock import Printer
from sync_pre_commit_lock.actions.install_hooks import ResolvedHookRunner, SetupPreCommitHooks
from sync_pre_commit_lock.config import HookRunner


@pytest.fixture()
def printer(mocker: MockerFixture) -> MagicMock:
    return mocker.MagicMock()


class TestResolvedHookRunner:
    def test_name(self) -> None:
        assert ResolvedHookRunner(HookRunner.PRE_COMMIT).name == "pre-commit"
        assert ResolvedHookRunner(HookRunner.PREK).name == "prek"

    @pytest.mark.parametrize(
        ("runner", "prefix", "arg", "expected"),
        [
            (HookRunner.PRE_COMMIT, (), "install", ["pre-commit", "install"]),
            (HookRunner.PRE_COMMIT, (), "--version", ["pre-commit", "--version"]),
            (HookRunner.PREK, (), "install", ["prek", "install"]),
            (HookRunner.PREK, (), "--version", ["prek", "--version"]),
            (HookRunner.PRE_COMMIT, ("pdm", "run"), "install", ["pdm", "run", "pre-commit", "install"]),
            (HookRunner.PRE_COMMIT, ("pdm", "run"), "--version", ["pdm", "run", "pre-commit", "--version"]),
            (HookRunner.PREK, ("poetry", "run"), "install", ["poetry", "run", "prek", "install"]),
            (HookRunner.PREK, ("poetry", "run"), "--version", ["poetry", "run", "prek", "--version"]),
        ],
    )
    def test_execute(self, runner: HookRunner, prefix: tuple, arg: str, expected: list) -> None:
        resolved = ResolvedHookRunner(runner, prefix)
        assert list(resolved.execute(arg)) == expected

    @pytest.mark.parametrize(
        ("runner", "prefix", "subprocess_return", "expected"),
        [
            (HookRunner.PRE_COMMIT, (), b"pre-commit 2.9.3", True),
            (HookRunner.PRE_COMMIT, (), FileNotFoundError(), False),
            (HookRunner.PREK, (), b"prek 0.5.0", True),
            (HookRunner.PREK, (), FileNotFoundError(), False),
            (HookRunner.PREK, ("poetry", "run"), b"prek 0.5.0", True),
        ],
    )
    def test_is_installed(
        self, mocker: MockerFixture, runner: HookRunner, prefix: tuple, subprocess_return, expected: bool
    ) -> None:
        if isinstance(subprocess_return, Exception):
            mocker.patch("subprocess.check_output", side_effect=subprocess_return)
        else:
            mocker.patch("subprocess.check_output", return_value=subprocess_return)
        resolved = ResolvedHookRunner(runner, prefix)
        assert resolved.is_installed() is expected

    @pytest.mark.parametrize(
        ("hook_runner", "subprocess_return", "expected_runner"),
        [
            (HookRunner.PRE_COMMIT, b"pre-commit 3.0.0", HookRunner.PRE_COMMIT),
            (HookRunner.PRE_COMMIT, FileNotFoundError(), None),
            (HookRunner.PREK, b"prek 0.5.0", HookRunner.PREK),
        ],
    )
    def test_resolve_explicit(
        self, printer, mocker: MockerFixture, hook_runner: HookRunner, subprocess_return, expected_runner
    ) -> None:
        if isinstance(subprocess_return, Exception):
            mocker.patch("subprocess.check_output", side_effect=subprocess_return)
        else:
            mocker.patch("subprocess.check_output", return_value=subprocess_return)
        resolved = ResolvedHookRunner.resolve(hook_runner, printer=printer)
        if expected_runner is None:
            assert resolved is None
        else:
            assert resolved is not None
            assert resolved.runner is expected_runner

    @pytest.mark.parametrize(
        ("available_runners", "expected_runner"),
        [
            ({"prek": b"prek 0.5.0", "pre-commit": b"pre-commit 3.0.0"}, HookRunner.PREK),
            ({"pre-commit": b"pre-commit 3.0.0"}, HookRunner.PRE_COMMIT),
            ({}, None),
        ],
    )
    def test_resolve_auto(self, printer, mocker: MockerFixture, available_runners: dict, expected_runner) -> None:
        def mock_check_output(command, **kwargs):
            for name, output in available_runners.items():
                if command == [name, "--version"]:
                    return output
            raise FileNotFoundError

        mocker.patch("subprocess.check_output", side_effect=mock_check_output)
        resolved = ResolvedHookRunner.resolve(HookRunner.AUTO, printer=printer)
        if expected_runner is None:
            assert resolved is None
        else:
            assert resolved is not None
            assert resolved.runner is expected_runner

    def test_resolve_auto_with_prefix(self, printer, mocker: MockerFixture) -> None:
        def mock_check_output(command, **kwargs):
            if command == ["pdm", "run", "prek", "--version"]:
                return b"prek 0.5.0"
            raise FileNotFoundError

        mocker.patch("subprocess.check_output", side_effect=mock_check_output)
        resolved = ResolvedHookRunner.resolve(HookRunner.AUTO, command_prefix=("pdm", "run"), printer=printer)
        assert resolved is not None
        assert resolved.runner is HookRunner.PREK
        assert list(resolved.execute("install")) == ["pdm", "run", "prek", "install"]


class TestSetupPreCommitHooks:
    @pytest.fixture()
    def mock_path_exists(self, mocker: MockerFixture) -> MagicMock:
        return mocker.patch.object(Path, "exists", autospec=True)

    def test_execute_no_runner(self, printer: Printer, mocker: MockerFixture):
        mocker.patch.object(ResolvedHookRunner, "resolve", return_value=None)
        setup = SetupPreCommitHooks(printer, dry_run=False)
        setup.execute()
        assert printer.debug.call_count == 1
        assert printer.debug.call_args == call(
            "No hook runner (pre-commit or prek) is installed (or detected). Skipping."
        )

    def test_execute_not_in_git_repo(self, printer: MagicMock, mocker: MockerFixture) -> None:
        mocker.patch.object(ResolvedHookRunner, "resolve", return_value=ResolvedHookRunner(HookRunner.PRE_COMMIT))
        mocker.patch(
            "subprocess.check_output", side_effect=subprocess.CalledProcessError(1, "git", b"error", b"output")
        )
        mocker.patch("subprocess.check_call", return_value=0)

        setup = SetupPreCommitHooks(printer, dry_run=False)
        setup.execute()
        assert printer.debug.call_count == 3
        assert printer.debug.call_args == call("Not in a git repository - can't install hooks. Skipping.")

    def test_execute_hooks_already_installed(self, printer, mock_path_exists, mocker) -> None:
        mocker.patch.object(ResolvedHookRunner, "resolve", return_value=ResolvedHookRunner(HookRunner.PRE_COMMIT))
        mocker.patch("subprocess.check_output", return_value=b"git_path")
        mock_path_exists.return_value = True
        setup = SetupPreCommitHooks(printer, dry_run=False)
        setup.execute()
        assert printer.debug.call_count == 1
        assert printer.debug.call_args == call("pre-commit hooks already installed. Skipping.")

    def test_execute_dry_run(self, printer, mock_path_exists, mocker) -> None:
        mocker.patch.object(ResolvedHookRunner, "resolve", return_value=ResolvedHookRunner(HookRunner.PRE_COMMIT))
        mocker.patch("subprocess.check_output", return_value=b"git_path")
        mock_path_exists.return_value = False
        setup = SetupPreCommitHooks(printer, dry_run=True)
        setup.execute()
        assert printer.debug.call_count == 1
        assert printer.debug.call_args == call("Dry run, skipping pre-commit hook installation.")

    def test_execute_install_hooks(self, printer, mock_path_exists, mocker) -> None:
        mocker.patch.object(ResolvedHookRunner, "resolve", return_value=ResolvedHookRunner(HookRunner.PRE_COMMIT))
        mocker.patch("subprocess.check_output", return_value=b"git_path")
        mock_path_exists.return_value = False
        mocker.patch("subprocess.check_call", return_value=0)
        setup = SetupPreCommitHooks(printer, dry_run=False)
        setup.execute()
        assert printer.info.call_count == 2
        printer.info.assert_has_calls(
            [call("Installing pre-commit hooks..."), call("pre-commit hooks successfully installed!")]
        )

    @pytest.mark.parametrize("hook_runner", [HookRunner.PRE_COMMIT, HookRunner.PREK])
    def test_install_hooks_success(self, printer, mocker, hook_runner: HookRunner) -> None:
        mocked_check_call = mocker.patch("subprocess.check_call", return_value=0)
        setup = SetupPreCommitHooks(printer, dry_run=False)
        resolved = ResolvedHookRunner(hook_runner)
        setup._install_hooks(resolved)
        name = hook_runner.value
        assert printer.info.call_count == 2
        printer.info.assert_has_calls(
            [call(f"Installing {name} hooks..."), call(f"{name} hooks successfully installed!")]
        )
        mocked_check_call.assert_called_once()

    @pytest.mark.parametrize("hook_runner", [HookRunner.PRE_COMMIT, HookRunner.PREK])
    def test_install_hooks_error(self, printer, mocker, hook_runner: HookRunner) -> None:
        mocker.patch("subprocess.check_call", side_effect=subprocess.CalledProcessError(1, "cmd"))
        setup = SetupPreCommitHooks(printer, dry_run=False)
        resolved = ResolvedHookRunner(hook_runner)
        setup._install_hooks(resolved)
        name = hook_runner.value
        assert printer.info.call_count == 1
        assert printer.error.call_count == 2
        printer.info.assert_has_calls([call(f"Installing {name} hooks...")])
        printer.error.assert_has_calls(
            [
                call(f"Failed to install {name} hooks due to an unexpected error"),
                call("Command 'cmd' returned non-zero exit status 1."),
            ]
        )

    @pytest.mark.parametrize("hook_runner", [HookRunner.PRE_COMMIT, HookRunner.PREK])
    def test_install_hooks_non_zero_return_code(self, printer, mocker, hook_runner: HookRunner) -> None:
        mocker.patch("subprocess.check_call", return_value=1)
        setup = SetupPreCommitHooks(printer, dry_run=False)
        resolved = ResolvedHookRunner(hook_runner)
        setup._install_hooks(resolved)
        name = hook_runner.value
        assert printer.info.call_count == 1
        assert printer.error.call_count == 1
        printer.info.assert_has_calls([call(f"Installing {name} hooks...")])
        printer.error.assert_has_calls([call(f"Failed to install {name} hooks")])


class TestSetupPreCommitHooksAutoDetect:
    @pytest.mark.parametrize(
        ("available_runners", "expected_runner"),
        [
            ({"prek": b"prek 0.5.0"}, HookRunner.PREK),
            ({"pre-commit": b"pre-commit 3.0.0"}, HookRunner.PRE_COMMIT),
        ],
        ids=["prek", "pre-commit-fallback"],
    )
    def test_auto_detect_execute_installs(
        self, printer, mocker, available_runners: dict, expected_runner: HookRunner
    ) -> None:
        """Full execute flow with auto-detect resolving to the first available runner."""

        def mock_check_output(command, **kwargs):
            for name, output in available_runners.items():
                if command == [name, "--version"]:
                    return output
            if command == ["git", "rev-parse", "--show-toplevel"]:
                return b"/fake/repo"
            raise FileNotFoundError

        mocker.patch("subprocess.check_output", side_effect=mock_check_output)
        mocker.patch.object(Path, "exists", return_value=False)
        mocked_check_call = mocker.patch("subprocess.check_call", return_value=0)

        setup = SetupPreCommitHooks(printer, dry_run=False, hook_runner=HookRunner.AUTO)
        setup.execute()

        name = expected_runner.value
        mocked_check_call.assert_called_once_with(
            [name, "install"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        printer.info.assert_has_calls(
            [call(f"Installing {name} hooks..."), call(f"{name} hooks successfully installed!")]
        )

    def test_auto_detect_execute_none_available(self, printer, mocker) -> None:
        """Full execute flow when no runner is available."""
        mocker.patch("subprocess.check_output", side_effect=FileNotFoundError())

        setup = SetupPreCommitHooks(printer, dry_run=False, hook_runner=HookRunner.AUTO)
        setup.execute()

        printer.debug.assert_called_once_with(
            "No hook runner (pre-commit or prek) is installed (or detected). Skipping."
        )
