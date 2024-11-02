from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING, NamedTuple, Sequence

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name

from sync_pre_commit_lock.db import DEPENDENCY_MAPPING, REPOSITORY_ALIASES, PackageRepoMapping
from sync_pre_commit_lock.pre_commit_config import PreCommitHook, PreCommitHookConfig, PreCommitRepo

if TYPE_CHECKING:
    from pathlib import Path

    from sync_pre_commit_lock import Printer
    from sync_pre_commit_lock.config import SyncPreCommitLockConfig


class GenericLockedPackage(NamedTuple):
    name: str
    version: str
    # Add original data here?


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
            return

        try:
            pre_commit_config_data = PreCommitHookConfig.from_yaml_file(self.pre_commit_config_file_path)
        except FileNotFoundError:
            self.printer.info(
                f"No pre-commit config file detected at {self.pre_commit_config_file_path}, skipping sync."
            )
            return
        except ValueError as e:
            self.printer.error(f"Invalid pre-commit config file: {self.pre_commit_config_file_path}: {e}")
            return

        # XXX We should have the list of packages mapped, but already up to date and print it
        to_fix, in_sync = self.analyze_repos(pre_commit_config_data.repos_normalized)

        if len(to_fix) == 0 and len(in_sync) == 0:
            self.printer.info("No pre-commit hook detected that matches a locked package.")
            return
        if len(to_fix) == 0:
            packages_str = ", ".join(
                f"{self.mapping_reverse_by_url[pre_commit.repo]} ({pre_commit.rev})" for pre_commit in in_sync.values()
            )
            self.printer.info(f"All pre-commit hooks are already up to date with the lockfile: {packages_str}")
            return

        self.printer.info("Detected pre-commit hooks that can be updated to match the lockfile:")
        self.printer.list_updated_packages(
            {self.mapping_reverse_by_url[repo.repo]: (repo, new_ver) for repo, new_ver in to_fix.items()}
        )

        if self.dry_run:
            self.printer.info("Dry run, skipping pre-commit hook update.")
            return
        pre_commit_config_data.update_pre_commit_repo_versions(to_fix)
        self.printer.success(f"Pre-commit hooks have been updated in {self.pre_commit_config_file_path.name}!")

    @cached_property
    def mapping(self) -> PackageRepoMapping:
        return {**DEPENDENCY_MAPPING, **self.plugin_config.dependency_mapping}

    @cached_property
    def mapping_reverse_by_url(self) -> dict[str, str]:
        """Merge the default mapping with the user-provided mapping. Also build a reverse mapping by URL."""
        mapping_reverse_by_url = {repo["repo"]: lib_name for lib_name, repo in self.mapping.items()}
        for canonical_name, aliases in REPOSITORY_ALIASES.items():
            if canonical_name in mapping_reverse_by_url:
                for alias in aliases:
                    mapping_reverse_by_url[alias] = mapping_reverse_by_url[canonical_name]
        # XXX Allow override / extend of aliases
        return mapping_reverse_by_url

    def get_pre_commit_repo_new_version(
        self,
        pre_commit_config_repo: PreCommitRepo,
    ) -> str | None:
        dependency = self.mapping[self.mapping_reverse_by_url[pre_commit_config_repo.repo]]
        dependency_name = self.mapping_reverse_by_url[pre_commit_config_repo.repo]
        locked_package = self.locked_packages.get(dependency_name)

        if not locked_package:
            self.printer.debug(
                f"Pre-commit hook {pre_commit_config_repo.repo} has a mapping to Python package `{dependency_name}`, "
                "but was not found in the lockfile"
            )
            return None

        if "+" in locked_package.version:
            self.printer.debug(
                f"Pre-commit hook {pre_commit_config_repo.repo} has a mapping to Python package `{dependency_name}`, "
                f"but is skipped because the locked version `{locked_package.version}` contaims a `+`, "
                "which is a local version identifier."
            )
            return None
        if locked_package.name in self.plugin_config.ignore:
            self.printer.debug(f"Ignoring {locked_package.name} from configuration.")
            return None

        self.printer.debug(
            f"Found mapping between pre-commit hook `{pre_commit_config_repo.repo}` and locked package `{locked_package.name}`."
        )
        formatted_rev = dependency["rev"].replace("${rev}", str(locked_package.version))
        if formatted_rev != pre_commit_config_repo.rev:
            self.printer.debug(
                f"Pre-commit hook {pre_commit_config_repo.repo} and locked package {locked_package.name} have different versions:\n"
                f" - Pre-commit hook ref: {pre_commit_config_repo.rev}\n"
                f" - Locked package version: {locked_package.version}"
            )
            return formatted_rev

        self.printer.debug(
            f"Pre-commit hook {pre_commit_config_repo.repo} version already matches the version from the lockfile package."
        )
        return None

    def get_pre_commit_repo_new_url(self, url: str) -> str:
        return self.mapping[self.mapping_reverse_by_url[url]]["repo"]

    def get_pre_commit_repo_new_hooks(self, hooks: Sequence[PreCommitHook]) -> Sequence[PreCommitHook]:
        return [self.get_pre_commit_repo_new_hook(hook) for hook in hooks]

    def get_pre_commit_repo_new_hook(self, hook: PreCommitHook) -> PreCommitHook:
        return PreCommitHook(
            hook.id, [self.get_pre_commit_repo_hook_new_dependency(dep) for dep in hook.additional_dependencies]
        )

    def get_pre_commit_repo_hook_new_dependency(self, dependency: str) -> str:
        if "+" in dependency:
            self.printer.debug(f"Additional dependency {dependency} is a local version. Ignoring.")
            return dependency
        try:
            requirement = Requirement(dependency)
        except InvalidRequirement:
            self.printer.debug(f"Invalid additional dependency {dependency}. Ignoring.")
            return dependency
        normalized_name = canonicalize_name(requirement.name)
        if not (locked_version := self.locked_packages.get(normalized_name)):
            self.printer.debug(f"Additional dependency {dependency} not found in the lockfile. Ignoring.")
            return dependency
        requirement.specifier = SpecifierSet(f"=={locked_version.version}")
        return str(requirement)

    def analyze_repos(
        self,
        pre_commit_repos: set[PreCommitRepo],
    ) -> tuple[dict[PreCommitRepo, PreCommitRepo], dict[PreCommitRepo, PreCommitRepo]]:
        to_fix: dict[PreCommitRepo, PreCommitRepo] = {}
        in_sync: dict[PreCommitRepo, PreCommitRepo] = {}
        for pre_commit_repo in pre_commit_repos:
            if pre_commit_repo.repo not in self.mapping_reverse_by_url:
                self.printer.debug(f"Pre-commit hook {pre_commit_repo.repo} not found in the DB mapping")
                continue

            new_repo = PreCommitRepo(
                repo=self.get_pre_commit_repo_new_url(pre_commit_repo.repo),
                rev=self.get_pre_commit_repo_new_version(pre_commit_repo) or pre_commit_repo.rev,
                hooks=self.get_pre_commit_repo_new_hooks(pre_commit_repo.hooks),
            )
            if new_repo != pre_commit_repo:
                to_fix[pre_commit_repo] = new_repo
            else:
                in_sync[pre_commit_repo] = pre_commit_repo

        return to_fix, in_sync
