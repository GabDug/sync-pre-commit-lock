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


FIXTURES = Path(__file__).parent / "fixtures" / "sample_pre_commit_config"


@pytest.mark.parametrize(
    ("path", "offset"),
    [
        (FIXTURES / "pre-commit-config-document-separator.yaml", 4),
        (FIXTURES / "pre-commit-config-start-empty-lines.yaml", 0),
        (FIXTURES / "pre-commit-config-with-local.yaml", 2),
        (FIXTURES / "pre-commit-config.yaml", 1),
        (FIXTURES / "sample-django-stubs.yaml", 0),
    ],
)
def test_files_offset(path: Path, offset: int) -> None:
    config = PreCommitHookConfig.from_yaml_file(path)
    assert config.document_start_offset == offset


def test_update_versions():
    config = PreCommitHookConfig.from_yaml_file(FIXTURES / "pre-commit-config-document-separator.yaml")
    config.pre_commit_config_file_path = MagicMock()

    config.update_pre_commit_repo_versions({PreCommitRepo("https://github.com/psf/black", "23.2.0"): "23.3.0"})
    # Assert open was called with "w" mode
    assert config.pre_commit_config_file_path.open.call_args[0][0] == "w"
