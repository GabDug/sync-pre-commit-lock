"""
Generic shell utilities.
"""

from __future__ import annotations

import os
import sys
from enum import IntEnum, auto
from typing import TYPE_CHECKING, TextIO

from packaging.requirements import Requirement

from sync_pre_commit_lock import Printer
from sync_pre_commit_lock.utils import url_diff

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from sync_pre_commit_lock.pre_commit_config import PreCommitHook, PreCommitRepo


def use_color() -> bool:
    """
    Determine if we should use color in the terminal output.
    Follows the NO_COLOR and FORCE_COLOR conventions.
    See:
    - https://no-color.org/
    - https://force-color.org/
    """
    no_color = os.getenv("NO_COLOR") is not None
    force_color = os.getenv("FORCE_COLOR") is not None
    return not no_color and (sys.stdout.isatty() or force_color)


# Compute once
USE_COLOR = use_color()


def _color(escape: str) -> str:
    return escape if USE_COLOR else ""


class Colors:
    """
    ANSI color codes for terminal output
    """

    BLUE = _color("\033[94m")
    GREEN = _color("\033[92m")
    YELLOW = _color("\033[93m")
    RED = _color("\033[91m")
    PURPLE = _color("\033[95m")
    CYAN = _color("\033[96m")
    BOLD = _color("\033[1m")
    UNDERLINE = _color("\033[4m")
    END = _color("\033[0m")


class Verbosity(IntEnum):
    QUIET = auto()
    NORMAL = auto()
    DEBUG = auto()


def style(*colors: str) -> Callable[[str], str]:
    prefix = "".join(colors)

    def helper(msg: str) -> str:
        return f"{prefix}{msg}{Colors.END}"

    return helper


debug = style(Colors.PURPLE)
cyan = style(Colors.CYAN)
info = style(Colors.CYAN)
bold = style(Colors.BOLD)
success = style(Colors.GREEN, Colors.BOLD)
warning = style(Colors.YELLOW)
error = style(Colors.RED, Colors.BOLD)


class ShellPrinter(Printer):
    success_list_token: str = f"{Colors.GREEN}✔{Colors.END}"

    """
    A printer that outputs messages to the shell with color coding.
    """

    def __init__(self, with_prefix: bool = True, verbosity: Verbosity = Verbosity.NORMAL) -> None:
        self.plugin_prefix = "[sync-pre-commit-lock]" if with_prefix else ""
        self.verbosity = verbosity

    def with_prefix(self, msg: str) -> str:
        if not self.plugin_prefix:
            return msg
        return "\n".join(f"{self.plugin_prefix} {line}" for line in msg.split("\n"))

    def print(self, msg: str, verbosity: Verbosity = Verbosity.NORMAL, out: TextIO | None = None) -> None:
        if self.verbosity >= verbosity:
            # Bind late due to https://github.com/pytest-dev/pytest/issues/5997
            (out or sys.stdout).write(f"{msg}\n")

    def debug(self, msg: str) -> None:
        self.print(debug(self.with_prefix(msg)), Verbosity.DEBUG)

    def info(self, msg: str) -> None:
        self.print(info(self.with_prefix(msg)))

    def success(self, msg: str) -> None:
        self.print(success(self.with_prefix(msg)))

    def warning(self, msg: str) -> None:
        self.print(warning(self.with_prefix(msg)))

    def error(self, msg: str) -> None:
        self.print(error(self.with_prefix(msg)), Verbosity.QUIET, out=sys.stderr)

    def list_updated_packages(self, packages: dict[str, tuple[PreCommitRepo, PreCommitRepo]]) -> None:
        for package, (old, new) in packages.items():
            for row in self._format_repo(package, old, new):
                line = " ".join(row).rstrip()
                if self.plugin_prefix:
                    line = f"{info(self.plugin_prefix)} {line}"
                self.print(line)

    def _format_repo_url(self, old_repo_url: str, new_repo_url: str, package_name: str) -> str:
        url = url_diff(
            old_repo_url,
            new_repo_url,
            f"{cyan('{')}{Colors.RED}",
            f"{Colors.END}{cyan(' -> ')}{Colors.GREEN}",
            f"{Colors.END}{cyan('}')}",
        )
        return url.replace(package_name, cyan(bold(package_name)))

    def _format_repo(self, package: str, old: PreCommitRepo, new: PreCommitRepo) -> Sequence[Sequence[str]]:
        new_version = new.rev != old.rev
        repo = (
            self.success_list_token,
            self._format_repo_url(old.repo, new.repo, package),
            "\t",
            error(old.rev) if new_version else "",
            info("->") if new_version else "",
            success(new.rev) if new_version else "",
        )
        nb_hooks = len(old.hooks)
        hooks = [
            row
            for idx, (old_hook, new_hook) in enumerate(zip(old.hooks, new.hooks))
            for row in self._format_hook(old_hook, new_hook, idx + 1 == nb_hooks)
        ]
        return [repo, *hooks] if hooks else [repo]

    def _format_hook(self, old: PreCommitHook, new: PreCommitHook, last: bool) -> Sequence[Sequence[str]]:
        if not len(old.additional_dependencies):
            return []
        hook = (
            f"  {'└' if last else '├'} {cyan(bold(old.id))}",
            "",
            "",
            "",
        )
        pairs = [
            (old_dep, new_dep)
            for old_dep, new_dep in zip(old.additional_dependencies, new.additional_dependencies)
            if old_dep != new_dep
        ]

        dependencies = [
            self._format_additional_dependency(old_dep, new_dep, " " if last else "│", idx + 1 == len(pairs))
            for idx, (old_dep, new_dep) in enumerate(pairs)
        ]
        return (hook, *dependencies)

    def _format_additional_dependency(self, old: str, new: str, prefix: str, last: bool) -> Sequence[str]:
        old_req = Requirement(old)
        new_req = Requirement(new)
        return (
            f"  {prefix} {'└' if last else '├'} {cyan(bold(old_req.name))}",
            "\t",
            error(str(old_req.specifier).lstrip("==") or "*"),
            info("->"),
            success(str(new_req.specifier).lstrip("==")),
        )
