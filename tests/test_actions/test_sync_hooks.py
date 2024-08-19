from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sync_pre_commit_lock import Printer
from sync_pre_commit_lock.actions.sync_hooks import (
    GenericLockedPackage,
    SyncPreCommitHooksVersion,
)
from sync_pre_commit_lock.config import SyncPreCommitLockConfig
from sync_pre_commit_lock.db import RepoInfo
from sync_pre_commit_lock.pre_commit_config import PreCommitHook, PreCommitHookConfig, PreCommitRepo


def test_execute_returns_early_when_disabled() -> None:
    printer = MagicMock(spec=Printer)
    pre_commit_config_file_path = MagicMock(spec=Path)
    locked_packages: dict[str, GenericLockedPackage] = {}
    plugin_config: SyncPreCommitLockConfig = MagicMock(spec=SyncPreCommitLockConfig)
    plugin_config.disable_sync_from_lock = True
    dry_run = False

    syncer = SyncPreCommitHooksVersion(
        printer=printer,
        pre_commit_config_file_path=pre_commit_config_file_path,
        locked_packages=locked_packages,
        plugin_config=plugin_config,
        dry_run=dry_run,
    )
    syncer.execute()
    printer.debug.assert_called_once_with("Sync pre-commit lock is disabled")


@patch("sync_pre_commit_lock.pre_commit_config.PreCommitHookConfig.from_yaml_file")
@patch.object(SyncPreCommitHooksVersion, "analyze_repos")
def test_execute_returns_early_during_dry_run(mock_analyze_repos: MagicMock, mock_from_yaml_file: MagicMock) -> None:
    printer = MagicMock(spec=Printer)
    pre_commit_config_file_path = MagicMock(spec=Path)
    locked_packages: dict[str, GenericLockedPackage] = {}
    plugin_config = MagicMock(spec=SyncPreCommitLockConfig)
    plugin_config.disable_sync_from_lock = False
    dry_run = True

    syncer = SyncPreCommitHooksVersion(
        printer=printer,
        pre_commit_config_file_path=pre_commit_config_file_path,
        locked_packages=locked_packages,
        plugin_config=plugin_config,
        dry_run=dry_run,
    )

    # Mocks
    pre_commit_config = MagicMock(spec=PreCommitHookConfig)
    mock_from_yaml_file.return_value = pre_commit_config
    syncer.mapping_reverse_by_url = {"repo1": "somepkg"}
    mock_analyze_repos.return_value = {PreCommitRepo("repo1", "rev1"): "rev2"}, {}

    syncer.execute()

    # Assertions
    mock_analyze_repos.assert_called_once()
    pre_commit_config.update_pre_commit_repo_versions.assert_not_called()
    printer.info.assert_called_with("Dry run, skipping pre-commit hook update.")


@patch("sync_pre_commit_lock.pre_commit_config.PreCommitHookConfig.from_yaml_file", side_effect=FileNotFoundError())
def test_execute_handles_file_not_found(mock_from_yaml_file: MagicMock) -> None:
    printer = MagicMock(spec=Printer)
    pre_commit_config_file_path = MagicMock(spec=Path)
    locked_packages: dict[str, GenericLockedPackage] = {}
    plugin_config = MagicMock(spec=SyncPreCommitLockConfig)
    plugin_config.disable_sync_from_lock = False
    dry_run = False

    syncer = SyncPreCommitHooksVersion(
        printer=printer,
        pre_commit_config_file_path=pre_commit_config_file_path,
        locked_packages=locked_packages,
        plugin_config=plugin_config,
        dry_run=dry_run,
    )
    syncer.execute()
    printer.info.assert_called_once_with(
        f"No pre-commit config file detected at {pre_commit_config_file_path}, skipping sync."
    )


@patch("sync_pre_commit_lock.pre_commit_config.PreCommitHookConfig.from_yaml_file", side_effect=ValueError())
def test_execute_handles_file_invalid(mock_from_yaml_file: MagicMock) -> None:
    printer = MagicMock(spec=Printer)
    pre_commit_config_file_path = MagicMock(spec=Path)
    locked_packages: dict[str, GenericLockedPackage] = {}
    plugin_config = MagicMock(spec=SyncPreCommitLockConfig)
    plugin_config.disable_sync_from_lock = False
    dry_run = False

    syncer = SyncPreCommitHooksVersion(
        printer=printer,
        pre_commit_config_file_path=pre_commit_config_file_path,
        locked_packages=locked_packages,
        plugin_config=plugin_config,
        dry_run=dry_run,
    )
    syncer.execute()
    printer.error.assert_called_once_with(f"Invalid pre-commit config file: {pre_commit_config_file_path}: ")


@patch("sync_pre_commit_lock.pre_commit_config.PreCommitHookConfig.from_yaml_file")
@patch.object(SyncPreCommitHooksVersion, "analyze_repos")
def test_execute_synchronizes_hooks(mock_analyze_repos: MagicMock, mock_from_yaml_file: MagicMock) -> None:
    printer = MagicMock(spec=Printer)
    pre_commit_config_file_path = MagicMock(spec=Path)
    pre_commit_config_file_path.name = ".pre-commit-config.yaml"
    locked_packages: dict[str, GenericLockedPackage] = {}
    plugin_config = MagicMock(spec=SyncPreCommitLockConfig)
    plugin_config.disable_sync_from_lock = False
    dry_run = False

    syncer = SyncPreCommitHooksVersion(
        printer=printer,
        pre_commit_config_file_path=pre_commit_config_file_path,
        locked_packages=locked_packages,
        plugin_config=plugin_config,
        dry_run=dry_run,
    )

    # Mocks
    pre_commit_config = MagicMock(spec=PreCommitHookConfig)
    mock_from_yaml_file.return_value = pre_commit_config
    syncer.mapping_reverse_by_url = {"repo1": "somepkg"}
    mock_analyze_repos.return_value = {PreCommitRepo("repo1", "rev1"): "rev2"}, {}

    syncer.execute()

    # Assertions
    mock_analyze_repos.assert_called_once()
    pre_commit_config.update_pre_commit_repo_versions.assert_called_once_with({PreCommitRepo("repo1", "rev1"): "rev2"})
    printer.success.assert_called_with("Pre-commit hooks have been updated in .pre-commit-config.yaml!")


@patch("sync_pre_commit_lock.pre_commit_config.PreCommitHookConfig.from_yaml_file")
@patch.object(SyncPreCommitHooksVersion, "analyze_repos")
def test_execute_synchronizes_hooks_no_match(mock_analyze_repos: MagicMock, mock_from_yaml_file: MagicMock) -> None:
    printer = MagicMock(spec=Printer)
    pre_commit_config_file_path = MagicMock(spec=Path)
    locked_packages: dict[str, GenericLockedPackage] = {}
    plugin_config = MagicMock(spec=SyncPreCommitLockConfig)
    plugin_config.disable_sync_from_lock = False
    dry_run = False

    syncer = SyncPreCommitHooksVersion(
        printer=printer,
        pre_commit_config_file_path=pre_commit_config_file_path,
        locked_packages=locked_packages,
        plugin_config=plugin_config,
        dry_run=dry_run,
    )
    syncer.mapping = {}

    # Mocks
    pre_commit_config = MagicMock(spec=PreCommitHookConfig)
    mock_from_yaml_file.return_value = pre_commit_config
    mock_analyze_repos.return_value = {}, {}

    syncer.execute()

    # Assertions
    mock_analyze_repos.assert_called_once()
    pre_commit_config.update_pre_commit_repo_versions.assert_not_called()
    printer.info.assert_called_with("No pre-commit hook detected that matches a locked package.")


def test_get_pre_commit_repo_new_version() -> None:
    printer = MagicMock(spec=Printer)
    pre_commit_config_file_path = MagicMock(spec=Path)
    locked_packages: dict[str, GenericLockedPackage] = {"lib-name": GenericLockedPackage("lib-name", "2.0.0")}
    plugin_config = MagicMock(spec=SyncPreCommitLockConfig)
    plugin_config.ignore = []
    syncer = SyncPreCommitHooksVersion(
        printer=printer,
        pre_commit_config_file_path=pre_commit_config_file_path,
        locked_packages=locked_packages,
        plugin_config=plugin_config,
    )
    pre_commit_config_repo = PreCommitRepo("repo_url", "1.2.3")
    syncer.mapping = {"lib-name": {"repo": "repo_url", "rev": "${rev}"}}

    new_version = syncer.get_pre_commit_repo_new_version(pre_commit_config_repo)

    assert new_version == "2.0.0"


@patch.object(SyncPreCommitHooksVersion, "get_pre_commit_repo_new_version")
def test_analyze_repos(mock_get_pre_commit_repo_new_version: MagicMock) -> None:
    printer = MagicMock(spec=Printer)
    pre_commit_config_file_path = MagicMock(spec=Path)
    locked_packages: dict[str, GenericLockedPackage] = {"lib-name": GenericLockedPackage("lib-name", "2.0.0")}
    plugin_config = MagicMock(spec=SyncPreCommitLockConfig)

    syncer = SyncPreCommitHooksVersion(
        printer=printer,
        pre_commit_config_file_path=pre_commit_config_file_path,
        locked_packages=locked_packages,
        plugin_config=plugin_config,
    )
    mock_get_pre_commit_repo_new_version.return_value = "2.0.0"
    pre_commit_repos = {PreCommitRepo("https://repo_url", "1.2.3")}
    syncer.mapping = {"lib-name": {"repo": "https://repo_url", "rev": "${rev}"}}
    syncer.mapping_reverse_by_url = {"https://repo_url": "lib-name"}

    to_fix, _ = syncer.analyze_repos(pre_commit_repos)

    assert to_fix == {PreCommitRepo("https://repo_url", "1.2.3"): PreCommitRepo("https://repo_url", "2.0.0")}


def test_build_mapping() -> None:
    printer = MagicMock(spec=Printer)
    pre_commit_config_file_path = MagicMock(spec=Path)
    locked_packages: dict[str, GenericLockedPackage] = {}
    plugin_config = MagicMock(spec=SyncPreCommitLockConfig)

    syncer = SyncPreCommitHooksVersion(
        printer=printer,
        pre_commit_config_file_path=pre_commit_config_file_path,
        locked_packages=locked_packages,
        plugin_config=plugin_config,
    )
    plugin_config.dependency_mapping = {"new_lib": {"repo": "new_repo_url", "rev": "${rev}"}}

    assert "new_lib" in syncer.mapping
    assert syncer.mapping["new_lib"]["repo"] == "new_repo_url"
    assert "new_repo_url" in syncer.mapping_reverse_by_url
    assert syncer.mapping_reverse_by_url["new_repo_url"] == "new_lib"


def test_get_pre_commit_repo_new_version_ignored() -> None:
    printer = MagicMock(spec=Printer)
    pre_commit_config_file_path = MagicMock(spec=Path)
    locked_packages: dict[str, GenericLockedPackage] = {"lib-name": GenericLockedPackage("lib-name", "2.0.0")}
    plugin_config = MagicMock(spec=SyncPreCommitLockConfig)
    plugin_config.ignore = ["lib-name"]

    syncer = SyncPreCommitHooksVersion(
        printer=printer,
        pre_commit_config_file_path=pre_commit_config_file_path,
        locked_packages=locked_packages,
        plugin_config=plugin_config,
    )
    syncer.mapping = {"lib-name": RepoInfo(repo="repo_url", rev="${rev}")}

    pre_commit_config_repo = PreCommitRepo("repo_url", "1.2.3")

    new_version = syncer.get_pre_commit_repo_new_version(pre_commit_config_repo)

    assert new_version is None


def test_get_pre_commit_repo_new_version_version_match() -> None:
    printer = MagicMock(spec=Printer)
    pre_commit_config_file_path = MagicMock(spec=Path)
    locked_packages: dict[str, GenericLockedPackage] = {"lib-name": GenericLockedPackage("lib-name", "1.2.3")}
    plugin_config = MagicMock(spec=SyncPreCommitLockConfig)
    plugin_config.ignore = []

    syncer = SyncPreCommitHooksVersion(
        printer=printer,
        pre_commit_config_file_path=pre_commit_config_file_path,
        locked_packages=locked_packages,
        plugin_config=plugin_config,
    )

    pre_commit_config_repo = PreCommitRepo("repo_url", "1.2.3")
    syncer.mapping = {"lib-name": RepoInfo(repo="repo_url", rev="${rev}")}

    new_version = syncer.get_pre_commit_repo_new_version(pre_commit_config_repo)

    assert new_version is None


@pytest.mark.parametrize(
    "dependency, expected",
    [
        pytest.param("dep==1.2.3", "dep==1.2.3", id="same"),
        pytest.param("dep", "dep==1.2.3", id="locked"),
        pytest.param("other", "other", id="not-in-lock"),
        pytest.param("dep<>unparsable", "dep<>unparsable", id="unparsable"),
        pytest.param("dep==1.0.0+dev", "dep==1.0.0+dev", id="local"),
        pytest.param("Dep", "Dep==1.2.3", id="casing"),
    ],
)
def test_get_pre_commit_repo_hook_new_dependency(dependency: str, expected: str) -> None:
    printer = MagicMock(spec=Printer)
    pre_commit_config_file_path = MagicMock(spec=Path)
    locked_packages: dict[str, GenericLockedPackage] = {"dep": GenericLockedPackage("dep", "1.2.3")}
    plugin_config = MagicMock(spec=SyncPreCommitLockConfig)
    plugin_config.ignore = []

    syncer = SyncPreCommitHooksVersion(
        printer=printer,
        pre_commit_config_file_path=pre_commit_config_file_path,
        locked_packages=locked_packages,
        plugin_config=plugin_config,
    )

    assert syncer.get_pre_commit_repo_hook_new_dependency(dependency) == expected


def test_analyze_repos_repo_not_in_mapping() -> None:
    printer = MagicMock(spec=Printer)
    pre_commit_config_file_path = MagicMock(spec=Path)
    locked_packages: dict[str, GenericLockedPackage] = {}
    plugin_config = MagicMock(spec=SyncPreCommitLockConfig)

    syncer = SyncPreCommitHooksVersion(
        printer=printer,
        pre_commit_config_file_path=pre_commit_config_file_path,
        locked_packages=locked_packages,
        plugin_config=plugin_config,
    )

    pre_commit_repos = {PreCommitRepo("repo_url", "1.2.3")}
    syncer.mapping = {}

    result, _ = syncer.analyze_repos(pre_commit_repos)

    assert result == {}


def test_analyze_repos_dependency_not_locked() -> None:
    printer = MagicMock(spec=Printer)
    pre_commit_config_file_path = MagicMock(spec=Path)
    locked_packages: dict[str, GenericLockedPackage] = {}
    plugin_config = MagicMock(spec=SyncPreCommitLockConfig)

    syncer = SyncPreCommitHooksVersion(
        printer=printer,
        pre_commit_config_file_path=pre_commit_config_file_path,
        locked_packages=locked_packages,
        plugin_config=plugin_config,
    )

    pre_commit_repos = {PreCommitRepo("repo_url", "1.2.3")}
    syncer.mapping = {"lib-name": {"repo": "repo_url", "rev": "${rev}"}}

    result, _ = syncer.analyze_repos(pre_commit_repos)

    assert result == {}


def test_analyze_repos_no_new_version() -> None:
    printer = MagicMock(spec=Printer)
    pre_commit_config_file_path = MagicMock(spec=Path)
    locked_packages: dict[str, GenericLockedPackage] = {"lib-name": MagicMock(version="1.2.3")}
    plugin_config = MagicMock(spec=SyncPreCommitLockConfig)
    plugin_config.ignore = []

    syncer = SyncPreCommitHooksVersion(
        printer=printer,
        pre_commit_config_file_path=pre_commit_config_file_path,
        locked_packages=locked_packages,
        plugin_config=plugin_config,
    )

    pre_commit_repos = {PreCommitRepo("repo_url", "1.2.3")}
    syncer.mapping = {"lib-name": RepoInfo(repo="repo_url", rev="${rev}")}

    result, _ = syncer.analyze_repos(pre_commit_repos)

    assert result == {}


def test_analyze_repos_local() -> None:
    printer = MagicMock(spec=Printer)
    pre_commit_config_file_path = MagicMock(spec=Path)
    locked_packages: dict[str, GenericLockedPackage] = {"lib-name": MagicMock(version="0.1.1+dev")}
    plugin_config = MagicMock(spec=SyncPreCommitLockConfig)
    plugin_config.ignore = []

    syncer = SyncPreCommitHooksVersion(
        printer=printer,
        pre_commit_config_file_path=pre_commit_config_file_path,
        locked_packages=locked_packages,
        plugin_config=plugin_config,
    )

    pre_commit_repos = {PreCommitRepo("repo_url", "1.2.3")}
    syncer.mapping = {"lib-name": RepoInfo(repo="repo_url", rev="${rev}")}

    result, _ = syncer.analyze_repos(pre_commit_repos)

    assert result == {}


def test_analyze_repos_additional_dependencies() -> None:
    printer = MagicMock(spec=Printer)
    pre_commit_config_file_path = MagicMock(spec=Path)
    locked_packages: dict[str, GenericLockedPackage] = {"lib-name": GenericLockedPackage("lib-name", "2.0.0")}
    plugin_config = SyncPreCommitLockConfig()

    syncer = SyncPreCommitHooksVersion(
        printer=printer,
        pre_commit_config_file_path=pre_commit_config_file_path,
        locked_packages=locked_packages,
        plugin_config=plugin_config,
    )
    pre_commit_repo = PreCommitRepo("https://repo_url", "1.2.3", [PreCommitHook("hook", ["lib-name==1.2.2"])])
    pre_commit_repos = {pre_commit_repo}
    syncer.mapping = {"lib-name": {"repo": "https://repo_url", "rev": "${rev}"}}

    to_fix, _ = syncer.analyze_repos(pre_commit_repos)

    assert to_fix == {
        pre_commit_repo: PreCommitRepo("https://repo_url", "2.0.0", [PreCommitHook("hook", ["lib-name==2.0.0"])])
    }


def test_analyze_repos_not_in_lock_but_additional_dependencies() -> None:
    printer = MagicMock(spec=Printer)
    pre_commit_config_file_path = MagicMock(spec=Path)
    locked_packages: dict[str, GenericLockedPackage] = {"lib-name": GenericLockedPackage("lib-name", "2.0.0")}
    plugin_config = SyncPreCommitLockConfig()

    syncer = SyncPreCommitHooksVersion(
        printer=printer,
        pre_commit_config_file_path=pre_commit_config_file_path,
        locked_packages=locked_packages,
        plugin_config=plugin_config,
    )
    pre_commit_repo = PreCommitRepo("https://repo_url", "1.2.3", [PreCommitHook("hook", ["lib-name==1.2.2"])])
    pre_commit_repos = {pre_commit_repo}
    syncer.mapping = {"not_lib": {"repo": "https://repo_url", "rev": "${rev}"}}

    to_fix, _ = syncer.analyze_repos(pre_commit_repos)

    assert to_fix == {
        pre_commit_repo: PreCommitRepo("https://repo_url", "1.2.3", [PreCommitHook("hook", ["lib-name==2.0.0"])])
    }


def test_analyze_repos_local_but_additional_dependencies() -> None:
    printer = MagicMock(spec=Printer)
    pre_commit_config_file_path = MagicMock(spec=Path)
    locked_packages: dict[str, GenericLockedPackage] = {
        "lib-name": GenericLockedPackage("lib-name", "2.0.0"),
        "local_lib": GenericLockedPackage("local_lib", "1.0.0+dev"),
    }
    plugin_config = SyncPreCommitLockConfig()

    syncer = SyncPreCommitHooksVersion(
        printer=printer,
        pre_commit_config_file_path=pre_commit_config_file_path,
        locked_packages=locked_packages,
        plugin_config=plugin_config,
    )
    pre_commit_repo = PreCommitRepo("https://repo_url", "1.2.3", [PreCommitHook("hook", ["lib-name==1.2.2"])])
    pre_commit_repos = {pre_commit_repo}
    syncer.mapping = {"local_lib": {"repo": "https://repo_url", "rev": "${rev}"}}

    to_fix, _ = syncer.analyze_repos(pre_commit_repos)

    assert to_fix == {
        pre_commit_repo: PreCommitRepo("https://repo_url", "1.2.3", [PreCommitHook("hook", ["lib-name==2.0.0"])])
    }
