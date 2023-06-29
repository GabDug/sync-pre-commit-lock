from __future__ import annotations


from typing import TYPE_CHECKING, Any, Final, NamedTuple

from pdm.signals import post_lock
import logging
from pdm.termui import Verbosity
import yaml

from sync_pre_commit_lock.db import DEPENDENCY_MAPPING

if TYPE_CHECKING:
    from pdm.core import Core
    from pdm.project import Project
    from pdm.models.candidates import Candidate

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def register_pdm_plugin(core: Core) -> None:
    """Register the plugin to PDM Core."""
    pass


PRE_COMMIT_CONFIG_FILENAME: Final[str] = ".pre-commit-config.yaml"


@post_lock.connect
def on_pdm_lock_check_pre_commit(project: Project, *args: Any, **kwargs: Any) -> None:
    resolution: dict[str, Candidate] = kwargs["resolution"]
    dry_run = kwargs.get("dry_run", False)
    if dry_run:
        # print("Dry run, skipping pre-commit hook check")
        logger.info("Dry run, skipping pre-commit hook check")
        return None

    # If no pre-commit config file exists, skip the check
    if not project.root.joinpath(PRE_COMMIT_CONFIG_FILENAME).exists():
        # print("No pre-commit config file found, skipping pre-commit hook check")
        logger.info("No pre-commit config file found, skipping pre-commit hook check")
        return None

    # Read the pre-commit config file
    with open(PRE_COMMIT_CONFIG_FILENAME, "r") as stream:
        pre_commit_data = yaml.safe_load(stream)

    # If no hooks are defined, skip the check
    if not pre_commit_data["repos"]:
        project.core.ui.echo(
            "No pre-commit hooks detected, skipping pre-commit hook check",
            verbosity=Verbosity.DEBUG,
        )
        logger.info("No pre-commit hooks detected, skipping pre-commit hook check")
        # print("No pre-commit hooks defined, skipping pre-commit hook check")
        return None

    pre_commit_repos = {
        PreCommitRepo(repo["repo"], str(repo["rev"]))
        for repo in pre_commit_data["repos"]
    }

    DEPENDENCY_MAPPING_REVERSE = {
        repo["repo"]: lib_name for lib_name, repo in DEPENDENCY_MAPPING.items()
    }
    "Mapping URL to lib name"
    to_fix: dict[PreCommitRepo, str] = {}
    for pre_commit_repo in pre_commit_repos:
        if pre_commit_repo.repo in DEPENDENCY_MAPPING_REVERSE:
            dependency = DEPENDENCY_MAPPING[
                DEPENDENCY_MAPPING_REVERSE[pre_commit_repo.repo]
            ]
            dependency_name = DEPENDENCY_MAPPING_REVERSE[pre_commit_repo.repo]
            dependency_locked = resolution.get(dependency_name)
            # dependency_locked_version.
            # if dep := resolution.get(dependency["repo"]):
            if dependency_locked:
                logger.info(
                    f"Pre-commit hook {pre_commit_repo.repo} found in the DB mapping"
                )
                formatted_rev = dependency["rev"].replace(
                    "${rev}", str(dependency_locked.version)
                )
                if formatted_rev != pre_commit_repo.rev:
                    logger.error(
                        f"Pre-commit hook {pre_commit_repo.repo} does not match the package from the DB mapping:\n"
                        f"Pre-commit hook ref: {pre_commit_repo.rev}\n"
                        f"Package version: {dependency_locked.version}\n"
                        f"dependency_name: {dependency_name}\n"
                        f"DB mapping: {dependency['rev']}\n"
                    )
                    to_fix[pre_commit_repo] = formatted_rev
                else:
                    logger.info(
                        f"Pre-commit hook {pre_commit_repo.repo} matches the package from the DB mapping"
                    )
            else:
                logger.error(
                    f"Pre-commit hook {pre_commit_repo.repo} not found in the lockfile\n"
                    f"dependency_name: {dependency_name}\n"
                    f"DB mapping: {dependency['rev']}\n"
                )
        else:
            logger.error(
                f"Pre-commit hook {pre_commit_repo.repo} not found in the DB mapping"
            )
    print(to_fix)
    if len(to_fix) > 0:
        project.core.ui.echo(
            "Detected pre-commit hooks that can be updated to match the lockfile:"
        )
        for repo, rev in to_fix.items():
            project.core.ui.echo(f"  - {repo.repo}: {repo.rev} -> {rev}")
    else:
        project.core.ui.echo("All detected pre-commit hooks match the lockfile!")
        return

    fix_pre_commit(project, to_fix)


def fix_pre_commit(project: Project, to_fix: dict[PreCommitRepo, str]) -> None:
    """Fixes the pre-commit hooks to match the lockfile. Preserves comments and formatting as much as possible."""
    import re
    import difflib
    import yaml

    with open(PRE_COMMIT_CONFIG_FILENAME, "r") as stream:
        original_lines = stream.readlines()
        updated_lines = original_lines[:]
        pre_commit_data = yaml.safe_load("".join(original_lines))

    for repo, rev in to_fix.items():
        for pre_commit_repo in pre_commit_data["repos"]:
            if pre_commit_repo["repo"] == repo.repo:
                rev_line_number = [
                    i
                    for i, line in enumerate(original_lines)
                    if f"repo: {repo.repo}" in line
                ][0] + 1
                original_rev_line = updated_lines[rev_line_number]
                updated_lines[rev_line_number] = re.sub(
                    r"(?<=rev: )\S*", rev, original_rev_line
                )

    changes = difflib.ndiff(original_lines, updated_lines)
    change_count = sum(1 for change in changes if change[0] in ["+", "-"])

    if change_count > 0:
        with open(PRE_COMMIT_CONFIG_FILENAME, "w") as stream:
            stream.writelines(updated_lines)
        project.core.ui.echo(
            "Pre-commit hooks have been updated to match the lockfile!"
        )


class PreCommitRepo(NamedTuple):
    repo: str
    rev: str  # Check if is not loaded as float/int/other yolo
