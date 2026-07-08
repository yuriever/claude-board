"""Cross-platform process primitive dispatch."""
from __future__ import annotations

import sys

from . import linux, macos
from .types import ProcessInfo


def list_processes() -> dict[int, ProcessInfo]:
    """Return a snapshot of visible processes keyed by pid."""
    if sys.platform == "darwin":
        return macos.list_processes()
    if sys.platform.startswith("linux"):
        return linux.list_processes()
    return {}


def process_cwd(pid: int) -> str | None:
    """Return the process cwd when available."""
    if sys.platform == "darwin":
        return macos.process_cwd(pid)
    if sys.platform.startswith("linux"):
        return linux.process_cwd(pid)
    return None


def process_start_ms(pid: int) -> int:
    """Return process start time as epoch milliseconds, or 0 when unknown."""
    if sys.platform == "darwin":
        return macos.process_start_ms(pid)
    if sys.platform.startswith("linux"):
        return linux.process_start_ms(pid)
    return 0


def open_files(pid: int) -> list[str]:
    """Return absolute file paths currently open by `pid`, if supported."""
    if sys.platform == "darwin":
        return macos.open_files(pid)
    if sys.platform.startswith("linux"):
        return linux.open_files(pid)
    return []
