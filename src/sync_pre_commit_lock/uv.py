from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ._compat import toml
from .actions.sync_hooks import GenericLockedPackage, SyncPreCommitHooksVersion
from .config import load_config
from .shell import ShellPrinter, Verbosity, cyan


def load_lock(path: Path | None = None) -> dict[str, GenericLockedPackage]:
    path = path or Path("uv.lock")
    with path.open("rb") as file:
        lock = toml.load(file)

    packages: dict[str, GenericLockedPackage] = {}

    for package in lock.get("package", []):
        name = package.get("name")
        version = package.get("version")
        if name and version:
            packages[name] = GenericLockedPackage(name=name, version=version)

    return packages


def sync_pre_commit() -> None:
    parser = argparse.ArgumentParser(
        description=f"Sync {cyan('.pre-commit-config.yaml')} hooks versions with {cyan('uv.lock')}"
    )
    parser.add_argument("--dry-run", action="store_true", help="Show the difference only and don't perform any action")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed output")
    parser.add_argument("-q", "--quiet", action="store_true", help="Hide all output except errors")

    args = parser.parse_args(sys.argv[1:])

    lock_data = load_lock()
    verbosity = Verbosity.DEBUG if args.verbose else Verbosity.QUIET if args.quiet else Verbosity.NORMAL
    printer = ShellPrinter(with_prefix=False, verbosity=verbosity)
    config = load_config()
    file_path = Path().cwd() / config.pre_commit_config_file
    SyncPreCommitHooksVersion(
        printer=printer,
        pre_commit_config_file_path=file_path,
        locked_packages=lock_data,
        plugin_config=config,
        dry_run=args.dry_run,
    ).execute()
