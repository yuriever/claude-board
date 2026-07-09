# Fork Sync Policy

## Repositories

Original repository:

```text
https://github.com/LukeLIN-web/claude-board
```

Fork repository:

```text
https://github.com/yuriever/claude-board
```

The local Git configuration should only contain the fork remote:

```text
origin = https://github.com/yuriever/claude-board.git
```

Do not add a persistent `upstream` remote. This keeps local commands scoped to the fork and avoids accidental confusion between the fork and the original repository.

## Branch Roles

### `original`

`original` is the clean upstream mirror branch inside the fork repository.

Rules:

* Do not commit local fork work on `original`.
* Do not use `original` as a development branch.
* Update `original` only with GitHub's Sync fork UI while the `original` branch is selected.
* If GitHub reports a conflict while syncing `original`, stop and resolve the upstream mirror problem explicitly before touching `master`.

### `master`

`master` is the fork integration branch.

Rules:

* Commit local implementation work here.
* Commit fork documentation here.
* Merge `origin/original` into `master` after syncing the fork through GitHub.
* Resolve all merge conflicts on `master`, never on `original`.

## Upstream Sync Workflow

1. On GitHub, open `yuriever/claude-board`.
2. Select the `original` branch.
3. Click `Sync fork`.
4. If GitHub can fast-forward or update the branch cleanly, accept the update.
5. In the local checkout, run:

```sh
git fetch origin
git switch master
git merge origin/original
uv run python -m unittest discover
```

6. Resolve conflicts on `master` if needed.
7. Push `master` back to the fork:

```sh
git push origin master
```

## Why This Policy Exists

This fork carries local macOS support and launcher improvements while the original repository can continue to evolve. Keeping a clean `original` branch inside the fork makes upstream changes visible without adding a persistent local remote for the original repository.

The model intentionally separates:

* upstream mirror state: `original`
* fork product state: `master`
* local-only agent or environment state: ignored files such as `AGENTS.md`, `uv.lock`, `.env.local`, caches, and logs

## Safety Checks

Before committing:

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
