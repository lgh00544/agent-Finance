"""Backend app package bootstrap."""
from __future__ import annotations

import sys
from pathlib import Path


def _detect_project_root() -> Path | None:
    here = Path(__file__).resolve()
    for candidate in (here.parents[2], here.parents[1]):
        if (candidate / "agent_prompts").is_dir():
            return candidate
    return None


_PROJECT_ROOT = _detect_project_root()
if _PROJECT_ROOT is not None:
    project_root = str(_PROJECT_ROOT)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
