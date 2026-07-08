"""Cross-platform process primitive dispatch."""
from __future__ import annotations

import sys

from . import linux, macos


def open_files(pid: int) -> list[str]:
    """Return absolute file paths currently open by `pid`, if supported."""
    if sys.platform == "darwin":
        return macos.open_files(pid)
    if sys.platform.startswith("linux"):
        return linux.open_files(pid)
    return []
