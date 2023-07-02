from __future__ import annotations

import difflib
import re
from functools import cached_property
from typing import TYPE_CHECKING, Any, NamedTuple

import yaml

from sync_pre_commit_lock.db import DEPENDENCY_MAPPING, PackageRepoMapping, RepoInfo
from sync_pre_commit_lock.utils import normalize_git_url

if TYPE_CHECKING:
    from pathlib import Path

    from sync_pre_commit_lock import Printer
    from sync_pre_commit_lock.config import SyncPreCommitLockConfig


class GenericLockedPackage(NamedTuple):
    name: str
    version: str
    # Add original data here?


class PreCommitRepo(NamedTuple):
    repo: str
    rev: str  # Check if is not loaded as float/int/other yolo


class PreCommitHookConfig:
    def __init__(self, data: dict[str, Any], pre_commit_config_file_path: Path, original_file_lines: list[str]) -> None:
        self._data = data
        self.pre_commit_config_file_path = pre_commit_config_file_path
        self.original_file_lines: list[str] = original_file_lines

    @property
    def data(self) -> dict[str, Any]:
        return self._data

    @data.setter
    def data(self, value: dict[str, Any]) -> None:
        raise NotImplementedError("This should not be used. Recreate the object instead.")

    @classmethod
    def from_yaml_file(cls, file_path: Path) -> PreCommitHookConfig:
        with file_path.open("r") as stream:
            x = yaml.safe_load(stream)
            if not isinstance(x, dict):
                raise ValueError(f"Invalid pre-commit config file: {file_path}. Expected a dict, got {type(x)}")
            if "repos" in x and not isinstance(x["repos"], list):
                raise ValueError(
                    f"Invalid pre-commit config file: {file_path}. Expected a list for `repos`, got {type(x['repos'])}"
                )
            return PreCommitHookConfig(x, file_path, original_file_lines=stream.readlines())

    @cached_property
    def repos(self) -> list[PreCommitRepo]:
        return [PreCommitRepo(repo=repo["repo"], rev=repo["rev"]) for repo in (self.data["repos"] or [])]

    @cached_property
    def repos_normalized(self) -> set[PreCommitRepo]:
        return {PreCommitRepo(repo=normalize_git_url(repo.repo), rev=repo.rev) for repo in self.repos}

    def update_pre_commit_repo_versions(self, new_versions: dict[PreCommitRepo, str]) -> None:
        """Fixes the pre-commit hooks to match the lockfile. Preserves comments and formatting as much as possible."""

        original_lines = self.original_file_lines
        updated_lines = original_lines[:]
        pre_commit_data = self.data

        for repo, rev in new_versions.items():
            for pre_commit_repo in pre_commit_data["repos"]:
                if pre_commit_repo["repo"] != repo.repo:
                    continue
                rev_line_number = [i for i, line in enumerate(original_lines) if f"repo: {repo.repo}" in line][0] + 1
                original_rev_line = updated_lines[rev_line_number]
                updated_lines[rev_line_number] = re.sub(r"(?<=rev: )\S*", rev, original_rev_line)

        changes = difflib.ndiff(original_lines, updated_lines)
        change_count = sum(1 for change in changes if change[0] in ["+", "-"])

        if change_count == 0:
            return
        with open(self.pre_commit_config_file_path, "w") as stream:
            stream.writelines(updated_lines)


class SyncPreCommitHooksVersion:
    def __init__(
        self,
        printer: Printer,
        pre_commit_config_file_path: Path,
        locked_packages: dict[str, GenericLockedPackage],
        plugin_config: SyncPreCommitLockConfig,
        dry_run: bool = False,
    ) -> None:
        self.printer = printer
        self.pre_commit_config_file_path = pre_commit_config_file_path
        self.locked_packages = locked_packages
        self.plugin_config = plugin_config
        self.dry_run = dry_run

    def execute(self) -> None:
        if self.plugin_config.disable_sync_from_lock:
            self.printer.debug("Sync pre-commit lock is disabled")
            return None

        if self.dry_run:
            self.printer.debug("Dry run, skipping pre-commit hook check")
            return None
        try:
            pre_commit_config_data = PreCommitHookConfig.from_yaml_file(self.pre_commit_config_file_path)
        except FileNotFoundError:
            self.printer.info(
                f"No pre-commit config file detected at {self.pre_commit_config_file_path}, skipping sync."
            )
            return
        except ValueError as e:
            self.printer.error(f"Invalid pre-commit config file: {self.pre_commit_config_file_path}: {e}")
            return None

        mapping, mapping_reverse_by_url = self.build_mapping()

        to_fix = self.analyze_repos(pre_commit_config_data.repos_normalized, mapping, mapping_reverse_by_url)

        if len(to_fix) == 0:
            self.printer.info("All matched pre-commit hooks already in sync with the lockfile!")
            return

        self.printer.info("Detected pre-commit hooks that can be updated to match the lockfile:")
        for repo, rev in to_fix.items():
            self.printer.info(f"  - {repo.repo}: {repo.rev} -> {rev}")
        pre_commit_config_data.update_pre_commit_repo_versions(to_fix)
        self.printer.info("Pre-commit hooks have been updated to match the lockfile!")

    def get_pre_commit_repo_new_version(
        self,
        pre_commit_config_repo: PreCommitRepo,
        mapping_db_repo_info: RepoInfo,
        locked_package: GenericLockedPackage,
    ) -> str | None:
        if locked_package.name in self.plugin_config.ignore:
            self.printer.debug(f"Ignoring {locked_package.name} from configuration.")
            return None

        self.printer.debug(
            f"Found mapping between pre-commit hook `{pre_commit_config_repo.repo}` and locked package `{locked_package.name}`."
        )
        formatted_rev = mapping_db_repo_info["rev"].replace("${rev}", str(locked_package.version))
        if formatted_rev != pre_commit_config_repo.rev:
            self.printer.warning(
                f"Pre-commit hook {pre_commit_config_repo.repo} and locked package {locked_package.name} have different versions:\n"
                f"  Pre-commit hook ref: {pre_commit_config_repo.rev}\n"
                f"  Locked package version: {locked_package.version}\n"
            )
            return formatted_rev
        else:
            self.printer.debug(
                f"Pre-commit hook {pre_commit_config_repo.repo} version already matches the version from the lockfile package."
            )
        return None

    def build_mapping(self) -> tuple[PackageRepoMapping, dict[str, str]]:
        """Merge the default mapping with the user-provided mapping. Also build a reverse mapping by URL."""
        mapping: PackageRepoMapping = {**DEPENDENCY_MAPPING, **self.plugin_config.dependency_mapping}
        mapping_reverse_by_url = {repo["repo"]: lib_name for lib_name, repo in mapping.items()}
        return mapping, mapping_reverse_by_url

    def analyze_repos(
        self,
        pre_commit_repos: set[PreCommitRepo],
        mapping: PackageRepoMapping,
        mapping_reverse_by_url: dict[str, str],
    ) -> dict[PreCommitRepo, str]:
        to_fix: dict[PreCommitRepo, str] = {}
        for pre_commit_repo in pre_commit_repos:
            if pre_commit_repo.repo not in mapping_reverse_by_url:
                self.printer.debug(f"Pre-commit hook {pre_commit_repo.repo} not found in the DB mapping")
                continue

            dependency = mapping[mapping_reverse_by_url[pre_commit_repo.repo]]
            dependency_name = mapping_reverse_by_url[pre_commit_repo.repo]
            dependency_locked = self.locked_packages.get(dependency_name)

            if not dependency_locked:
                self.printer.info(
                    f"Pre-commit hook {pre_commit_repo.repo} has a mapping to Python package `{dependency_name}`,"
                    "but was not found in the lockfile"
                )
                continue

            new_ver = self.get_pre_commit_repo_new_version(pre_commit_repo, dependency, dependency_locked)
            if new_ver:
                to_fix[pre_commit_repo] = new_ver

        return to_fix
