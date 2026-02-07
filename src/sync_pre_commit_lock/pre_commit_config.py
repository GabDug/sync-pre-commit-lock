from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from functools import cached_property
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
    def document_start_offset(self) -> int:
        """Return the line number where the YAML document starts."""
        lines = self.raw_file_contents.split("\n")
        for i, line in enumerate(lines):
            # Trim leading/trailing whitespaces
            line = line.rstrip()
            # Skip if line is a comment or empty/whitespace
            if line.startswith("#") or line == "":
                continue
            # If line is '---', return line number + 1
            if line == "---":
                return i + 1
        return 0

    def update_pre_commit_repo_versions(self, new_versions: dict[PreCommitRepo, PreCommitRepo]) -> None:
        """Fix the pre-commit hooks to match the lockfile. Preserve comments and formatting as much as possible."""
        if len(new_versions) == 0:
            return

        original_lines = self.original_file_lines
        updated_lines = original_lines[:]

        repos_list = self.yaml["repos"]
        for repo_idx, repo_rev in enumerate(repos_list):
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

            rev_line_number: int = rev.end_line + self.document_start_offset
            rev_line_idx: int = rev_line_number - 1
            original_rev_line: str = updated_lines[rev_line_idx]
            updated_lines[rev_line_idx] = original_rev_line.replace(str(rev), updated_repo.rev)

            if repo_idx + 1 < len(repos_list):
                next_repo_start_line = repos_list[repo_idx + 1]["repo"].start_line + self.document_start_offset
                repo_end_idx = next_repo_start_line - 2
            else:
                repo_end_idx = len(updated_lines) - 1

            for src_hook, old_hook, new_hook in zip(hooks, normalized_repo.hooks, updated_repo.hooks):
                if new_hook == old_hook:
                    continue
                for src_dep, old_dep, new_dep in zip(
                    src_hook.get("additional_dependencies", []),
                    old_hook.additional_dependencies,
                    new_hook.additional_dependencies,
                ):
                    if old_dep == new_dep:
                        continue
                    dep_line_number: int = src_dep.end_line + self.document_start_offset
                    dep_line_idx: int = dep_line_number - 1
                    old_dep_str = str(old_dep)
                    if dep_line_idx >= len(updated_lines) or old_dep_str not in updated_lines[dep_line_idx]:
                        search_start = rev_line_idx
                        search_end = min(repo_end_idx + 1, len(updated_lines))
                        candidates = [
                            idx for idx in range(search_start, search_end) if old_dep_str in updated_lines[idx]
                        ]
                        if candidates:
                            dep_line_idx = min(candidates, key=lambda idx: abs(idx - dep_line_idx))
                    original_dep_line: str = updated_lines[dep_line_idx]
                    updated_lines[dep_line_idx] = original_dep_line.replace(str(src_dep), new_dep)

        changes = difflib.ndiff(original_lines, updated_lines)
        change_count = sum(1 for change in changes if change[0] in ["+", "-"])

        if change_count == 0:
            msg = "No changes to write, this should not happen"
            raise RuntimeError(msg)
        with self.pre_commit_config_file_path.open("w") as stream:
            stream.writelines(updated_lines)
