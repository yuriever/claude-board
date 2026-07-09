# Fork Backlog

This file tracks unfinished fork follow-up work. Original implementation plans belong in `plans/original/`, short completion records belong in `plans/completed/`, and current shipped behavior belongs in `audits/current-fork-delta.md`.

## Active

### Run Launcher Conflict Surface

`run.sh` carries useful fork behavior but is likely to conflict when upstream changes startup logic. If this becomes noisy during upstream sync, move fork-specific startup behavior into a separate script and reduce `run.sh` to a smaller wrapper.

### macOS Smoke Test

Run a real macOS smoke test with live Claude and Codex sessions. Confirm that `ps` and `lsof` permissions are sufficient, live cards appear, rollout attachment works, and missing permissions fail closed without misleading cards.

### macOS Polling Cost

Measure the actual cost of the current `ps` and `lsof` calls only after the smoke test. Consider batched lookup or a native helper only if measured polling cost is a real problem.

## Not Planned

* Adding a persistent local remote for the original repository.
* Moving Claude/Codex product classifiers into `core/platform/`.
* Reworking tmux, focus, terminal spawn, search, or history parsing without a concrete OS primitive requirement.
