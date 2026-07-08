"""Linux process primitives."""
from __future__ import annotations

import os


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
