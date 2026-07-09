# Completed Platform Adapter Phase 2

Status: complete in `4993b8e Add platform process primitives`.

## Goal

Move the remaining Linux-only live discovery primitives behind `core/platform/` so live Codex and fresh Claude process discovery can work on macOS.

## Result

* Added `ProcessInfo`.
* Added `list_processes()`, `process_cwd(pid)`, and `process_start_ms(pid)`.
* Routed Codex live discovery through the platform process snapshot, cwd, start time, and open-file APIs.
* Routed Claude fresh-process discovery through the platform process snapshot, cwd, and start-time APIs.
* Removed live-discovery dependence on `Path("/proc").is_dir()`.
* Added mocked tests for Linux and macOS process behavior.

## Safety Properties

* PIDs are converted through `int(pid)` before subprocess or `/proc` use.
* macOS helper calls use argv lists, finite timeouts, and no shell strings.
* `ps` and `lsof` failures return empty or unknown values instead of guessed process facts.
* Test fixtures use synthetic paths rather than local usernames or machine-specific home paths.

## Notes

Performance optimization is intentionally deferred until real macOS smoke testing shows a measurable polling problem. Current follow-up work is tracked in `fork-docs/backlog.md`.
