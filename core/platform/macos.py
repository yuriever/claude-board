"""macOS process primitives."""
from __future__ import annotations

import subprocess


def _parse_lsof_open_files(output: str) -> list[str]:
    """Parse `lsof -Fn` output, returning only absolute path name records."""
    paths: list[str] = []
    for raw in output.splitlines():
        line = raw.rstrip("\r\n")
        if len(line) > 1 and line[0] == "n" and line[1] == "/":
            paths.append(line[1:])
    return paths


def open_files(pid: int) -> list[str]:
    """Return absolute file paths currently open by `pid` using lsof."""
    try:
        proc = subprocess.run(
            ["lsof", "-nP", "-p", str(int(pid)), "-Fn"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return []
    if proc.returncode != 0 or not proc.stdout:
        return []
    return _parse_lsof_open_files(proc.stdout)
