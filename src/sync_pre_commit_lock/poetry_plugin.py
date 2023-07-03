from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from cleo.events.console_events import TERMINATE
from cleo.events.console_terminate_event import ConsoleTerminateEvent
from cleo.io.outputs.output import Verbosity
from poetry.console.commands.add import AddCommand
from poetry.console.commands.install import InstallCommand
from poetry.console.commands.lock import LockCommand
from poetry.console.commands.self.self_command import SelfCommand
from poetry.console.commands.update import UpdateCommand
from poetry.plugins.application_plugin import ApplicationPlugin

from sync_pre_commit_lock import Printer
from sync_pre_commit_lock.actions.install_hooks import SetupPreCommitHooks
from sync_pre_commit_lock.actions.sync_hooks import GenericLockedPackage, SyncPreCommitHooksVersion
from sync_pre_commit_lock.config import load_config

if TYPE_CHECKING:
    from collections.abc import Sequence

    from cleo.events.event import Event
    from cleo.events.event_dispatcher import EventDispatcher
    from cleo.io.io import IO
    from poetry.console.application import Application


class PoetryPrinter(Printer):
    def __init__(self, io: IO) -> None:
        self.io = io
        self.plugin_prefix = "[sync-pre-commit-lock]"

    def debug(self, msg: str) -> None:
        self.io.write_line(f"<info>{self.plugin_prefix} {msg}</info>", verbosity=Verbosity.NORMAL)

    def info(self, msg: str) -> None:
        self.io.write_line(f"<info>{self.plugin_prefix} {msg}</info>", verbosity=Verbosity.NORMAL)

    def warning(self, msg: str) -> None:
        return self.io.write_line(f"<warning>{self.plugin_prefix} {msg}</warning>", verbosity=Verbosity.NORMAL)

    def error(self, msg: str) -> None:
        return self.io.write_error_line(f"<error>{self.plugin_prefix} {msg}</error>", verbosity=Verbosity.NORMAL)


class PoetrySetupPreCommitHooks(SetupPreCommitHooks):
    install_pre_commit_hooks_command: ClassVar[Sequence[str | bytes]] = ["poetry", "run", "pre-commit", "install"]
    check_pre_commit_version_command: ClassVar[Sequence[str | bytes]] = ["poetry", "run", "pre-commit", "--version"]


class SyncPreCommitLockPlugin(ApplicationPlugin):
    application: Application | None

    def activate(self, application: Application) -> None:
        assert application.event_dispatcher is not None
        application.event_dispatcher.add_listener(TERMINATE, self._handle_post_command)

        self.application = application

    def _handle_post_command(
        self, event: ConsoleTerminateEvent | Event, event_name: str, dispatcher: EventDispatcher
    ) -> None:
        assert isinstance(event, ConsoleTerminateEvent)
        if event.exit_code != 0:
            # The command failed, so the plugin shouldn't do anything
            return

        command = event.command
        printer = PoetryPrinter(event.io)
        dry_run: bool = bool(command.option("dry-run"))

        if isinstance(command, SelfCommand):
            printer.debug("Poetry pre-commit plugin does not run for 'self' command.")
            return

        if any(isinstance(command, t) for t in [InstallCommand, AddCommand]):
            PoetrySetupPreCommitHooks(printer, dry_run=dry_run).execute()

        if any(isinstance(command, t) for t in [InstallCommand, AddCommand, LockCommand, UpdateCommand]):
            if self.application is None:
                raise RuntimeError("self.application is None")

            # Get all locked dependencies from self.application
            poetry_locked_packages = self.application.poetry.locker.locked_repository().packages
            locked_packages = {
                str(p.name): GenericLockedPackage(p.name, str(p.version)) for p in poetry_locked_packages
            }
            plugin_config = load_config()
            file_path = Path().cwd() / plugin_config.pre_commit_config_file

            SyncPreCommitHooksVersion(
                printer,
                pre_commit_config_file_path=file_path,
                plugin_config=plugin_config,
                locked_packages=locked_packages,
                dry_run=dry_run,
            ).execute()
