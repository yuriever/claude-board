"""Linux process primitives."""
from __future__ import annotations

import os
import subprocess

from .types import ProcessInfo


def _parse_ps_processes(output: str) -> dict[int, ProcessInfo]:
    table: dict[int, ProcessInfo] = {}
    for line in output.splitlines():
        parts = line.split(None, 4)
        if len(parts) < 5:
            continue
        try:
            pid, ppid = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        table[pid] = ProcessInfo(
            pid=pid,
            ppid=ppid,
            tty=parts[2],
            comm=parts[3],
            args=parts[4],
        )
    return table


def list_processes() -> dict[int, ProcessInfo]:
    """Return visible process facts from a single ps snapshot."""
    try:
        proc = subprocess.run(
            ["ps", "-eo", "pid=,ppid=,tty=,comm=,args="],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            text=True,
            timeout=5,
        )
    except Exception:
        return {}
    if proc.returncode != 0 or not proc.stdout:
        return {}
    return _parse_ps_processes(proc.stdout)


def process_cwd(pid: int) -> str | None:
    """Return /proc/<pid>/cwd, or None when unavailable."""
    try:
        return os.readlink(f"/proc/{int(pid)}/cwd")
    except Exception:
        return None


def process_start_ms(pid: int) -> int:
    """Approximate process start time from /proc/<pid> directory mtime."""
    try:
        return int(os.stat(f"/proc/{int(pid)}").st_mtime * 1000)
    except Exception:
        return 0


def open_files(pid: int) -> list[str]:
    """Return absolute file paths currently open by `pid`.

    Linux exposes file descriptors as symlinks under /proc/<pid>/fd. Non-file
    descriptors resolve to values such as socket:[...], which are intentionally
    excluded so callers receive paths only.
    """
    try:
        fd_dir = f"/proc/{int(pid)}/fd"
        names = os.listdir(fd_dir)
    except Exception:
        return []

    paths: list[str] = []
    for name in names:
        try:
            target = os.readlink(os.path.join(fd_dir, name))
        except Exception:
            continue
        if target.startswith("/"):
            paths.append(target)
    return paths
