"""macOS process primitives."""
from __future__ import annotations

from datetime import datetime
import os
import subprocess

from .types import ProcessInfo

_PS = "/bin/ps"
_LSOF = "/usr/sbin/lsof"


def _parse_ps_processes(output: str) -> dict[int, ProcessInfo]:
    table: dict[int, ProcessInfo] = {}
    for line in output.splitlines():
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        try:
            pid, ppid = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        table[pid] = ProcessInfo(
            pid=pid,
            ppid=ppid,
            tty=parts[2],
            args=parts[3],
            comm="",
        )
    return table


def list_processes() -> dict[int, ProcessInfo]:
    """Return visible process facts from a single ps snapshot."""
    try:
        proc = subprocess.run(
            [_PS, "-axww", "-o", "pid=,ppid=,tty=,command="],
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


def _parse_lsof_open_files(output: str) -> list[str]:
    """Parse `lsof -Fn` output, returning only absolute path name records."""
    paths: list[str] = []
    for raw in output.splitlines():
        line = raw.rstrip("\r\n")
        if len(line) > 1 and line[0] == "n" and line[1] == "/":
            paths.append(line[1:])
    return paths


def _parse_lsof_cwd(output: str) -> str | None:
    """Parse `lsof -Fn` cwd output, returning the first absolute name record."""
    for raw in output.splitlines():
        line = raw.rstrip("\r\n")
        if len(line) > 1 and line[0] == "n" and line[1] == "/":
            return line[1:]
    return None


def process_cwd(pid: int) -> str | None:
    """Return process cwd using lsof, or None when unavailable."""
    try:
        proc = subprocess.run(
            [_LSOF, "-a", "-p", str(int(pid)), "-d", "cwd", "-Fn"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    if proc.returncode != 0 or not proc.stdout:
        return None
    return _parse_lsof_cwd(proc.stdout)


def _parse_lstart_ms(output: str) -> int:
    line = output.strip()
    if not line:
        return 0
    try:
        started = datetime.strptime(line, "%a %b %d %H:%M:%S %Y")
    except ValueError:
        return 0
    return int(started.timestamp() * 1000)


def process_start_ms(pid: int) -> int:
    """Return process start time from ps lstart, or 0 when unavailable."""
    try:
        proc = subprocess.run(
            [_PS, "-o", "lstart=", "-p", str(int(pid))],
            capture_output=True,
            env={**os.environ, "LC_ALL": "C", "LANG": "C"},
            text=True,
            timeout=5,
        )
    except Exception:
        return 0
    if proc.returncode != 0 or not proc.stdout:
        return 0
    return _parse_lstart_ms(proc.stdout)


def open_files(pid: int) -> list[str]:
    """Return absolute file paths currently open by `pid` using lsof."""
    try:
        proc = subprocess.run(
            [_LSOF, "-nP", "-p", str(int(pid)), "-Fn"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return []
    if proc.returncode != 0 or not proc.stdout:
        return []
    return _parse_lsof_open_files(proc.stdout)
