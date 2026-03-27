from __future__ import annotations

import tempfile
import uuid
from pathlib import Path


def make_workspace_temp_dir(test_name: str) -> Path:
    candidate_roots = [
        Path("tests") / ".tmp",
        Path(tempfile.gettempdir()) / "ai-resume-tailor-tests",
    ]
    for root in candidate_roots:
        try:
            root.mkdir(parents=True, exist_ok=True)
            path = root / f"{test_name}-{uuid.uuid4().hex[:8]}"
            path.mkdir(parents=True, exist_ok=False)
            return path
        except PermissionError:
            continue
    raise PermissionError("Unable to create a writable temporary test directory.")
