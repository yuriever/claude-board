# Codex Desktop Monitor Phase 3 Plan

This is the current plan for adding Codex Desktop thread visibility to the fork. Phase 1 and Phase 2 made Codex CLI/TUI live cards work through platform process primitives. Desktop needs a different adapter because it can host multiple app-internal threads behind the GUI process and does not expose a controlling tty or rollout fd per thread.

## Objective

Add read-only Codex Desktop live-thread cards through the Desktop IPC router, while keeping the upstream conflict surface small.

The implementation should show loaded Desktop threads as separate cards with real runtime status. It must not drive Desktop, send prompts, resume threads, or use sidecar app-server guesses.

## Current Observation

The existing Codex live-card path is correct for CLI/TUI sessions:

* it finds interactive `codex` processes with a controlling tty
* it excludes background `app-server`, `mcp-server`, and `exec`
* it attaches a rollout transcript when an interactive process keeps `rollout-*.jsonl` open

Codex Desktop does not match that model:

* Desktop processes have tty `??`
* the visible app is launched under the app bundle, not as an interactive CLI
* one Desktop process can have multiple loaded threads
* tmux-backed controls do not apply

The useful Desktop source is the local IPC router socket, not a separate app-server sidecar. The socket lives under the user temp directory as `codex-ipc/ipc-<uid>.sock`. The protocol is length-prefixed JSON: four little-endian bytes for payload length, followed by a UTF-8 JSON object.

Observed safe handshake:

```json
{
    "type": "request",
    "method": "initialize",
    "version": 0,
    "params": {
        "clientType": "claude-board-monitor"
    }
}
```

The router returns a client id and broadcasts Desktop thread changes. `thread-stream-state-changed` messages include snapshot and patch forms. Snapshot messages contain `conversationState.threadRuntimeStatus`, `cwd`, `source`, `rolloutPath`, and other thread metadata. Patch messages can update fields such as runtime status and in-progress command items.

The monitor must treat the IPC stream as high-sensitivity input because full snapshots and patches can include prompts, command text, outputs, and token usage. The adapter should extract only whitelisted status metadata and discard everything else immediately.

## Scope

### In Scope

* Add a Desktop IPC monitor module, for example `core/codex_desktop.py`.
* Discover the socket path from `tempfile.gettempdir()` and `os.getuid()`.
* Connect with a timeout and register as `claude-board-monitor`.
* Reply to every `client-discovery-request` with `canHandle: false` so Desktop is not delayed by monitor participation.
* Maintain an in-memory cache of loaded Desktop thread summaries from `thread-stream-state-changed`.
* Extract only whitelisted fields: `conversationId`, `hostId`, `threadRuntimeStatus`, `cwd`, `source`, `rolloutPath`, `revision`, timestamps when present, and minimal display name if already exposed as thread metadata.
* Convert Desktop runtime status into existing dashboard vocabulary: active to busy, idle to idle, waiting flags to waiting.
* Emit read-only dashboard cards with a distinct platform value such as `codex-desktop`.
* Add focused unit tests using mocked IPC frames and mocked socket behavior.

### Out Of Scope

* App-server sidecar monitoring for Desktop live status.
* `thread/resume`, `turn/start`, `turn/steer`, `turn/interrupt`, approval responses, shell commands, file edits, or any mutating App Server or IPC method.
* Reading Chromium profile databases, browser storage, crash reports, auth tokens, or private app storage.
* GUI automation, AppleScript, screen scraping, or Accessibility control.
* Reusing tty grouping, rollout fd attachment, or Codex CLI/TUI classifiers for Desktop.
* Broad frontend redesign or shared session model refactors.

## Recommended Design

Add a product-level Desktop source module:

```text
core/codex_desktop.py
```

Suggested public API:

```python
def list_codex_desktop_windows() -> list[Window]: ...
def codex_desktop_window_dicts() -> list[dict]: ...
```

The module should keep all Desktop-specific rules outside `core/platform/`. The platform layer should not learn about Codex Desktop or the IPC protocol.

Use a small background client only while the dashboard process is running. It should reconnect with backoff if the socket is missing or Desktop restarts. On every reconnect it should rebuild state from received snapshots; if no snapshot arrives, return no Desktop cards rather than guessing from persisted metadata.

`app.py` should make a narrow call-site change in `_enriched_snapshot()`:

* collect Claude windows
* collect Codex CLI/TUI windows
* collect Codex Desktop IPC windows
* merge them before counts and sorting

Do not move large blocks of `core/codex.py`. Existing CLI/TUI behavior should remain unchanged.

### Current Codebase Integration Notes

The existing backend and frontend key live cards by numeric `pid`. Desktop cannot use the Desktop app process id because one app process can own multiple loaded threads. The first implementation should keep the current dashboard shape by assigning each Desktop thread a stable synthetic negative integer derived from `conversationId`, for example from a bounded hash. The synthetic id must be stable across polling ticks, must not collide within one cache, and must not be treated as an operating-system pid.

Desktop card dicts should also expose a real thread identifier, such as `thread_id` or `desktop_conversation_id`, and a read-only marker such as `supports_actions: False` or `read_only: True`. The frontend should use that marker, or `platform == "codex-desktop"`, to hide every control that depends on tmux, tty, process ownership, or a writable session endpoint.

Expected action behavior:

* shell descendant counts should ignore synthetic negative ids
* Desktop cards should report shell count as zero or omit it
* prompt, clear, commit, escape, close, fork, review, permission, and background-task controls should not render for Desktop cards
* backend action endpoints should fail closed if a Desktop synthetic id reaches them anyway
* timeline or transcript expansion should be disabled unless the IPC snapshot directly exposes a safe rollout path already supported by existing transcript readers
* sorting and SSE diff signatures should use only sanitized metadata, such as synthetic id, status, waiting state, and update time

## State Handling

The adapter should keep one cache entry per `conversationId`.

When a snapshot arrives, replace the cache entry with a sanitized summary extracted from `conversationState`.

When patches arrive, apply only whitelisted top-level status metadata updates. Ignore patches under `turns`, `items`, `input`, `diff`, `aggregatedOutput`, `latestTokenUsageInfo`, and any command/output fields. A patch stream without a prior snapshot should not create a full card unless it includes enough whitelisted fields to identify the thread safely.

When a thread becomes closed or disappears, prefer removing the cache entry when a clear close or disconnect signal appears. Otherwise, keep the last entry only for a short TTL so stale active cards decay to unknown or disappear.

## Card Behavior

Desktop cards should be read-only and should not show tmux controls.

Suggested fields:

* `platform`: `codex-desktop`
* `status`: `busy`, `waiting`, `idle`, or `unknown`
* `session_id`: `codex-desktop-<conversation-id>`
* `thread_id`: Desktop `conversationId`
* `desktop_conversation_id`: Desktop `conversationId`
* `pid`: stable synthetic negative integer derived from `conversationId`
* `supports_actions`: `False`
* `read_only`: `True`
* `cwd`: sanitized cwd from the snapshot
* `transcript_path`: rollout path only if the snapshot exposes it directly; do not scan Desktop storage to find it
* `tty`: empty

Controls that require tmux, tty, or direct process ownership must not appear for `codex-desktop`.

## Security Rules

* Treat every IPC frame as sensitive.
* Do not log raw frames, snapshots, patches, prompts, command text, outputs, paths from command payloads, or token usage.
* Enforce a maximum frame length before allocation.
* Use a fixed socket path derived from temp dir and uid; do not accept user-supplied socket paths in the web API.
* Use timeouts and reconnect backoff.
* Register as a monitor client only; do not advertise request handlers.
* Always answer `client-discovery-request` with `canHandle: false`.
* Return no cards on malformed frames, missing socket, version mismatch, or permission failure.

## Tests

Add `tests/test_codex_desktop.py`.

Required cases:

* IPC frame encoder and decoder handles split frames and rejects oversized or invalid frames.
* initialize response stores client id.
* `client-discovery-request` produces `canHandle: false`.
* snapshot broadcast creates one sanitized `codex-desktop` card.
* each Desktop card gets a stable synthetic negative pid derived from conversation id.
* shell count and process actions ignore Desktop synthetic pids.
* frontend or card helper state marks Desktop cards read-only and hides action controls.
* active status maps to busy, idle status maps to idle, waiting flags map to waiting.
* patch broadcast updates only whitelisted status fields.
* prompt text, command text, command output, token usage, and turn items are not stored in the cache or card dict.
* malformed JSON, missing socket, closed socket, and reconnect failure degrade to no cards.
* existing Codex CLI/TUI tests remain green.

## Verification

Run:

```sh
uv run python -m py_compile app.py core/*.py core/platform/*.py
uv run python -m unittest tests.test_codex_desktop tests.test_codex
uv run python -m unittest discover
```

Run normal Codex Review and security-focused Codex Review before committing.

## Completion Criteria

Phase 3 is complete when:

* Loaded Codex Desktop threads appear as separate read-only dashboard cards.
* Desktop cards reflect active, waiting, and idle status from IPC snapshots or whitelisted patches.
* Desktop cards remain stable across SSE polling ticks without using the Desktop app process id as the card key.
* Desktop cards do not expose tmux, prompt, close, fork, review, or background-task controls.
* No sidecar app-server is used to infer Desktop live status.
* Existing Codex CLI/TUI cards still work.
* Claude cards are unchanged.
* Raw IPC frame content is never logged or retained.
* Tests and reviews are clean.
