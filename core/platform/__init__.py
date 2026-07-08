"""Narrow platform adapters used by core modules."""
from __future__ import annotations

from .process import list_processes, open_files, process_cwd, process_start_ms
from .types import ProcessInfo

__all__ = [
    "ProcessInfo",
    "list_processes",
    "open_files",
    "process_cwd",
    "process_start_ms",
]
