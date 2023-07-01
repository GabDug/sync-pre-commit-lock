from __future__ import annotations

import tomllib as toml
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeVar

_T = TypeVar("_T")


if TYPE_CHECKING:
    from sync_pre_commit_lock.db import DependencyMapping


def from_toml(data: dict[str, Any]) -> SyncPreCommitLockConfig:
    fields = {f.metadata.get("toml", f.name): f for f in SyncPreCommitLockConfig.__dataclass_fields__.values()}

    # XXX Warn if unknown fields
    for name in data:
        if name not in fields:
            raise ValueError(f"Unknown field in sync-pre-commit-lock: {name}")

    return SyncPreCommitLockConfig(
        **{
            fields[name].name: (
                data[name]
                if isinstance(fields[name].type, type) and issubclass(fields[name].type, SyncPreCommitLockConfig)
                else data[name]
            )
            for name in data
        }
    )


@dataclass
class SyncPreCommitLockConfig:
    automatically_install_hooks: bool = field(default=True, metadata={"toml": "automatically-install-hooks"})
    disable_sync_from_lock: bool = field(default=False, metadata={"toml": "disable-sync-from-lock"})
    ignore: list[str] = field(default_factory=list, metadata={"toml": "ignore"})
    pre_commit_config_file: str = field(metadata={"toml": "pre-commit-config-file"}, default=".pre-commit-config.yaml")
    dependency_mapping: dict[str, DependencyMapping] = field(
        default_factory=dict, metadata={"toml": "dependency-mapping"}
    )


def load_config() -> SyncPreCommitLockConfig:
    with open("pyproject.toml", "rb") as file:
        config_dict = toml.load(
            file,
        )

    tool_dict = config_dict.get("tool", {}).get("sync-pre-commit-lock", {})
    if not tool_dict or len(tool_dict) == 0:
        return SyncPreCommitLockConfig()

    sync_pre_commit_lock = from_toml(tool_dict)
    return sync_pre_commit_lock
