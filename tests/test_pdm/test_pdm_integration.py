from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pytest
from packaging import version

from sync_pre_commit_lock import PRE_COMMIT_CONFIG_FILENAME

pytest.importorskip("pdm")
from pdm.__version__ import __version__ as pdm_version

if TYPE_CHECKING:
    from pathlib import Path

    from pdm.project import Project
    from pdm.pytest import PDMCallable


@pytest.fixture
def project(project: Project, fixtures: Path) -> Project:
    shutil.copy(fixtures / "pdm_project" / PRE_COMMIT_CONFIG_FILENAME, project.root)

    return project


def test_pdm_lock(pdm: PDMCallable, project: Project):
    project.pyproject.settings["dev-dependencies"] = {"lint": ["ruff"]}
    project.pyproject.write()

    pdm("lock -v", obj=project, strict=True)

    pre_commit_config = (project.root / PRE_COMMIT_CONFIG_FILENAME).read_text()

    assert "rev: v" in pre_commit_config
    assert "rev: v0.1.0" not in pre_commit_config


def test_pdm_install(pdm: PDMCallable, project: Project):
    # Needed by pdm 2.7
    # See: https://github.com/pdm-project/pdm/issues/917
    project.pyproject.metadata["requires-python"] = ">=3.9"
    project.pyproject.write()
    pdm("add ruff==0.6.7 -v", obj=project, strict=True)

    pre_commit_config = (project.root / PRE_COMMIT_CONFIG_FILENAME).read_text()

    assert "rev: v0.6.7" in pre_commit_config


@pytest.mark.skipif(
    version.parse(str(pdm_version)) < version.parse("2.25.0"),
    reason="PDM version must be >= 2.25.0 for pylock format support",
)
def test_pdm_lock_new_format(pdm: PDMCallable, project: Project) -> None:
    """Test PDM 2.25+ with the new lock format."""
    # Set the lock format to pylock
    project.project_config["lock.format"] = "pylock"
    project.pyproject.settings["dev-dependencies"] = {"lint": ["ruff"]}
    project.pyproject.write()

    pdm("lock -v", obj=project, strict=True)
    assert project.lockfile._path.name == ("pylock.toml")

    pre_commit_config = (project.root / PRE_COMMIT_CONFIG_FILENAME).read_text()

    assert "rev: v" in pre_commit_config
    assert "rev: v0.1.0" not in pre_commit_config
