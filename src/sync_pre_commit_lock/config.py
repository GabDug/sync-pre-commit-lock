from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, TypedDict

try:
    # 3.11+
    import tomllib as toml  # type: ignore[import,unused-ignore]
except ImportError:
    import tomli as toml  # type: ignore[no-redef,unused-ignore]


if TYPE_CHECKING:
    from sync_pre_commit_lock.db import PackageRepoMapping

    pass

ENV_PREFIX = "SYNC_PRE_COMMIT_LOCK"


def env_as_bool(value: str) -> bool:
    return (value or "False").lower() in ("true", "1")


def env_as_list(value: str) -> list[str]:
    return [v.strip() for v in (value or "").split(",")]


def from_toml(data: dict[str, Any]) -> SyncPreCommitLockConfig:
    if len(data) == 0:
        return SyncPreCommitLockConfig()

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


def update_from_env(config: SyncPreCommitLockConfig) -> SyncPreCommitLockConfig:
    vars = {
        f.metadata["env"]: f for f in SyncPreCommitLockConfig.__dataclass_fields__.values() if f.metadata.get("env")
    }
    for var, specs in vars.items():
        if value := os.getenv(f"{ENV_PREFIX}_{var}"):
            caster = specs.metadata.get("cast", lambda v: v)
            setattr(config, specs.name, caster(value))
    return config


class Metadata(TypedDict, total=False):
    """Configuration metadata known fields"""

    toml: str
    """Map the `toml` field"""
    env: str
    """Optionnaly map the environment variable suffix"""
    cast: Callable[[str], Any]
    """Optionnaly provide a cast function for environment variable"""


@dataclass
class SyncPreCommitLockConfig:
    automatically_install_hooks: bool = field(
        default=True,
        metadata=Metadata(toml="automatically-install-hooks", env="INSTALL", cast=env_as_bool),
    )
    disable_sync_from_lock: bool = field(
        default=False,
        metadata=Metadata(toml="disable-sync-from-lock", env="DISABLED", cast=env_as_bool),
    )
    ignore: list[str] = field(
        default_factory=list,
        metadata=Metadata(toml="ignore", env="IGNORE", cast=env_as_list),
    )
    pre_commit_config_file: str = field(
        default=".pre-commit-config.yaml",
        metadata=Metadata(toml="pre-commit-config-file", env="PRE_COMMIT_FILE"),
    )
    dependency_mapping: PackageRepoMapping = field(
        default_factory=dict,
        metadata=Metadata(toml="dependency-mapping"),
    )


def load_config(path: Path | None = None) -> SyncPreCommitLockConfig:
    """
    Load the configuration from pyproject.toml file, and then from environment variables.

    Args:
        path (Path | None): The path to the pyproject.toml file. If None, defaults to "pyproject.toml". Best if provided by PDM or Poetry.

    Returns:
        SyncPreCommitLockConfig: The loaded configuration.
    """
    path = path or Path("pyproject.toml")
    with path.open("rb") as file:
        config_dict = toml.load(file)

    tool_dict: dict[str, Any] = config_dict.get("tool", {}).get("sync-pre-commit-lock", {})

    return update_from_env(from_toml(tool_dict))
