from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pytest

from sync_pre_commit_lock import PRE_COMMIT_CONFIG_FILENAME

pytest.importorskip("pdm")

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
