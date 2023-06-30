from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pdm.core import Core
from pdm.models.candidates import Candidate
from pdm.models.requirements import NamedRequirement
from pdm.project import Project
from pdm.termui import UI, Verbosity
from sync_pre_commit_lock import (
    PreCommitRepo,
    SyncPreCommitLockConfig,
    build_mapping,
    fix_pre_commit,
    on_pdm_lock_check_pre_commit,
    register_pdm_plugin,
    resolve_file_path,
)


@pytest.fixture
def project():
    x = MagicMock(spec=Project)
    x.root = MagicMock(spec=Path)
    x.core = MagicMock(spec=Core)
    x.core.ui = MagicMock(spec=UI)
    return x


def test_register_pdm_plugin():
    core = MagicMock(spec=Core)
    register_pdm_plugin(core)
    # As function has no implementation currently, nothing to assert


def test_resolve_file_path(project: MagicMock):
    project.root.joinpath.return_value = Path("/path/to/project/test.py")
    file_path = resolve_file_path(project, "test.py")
    assert str(file_path) == "/path/to/project/test.py"
    project.root.joinpath.assert_called_once_with("test.py")


@patch("sync_pre_commit_lock.load_config")
def test_on_pdm_lock_check_pre_commit(mock_load_config: MagicMock, project: MagicMock):
    mock_load_config.return_value = SyncPreCommitLockConfig(disable=True)
    resolution = {
        "some-library": Candidate(NamedRequirement("some-library"), "1.0.0", "https://example.com/some-library")
    }
    on_pdm_lock_check_pre_commit(project, dry_run=False, resolution=resolution)
    mock_load_config.assert_called_once()
    project.core.ui.echo.assert_called_once_with("Sync pre-commit lock is disabled", verbosity=Verbosity.DEBUG)


@patch("sync_pre_commit_lock.load_config")
def test_on_pdm_lock_check_pre_commit_dry_run(mock_load_config: MagicMock, project: MagicMock):
    mock_load_config.return_value = SyncPreCommitLockConfig(disable=False)
    resolution = {
        "some-library": Candidate(NamedRequirement("some-library"), "1.0.0", "https://example.com/some-library")
    }
    on_pdm_lock_check_pre_commit(project, dry_run=True, resolution=resolution)
    mock_load_config.assert_called_once()


@patch("sync_pre_commit_lock.yaml.safe_load")
@patch("builtins.open", new_callable=MagicMock)
def test_fix_pre_commit(mock_open: MagicMock, mock_load: MagicMock, project: MagicMock):
    mock_load.return_value = {"repos": [{"repo": "repo-1", "rev": "1.0.0"}, {"repo": "repo-2", "rev": "2.0.0"}]}
    to_fix = {PreCommitRepo("repo-1", "1.0.0"): "1.0.1"}
    mock_open.return_value.__enter__.return_value.readlines.return_value = [
        "repos:\n",
        "  - repo: repo-1\n",
        "    rev: 1.0.0\n",
        "  - repo: repo-2\n",
        "    rev: 2.0.0\n",
    ]
    fix_pre_commit(project, to_fix, Path("/path/to/project/.pre-commit-config.yaml"))
    mock_open.assert_called_with(Path("/path/to/project/.pre-commit-config.yaml"), "w")
    mock_load.assert_called_once()
    project.core.ui.echo.assert_called_once_with("Pre-commit hooks have been updated to match the lockfile!")


def test_build_mapping():
    config = SyncPreCommitLockConfig()
    mapping, mapping_reverse_by_url = build_mapping(config)
    # assert correct structure of mapping and mapping_reverse_by_url based on DEPENDENCY_MAPPING
