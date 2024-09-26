from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, ClassVar, Union

from packaging.requirements import Requirement
from pdm import termui
from pdm.__version__ import __version__ as pdm_version
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
from sync_pre_commit_lock.utils import url_diff

if TYPE_CHECKING:
    import argparse
    from collections.abc import Sequence
    from pathlib import Path

    from pdm.core import Core
    from pdm.models.candidates import Candidate
    from pdm.models.repositories.lock import LockedRepository
    from pdm.project import Project
    from pdm.termui import UI

    from sync_pre_commit_lock.pre_commit_config import PreCommitHook, PreCommitRepo


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

    def _format_repo_url(self, old_repo_url: str, new_repo_url: str, package_name: str) -> str:
        url = url_diff(old_repo_url, new_repo_url, "[cyan]{[/][red]", "[/red][cyan] -> [/][green]", "[/][cyan]}[/]")
        return url.replace(package_name, f"[cyan][bold]{package_name}[/bold][/cyan]")

    def list_updated_packages(self, packages: dict[str, tuple[PreCommitRepo, PreCommitRepo]]) -> None:
        """
        Args:
            packages: Dict of package name -> (repo, new_rev)
        """
        self.ui.display_columns(
            [row for package, (old, new) in packages.items() for row in self._format_repo(package, old, new)]
        )

    def _format_repo(self, package: str, old: PreCommitRepo, new: PreCommitRepo) -> Sequence[Sequence[str]]:
        new_version = new.rev != old.rev
        repo = (
            f"[info]{self.plugin_prefix}[/info] {self.success_list_token}",
            f"[info]{self._format_repo_url(old.repo, new.repo, package)}[/info]",
            " ",
            f"[error]{old.rev}[/error]" if new_version else "",
            "[info]->[/info]" if new_version else "",
            f"[green]{new.rev}[/green]" if new_version else "",
        )
        nb_hooks = len(old.hooks)
        hooks = [
            row
            for idx, (old_hook, new_hook) in enumerate(zip(old.hooks, new.hooks))
            for row in self._format_hook(old_hook, new_hook, idx + 1 == nb_hooks)
        ]
        return [repo, *hooks] if hooks else [repo]

    def _format_hook(self, old: PreCommitHook, new: PreCommitHook, last: bool) -> Sequence[Sequence[str]]:
        if not (nb_deps := len(old.additional_dependencies)):
            return []
        hook = (
            f"[info]{self.plugin_prefix}[/info]",
            f"{'└' if last else '├'} [cyan][bold]{old.id}[/bold][/cyan]",
            "",
            "",
            "",
        )
        dependencies = [
            self._format_additional_dependency(old_dep, new_dep, " " if last else "│", idx + 1 == nb_deps)
            for idx, (old_dep, new_dep) in enumerate(zip(old.additional_dependencies, new.additional_dependencies))
        ]
        return (hook, *dependencies)

    def _format_additional_dependency(self, old: str, new: str, prefix: str, last: bool) -> Sequence[str]:
        old_req = Requirement(old)
        new_req = Requirement(new)
        return (
            f"[info]{self.plugin_prefix}[/info]",
            f"{prefix} {'└' if last else '├'} [cyan][bold]{old_req.name}[/bold][/cyan]",
            " ",
            f"[error]{str(old_req.specifier).lstrip('==') or '*'}[/error]",
            "[info]->[/info]",
            f"[green]{str(new_req.specifier).lstrip('==')}[/green]",
        )


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
def on_pdm_install_setup_pre_commit(project: Project, *, dry_run: bool, **_: Any) -> None:
    printer = PDMPrinter(project.core.ui)
    project_root: Path = project.root
    plugin_config: SyncPreCommitLockConfig = load_config(project_root / project.PYPROJECT_FILENAME)
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


if TYPE_CHECKING:
    Resolution = Union[dict[str, list[Candidate]], dict[str, Candidate]]


def select_candidate(candidate: Union[Candidate, list[Candidate]]) -> Candidate | None:
    if isinstance(candidate, Iterable):
        return next(iter(candidate), None)
    return candidate


@post_lock.connect
def on_pdm_lock_check_pre_commit(
    project: Project, *, resolution: Resolution, dry_run: bool, with_prefix: bool = True, **_: Any
) -> None:
    project_root: Path = project.root
    plugin_config: SyncPreCommitLockConfig = load_config(project_root / project.PYPROJECT_FILENAME)
    printer = PDMPrinter(project.core.ui, with_prefix=with_prefix)

    file_path = project_root / plugin_config.pre_commit_config_file
    resolved_packages: dict[str, GenericLockedPackage] = {
        k: GenericLockedPackage(c.name, c.version)
        for k, v in resolution.items()
        if (c := select_candidate(v)) and c.name and c.version
    }
    # Adds pdm itself has it won't be part of the resolved dependencies
    resolved_packages["pdm"] = GenericLockedPackage("pdm", pdm_version)
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
        candidates = self._get_locked_repository(project).all_candidates

        on_pdm_lock_check_pre_commit(project, resolution=candidates, dry_run=options.dry_run, with_prefix=False)

    def _get_locked_repository(self, project: Project) -> LockedRepository:
        # `locked_repository` was deprecated in PDM 2.17 favour of `get_locked_repository`, try to use it first to avoid warning
        if hasattr(project, "get_locked_repository"):
            return project.get_locked_repository()
        return project.locked_repository
