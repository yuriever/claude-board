# Fork Documentation

This directory tracks maintenance knowledge for the `yuriever/claude-board` fork. It is not upstream product documentation.

## Files

* `decisions/fork-sync-policy.md`: branch and remote policy for keeping the fork close to upstream without adding a persistent upstream remote.
* `decisions/platform-adapter-boundaries.md`: current rules for what belongs in `core/platform/` and what stays in product modules.
* `audits/current-fork-delta.md`: the current intentional delta carried by `master` relative to `original`.
* `backlog.md`: open follow-up work that is not part of the completed platform-adapter phases.
* `plans/original/`: archived original long-form implementation plans.
* `plans/completed/`: short completion summaries for finished implementation phases.

## Rules

* Put durable fork decisions under `decisions/`.
* Put current branch delta and verification state under `audits/`.
* Put unfinished follow-up work in `backlog.md`.
* Keep original implementation plans under `plans/original/` as historical archives.
* Keep short completion records under `plans/completed/`.
