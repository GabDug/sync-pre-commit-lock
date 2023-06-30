from unittest.mock import MagicMock, patch

from sync_pre_commit_lock.config import SyncPreCommitLockConfig, from_toml, load_config


# @patch('sync_pre_commit_lock.config.SyncPreCommitLockConfig.__dataclass_fields__', new_callable=MagicMock)
def test_from_toml():
    data = {
        "disable": True,
        "ignore": ["a", "b"],
        "pre-commit-config-file": ".test-config.yaml",
        "dependency-mapping": {"pytest": "4.6.1"},
    }
    expected_config = SyncPreCommitLockConfig(
        disable=True,
        ignore=["a", "b"],
        pre_commit_config_file=".test-config.yaml",
        dependency_mapping={"pytest": "4.6.1"},
    )

    # mock_fields.values.return_value = data
    actual_config = from_toml(data)

    assert actual_config == expected_config
    # mock_fields.values.assert_called_once()


def test_sync_pre_commit_lock_config():
    config = SyncPreCommitLockConfig(
        disable=True,
        ignore=["a", "b"],
        pre_commit_config_file=".test-config.yaml",
        dependency_mapping={"pytest": "4.6.1"},
    )

    assert config.disable is True
    assert config.ignore == ["a", "b"]
    assert config.pre_commit_config_file == ".test-config.yaml"
    assert config.dependency_mapping == {"pytest": "4.6.1"}


@patch("sync_pre_commit_lock.config.toml.load", return_value={"tool": {"sync-pre-commit-lock": {}}})
@patch("builtins.open", new_callable=MagicMock)
def test_load_config_with_empty_tool_dict(mock_open, mock_load):
    expected_config = SyncPreCommitLockConfig()

    actual_config = load_config()

    assert actual_config == expected_config
    mock_open.assert_called_once_with("pyproject.toml", "rb")
    mock_load.assert_called_once()


@patch("sync_pre_commit_lock.config.toml.load", return_value={"tool": {"sync-pre-commit-lock": {"disable": True}}})
@patch("builtins.open", new_callable=MagicMock)
@patch("sync_pre_commit_lock.config.from_toml", return_value=SyncPreCommitLockConfig(disable=True))
def test_load_config_with_data(mock_from_toml, mock_open, mock_load):
    expected_config = SyncPreCommitLockConfig(disable=True)

    actual_config = load_config()

    assert actual_config == expected_config
    mock_open.assert_called_once_with("pyproject.toml", "rb")
    mock_load.assert_called_once()
    mock_from_toml.assert_called_once_with({"disable": True})
