# Current Fork Delta

This audit describes the intentional fork delta after the macOS platform adapter work.

## Reference Branches

Clean upstream mirror branch in the fork:

```text
original = bfc2de8 Detect the borderless /btw overlay on the send path too
```

Fork integration branch:

```text
master carries the fork commits listed below, plus this documentation commit.
```

## Intentional Changes On `master`

### Launcher Portability

Commit:

```text
50d055b Improve launcher portability
```

Purpose:

* Prefer `uv run` for startup.
* Fall back to a local `.venv` when `uv` is unavailable.
* Require Python 3.10 or newer.
* Parse `.env.local` as a restricted key-value file instead of executing it.
* Validate the HTTP port.
* Support detached startup through `setsid` or `nohup`.
* Keep `uvicorn.log` local and private.

Conflict risk:

* Medium to high. `run.sh` is an upstream-owned launcher file and the fork currently rewrites a large part of it.

### Platform Adapter Phase 1

Commit:

```text
4eaea95 Add platform open-files adapter
```

Purpose:

* Add `core/platform/`.
* Move Codex open-file discovery behind `platform.open_files(pid)`.
* Keep Linux behavior based on `/proc/<pid>/fd`.
* Add macOS behavior based on `lsof`.
* Keep rollout selection rules in `core/codex.py`.

Conflict risk:

* Low to medium. Most code is in new files. The existing `core/codex.py` changes are narrow call-site changes.

### Platform Adapter Phase 2

Commit:

```text
4993b8e Add platform process primitives
```

Purpose:

* Add `ProcessInfo`.
* Add platform process snapshot, cwd, and start-time primitives.
* Route Codex live discovery through the platform layer.
* Route Claude fresh-process discovery through the platform layer.
* Remove live-discovery dependence on `Path("/proc").is_dir()`.
* Add mocked tests for Linux and macOS process behavior.

Security decisions:

* macOS helper commands use `/bin/ps` and `/usr/sbin/lsof`.
* PIDs are converted through `int(pid)` before subprocess use.
* Subprocess calls use argv lists, timeouts, and no shell strings.
* `lsof` and `ps` failures fail closed instead of guessing process facts.
* Test fixtures use synthetic paths such as `/tmp/codex-home` and `/tmp/example-project`, not local usernames or machine-specific home paths.

Conflict risk:

* Low to medium. Platform code is mostly new. Existing `core/codex.py` and `core/sessions.py` changes are limited to OS primitive call sites.

### Fork Documentation

Purpose:

* Track fork-only planning, sync policy, and maintenance audits.
* Keep local fork knowledge available to future Codex threads and human review.

Conflict risk:

* Low. Documentation lives under `fork-docs/`, which upstream should not touch.

## Verification Already Performed

After Phase 2 was merged into `master`:

```sh
uv run python -m py_compile app.py core/*.py core/platform/*.py
uv run python -m unittest tests.test_codex tests.test_claude_proc tests.test_platform_process
uv run python -m unittest discover
```

Results:

* focused tests: 53 tests passed
* full discovery: 236 tests passed

Normal Codex Review and security-focused review were clean for Phase 2.

## Remaining Maintenance Risk

`run.sh` is the main remaining conflict surface. If upstream changes startup behavior often, consider moving fork-specific launch behavior into a separate fork-local script and reducing `run.sh` to a smaller wrapper or near-upstream file.
