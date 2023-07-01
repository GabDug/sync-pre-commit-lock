from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest
from pdm.core import Core
from pdm.models.candidates import Candidate
from pdm.models.requirements import NamedRequirement
from pdm.project import Project
from pdm.termui import UI, Verbosity
from sync_pre_commit_lock import (
    PreCommitRepo,
    analyze_repos,
    build_mapping,
    build_pre_commit_repos,
    check_and_log_dependency,
    fix_pre_commit,
    handle_fixes,
    load_pre_commit_data,
    on_pdm_lock_check_pre_commit,
    print_to_fix_repos,
    register_pdm_plugin,
    resolve_file_path,
)
from sync_pre_commit_lock.config import SyncPreCommitLockConfig
from sync_pre_commit_lock.db import DependencyMapping


@pytest.fixture
def project():
    x = MagicMock(spec=Project)
    x.root = MagicMock(spec=Path)
    x.core = MagicMock(spec=Core)
    x.core.ui = MagicMock(spec=UI)
    return x


def test_register_pdm_plugin():
    core = MagicMock(spec=Core)
    register_pdm_plugin(core)
    # As function has no implementation currently, nothing to assert


def test_resolve_file_path(project: MagicMock):
    project.root.joinpath.return_value = Path("/path/to/project/test.py")
    file_path = resolve_file_path(project.root, "test.py")
    assert str(file_path) == "/path/to/project/test.py"
    project.root.joinpath.assert_called_once_with("test.py")


@patch("sync_pre_commit_lock.load_config")
def test_on_pdm_lock_check_pre_commit(mock_load_config: MagicMock, project: MagicMock):
    mock_load_config.return_value = SyncPreCommitLockConfig(disable_sync_from_lock=True)
    resolution = {
        "some-library": Candidate(NamedRequirement("some-library"), "1.0.0", "https://example.com/some-library")
    }
    on_pdm_lock_check_pre_commit(project, dry_run=False, resolution=resolution)
    mock_load_config.assert_called_once()
    project.core.ui.echo.assert_called_once_with("Sync pre-commit lock is disabled", verbosity=Verbosity.DEBUG)


@patch("sync_pre_commit_lock.load_config")
def test_on_pdm_lock_check_pre_commit_dry_run(mock_load_config: MagicMock, project: MagicMock):
    mock_load_config.return_value = SyncPreCommitLockConfig(disable_sync_from_lock=False)
    resolution = {
        "some-library": Candidate(NamedRequirement("some-library"), "1.0.0", "https://example.com/some-library")
    }
    on_pdm_lock_check_pre_commit(project, dry_run=True, resolution=resolution)
    mock_load_config.assert_called_once()


@patch("sync_pre_commit_lock.yaml.safe_load")
@patch("builtins.open", new_callable=MagicMock)
def test_fix_pre_commit(mock_open: MagicMock, mock_load: MagicMock, project: MagicMock):
    mock_load.return_value = {"repos": [{"repo": "repo-1", "rev": "1.0.0"}, {"repo": "repo-2", "rev": "2.0.0"}]}
    to_fix = {PreCommitRepo("repo-1", "1.0.0"): "1.0.1"}
    mock_open.return_value.__enter__.return_value.readlines.return_value = [
        "repos:\n",
        "  - repo: repo-1\n",
        "    rev: 1.0.0\n",
        "  - repo: repo-2\n",
        "    rev: 2.0.0\n",
    ]
    fix_pre_commit(project, to_fix, Path("/path/to/project/.pre-commit-config.yaml"))
    mock_open.assert_called_with(Path("/path/to/project/.pre-commit-config.yaml"), "w")
    mock_load.assert_called_once()


def test_build_mapping():
    config = SyncPreCommitLockConfig()
    mapping, mapping_reverse_by_url = build_mapping(config)
    # assert correct structure of mapping and mapping_reverse_by_url based on DEPENDENCY_MAPPING


# Since `check_and_log_dependency` logs messages and modifies a dictionary, it might be tricky to test.
# However, you can test it by checking the `to_fix` dictionary after calling the function.


def test_check_and_log_dependency():
    project = Mock(spec=Project)
    pre_commit_repo = PreCommitRepo("https://myrepo.local", "1.0")
    dependency = DependencyMapping(repo="https://myrepo.local", rev="${rev}")
    dependency_locked = Mock(spec=Candidate)
    dependency_locked.name = "name"
    dependency_locked.version = "2.0"
    dependency_name = "dependency_name"
    plugin_config = SyncPreCommitLockConfig()
    to_fix = {}

    check_and_log_dependency(
        project, pre_commit_repo, dependency, dependency_locked, dependency_name, plugin_config, to_fix
    )

    # assuming the function should add something to `to_fix` under certain conditions,
    # replace this with actual expected behavior
    assert to_fix == {pre_commit_repo: "2.0"}


# For `print_to_fix_repos`, you can test it by checking if it calls `project.core.ui.echo` with the correct arguments.


def test_print_to_fix_repos(project):
    # XXX(todo): asset with capsys
    to_fix = {
        PreCommitRepo("repo1", "rev1"): "rev1_new",
        PreCommitRepo("repo2", "rev2"): "rev2_new",
    }

    print_to_fix_repos(project, to_fix)


# For `handle_fixes`, you can test it by checking if it calls `project.core.ui.echo` and `fix_pre_commit` with the correct arguments.


def test_handle_fixes(mocker: Any, project: Project):
    # echo_mock = mocker.patch('pdm.project.core.ui.echo')
    fix_pre_commit_mock = mocker.patch("sync_pre_commit_lock.fix_pre_commit")

    to_fix = {
        PreCommitRepo("repo1", "rev1"): "rev1_new",
        PreCommitRepo("repo2", "rev2"): "rev2_new",
    }
    file_path = Path("file_path")

    handle_fixes(project, to_fix, file_path)

    # echo_mock.assert_called_once_with("Pre-commit hooks have been updated to match the lockfile!")
    fix_pre_commit_mock.assert_called_once_with(project, to_fix, file_path)


# `analyze_repos` depends on other functions that could be mocked.
def test_analyze_repos(mocker: Any, project: Project):
    check_and_log_dependency_mock = mocker.patch("sync_pre_commit_lock.check_and_log_dependency")
    mapping = {"name": DependencyMapping(repo="name", rev="rev")}
    mapping_reverse_by_url = {"url": "name"}
    pre_commit_repos = {PreCommitRepo("repo", "rev")}
    resolution = {"name": Mock(spec=Candidate)}
    plugin_config = SyncPreCommitLockConfig()

    analyze_repos(
        project,
        mapping=mapping,
        mapping_reverse_by_url=mapping_reverse_by_url,
        pre_commit_repos=pre_commit_repos,
        resolution=resolution,
        plugin_config=plugin_config,
    )

    # assuming the function should call `check_and_log_dependency` once,
    # replace this with actual expected behavior
    assert check_and_log_dependency_mock.call_count == 1


# `build_pre_commit_repos` test could be based on input-output pairs.
def test_build_pre_commit_repos():
    pre_commit_data_repos = [
        {"repo": "repo1", "rev": "rev1"},
        {"repo": "repo2", "rev": "rev2"},
    ]

    pre_commit_repos = build_pre_commit_repos(pre_commit_data_repos)

    # it should return a set of PreCommitRepo objects based on `pre_commit_data`
    assert pre_commit_repos == {PreCommitRepo("repo1", "rev1"), PreCommitRepo("repo2", "rev2")}


# `load_pre_commit_data` reads from a file, so you need to mock the `open` function.
@patch("builtins.open", new_callable=mock_open, read_data="repos:\n- repo: repo1\n  rev: rev1")
def test_load_pre_commit_data(mock_file):
    file_path = Path("path_to_file")
    pre_commit_data = load_pre_commit_data(file_path)

    # it should return a dictionary based on the YAML content of the file
    assert pre_commit_data == {"repos": [{"repo": "repo1", "rev": "rev1"}]}
