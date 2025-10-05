from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from unittest import mock

import pytest

pdm_module = pytest.importorskip("pdm")
# ruff: noqa: E402
from pdm.core import Core
from pdm.project import Project
from pdm.termui import UI

from sync_pre_commit_lock.config import SyncPreCommitLockConfig
from sync_pre_commit_lock.pdm_plugin import (
    PDMPrinter,
    PDMSetupPreCommitHooks,
)
from sync_pre_commit_lock.pre_commit_config import PreCommitHook, PreCommitRepo

# Create the mock objects


@pytest.fixture()
def project() -> Project:
    x = mock.MagicMock(spec=Project)
    x.root = mock.MagicMock(spec=Path)
    x.core = mock.MagicMock(spec=Core)
    x.core.ui = mock.MagicMock(spec=UI)
    return x


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

        on_pdm_install_setup_pre_commit(project, dry_run=False)
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

        on_pdm_install_setup_pre_commit(project, dry_run=False)
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

        on_pdm_install_setup_pre_commit(project, dry_run=False)

    action_mock.execute.assert_called_once()


def assert_output(out: str, expected: str):
    __tracebackhide__ = True

    # Invisible whitespace enfinf lines (table side effect)
    out = "\n".join(line.rstrip() for line in out.splitlines())

    assert out.strip() == dedent(expected).strip()


def test_pdm_printer_list_success(capsys: pytest.CaptureFixture[str]) -> None:
    printer = PDMPrinter(UI())

    printer.list_updated_packages(
        {
            "package": (
                PreCommitRepo("https://repo1.local/test", "rev1", [PreCommitHook("hook")]),
                PreCommitRepo("https://repo1.local/test", "rev2", [PreCommitHook("hook")]),
            )
        }
    )
    captured = capsys.readouterr()

    assert_output(captured.out, "[sync-pre-commit-lock]  ✔ https://repo1.local/test   rev1 -> rev2")


def test_pdm_printer_list_success_additional_dependency(capsys: pytest.CaptureFixture[str]) -> None:
    printer = PDMPrinter(UI())

    printer.list_updated_packages(
        {
            "package": (
                PreCommitRepo("https://repo1.local/test", "rev1", [PreCommitHook("hook", ["dep"])]),
                PreCommitRepo("https://repo1.local/test", "rev1", [PreCommitHook("hook", ["dep==0.1.2"])]),
            )
        }
    )
    captured = capsys.readouterr()

    expected = """
    [sync-pre-commit-lock]  ✔ https://repo1.local/test
    [sync-pre-commit-lock]    └ hook
    [sync-pre-commit-lock]      └ dep                    * -> 0.1.2
    """
    assert_output(captured.out, expected)


def test_pdm_printer_list_success_repo_with_multiple_hooks_and_additional_dependency(
    capsys: pytest.CaptureFixture[str],
) -> None:
    printer = PDMPrinter(UI())

    printer.list_updated_packages(
        {
            "package": (
                PreCommitRepo(
                    repo="https://repo1.local/test",
                    rev="rev1",
                    hooks=[
                        PreCommitHook("1st-hook", ["dep==0.1.2", "other==0.42"]),
                        PreCommitHook("2nd-hook", ["dep", "other>=0.42"]),
                    ],
                ),
                PreCommitRepo(
                    repo="https://repo1.local/test",
                    rev="rev2",
                    hooks=[
                        PreCommitHook("1st-hook", ["dep==0.1.2", "other==3.4.5"]),
                        PreCommitHook("2st-hook", ["dep==0.1.2", "other==3.4.5"]),
                    ],
                ),
            )
        }
    )
    captured = capsys.readouterr()

    expected = """
    [sync-pre-commit-lock]  ✔ https://repo1.local/test   rev1   -> rev2
    [sync-pre-commit-lock]    ├ 1st-hook
    [sync-pre-commit-lock]    │ └ other                  0.42   -> 3.4.5
    [sync-pre-commit-lock]    └ 2nd-hook
    [sync-pre-commit-lock]      ├ dep                    *      -> 0.1.2
    [sync-pre-commit-lock]      └ other                  >=0.42 -> 3.4.5
    """
    assert_output(captured.out, expected)


def test_pdm_printer_list_success_renamed_repository(capsys: pytest.CaptureFixture[str]) -> None:
    printer = PDMPrinter(UI())

    printer.list_updated_packages(
        {
            "package": (
                PreCommitRepo("https://old.repo.local/test", "rev1", [PreCommitHook("hook")]),
                PreCommitRepo("https://new.repo.local/test", "rev2", [PreCommitHook("hook")]),
            ),
        }
    )
    captured = capsys.readouterr()

    assert_output(captured.out, "[sync-pre-commit-lock]  ✔ https://{old -> new}.repo.local/test   rev1 -> rev2")
