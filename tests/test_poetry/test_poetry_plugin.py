import re
from unittest.mock import MagicMock, patch

import pytest

poetry_module = pytest.importorskip("poetry")
# ruff: noqa: E402
from cleo.events.console_terminate_event import ConsoleTerminateEvent
from poetry.console.application import Application
from poetry.console.commands.install import InstallCommand
from poetry.console.commands.lock import LockCommand
from poetry.console.commands.self.self_command import SelfCommand

from sync_pre_commit_lock.poetry_plugin import SyncPreCommitLockPlugin, SyncPreCommitPoetryCommand
from sync_pre_commit_lock.pre_commit_config import PreCommitHook, PreCommitRepo


def test_activate() -> None:
    application = MagicMock()
    plugin = SyncPreCommitLockPlugin()

    plugin.activate(application)

    application.event_dispatcher.add_listener.assert_called_once()


def test_handle_post_command_exit_code_not_zero() -> None:
    event = MagicMock(spec=ConsoleTerminateEvent, exit_code=1)
    event_name = "event_name"
    dispatcher = MagicMock()

    plugin = SyncPreCommitLockPlugin()

    plugin._handle_post_command(event, event_name, dispatcher)

    event.io.write_line.assert_not_called()


@patch("sync_pre_commit_lock.poetry_plugin.PoetrySetupPreCommitHooks.execute")
@patch("sync_pre_commit_lock.config.toml.load", return_value={"tool": {"sync-pre-commit-lock": {}}})
def test_handle_post_command_install_add_commands(mocked_execute: MagicMock, mock_load: MagicMock) -> None:
    event = MagicMock(
        spec=ConsoleTerminateEvent,
        exit_code=0,
        command=MagicMock(spec=InstallCommand, option=MagicMock(return_value=True)),
    )
    event_name = "event_name"
    dispatcher = MagicMock()

    plugin = SyncPreCommitLockPlugin()
    plugin.application = MagicMock(spec=Application, instance=True)
    plugin._handle_post_command(event, event_name, dispatcher)

    mocked_execute.assert_called_once()


def test_handle_post_command_self_command() -> None:
    event = MagicMock(spec=ConsoleTerminateEvent, exit_code=0, command=MagicMock(spec=SelfCommand))
    event_name = "event_name"
    dispatcher = MagicMock()

    plugin = SyncPreCommitLockPlugin()

    plugin._handle_post_command(event, event_name, dispatcher)

    event.io.write_line.assert_called_once()


@patch("sync_pre_commit_lock.poetry_plugin.SyncPreCommitHooksVersion.execute")
@patch("sync_pre_commit_lock.config.toml.load", return_value={"tool": {"sync-pre-commit-lock": {}}})
def test_handle_post_command_install_add_lock_update_commands(mocked_execute: MagicMock, mock_load: MagicMock) -> None:
    event = MagicMock(
        spec=ConsoleTerminateEvent,
        exit_code=0,
        command=MagicMock(spec=LockCommand, option=MagicMock(return_value=True)),
    )
    event_name = "event_name"
    dispatcher = MagicMock()

    plugin = SyncPreCommitLockPlugin()
    plugin.application = MagicMock()
    plugin.application.poetry.locker.locked_repository.return_value.packages = [MagicMock()]

    plugin._handle_post_command(event, event_name, dispatcher)

    mocked_execute.assert_called_once()


def test_handle_post_command_application_none() -> None:
    event = MagicMock(
        spec=ConsoleTerminateEvent,
        exit_code=0,
        command=MagicMock(spec=LockCommand, option=MagicMock(return_value=True)),
    )
    event_name = "event_name"
    dispatcher = MagicMock()

    plugin = SyncPreCommitLockPlugin()
    # As if the plugin was not activated
    plugin.application = None

    try:
        plugin._handle_post_command(event, event_name, dispatcher)
    except RuntimeError:
        assert True
    else:
        pytest.fail("RuntimeError not raised")


def test_poetry_printer_list_success(capsys: pytest.CaptureFixture[str]) -> None:
    from cleo.io.inputs.input import Input
    from cleo.io.io import IO
    from cleo.io.outputs.output import Output

    from sync_pre_commit_lock.poetry_plugin import PoetryPrinter

    output = Output()

    def _write(message: str, new_line: bool = False):
        print(message)  # noqa: T201

    output._write = _write
    printer = PoetryPrinter(IO(input=Input(), output=output, error_output=output))

    printer.list_updated_packages(
        {
            "package": (
                PreCommitRepo("https://repo1.local/test", "rev1", [PreCommitHook("hook")]),
                PreCommitRepo("https://repo1.local/test", "rev2", [PreCommitHook("hook")]),
            )
        }
    )
    captured = capsys.readouterr()
    # Remove all <..> tags, as we don't have the real parser
    out = re.sub(r"<[^>]*>", "", captured.out)

    assert "[sync-pre-commit-lock]  • https://repo1.local/test   rev1 -> rev2" in out


def test_poetry_printer_list_success_additional_dependency(capsys: pytest.CaptureFixture[str]) -> None:
    from cleo.io.inputs.input import Input
    from cleo.io.io import IO
    from cleo.io.outputs.output import Output

    from sync_pre_commit_lock.poetry_plugin import PoetryPrinter

    output = Output()

    def _write(message: str, new_line: bool = False):
        print(message)  # noqa: T201

    output._write = _write
    printer = PoetryPrinter(IO(input=Input(), output=output, error_output=output))

    printer.list_updated_packages(
        {
            "package": (
                PreCommitRepo("https://repo1.local/test", "rev1", [PreCommitHook("hook", ["dep"])]),
                PreCommitRepo("https://repo1.local/test", "rev1", [PreCommitHook("hook", ["dep==0.1.2"])]),
            )
        }
    )
    captured = capsys.readouterr()
    # Remove all <..> tags, as we don't have the real parser
    out = re.sub(r"<[^>]*>", "", captured.out)

    assert "[sync-pre-commit-lock]  • https://repo1.local/test" in out
    assert "[sync-pre-commit-lock]    └ hook" in out
    assert "[sync-pre-commit-lock]      └ dep                    * -> 0.1.2" in out


def test_poetry_printer_list_success_with_multiple_hooks_and_additional_dependency(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from cleo.io.inputs.input import Input
    from cleo.io.io import IO
    from cleo.io.outputs.output import Output

    from sync_pre_commit_lock.poetry_plugin import PoetryPrinter

    output = Output()

    def _write(message: str, new_line: bool = False):
        print(message)  # noqa: T201

    output._write = _write
    printer = PoetryPrinter(IO(input=Input(), output=output, error_output=output))

    printer.list_updated_packages(
        {
            "package": (
                PreCommitRepo(
                    repo="https://repo1.local/test",
                    rev="rev1",
                    hooks=[
                        PreCommitHook("1st-hook", ["dep==0.1.2", "other==0.42"]),
                        PreCommitHook("2nd-hook", ["dep", "other>=0.42"]),
                    ],
                ),
                PreCommitRepo(
                    repo="https://repo1.local/test",
                    rev="rev2",
                    hooks=[
                        PreCommitHook("1st-hook", ["dep==0.1.2", "other==3.4.5"]),
                        PreCommitHook("2st-hook", ["dep==0.1.2", "other==3.4.5"]),
                    ],
                ),
            )
        }
    )
    captured = capsys.readouterr()
    # Remove all <..> tags, as we don't have the real parser
    out = re.sub(r"<[^>]*>", "", captured.out)

    assert "[sync-pre-commit-lock]  • https://repo1.local/test   rev1   -> rev2" in out
    assert "[sync-pre-commit-lock]    ├ 1st-hook" in out
    assert "[sync-pre-commit-lock]    │ └ other                  0.42   -> 3.4.5" in out
    assert "[sync-pre-commit-lock]    └ 2nd-hook" in out
    assert "[sync-pre-commit-lock]      ├ dep                    *      -> 0.1.2" in out
    assert "[sync-pre-commit-lock]      └ other                  >=0.42 -> 3.4.5" in out


def test_poetry_printer_list_success_renamed_repository(capsys: pytest.CaptureFixture[str]) -> None:
    from cleo.io.inputs.input import Input
    from cleo.io.io import IO
    from cleo.io.outputs.output import Output

    from sync_pre_commit_lock.poetry_plugin import PoetryPrinter

    output = Output()

    def _write(message: str, new_line: bool = False):
        print(message)  # noqa: T201

    output._write = _write
    printer = PoetryPrinter(IO(input=Input(), output=output, error_output=output))

    printer.list_updated_packages(
        {
            "package": (
                PreCommitRepo("https://old.repo.local/test", "rev1", [PreCommitHook("hook")]),
                PreCommitRepo("https://new.repo.local/test", "rev2", [PreCommitHook("hook")]),
            ),
        }
    )
    captured = capsys.readouterr()
    # Remove all <..> tags, as we don't have the real parser
    out = re.sub(r"<[^>]*>", "", captured.out)

    assert "[sync-pre-commit-lock]  • https://{old -> new}.repo.local/test   rev1 -> rev2" in out


def test_direct_command_invocation():
    with pytest.raises(RuntimeError, match="self.application is None"):
        SyncPreCommitPoetryCommand().handle()
