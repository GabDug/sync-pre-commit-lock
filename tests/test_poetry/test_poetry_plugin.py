from unittest.mock import MagicMock, patch

import pytest
from cleo.events.console_terminate_event import ConsoleTerminateEvent
from poetry.console.application import Application
from poetry.console.commands.install import InstallCommand
from poetry.console.commands.lock import LockCommand
from poetry.console.commands.self.self_command import SelfCommand
from sync_pre_commit_lock.poetry_plugin import SyncPreCommitLockPlugin


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
def test_handle_post_command_install_add_commands(mocked_execute: MagicMock) -> None:
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
def test_handle_post_command_install_add_lock_update_commands(mocked_execute: MagicMock) -> None:
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
