import shutil
from pathlib import Path

import pytest


@pytest.fixture
def project(fixtures: Path, tmp_path: Path) -> Path:
    project_path = tmp_path / "project"
    shutil.copytree(fixtures / "uv_project", project_path)

    return project_path


def test_load_lock(project: Path):
    from sync_pre_commit_lock.uv import load_lock

    lock_path = project / "uv.lock"
    lock = load_lock(lock_path)

    assert len(lock) == 95
    assert "ruff" in lock
    assert lock["ruff"].version == "0.13.2"


def test_sync_pre_commit(project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture):
    from sync_pre_commit_lock.uv import sync_pre_commit

    monkeypatch.chdir(project)
    monkeypatch.setattr("sys.argv", ["sync-pre-commit-uv"])

    sync_pre_commit()

    captured = capsys.readouterr()

    assert "https://github.com/astral-sh/ruff-pre-commit \t v0.1.0 -> v0.13.2" in captured.out
