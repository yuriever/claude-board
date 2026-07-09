# Codex Desktop IPC Probe

Date: 2026-07-09

## Objective

Check whether Codex Desktop exposes live thread state through a local IPC path, without using `thread/resume`, sidecar app-server inference, GUI automation, or mutating commands.

## Result

The Desktop IPC route is viable for read-only live status.

Codex Desktop owns a Unix socket under the user temp directory:

```text
codex-ipc/ipc-<uid>.sock
```

The protocol is length-prefixed JSON: a four-byte little-endian payload length followed by one UTF-8 JSON object. A monitor client can register with:

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

After initialization, the monitor receives `thread-stream-state-changed` broadcasts. A short local probe received multiple loaded Desktop thread snapshots, including idle threads and the currently active thread. Snapshot data included runtime status, cwd, source, rollout path, and revision metadata.

## Important Safety Finding

The broadcast payloads can also include prompts, command text, command output, token usage, and turn items. A production adapter must never log or retain raw IPC frames. It should extract a small allowlist of metadata fields and discard the rest immediately.

The probe also received `client-discovery-request` messages such as `ide-context`. A monitor that does not implement request handlers must respond with `canHandle: false`; otherwise Desktop may wait for request discovery timeouts.

## What This Replaces

This route is stronger than the previous sidecar app-server idea. A separate app-server can list persisted thread metadata, but it does not share Desktop's in-memory loaded status. The IPC router broadcasts the Desktop app's own live state.

## Recommended Next Step

Implement Phase 3 from `fork-docs/plans/original/codex-desktop-monitor-phase-3.md`: a read-only `core/codex_desktop.py` adapter with sanitized in-memory state, no mutating IPC methods, and focused tests for frame parsing, status mapping, and sensitive-field dropping.
