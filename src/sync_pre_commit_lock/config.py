from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

try:
    # 3.11+
    import tomllib as toml  # type: ignore[import,unused-ignore]
except ImportError:
    import tomli as toml  # type: ignore[no-redef,unused-ignore]


if TYPE_CHECKING:
    from sync_pre_commit_lock.db import PackageRepoMapping

    pass


def from_toml(data: dict[str, Any]) -> SyncPreCommitLockConfig:
    fields = {f.metadata.get("toml", f.name): f for f in SyncPreCommitLockConfig.__dataclass_fields__.values()}
    # XXX We should warn about unknown fields
    return SyncPreCommitLockConfig(
        **{
            fields[name].name: (
                data[name]
                if isinstance(fields[name].type, type) and issubclass(fields[name].type, SyncPreCommitLockConfig)
                else data[name]
            )
            for name in data
            if name in fields
        }
    )


@dataclass
class SyncPreCommitLockConfig:
    automatically_install_hooks: bool = field(default=True, metadata={"toml": "automatically-install-hooks"})
    disable_sync_from_lock: bool = field(default=False, metadata={"toml": "disable-sync-from-lock"})
    ignore: list[str] = field(default_factory=list, metadata={"toml": "ignore"})
    pre_commit_config_file: str = field(metadata={"toml": "pre-commit-config-file"}, default=".pre-commit-config.yaml")
    dependency_mapping: PackageRepoMapping = field(default_factory=dict, metadata={"toml": "dependency-mapping"})


def load_config(path: Path | None = None) -> SyncPreCommitLockConfig:
    # XXX We should not hard-code this, and get the filename from PDM/Poetry/custom resolution
    path = path or Path("pyproject.toml")
    with path.open("rb") as file:
        config_dict = toml.load(file)

    tool_dict = config_dict.get("tool", {}).get("sync-pre-commit-lock", {})
    if not tool_dict or len(tool_dict) == 0:
        return SyncPreCommitLockConfig()

    return from_toml(tool_dict)
