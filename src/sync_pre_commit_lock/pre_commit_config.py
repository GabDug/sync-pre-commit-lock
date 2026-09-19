from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from importlib.metadata import version
from typing import TYPE_CHECKING, Any

import strictyaml as yaml
from strictyaml import Any as AnyStrictYaml
from strictyaml import MapCombined, Optional, Seq, Str

from sync_pre_commit_lock.utils import normalize_git_url

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

schema = MapCombined(
    {
        Optional("repos"): Seq(
            MapCombined(
                {
                    "repo": Str(),
                    Optional("rev"): Str(),
                    Optional("hooks"): Seq(
                        MapCombined(
                            {
                                "id": Str(),
                                Optional("additional_dependencies"): Seq(Str()),
                            },
                            Str(),
                            AnyStrictYaml(),
                        )
                    ),
                },
                Str(),
                AnyStrictYaml(),
            ),
        )
    },
    Str(),
    AnyStrictYaml(),
)


def _round_trip_load(raw: str) -> Any:
    """Parse ``raw`` with a ruamel round-trip loader, whose nodes carry ``lc`` source marks.

    strictyaml vendors ruamel, so this normally costs no extra dependency. A strictyaml
    that stops vendoring it still works if ruamel.yaml is installed on its own.
    """
    try:
        from strictyaml.ruamel import YAML  # type: ignore[import-untyped]
    except ImportError:
        try:
            from ruamel.yaml import YAML  # type: ignore[import-not-found]
        except ImportError as exc:
            msg = (
                "Updating .pre-commit-config.yaml needs a ruamel round-trip parser, which"
                f" strictyaml {version('strictyaml')} does not vendor. Install ruamel.yaml,"
                " or pin strictyaml<2."
            )
            raise RuntimeError(msg) from exc
    return YAML().load(raw)


@dataclass(frozen=True)
class PreCommitHook:
    id: str
    additional_dependencies: Sequence[str] = field(default_factory=tuple)

    def __hash__(self) -> int:
        return hash((self.id, *self.additional_dependencies))

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, PreCommitHook)
            and other.id == self.id
            and all(
                other_dep == self_dep
                for other_dep, self_dep in zip(other.additional_dependencies, self.additional_dependencies)
            )
        )


@dataclass(frozen=True)
class PreCommitRepo:
    repo: str
    rev: str  # Check if is not loaded as float/int/other yolo
    hooks: Sequence[PreCommitHook] = field(default_factory=tuple)

    def __hash__(self) -> int:
        return hash((self.repo, self.rev, *[hook.__hash__() for hook in self.hooks]))

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, PreCommitRepo)
            and other.repo == self.repo
            and other.rev == self.rev
            and all(other_hook == self_hook for other_hook, self_hook in zip(other.hooks, self.hooks))
        )


class PreCommitHookConfig:
    def __init__(
        self,
        raw_file_contents: str,
        pre_commit_config_file_path: Path,
    ) -> None:
        self.raw_file_contents = raw_file_contents
        self.yaml = yaml.dirty_load(
            raw_file_contents, schema=schema, allow_flow_style=True, label=str(pre_commit_config_file_path)
        )

        self.pre_commit_config_file_path = pre_commit_config_file_path

    @cached_property
    def original_file_lines(self) -> list[str]:
        return self.raw_file_contents.splitlines(keepends=True)

    @property
    def data(self) -> Any:
        return self.yaml.data

    @classmethod
    def from_yaml_file(cls, file_path: Path) -> PreCommitHookConfig:
        with file_path.open("r") as stream:
            file_contents = stream.read()

        return PreCommitHookConfig(file_contents, file_path)

    @cached_property
    def repos(self) -> list[PreCommitRepo]:
        """Return the repos, excluding local repos."""
        return [
            PreCommitRepo(
                repo=repo["repo"],
                rev=repo["rev"],
                hooks=tuple(
                    PreCommitHook(hook["id"], hook.get("additional_dependencies", tuple()))
                    for hook in repo.get("hooks", tuple())
                ),
            )
            for repo in (self.data["repos"] or [])
            if "rev" in repo
        ]

    @cached_property
    def repos_normalized(self) -> set[PreCommitRepo]:
        return {
            PreCommitRepo(
                repo=normalize_git_url(repo.repo),
                rev=repo.rev,
                hooks=repo.hooks,
            )
            for repo in self.repos
        }

    @cached_property
    def repo_marks(self) -> Any:
        """Exact source positions for each repo entry, from a ruamel round-trip parse.

        strictyaml's own ``end_line`` counts logical nodes, so it drifts past any
        multi-line flow sequence (see #64). ruamel's ``lc`` marks come from the lexer
        and stay exact, document separator and comments included.
        """
        return _round_trip_load(self.raw_file_contents)["repos"]

    def update_pre_commit_repo_versions(self, new_versions: dict[PreCommitRepo, PreCommitRepo]) -> None:
        """Fix the pre-commit hooks to match the lockfile. Preserve comments and formatting as much as possible."""
        if len(new_versions) == 0:
            return

        edits: list[tuple[int, int, str, str]] = []

        for repo_rev, marks in zip(self.yaml["repos"], self.repo_marks):
            if "rev" not in repo_rev:
                continue

            repo, rev, hooks = repo_rev["repo"], repo_rev["rev"], repo_rev.get("hooks", tuple())
            normalized_repo = PreCommitRepo(
                normalize_git_url(str(repo)),
                str(rev),
                tuple(
                    PreCommitHook(str(hook["id"]), [str(dep) for dep in hook.get("additional_dependencies", tuple())])
                    for hook in hooks
                ),
            )
            if not (updated_repo := new_versions.get(normalized_repo)):
                continue

            if str(rev) != updated_repo.rev:
                _, _, rev_line, rev_col = marks.lc.data["rev"]
                edits.append((rev_line, rev_col, str(rev), updated_repo.rev))

            for hook_marks, old_hook, new_hook in zip(
                marks.get("hooks", ()), normalized_repo.hooks, updated_repo.hooks
            ):
                if new_hook == old_hook:
                    continue
                for i, (old_dep, new_dep) in enumerate(
                    zip(old_hook.additional_dependencies, new_hook.additional_dependencies)
                ):
                    if old_dep == new_dep:
                        continue
                    dep_line, dep_col = hook_marks["additional_dependencies"].lc.data[i]
                    edits.append((dep_line, dep_col, old_dep, new_dep))

        if not edits:
            msg = "No changes to write, this should not happen"
            raise RuntimeError(msg)

        updated_lines = self.original_file_lines[:]
        # Rightmost edit first: replacing an earlier scalar on the same line would shift
        # every column after it, and those columns were measured against the original text.
        for line_idx, col, old, new in sorted(edits, reverse=True):
            line = updated_lines[line_idx]
            if old not in line[col:]:
                msg = f"Expected {old!r} at line {line_idx + 1}, column {col + 1}, found {line[col:].rstrip()!r}"
                raise RuntimeError(msg)
            updated_lines[line_idx] = line[:col] + line[col:].replace(old, new, 1)

        with self.pre_commit_config_file_path.open("w") as stream:
            stream.writelines(updated_lines)
