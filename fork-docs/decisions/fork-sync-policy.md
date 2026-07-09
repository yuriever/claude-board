# Fork Sync Policy

## Repositories

```text
original repository: https://github.com/LukeLIN-web/claude-board
fork repository:     https://github.com/yuriever/claude-board
local remote:        origin = https://github.com/yuriever/claude-board.git
```

Do not add a persistent local remote for `LukeLIN-web/claude-board`. Local commands should stay scoped to the fork.

## Branches

`original` is the clean upstream mirror branch inside the fork repository. It is updated only through GitHub's Sync fork UI while the `original` branch is selected. Do not commit local work on `original`.

`master` is the fork integration branch. Local implementation work, fork documentation, and conflict resolution happen on `master`.

## Sync Workflow

1. On GitHub, open `yuriever/claude-board`.
2. Select `original`.
3. Click `Sync fork`.
4. If the sync succeeds, update local state and merge into `master`:

```sh
git fetch origin
git switch master
git merge origin/original
uv run python -m unittest discover
git push origin master
```

If GitHub cannot sync `original` cleanly, stop and handle the mirror problem before touching `master`.

## Safety Checks

Before committing, confirm the branch is `master`:

```sh
git status --short --branch
```

Expected development branch:

```text
## master...origin/master
```

Never commit when the branch header says:

```text
## original
```
