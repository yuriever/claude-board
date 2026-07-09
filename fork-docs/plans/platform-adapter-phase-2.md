# Platform Adapter Phase 2 Plan

This is the handoff plan for the second platform-adapter implementation phase in this fork. Phase 1 already added `core/platform.open_files(pid)` and migrated Codex rollout open-file discovery away from direct `/proc/<pid>/fd` access. Phase 2 should migrate the remaining process primitives that still keep live discovery Linux-only.

Keep this phase focused on live process discovery. Do not move tmux behavior, focus behavior, terminal spawn behavior, shell counting, search, history parsing, or Claude/Codex product classifiers unless a narrow call-site adjustment is required by the process adapter.

## Objective

Make live Codex and fresh Claude process discovery work on macOS by moving these OS-level primitives into `core/platform/`:

* batched process snapshot
* process current working directory
* process start time

The platform layer must stay primitive-only. It returns process facts; `core/codex.py` and `core/sessions.py` keep the business rules about what counts as Codex, what counts as Claude, how transcripts are matched, and how cards are classified.

## Current Linux-Only Call Sites

Codex:

* `core/codex.py:_proc_table()` shells out to `ps -eo pid=,ppid=,tty=,args=`.
* `core/codex.py:_proc_start_ms(pid)` reads `/proc/<pid>` mtime.
* `core/codex.py:list_codex_windows()` returns `[]` when `Path("/proc").is_dir()` is false.
* `core/codex.py:list_codex_windows()` reads `/proc/<pid>/cwd`.

Claude:

* `core/sessions.py:_proc_start_ms(pid)` reads `/proc/<pid>` mtime.
* `core/sessions.py:list_claude_proc_windows()` returns `[]` when `Path("/proc").is_dir()` is false.
* `core/sessions.py:list_claude_proc_windows()` shells out to `ps -eo pid=,tty=,args=`.
* `core/sessions.py:list_claude_proc_windows()` reads `/proc/<pid>/cwd`.

`core/sessions.py:get_tty(pid)` currently uses `ps -o tty= -p <pid>`. This is already cross-platform enough for now and does not need to be migrated in Phase 2 unless doing so falls out naturally without broad churn.

## Public API To Add

Extend `core/platform/process.py` and the platform backends with:

```python
from dataclasses import dataclass


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
```

Keep the existing `open_files(pid) -> list[str]` API.

Export all public names through `core/platform/__init__.py`.

## Platform Implementations

### Linux

Use the existing behavior as the compatibility baseline:

* `list_processes()` should call `ps -eo pid=,ppid=,tty=,comm=,args=` or an equivalent parseable command. Preserve command arguments exactly as much as practical.
* `process_cwd(pid)` should read `/proc/<pid>/cwd` and return `None` on any error.
* `process_start_ms(pid)` should return `int(os.stat(f"/proc/{pid}").st_mtime * 1000)` or `0` on any error.
* `open_files(pid)` remains the Phase 1 implementation.

### macOS

Use safe subprocess calls with argv lists, integer pid conversion, timeouts, and no shell interpolation:

* `list_processes()` can start with BSD `ps`, preferably `ps -axo pid=,ppid=,tty=,comm=,command=`. If parsing `comm` and `command` together becomes fragile, it is acceptable to use `ps -axo pid=,ppid=,tty=,command=` and leave `comm=""` for Phase 2, as long as Codex and Claude discovery still have `args`.
* `process_cwd(pid)` should use `lsof -a -p <pid> -d cwd -Fn` and parse the first absolute `n...` record. Return `None` on missing `lsof`, permission denial, nonzero exit, empty output, or malformed output.
* `process_start_ms(pid)` should use `ps -o lstart= -p <pid>` and parse the timestamp to epoch milliseconds. Return `0` on parse failure, missing process, or nonzero exit.
* `open_files(pid)` remains the Phase 1 implementation.

The macOS implementation can be optimized later with `proc_pidinfo` or batched cwd/start-time lookup. Phase 2 should favor a small correct implementation with timeouts over a large native helper.

## Migration Order

### Commit 1: Add Process Primitives

Add `ProcessInfo`, `list_processes`, `process_cwd`, and `process_start_ms` to `core/platform/`. Add unit tests for parser and failure behavior. This commit may touch:

* `core/platform/__init__.py`
* `core/platform/process.py`
* `core/platform/linux.py`
* `core/platform/macos.py`
* tests covering platform parsing

Do not migrate `core/codex.py` or `core/sessions.py` in this commit unless the implementation thread decides one commit is cleaner. If one commit is used for all Phase 2 work, keep changes staged and reviewed as one coherent phase.

### Commit 2: Migrate Codex Live Discovery

Replace `core/codex.py:_proc_table()` internals or callers with `platform.list_processes()`. Remove the `Path("/proc").is_dir()` gate from `list_codex_windows()` and let an empty process table degrade to `[]`.

Replace direct `/proc/<pid>/cwd` reads with `platform.process_cwd(pid)`.

Replace `_proc_start_ms(pid)` internals with `platform.process_start_ms(pid)`, or remove the local helper if doing so stays small.

Keep these Codex behaviors unchanged:

* group interactive Codex processes by controlling tty
* skip background Codex subcommands
* show a just-launched live Codex card even before a rollout exists
* attach the newest open rollout when available
* keep `_newest_rollout_from_paths(...)` in `core/codex.py`

### Commit 3: Migrate Claude Fresh Process Discovery

Replace the `Path("/proc").is_dir()` gate in `core/sessions.py:list_claude_proc_windows()` with a platform process snapshot check. Empty snapshot means `[]`.

Replace the local `ps -eo pid=,tty=,args=` scan with `platform.list_processes()`.

Replace direct `/proc/<pid>/cwd` reads with `platform.process_cwd(pid)`.

Replace `_proc_start_ms(pid)` internals with `platform.process_start_ms(pid)`, including the use in `list_windows()` for live session files.

Keep these Claude behaviors unchanged:

* `_parse_claude_proc(...)` stays in `core/sessions.py`
* known pid, known tty, and known session-id dedupe remain unchanged
* cwd visibility filters remain unchanged
* fresh spawn transcript discovery remains unchanged
* `--resume <id>` fork adoption remains unchanged
* cards seeded as `waiting` with `waiting_for="dialog open"` remain unchanged

It is acceptable to collapse Commit 2 and Commit 3 into one commit if the diff stays small and tests remain clear. Prefer multiple commits if that makes review easier.

## Tests To Add Or Update

Use mocked subprocess and filesystem calls. Do not require a real `/proc`, real `lsof`, a live Codex process, or a live Claude process.

Required tests:

* platform `ProcessInfo` parsing handles normal `ps` output and malformed rows.
* macOS cwd parser extracts the absolute `n...` cwd record and ignores non-path records.
* macOS cwd returns `None` on missing `lsof`, nonzero exit, empty output, or malformed output.
* macOS start-time parser returns epoch milliseconds for a representative `lstart` string and `0` for bad output.
* Codex `list_codex_windows()` uses the platform snapshot on non-Linux without a `/proc` gate. Mock `core.codex.platform_process` functions and verify a just-launched Codex process still becomes a card.
* Codex card cwd comes from `platform.process_cwd(pid)` when no rollout is attached, and falls back to rollout metadata when a rollout exists.
* Claude `list_claude_proc_windows()` uses the platform snapshot without a `/proc` gate. Existing Linux-only skipped tests should become pure mocked tests where practical.
* Claude process cwd comes from `platform.process_cwd(pid)`, and a `None` cwd degrades to `""` without crashing.
* Existing tests for transcript matching, resume fork adoption, and rollout selection remain green.

Suggested files:

* Add `tests/test_platform_process.py` for platform primitives.
* Update `tests/test_codex.py` for Codex process snapshot behavior.
* Update `tests/test_claude_proc.py` to remove Linux-only skips where the test can now be mocked.

## Verification Commands

Run these after each implementation pass:

```sh
uv run python -m py_compile app.py core/*.py core/platform/*.py
uv run python -m unittest tests.test_codex tests.test_claude_proc
uv run python -m unittest discover
```

If `uv run python -m unittest discover` fails because of unrelated existing environment problems, report the exact failure and still run the focused tests. Prefer fixing genuine failures introduced by Phase 2.

## Review Loop

After each coherent implementation pass:

1. Run the test commands above.
2. Run normal Codex Review using `$codex-review`, preferably `codex review --uncommitted` before committing or `codex review --commit <sha>` after committing.
3. Run a security-focused Codex Review. If the CLI does not support a custom security prompt for the selected review mode, run a second review with a clearly security-focused title/prompt in the thread and report the limitation.
4. Fix every valid finding.
5. Repeat tests and both reviews until there are no new findings.
6. Commit only after tests and both reviews are clean.

Each commit should represent an independent feature slice or the full Phase 2 if the final diff is still compact.

## Security Rules

* Convert pid arguments with `int(pid)` before passing them to subprocess calls.
* Use subprocess argv lists, never shell strings, for `ps` and `lsof`.
* Use `capture_output=True`, `text=True`, and finite `timeout=` values.
* Return empty values on permission errors or missing tools. Do not guess a cwd, transcript, or start time.
* Do not expose stderr from `lsof` or `ps` in UI fields.
* Do not follow or parse arbitrary paths in the platform layer except for `/proc` links on Linux and `n...` records returned by `lsof`.
* Keep all transcript selection in the caller modules, not the platform layer.

## Out Of Scope

* Migrating `core/tmux.py`
* Reworking focus behavior
* Reworking terminal spawn behavior
* Reworking search/history parsing
* Rewriting Claude/Codex process classifiers
* Adding a native macOS helper binary
* Optimizing macOS performance beyond reasonable command batching and timeouts

## Completion Criteria

Phase 2 is complete when:

* `core/codex.py:list_codex_windows()` no longer depends on `Path("/proc").is_dir()` or direct `/proc/<pid>/cwd`.
* `core/sessions.py:list_claude_proc_windows()` no longer depends on `Path("/proc").is_dir()` or direct `/proc/<pid>/cwd`.
* process start time reads are routed through `core.platform.process_start_ms`.
* Linux behavior remains compatible with the pre-adapter behavior.
* macOS has implementations for process snapshot, cwd, and start time that fail closed.
* Focused and full test suites pass under `uv run`.
* Normal and security-focused Codex Review are clean.
