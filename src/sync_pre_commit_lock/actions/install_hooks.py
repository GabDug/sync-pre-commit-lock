# Modified from https://github.com/vstrimaitis/poetry-pre-commit-plugin/blob/master/src/poetry_pre_commit_plugin/plugin.py
# Original code under GPLv3, written by Vytautas Strimaitis and contributors

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from sync_pre_commit_lock.config import HookRunner

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sync_pre_commit_lock import Printer


class ResolvedHookRunner:
    """A resolved hook runner, bound to a concrete runner (never AUTO) and a command prefix."""

    # Probe order for auto-detection: try prek first, then pre-commit
    _AUTO_ORDER: ClassVar[tuple[HookRunner, ...]] = (HookRunner.PREK, HookRunner.PRE_COMMIT)

    def __init__(self, runner: HookRunner, command_prefix: Sequence[str] = ()) -> None:
        self.runner = runner
        self.command_prefix = command_prefix

    @property
    def name(self) -> str:
        return self.runner.value

    def execute(self, *args: str) -> Sequence[str | bytes]:
        return [*self.command_prefix, self.runner.value, *args]

    def is_installed(self) -> bool:
        """Check if this runner is installed by running its --version command."""
        try:
            output = subprocess.check_output(self.execute("--version")).decode()  # noqa: S603
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
        else:
            return self.runner.value in output

    @classmethod
    def resolve(
        cls,
        hook_runner: HookRunner,
        command_prefix: Sequence[str] = (),
        printer: Printer | None = None,
    ) -> ResolvedHookRunner | None:
        """Resolve a HookRunner config to a concrete ResolvedHookRunner, or None if not found."""
        candidates = cls._AUTO_ORDER if hook_runner is HookRunner.AUTO else [hook_runner]
        for candidate in candidates:
            runner = cls(candidate, command_prefix)
            if runner.is_installed():
                if hook_runner is HookRunner.AUTO and printer:
                    printer.debug(f"Auto-detected hook runner: {candidate.value}")
                return runner
        return None


class SetupPreCommitHooks:
    command_prefix: ClassVar[Sequence[str]] = ()

    def __init__(
        self,
        printer: Printer,
        dry_run: bool = False,
        hook_runner: HookRunner = HookRunner.PRE_COMMIT,
    ) -> None:
        self.printer = printer
        self.dry_run = dry_run
        self.hook_runner = hook_runner

    def execute(self) -> None:
        runner = ResolvedHookRunner.resolve(self.hook_runner, self.command_prefix, self.printer)
        if runner is None:
            self.printer.debug("No hook runner (pre-commit or prek) is installed (or detected). Skipping.")
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

        self._install_hooks(runner)

    def _install_hooks(self, runner: ResolvedHookRunner) -> None:
        try:
            self.printer.info(f"Installing {runner.name} hooks...")
            return_code = subprocess.check_call(  # noqa: S603
                runner.execute("install"),
                # XXX We probably want to see the output, at least in verbose mode or if it fails
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if return_code == 0:
                self.printer.info(f"{runner.name} hooks successfully installed!")
            else:
                self.printer.error(f"Failed to install {runner.name} hooks")
        except Exception as e:
            self.printer.error(f"Failed to install {runner.name} hooks due to an unexpected error")
            self.printer.error(f"{e}")

    @staticmethod
    def _are_pre_commit_hooks_installed(git_root: Path) -> bool:
        return (git_root / "hooks" / "pre-commit").exists()

    def _get_git_directory_path(self) -> Path | None:
        try:
            result = subprocess.check_output(  # noqa: S603
                ["git", "rev-parse", "--show-toplevel"],  # noqa: S607
                stderr=subprocess.PIPE,
            )
            return Path(result.decode().strip()) / ".git"
        except subprocess.CalledProcessError as exc:
            self.printer.debug("Failed to get git root directory.")
            self.printer.debug(f"Git command stderr: {exc.stderr.decode()}")
            return None
        except FileNotFoundError:
            return None
