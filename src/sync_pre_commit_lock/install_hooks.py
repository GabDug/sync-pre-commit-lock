import subprocess
from pathlib import Path
from typing import Optional

from sync_pre_commit_lock import Printer


class SetupPreCommitHooks:
    def __init__(self, printer: Printer) -> None:
        self.printer = printer

    def setup_pre_commit_hooks_if_appropriate(self, dry_run: bool = False) -> None:
        if not self._is_pre_commit_package_installed():
            self.printer.debug("pre-commit package not installed")
            return

        git_root = self._get_git_directory_path()
        if git_root is None:
            # Not in a git repository - can't install hooks
            self.printer.debug("Not in a git repository - can't install hooks")
            return

        if self._are_pre_commit_hooks_installed(git_root):
            self.printer.debug("pre-commit hooks already installed. Skipping.")
            return

        if dry_run is True:
            self.printer.debug("Dry run, skipping pre-commit hook installation")
            return

        self._install_pre_commit_hooks()

    def _install_pre_commit_hooks(self) -> None:
        try:
            self.printer.info("Installing pre-commit hooks...")
            return_code = subprocess.check_call(
                ["pdm", "run", "pre-commit", "install"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if return_code == 0:
                self.printer.info("pre-commit hooks successfully installed!")
            else:
                self.printer.error("Failed to install pre-commit hooks")
        except Exception as e:
            self.printer.error("Failed to install pre-commit hooks due to an unexpected error")
            self.printer.error(f"<error>{e}</>")

    def _is_pre_commit_package_installed(self) -> bool:
        try:
            # Try is `pre-commmit --version` works
            output = subprocess.check_output(
                ["pdm", "run", "pre-commit", "--version"],
            ).decode()
            return "pre-commit" in output
        except FileNotFoundError:
            return False

    def _are_pre_commit_hooks_installed(self, git_root: Path) -> bool:
        if git_root is None:
            return False
        return (git_root / "hooks" / "pre-commit").exists()

    def _get_git_directory_path(self) -> Optional[Path]:
        try:
            result = subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"],
            )
            return Path(result.decode().strip()) / ".git"
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
