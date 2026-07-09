# Current Fork Delta

This audit summarizes the intentional delta carried by `master` relative to the clean upstream mirror branch `original`.

## Reference

```text
original = bfc2de8 Detect the borderless /btw overlay on the send path too
```

`master` carries the fork changes below.

## Delta

### Launcher Portability

```text
50d055b Improve launcher portability
```

`run.sh` now prefers `uv run`, falls back to `.venv`, requires Python 3.10 or newer, parses `.env.local` without executing it, validates the HTTP port, and keeps detached startup logs local.

Conflict risk: medium to high. `run.sh` is upstream-owned and remains the largest merge-conflict surface.

### Platform Adapter Phase 1

```text
4eaea95 Add platform open-files adapter
```

Codex rollout open-file discovery now goes through `core.platform.open_files(pid)`. Linux keeps `/proc/<pid>/fd`; macOS uses `lsof`. Rollout selection remains in `core/codex.py`.

Conflict risk: low to medium. Most code is new under `core/platform/`; the `core/codex.py` change is a narrow call-site change.

### Platform Adapter Phase 2

```text
4993b8e Add platform process primitives
```

Live Codex and fresh Claude process discovery now use platform primitives for process snapshots, cwd, and start time. Linux keeps `/proc` behavior; macOS uses `ps` and `lsof` with argv-list subprocess calls, timeouts, integer pid conversion, and fail-closed parsing.

Conflict risk: low to medium. Existing `core/codex.py` and `core/sessions.py` changes stay near OS primitive call sites.

### Fork Documentation

`fork-docs/` records fork policy, current delta, remaining follow-up work, and historical implementation plans.

Conflict risk: low. This directory is fork-owned.

## Verification

Latest full verification after the platform adapter work:

```sh
uv run python -m py_compile app.py core/*.py core/platform/*.py
uv run python -m unittest tests.test_codex tests.test_claude_proc tests.test_platform_process
uv run python -m unittest discover
```

Results:

* focused tests: 53 tests passed
* full discovery: 236 tests passed

Normal Codex Review and security-focused review were clean for Phase 2.

Open follow-up work is tracked in `fork-docs/backlog.md`.
