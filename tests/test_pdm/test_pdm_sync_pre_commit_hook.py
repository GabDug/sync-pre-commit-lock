from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pdm.core import Core
from pdm.models.candidates import Candidate
from pdm.models.requirements import NamedRequirement
from pdm.project import Project
from pdm.termui import UI
from sync_pre_commit_lock import (
    Printer,
)
from sync_pre_commit_lock.config import SyncPreCommitLockConfig
from sync_pre_commit_lock.pdm_plugin import on_pdm_lock_check_pre_commit, register_pdm_plugin


@pytest.fixture()
def project() -> Project:
    x = MagicMock(spec=Project)
    x.root = MagicMock(spec=Path)
    x.core = MagicMock(spec=Core)
    x.core.ui = MagicMock(spec=UI)
    return x


@pytest.fixture()
def printer() -> Printer:
    x = MagicMock(spec=Printer)
    x.debug = MagicMock()
    x.info = MagicMock()
    x.warning = MagicMock()
    x.error = MagicMock()
    return x


def test_register_pdm_plugin(project: Project) -> None:
    core = project.core
    register_pdm_plugin(core)
    # As function has no implementation currently, nothing to assert
    assert core.ui.echo.call_count == 1


@patch("sync_pre_commit_lock.pdm_plugin.load_config")
def test_on_pdm_lock_check_pre_commit(mock_load_config: MagicMock, project: MagicMock) -> None:
    mock_load_config.return_value = SyncPreCommitLockConfig(disable_sync_from_lock=True)
    resolution = {
        "some-library": Candidate(NamedRequirement("some-library"), "1.0.0", "https://example.com/some-library")
    }
    on_pdm_lock_check_pre_commit(project, dry_run=False, resolution=resolution)
    mock_load_config.assert_called_once()


@patch("sync_pre_commit_lock.pdm_plugin.load_config")
def test_on_pdm_lock_check_pre_commit_dry_run(mock_load_config: MagicMock, project: MagicMock) -> None:
    mock_load_config.return_value = SyncPreCommitLockConfig(disable_sync_from_lock=False)
    resolution = {
        "some-library": Candidate(NamedRequirement("some-library"), "1.0.0", "https://example.com/some-library")
    }
    on_pdm_lock_check_pre_commit(project, dry_run=True, resolution=resolution)
    mock_load_config.assert_called_once()
