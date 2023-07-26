from pathlib import Path
from unittest.mock import MagicMock, mock_open

import pytest
import yaml
from strictyaml.exceptions import YAMLValidationError
from sync_pre_commit_lock.pre_commit_config import PreCommitHookConfig, PreCommitRepo


def test_pre_commit_hook_config_initialization() -> None:
    data = {"repos": [{"repo": "repo1", "rev": "rev1"}]}
    path = Path("dummy_path")
    config = PreCommitHookConfig(yaml.dump(data), path)

    assert config.data == data
    assert config.pre_commit_config_file_path == path


def test_from_yaml_file() -> None:
    file_data = "repos:\n- repo: repo1\n  rev: rev1\n"
    mock_path = MagicMock(spec=Path)
    mock_path.open = mock_open(read_data=file_data)

    config = PreCommitHookConfig.from_yaml_file(mock_path)

    mock_path.open.assert_called_once_with("r")
    assert config.data == {"repos": [{"repo": "repo1", "rev": "rev1"}]}
    assert config.pre_commit_config_file_path == mock_path
    assert config.original_file_lines == file_data.splitlines(keepends=True)


def test_from_yaml_file_invalid() -> None:
    mock_path = MagicMock(spec=Path)
    mock_path.open = mock_open(read_data="dummy_stream")

    with pytest.raises(YAMLValidationError, match="when expecting a mapping"):
        PreCommitHookConfig.from_yaml_file(mock_path)

    mock_path.open.assert_called_once_with("r")


def test_repos_property() -> None:
    data = {"repos": [{"repo": "https://repo1.local:443/test", "rev": "rev1"}]}
    path = Path("dummy_path")
    config = PreCommitHookConfig(yaml.dump(data), path)

    assert config.repos[0].repo == "https://repo1.local:443/test"
    assert config.repos[0].rev == "rev1"
    assert config.repos_normalized == {PreCommitRepo("https://repo1.local/test", "rev1")}
