# Modified from https://github.com/vstrimaitis/poetry-pre-commit-plugin/blob/master/src/poetry_pre_commit_plugin/plugin.py
# Original code un GPLv3, written by Vytautas Strimaitis and contributors

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sync_pre_commit_lock import Printer


class SetupPreCommitHooks:
    install_pre_commit_hooks_command: ClassVar[Sequence[str | bytes]] = ["pre-commit", "install"]
    check_pre_commit_version_command: ClassVar[Sequence[str | bytes]] = ["pre-commit", "--version"]

    def __init__(self, printer: Printer, dry_run: bool = False) -> None:
        self.printer = printer
        self.dry_run = dry_run

    def execute(self) -> None:
        if not self._is_pre_commit_package_installed():
            self.printer.debug("pre-commit package is not installed (or detected). Skipping.")
            return

        git_root = self._get_git_directory_path()
        if git_root is None:
            self.printer.debug("Not in a git repository - can't install hooks. Skipping.")
            return

        if self._are_pre_commit_hooks_installed(git_root):
            self.printer.debug("pre-commit hooks already installed. Skipping.")
            return

        if self.dry_run is True:
            self.printer.debug("Dry run, skipping pre-commit hook installation.")
            return

        self._install_pre_commit_hooks()

    def _install_pre_commit_hooks(self) -> None:
        try:
            self.printer.info("Installing pre-commit hooks...")
            return_code = subprocess.check_call(
                self.install_pre_commit_hooks_command,
                # XXX We probably want to see the output, at least in verbose mode or if it fails
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if return_code == 0:
                self.printer.info("pre-commit hooks successfully installed!")
            else:
                self.printer.error("Failed to install pre-commit hooks")
        except Exception as e:
            self.printer.error("Failed to install pre-commit hooks due to an unexpected error")
            self.printer.error(f"{e}")

    def _is_pre_commit_package_installed(self) -> bool:
        try:
            # Try is `pre-commit --version` works
            output = subprocess.check_output(
                self.check_pre_commit_version_command,
            ).decode()
            return "pre-commit" in output
        except FileNotFoundError:
            return False

    @staticmethod
    def _are_pre_commit_hooks_installed(git_root: Path) -> bool:
        return (git_root / "hooks" / "pre-commit").exists()

    @staticmethod
    def _get_git_directory_path() -> Path | None:
        try:
            result = subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"],
            )
            return Path(result.decode().strip()) / ".git"
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
