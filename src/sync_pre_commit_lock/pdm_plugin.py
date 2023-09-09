from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from pdm import termui
from pdm.cli.commands.base import BaseCommand
from pdm.cli.options import dry_run_option
from pdm.signals import post_install, post_lock
from pdm.termui import Verbosity

from sync_pre_commit_lock import (
    Printer,
)
from sync_pre_commit_lock.actions.install_hooks import SetupPreCommitHooks
from sync_pre_commit_lock.actions.sync_hooks import GenericLockedPackage, SyncPreCommitHooksVersion
from sync_pre_commit_lock.config import SyncPreCommitLockConfig, load_config

if TYPE_CHECKING:
    import argparse
    from collections.abc import Sequence
    from pathlib import Path

    from pdm.cli.hooks import HookManager
    from pdm.core import Core
    from pdm.models.candidates import Candidate
    from pdm.project import Project
    from pdm.termui import UI


class PDMPrinter(Printer):
    success_list_token: str = f"[success]{termui.Emoji.SUCC}[/]"

    def __init__(self, ui: UI, with_prefix: bool = True, **_: Any):
        self.ui = ui
        self.plugin_prefix = "\\[sync-pre-commit-lock] " if with_prefix else ""

    def prefix_lines(self, msg: str) -> str:
        lines = msg.split("\n")
        return "\n".join(f"{self.plugin_prefix}{line}" for line in lines)

    def debug(self, msg: str) -> None:
        self.ui.echo(self.prefix_lines("[debug]" + msg + "[/debug]"), verbosity=Verbosity.DEBUG)

    def info(self, msg: str) -> None:
        self.ui.echo("[info]" + self.prefix_lines(msg) + "[/info]", verbosity=Verbosity.NORMAL)

    def warning(self, msg: str) -> None:
        self.ui.echo("[warning]" + self.prefix_lines(msg) + "[/warning]", verbosity=Verbosity.NORMAL)

    def error(self, msg: str) -> None:
        self.ui.echo("[error]" + self.prefix_lines(msg) + "[/error]", verbosity=Verbosity.NORMAL)

    def success(self, msg: str) -> None:
        self.ui.echo("[success]" + self.prefix_lines(msg) + "[/success]", verbosity=Verbosity.NORMAL)


def register_pdm_plugin(core: Core) -> None:
    """Register the plugin to PDM Core."""
    core.register_command(SyncPreCommitVersionsPDMCommand, "sync-pre-commit")
    printer = PDMPrinter(core.ui)
    printer.debug("Registered sync-pre-commit-lock plugin.")


class PDMSetupPreCommitHooks(SetupPreCommitHooks):
    install_pre_commit_hooks_command: ClassVar[Sequence[str | bytes]] = ["pdm", "run", "pre-commit", "install"]
    check_pre_commit_version_command: ClassVar[Sequence[str | bytes]] = ["pdm", "run", "pre-commit", "--version"]


class PDMSyncPreCommitHooksVersion(SyncPreCommitHooksVersion):
    pass


@post_install.connect
def on_pdm_install_setup_pre_commit(
    project: Project, *, hooks: HookManager, candidates: list[Candidate], dry_run: bool, **_: Any
) -> None:
    printer = PDMPrinter(project.core.ui)
    plugin_config: SyncPreCommitLockConfig = load_config()
    printer.debug("Checking if pre-commit hooks are installed")

    if not plugin_config.automatically_install_hooks:
        printer.debug("Automatically installing pre-commit hooks is disabled. Skipping.")
        return
    action = PDMSetupPreCommitHooks(printer, dry_run=dry_run)
    file_path = project.root / plugin_config.pre_commit_config_file
    if not file_path.exists():
        printer.info("No pre-commit config file found, skipping pre-commit hook check")
        return

    printer.debug("Pre-commit config file found. Setting up pre-commit hooks...")

    action.execute()


@post_lock.connect
def on_pdm_lock_check_pre_commit(
    project: Project, *, resolution: dict[str, Candidate], dry_run: bool, with_prefix: bool = True, **kwargs: Any
) -> None:
    project_root: Path = project.root
    plugin_config: SyncPreCommitLockConfig = load_config(project_root / project.PYPROJECT_FILENAME)
    printer = PDMPrinter(project.core.ui, with_prefix=with_prefix)

    file_path = project_root / plugin_config.pre_commit_config_file
    resolved_packages: dict[str, GenericLockedPackage] = {
        k: GenericLockedPackage(v.name, v.version) for k, v in resolution.items() if v.name and v.version
    }
    action = SyncPreCommitHooksVersion(
        printer=printer,
        pre_commit_config_file_path=file_path,
        locked_packages=resolved_packages,
        plugin_config=plugin_config,
        dry_run=dry_run,
    )
    action.execute()


class SyncPreCommitVersionsPDMCommand(BaseCommand):
    """Sync `.pre-commit-config.yaml` hooks versions with the lockfile"""

    # The class docstring acts as the description of the command, don't make it longer!

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        dry_run_option.add_to_parser(parser)

    def handle(self, project: Project, options: argparse.Namespace) -> None:
        candidates = project.locked_repository.all_candidates

        on_pdm_lock_check_pre_commit(project, resolution=candidates, dry_run=options.dry_run, with_prefix=False)
