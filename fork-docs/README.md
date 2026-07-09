# Fork Documentation

This directory contains documentation for the `yuriever/claude-board` fork. It is intentionally tracked in Git because it explains local fork decisions, branching policy, and maintenance steps that future work should preserve.

These files are not upstream product documentation. Keep upstream-facing documentation under the upstream project's normal documentation directories.

## Layout

```text
fork-docs/
  README.md
  plans/
    platform-adapter-overview-and-phase-1.md
    platform-adapter-phase-2.md
  decisions/
    fork-sync-policy.md
  audits/
    current-fork-delta.md
```

## Branch Model

`master` is the fork integration branch. It carries local implementation work, including macOS support and fork documentation.

`original` is a clean mirror branch for the upstream repository. It should be updated only through GitHub's Sync fork UI, not by local commits.

The local checkout intentionally keeps only the fork remote:

```text
origin = https://github.com/yuriever/claude-board.git
```

Do not add a persistent local remote for `LukeLIN-web/claude-board`.

## Tracked And Ignored Fork Content

Tracked:

* `fork-docs/`

Ignored:

* `AGENTS.md`
* `uv.lock`
* `.env.local`
* local virtual environments, caches, logs, and generated files

## Maintenance Rule

When changing fork policy, macOS adaptation strategy, or the expected upstream sync workflow, update this directory in the same commit or in a nearby documentation commit.
