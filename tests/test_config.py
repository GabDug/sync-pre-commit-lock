from unittest.mock import MagicMock, patch

import pytest

from sync_pre_commit_lock.config import SyncPreCommitLockConfig, from_toml, load_config, update_from_env
from sync_pre_commit_lock.db import RepoInfo


def test_from_toml() -> None:
    data = {
        "disable-sync-from-lock": True,
        "ignore": ["a", "b"],
        "pre-commit-config-file": ".test-config.yaml",
        "dependency-mapping": {"pytest": {"repo": "pytest", "rev": "${ver}"}},
    }
    expected_config = SyncPreCommitLockConfig(
        disable_sync_from_lock=True,
        ignore=["a", "b"],
        pre_commit_config_file=".test-config.yaml",
        dependency_mapping={"pytest": RepoInfo(repo="pytest", rev="${ver}")},
    )

    actual_config = from_toml(data)

    assert actual_config == expected_config


def test_update_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYNC_PRE_COMMIT_LOCK_DISABLED", "1")
    monkeypatch.setenv("SYNC_PRE_COMMIT_LOCK_INSTALL", "false")
    monkeypatch.setenv("SYNC_PRE_COMMIT_LOCK_IGNORE", "a, b")
    monkeypatch.setenv("SYNC_PRE_COMMIT_LOCK_PRE_COMMIT_FILE", ".test-config.yaml")
    expected_config = SyncPreCommitLockConfig(
        automatically_install_hooks=False,
        disable_sync_from_lock=True,
        ignore=["a", "b"],
        pre_commit_config_file=".test-config.yaml",
        dependency_mapping={},
    )

    actual_config = update_from_env(SyncPreCommitLockConfig())

    assert actual_config == expected_config


def test_sync_pre_commit_lock_config() -> None:
    config = SyncPreCommitLockConfig(
        disable_sync_from_lock=True,
        ignore=["a", "b"],
        pre_commit_config_file=".test-config.yaml",
        dependency_mapping={"pytest": RepoInfo(repo="pytest", rev="${ver}")},
    )

    assert config.disable_sync_from_lock is True
    assert config.ignore == ["a", "b"]
    assert config.pre_commit_config_file == ".test-config.yaml"
    assert config.dependency_mapping == {"pytest": {"repo": "pytest", "rev": "${ver}"}}


@patch("sync_pre_commit_lock.config.toml.load", return_value={"tool": {"sync-pre-commit-lock": {}}})
@patch("builtins.open", new_callable=MagicMock)
def test_load_config_with_empty_tool_dict(mock_open: MagicMock, mock_load: MagicMock) -> None:
    expected_config = SyncPreCommitLockConfig()
    mock_path = MagicMock()
    mock_path.open = mock_open(read_data="dummy_stream")
    actual_config = load_config(mock_path)

    assert actual_config == expected_config
    mock_path.open.assert_called_once_with("rb")
    mock_load.assert_called_once()


@patch("sync_pre_commit_lock.config.toml.load", return_value={"tool": {"sync-pre-commit-lock": {"disable": True}}})
@patch("builtins.open", new_callable=MagicMock)
@patch("sync_pre_commit_lock.config.from_toml", return_value=SyncPreCommitLockConfig(disable_sync_from_lock=True))
def test_load_config_with_data(mock_from_toml: MagicMock, mock_open: MagicMock, mock_load: MagicMock) -> None:
    expected_config = SyncPreCommitLockConfig(disable_sync_from_lock=True)
    mock_path = MagicMock()
    mock_path.open = mock_open(read_data="dummy_stream")
    actual_config = load_config(mock_path)

    assert actual_config == expected_config
    mock_path.open.assert_called_once_with("rb")
    mock_load.assert_called_once()
    mock_from_toml.assert_called_once_with({"disable": True})


@patch("sync_pre_commit_lock.config.toml.load", return_value={"tool": {"sync-pre-commit-lock": {"ignore": ["fake"]}}})
@patch("builtins.open", new_callable=MagicMock)
def test_env_override_config(mock_open: MagicMock, mock_load: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYNC_PRE_COMMIT_LOCK_DISABLED", "true")
    monkeypatch.setenv("SYNC_PRE_COMMIT_LOCK_IGNORE", "a, b")
    expected_config = SyncPreCommitLockConfig(
        disable_sync_from_lock=True,
        ignore=["a", "b"],
    )
    mock_path = MagicMock()
    mock_path.open = mock_open(read_data="dummy_stream")
    actual_config = load_config(mock_path)

    assert actual_config == expected_config
    mock_path.open.assert_called_once_with("rb")
