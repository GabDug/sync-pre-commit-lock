from __future__ import annotations

import difflib
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING, Any

import strictyaml
import strictyaml as yaml
from strictyaml import Any as AnyStrictYaml
from strictyaml import MapCombined, Optional, Seq, Str

from sync_pre_commit_lock.utils import normalize_git_url

if TYPE_CHECKING:
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


@dataclass
class PreCommitRepo:
    repo: str
    rev: str  # Check if is not loaded as float/int/other yolo
    hooks: list[dict[str, Any]] = field(default_factory=list)
    _changes: dict[tuple[str | int, ...], Any] = field(default_factory=dict)
    idx: int = -1

    def __hash__(self) -> int:
        return hash((self.repo, self.rev))


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
            PreCommitRepo(repo=repo["repo"], rev=repo["rev"], idx=idx, hooks=repo.get("hooks", []))
            for idx, repo in enumerate(self.data["repos"] or [])
            if "rev" in repo
        ]

    @cached_property
    def repos_normalized(self) -> set[PreCommitRepo]:
        return {PreCommitRepo(repo=normalize_git_url(repo.repo), rev=repo.rev, hooks=repo.hooks) for repo in self.repos}

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

    def update_pre_commit_repo_versions(
        self,
        new_versions: dict[PreCommitRepo, str],
        additional_changes: list[PreCommitRepo] | None = None,
    ) -> None:
        """Fix the pre-commit hooks to match the lockfile. Preserve comments and formatting as much as possible."""
        # all_changes = {**new_versions, **old}
        if additional_changes is None:
            additional_changes = []

        if len(new_versions) == 0 and len(additional_changes or []) == 0:
            return

        original_lines = self.original_file_lines
        updated_lines = original_lines[:]

        for repo_rev in self.yaml["repos"]:
            if "rev" not in repo_rev:
                continue

            repo, rev = repo_rev["repo"], repo_rev["rev"]
            normalized_repo = PreCommitRepo(normalize_git_url(str(repo)), str(rev))
            if normalized_repo not in new_versions:
                continue

            rev_line_number: int = rev.end_line + self.document_start_offset
            rev_line_idx: int = rev_line_number - 1
            original_rev_line: str = updated_lines[rev_line_idx]
            updated_lines[rev_line_idx] = original_rev_line.replace(str(rev), new_versions[normalized_repo])

        for repo_changes in additional_changes:
            if not repo_changes._changes or len(repo_changes._changes) == 0:
                continue

            for change_key, change_value in repo_changes._changes.items():
                print(change_key, change_value)
                # Change key is the full yaml path
                # Change value is the new value

                key_from_yaml = get_object_from_path(self.yaml, change_key)

                # breakpoint()
                val_line_number: int = key_from_yaml.end_line + self.document_start_offset
                val_line_idx: int = val_line_number - 1
                original_val_line: str = updated_lines[val_line_idx]
                updated_lines[val_line_idx] = original_val_line.replace(str(key_from_yaml), change_value)

        changes = difflib.ndiff(original_lines, updated_lines)
        change_count = sum(1 for change in changes if change[0] in ["+", "-"])

        if change_count == 0:
            msg = "No changes to write, this should not happen"
            raise RuntimeError(msg)

        # Check the file is valid yaml
        try:
            yaml.dirty_load(
                "".join(updated_lines),
                schema=schema,
                allow_flow_style=True,
            )
        except strictyaml.ruamel.parser.ParserError:
            raise ValueError(
                "Updated pre-commit config file is not valid YAML. You may want to tweak your quoting and report this."
            )
        with self.pre_commit_config_file_path.open("w") as stream:
            stream.writelines(updated_lines)


def get_object_from_path(obj: Mapping[int | str, Any], path: tuple[str | int, ...]) -> Any:
    """Get an object from a path string."""
    for key in path:
        obj = obj[key]
    return obj
