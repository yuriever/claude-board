# Platform Adapter Boundaries

`core/platform/` owns OS process primitives needed for live session discovery. It should stay small and primitive-only.

## In Scope

* process snapshots: pid, parent pid, tty, command name, command arguments
* process current working directory
* process start time
* open file paths for a process
* OS-specific implementations for Linux and macOS

## Out Of Scope

* deciding whether a process is Claude, Codex, or a background helper
* choosing, parsing, or ranking transcripts and rollout files
* patrol status, card state, UI labels, and product workflow rules
* tmux behavior while the tmux command interface remains sufficient
* focus behavior, terminal spawn behavior, search, and history parsing unless a concrete OS primitive is required

## Implementation Rules

* Put new OS-specific behavior in `core/platform/`.
* Touch upstream-owned modules only at narrow call sites.
* Use argv-list subprocess calls with finite timeouts.
* Convert pid inputs with `int(pid)` before subprocess or `/proc` use.
* Fail closed on missing tools, permission errors, malformed output, and vanished processes.
* Keep tests mocked; do not require real `/proc`, real `lsof`, or live Claude/Codex sessions.

## Current Status

Phase 1 and Phase 2 of the platform adapter are complete. Open follow-up work lives in `fork-docs/backlog.md`.
