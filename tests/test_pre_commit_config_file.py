import builtins
from pathlib import Path
from unittest.mock import MagicMock, mock_open

import pytest
import yaml
from strictyaml.exceptions import YAMLValidationError

from sync_pre_commit_lock.pre_commit_config import (
    PreCommitHook,
    PreCommitHookConfig,
    PreCommitRepo,
    _round_trip_load,
)


def test_pre_commit_hook_config_initialization() -> None:
    data = {"repos": [{"repo": "repo1", "rev": "rev1"}]}
    path = Path("dummy_path")
    config = PreCommitHookConfig(yaml.dump(data), path)

    assert config.data == data
    assert config.pre_commit_config_file_path == path


def test_from_yaml_file() -> None:
    file_data = "repos:\n- repo: repo1\n  rev: rev1\n"
    mock_path = MagicMock(spec=Path)
    mock_path.open = mock_open(read_data=file_data)

    config = PreCommitHookConfig.from_yaml_file(mock_path)

    mock_path.open.assert_called_once_with("r")
    assert config.data == {"repos": [{"repo": "repo1", "rev": "rev1"}]}
    assert config.pre_commit_config_file_path == mock_path
    assert config.original_file_lines == file_data.splitlines(keepends=True)


def test_from_yaml_file_invalid() -> None:
    mock_path = MagicMock(spec=Path)
    mock_path.open = mock_open(read_data="dummy_stream")

    with pytest.raises(YAMLValidationError, match="when expecting a mapping"):
        PreCommitHookConfig.from_yaml_file(mock_path)

    mock_path.open.assert_called_once_with("r")


def test_repos_property() -> None:
    data = {"repos": [{"repo": "https://repo1.local:443/test", "rev": "rev1"}]}
    path = Path("dummy_path")
    config = PreCommitHookConfig(yaml.dump(data), path)

    assert config.repos[0].repo == "https://repo1.local:443/test"
    assert config.repos[0].rev == "rev1"
    assert config.repos_normalized == {PreCommitRepo("https://repo1.local/test", "rev1")}


FIXTURES = Path(__file__).parent / "fixtures" / "sample_pre_commit_config"


def test_update_versions() -> None:
    config = PreCommitHookConfig.from_yaml_file(FIXTURES / "pre-commit-config-document-separator.yaml")
    config.pre_commit_config_file_path = MagicMock()

    initial_repo = PreCommitRepo("https://github.com/psf/black", "23.2.0", [PreCommitHook("black")])
    updated_repo = PreCommitRepo("https://github.com/psf/black", "23.3.0", [PreCommitHook("black")])
    config.update_pre_commit_repo_versions({initial_repo: updated_repo})
    assert config.pre_commit_config_file_path.open.call_args[0][0] == "w"

    config.update_pre_commit_repo_versions({})
    assert config.pre_commit_config_file_path.open.call_count == 1

    with pytest.raises(RuntimeError):
        config.update_pre_commit_repo_versions(
            {PreCommitRepo("https://github.com/psf/notexist", "23.2.0"): updated_repo}
        )
        assert config.pre_commit_config_file_path.open.call_count == 1


@pytest.mark.parametrize(
    "name",
    [
        "pre-commit-config.yaml",
        "pre-commit-config-document-separator.yaml",
        "pre-commit-config-start-empty-lines.yaml",
        "pre-commit-config-with-local.yaml",
        "sample-django-stubs.yaml",
    ],
)
def test_update_versions_rewrites_only_the_rev(name: str) -> None:
    """Whatever precedes the rev -- blank lines, comments, a `---` separator, a local repo
    with no rev -- the bump must land on that rev and change nothing else (#64).
    """
    path = FIXTURES / name
    config = PreCommitHookConfig.from_yaml_file(path)
    mock_file = config.pre_commit_config_file_path = MagicMock()
    mock_file.open = mock_open()

    initial_repo = config.repos[0]
    config.update_pre_commit_repo_versions(
        {initial_repo: PreCommitRepo(initial_repo.repo, "99.99.99", initial_repo.hooks)}
    )

    written = "".join(mock_file.open().writelines.call_args[0][0])
    assert "99.99.99" in written
    assert written.replace("99.99.99", initial_repo.rev) == path.read_text()


def test_round_trip_load_explains_itself_without_a_ruamel_parser(monkeypatch: pytest.MonkeyPatch) -> None:
    """strictyaml vendors ruamel today; if a future one stops, say what to install."""
    real_import = builtins.__import__

    def no_ruamel(name: str, *args: object, **kwargs: object) -> object:
        if name in {"strictyaml.ruamel", "ruamel.yaml"}:
            raise ImportError(name)
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", no_ruamel)

    with pytest.raises(RuntimeError, match="Install ruamel.yaml"):
        _round_trip_load("repos: []")


def test_update_deps_sharing_a_line_when_the_first_one_shrinks() -> None:
    """A shorter replacement shifts every column after it on that line, so edits must be
    applied rightmost-first or the later dependency is silently left untouched.
    """
    file_content = """\
repos:
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.0.0
    hooks:
      - id: mypy
        additional_dependencies: [types-PyYAML==6.0.12.20240311, types-requests==2.31.0]
"""
    mock_path = MagicMock(spec=Path)
    mock_path.open = mock_open(read_data=file_content)
    config = PreCommitHookConfig.from_yaml_file(mock_path)

    initial_repo = config.repos[0]
    mock_path.open = mock_open()
    config.update_pre_commit_repo_versions(
        {
            initial_repo: PreCommitRepo(
                initial_repo.repo,
                initial_repo.rev,
                [PreCommitHook("mypy", ["types-PyYAML==6.0.12", "types-requests==2.32.0"])],
            )
        }
    )

    written = "".join(mock_path.open().writelines.call_args[0][0])
    assert "additional_dependencies: [types-PyYAML==6.0.12, types-requests==2.32.0]" in written


@pytest.mark.parametrize(
    "base", ["only-deps", "with-deps", "with-one-liner-deps", "without-new-deps", "flow-multiline-deps"]
)
def test_update_additional_dependencies_versions(base: str) -> None:
    config = PreCommitHookConfig.from_yaml_file(FIXTURES / f"pre-commit-config-{base}.yaml")
    mock_file = config.pre_commit_config_file_path = MagicMock()
    mock_file.open = mock_open()

    initial_repo = next(repo for repo in config.repos if repo.repo.endswith("/mirrors-mypy"))
    updated_repo = PreCommitRepo(
        "https://github.com/pre-commit/mirrors-mypy",
        "v1.5.0",
        [PreCommitHook("mypy", ["types-PyYAML==1.2.4", "types-requests==3.4.5"])],
    )

    config.update_pre_commit_repo_versions({initial_repo: updated_repo})

    expected = (FIXTURES / f"pre-commit-config-{base}.expected.yaml").read_text()

    mock_file.open().writelines.assert_called_once_with(expected.splitlines(keepends=True))


# Syntactic sugar
Repo = PreCommitRepo
Hook = PreCommitHook


@pytest.mark.parametrize(
    "repo1,repo2,equal",
    (
        (Repo("https://some.url", "0.42"), Repo("https://some.url", "0.42"), True),
        (Repo("https://some.url", "0.42", tuple()), Repo("https://some.url", "0.42", []), True),
        (
            Repo("https://some.url", "0.42", [Hook("hook")]),
            Repo("https://some.url", "0.42", [Hook("hook")]),
            True,
        ),
        (
            Repo("https://some.url", "0.42", [Hook("hook", ["somelib"])]),
            Repo("https://some.url", "0.42", [Hook("hook", ["somelib"])]),
            True,
        ),
        (
            Repo("https://some.url", "0.42", [Hook("hook", ("somelib",))]),
            Repo("https://some.url", "0.42", [Hook("hook", ["somelib"])]),
            True,
        ),
        (
            Repo(
                "https://some.url",
                "0.42",
                [
                    Hook("1st-hook", ["somelib"]),
                    Hook("2nd-hook", ["somelib", "another-lib"]),
                ],
            ),
            Repo(
                "https://some.url",
                "0.42",
                [
                    Hook("1st-hook", ["somelib"]),
                    Hook("2nd-hook", ["somelib", "another-lib"]),
                ],
            ),
            True,
        ),
        (
            Repo("https://some.url", "0.42"),
            Repo("https://some.new.url", "0.42"),
            False,
        ),
        (
            Repo("https://some.url", "0.42"),
            Repo("https://some.url", "0.43"),
            False,
        ),
        (
            Repo("https://some.url", "0.42", [Hook("hook", ["somelib==0.1"])]),
            Repo("https://some.url", "0.42", [Hook("hook", ["somelib"])]),
            False,
        ),
        (
            Repo(
                "https://some.url",
                "0.42",
                [
                    Hook("1st-hook", ["somelib"]),
                    Hook("2nd-hook", ["somelib", "another-lib"]),
                ],
            ),
            Repo(
                "https://some.url",
                "0.42",
                [
                    Hook("1st-hook", ["somelib"]),
                    Hook("2nd-hook", ["somelib==0.42", "another-lib"]),
                ],
            ),
            False,
        ),
    ),
)
def test_precommit_repo_equality(repo1: PreCommitRepo, repo2: PreCommitRepo, equal: bool):
    assert (repo1 == repo2) is equal
    assert (hash(repo1) == hash(repo2)) is equal


def test_prek_config_support() -> None:
    # A config file with prek-specific keys
    file_content = """\
minimum_prek_version: "0.1.0"
orphan: true
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
        priority: 10
        env:
            FOO: bar
"""
    mock_path = MagicMock(spec=Path)
    mock_path.open = mock_open(read_data=file_content)

    config = PreCommitHookConfig.from_yaml_file(mock_path)

    updated_repo = PreCommitRepo(
        "https://github.com/psf/black",
        "23.4.0",
        [PreCommitHook("black")],
    )

    mock_path.open = mock_open()
    config.update_pre_commit_repo_versions({config.repos[0]: updated_repo})

    expected_content = """\
minimum_prek_version: "0.1.0"
orphan: true
repos:
  - repo: https://github.com/psf/black
    rev: 23.4.0
    hooks:
      - id: black
        priority: 10
        env:
            FOO: bar
"""
    mock_path.open().writelines.assert_called_once_with(expected_content.splitlines(keepends=True))
