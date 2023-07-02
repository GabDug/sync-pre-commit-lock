from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest
import yaml
from sync_pre_commit_lock.actions.sync_hooks import PreCommitHookConfig, PreCommitRepo


def test_pre_commit_hook_config_initialization() -> None:
    data = {"repos": [{"repo": "repo1", "rev": "rev1"}]}
    path = Path("dummy_path")
    config = PreCommitHookConfig(data, path, yaml.dump(data).splitlines())

    assert config.data == data
    assert config.pre_commit_config_file_path == path


def test_data_setter_raises_not_implemented_error() -> None:
    data = {"repos": [{"repo": "repo1", "rev": "rev1"}]}
    path = Path("dummy_path")
    config = PreCommitHookConfig(data, path, yaml.dump(data).splitlines())

    with pytest.raises(NotImplementedError):
        config.data = {"new": "data"}


@patch("sync_pre_commit_lock.actions.sync_hooks.yaml")
def test_from_yaml_file(mock_yaml: MagicMock) -> None:
    mock_yaml.safe_load.return_value = {"repos": [{"repo": "repo1", "rev": "rev1"}]}

    mock_path = MagicMock(spec=Path)
    mock_path.open = mock_open(read_data="dummy_stream")

    config = PreCommitHookConfig.from_yaml_file(mock_path)

    mock_path.open.assert_called_once_with("r")
    assert config.data == {"repos": [{"repo": "repo1", "rev": "rev1"}]}
    assert config.pre_commit_config_file_path == mock_path


@patch("sync_pre_commit_lock.actions.sync_hooks.yaml")
def test_from_yaml_file_invalid_not_dict(mock_yaml: MagicMock) -> None:
    mock_yaml.safe_load.return_value = ["not a dict"]

    mock_path = MagicMock(spec=Path)
    mock_path.open = mock_open(read_data="dummy_stream")

    with pytest.raises(ValueError, match="Expected a dict, got"):
        PreCommitHookConfig.from_yaml_file(mock_path)

    mock_path.open.assert_called_once_with("r")


@patch("sync_pre_commit_lock.actions.sync_hooks.yaml")
def test_from_yaml_file_invalid_repos_not_list(mock_yaml: MagicMock) -> None:
    mock_yaml.safe_load.return_value = {"repos": "not a list"}

    mock_path = MagicMock(spec=Path)
    mock_path.open = mock_open(read_data="dummy_stream")

    with pytest.raises(ValueError, match="Expected a list for `repos`, got"):
        PreCommitHookConfig.from_yaml_file(mock_path)

    mock_path.open.assert_called_once_with("r")


def test_repos_property() -> None:
    data = {"repos": [{"repo": "https://repo1.local:443/test", "rev": "rev1"}]}
    path = Path("dummy_path")
    config = PreCommitHookConfig(data, path, yaml.dump(data).splitlines())

    assert config.repos[0].repo == "https://repo1.local:443/test"
    assert config.repos[0].rev == "rev1"
    assert config.repos_normalized == {PreCommitRepo("https://repo1.local/test", "rev1")}


@patch("sync_pre_commit_lock.actions.sync_hooks.difflib")
@patch("sync_pre_commit_lock.actions.sync_hooks.re")
@patch("builtins.open", new_callable=mock_open)
def test_update_pre_commit_repo_versions(mock_open_file: MagicMock, mock_re: MagicMock, mock_diff: MagicMock) -> None:
    data = {"repos": [{"repo": "repo1", "rev": "rev1"}]}
    mock_path = MagicMock(spec=Path)
    original_file_lines = ["repos:\n", "  - repo: repo1\n", "    rev: rev1\n"]

    config = PreCommitHookConfig(data, mock_path, original_file_lines=original_file_lines)
    config.original_file_lines = original_file_lines  # setup original file lines
    new_versions = {PreCommitRepo("repo1", "rev1"): "rev2"}

    mock_re.sub.return_value = "    rev: rev2\n"
    mock_diff.ndiff.return_value = ["- rev: rev1", "+ rev: rev2"]

    config.update_pre_commit_repo_versions(new_versions)

    mock_open_file.assert_called_once_with(mock_path, "w")  # asserts the file is opened for writing
    mock_re.sub.assert_called_once_with(r"(?<=rev: )\S*", "rev2", "    rev: rev1\n")
    assert mock_diff.ndiff.called


@patch("sync_pre_commit_lock.actions.sync_hooks.difflib")
@patch("sync_pre_commit_lock.actions.sync_hooks.re")
@patch("builtins.open", new_callable=mock_open)
def test_update_pre_commit_repo_versions_no_change(
    mock_open_file: MagicMock, mock_re: MagicMock, mock_diff: MagicMock
) -> None:
    data = {"repos": [{"repo": "repo1", "rev": "rev1"}]}
    mock_path = MagicMock(spec=Path)
    original_file_lines = ["repos:\n", "  - repo: repo1\n", "    rev: rev1\n"]

    config = PreCommitHookConfig(data, mock_path, original_file_lines=original_file_lines)
    config.original_file_lines = original_file_lines  # setup original file lines
    new_versions = {PreCommitRepo("repo1", "rev1"): "rev1"}  # no change in version

    mock_re.sub.return_value = "    rev: rev1\n"
    mock_diff.ndiff.return_value = []  # return empty diff, indicating no changes

    config.update_pre_commit_repo_versions(new_versions)

    mock_open_file.assert_not_called()  # asserts the file is not opened for writing
    mock_re.sub.assert_called_once_with(r"(?<=rev: )\S*", "rev1", "    rev: rev1\n")
    assert mock_diff.ndiff.called


@patch("sync_pre_commit_lock.actions.sync_hooks.difflib")
@patch("sync_pre_commit_lock.actions.sync_hooks.re")
@patch("builtins.open", new_callable=mock_open)
def test_update_pre_commit_repo_versions_no_match(
    mock_open_file: MagicMock, mock_re: MagicMock, mock_diff: MagicMock
) -> None:
    data = {"repos": [{"repo": "repo1", "rev": "rev1"}]}
    mock_path = MagicMock(spec=Path)
    original_file_lines = ["repos:\n", "  - repo: repo1\n", "    rev: rev1\n"]

    config = PreCommitHookConfig(data, mock_path, original_file_lines=original_file_lines)
    config.original_file_lines = original_file_lines  # setup original file lines
    new_versions = {PreCommitRepo("repo2", "rev2"): "rev2"}  # no matching repo in new_versions

    mock_re.sub.return_value = "    rev: rev1\n"
    mock_diff.ndiff.return_value = []  # return empty diff, indicating no changes

    config.update_pre_commit_repo_versions(new_versions)

    mock_open_file.assert_not_called()  # asserts the file is not opened for writing
    mock_re.sub.assert_not_called()  # no substitution should have been attempted
