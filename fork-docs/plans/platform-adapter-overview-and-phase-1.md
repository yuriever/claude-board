# Platform Adapter Overview And Phase 1 Plan

This document records the fork-local plan for macOS platform adaptation. It is kept under `fork-docs/` so local fork decisions stay separate from upstream documentation and are easier to rebase around.

## Objective

Add macOS support where the current code relies on Linux-only process introspection, while keeping the upstream conflict surface small.

The adapter should cover only OS-level primitives that are required for correctness or acceptable hot-path performance. It should not become a generic place for product logic, formatting preferences, or optional cleanup.

## Current Problem

The dashboard can read historical Claude and Codex transcripts on macOS, but live session discovery is incomplete. The key failure is that live Codex and fresh Claude discovery depend on Linux `/proc`:

* Codex maps a live TUI process to its active `rollout-*.jsonl` through `/proc/<pid>/fd`.
* Claude fresh-process discovery reads `/proc/<pid>/cwd` and `/proc/<pid>` metadata before `~/.claude/sessions/<pid>.json` exists.
* Process start time is approximated from `/proc/<pid>` directory mtime.

macOS has no Linux-style `/proc`, so those live cards either disappear or lose the data needed to associate a process with a session.

## Required Platform Seams

### 1. Process Snapshot

Needed by:

* `core/sessions.py:list_claude_proc_windows`
* `core/codex.py:list_codex_windows`
* `core/codex.py:_proc_table`

Required fields:

* `pid`
* `ppid`
* `tty`
* `args`
* `comm`

Reason: both Claude and Codex live discovery need to scan interactive processes and group them by controlling tty. This should be batched instead of shelling out per process.

Linux source:

* `ps -eo pid=,ppid=,tty=,args=`
* `ps -eo pid=,ppid=,comm=`

macOS source:

* BSD `ps` with equivalent fields where available.

### 2. Process CWD

Needed by:

* `core/sessions.py:list_claude_proc_windows`
* `core/codex.py:list_codex_windows`

Linux source:

* `/proc/<pid>/cwd`

macOS source options:

* `lsof -a -p <pid> -d cwd -Fn`
* `proc_pidinfo` through a small Python/ctypes helper if `lsof` is too slow or unavailable.

Reason: cwd drives project naming, cwd filtering, and Claude transcript lookup through the project slug. Without it, fresh live cards cannot be reliably tied to their transcript directory.

### 3. Process Start Time

Needed by:

* `core/sessions.py:_proc_start_ms`
* `core/codex.py:_proc_start_ms`

Linux source:

* `/proc/<pid>` directory mtime.

macOS source options:

* `ps -o lstart= -p <pid>` parsed to epoch milliseconds.
* batched `ps` output if the per-pid call becomes measurable overhead.

Reason: start time is used as a stable card-ordering anchor and as a guard when associating a fresh process with a newly written transcript. If this is wrong, cards can jump around or adopt stale transcripts.

### 4. Open Files For PID

Needed by:

* `core/codex.py:_rollout_fd`
* `core/codex.py:_newest_rollout_in_fd_dir` replacement/seam

Linux source:

* `/proc/<pid>/fd` symlink targets.

macOS source options:

* `lsof -nP -p <pid> -Fn`
* preferably batched across candidate Codex pids if polling cost is noticeable.

Reason: a live Codex session can keep multiple rollout files open. The dashboard must pick the newest open `rollout-*.jsonl` under `~/.codex/sessions`; scanning all session files by mtime is not safe because it can attach a live card to an unrelated or stale rollout.

## Recommended Directory

Use a narrow process/platform layer:

```text
core/platform/
  __init__.py
  process.py
  linux.py
  macos.py
```

Suggested public API:

```python
@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    ppid: int
    tty: str
    args: str
    comm: str = ""


def list_processes() -> dict[int, ProcessInfo]: ...
def process_cwd(pid: int) -> str | None: ...
def process_start_ms(pid: int) -> int: ...
def open_files(pid: int) -> list[str]: ...
```

Keep this layer limited to OS primitives. It should not decide which process is Codex, which transcript is a rollout, which session is stale, or how cards are classified. Those remain business rules in `core/codex.py` and `core/sessions.py`.

## First Implementation Step

Build `core/platform/` and migrate only Codex live discovery first:

1. Add the platform API above.
2. Implement Linux using the current `/proc` behavior.
3. Implement macOS `open_files(pid)` using `lsof`.
4. Change `core/codex.py:_rollout_fd` to use `platform.open_files(pid)`.
5. Keep `_newest_rollout` selection logic in `core/codex.py`, operating on a list of open file paths instead of a `/proc/<pid>/fd` directory.
6. Add tests with fake open-file lists and fake macOS `lsof` output.

Why Codex first:

* It is the clearest macOS functional gap.
* The current Linux behavior is already isolated around `_rollout_fd`.
* The change can be made with a very small hook in `core/codex.py`.
* It avoids a larger first-step refactor of Claude process discovery.

## Second Implementation Step

Migrate the process snapshot, cwd, and start-time calls used by:

* `core/codex.py:list_codex_windows`
* `core/sessions.py:list_claude_proc_windows`

This should remove the `Path("/proc").is_dir()` gates from live discovery and replace them with platform capability checks.

Suggested capability flags:

```python
supports_process_snapshot = True
supports_process_cwd = True
supports_process_open_files = True
```

When a capability is false, the caller should degrade to historical transcript views rather than guessing.

## Do Not Abstract Yet

These areas look platform-related but should stay out of the first adapter pass:

* `core/tmux.py`: tmux has a stable cross-platform command interface when tmux is installed. The existing module already centralizes tmux calls.
* `core/search.py` and history ripgrep search: `rg` is cross-platform enough and not the source of macOS live discovery failures.
* CLI classifiers such as `_parse_claude_proc` and `_is_interactive_codex`: these are Claude/Codex product-protocol rules, not OS rules.
* POSIX liveness and termination through `os.kill(pid, 0)` and `SIGTERM`: these work on macOS and Linux for this use case.
* Focus behavior: macOS already has `scripts/focus-tty.sh` and a user override at `~/.claude/focus-tty.sh`. Move this only if a Linux focus backend is added.
* iTerm AppleScript spawn fallback: useful but secondary. The first goal is live discovery correctness, not new terminal launch behavior.

## Conflict-Control Rules

* Prefer new files under `core/platform/`.
* Touch existing upstream files only at narrow call sites.
* Do not move large blocks of `core/codex.py` or `core/sessions.py`.
* Keep tests pure and mocked; do not require real `/proc`, real `lsof`, or a live Codex process.
* Keep fork planning docs under `fork-docs/`, not upstream-facing `docs/`.

## Test Plan

Initial tests should cover:

* Linux open-file adapter returns the same newest rollout behavior as current `/proc/<pid>/fd` tests.
* macOS `lsof -Fn` parser extracts opened paths and ignores non-rollout files.
* Multiple opened rollout files choose the newest by filesystem mtime.
* Missing `lsof`, denied process access, and empty file lists return no live rollout rather than guessing.
* `list_codex_windows` still shows a just-launched Codex process without a rollout, then fills in the session id once an open rollout is found.

## Expected Outcome

After the first two steps:

* Linux behavior should remain unchanged.
* macOS should reliably show live Codex cards once the TUI has opened a rollout.
* Fresh Claude process cards on macOS should become possible once cwd/start-time are migrated.
* Future OS-specific work should have a clear home, reducing rebase conflicts with upstream.

## Handoff Checklist For Phase 1

Give a new implementation thread only the first phase. Do not migrate Claude discovery, process cwd, process start time, tmux, focus behavior, or terminal spawn behavior in this phase.

Phase 1 scope:

* Create `core/platform/` with the platform API shape from this document.
* Implement `open_files(pid)` for Linux by reading `/proc/<pid>/fd` symlink targets.
* Implement `open_files(pid)` for macOS using `lsof -nP -p <pid> -Fn`.
* Parse `lsof -Fn` by collecting only `n...` name records that represent file paths. Ignore process ids, file descriptors, types, devices, warnings, blank lines, and malformed records.
* Keep rollout selection rules in `core/codex.py`. The platform layer returns open file paths only.
* Replace the `/proc/<pid>/fd` dependency in `core/codex.py:_rollout_fd` with `platform.open_files(pid)`.
* Prefer extracting `_newest_rollout_from_paths(paths, sessions_marker)` in `core/codex.py`; keep `_newest_rollout_in_fd_dir(...)` only as a small compatibility wrapper if existing tests still need it.
* Preserve the existing behavior when a live Codex process has no rollout yet: show the live process card when possible, then attach the session id once an open rollout is found.

Suggested tests:

* Parser test: macOS `lsof -Fn` output returns only path names and ignores non-`n` records.
* Parser test: missing `lsof`, permission-denied output, nonzero exit, and empty output produce an empty list.
* Codex test: multiple open rollout paths choose the newest by filesystem mtime.
* Codex test: open non-rollout files are ignored.
* Regression test: current `/proc/<pid>/fd` fixture behavior still selects the same newest rollout on Linux.

Verification commands:

```sh
uv run python -m py_compile app.py core/*.py
uv run python -m unittest tests.test_codex
```

Review requirement:

* Run `$codex-review` with `codex review --uncommitted` after each implementation pass.
* Run a normal correctness review and a security-focused review. If either review reports a finding, fix it and repeat both review passes until there are no new findings.
* Commit only after review is clean. Each commit should represent one independent feature or phase; Phase 1 can be one commit if all of the above lands together cleanly.
