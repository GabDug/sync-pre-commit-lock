import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest
from pytest_mock import MockerFixture

from sync_pre_commit_lock import Printer
from sync_pre_commit_lock.actions.install_hooks import SetupPreCommitHooks


class TestSetupPreCommitHooks:
    @pytest.fixture()
    def printer(self, mocker: MockerFixture) -> MagicMock:
        return mocker.MagicMock()

    @pytest.fixture()
    def mock_subprocess(self, mocker: MockerFixture) -> MagicMock:
        return mocker.patch("subprocess.check_output", autospec=True)

    @pytest.fixture()
    def mock_path_exists(self, mocker: MockerFixture) -> MagicMock:
        return mocker.patch.object(Path, "exists", autospec=True)

    def test_execute_pre_commit_not_installed(self, printer: Printer, mock_subprocess: MagicMock):
        mock_subprocess.return_value.decode.return_value = "fail"
        setup = SetupPreCommitHooks(printer, dry_run=False)
        setup._is_pre_commit_package_installed = MagicMock(return_value=False)
        setup.execute()
        assert printer.debug.call_count == 1
        assert printer.debug.call_args == call("pre-commit package is not installed (or detected). Skipping.")

    def test_execute_not_in_git_repo(self, printer: MagicMock, mocker: MockerFixture) -> None:
        mocker.patch(
            "subprocess.check_output", side_effect=subprocess.CalledProcessError(1, "git", b"error", b"output")
        )
        mocker.patch("subprocess.check_call", return_value=0)

        setup = SetupPreCommitHooks(printer, dry_run=False)
        setup._is_pre_commit_package_installed = MagicMock(return_value=True)
        setup.execute()
        assert printer.debug.call_count == 3
        assert printer.debug.call_args == call("Not in a git repository - can't install hooks. Skipping.")

    def test_execute_pre_commit_hooks_already_installed(
        self, printer, mock_subprocess, mock_path_exists, mocker
    ) -> None:
        mock_subprocess.return_value.decode.return_value = "pre-commit"
        mocker.patch("subprocess.check_output", return_value=b"git_path")
        mock_path_exists.return_value = True
        setup = SetupPreCommitHooks(printer, dry_run=False)
        # Mock _is_pre_commit_package_installed
        setup._is_pre_commit_package_installed = MagicMock(return_value=True)
        setup.execute()
        assert printer.debug.call_count == 1
        assert printer.debug.call_args == call("pre-commit hooks already installed. Skipping.")

    def test_execute_dry_run(self, printer, mock_subprocess, mock_path_exists, mocker) -> None:
        mock_subprocess.return_value.decode.return_value = "pre-commit"
        mocker.patch("subprocess.check_output", return_value=b"git_path")
        mock_path_exists.return_value = False
        setup = SetupPreCommitHooks(printer, dry_run=True)
        setup._is_pre_commit_package_installed = MagicMock(return_value=True)
        setup.execute()
        assert printer.debug.call_count == 1
        assert printer.debug.call_args == call("Dry run, skipping pre-commit hook installation.")

    def test_execute_install_hooks(self, printer, mock_subprocess, mock_path_exists, mocker) -> None:
        mock_subprocess.return_value.decode.return_value = "pre-commit"
        mocker.patch("subprocess.check_output", return_value=b"git_path")
        mock_path_exists.return_value = False
        mocker.patch("subprocess.check_call", return_value=0)
        setup = SetupPreCommitHooks(printer, dry_run=False)
        setup._is_pre_commit_package_installed = MagicMock(return_value=True)
        setup.execute()
        assert printer.info.call_count == 2
        printer.info.assert_has_calls(
            [call("Installing pre-commit hooks..."), call("pre-commit hooks successfully installed!")]
        )

    def test_install_pre_commit_hooks_success(self, printer, mocker) -> None:
        mocked_check_call = mocker.patch("subprocess.check_call", return_value=0)
        setup = SetupPreCommitHooks(printer, dry_run=False)
        setup._install_pre_commit_hooks()
        assert printer.info.call_count == 2
        printer.info.assert_has_calls(
            [call("Installing pre-commit hooks..."), call("pre-commit hooks successfully installed!")]
        )
        mocked_check_call.assert_called_once()

    def test_install_pre_commit_hooks_error(self, printer, mocker) -> None:
        mocked_check_call = mocker.patch("subprocess.check_call", side_effect=subprocess.CalledProcessError(1, "cmd"))
        setup = SetupPreCommitHooks(printer, dry_run=False)
        setup._install_pre_commit_hooks()
        assert printer.info.call_count == 1
        assert printer.error.call_count == 2
        printer.info.assert_has_calls([call("Installing pre-commit hooks...")])
        printer.error.assert_has_calls(
            [
                call("Failed to install pre-commit hooks due to an unexpected error"),
                call("Command 'cmd' returned non-zero exit status 1."),
            ]
        )
        mocked_check_call.assert_called_once()

    def test_is_pre_commit_package_installed_true(self, printer, mocker) -> None:
        mocked_check_output = mocker.patch("subprocess.check_output", return_value=b"pre-commit 2.9.3")
        setup = SetupPreCommitHooks(printer, dry_run=False)
        assert setup._is_pre_commit_package_installed() is True
        mocked_check_output.assert_called_once()

    def test_is_pre_commit_package_installed_error(self, printer, mocker) -> None:
        mocked_check_output = mocker.patch("subprocess.check_output", side_effect=FileNotFoundError())
        setup = SetupPreCommitHooks(printer, dry_run=False)
        assert setup._is_pre_commit_package_installed() is False
        mocked_check_output.assert_called_once()

    def test_install_pre_commit_hooks_non_zero_return_code(self, printer, mocker) -> None:
        mocked_check_call = mocker.patch("subprocess.check_call", return_value=1)
        setup = SetupPreCommitHooks(printer, dry_run=False)
        setup._install_pre_commit_hooks()
        assert printer.info.call_count == 1
        assert printer.error.call_count == 1
        printer.info.assert_has_calls([call("Installing pre-commit hooks...")])
        printer.error.assert_has_calls([call("Failed to install pre-commit hooks")])
        mocked_check_call.assert_called_once()
