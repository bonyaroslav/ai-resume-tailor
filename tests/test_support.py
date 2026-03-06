from __future__ import annotations

import uuid
from pathlib import Path


def make_workspace_temp_dir(test_name: str) -> Path:
    root = Path("tests") / ".tmp"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{test_name}-{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=False)
    return path
