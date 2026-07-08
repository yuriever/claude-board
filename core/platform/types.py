"""Shared platform primitive data types."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    ppid: int
    tty: str
    args: str
    comm: str = ""
