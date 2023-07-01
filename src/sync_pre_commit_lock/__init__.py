from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Final, NamedTuple

import yaml
from pdm.signals import post_install, post_lock
from pdm.termui import Verbosity

from sync_pre_commit_lock.config import SyncPreCommitLockConfig, load_config
from sync_pre_commit_lock.db import DEPENDENCY_MAPPING, DependencyMapping

if TYPE_CHECKING:
    from pathlib import Path

    from pdm.cli.hooks import HookManager
    from pdm.core import Core
    from pdm.models.candidates import Candidate
    from pdm.project import Project

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def register_pdm_plugin(core: Core) -> None:
    """Register the plugin to PDM Core."""
    pass


PRE_COMMIT_CONFIG_FILENAME: Final[str] = ".pre-commit-config.yaml"


class Printer:
    def __init__(self, project: Project | None = None):
        self.project = project
        plugin_prefix = "\[sync-pre-commit-lock]"
        if project:

            def debug(msg: str):
                project.core.ui.echo(f"[info]{plugin_prefix} " + msg + "[/info]", verbosity=Verbosity.NORMAL)

            def info(msg: str):
                project.core.ui.echo(f"[info]{plugin_prefix} " + msg + "[/info]", verbosity=Verbosity.NORMAL)

            def warning(msg: str):
                project.core.ui.echo(f"[warning]{plugin_prefix} " + msg + "[/warning]", verbosity=Verbosity.NORMAL)

            def error(msg: str):
                project.core.ui.echo(f"[error]{plugin_prefix} " + msg + "[/error]", verbosity=Verbosity.NORMAL)

        else:
            logger = logging.getLogger(__name__)

            def debug(msg: str):
                logger.debug(msg)

            def info(msg: str):
                logger.info(msg)

            def warning(msg: str):
                logger.warning(msg)

            def error(msg: str):
                logger.error(msg)

        self.debug = debug
        self.info = info
        self.warning = warning
        self.error = error


def resolve_file_path(root_path: Path, file_path: str) -> Path:
    """Resolve the file path relative to the project root."""
    return root_path.joinpath(file_path)


@post_install.connect
def on_pdm_install_setup_pre_commit(
    project: Project, *, hooks: HookManager, candidates: list[Candidate], dry_run: bool, **_
):
    printer = Printer(project)
    plugin_config: SyncPreCommitLockConfig = load_config()
    printer.debug("Checking if pre-commit hooks are installed")

    if not plugin_config.automatically_install_hooks:
        printer.debug("Automatically installing pre-commit hooks is disabled. Skipping.")
        return None

    file_path = resolve_file_path(project.root, plugin_config.pre_commit_config_file).absolute()

    if not file_path.exists():
        printer.info("No pre-commit config file found, skipping pre-commit hook check")
        return None

    printer.debug("Pre-commit config file found. Setting up pre-commit hooks...")
    from sync_pre_commit_lock.install_hooks import SetupPreCommitHooks

    action = SetupPreCommitHooks(printer)
    action.setup_pre_commit_hooks_if_appropriate(dry_run=dry_run)


@post_lock.connect
def on_pdm_lock_check_pre_commit(
    project: Project, *, resolution: dict[str, Candidate], dry_run: bool, **kwargs: Any
) -> None:
    plugin_config: SyncPreCommitLockConfig = load_config()
    printer = Printer(project)
    project_root: Path = project.root
    if plugin_config.disable_sync_from_lock:
        printer.debug("Sync pre-commit lock is disabled")
        return None

    if dry_run:
        printer.debug("Dry run, skipping pre-commit hook check")
        return None

    file_path = resolve_file_path(project_root, plugin_config.pre_commit_config_file).absolute()

    if not file_path.exists():
        printer.info("No pre-commit config file found, skipping pre-commit hook check")
        return None

    pre_commit_data = load_pre_commit_data(file_path)

    assert isinstance(pre_commit_data, dict)

    if not pre_commit_data["repos"]:
        printer.debug("No pre-commit hooks detected, skipping pre-commit hook check")
        return None

    assert isinstance(pre_commit_data["repos"], list)
    pre_commit_repos = build_pre_commit_repos(pre_commit_data["repos"])
    mapping, mapping_reverse_by_url = build_mapping(plugin_config)
    to_fix = analyze_repos(printer, pre_commit_repos, resolution, plugin_config, mapping, mapping_reverse_by_url)

    if len(to_fix) > 0:
        print_to_fix_repos(printer, to_fix)
        handle_fixes(printer, to_fix, file_path)
    else:
        printer.info("All matched pre-commit hooks in sync with the lockfile!")
        return


def load_pre_commit_data(file_path: Path) -> Any:
    with open(file_path) as stream:
        return yaml.safe_load(stream)


def build_pre_commit_repos(pre_commit_data_list: list[dict[str, str]]) -> set[PreCommitRepo]:
    return {PreCommitRepo(repo["repo"], str(repo["rev"])) for repo in pre_commit_data_list}


def analyze_repos(
    printer: Printer,
    pre_commit_repos: set[PreCommitRepo],
    resolution: dict[str, Candidate],
    plugin_config: SyncPreCommitLockConfig,
    mapping: dict[str, DependencyMapping],
    mapping_reverse_by_url: dict[str, str],
) -> dict[PreCommitRepo, str]:
    to_fix: dict[PreCommitRepo, str] = {}
    for pre_commit_repo in pre_commit_repos:
        if pre_commit_repo.repo in mapping_reverse_by_url:
            dependency = mapping[mapping_reverse_by_url[pre_commit_repo.repo]]
            dependency_name = mapping_reverse_by_url[pre_commit_repo.repo]
            dependency_locked = resolution.get(dependency_name)

            if dependency_locked:
                check_and_log_dependency(
                    printer, pre_commit_repo, dependency, dependency_locked, dependency_name, plugin_config, to_fix
                )
            else:
                printer.error(
                    f"Pre-commit hook {pre_commit_repo.repo} not found in the lockfile\n"
                    f"dependency_name: {dependency_name}\n"
                    f"DB mapping: {dependency['rev']}\n"
                )
        else:
            printer.warning(f"Pre-commit hook {pre_commit_repo.repo} not found in the DB mapping")
    return to_fix


def check_and_log_dependency(
    printer: Printer,
    pre_commit_repo: PreCommitRepo,
    dependency: DependencyMapping,
    dependency_locked: Candidate,
    dependency_name: str,
    plugin_config: SyncPreCommitLockConfig,
    to_fix: dict[PreCommitRepo, str],
) -> None:
    if dependency_locked.name in plugin_config.ignore:
        printer.debug(f"Ignoring {dependency_locked.name}")
    printer.info(f"Pre-commit hook {pre_commit_repo.repo} found in the DB mapping")
    formatted_rev = dependency["rev"].replace("${rev}", str(dependency_locked.version))
    if formatted_rev != pre_commit_repo.rev:
        printer.error(
            f"Pre-commit hook {pre_commit_repo.repo} does not match the package from the DB mapping:\n"
            f"Pre-commit hook ref: {pre_commit_repo.rev}\n"
            f"Package version: {dependency_locked.version}\n"
            f"dependency_name: {dependency_name}\n"
            f"DB mapping: {dependency['rev']}\n"
        )
        to_fix[pre_commit_repo] = formatted_rev
    else:
        printer.info(f"Pre-commit hook {pre_commit_repo.repo} matches the package from the DB mapping")


def print_to_fix_repos(printer: Printer, to_fix: dict[PreCommitRepo, str]) -> None:
    printer.info("Detected pre-commit hooks that can be updated to match the lockfile:")
    for repo, rev in to_fix.items():
        printer.info(f"  - {repo.repo}: {repo.rev} -> {rev}")


def handle_fixes(printer: Printer, to_fix: dict[PreCommitRepo, str], file_path: Path) -> None:
    fix_pre_commit(to_fix, file_path)
    printer.info("Pre-commit hooks have been updated to match the lockfile!")


def fix_pre_commit(to_fix: dict[PreCommitRepo, str], file_path: Path) -> None:
    """Fixes the pre-commit hooks to match the lockfile. Preserves comments and formatting as much as possible."""
    import difflib
    import re

    import yaml

    with open(file_path) as stream:
        original_lines = stream.readlines()
        updated_lines = original_lines[:]
        pre_commit_data = yaml.safe_load("".join(original_lines))

    for repo, rev in to_fix.items():
        for pre_commit_repo in pre_commit_data["repos"]:
            if pre_commit_repo["repo"] == repo.repo:
                rev_line_number = [i for i, line in enumerate(original_lines) if f"repo: {repo.repo}" in line][0] + 1
                original_rev_line = updated_lines[rev_line_number]
                updated_lines[rev_line_number] = re.sub(r"(?<=rev: )\S*", rev, original_rev_line)

    changes = difflib.ndiff(original_lines, updated_lines)
    change_count = sum(1 for change in changes if change[0] in ["+", "-"])

    if change_count > 0:
        with open(file_path, "w") as stream:
            stream.writelines(updated_lines)


def build_mapping(config: SyncPreCommitLockConfig) -> tuple[dict[str, DependencyMapping], dict[str, str]]:
    # Merge the default mapping with the user-provided mapping
    mapping: dict[str, DependencyMapping] = {**DEPENDENCY_MAPPING, **config.dependency_mapping}
    mapping_reverse_by_url = {repo["repo"]: lib_name for lib_name, repo in mapping.items()}
    return mapping, mapping_reverse_by_url


class PreCommitRepo(NamedTuple):
    repo: str
    rev: str  # Check if is not loaded as float/int/other yolo
