from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest
from pdm.cli.hooks import HookManager
from pdm.core import Core
from pdm.models.candidates import Candidate
from pdm.project import Project
from pdm.termui import UI
from sync_pre_commit_lock.config import SyncPreCommitLockConfig
from sync_pre_commit_lock.pdm_plugin import (
    PDMPrinter,
    PDMSetupPreCommitHooks,
)
from sync_pre_commit_lock.pre_commit_config import PreCommitRepo

# Create the mock objects


@pytest.fixture()
def project() -> Project:
    x = mock.MagicMock(spec=Project)
    x.root = mock.MagicMock(spec=Path)
    x.core = mock.MagicMock(spec=Core)
    x.core.ui = mock.MagicMock(spec=UI)
    return x


hooks_mock = mock.create_autospec(HookManager, instance=True)
candidates_mock = [mock.create_autospec(Candidate, instance=True)]
config_mock = mock.create_autospec(SyncPreCommitLockConfig, instance=True)
printer_mock = mock.create_autospec(PDMPrinter, instance=True)
action_mock = mock.create_autospec(PDMSetupPreCommitHooks, instance=True)


def test_on_pdm_install_setup_pre_commit_auto_install_disabled(project: mock.MagicMock) -> None:
    config_mock.automatically_install_hooks = False
    with (
        mock.patch("sync_pre_commit_lock.pdm_plugin.PDMPrinter", return_value=printer_mock),
        mock.patch("sync_pre_commit_lock.pdm_plugin.load_config", return_value=config_mock),
    ):
        from sync_pre_commit_lock.pdm_plugin import on_pdm_install_setup_pre_commit

        on_pdm_install_setup_pre_commit(project, hooks=hooks_mock, candidates=candidates_mock, dry_run=False)
    printer_mock.debug.assert_any_call("Automatically installing pre-commit hooks is disabled. Skipping.")


def test_on_pdm_install_setup_pre_commit_no_config_file(tmp_path: Path, project: Project) -> None:
    config_mock.automatically_install_hooks = True
    config_mock.pre_commit_config_file = SyncPreCommitLockConfig.pre_commit_config_file
    project.root = tmp_path
    with (
        mock.patch("sync_pre_commit_lock.pdm_plugin.PDMPrinter", return_value=printer_mock),
        mock.patch("sync_pre_commit_lock.pdm_plugin.load_config", return_value=config_mock),
    ):
        from sync_pre_commit_lock.pdm_plugin import on_pdm_install_setup_pre_commit

        on_pdm_install_setup_pre_commit(project, hooks=hooks_mock, candidates=candidates_mock, dry_run=False)
    printer_mock.info.assert_called_once_with("No pre-commit config file found, skipping pre-commit hook check")


def test_on_pdm_install_setup_pre_commit_success(project: Project) -> None:
    config_mock.automatically_install_hooks = True
    config_mock.pre_commit_config_file = SyncPreCommitLockConfig.pre_commit_config_file
    project.root = (
        Path(__file__).parent.parent / "fixtures" / "poetry_project"
    )  # Assuming config file exists at this path
    with (
        mock.patch("sync_pre_commit_lock.pdm_plugin.load_config", return_value=config_mock),
        mock.patch("sync_pre_commit_lock.pdm_plugin.PDMSetupPreCommitHooks", return_value=action_mock),
    ):
        from sync_pre_commit_lock.pdm_plugin import on_pdm_install_setup_pre_commit

        on_pdm_install_setup_pre_commit(project, hooks=hooks_mock, candidates=candidates_mock, dry_run=False)

    action_mock.execute.assert_called_once()


def test_pdm_printer_list_success(capsys: pytest.CaptureFixture[str]) -> None:
    from sync_pre_commit_lock.pdm_plugin import PDMPrinter

    printer = PDMPrinter(UI())

    printer.list_updated_packages(
        {
            "package1": (
                PreCommitRepo(repo="https://repo1.local/test", rev="rev1"),
                "rev2",
            )
        }
    )
    captured = capsys.readouterr()

    assert "[sync-pre-commit-lock]  ✔ https://repo1.local/test   rev1 -> rev2" in captured.out
