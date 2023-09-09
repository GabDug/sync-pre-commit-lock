from pathlib import Path
from unittest.mock import MagicMock, patch

from sync_pre_commit_lock import Printer
from sync_pre_commit_lock.actions.sync_hooks import (
    GenericLockedPackage,
    SyncPreCommitHooksVersion,
)
from sync_pre_commit_lock.config import SyncPreCommitLockConfig
from sync_pre_commit_lock.db import PackageRepoMapping, RepoInfo
from sync_pre_commit_lock.pre_commit_config import PreCommitHookConfig, PreCommitRepo


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
@patch.object(SyncPreCommitHooksVersion, "build_mapping")
@patch.object(SyncPreCommitHooksVersion, "analyze_repos")
def test_execute_returns_early_during_dry_run(
    mock_analyze_repos: MagicMock, mock_build_mapping: MagicMock, mock_from_yaml_file: MagicMock
) -> None:
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
    mock_build_mapping.return_value = ({}, {"repo1": "somepkg"})
    mock_analyze_repos.return_value = {PreCommitRepo("repo1", "rev1"): "rev2"}, {}

    syncer.execute()

    # Assertions
    mock_build_mapping.assert_called_once()
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
@patch.object(SyncPreCommitHooksVersion, "build_mapping")
@patch.object(SyncPreCommitHooksVersion, "analyze_repos")
def test_execute_synchronizes_hooks(
    mock_analyze_repos: MagicMock, mock_build_mapping: MagicMock, mock_from_yaml_file: MagicMock
) -> None:
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
    mock_build_mapping.return_value = ({}, {"repo1": "somepkg"})
    mock_analyze_repos.return_value = {PreCommitRepo("repo1", "rev1"): "rev2"}, {}

    syncer.execute()

    # Assertions
    mock_build_mapping.assert_called_once()
    mock_analyze_repos.assert_called_once()
    pre_commit_config.update_pre_commit_repo_versions.assert_called_once_with({PreCommitRepo("repo1", "rev1"): "rev2"})
    printer.success.assert_called_with("Pre-commit hooks have been updated in .pre-commit-config.yaml!")


@patch("sync_pre_commit_lock.pre_commit_config.PreCommitHookConfig.from_yaml_file")
@patch.object(SyncPreCommitHooksVersion, "build_mapping")
@patch.object(SyncPreCommitHooksVersion, "analyze_repos")
def test_execute_synchronizes_hooks_no_match(
    mock_analyze_repos: MagicMock, mock_build_mapping: MagicMock, mock_from_yaml_file: MagicMock
) -> None:
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

    # Mocks
    pre_commit_config = MagicMock(spec=PreCommitHookConfig)
    mock_from_yaml_file.return_value = pre_commit_config
    mock_build_mapping.return_value = ({}, {})
    mock_analyze_repos.return_value = {}, {}

    syncer.execute()

    # Assertions
    mock_build_mapping.assert_called_once()
    mock_analyze_repos.assert_called_once()
    pre_commit_config.update_pre_commit_repo_versions.assert_not_called()
    printer.info.assert_called_with("No pre-commit hook detected that matches a locked package.")


def test_get_pre_commit_repo_new_version() -> None:
    printer = MagicMock(spec=Printer)
    pre_commit_config_file_path = MagicMock(spec=Path)
    locked_packages: dict[str, GenericLockedPackage] = {"lib_name": GenericLockedPackage("lib_name", "2.0.0")}
    plugin_config = MagicMock(spec=SyncPreCommitLockConfig)
    plugin_config.ignore = []
    syncer = SyncPreCommitHooksVersion(
        printer=printer,
        pre_commit_config_file_path=pre_commit_config_file_path,
        locked_packages=locked_packages,
        plugin_config=plugin_config,
    )
    pre_commit_config_repo = PreCommitRepo("repo_url", "1.2.3")
    mapping_db_repo_info: RepoInfo = {"repo": "repo_url", "rev": "${rev}"}

    new_version = syncer.get_pre_commit_repo_new_version(
        pre_commit_config_repo, mapping_db_repo_info, locked_packages["lib_name"]
    )

    assert new_version == "2.0.0"


@patch.object(SyncPreCommitHooksVersion, "get_pre_commit_repo_new_version")
def test_analyze_repos(mock_get_pre_commit_repo_new_version: MagicMock) -> None:
    printer = MagicMock(spec=Printer)
    pre_commit_config_file_path = MagicMock(spec=Path)
    locked_packages: dict[str, GenericLockedPackage] = {"lib_name": GenericLockedPackage("lib_name", "2.0.0")}
    plugin_config = MagicMock(spec=SyncPreCommitLockConfig)

    syncer = SyncPreCommitHooksVersion(
        printer=printer,
        pre_commit_config_file_path=pre_commit_config_file_path,
        locked_packages=locked_packages,
        plugin_config=plugin_config,
    )
    mock_get_pre_commit_repo_new_version.return_value = "2.0.0"
    pre_commit_repos = {PreCommitRepo("https://repo_url", "1.2.3")}
    mapping: PackageRepoMapping = {"lib_name": {"repo": "https://repo_url", "rev": "${rev}"}}
    mapping_reverse_by_url = {"https://repo_url": "lib_name"}

    to_fix, _ = syncer.analyze_repos(pre_commit_repos, mapping, mapping_reverse_by_url)

    assert to_fix == {PreCommitRepo("https://repo_url", "1.2.3"): "2.0.0"}


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

    mapping, mapping_reverse_by_url = syncer.build_mapping()

    assert "new_lib" in mapping
    assert mapping["new_lib"]["repo"] == "new_repo_url"
    assert "new_repo_url" in mapping_reverse_by_url
    assert mapping_reverse_by_url["new_repo_url"] == "new_lib"


def test_get_pre_commit_repo_new_version_ignored() -> None:
    printer = MagicMock(spec=Printer)
    pre_commit_config_file_path = MagicMock(spec=Path)
    locked_packages: dict[str, GenericLockedPackage] = {}
    plugin_config = MagicMock(spec=SyncPreCommitLockConfig)
    plugin_config.ignore = ["lib_name"]

    syncer = SyncPreCommitHooksVersion(
        printer=printer,
        pre_commit_config_file_path=pre_commit_config_file_path,
        locked_packages=locked_packages,
        plugin_config=plugin_config,
    )

    pre_commit_config_repo = PreCommitRepo("repo_url", "1.2.3")
    mapping_db_repo_info = RepoInfo(repo="repo_url", rev="${rev}")
    locked_package = GenericLockedPackage("lib_name", "2.0.0")

    new_version = syncer.get_pre_commit_repo_new_version(pre_commit_config_repo, mapping_db_repo_info, locked_package)

    assert new_version is None


def test_get_pre_commit_repo_new_version_version_match() -> None:
    printer = MagicMock(spec=Printer)
    pre_commit_config_file_path = MagicMock(spec=Path)
    locked_packages: dict[str, GenericLockedPackage] = {}
    plugin_config = MagicMock(spec=SyncPreCommitLockConfig)
    plugin_config.ignore = []

    syncer = SyncPreCommitHooksVersion(
        printer=printer,
        pre_commit_config_file_path=pre_commit_config_file_path,
        locked_packages=locked_packages,
        plugin_config=plugin_config,
    )

    pre_commit_config_repo = PreCommitRepo("repo_url", "1.2.3")
    mapping_db_repo_info = RepoInfo(repo="repo_url", rev="${rev}")
    locked_package = GenericLockedPackage("lib_name", "1.2.3")

    new_version = syncer.get_pre_commit_repo_new_version(pre_commit_config_repo, mapping_db_repo_info, locked_package)

    assert new_version is None


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
    mapping: PackageRepoMapping = {}
    mapping_reverse_by_url: dict[str, str] = {}

    result, _ = syncer.analyze_repos(pre_commit_repos, mapping, mapping_reverse_by_url)

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
    mapping: PackageRepoMapping = {"lib_name": {"repo": "repo_url", "rev": "${rev}"}}
    mapping_reverse_by_url = {"repo_url": "lib_name"}

    result, _ = syncer.analyze_repos(pre_commit_repos, mapping, mapping_reverse_by_url)

    assert result == {}


def test_analyze_repos_no_new_version() -> None:
    printer = MagicMock(spec=Printer)
    pre_commit_config_file_path = MagicMock(spec=Path)
    locked_packages: dict[str, GenericLockedPackage] = {"lib_name": MagicMock(version="1.2.3")}
    plugin_config = MagicMock(spec=SyncPreCommitLockConfig)
    plugin_config.ignore = []

    syncer = SyncPreCommitHooksVersion(
        printer=printer,
        pre_commit_config_file_path=pre_commit_config_file_path,
        locked_packages=locked_packages,
        plugin_config=plugin_config,
    )

    pre_commit_repos = {PreCommitRepo("repo_url", "1.2.3")}
    mapping = {"lib_name": RepoInfo(repo="repo_url", rev="${rev}")}
    mapping_reverse_by_url = {"repo_url": "lib_name"}

    result, _ = syncer.analyze_repos(pre_commit_repos, mapping, mapping_reverse_by_url)

    assert result == {}
