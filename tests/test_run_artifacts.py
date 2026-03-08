from __future__ import annotations

from run_artifacts import create_run_directory
from tests.test_support import make_workspace_temp_dir


def test_create_run_directory_appends_incremental_suffix() -> None:
    tmp_dir = make_workspace_temp_dir("run-artifacts")
    runs_dir = tmp_dir / "runs"

    first = create_run_directory(runs_dir, "Acme Corp")
    second = create_run_directory(runs_dir, "Acme Corp")
    third = create_run_directory(runs_dir, "Acme Corp")

    assert first.name.endswith("-1")
    assert second.name.endswith("-2")
    assert third.name.endswith("-3")
