# Fork Backlog

This file tracks unfinished fork follow-up work. Original implementation plans belong in `plans/original/`, short completion records belong in `plans/completed/`, and current shipped behavior belongs in `audits/current-fork-delta.md`.

## Active

### Codex Desktop Monitor

Add Codex Desktop as a separate dashboard source from Codex CLI/TUI. The next implementation should use the Desktop IPC router to create read-only live-thread cards from sanitized `thread-stream-state-changed` snapshots and patches. Plan: `plans/original/codex-desktop-monitor-phase-3.md`.

### Run Launcher Conflict Surface

`run.sh` carries useful fork behavior but is likely to conflict when upstream changes startup logic. If this becomes noisy during upstream sync, move fork-specific startup behavior into a separate script and reduce `run.sh` to a smaller wrapper.

### macOS Smoke Test

Codex CLI/TUI live-card discovery has been manually confirmed on macOS. Remaining smoke coverage should check Claude fresh-process cards, missing-permission degradation, and regressions after Phase 3.

### macOS Polling Cost

Measure the actual cost of the current `ps` and `lsof` calls only after the smoke test. Consider batched lookup or a native helper only if measured polling cost is a real problem.

## Not Planned

* Adding a persistent local remote for the original repository.
* Moving Claude/Codex product classifiers into `core/platform/`.
* Folding Codex Desktop discovery into Codex CLI/TUI tty discovery.
* Reworking tmux, focus, terminal spawn, search, or history parsing without a concrete OS primitive requirement.
